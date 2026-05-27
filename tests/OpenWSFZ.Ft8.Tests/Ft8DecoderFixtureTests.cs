using FluentAssertions;
using OpenWSFZ.Ft8;
using OpenWSFZ.Ft8.Dsp;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Ft8Decoder: Ft8DecoderFixtureTests
///
/// Full-pipeline integration test using an embedded WAV fixture.
/// Skipped until ft8-sample.wav is committed to Fixtures/ (task 8.1–8.2).
/// </summary>
public sealed class Ft8DecoderFixtureTests
{
    [Fact(DisplayName = "FR-001: Ft8Decoder returns DecodeResult records from a known-good synthetic FT8 fixture")]
    public async Task DecodeAsync_WavFixture_ReturnsKnownDecodes()
    {
        const double baseFreqHz = 1500.0;
        byte[] msgBits  = TestFt8Encoder.PackType1(c1: 2, c2: 1_674_730, rg: 10_331);
        byte[] infoBits = TestFt8Encoder.AppendCrc14(msgBits);
        byte[] codeword = TestFt8Encoder.LdpcEncode(infoBits);
        int[]  symbols  = TestFt8Encoder.BitsToSymbols(codeword);
        float[] pcm     = TestFt8Encoder.SymbolsToPcm(symbols, baseFreqHz, startSample: 0);

        var clock   = new FakeClock(new DateTime(2026, 5, 21, 15, 30, 0, DateTimeKind.Utc));
        var decoder = new Ft8Decoder(clock);
        var results = await decoder.DecodeAsync(pcm, CancellationToken.None);

        results.Should().NotBeEmpty("the synthetic fixture should contain at least one decodable FT8 message");
        results.Select(r => r.Message).Should().Contain("CQ Q1AW FN31",
            "the known-good synthetic frame for 'CQ Q1AW FN31' must decode correctly end-to-end");
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

        byte[] msgBits  = TestFt8Encoder.PackType1(c1: 2, c2: 1_674_730, rg: 10_331);
        byte[] infoBits = TestFt8Encoder.AppendCrc14(msgBits);
        byte[] codeword = TestFt8Encoder.LdpcEncode(infoBits);
        int[]  symbols  = TestFt8Encoder.BitsToSymbols(codeword);
        float[] pcm     = TestFt8Encoder.SymbolsToPcm(symbols, baseFreqHz, startSample: startSample);

        var clock   = new FakeClock(new DateTime(2026, 5, 21, 15, 30, 0, DateTimeKind.Utc));
        var decoder = new Ft8Decoder(clock);
        var results = await decoder.DecodeAsync(pcm, CancellationToken.None);

        results.Should().NotBeEmpty(
            "a signal offset by half a symbol period must be decodable with the half-symbol time sweep");
        results.Select(r => r.Message).Should().Contain("CQ Q1AW FN31",
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

        byte[] msgBits  = TestFt8Encoder.PackType1(c1: 2, c2: 1_674_730, rg: 10_331);
        byte[] infoBits = TestFt8Encoder.AppendCrc14(msgBits);
        byte[] codeword = TestFt8Encoder.LdpcEncode(infoBits);
        int[]  symbols  = TestFt8Encoder.BitsToSymbols(codeword);
        float[] pcm     = TestFt8Encoder.SymbolsToPcm(symbols, baseFreqHz, startSample: startSample);

        var clock   = new FakeClock(new DateTime(2026, 5, 21, 15, 30, 0, DateTimeKind.Utc));
        var decoder = new Ft8Decoder(clock);
        var results = await decoder.DecodeAsync(pcm, CancellationToken.None);

        results.Should().NotBeEmpty(
            "a signal at quarter-symbol offset (worst case between sweep steps) must decode");
        results.Select(r => r.Message).Should().Contain("CQ Q1AW FN31");
    }
}
