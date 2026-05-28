using System;
using System.IO;
using FluentAssertions;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// WavReader — unit tests.
///
/// Verifies that the minimal 12 kHz mono int16 WAV→PCM reader (FR-029) correctly
/// normalises samples and clearly rejects unsupported formats. These tests use
/// synthetic in-memory WAV byte arrays so they run without any external files.
/// </summary>
public sealed class WavReaderTests
{
    // ── WAV builder ───────────────────────────────────────────────────────────

    /// <summary>
    /// Builds a minimal well-formed RIFF/WAVE byte array from the supplied
    /// parameters. Pass custom values to produce deliberately malformed WAVs.
    /// </summary>
    private static byte[] BuildWav(
        short  audioFormat    = 1,
        short  channels       = 1,
        int    sampleRate     = 12_000,
        short  bitsPerSample  = 16,
        short[]? samples      = null)
    {
        samples ??= [0, 16_384, -16_384, 32_767, -32_768];

        // Serialise samples as little-endian int16
        byte[] sampleBytes = new byte[samples.Length * 2];
        for (int i = 0; i < samples.Length; i++)
        {
            sampleBytes[i * 2]     = (byte)( samples[i]        & 0xFF);
            sampleBytes[i * 2 + 1] = (byte)((samples[i] >> 8)  & 0xFF);
        }

        short blockAlign = (short)(channels * bitsPerSample / 8);
        int   byteRate   = sampleRate * channels * bitsPerSample / 8;
        int   dataSize   = sampleBytes.Length;
        int   riffSize   = 4 + (8 + 16) + (8 + dataSize); // WAVE + fmt-chunk + data-chunk

        using var ms = new MemoryStream();
        using var w  = new BinaryWriter(ms);

        // RIFF header
        w.Write(new byte[] { (byte)'R', (byte)'I', (byte)'F', (byte)'F' });
        w.Write(riffSize);
        w.Write(new byte[] { (byte)'W', (byte)'A', (byte)'V', (byte)'E' });

        // fmt chunk
        w.Write(new byte[] { (byte)'f', (byte)'m', (byte)'t', (byte)' ' });
        w.Write(16);             // chunk size
        w.Write(audioFormat);
        w.Write(channels);
        w.Write(sampleRate);
        w.Write(byteRate);
        w.Write(blockAlign);
        w.Write(bitsPerSample);

        // data chunk
        w.Write(new byte[] { (byte)'d', (byte)'a', (byte)'t', (byte)'a' });
        w.Write(dataSize);
        w.Write(sampleBytes);

        return ms.ToArray();
    }

    // ── Happy-path ────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-029: WavReader returns correct sample count for a valid 12 kHz mono int16 WAV")]
    public void Read_ValidWav_ReturnsCorrectSampleCount()
    {
        var samples = new short[] { 0, 32_767, -32_768, 16_384 };
        using var ms = new MemoryStream(BuildWav(samples: samples));

        float[] pcm = WavReader.Read(ms);

        pcm.Should().HaveCount(4,
            "sample count must equal the number of int16 samples in the WAV data chunk");
    }

    [Fact(DisplayName = "FR-029: WavReader normalises int16 samples to [-1, 1] correctly")]
    public void Read_ValidWav_NormalisesSamples()
    {
        // Choose samples whose normalised values are easy to assert exactly.
        var samples = new short[] { 0, 32_767, -32_768, 16_384 };
        using var ms = new MemoryStream(BuildWav(samples: samples));

        float[] pcm = WavReader.Read(ms);

        pcm[0].Should().BeApproximately(0.0f,            precision: 1e-6f,
            "0 normalises to 0.0");
        pcm[1].Should().BeApproximately(32_767 / 32_768.0f, precision: 1e-5f,
            "32 767 normalises to approximately +1.0");
        pcm[2].Should().BeApproximately(-32_768 / 32_768.0f, precision: 1e-5f,
            "-32 768 normalises to exactly -1.0");
        pcm[3].Should().BeApproximately(16_384 / 32_768.0f, precision: 1e-5f,
            "16 384 normalises to approximately +0.5");
    }

    [Fact(DisplayName = "FR-029: WavReader accepts a 180 000-sample WAV matching the FT8 cycle length")]
    public void Read_FullCycleWav_Returns180000Samples()
    {
        // 15 s × 12 000 Hz = 180 000 samples — the expected FT8 cycle length
        var samples = new short[180_000];
        using var ms = new MemoryStream(BuildWav(samples: samples));

        float[] pcm = WavReader.Read(ms);

        pcm.Should().HaveCount(180_000,
            "a 15-second 12 kHz cycle produces exactly 180 000 samples");
    }

    // ── Rejection tests ───────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-029: WavReader rejects WAV with non-12 kHz sample rate")]
    public void Read_Non12kHzSampleRate_ThrowsWithRate()
    {
        using var ms = new MemoryStream(BuildWav(sampleRate: 44_100));

        var act = () => WavReader.Read(ms);

        act.Should()
           .Throw<InvalidDataException>()
           .WithMessage("*44100*",
               "error message must include the actual sample rate so the caller knows what was found");
    }

    [Fact(DisplayName = "FR-029: WavReader rejects stereo WAV")]
    public void Read_StereoWav_ThrowsWithChannelCount()
    {
        using var ms = new MemoryStream(BuildWav(channels: 2));

        var act = () => WavReader.Read(ms);

        act.Should()
           .Throw<InvalidDataException>()
           .WithMessage("*2*channel*",
               "error message must include the channel count and the word 'channel'");
    }

    [Fact(DisplayName = "FR-029: WavReader rejects non-PCM audio format (e.g. IEEE float)")]
    public void Read_NonPcmAudioFormat_ThrowsMentioningPcm()
    {
        using var ms = new MemoryStream(BuildWav(audioFormat: 3)); // 3 = IEEE float

        var act = () => WavReader.Read(ms);

        act.Should()
           .Throw<InvalidDataException>()
           .WithMessage("*PCM*",
               "error message must mention PCM to make clear what format is required");
    }

    [Fact(DisplayName = "FR-029: WavReader rejects 8-bit WAV")]
    public void Read_8BitWav_ThrowsWithBitDepth()
    {
        using var ms = new MemoryStream(BuildWav(bitsPerSample: 8));

        var act = () => WavReader.Read(ms);

        act.Should()
           .Throw<InvalidDataException>()
           .WithMessage("*8*",
               "error message must include the actual bit depth");
    }

    [Fact(DisplayName = "FR-029: WavReader rejects malformed RIFF header")]
    public void Read_NotRiff_Throws()
    {
        // A byte array that does not start with 'RIFF'
        byte[] notRiff = new byte[44];
        notRiff[0] = (byte)'F'; notRiff[1] = (byte)'A'; notRiff[2] = (byte)'K'; notRiff[3] = (byte)'E';
        using var ms = new MemoryStream(notRiff);

        var act = () => WavReader.Read(ms);

        act.Should().Throw<InvalidDataException>();
    }
}
