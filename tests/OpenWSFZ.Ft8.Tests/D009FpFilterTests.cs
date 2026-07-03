using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Ft8;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Unit and integration tests for D-009 — OSD false-positive callsign filter.
///
/// <para>
/// The OSD fallback (shim 20260025) evaluates up to 529 trial codewords per candidate;
/// in a busy band (S5 noise-only, S8 12-signal scene) a non-trivial fraction produce a
/// valid LDPC CRC-14 by chance and decode to garbage messages.  S5 gate measured 91.67%
/// FP rate (11 FP events / 12 noise-only slots; threshold ≤ 6.0%).
/// </para>
///
/// <para>
/// Fix: three new filter rules added to <see cref="Ft8Decoder.IsPlausibleMessage"/>:
/// <list type="bullet">
///   <item>D9-R1 — reject blank / whitespace messages.</item>
///   <item>D9-R2 — reject single-token hex-dump strings ≥ 16 chars (unrecognised type).</item>
///   <item>D9-R3 — reject messages whose callsign-position token has a base length
///     exceeding 11 chars, or total length exceeding 11 chars (not valid Type 1 packing,
///     nor a valid Type 4 literal nonstandard-callsign full-text field). Raised from the
///     original 6/10-char ceiling by D-011 to admit genuine literal nonstandard callsigns
///     (up to the true 11-char protocol maximum) without reopening the OSD false-positive
///     hole for tokens that are genuinely oversized beyond that true maximum.</item>
/// </list>
/// </para>
///
/// <para>
/// All callsigns in the "accept" cases use ITU-unallocated Q-prefix per NFR-021.
/// Garbage callsigns in "reject" cases are not real assignments; they are observed
/// OSD false-positive outputs.
/// </para>
/// </summary>
public sealed class D009FpFilterTests
{
    // ── Test double ───────────────────────────────────────────────────────────

    /// <summary>
    /// Fake interop that returns a fixed set of <see cref="Ft8NativeResult"/>s,
    /// allowing precise control over the message strings returned to <see cref="Ft8Decoder"/>
    /// without loading the native DLL.
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

    // ── Helpers ───────────────────────────────────────────────────────────────

    /// <summary>Returns a 180 000-sample PCM buffer well above the silence guard (1e-6 RMS).</summary>
    private static float[] BuildLoudPcm()
    {
        var pcm = new float[180_000];
        for (int i = 0; i < pcm.Length; i++)
            pcm[i] = 0.1f;
        return pcm;
    }

    private static Ft8Decoder BuildDecoder(IFt8NativeInterop interop)
        => new(new FakeClock(new DateTime(2026, 6, 20, 10, 0, 0, DateTimeKind.Utc)),
               logger: null,
               interop: interop);

    // ── Unit tests: D9-R1 — blank / whitespace ────────────────────────────────

    [Theory(DisplayName = "D009 D9-R1: IsPlausibleMessage rejects null, empty, and whitespace-only strings")]
    [InlineData(null,    "null")]
    [InlineData("",      "empty string")]
    [InlineData("   ",   "spaces only")]
    [InlineData("\t",    "tab only")]
    public void IsPlausibleMessage_BlankOrWhitespace_ReturnsFalse(string? text, string reason)
        => Ft8Decoder.IsPlausibleMessage(text).Should().BeFalse(
               $"'{text}' is blank/whitespace and must be rejected by D9-R1 ({reason})");

    // ── Unit tests: D9-R2 — hex dump ─────────────────────────────────────────

    [Theory(DisplayName = "D009 D9-R2: IsPlausibleMessage rejects hex-dump strings (≥16 uppercase hex chars, no space)")]
    [InlineData("586A8555F2A13462F6",   "observed OSD FP — 18 hex chars")]
    [InlineData("1DA5713612BD5A3C22",   "observed OSD FP — 18 hex chars")]
    [InlineData("0000000000000000",     "16-char all-zero hex string")]
    public void IsPlausibleMessage_HexDump_ReturnsFalse(string text, string reason)
        => Ft8Decoder.IsPlausibleMessage(text).Should().BeFalse(
               $"'{text}' is a hex-dump string and must be rejected by D9-R2 ({reason})");

    // ── Unit tests: D9-R3 — oversized callsign in CQ message ─────────────────

    [Theory(DisplayName = "D009 D9-R3: IsPlausibleMessage rejects CQ messages with oversized callsigns")]
    [InlineData("CQ ETRHB0I3RYOX",  "12-char base callsign — beyond the true 11-char protocol maximum (D-011)")]
    [InlineData("CQ GKC5JNL82FWZ",  "12-char base callsign — beyond the true 11-char protocol maximum (D-011)")]
    [InlineData("CQ ELUX7QIYUCFZ",  "12-char base callsign — beyond the true 11-char protocol maximum (D-011)")]
    public void IsPlausibleMessage_CqOversizedCallsign_ReturnsFalse(string text, string reason)
        => Ft8Decoder.IsPlausibleMessage(text).Should().BeFalse(
               $"'{text}' has an oversized CQ callsign and must be rejected by D9-R3 ({reason})");

    // ── Unit tests: D9-R3 — oversized callsign in Standard QSO (sender) ──────

    [Theory(DisplayName = "D009 D9-R3: IsPlausibleMessage rejects Standard QSO with oversized sender callsign")]
    [InlineData("UDWA9WGLHXQR <...> RR73",  "12-char sender — beyond the true 11-char protocol maximum (D-011)")]
    [InlineData("DDK4NYWXBIUZ Q9XYZ RR73",  "12-char sender — beyond the true 11-char protocol maximum (D-011)")]
    [InlineData("1RY8RU98FJ9Z Q1ABC R-05",  "12-char sender — beyond the true 11-char protocol maximum (D-011)")]
    public void IsPlausibleMessage_StandardQsoOversizedSender_ReturnsFalse(string text, string reason)
        => Ft8Decoder.IsPlausibleMessage(text).Should().BeFalse(
               $"'{text}' has an oversized sender callsign and must be rejected by D9-R3 ({reason})");

    // ── Unit tests: D9-R3 — oversized callsign in Standard QSO (addressee) ───

    [Theory(DisplayName = "D009 D9-R3: IsPlausibleMessage rejects Standard QSO with oversized addressee callsign")]
    [InlineData("Q1ABC ETRHB0I3RYOX R-10",  "12-char addressee — beyond the true 11-char protocol maximum (D-011)")]
    [InlineData("Q9XYZ 1RY8RU98FJ9Z 73",    "12-char addressee — beyond the true 11-char protocol maximum (D-011)")]
    public void IsPlausibleMessage_StandardQsoOversizedAddressee_ReturnsFalse(string text, string reason)
        => Ft8Decoder.IsPlausibleMessage(text).Should().BeFalse(
               $"'{text}' has an oversized addressee callsign and must be rejected by D9-R3 ({reason})");

    // ── Unit tests: D9-R3 Gap A — 2-token messages: both tokens now checked ──────

    [Theory(DisplayName = "D009 Gap A (R2): IsPlausibleMessage rejects 2-token messages with oversized token")]
    [InlineData("<...> M5E5B91HFHLZ", "12-char token1, beyond the true 11-char protocol maximum (D-011); was not caught before Gap A fix")]
    [InlineData("<...> 7P8R9J2R3BGZ", "12-char token1, beyond the true 11-char protocol maximum (D-011)")]
    [InlineData("<...> UF5NDNNJD2PZ", "12-char token1, beyond the true 11-char protocol maximum (D-011)")]
    [InlineData("9ULLPTCDZHQR <...>", "12-char token0, beyond the true 11-char protocol maximum (D-011); hash in token1")]
    public void IsPlausibleMessage_GapA_TwoTokenOversized_ReturnsFalse(string text, string reason)
        => Ft8Decoder.IsPlausibleMessage(text).Should().BeFalse(
               $"'{text}' has an oversized token in a 2-token message and must be rejected by Gap A ({reason})");

    [Theory(DisplayName = "D009 Gap A (R2): IsPlausibleMessage accepts valid 2-token messages")]
    [InlineData("CQ Q1ABC",      "CQ callsign without grid — valid 2-token form")]
    [InlineData("<...> Q1ABC",   "hash sender, valid callsign addressee")]
    [InlineData("Q1ABC <...>",   "valid callsign sender, hash addressee")]
    [InlineData("<...> RR73",    "Type 4 shorthand terminal")]
    public void IsPlausibleMessage_GapA_ValidTwoToken_ReturnsTrue(string text, string reason)
        => Ft8Decoder.IsPlausibleMessage(text).Should().BeTrue(
               $"'{text}' is a valid 2-token message and must not be rejected by Gap A ({reason})");

    // ── Unit tests: D9-R3 Gap C — CQ 3-token garbage third token ─────────────

    [Theory(DisplayName = "D009 Gap C (R2): IsPlausibleMessage rejects CQ 3-token messages with garbage grid field")]
    [InlineData("CQ 3QQF EXLJSR",  "6-char third token; not a valid Maidenhead grid")]
    [InlineData("CQ /UX 6PY23BM",  "7-char third token; not a valid Maidenhead grid")]
    public void IsPlausibleMessage_GapC_CqGarbageThirdToken_ReturnsFalse(string text, string reason)
        => Ft8Decoder.IsPlausibleMessage(text).Should().BeFalse(
               $"'{text}' has a garbage third token and must be rejected now that the CQ early-return is removed ({reason})");

    [Theory(DisplayName = "D009 Gap C (R2): IsPlausibleMessage accepts valid CQ 3-token messages")]
    [InlineData("CQ Q1ABC FN42",  "standard CQ with grid — must still be accepted")]
    [InlineData("CQ 3DA0MN KH51", "6-char DX call with grid")]
    [InlineData("CQ VK9AA OC12",  "5-char DX call with grid")]
    public void IsPlausibleMessage_GapC_ValidCqMessage_ReturnsTrue(string text, string reason)
        => Ft8Decoder.IsPlausibleMessage(text).Should().BeTrue(
               $"'{text}' is a valid CQ message and must not be rejected by Gap C ({reason})");

    // ── Unit tests: R5 Rule A — single-token reject ──────────────────────────

    [Theory(DisplayName = "D009 R5 Rule A: IsPlausibleMessage rejects single-token messages")]
    [InlineData("Q1ABC",    "callsign-length single token — no valid FT8 decode is single-token")]
    [InlineData("BEACON",   "6-char single token")]
    [InlineData("73",       "terminal without context")]
    [InlineData("RR73",     "shorthand without sender/addressee")]
    public void IsPlausibleMessage_RuleA_SingleToken_ReturnsFalse(string text, string reason)
        => Ft8Decoder.IsPlausibleMessage(text).Should().BeFalse(
               $"'{text}' is a single-token string and must be rejected by R5 Rule A ({reason})");

    // ── Unit tests: R5 Rule B — 5+ token reject ──────────────────────────────

    [Theory(DisplayName = "D009 R5 Rule B: IsPlausibleMessage rejects messages with 5 or more tokens")]
    [InlineData("Q1ABC Q9XYZ R -10 73",        "5 tokens — not a valid FT8 message form")]
    [InlineData("CQ DX Q1ABC FN42 73",         "5 tokens — trailing extra token")]
    [InlineData("Q1ABC Q9XYZ -10 73 RR73",     "5 tokens — OSD CRC-14 noise coincidence")]
    public void IsPlausibleMessage_RuleB_FivePlusTokens_ReturnsFalse(string text, string reason)
        => Ft8Decoder.IsPlausibleMessage(text).Should().BeFalse(
               $"'{text}' has 5+ tokens and must be rejected by R5 Rule B ({reason})");

    // ── Unit tests: R5 Rule C — CQ <hash> 2-token reject ─────────────────────

    [Theory(DisplayName = "D009 R5 Rule C: IsPlausibleMessage rejects 2-token 'CQ <hash>' messages")]
    [InlineData("CQ <...>",     "CQ followed by hash — not a valid 2-token FT8 form (D-009 Category C FP)")]
    [InlineData("CQ <Q1ABC>",   "CQ followed by bracketed callsign hash")]
    public void IsPlausibleMessage_RuleC_CqHash_ReturnsFalse(string text, string reason)
        => Ft8Decoder.IsPlausibleMessage(text).Should().BeFalse(
               $"'{text}' is a 'CQ <hash>' 2-token message and must be rejected by R5 Rule C ({reason})");

    [Theory(DisplayName = "D009 R5 Rule C: IsPlausibleMessage accepts hash-first 2-token messages")]
    [InlineData("<...> Q1ABC",  "hash SENDER with valid callsign addressee — valid Type 4 form")]
    [InlineData("<...> RR73",   "hash sender with terminal — valid Type 4 shorthand")]
    [InlineData("Q1ABC <...>",  "callsign sender, hash addressee — valid Type 4 QSO")]
    public void IsPlausibleMessage_RuleC_HashFirst_ReturnsTrue(string text, string reason)
        => Ft8Decoder.IsPlausibleMessage(text).Should().BeTrue(
               $"'{text}' is a hash-first (not CQ-first) 2-token message and must not be rejected by Rule C ({reason})");

    // ── Unit tests: D9-R3 R3 — 4-token non-CQ reject ────────────────────────

    [Theory(DisplayName = "D009 R3: IsPlausibleMessage rejects 4-token messages where token0 is not CQ")]
    [InlineData("Q1AAA Q2BBB/R R OH76",     "CALLSIGN CALLSIGN R GRID — not a valid Type 1 message")]
    [InlineData("Q3CCC/P Q4DDD R EQ48",     "portable sender; still not a valid 4-token form")]
    [InlineData("Q5EEE/R Q6FFF/R R CH00",   "two portable callsigns; R GRID is not a Type 1 closing")]
    [InlineData("Q7GGG/P Q8HHH R EO10",     "same CALLSIGN CALLSIGN R GRID pattern")]
    [InlineData("Q9III/P Q1JJJ O/P QG94",   "O/P as third token is not a valid FT8 field")]
    public void IsPlausibleMessage_FourTokenNonCq_ReturnsFalse(string text, string reason)
        => Ft8Decoder.IsPlausibleMessage(text).Should().BeFalse(
               $"'{text}' is a non-CQ 4-token message and must be rejected by the R3 4-token rule ({reason})");

    [Theory(DisplayName = "D009 R3: IsPlausibleMessage accepts valid CQ 4-token messages")]
    [InlineData("CQ DX Q1ABC FN42", "standard CQ DX with grid")]
    [InlineData("CQ NA Q9XYZ EN37", "CQ North America")]
    [InlineData("CQ EU Q1AW JO54",  "CQ Europe")]
    public void IsPlausibleMessage_FourTokenCq_ReturnsTrue(string text, string reason)
        => Ft8Decoder.IsPlausibleMessage(text).Should().BeTrue(
               $"'{text}' is a valid CQ 4-token message and must not be rejected by the R3 4-token rule ({reason})");

    // ── Unit tests: must NOT reject — valid messages ──────────────────────────

    [Theory(DisplayName = "D009: IsPlausibleMessage accepts valid FT8 messages (must not reject)")]
    [InlineData("CQ Q1ABC FN42",          "standard CQ with grid")]
    [InlineData("Q1ABC Q9XYZ -10",        "standard QSO dB report")]
    [InlineData("Q9XYZ Q1AW RR73",        "terminal RR73")]
    [InlineData("Q1AW Q1ABC +05",         "positive dB report")]
    [InlineData("CQ Q9XYZ EN37",          "CQ with Maidenhead grid")]
    [InlineData("<...> Q9XYZ RR73",       "hash sender — not oversized")]
    [InlineData("Q1ABC <...> R-08",       "hash addressee — not oversized")]
    [InlineData("CQ VK9AA OC12",          "5-char DX call in CQ")]
    [InlineData("CQ 3DA0MN KH51",         "6-char digit-prefix DX call (3DA0MN)")]
    [InlineData("VK9AA Q1ABC -15",        "5-char DX call in sender position")]
    [InlineData("Q1ABC VK9AA/P RR73",     "8-char portable suffix in addressee (base 5, total 8)")]
    public void IsPlausibleMessage_ValidMessages_ReturnsTrue(string text, string reason)
        => Ft8Decoder.IsPlausibleMessage(text).Should().BeTrue(
               $"'{text}' is a valid FT8 message and must not be rejected ({reason})");

    // ── Integration test: DecodeAsync filters garbage messages end-to-end ─────

    /// <summary>
    /// Drives <see cref="Ft8Decoder.DecodeAsync"/> with a fake interop returning a mix of
    /// valid messages and the observed OSD false-positive garbage patterns.  Asserts that
    /// only the valid messages survive.
    /// </summary>
    [Fact(DisplayName = "D009 integration: DecodeAsync passes valid messages and filters all D-009 FP patterns")]
    public async Task DecodeAsync_MixedValidAndGarbage_ReturnsOnlyValidMessages()
    {
        var interop = new FixedResultInterop(
            // ── Valid messages (must survive) ─────────────────────────────────
            new Ft8NativeResult { FreqHz = 1000, Dt = 0.2f, Snr = -5,  Message = "Q1ABC Q9XYZ -10"  },
            new Ft8NativeResult { FreqHz = 1100, Dt = 0.1f, Snr =  3,  Message = "CQ Q1AW EN37"     },
            new Ft8NativeResult { FreqHz = 1200, Dt = 0.3f, Snr = -12, Message = "<...> Q9XYZ RR73" },

            // ── D9-R1: blank / whitespace (must be filtered) ─────────────────
            new Ft8NativeResult { FreqHz = 1300, Dt = 0.0f, Snr = -25, Message = ""                 },
            new Ft8NativeResult { FreqHz = 1350, Dt = 0.0f, Snr = -27, Message = "   "              },

            // ── D9-R2: hex dump (must be filtered) ───────────────────────────
            new Ft8NativeResult { FreqHz = 1400, Dt = 0.1f, Snr = -26, Message = "586A8555F2A13462F6" },
            new Ft8NativeResult { FreqHz = 1450, Dt = 0.2f, Snr = -28, Message = "1DA5713612BD5A3C22" },

            // ── D9-R3: oversized callsign (must be filtered) ─────────────────
            new Ft8NativeResult { FreqHz = 1500, Dt = 0.1f, Snr = -23, Message = "CQ ETRHB0I3RYOX"          },
            new Ft8NativeResult { FreqHz = 1600, Dt = 0.2f, Snr = -24, Message = "DDK4NYWXBIUZ Q9XYZ RR73"  },
            new Ft8NativeResult { FreqHz = 1700, Dt = 0.3f, Snr = -25, Message = "Q1ABC 1RY8RU98FJ9Z 73"    },

            // ── D9-R3 Gap A: 2-token both-token check (must be filtered) ─────
            new Ft8NativeResult { FreqHz = 1800, Dt = 0.1f, Snr = -27, Message = "<...> M5E5B91HFHLZ" },
            new Ft8NativeResult { FreqHz = 1850, Dt = 0.2f, Snr = -28, Message = "9ULLPTCDZHQR <...>" },

            // ── D9-R3 Gap C: CQ with garbage grid field (must be filtered) ───
            new Ft8NativeResult { FreqHz = 1900, Dt = 0.1f, Snr = -26, Message = "CQ 3QQF EXLJSR"  },
            new Ft8NativeResult { FreqHz = 1950, Dt = 0.2f, Snr = -27, Message = "CQ /UX 6PY23BM"  },

            // ── D009 R3: 4-token non-CQ patterns (must be filtered) ──────────
            new Ft8NativeResult { FreqHz = 2000, Dt = 0.1f, Snr = -27, Message = "Q1AAA Q2BBB/R R OH76"   },
            new Ft8NativeResult { FreqHz = 2050, Dt = 0.2f, Snr = -27, Message = "Q9III/P Q1JJJ O/P QG94" },

            // ── R5 Rule A: single-token (must be filtered) ────────────────────
            new Ft8NativeResult { FreqHz = 2100, Dt = 0.1f, Snr = -28, Message = "Q1ABC"                  },
            new Ft8NativeResult { FreqHz = 2150, Dt = 0.2f, Snr = -29, Message = "RR73"                   },

            // ── R5 Rule B: 5+ tokens (must be filtered) ──────────────────────
            new Ft8NativeResult { FreqHz = 2200, Dt = 0.1f, Snr = -27, Message = "Q1ABC Q9XYZ R -10 73"   },

            // ── R5 Rule C: CQ <hash> 2-token (must be filtered) ──────────────
            new Ft8NativeResult { FreqHz = 2300, Dt = 0.1f, Snr = -26, Message = "CQ <...>"               }
        );

        var decoder = BuildDecoder(interop);
        var results = await decoder.DecodeAsync(BuildLoudPcm(), CancellationToken.None);

        results.Should().HaveCount(3,
            "only the three valid messages must survive the D-009 filter; " +
            "blanks, hex dumps, oversized-callsign garbage, Gap A 2-token patterns, Gap C CQ garbage, " +
            "R3 4-token non-CQ patterns, R5 Rule A single-token, R5 Rule B 5+-token, and R5 Rule C CQ-hash " +
            "patterns must all be rejected");

        results.Select(r => r.Message).Should().BeEquivalentTo(
            ["Q1ABC Q9XYZ -10", "CQ Q1AW EN37", "<...> Q9XYZ RR73"],
            "the surviving messages must be exactly the three valid inputs, in original order");
    }
}
