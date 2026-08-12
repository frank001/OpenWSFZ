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
/// assembly. This class consumes several hundred hash-table entries, and its opt-in
/// <see cref="HashTableSaturation_AtG2Capacity_RejectsNewEntriesWithoutCorruptingExistingOnes"/>
/// deliberately and permanently fills the table to capacity when enabled — once that runs,
/// every later test that needs a fresh hash-table slot silently fails to have its entry
/// stored, for the remaining lifetime of the process. Running this whole class last
/// guarantees every other test gets a non-exhausted table first,
/// regardless of xUnit's otherwise-unstable cross-class execution order. ⚠️ Before g2
/// (shim 20260038) capacity was 256 and the standard-suite 264-callsign test saturated it on
/// every run; at 4096 it no longer does, and only the opt-in test reaches capacity.
/// See that orderer's
/// doc comment (<c>HashTableSaturationCollection.cs</c>) for the full root-cause writeup —
/// this was the actual cause of the f-003 co-channel AP-decode test's flakiness, not the
/// LDPC/decode-margin timing sensitivity originally suspected.
/// </para>
/// </summary>
[Collection(HashTableSaturationCollectionDefinition.Name)]
[TestCaseOrderer(
    "OpenWSFZ.Ft8.Tests.RunD012RegressionAfterSaturationTestCaseOrderer", "OpenWSFZ.Ft8.Tests")]
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

    // ── 3.4: Hash-table sizing regression (g2, shim 20260038) ─────────────────

    /// <summary>
    /// <b>g2-hash-table-sizing regression (shim 20260038), the direct verification required by
    /// <c>dev-tasks/2026-08-10-g2-hash-table-sizing-and-candidate-passband.md</c> §1.4 item 1.</b>
    /// Announces 264 distinct nonstandard callsigns — comfortably more than the OLD
    /// <c>HASH_TABLE_SIZE</c> of 256 — and asserts that <em>every one</em> still resolves and
    /// that the reject-when-full counter did not move at all.
    ///
    /// <para>
    /// <b>This test previously asserted the exact opposite</b>, and its inversion is the whole
    /// point of G2 item (a). At <c>HASH_TABLE_SIZE = 256</c> the table keyed on a 10-bit bucket
    /// (1024 distinct values) placed at <c>(h10 * 23) % HASH_TABLE_SIZE</c>, which is injective
    /// only up to N = 1024 — so 256 collided 4:1 <em>by construction</em>, and these same 264
    /// callsigns forced at least 8 reject-when-full discards. At <c>HASH_TABLE_SIZE = 4096</c>
    /// they all fit with room to spare. Field symptom this fixes: <c>hashTableRejectCount</c> =
    /// 35,379 on the 2026-08-08 20m leg (against 595 across C.1's entire 68-cycle corpus).
    /// </para>
    /// <para>
    /// 🛑 <b>Scope:</b> this is a message-TEXT fix — fewer <c>&lt;...&gt;</c> placeholders where a
    /// resolvable callsign exists. It cannot change the decode count: <c>message.c</c>'s two call
    /// sites already discard a hashed callsign's resolution failure without affecting whether a
    /// decode is produced. Do not read this test as covering D-001 recall.
    /// </para>
    /// <para>
    /// The table is process-global and shared by the whole assembly, so the absolute reject count
    /// is meaningless — only the DELTA this test induces is well-defined. The suite's total
    /// distinct-callsign footprint is a couple of dozen Q-prefix calls, so 264 + that footprint
    /// remains far below 4096 and the delta must be exactly zero.
    /// </para>
    /// <para>
    /// Coverage note: because 264 no longer saturates a 4096-slot table, the D3 reject-when-full
    /// guard is no longer exercised here. That coverage moves to
    /// <c>G2HashTableSaturationOptInTests</c>, which genuinely exceeds 4096 but costs several
    /// minutes and is therefore opt-in only (same precedent as
    /// <see cref="F005RealCorpusSaturationCheck"/>). It is deliberately NOT dropped.
    /// </para>
    /// <para>
    /// Signals are batched 8-per-<see cref="Ft8LibInterop.DecodeAll"/>-call (250 Hz spacing,
    /// matching the existing FR-026 multi-signal precedent in
    /// <c>Ft8DecoderFixtureTests</c>): 264 callsigns needs only 33 announce calls + 33
    /// verification calls.
    /// </para>
    /// </summary>
    [Fact(DisplayName = "g2 sizing: 264 distinct callsigns (> the old 256 cap) all resolve with zero reject-when-full events")]
    public void HashTableSizing_264DistinctCallsigns_AllResolveWithZeroRejects()
    {
        const int totalAttempts = 264; // > the OLD HASH_TABLE_SIZE (256); 33 batches of 8
        var callsigns = Enumerable.Range(0, totalAttempts)
            .Select(i => $"Q0{i:D5}") // 7-char, all-digits-after-Q, unique per index
            .ToArray();

        // Snapshot the native reject counter immediately before the announce phase. Only the
        // DELTA is well-defined — the table is process-global and shared with the assembly.
        int rejectsBefore = Ft8LibInterop.GetHashTableRejectCount();

        // Announce phase — batched Type 4 messages. All adds (and therefore any
        // reject-when-full events) happen here; the verify phase below only performs hash
        // *lookups*, which never call hash_table_add.
        foreach (var batch in callsigns.Chunk(BatchFreqsHz.Length))
        {
            float[] pcm = BuildBatchedPcm(batch, BuildPcmFromType4);
            _ = Ft8LibInterop.DecodeAll(pcm);
        }

        int rejectsAfter = Ft8LibInterop.GetHashTableRejectCount();

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

        resolved.Count.Should().Be(totalAttempts,
            "at HASH_TABLE_SIZE = 4096 all 264 distinct nonstandard callsigns must be stored " +
            "AND resolve — this is the g2 item (a) sizing fix. At the previous 256 they could " +
            "not, because (h10 * 23) % 256 collides 4:1 by construction before the table is " +
            "even full. A shortfall here means the sizing change did not take effect (stale " +
            "libft8.dll?) or first-probe placement regressed");

        (rejectsAfter - rejectsBefore).Should().Be(0,
            "264 new callsigns plus this suite's small existing footprint sit far below the " +
            "4096-slot capacity, so no announcement may be turned away for lack of room — a " +
            "non-zero delta means the table saturated far earlier than its nominal capacity");

        for (int i = 0; i < 10; i++)
            resolved.Should().Contain(callsigns[i],
                $"entry #{i} was added early in the batch and must remain resolvable and " +
                "unchanged — later adds must not corrupt or evict earlier entries");
    }

    // ── 3.5: D-012 regression — repeat announcement of an already-known callsign after
    // saturation must not increment the reject counter ─────────────────────────────

    /// <summary>
    /// Regression test for D-012
    /// (dev-tasks/2026-07-06-d-012-hash-table-reject-count-overcounting.md): before the fix,
    /// <c>hash_table_add</c>'s full-table guard ran BEFORE the "already known" linear-probe
    /// check, so once the table saturated, EVERY call — including a re-announcement of a
    /// callsign already stored — incremented <c>g_hash_table_reject_count</c>. A real 9.5h
    /// off-air corpus replay exposed a reject-count delta of 73,627 against only 42,429 total
    /// decodes, an arithmetic impossibility that only a real-traffic replay (not this
    /// synthetic suite's unique-per-test callsigns) could surface, because a real station
    /// re-announces the same callsign many times over a long session.
    ///
    /// <para>
    /// <b>Deliberately reuses <see cref="HashTableSizing_264DistinctCallsigns_AllResolveWithZeroRejects"/>'s
    /// own guaranteed-resolvable early entry ("Q000000", its <c>callsigns[0]</c>) instead of
    /// storing a fresh callsign of its own.</b> The native hash table is process-global and never
    /// reset (design D1/D3), so depending on a sibling test's proven-present entry is more robust
    /// than assuming a fresh insert succeeds. This test is therefore pinned to run strictly AFTER
    /// that sibling test via <c>[TestCaseOrderer(...)]</c> on this class
    /// (<see cref="RunD012RegressionAfterSaturationTestCaseOrderer"/>) — xUnit does not guarantee
    /// method-execution order within a class by default.
    /// </para>
    /// <para>
    /// 🔴 <b>Coverage caveat since g2 (shim 20260038, HASH_TABLE_SIZE 256 → 4096):</b> the sibling
    /// test's 264 callsigns NO LONGER saturate the table, so this test now exercises the
    /// "already-known callsign is a no-op for the reject counter" path in the <em>non-full</em>
    /// regime only. The original D-012 bug specifically required a FULL table (the full-table
    /// guard ran before the already-known check), and that exact condition is now covered by
    /// <c>G2HashTableSaturationOptInTests</c>, which genuinely exceeds 4096 entries but costs
    /// several minutes and is opt-in only. This test is retained because the no-op assertion is
    /// still correct and cheap; it is no longer sufficient on its own to catch a D-012 regression.
    /// </para>
    /// </summary>
    [Fact(DisplayName = "D-012: re-announcing an already-known callsign does not increment the reject count (non-full regime; full-table case is opt-in)")]
    public void RepeatAnnouncement_OfAlreadyKnownCallsign_DoesNotIncrementRejectCount()
    {
        // "Q000000" == HashTableSizing_264DistinctCallsigns_AllResolveWithZeroRejects's own
        // callsigns[0] ($"Q0{0:D5}") — proven resolvable by that test's own final assertions. This
        // test relies on that sibling test having already run, enforced by this class's
        // [TestCaseOrderer] (RunD012RegressionAfterSaturationTestCaseOrderer).
        const string knownCallsign = "Q000000";

        float[] pcmVerifyBefore = BuildPcmFromEncodedMessage($"Q1D12PR {knownCallsign} JO33", DefaultFreqHz);
        var verifyBeforeResults = Ft8LibInterop.DecodeAll(pcmVerifyBefore);
        verifyBeforeResults.Should().Contain(r => r.Message.Contains(knownCallsign),
            "the sibling sizing test must have already run and stored this callsign — if " +
            "this fails, the class's [TestCaseOrderer] is not enforcing the required method order");

        int rejectsBefore = Ft8LibInterop.GetHashTableRejectCount();

        // Re-announce via a fresh Type 4 decode cycle (not a hash reference) — exactly the
        // "repeat CQ from the same station" shape a real corpus produces. This is the assertion
        // that fails on the pre-D-012-fix code.
        float[] pcmReannounce = BuildPcmFromType4(knownCallsign, DefaultFreqHz);
        var reannounceResults = Ft8LibInterop.DecodeAll(pcmReannounce);
        reannounceResults.Should().Contain(r => r.Message.Contains(knownCallsign),
            "the repeat announcement must still decode correctly");

        int rejectsAfter = Ft8LibInterop.GetHashTableRejectCount();

        (rejectsAfter - rejectsBefore).Should().Be(0,
            "D-012: re-announcing a callsign already present in the table must be a no-op " +
            "for the reject counter — only a genuinely new callsign turned away for lack of " +
            "room may increment it. (Since g2/shim 20260038 this exercises the non-full " +
            "regime; the full-table case D-012 originally regressed on is covered by the " +
            "opt-in G2HashTableSaturationOptInTests)");

        // The known callsign must still resolve correctly after the repeat announcement (the
        // no-op path only refreshes the stored hash's high bits; it must not corrupt or evict
        // the entry).
        float[] pcmVerifyAfter = BuildPcmFromEncodedMessage($"Q1D12PA {knownCallsign} JO33", DefaultFreqHz);
        var verifyAfterResults = Ft8LibInterop.DecodeAll(pcmVerifyAfter);
        verifyAfterResults.Should().Contain(r => r.Message.Contains(knownCallsign),
            "the known callsign must remain resolvable after its repeat announcement");
    }

    // ── 3.6: D3 reject-when-full guard at the g2 capacity (OPT-IN, several minutes) ──

    private const string SaturationOptInEnvVar = "OPENWSFZ_RUN_G2_SATURATION";

    /// <summary>
    /// <b>Opt-in only.</b> Preserves coverage of the D3 reject-when-full guard — and of D-012's
    /// original FULL-table condition — at the g2 capacity of <c>HASH_TABLE_SIZE = 4096</c>
    /// (shim 20260038).
    ///
    /// <para>
    /// <b>Why this exists as a separate, gated test.</b> Before g2 the table held 256 entries, so
    /// the standard-suite test could saturate it with 264 announcements in ~45 s and the guard was
    /// covered for free. At 4096 the same coverage needs &gt; 4096 distinct announcements — roughly
    /// 525 native <see cref="Ft8LibInterop.DecodeAll"/> calls, about six minutes — which is far too
    /// slow to run on every <c>dotnet test</c>. Rather than silently dropping coverage of a guard
    /// that prevents an unbounded probe loop on a full table, it moves here behind an environment
    /// variable, following the same Captain-approved opt-in precedent as
    /// <see cref="F005RealCorpusSaturationCheck"/>. Absent the variable it skips instantly.
    /// </para>
    /// <para>
    /// <b>This permanently saturates the process-global table</b> (there is no reset entry point,
    /// by design — f-001 D1/D3), so it is pinned to run strictly last, after every other test in
    /// this class, via <see cref="RunD012RegressionAfterSaturationTestCaseOrderer"/>; the class
    /// itself already runs last in the assembly via
    /// <see cref="RunHashTableSaturationCollectionLastOrderer"/>. Any test running after it would
    /// silently fail to have a new callsign stored.
    /// </para>
    /// <para>
    /// To run deliberately:
    /// <code>
    /// OPENWSFZ_RUN_G2_SATURATION=1 dotnet test -c Release --filter "DisplayName~g2 SATURATION"
    /// </code>
    /// </para>
    /// </summary>
    [Fact(DisplayName = "g2 SATURATION (opt-in): the D3 reject-when-full guard still fires at HASH_TABLE_SIZE 4096 without corrupting stored entries")]
    public void HashTableSaturation_AtG2Capacity_RejectsNewEntriesWithoutCorruptingExistingOnes()
    {
        if (Environment.GetEnvironmentVariable(SaturationOptInEnvVar) != "1")
            return; // ~6-minute test; opt-in only. See the doc comment above.

        // 4200 > HASH_TABLE_SIZE (4096), so the guard must fire regardless of how much of the
        // table this assembly's other tests had already consumed: if the table already holds X
        // entries, rejects >= 4200 - (4096 - X) >= 104. A distinct "Q9" prefix keeps these from
        // colliding with the sizing test's "Q0" series.
        const int totalAttempts = 4200;
        const int guaranteedMinimumRejects = totalAttempts - 4096; // 104

        var callsigns = Enumerable.Range(0, totalAttempts)
            .Select(i => $"Q9{i:D5}")
            .ToArray();

        int rejectsBefore = Ft8LibInterop.GetHashTableRejectCount();

        foreach (var batch in callsigns.Chunk(BatchFreqsHz.Length))
        {
            float[] pcm = BuildBatchedPcm(batch, BuildPcmFromType4);
            _ = Ft8LibInterop.DecodeAll(pcm);
        }

        int rejectsAfter = Ft8LibInterop.GetHashTableRejectCount();

        (rejectsAfter - rejectsBefore).Should().BeGreaterThanOrEqualTo(guaranteedMinimumRejects,
            $"{totalAttempts} distinct new callsigns cannot all fit in a 4096-slot table, so the " +
            "D3 reject-when-full guard must have turned away at least the overflow and the f-005 " +
            "counter must have observed every one of them");

        // Entries stored early must survive: a full table must reject NEW entries, never corrupt
        // or evict ones already present. Sampling the first batch keeps the verify phase cheap.
        var firstBatch = callsigns.Take(BatchFreqsHz.Length).ToArray();
        float[] verifyPcm = BuildBatchedPcm(
            firstBatch, (cs, f) => BuildPcmFromEncodedMessage($"Q1SAT {cs} JO33", f));
        var verifyResults = Ft8LibInterop.DecodeAll(verifyPcm);
        foreach (var cs in firstBatch)
            verifyResults.Should().Contain(r => r.Message.Contains(cs),
                $"{cs} was stored before the table filled and must remain resolvable — a full " +
                "table must reject new entries, not corrupt or evict stored ones");

        // D-012's ORIGINAL condition, which the standard-suite test can no longer reach: with the
        // table genuinely full, re-announcing an already-known callsign must still be a no-op for
        // the reject counter. Pre-fix, the full-table guard ran before the already-known probe and
        // every such re-announcement was miscounted.
        int beforeReannounce = Ft8LibInterop.GetHashTableRejectCount();
        _ = Ft8LibInterop.DecodeAll(BuildPcmFromType4(callsigns[0], DefaultFreqHz));
        int afterReannounce = Ft8LibInterop.GetHashTableRejectCount();

        (afterReannounce - beforeReannounce).Should().Be(0,
            "D-012, full-table regime: re-announcing a callsign already present must not " +
            "increment the reject counter even when the table has no room left — only a " +
            "genuinely new callsign turned away for lack of room may increment it");
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
