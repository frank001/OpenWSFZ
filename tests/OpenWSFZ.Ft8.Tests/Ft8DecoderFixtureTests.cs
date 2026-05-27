using FluentAssertions;
using OpenWSFZ.Ft8;
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
}
