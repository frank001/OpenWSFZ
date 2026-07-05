using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Tests for the native shim's session-scoped callsign hash table
/// (f-001-hashed-callsign-resolution, shim 20260031).
///
/// <para>
/// A Type 4 message announces a nonstandard/compound callsign (e.g. a fictional
/// <c>PJ4/K1ABC</c>-shaped call) in full text; a later Type 1/2/3 message can then
/// reference that callsign cheaply via its 22-bit hash. Resolving the hash requires the
/// native decoder to remember hash→callsign mappings <em>across</em> separate
/// <see cref="Ft8LibInterop.DecodeAll"/> calls — previously the table was destroyed at
/// the end of every call, so this never worked. These tests exercise the real native
/// shim directly (no mocking) via two independent tools:
/// <list type="bullet">
///   <item><see cref="TestFt8Encoder.PackType4CqAnnounce"/> — hand-packs a genuine
///     Type 4 wire signal (the shim's own <c>ft8_encode_message</c> cannot produce one
///     for well-formed callsigns; see that method's doc comment).</item>
///   <item><see cref="Ft8LibInterop.EncodeMessage"/> — the real native encoder, used for
///     Type 1 hash-reference messages: <c>pack28</c> already falls back to a 22-bit hash
///     for any callsign that isn't a standard 6-character basecall shape.</item>
/// </list>
/// </para>
///
/// <para>
/// <strong>Shared native state:</strong> the hash table under test is a process-global
/// native static, shared by every test in this assembly for the life of the test
/// process (there is no reset entry point — deliberately: design.md's Migration Plan
/// calls for no new P/Invoke surface). Test-suite parallelization is disabled
/// assembly-wide (<c>AssemblyInfo.cs</c>) specifically so every test that touches
/// <see cref="Ft8LibInterop.DecodeAll"/>/<see cref="Ft8LibInterop.EncodeMessage"/>
/// observes a single, serialised view of this table — otherwise two test classes
/// racing on the same unsynchronized native struct could corrupt it or produce flaky
/// failures. All fictional callsigns here use unique names not used elsewhere in the
/// suite (NFR-021: Q-prefix synthetic calls only).
/// </para>
/// <para>
/// <strong>Run-order pin (dev-tasks/2026-07-05-f-003-ap-assist-flaky-decode-test.md):</strong>
/// this class is deliberately assigned to the
/// <see cref="HashTableSaturationCollectionDefinition"/> collection, which
/// <see cref="RunHashTableSaturationCollectionLastOrderer"/> always schedules last in the
/// assembly. <see cref="HashTableSaturation_RejectsNewEntriesOnceFull_ExistingEntriesSurvive"/>
/// below deliberately and permanently fills the 256-slot table to capacity — once it runs,
/// every later test that needs a fresh hash-table slot silently fails to have its entry
/// stored, for the remaining lifetime of the process. Running this whole class last (not
/// just that one test) guarantees every other test gets a non-exhausted table first,
/// regardless of xUnit's otherwise-unstable cross-class execution order. See that orderer's
/// doc comment (<c>HashTableSaturationCollection.cs</c>) for the full root-cause writeup —
/// this was the actual cause of the f-003 co-channel AP-decode test's flakiness, not the
/// LDPC/decode-margin timing sensitivity originally suspected.
/// </para>
/// </summary>
[Collection(HashTableSaturationCollectionDefinition.Name)]
public sealed class HashedCallsignResolutionTests
{
    private const double DefaultFreqHz = 1500.0;

    // ── 3.1: Cross-cycle resolution (primary spec requirement) ────────────────

    [Fact(DisplayName = "Cross-cycle: a Type 4 announcement in cycle 1 resolves a Type 1 hash reference in cycle 2")]
    public void CrossCycleResolution_Type4ThenHashReference_ResolvesFullCallsign()
    {
        const string nonstd = "Q0X7ZFZ"; // fictional, unique to this test

        // Cycle 1 — separate DecodeAll call: Type 4 announcement ("CQ Q0X7ZFZ").
        float[] pcm1 = BuildPcmFromType4(nonstd, DefaultFreqHz);
        var results1 = Ft8LibInterop.DecodeAll(pcm1);
        results1.Should().Contain(r => r.Message.Contains(nonstd),
            "cycle 1 must decode the Type 4 announcement and learn the callsign's hash");

        // Cycle 2 — a LATER, separate DecodeAll call: Type 1 message referencing the same
        // callsign's 22-bit hash (ft8_encode_message's pack28 automatically falls back to
        // the nonstandard-hash branch for any callsign that isn't a 6-char basecall shape).
        float[] pcm2 = BuildPcmFromEncodedMessage($"Q1TST {nonstd} JO33", DefaultFreqHz);
        var results2 = Ft8LibInterop.DecodeAll(pcm2);

        results2.Should().Contain(r => r.Message.Contains(nonstd),
            "the persistent hash table must resolve the hash learned in cycle 1, so cycle " +
            "2's decoded text contains the full callsign rather than the <...> placeholder " +
            "— this is the entire point of f-001-hashed-callsign-resolution");
    }

    // ── Effectiveness gap-closer: cross-cycle resolution through the FULL managed pipeline ──
    //
    // Every test above drives Ft8LibInterop.DecodeAll directly — proving the native table
    // mechanism is correct, but not that a resolved callsign actually reaches the
    // operator-facing layer. Ft8Decoder.DecodeAsync sits between the shim and the UI/log
    // surface, and applies IsPlausibleMessage/IsCallsignOversized (the D9-R3 false-positive
    // guard) to every decoded message — including a resolved cross-cycle callsign, which is
    // a literal (non-"<...>") token once resolved, exactly the shape D-011 found the guard
    // silently discarding for a *directly*-decoded literal nonstandard callsign. Nothing in
    // the existing suite chains two DecodeAsync calls to confirm the RESOLVED text (as
    // opposed to a hand-authored fake string, per D011NonstandardCallsignFpGuardTests, or an
    // unresolved "<...>" placeholder) survives the guard. This closes that gap.

    [Fact(DisplayName = "Cross-cycle resolution survives the full managed pipeline: DecodeAsync (real interop) in cycle 2 surfaces the resolved callsign, not a placeholder and not filtered by the D9-R3 guard")]
    public async Task CrossCycleResolution_ThroughManagedDecodeAsync_ResolvedCallsignReachesOperatorFacingLayer()
    {
        const string nonstd = "Q0MGDTST"; // fictional, 8 chars, unique to this test

        var clock = new FakeClock(new DateTime(2026, 7, 4, 20, 0, 0, DateTimeKind.Utc));

        // Cycle 1 — through Ft8Decoder.DecodeAsync (real interop): Type 4 announcement.
        var decoder1 = new Ft8Decoder(clock);
        float[] pcm1 = BuildPcmFromType4(nonstd, DefaultFreqHz);
        var results1 = await decoder1.DecodeAsync(pcm1, CancellationToken.None);
        results1.Select(r => r.Message).Should().Contain(m => m.Contains(nonstd),
            "cycle 1 must decode the Type 4 announcement through the managed layer, " +
            "surviving IsPlausibleMessage exactly as D011NonstandardCallsignFpGuardTests " +
            "proves for a single cycle");

        // Cycle 2 — a separate Ft8Decoder instance and a separate DecodeAsync call (the
        // hash table is a process-global native static, so persistence does not depend on
        // reusing the same managed Ft8Decoder object): Type 1 message referencing the same
        // callsign's 22-bit hash.
        var decoder2 = new Ft8Decoder(clock);
        float[] pcm2 = BuildPcmFromEncodedMessage($"Q1MGD2 {nonstd} JO33", DefaultFreqHz);
        var results2 = await decoder2.DecodeAsync(pcm2, CancellationToken.None);

        results2.Select(r => r.Message).Should().Contain(m => m.Contains(nonstd),
            "the persistent hash table must resolve the hash learned in cycle 1, AND the " +
            "resolved (now-literal, non-\"<...>\") callsign text must survive Ft8Decoder's " +
            "D9-R3 false-positive guard on its way out of DecodeAsync — proving the " +
            "feature's effectiveness through the actual code path the daemon uses, not just " +
            "the raw native P/Invoke layer this test class otherwise exercises");
        results2.Select(r => r.Message).Should().NotContain(m => m.Contains("<...>") && m.Contains("Q1MGD2"),
            "a resolved cycle-2 reference must not still show the unresolved placeholder");
    }

    // ── 3.2: Never-announced hash remains unresolved (regression / unchanged behaviour) ──

    [Fact(DisplayName = "Never-announced hash remains unresolved: an unfamiliar hash decodes to the <...> placeholder")]
    public void NeverAnnouncedHash_DecodesToPlaceholder()
    {
        const string neverAnnounced = "Q0NEVER1"; // never used as a Type 4 announcement anywhere in this suite

        float[] pcm = BuildPcmFromEncodedMessage($"Q1TST {neverAnnounced} JO33", DefaultFreqHz);
        var results = Ft8LibInterop.DecodeAll(pcm);

        results.Should().Contain(r => r.Message.Contains("<...>"),
            "a callsign hash with no prior Type 4 announcement in this process session must " +
            "decode to the unresolved placeholder, matching current WSJT-X-compatible " +
            "behaviour — no change from today's output for this case");
        results.Should().NotContain(r => r.Message.Contains(neverAnnounced),
            "the never-announced callsign's full text must never appear in decoded output");
    }

    // ── 3.3: Same-cycle resolution continues to work (pre-existing behaviour, unchanged) ──

    [Fact(DisplayName = "Same-cycle resolution: a Type 4 announcement and its hash reference in one decode cycle both resolve")]
    public void SameCycleResolution_Type4AndHashReferenceInOneCall_BothResolve()
    {
        const string nonstd = "Q0SAMECY"; // fictional, unique to this test

        float[] pcmAnnounce  = BuildPcmFromType4(nonstd, baseFreqHz: 800.0);
        float[] pcmReference = BuildPcmFromEncodedMessage($"Q1TST {nonstd} JO33", baseFreqHz: 1900.0);

        var combined = new float[180_000];
        for (int i = 0; i < combined.Length; i++)
            combined[i] = pcmAnnounce[i] + pcmReference[i];

        var results = Ft8LibInterop.DecodeAll(combined);

        results.Should().Contain(r => r.Message.Contains(nonstd) && r.Message.StartsWith("CQ"),
            "the Type 4 announcement must still decode correctly within the combined cycle");
        results.Should().Contain(r => r.Message.Contains(nonstd) && r.Message.Contains("Q1TST"),
            "same-cycle resolution (Type 4 and its hash reference both decoded within the " +
            "SAME ft8_decode_all call) must continue to succeed exactly as it did before " +
            "this change — only cross-cycle resolution was broken");
    }

    // ── 3.4: Bounded hash table growth (saturation / D3) ──────────────────────

    /// <summary>
    /// Fills the table with more than its 256-entry capacity worth of distinct nonstandard
    /// callsigns, then confirms (a) the reject-when-full guard triggers rather than
    /// corrupting existing entries, and (b) entries added early remain resolvable.
    ///
    /// <para>
    /// Because the table is process-global and shared by the whole test assembly, this test
    /// cannot assume it starts empty. It sidesteps that by adding 264 (&gt; 256) distinct new
    /// callsigns itself: even in the worst case where every other test in the suite added
    /// zero entries, 264 distinct new ones alone must exceed the 256-slot capacity, so the
    /// guard is provably exercised regardless of prior test order. (In practice this
    /// suite's total distinct-callsign footprint is small — a couple of dozen fictional
    /// Q-prefix calls across all other tests — so the first several dozen of these 264 are
    /// expected to succeed comfortably before any saturation.)
    /// </para>
    /// <para>
    /// <b>This permanently saturates the table for the rest of the process.</b> There is no
    /// reset entry point (by design), so every later test needing a fresh hash-table slot
    /// would silently fail to have its entry stored if it ran after this one. That is exactly
    /// what caused <c>F003ApAssistNonstandardCallsignDecodeTests</c>'s co-channel AP-decode
    /// test to flake under the full suite (see
    /// <c>dev-tasks/2026-07-05-f-003-ap-assist-flaky-decode-test.md</c>) — this class is now
    /// pinned to run last via <see cref="HashTableSaturationCollectionDefinition"/> /
    /// <see cref="RunHashTableSaturationCollectionLastOrderer"/> specifically so this test's
    /// deliberate saturation can never precede anything that still needs table capacity.
    /// </para>
    /// <para>
    /// Signals are batched 8-per-<see cref="Ft8LibInterop.DecodeAll"/>-call (250 Hz spacing,
    /// matching the existing FR-026 multi-signal precedent in
    /// <c>Ft8DecoderFixtureTests</c>) to keep the native-call count — and CI runtime —
    /// manageable: 264 callsigns needs only 33 announce calls + 33 verification calls.
    /// </para>
    /// </summary>
    [Fact(DisplayName = "Bounded hash table growth: table rejects new entries once full without corrupting existing ones")]
    public void HashTableSaturation_RejectsNewEntriesOnceFull_ExistingEntriesSurvive()
    {
        const int totalAttempts = 264; // > HASH_TABLE_SIZE (256); 33 batches of 8
        var callsigns = Enumerable.Range(0, totalAttempts)
            .Select(i => $"Q0{i:D5}") // 7-char, all-digits-after-Q, unique per index
            .ToArray();

        // Announce phase — batched Type 4 messages.
        foreach (var batch in callsigns.Chunk(BatchFreqsHz.Length))
        {
            float[] pcm = BuildBatchedPcm(batch, BuildPcmFromType4);
            _ = Ft8LibInterop.DecodeAll(pcm);
        }

        // Verify phase — batched Type 1 hash-reference messages.
        var resolved = new HashSet<string>();
        foreach (var batch in callsigns.Chunk(BatchFreqsHz.Length))
        {
            float[] pcm = BuildBatchedPcm(batch, (cs, f) => BuildPcmFromEncodedMessage($"Q1TST {cs} JO33", f));
            var results = Ft8LibInterop.DecodeAll(pcm);
            foreach (var cs in batch)
                if (results.Any(r => r.Message.Contains(cs)))
                    resolved.Add(cs);
        }

        resolved.Count.Should().BeLessThan(totalAttempts,
            "264 distinct new nonstandard callsigns cannot all fit in a 256-slot table — " +
            "at least one must have been rejected by the reject-when-full guard (D3), " +
            "regardless of how much capacity other tests in this process had already used");

        for (int i = 0; i < 10; i++)
            resolved.Should().Contain(callsigns[i],
                $"entry #{i} was added early in the saturation batch and must remain " +
                "resolvable and unchanged — a full table must reject NEW entries, not " +
                "corrupt or evict ones already stored");
    }

    // ── Helpers ────────────────────────────────────────────────────────────────

    private static readonly double[] BatchFreqsHz = { 500, 750, 1000, 1250, 1500, 1750, 2000, 2250 };

    /// <summary>
    /// Builds a 180 000-sample PCM buffer carrying a single Type 4 ("CQ" + full-text
    /// nonstandard callsign) announcement.
    /// </summary>
    private static float[] BuildPcmFromType4(string nonstandardCallsign, double baseFreqHz)
    {
        byte[] bits = TestFt8Encoder.PackType4CqAnnounce(nonstandardCallsign);
        byte[] info = TestFt8Encoder.AppendCrc14(bits);
        byte[] cw   = TestFt8Encoder.LdpcEncode(info);
        int[]  syms = TestFt8Encoder.BitsToSymbols(cw);
        return TestFt8Encoder.SymbolsToPcm(syms, baseFreqHz);
    }

    /// <summary>
    /// Builds a 180 000-sample PCM buffer carrying a single message encoded via the real
    /// native encoder (<see cref="Ft8LibInterop.EncodeMessage"/>) — used for standard
    /// Type 1/2 messages, including ones referencing a nonstandard callsign's 22-bit hash.
    /// </summary>
    private static float[] BuildPcmFromEncodedMessage(string message, double baseFreqHz)
    {
        var tones = new byte[Ft8LibInterop.EncodedToneCount];
        Ft8LibInterop.EncodeMessage(message, tones);
        int[] syms = new int[tones.Length];
        for (int i = 0; i < tones.Length; i++) syms[i] = tones[i];
        return TestFt8Encoder.SymbolsToPcm(syms, baseFreqHz);
    }

    /// <summary>
    /// Superimposes up to <see cref="BatchFreqsHz"/>.Length single-signal frames (each
    /// built via <paramref name="builder"/>, one per callsign) into one PCM buffer at
    /// distinct frequencies, so a single <see cref="Ft8LibInterop.DecodeAll"/> call can
    /// process an entire batch at once.
    /// </summary>
    private static float[] BuildBatchedPcm(IReadOnlyList<string> callsignBatch, Func<string, double, float[]> builder)
    {
        var combined = new float[180_000];
        for (int i = 0; i < callsignBatch.Count; i++)
        {
            float[] frame = builder(callsignBatch[i], BatchFreqsHz[i % BatchFreqsHz.Length]);
            for (int s = 0; s < combined.Length; s++)
                combined[s] += frame[s];
        }
        return combined;
    }
}
