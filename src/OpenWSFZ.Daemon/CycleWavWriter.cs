namespace OpenWSFZ.Daemon;

/// <summary>
/// Encodes a decode cycle's PCM window into a canonical, WSJT-X-byte-compatible RIFF/WAVE file
/// (<c>cycle-audio-archive</c> capability, design.md Decision 4): 12 000 Hz, mono, 16-bit signed
/// PCM, a 44-byte canonical header, no extension chunks.
///
/// <para>
/// Deliberately does not use NAudio's <c>WaveFileWriter</c> — <c>OpenWSFZ.Audio.csproj</c>
/// package-references NAudio only under <c>Condition="$([MSBuild]::IsOSPlatform('Windows'))"</c>,
/// so a NAudio call here would break the Linux (<c>arecord</c>) and macOS (<c>sox</c>) builds. A
/// canonical 44-byte header written directly against raw bytes has no such dependency and is
/// cross-platform by construction.
/// </para>
/// </summary>
public static class CycleWavWriter
{
    /// <summary>Sample rate of every archived file, matching WSJT-X's own recordings.</summary>
    public const int SampleRateHz = 12_000;

    /// <summary>Channel count of every archived file (mono).</summary>
    public const int Channels = 1;

    /// <summary>Bit depth of every archived file (16-bit signed PCM).</summary>
    public const int BitsPerSample = 16;

    /// <summary>Size in bytes of the canonical RIFF/WAVE header this writer emits.</summary>
    public const int HeaderSize = 44;

    /// <summary>
    /// Encodes <paramref name="pcm"/> (float samples, expected in [-1, 1]) into a complete
    /// RIFF/WAVE byte buffer, converting each sample to 16-bit signed PCM by scaling by 32767,
    /// rounding to the nearest integer, and clamping to the representable range
    /// (design.md Decision 4).
    /// </summary>
    /// <param name="pcm">Float PCM samples for one decode cycle window.</param>
    /// <returns>
    /// The complete file bytes (header + data) and the count of samples that required clamping
    /// (a nonzero count indicates an input-level problem and is recorded in the manifest).
    /// </returns>
    public static (byte[] Bytes, int ClippedSamples) Encode(float[] pcm)
    {
        ArgumentNullException.ThrowIfNull(pcm);

        int dataSize = pcm.Length * (BitsPerSample / 8);
        var buffer   = new byte[HeaderSize + dataSize];

        WriteHeader(buffer, dataSize);

        int clipped = 0;
        int offset  = HeaderSize;
        for (int i = 0; i < pcm.Length; i++)
        {
            float scaled = MathF.Round(pcm[i] * 32767f);
            if (scaled > 32767f || scaled < -32768f)
                clipped++;

            short sample = (short)Math.Clamp(scaled, -32768f, 32767f);
            buffer[offset]     = (byte)(sample & 0xFF);
            buffer[offset + 1] = (byte)((sample >> 8) & 0xFF);
            offset += 2;
        }

        return (buffer, clipped);
    }

    // ── Private helpers ───────────────────────────────────────────────────────

    private static void WriteHeader(byte[] buffer, int dataSize)
    {
        int   byteRate   = SampleRateHz * Channels * BitsPerSample / 8;
        short blockAlign = (short)(Channels * BitsPerSample / 8);

        WriteAscii (buffer,  0, "RIFF");
        WriteUInt32(buffer,  4, (uint)(36 + dataSize)); // total file size − 8
        WriteAscii (buffer,  8, "WAVE");
        WriteAscii (buffer, 12, "fmt ");
        WriteUInt32(buffer, 16, 16);                    // fmt chunk size (16 for PCM, no extension)
        WriteUInt16(buffer, 20, 1);                     // audio format = 1 (PCM)
        WriteUInt16(buffer, 22, (ushort)Channels);
        WriteUInt32(buffer, 24, SampleRateHz);
        WriteUInt32(buffer, 28, (uint)byteRate);
        WriteUInt16(buffer, 32, (ushort)blockAlign);
        WriteUInt16(buffer, 34, BitsPerSample);
        WriteAscii (buffer, 36, "data");
        WriteUInt32(buffer, 40, (uint)dataSize);
    }

    private static void WriteAscii(byte[] buffer, int offset, string ascii)
    {
        for (int i = 0; i < ascii.Length; i++)
            buffer[offset + i] = (byte)ascii[i];
    }

    private static void WriteUInt32(byte[] buffer, int offset, uint value)
    {
        buffer[offset]     = (byte)(value & 0xFF);
        buffer[offset + 1] = (byte)((value >> 8)  & 0xFF);
        buffer[offset + 2] = (byte)((value >> 16) & 0xFF);
        buffer[offset + 3] = (byte)((value >> 24) & 0xFF);
    }

    private static void WriteUInt16(byte[] buffer, int offset, ushort value)
    {
        buffer[offset]     = (byte)(value & 0xFF);
        buffer[offset + 1] = (byte)((value >> 8) & 0xFF);
    }
}
