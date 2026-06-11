using FluentAssertions;
using OpenWSFZ.Ft8;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Unit tests for <see cref="Ft8Decoder.NormalisePcm"/> (D-002 SNR-bias fix).
///
/// <para>
/// <c>NormalisePcm</c> scales a float[] PCM buffer to a fixed target RMS, bringing
/// any input amplitude to a known level before it reaches the native libft8 histogram.
/// The silent-buffer guard prevents divide-by-zero for all-zero inputs.
/// </para>
/// </summary>
public sealed class PcmNormalisationTests
{
    private const float TargetRms   = 0.08f;
    private const float Tolerance   = 0.001f;   // 0.1 % RMS accuracy requirement

    // ── 3.2 White-noise buffer of known RMS ──────────────────────────────────

    [Fact(DisplayName = "3.2: NormalisePcm scales white-noise buffer to target RMS (within 0.1%)")]
    public void NormalisePcm_WhiteNoiseBuffer_OutputRmsEqualsTarget()
    {
        // Deterministic PRNG (seed = 42) produces a white-noise-like sequence
        // with a well-defined RMS that differs from the target.
        float[] pcm = GenerateWhiteNoise(seed: 42, count: 180_000, amplitude: 0.5f);

        float[] result = Ft8Decoder.NormalisePcm(pcm, TargetRms);

        float outRms = ComputeRms(result);
        outRms.Should().BeApproximately(TargetRms, Tolerance,
            because: "output RMS should equal target RMS within 0.1%");
    }

    [Fact(DisplayName = "3.2b: NormalisePcm does not mutate the input array")]
    public void NormalisePcm_DoesNotMutateInput()
    {
        float[] pcm = GenerateWhiteNoise(seed: 7, count: 1_000, amplitude: 0.3f);
        float[] copy = (float[])pcm.Clone();

        _ = Ft8Decoder.NormalisePcm(pcm, TargetRms);

        pcm.Should().Equal(copy, because: "NormalisePcm must not mutate the original buffer");
    }

    // ── 3.3 Silent buffer (all zeros) ────────────────────────────────────────

    [Fact(DisplayName = "3.3: NormalisePcm returns silent buffer unchanged without throwing")]
    public void NormalisePcm_SilentBuffer_ReturnedUnchanged()
    {
        float[] pcm    = new float[180_000];   // all zeros
        float[] result = Ft8Decoder.NormalisePcm(pcm, TargetRms);

        // Must return the same reference (not a scaled copy) for the silent path
        result.Should().BeSameAs(pcm,
            because: "silent buffer guard must return the original array unchanged");
    }

    [Fact(DisplayName = "3.3b: NormalisePcm does not throw for near-zero amplitude buffer")]
    public void NormalisePcm_NearZeroAmplitude_DoesNotThrow()
    {
        // RMS well below SilenceRmsThreshold (1e-6)
        float[] pcm = new float[1_000];
        pcm[0] = 1e-10f;

        var act = () => Ft8Decoder.NormalisePcm(pcm, TargetRms);
        act.Should().NotThrow(because: "near-zero RMS should not produce an exception");
    }

    // ── 3.4 Single-sample buffer ──────────────────────────────────────────────

    [Fact(DisplayName = "3.4: NormalisePcm normalises a single-sample buffer correctly")]
    public void NormalisePcm_SingleSample_NormalisedCorrectly()
    {
        // Single sample of value 0.5 → RMS = 0.5; after normalisation RMS = target
        float[] pcm    = [0.5f];
        float[] result = Ft8Decoder.NormalisePcm(pcm, TargetRms);

        float outRms = ComputeRms(result);
        outRms.Should().BeApproximately(TargetRms, Tolerance,
            because: "single-sample buffer: RMS = |sample|, should be scaled to target");
    }

    // ── 3.5 Buffer already at target RMS ─────────────────────────────────────

    [Fact(DisplayName = "3.5: NormalisePcm of buffer already at target RMS returns values unchanged")]
    public void NormalisePcm_AlreadyAtTargetRms_OutputApproximatelyUnchanged()
    {
        // Construct a buffer whose RMS equals TargetRms exactly.
        // Simple approach: all samples equal to TargetRms → RMS = TargetRms.
        const int n     = 1_000;
        float[]   pcm   = new float[n];
        for (int i = 0; i < n; i++) pcm[i] = TargetRms;

        float[] result = Ft8Decoder.NormalisePcm(pcm, TargetRms);

        // Scale factor should be ≈ 1.0; every output sample ≈ input sample
        for (int i = 0; i < n; i++)
            result[i].Should().BeApproximately(pcm[i], Tolerance,
                because: $"sample[{i}] should be unchanged when input RMS already equals target");
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static float ComputeRms(float[] pcm)
    {
        if (pcm.Length == 0) return 0f;
        double sum = 0.0;
        foreach (float s in pcm) sum += (double)s * s;
        return (float)Math.Sqrt(sum / pcm.Length);
    }

    private static float[] GenerateWhiteNoise(int seed, int count, float amplitude)
    {
        var   rng    = new Random(seed);
        var   result = new float[count];
        for (int i = 0; i < count; i++)
            result[i] = (float)(rng.NextDouble() * 2.0 - 1.0) * amplitude;
        return result;
    }
}
