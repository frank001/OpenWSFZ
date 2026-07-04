using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Regression coverage for D-011 — the D-009 false-positive guard
/// (<see cref="Ft8Decoder.IsPlausibleMessage"/> / <c>IsCallsignOversized</c>) was silently
/// discarding genuine literal (non-hash) nonstandard-callsign decodes.
///
/// <para>
/// Root cause: <c>IsCallsignOversized</c>'s base-callsign ceiling was 6 characters (10 with
/// a portable suffix) — correct for Type 1 packing, but the Type 4 58-bit full-text field
/// (<c>f-001-hashed-callsign-resolution</c> design.md's <c>ihashcall</c>/<c>pack58</c>
/// charset) can legitimately carry a literal, non-hash callsign up to 11 characters. A real
/// special-event station's own <c>CQ &lt;call&gt;</c> announcements and direct confirmations
/// were rejected by the guard on every cycle, while the *other* party's hash-resolved view of
/// the same conversation (<c>&lt;call&gt;</c>, always exempt) survived — see the dev-task
/// writeup for the live off-air evidence (NFR-021: no real callsigns reproduced here).
/// </para>
///
/// <para>
/// Two layers of coverage, per AC-3 (dev-task 2026-07-03-d-011): a fast unit-level suite
/// against a fake interop (mirrors <see cref="D009FpFilterTests"/>'s style, exercising the
/// exact three message shapes from the live bug report), and one true end-to-end test that
/// hand-packs a genuine Type 4 wire signal (<see cref="TestFt8Encoder.PackType4CqAnnounce"/>)
/// and drives it through the real native decoder via <see cref="Ft8Decoder"/>'s public,
/// real-interop constructor — proving the fix holds with actual native decode output, not
/// just a hand-authored fake string. All callsigns are fictional Q-prefix synthetic calls
/// per NFR-021, unique to this file (the hash table under test is a shared process-global
/// native static — see <see cref="HashedCallsignResolutionTests"/>'s remarks).
/// </para>
/// </summary>
public sealed class D011NonstandardCallsignFpGuardTests
{
    // ── Unit tests: literal nonstandard callsigns 7–11 chars must survive ────

    [Theory(DisplayName = "D011: IsPlausibleMessage accepts a literal (non-hash) CQ announcement from a 7-11 char nonstandard callsign")]
    [InlineData("CQ Q0D011A",     "7-char literal nonstandard callsign")]
    [InlineData("CQ Q0D011AB",    "8-char literal nonstandard callsign")]
    [InlineData("CQ Q0D011ABC",   "9-char literal nonstandard callsign")]
    [InlineData("CQ Q0D011ABCD",  "10-char literal nonstandard callsign")]
    [InlineData("CQ Q0D011ABCDE", "11-char literal nonstandard callsign — true protocol maximum")]
    public void IsPlausibleMessage_LiteralNonstandardCqAnnounce_ReturnsTrue(string text, string reason)
        => Ft8Decoder.IsPlausibleMessage(text, FixedCallsignGrammarStore.Default).Should().BeTrue(
               $"'{text}' is a genuine literal Type 4 CQ announcement and must not be rejected by D9-R3 ({reason})");

    [Theory(DisplayName = "D011: IsPlausibleMessage accepts a literal nonstandard callsign confirming to a hash-resolved addressee")]
    [InlineData("Q0D011FZA <...> RR73",  "7-char literal sender, hash addressee")]
    [InlineData("Q0D011FZAB <...> RR73", "8-char literal sender, hash addressee")]
    [InlineData("Q0D011FZABC <...> 73",  "9-char literal sender, hash addressee")]
    public void IsPlausibleMessage_LiteralNonstandardSenderHashAddressee_ReturnsTrue(string text, string reason)
        => Ft8Decoder.IsPlausibleMessage(text, FixedCallsignGrammarStore.Default).Should().BeTrue(
               $"'{text}' mirrors the live bug report's 'NONSTD1 <hash> RR73' shape and must not be rejected ({reason})");

    [Theory(DisplayName = "D011: IsPlausibleMessage accepts a hash-resolved sender confirming to a literal nonstandard addressee")]
    [InlineData("<...> Q0D011GZA RR73",  "7-char literal addressee, hash sender")]
    [InlineData("<...> Q0D011GZAB RR73", "8-char literal addressee, hash sender")]
    [InlineData("<...> Q0D011GZABC 73",  "9-char literal addressee, hash sender")]
    public void IsPlausibleMessage_HashSenderLiteralNonstandardAddressee_ReturnsTrue(string text, string reason)
        => Ft8Decoder.IsPlausibleMessage(text, FixedCallsignGrammarStore.Default).Should().BeTrue(
               $"'{text}' mirrors the live bug report's '<hash> NONSTD1 RR73' shape and must not be rejected ({reason})");

    // ── Integration test: DecodeAsync (fake interop) surfaces the exact bug-report shapes ──

    /// <summary>
    /// Fake interop mirroring <see cref="D009FpFilterTests"/>'s test double, used to drive
    /// <see cref="Ft8Decoder.DecodeAsync"/> without loading the native DLL.
    /// </summary>
    private sealed class FixedResultInterop(params Ft8NativeResult[] results) : IFt8NativeInterop
    {
        public int MaxDecodePasses => 2;

        public Ft8NativeResult[] DecodeAll(float[] pcm) => results;

        public int[]  GetLastPassCounts(int maxPasses)      => [results.Length, 0];
        public int[]  GetLastCandidateCounts(int maxPasses) => [results.Length, 0];
        public float  GetLastNoiseFloorDb()                  => -70.0f;
        public (float[] MeanAbs, float[] PrenormVariance, int[] FailCount) GetLastLlrStats(int maxPasses)
            => (new float[maxPasses], new float[maxPasses], new int[maxPasses]);

        public void SetApBits(byte[] mycallBits, byte[] hiscallBits) { /* no-op */ }
        public void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax) { /* no-op */ }
    }

    private static float[] BuildLoudPcm()
    {
        var pcm = new float[180_000];
        for (int i = 0; i < pcm.Length; i++)
            pcm[i] = 0.1f;
        return pcm;
    }

    [Fact(DisplayName = "D011 integration (fake interop): DecodeAsync surfaces all three live bug-report message shapes")]
    public async Task DecodeAsync_LiteralNonstandardCallsignShapes_AllSurvive()
    {
        var interop = new FixedResultInterop(
            new Ft8NativeResult { FreqHz = 1000, Dt = 0.2f, Snr =  10, Message = "CQ Q0D011ABCDE"          },
            new Ft8NativeResult { FreqHz = 1100, Dt = 0.1f, Snr =   5, Message = "Q0D011FZABC <...> RR73"  },
            new Ft8NativeResult { FreqHz = 1200, Dt = 0.3f, Snr =   7, Message = "<...> Q0D011GZABC RR73"  }
        );

        var decoder = new Ft8Decoder(
            new FakeClock(new DateTime(2026, 7, 3, 20, 0, 0, DateTimeKind.Utc)),
            logger: null,
            interop: interop);

        var results = await decoder.DecodeAsync(BuildLoudPcm(), CancellationToken.None);

        results.Select(r => r.Message).Should().BeEquivalentTo(
            ["CQ Q0D011ABCDE", "Q0D011FZABC <...> RR73", "<...> Q0D011GZABC RR73"],
            "all three literal-nonstandard-callsign message shapes from the live D-011 bug " +
            "report must reach the decode results, not be silently dropped by the D9-R3 guard");
    }

    // ── End-to-end test: genuine Type 4 wire signal through the REAL native decoder ──

    /// <summary>
    /// AC-3: proves the fix holds through <see cref="Ft8Decoder"/>'s real, production
    /// <see cref="Ft8LibInterop"/>-backed path — not just a fake interop returning a
    /// hand-authored string. Hand-packs a genuine Type 4 ("CQ" + full-text nonstandard
    /// callsign) wire signal via <see cref="TestFt8Encoder.PackType4CqAnnounce"/> (the same
    /// fixture f-001's own <see cref="HashedCallsignResolutionTests"/> uses, per the
    /// dev-task's Action 3.2), runs it through the actual LDPC/OSD native decode pipeline,
    /// and asserts the managed wrapper's D9-R3 guard lets the result through.
    /// </summary>
    [Fact(DisplayName = "D011 end-to-end: a genuine Type 4 CQ announcement for an 11-char nonstandard callsign decodes through the real native pipeline and Ft8Decoder")]
    public async Task DecodeAsync_RealNativeType4CqAnnounce_11CharCallsign_Survives()
    {
        const string nonstd = "Q0D011XYZAB"; // fictional, 11 chars, unique to this test

        byte[] bits = TestFt8Encoder.PackType4CqAnnounce(nonstd);
        byte[] info = TestFt8Encoder.AppendCrc14(bits);
        byte[] cw   = TestFt8Encoder.LdpcEncode(info);
        int[]  syms = TestFt8Encoder.BitsToSymbols(cw);
        float[] pcm = TestFt8Encoder.SymbolsToPcm(syms, baseFreqHz: 1500.0);

        var decoder = new Ft8Decoder(
            new FakeClock(new DateTime(2026, 7, 3, 20, 0, 0, DateTimeKind.Utc)));

        var results = await decoder.DecodeAsync(pcm, CancellationToken.None);

        results.Should().Contain(r => r.Message.Contains(nonstd) && r.Message.StartsWith("CQ"),
            "a genuine Type 4 CQ announcement for an 11-char literal nonstandard callsign, " +
            "decoded by the real native pipeline, must survive Ft8Decoder's D9-R3 " +
            "false-positive guard — this is the exact class of message D-011 found silently " +
            "discarded on live off-air traffic");
    }
}
