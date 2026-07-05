using FluentAssertions;
using OpenWSFZ.Ft8;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// End-to-end proof that AP-assisted decode (H6, D-001) succeeds for a nonstandard/compound
/// callsign QSO exchange, now that both halves of "Gap B" are in place
/// (f-003-ap-assist-nonstandard-callsigns tasks.md task 5.1):
/// <list type="bullet">
///   <item><c>f-001-hashed-callsign-resolution</c> — the native decoder's session-scoped hash
///     table, so a nonstandard callsign announced via a Type 4 message resolves to plaintext
///     when referenced by hash in a later cycle (see <see cref="HashedCallsignResolutionTests"/>).</item>
///   <item><c>f-003-ap-assist-nonstandard-callsigns</c> (this change) — <see cref="Ft8CallsignPacker.Pack28"/>
///     can now pack a nonstandard callsign into a valid AP hint instead of returning an empty
///     array, so <c>QsoAnswererService</c>/<c>QsoCallerService</c> no longer need to disable AP
///     for the whole QSO just because one party's callsign is nonstandard.</item>
/// </list>
/// This is the scenario <c>f-001</c>'s own tasks.md deferred task 6.3 originally described.
/// </summary>
/// <remarks>
/// Uses the real native decoder end to end (<see cref="Ft8Decoder"/>, the same class the daemon
/// uses) — no fake/mocked interop. See <see cref="D001H6ApDecodeTests"/> for the co-channel
/// AP-decode technique this test's fixture mirrors, and <see cref="HashedCallsignResolutionTests"/>
/// for the underlying cross-cycle hash-resolution mechanism (including its notes on the shared,
/// process-global native hash table and why assembly-wide test parallelization is disabled).
/// <para>
/// <b>Flake history (resolved, dev-tasks/2026-07-05-f-003-ap-assist-flaky-decode-test.md):</b>
/// this test failed intermittently under the full <c>OpenWSFZ.Ft8.Tests</c> suite (never in
/// isolation). Root cause, confirmed via repeated full-suite runs with TRX timeline capture:
/// <see cref="HashedCallsignResolutionTests"/>'s
/// <c>HashTableSaturation_RejectsNewEntriesOnceFull_ExistingEntriesSurvive</c> deliberately and
/// permanently fills the shared, never-reset native <c>g_session_hash_table</c> (256-slot
/// capacity) — assembly-wide test order was not stable across runs, so whenever that test
/// happened to execute before this one, this test's cycle-1 Type 4 announcement was silently
/// dropped by the shim's reject-when-full guard. Cycle 2's AP-assisted decode still succeeded
/// structurally (a failing run's actual decoded text was <c>"Q1OFZ &lt;...&gt; JO33"</c> — LDPC
/// converged fine), but the hiscall hash could never resolve to plaintext. This was <em>not</em>
/// an LDPC/decode-margin timing sensitivity, despite that being the original working theory.
/// Fixed by pinning <see cref="HashedCallsignResolutionTests"/> to always run last (see
/// <see cref="RunHashTableSaturationCollectionLastOrderer"/>) rather than by loosening this
/// test's co-channel fixture or adding a retry.
/// </para>
/// </remarks>
[Trait("Category", "Integration")]
public sealed class F003ApAssistNonstandardCallsignDecodeTests
{
    // NFR-021: fictional Q-prefix callsigns, unique to this test class.
    private const string Mycall = "Q1OFZ";
    private const string Nonstd = "Q0F003GAP"; // 9 chars — matches D-011's shape grammar

    private const double AudioFreqHz     = 1500.0;
    private const float  SignalAmplitude = 0.35f;
    private const int    TotalSamples    = 180_000;

    [Fact(DisplayName = "f-003 5.1: AP-assisted decode recovers a nonstandard-callsign co-channel message, resolved to plaintext")]
    public async Task ApDecode_NonstandardCallsignCoChannel_RecoversResolvedPlaintext()
    {
        var clock = new FakeClock(new DateTime(2026, 7, 5, 12, 0, 0, DateTimeKind.Utc));

        // Cycle 1 — announce the nonstandard callsign via a Type 4 message (f-001 prerequisite),
        // through the real managed decode path so the native hash table learns its hash.
        var announceDecoder = new Ft8Decoder(clock);
        float[] pcmAnnounce = BuildPcmFromType4(Nonstd, baseFreqHz: 800.0);
        var announceResults = await announceDecoder.DecodeAsync(pcmAnnounce, CancellationToken.None);
        announceResults.Should().Contain(r => r.Message.Contains(Nonstd),
            "cycle 1 must decode the Type 4 announcement so the native hash table learns this " +
            "callsign, exactly as HashedCallsignResolutionTests proves for f-001 alone");

        // Cycle 2 — AP-assisted co-channel decode (H6, D-001), using Pack28's extended encoding
        // (this change) to arm AP constraints for the nonstandard hiscall. Before f-003, Pack28
        // would return an empty array here and both QsoAnswererService/QsoCallerService would
        // disable AP entirely for this QSO.
        byte[] mycallBits  = Ft8CallsignPacker.Pack28(Mycall);
        byte[] hiscallBits = Ft8CallsignPacker.Pack28(Nonstd);
        mycallBits.Should().HaveCount(4, "Pack28(Q1OFZ) must succeed (standard-basecall path, unchanged)");
        hiscallBits.Should().NotBeEmpty(
            "the extended packer (f-003) must be able to pack a nonstandard callsign into a " +
            "valid AP hint, instead of returning empty and forcing AP to be disabled");

        var decoder = new Ft8Decoder(clock);
        decoder.SetApConstraints(new Ft8ApConstraints(mycallBits, hiscallBits));

        float[] pcm = BuildCoChannelFixture();
        var results = await decoder.DecodeAsync(pcm, CancellationToken.None);

        results.Should().Contain(r => r.Message.Contains(Nonstd) && r.Message.Contains(Mycall),
            "AP decode should recover the co-channel message naming both parties, and — " +
            "because cycle 1 already announced it — the nonstandard callsign must appear as " +
            "resolved plaintext, not the \"<...>\" placeholder");
    }

    // ── Fixture builders ───────────────────────────────────────────────────────

    /// <summary>
    /// Builds a 15-second (180 000-sample) PCM buffer carrying a single Type 4 ("CQ" +
    /// full-text nonstandard callsign) announcement. Mirrors
    /// <c>HashedCallsignResolutionTests.BuildPcmFromType4</c> exactly (that class's own encoder
    /// cannot be reused directly — it is a private instance helper — but the technique and
    /// underlying <see cref="TestFt8Encoder"/> calls are identical).
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
    /// Builds a 15-second co-channel fixture: two equal-amplitude signals superimposed at the
    /// same audio frequency, mirroring <c>D001H6ApDecodeTests.BuildCoChannelFixture</c>.
    /// <list type="bullet">
    ///   <item>Signal A — <c>"{Mycall} {Nonstd} JO33"</c>: hiscall is the nonstandard callsign,
    ///     recovered via AP.</item>
    ///   <item>Signal B — <c>"{Nonstd} {Mycall} RR73"</c>: callsigns swapped, so AP bits are
    ///     wrong for B — blind decode of the composite is ambiguous; AP anchors signal A.</item>
    /// </list>
    /// </summary>
    private static float[] BuildCoChannelFixture()
    {
        string messageA = $"{Mycall} {Nonstd} JO33";
        string messageB = $"{Nonstd} {Mycall} RR73";

        var tonesA = new byte[Ft8LibInterop.EncodedToneCount];
        var tonesB = new byte[Ft8LibInterop.EncodedToneCount];
        Ft8LibInterop.EncodeMessage(messageA, tonesA);
        Ft8LibInterop.EncodeMessage(messageB, tonesB);

        int[] symA = Array.ConvertAll(tonesA, static t => (int)t);
        int[] symB = Array.ConvertAll(tonesB, static t => (int)t);

        float[] pcmA = TestFt8Encoder.SymbolsToPcm(symA, AudioFreqHz, amplitude: SignalAmplitude);
        float[] pcmB = TestFt8Encoder.SymbolsToPcm(symB, AudioFreqHz, amplitude: SignalAmplitude);

        var pcm = new float[TotalSamples];
        for (int i = 0; i < TotalSamples; i++)
            pcm[i] = pcmA[i] + pcmB[i];

        return pcm;
    }
}
