using FluentAssertions;
using OpenWSFZ.Daemon;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="CycleWavWriter"/> (cycle-audio-archive capability, tasks 2.1-2.3).
/// Verifies canonical RIFF/WAVE header correctness, exact frame count, float→int16 clamping and
/// clip counting, and a round-trip of a known sample pattern.
/// </summary>
[Trait("Category", "Unit")]
public sealed class CycleWavWriterTests
{
    private const int TotalFrames = 180_000; // 15 s × 12 kHz — the framer's actual window size

    // ── Header field correctness ─────────────────────────────────────────────

    [Fact(DisplayName = "cycle-audio-archive: Encode produces a canonical 44-byte RIFF/WAVE header with correct chunk sizes")]
    public void Encode_ProducesCanonicalHeader()
    {
        var pcm = new float[TotalFrames];

        var (bytes, clipped) = CycleWavWriter.Encode(pcm);

        clipped.Should().Be(0, "all-silent PCM should not clip");
        bytes.Length.Should().Be(44 + TotalFrames * 2, "header (44 bytes) + 16-bit samples");

        // RIFF / WAVE / fmt  / data ASCII tags.
        Ascii(bytes, 0, 4).Should().Be("RIFF");
        Ascii(bytes, 8, 4).Should().Be("WAVE");
        Ascii(bytes, 12, 4).Should().Be("fmt ");
        Ascii(bytes, 36, 4).Should().Be("data");

        // RIFF chunk size = total file size − 8.
        ReadUInt32(bytes, 4).Should().Be((uint)(bytes.Length - 8));

        // fmt chunk: size=16, format=1 (PCM), channels=1, sampleRate=12000, bitsPerSample=16.
        ReadUInt32(bytes, 16).Should().Be(16, "PCM fmt chunk carries no extension");
        ReadUInt16(bytes, 20).Should().Be(1, "audio format must be 1 (PCM)");
        ReadUInt16(bytes, 22).Should().Be(1, "mono — 1 channel");
        ReadUInt32(bytes, 24).Should().Be(12_000, "sample rate must be 12 000 Hz");
        ReadUInt16(bytes, 34).Should().Be(16, "16 bits per sample");

        // byteRate = sampleRate * channels * bitsPerSample/8; blockAlign = channels * bitsPerSample/8.
        ReadUInt32(bytes, 28).Should().Be(12_000 * 1 * 2);
        ReadUInt16(bytes, 32).Should().Be(2);

        // data chunk size = number of samples * 2 bytes.
        ReadUInt32(bytes, 40).Should().Be((uint)(TotalFrames * 2));
    }

    [Fact(DisplayName = "cycle-audio-archive: Encode reports exactly 180 000 sample frames for a 15 s window")]
    public void Encode_ReportsExactFrameCount()
    {
        var pcm = new float[TotalFrames];

        var (bytes, _) = CycleWavWriter.Encode(pcm);

        var dataSize   = ReadUInt32(bytes, 40);
        var frameCount = dataSize / 2; // 16-bit mono → 2 bytes/frame
        frameCount.Should().Be(TotalFrames);
    }

    // ── Clamping and clip counting ────────────────────────────────────────────

    [Fact(DisplayName = "cycle-audio-archive: full-scale samples clamp to +32767/-32768 rather than wrap, and are counted")]
    public void Encode_ClampsOutOfRangeSamples_AndCountsThem()
    {
        var pcm = new float[TotalFrames];
        pcm[0] = 1.5f;
        pcm[1] = -1.5f;

        var (bytes, clipped) = CycleWavWriter.Encode(pcm);

        clipped.Should().Be(2, "exactly two samples exceed the representable range");

        short sample0 = ReadInt16(bytes, 44 + 0 * 2);
        short sample1 = ReadInt16(bytes, 44 + 1 * 2);
        sample0.Should().Be(32767, "a value of +1.5 must clamp to the maximum positive int16, not wrap");
        sample1.Should().Be(-32768, "a value of -1.5 must clamp to the maximum negative int16, not wrap");
    }

    [Fact(DisplayName = "cycle-audio-archive: in-range samples do not clip")]
    public void Encode_InRangeSamples_DoNotClip()
    {
        var pcm = new float[TotalFrames];
        pcm[0] = 0.5f;
        pcm[1] = -0.5f;
        pcm[2] = 1.0f;
        pcm[3] = -1.0f;

        var (_, clipped) = CycleWavWriter.Encode(pcm);

        clipped.Should().Be(0, "no sample in [-1, 1] should require clamping");
    }

    // ── Round-trip of a known sample pattern ──────────────────────────────────

    [Fact(DisplayName = "cycle-audio-archive: a known sample pattern round-trips through Encode exactly")]
    public void Encode_KnownSamplePattern_RoundTripsExactly()
    {
        var pcm = new float[TotalFrames];
        // A short, exactly-representable known pattern at the start of the window.
        pcm[0] = 0.0f;
        pcm[1] = 0.5f;
        pcm[2] = -0.5f;
        pcm[3] = 1.0f;
        pcm[4] = -1.0f;

        var (bytes, clipped) = CycleWavWriter.Encode(pcm);

        clipped.Should().Be(0);

        ReadInt16(bytes, 44 + 0 * 2).Should().Be(0);
        ReadInt16(bytes, 44 + 1 * 2).Should().Be((short)Math.Round(0.5 * 32767));
        ReadInt16(bytes, 44 + 2 * 2).Should().Be((short)-Math.Round(0.5 * 32767));
        ReadInt16(bytes, 44 + 3 * 2).Should().Be(32767, "1.0 scaled by 32767 and rounded is exactly 32767");
        ReadInt16(bytes, 44 + 4 * 2).Should().Be(-32767,
            "-1.0 scaled by 32767 and rounded is exactly -32767 (not clamped further to -32768)");
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static string Ascii(byte[] buf, int offset, int count) =>
        System.Text.Encoding.ASCII.GetString(buf, offset, count);

    private static uint ReadUInt32(byte[] buf, int offset) =>
        (uint)(buf[offset] | (buf[offset + 1] << 8) | (buf[offset + 2] << 16) | (buf[offset + 3] << 24));

    private static ushort ReadUInt16(byte[] buf, int offset) =>
        (ushort)(buf[offset] | (buf[offset + 1] << 8));

    private static short ReadInt16(byte[] buf, int offset) =>
        (short)(buf[offset] | (buf[offset + 1] << 8));
}
