using System;
using System.IO;
using System.Text;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Minimal WAV reader that converts a 12 kHz mono int16 PCM WAV file into the
/// normalised <c>float[]</c> PCM buffer accepted by <see cref="Ft8Decoder.DecodeAsync"/>.
///
/// Only 12 kHz / mono (1 channel) / 16-bit linear PCM WAVs are accepted — exactly
/// the format WSJT-X's <em>File → Save → Save All</em> produces. Any other format is
/// rejected with a clear <see cref="InvalidDataException"/> rather than silently
/// misinterpreting the samples.
///
/// Implements the WAV-to-PCM reader defined in the <c>decoder-ground-truth</c> spec
/// (FR-029).
/// </summary>
internal static class WavReader
{
    private const int   RequiredSampleRate   = 12_000;
    private const short RequiredChannels     = 1;
    private const short RequiredBitsPerSample = 16;
    private const short PcmAudioFormat       = 1; // Linear PCM

    /// <summary>
    /// Reads a 12 kHz mono int16 WAV file and returns the samples normalised
    /// to <c>[-1, 1]</c> as required by <c>Ft8Decoder.DecodeAsync</c>.
    /// </summary>
    /// <param name="path">Absolute or relative path to the WAV file.</param>
    /// <returns>
    /// Normalised PCM samples; length equals the WAV's sample count.
    /// </returns>
    /// <exception cref="InvalidDataException">
    /// Thrown when the file is not a 12 kHz mono int16 PCM WAV.
    /// </exception>
    public static float[] Read(string path)
    {
        using var fs = File.OpenRead(path);
        return Read(fs);
    }

    /// <summary>
    /// Reads a 12 kHz mono int16 WAV from the provided <paramref name="stream"/>
    /// and returns the samples normalised to <c>[-1, 1]</c>.
    /// </summary>
    /// <exception cref="InvalidDataException">
    /// Thrown when the stream does not contain a valid 12 kHz mono int16 PCM WAV.
    /// </exception>
    public static float[] Read(Stream stream)
    {
        using var reader = new BinaryReader(stream, Encoding.ASCII, leaveOpen: true);

        // ── RIFF header ──────────────────────────────────────────────────────
        string riff = ReadFourCC(reader);
        if (riff != "RIFF")
            throw new InvalidDataException($"Not a RIFF file (got '{riff}').");

        reader.ReadInt32(); // overall file size — not needed

        string wave = ReadFourCC(reader);
        if (wave != "WAVE")
            throw new InvalidDataException($"RIFF subtype is not WAVE (got '{wave}').");

        // ── Walk chunks ───────────────────────────────────────────────────────
        short  audioFormat   = 0;
        short  channels      = 0;
        int    sampleRate    = 0;
        short  bitsPerSample = 0;
        byte[]? audioData    = null;

        while (stream.Position + 8 <= stream.Length)
        {
            string chunkId   = ReadFourCC(reader);
            int    chunkSize = reader.ReadInt32();

            switch (chunkId)
            {
                case "fmt ":
                    audioFormat   = reader.ReadInt16();
                    channels      = reader.ReadInt16();
                    sampleRate    = reader.ReadInt32();
                    reader.ReadInt32(); // byte rate — skip
                    reader.ReadInt16(); // block align — skip
                    bitsPerSample = reader.ReadInt16();
                    // Skip any extension bytes (e.g., extensible format extra fields)
                    int extra = chunkSize - 16;
                    if (extra > 0) reader.ReadBytes(extra);
                    // RIFF spec: chunks with odd data size are followed by one pad byte.
                    if (chunkSize % 2 != 0 && stream.Position < stream.Length) reader.ReadByte();
                    break;

                case "data":
                    audioData = reader.ReadBytes(chunkSize);
                    // RIFF spec: chunks with odd data size are followed by one pad byte.
                    if (chunkSize % 2 != 0 && stream.Position < stream.Length) reader.ReadByte();
                    break;

                default:
                    // Skip unknown/optional chunks (INFO, LIST, JUNK, etc.)
                    reader.ReadBytes(chunkSize);
                    // RIFF spec: chunks with odd data size are followed by one pad byte.
                    if (chunkSize % 2 != 0 && stream.Position < stream.Length) reader.ReadByte();
                    break;
            }
        }

        // ── Validate ──────────────────────────────────────────────────────────
        if (audioFormat != PcmAudioFormat)
            throw new InvalidDataException(
                $"WAV audio format must be linear PCM (1); got {audioFormat}. " +
                $"Only uncompressed PCM WAVs are supported.");

        if (channels != RequiredChannels)
            throw new InvalidDataException(
                $"WAV must be mono (1 channel); got {channels} channels. " +
                $"WSJT-X Save All produces mono recordings.");

        if (sampleRate != RequiredSampleRate)
            throw new InvalidDataException(
                $"WAV sample rate must be {RequiredSampleRate} Hz; got {sampleRate} Hz. " +
                $"WSJT-X Save All produces 12 000 Hz recordings.");

        if (bitsPerSample != RequiredBitsPerSample)
            throw new InvalidDataException(
                $"WAV must be 16-bit PCM; got {bitsPerSample} bits per sample.");

        if (audioData is null || audioData.Length == 0)
            throw new InvalidDataException("WAV file contains no audio data (data chunk missing or empty).");

        // ── Convert int16 → float [-1, 1] ────────────────────────────────────
        int     sampleCount = audioData.Length / 2;
        float[] pcm         = new float[sampleCount];

        for (int i = 0; i < sampleCount; i++)
        {
            short s = (short)(audioData[i * 2] | (audioData[i * 2 + 1] << 8));
            pcm[i]  = s / 32768.0f;
        }

        return pcm;
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    /// <summary>Reads exactly 4 bytes from the reader and returns them as an ASCII string.</summary>
    private static string ReadFourCC(BinaryReader reader)
    {
        byte[] b = reader.ReadBytes(4);
        if (b.Length < 4)
            throw new InvalidDataException("Unexpected end of stream while reading WAV chunk header.");
        return Encoding.ASCII.GetString(b);
    }
}
