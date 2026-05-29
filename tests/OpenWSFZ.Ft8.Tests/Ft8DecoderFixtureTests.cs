using FluentAssertions;
using OpenWSFZ.Ft8;
using OpenWSFZ.Ft8.Dsp;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Ft8Decoder: Ft8DecoderFixtureTests — INTERNAL CONSISTENCY CHECKS ONLY
///
/// ⚠️ These tests use <see cref="TestFt8Encoder"/> to build synthetic inputs that
/// share the same Gray map, CRC convention, LDPC generator, and waveform synthesis
/// as the decoder. A self-consistent encoder/decoder pair always round-trips, so
/// green results here prove only that the decoder agrees with <em>itself</em> — not
/// that it can decode real off-air FT8 signals.
///
/// Per <c>RECOVERY_PLAN.md</c> D3 and FR-029: <strong>these tests are classified as
/// internal-consistency checks and are NOT accepted as evidence of decoder
/// correctness against real signals.</strong> The authoritative correctness oracle
/// is <see cref="RealSignalFixtureTests"/>, which decodes real WSJT-X Save All
/// recordings.
/// </summary>
public sealed class Ft8DecoderFixtureTests
{
    [Fact(DisplayName = "FR-001: Ft8Decoder returns DecodeResult records from a known-good synthetic FT8 fixture")]
    public async Task DecodeAsync_WavFixture_ReturnsKnownDecodes()
    {
        const double baseFreqHz = 1500.0;
        byte[] msgBits  = TestFt8Encoder.PackType1(c1: 2, c2: 6_516_426, rg: 10_331);
        byte[] infoBits = TestFt8Encoder.AppendCrc14(msgBits);
        byte[] codeword = TestFt8Encoder.LdpcEncode(infoBits);
        int[]  symbols  = TestFt8Encoder.BitsToSymbols(codeword);
        float[] pcm     = TestFt8Encoder.SymbolsToPcm(symbols, baseFreqHz, startSample: 0);

        var clock   = new FakeClock(new DateTime(2026, 5, 21, 15, 30, 0, DateTimeKind.Utc));
        var decoder = new Ft8Decoder(clock);
        var results = await decoder.DecodeAsync(pcm, CancellationToken.None);

        results.Should().NotBeEmpty("the synthetic fixture should contain at least one decodable FT8 message");
        results.Select(r => r.Message).Should().Contain("CQ W1AW FN31",
            "the known-good synthetic frame for 'CQ W1AW FN31' must decode correctly end-to-end");
    }

    [Fact(DisplayName = "FR-001: Ft8Decoder returns empty list for all-silent PCM input")]
    public async Task DecodeAsync_SilentPcm_ReturnsEmptyList()
    {
        var clock   = new FakeClock(new DateTime(2026, 5, 21, 15, 30, 0, DateTimeKind.Utc));
        var decoder = new Ft8Decoder(clock);
        var pcm     = new float[180_000]; // all zeros

        var results = await decoder.DecodeAsync(pcm, CancellationToken.None);

        results.Should().BeEmpty("silence should produce no decoded messages");
    }

    [Fact(DisplayName = "FR-001: Ft8Decoder respects CancellationToken and throws OperationCanceledException")]
    public async Task DecodeAsync_Cancelled_ThrowsOperationCancelled()
    {
        var clock   = new FakeClock(new DateTime(2026, 5, 21, 15, 30, 0, DateTimeKind.Utc));
        var decoder = new Ft8Decoder(clock);
        var pcm     = new float[180_000];

        using var cts = new CancellationTokenSource();
        cts.Cancel();

        var act = async () => await decoder.DecodeAsync(pcm, cts.Token);
        await act.Should().ThrowAsync<OperationCanceledException>();
    }

    /// <summary>
    /// D11 regression test: verifies that a signal starting at a half-symbol-period offset
    /// (960 samples = 80 ms) is decoded correctly.
    ///
    /// Root cause of D11: the time-domain sweep previously stepped in full symbol periods
    /// (1920 samples).  A signal whose UTC clock dt places it exactly halfway between two
    /// sweep positions produced a 50/50 mix of adjacent-symbol samples in every Goertzel
    /// window, corrupting LLR signs and preventing LDPC convergence.  With the half-symbol
    /// step (TimeSweepStep = 960), the sweep hits startSample = 960 — exact alignment —
    /// and recovers clean LLRs.
    ///
    /// The soft Costas score (D11, Part 1) is also exercised: at startSample = 960 the
    /// Costas sweep finds the signal with a high soft score and passes it to Goertzel.
    /// </summary>
    [Fact(DisplayName = "FR-001: Ft8Decoder decodes signal at half-symbol-period offset (D11 regression)")]
    public async Task DecodeAsync_HalfSymbolOffset_ReturnsKnownDecodes()
    {
        const double baseFreqHz  = 1500.0;
        // Place the signal at exactly one half-symbol period into the buffer.
        // With the old full-symbol sweep this position falls equidistant between
        // startSample=0 and startSample=1920, giving 50% contamination at both.
        // With TimeSweepStep=960 the sweep lands at startSample=960 — perfect alignment.
        int startSample = SymbolExtractor.SamplesPerSymbol / 2; // 960

        byte[] msgBits  = TestFt8Encoder.PackType1(c1: 2, c2: 6_516_426, rg: 10_331);
        byte[] infoBits = TestFt8Encoder.AppendCrc14(msgBits);
        byte[] codeword = TestFt8Encoder.LdpcEncode(infoBits);
        int[]  symbols  = TestFt8Encoder.BitsToSymbols(codeword);
        float[] pcm     = TestFt8Encoder.SymbolsToPcm(symbols, baseFreqHz, startSample: startSample);

        var clock   = new FakeClock(new DateTime(2026, 5, 21, 15, 30, 0, DateTimeKind.Utc));
        var decoder = new Ft8Decoder(clock);
        var results = await decoder.DecodeAsync(pcm, CancellationToken.None);

        results.Should().NotBeEmpty(
            "a signal offset by half a symbol period must be decodable with the half-symbol time sweep");
        results.Select(r => r.Message).Should().Contain("CQ W1AW FN31",
            "the known-good synthetic frame must survive the timing offset end-to-end");
    }

    /// <summary>
    /// D11 regression test, part 2: verifies a signal at a quarter-symbol-period offset.
    /// This exercises the worst case between two consecutive half-symbol sweep steps
    /// (480 samples = 40 ms offset, 25% contamination).
    /// </summary>
    [Fact(DisplayName = "FR-001: Ft8Decoder decodes signal at quarter-symbol-period offset (D11 regression)")]
    public async Task DecodeAsync_QuarterSymbolOffset_ReturnsKnownDecodes()
    {
        const double baseFreqHz  = 1500.0;
        int startSample = SymbolExtractor.SamplesPerSymbol / 4; // 480

        byte[] msgBits  = TestFt8Encoder.PackType1(c1: 2, c2: 6_516_426, rg: 10_331);
        byte[] infoBits = TestFt8Encoder.AppendCrc14(msgBits);
        byte[] codeword = TestFt8Encoder.LdpcEncode(infoBits);
        int[]  symbols  = TestFt8Encoder.BitsToSymbols(codeword);
        float[] pcm     = TestFt8Encoder.SymbolsToPcm(symbols, baseFreqHz, startSample: startSample);

        var clock   = new FakeClock(new DateTime(2026, 5, 21, 15, 30, 0, DateTimeKind.Utc));
        var decoder = new Ft8Decoder(clock);
        var results = await decoder.DecodeAsync(pcm, CancellationToken.None);

        results.Should().NotBeEmpty(
            "a signal at quarter-symbol offset (worst case between sweep steps) must decode");
        results.Select(r => r.Message).Should().Contain("CQ W1AW FN31");
    }

    /// <summary>
    /// FR-026 performance regression test: DecodeAsync must complete within 10 seconds
    /// on a synthetic fixture containing 8 simultaneous FT8 signals.
    ///
    /// A single-signal fixture cannot expose the candidate explosion that caused the
    /// ~59-second decode regression.  Eight concurrent signals approximate a moderately
    /// busy band.  The 10-second budget is conservative (target post-fix is under 5 s);
    /// it provides headroom for CI runner variance while still catching regressions.
    ///
    /// De-duplication by message string is verified: the decoder must return at least 6
    /// of the 8 known callsigns (all 8 expected on a fast machine; 6 is the floor to
    /// tolerate marginal-SNR edge cases at the frequency extremes).
    /// </summary>
    [Fact(DisplayName = "FR-026: DecodeAsync completes within 10 s on 8-signal fixture")]
    [Trait("Category", "Performance")]
    public async Task DecodeAsync_MultiSignal_CompletesWithinBudget()
    {
        // Eight callsigns with distinct 28-bit encodings, each at a unique base frequency
        // on the 50 Hz outer sweep grid (MinFreqHz=50, FreqSweepStep=50).
        var signals = new (string callsign, double baseHz)[]
        {
            ("W1AW", 500.0),
            ("W2AW", 750.0),
            ("W3AW", 1000.0),
            ("W4AW", 1250.0),
            ("W5AW", 1500.0),
            ("W6AW", 1750.0),
            ("W7AW", 2000.0),
            ("W8AW", 2250.0),
        };
        const string grid = "FN31";

        // Build a composite PCM buffer: superimpose all 8 signals.
        const int totalSamples = 180_000;
        var pcm = new float[totalSamples];

        var expectedCallsigns = new List<string>();
        foreach (var (callsign, baseHz) in signals)
        {
            ulong c2      = TestFt8Encoder.EncodeCallsign28(callsign);
            ulong rg      = TestFt8Encoder.EncodeReport15Grid(grid);
            byte[] msg    = TestFt8Encoder.PackType1(c1: 2, c2: c2, rg: rg);
            byte[] info   = TestFt8Encoder.AppendCrc14(msg);
            byte[] cw     = TestFt8Encoder.LdpcEncode(info);
            int[]  syms   = TestFt8Encoder.BitsToSymbols(cw);
            float[] frame = TestFt8Encoder.SymbolsToPcm(syms, baseHz, startSample: 0);

            for (int i = 0; i < totalSamples; i++)
                pcm[i] += frame[i];

            expectedCallsigns.Add($"CQ {callsign} {grid}");
        }

        // Additive Gaussian noise — σ = 0.001, seeded for reproducibility.
        // Signal amplitude = 0.5 (default); SNR ≈ 54 dB — well above the LDPC floor.
        var rng = new Random(42);
        const double sigma = 0.001;
        for (int i = 0; i < totalSamples; i++)
        {
            // Box-Muller transform.
            double u1 = 1.0 - rng.NextDouble();
            double u2 = 1.0 - rng.NextDouble();
            double z  = Math.Sqrt(-2.0 * Math.Log(u1)) * Math.Cos(2.0 * Math.PI * u2);
            pcm[i] += (float)(z * sigma);
        }

        var clock   = new FakeClock(new DateTime(2026, 5, 28, 15, 30, 0, DateTimeKind.Utc));
        var decoder = new Ft8Decoder(clock);

        var sw = System.Diagnostics.Stopwatch.StartNew();
        var results = await decoder.DecodeAsync(pcm, CancellationToken.None);
        sw.Stop();

        sw.ElapsedMilliseconds.Should().BeLessThan(10_000,
            "FR-026: decode must complete within 10 seconds on an 8-signal fixture");

        var decodedMessages = results.Select(r => r.Message).ToList();
        int hits = expectedCallsigns.Count(expected => decodedMessages.Contains(expected));
        hits.Should().BeGreaterThanOrEqualTo(6,
            $"at least 6 of 8 known FT8 messages must be decoded; got {hits}. " +
            $"Decoded: [{string.Join(", ", decodedMessages)}]");
    }

    /// <summary>
    /// Task 8.1–8.2 integration test: loads the committed WAV fixture file
    /// (ft8-sample.wav) from the embedded assembly resources, runs the full
    /// decode pipeline, and asserts every message line from ft8-sample.ref
    /// appears in the results.
    ///
    /// The fixture is a synthetic 15-second 12 kHz mono IEEE float-32 WAV
    /// generated by <c>tools/GenerateFt8Fixture</c> for "CQ W1AW FN31".
    /// </summary>
    [Fact(DisplayName = "FR-001: Ft8Decoder decodes embedded WAV fixture and matches ft8-sample.ref")]
    public async Task DecodeAsync_EmbeddedWavFixture_MatchesRefFile()
    {
        float[] pcm      = WavFixtureHelper.LoadEmbeddedWav("ft8-sample.wav");
        var     refLines = WavFixtureHelper.LoadEmbeddedLines("ft8-sample.ref");

        refLines.Should().NotBeEmpty(
            "ft8-sample.ref must contain at least one reference decode line; " +
            "if the file is blank the test asserts nothing");

        var clock   = new FakeClock(new DateTime(2026, 5, 21, 15, 30, 0, DateTimeKind.Utc));
        var decoder = new Ft8Decoder(clock);
        var results = await decoder.DecodeAsync(pcm, CancellationToken.None);

        results.Should().NotBeEmpty("the WAV fixture must contain at least one decodable FT8 message");

        var decodedMessages = results.Select(r => r.Message).ToList();
        foreach (var expected in refLines)
        {
            decodedMessages.Should().Contain(expected,
                $"message '{expected}' from ft8-sample.ref must appear in the decoded results");
        }
    }
}
