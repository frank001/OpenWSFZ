using FluentAssertions;
using OpenWSFZ.Ft8;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Ft8Decoder: basic correctness and performance checks.
///
/// Decode correctness against real off-air signals is covered by
/// <see cref="RealSignalFixtureTests"/> (G6 gate).
/// </summary>
public sealed class Ft8DecoderFixtureTests
{
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
    /// FR-026 performance regression test: DecodeAsync must complete within 10 seconds
    /// on a synthetic fixture containing 8 simultaneous FT8 signals.
    ///
    /// A single-signal fixture cannot expose the candidate explosion that caused the
    /// ~59-second decode regression.  Eight concurrent signals approximate a moderately
    /// busy band.  The 10-second budget is conservative; it provides headroom for CI
    /// runner variance while still catching regressions.
    ///
    /// NOTE: <see cref="TestFt8Encoder"/> uses i3=0 (FREE TEXT) rather than i3=1
    /// (standard callsign); ft8_lib correctly rejects the payload.  This test validates
    /// only that the ft8_lib call path completes within the cycle budget.  Decode
    /// correctness is verified by <see cref="RealSignalFixtureTests"/> (G6 gate).
    /// </summary>
    [Fact(DisplayName = "FR-026: DecodeAsync completes within 10 s on 8-signal fixture")]
    [Trait("Category", "Performance")]
    public async Task DecodeAsync_MultiSignal_CompletesWithinBudget()
    {
        // Eight callsigns with distinct 28-bit encodings, each at a unique base frequency
        // on the 50 Hz outer sweep grid (MinFreqHz=50, FreqSweepStep=50).
        var signals = new (string callsign, double baseHz)[]
        {
            ("Q1AW", 500.0),
            ("Q2AW", 750.0),
            ("Q3AW", 1000.0),
            ("Q4AW", 1250.0),
            ("Q5AW", 1500.0),
            ("Q6AW", 1750.0),
            ("Q7AW", 2000.0),
            ("Q8AW", 2250.0),
        };
        const string grid = "FN31";

        // Build a composite PCM buffer: superimpose all 8 signals.
        const int totalSamples = 180_000;
        var pcm = new float[totalSamples];

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
        _ = await decoder.DecodeAsync(pcm, CancellationToken.None);
        sw.Stop();

        sw.ElapsedMilliseconds.Should().BeLessThan(10_000,
            "FR-026: decode must complete within 10 seconds on an 8-signal fixture");
    }
}
