using System.Reflection;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Reads an IEEE float-32 (PCM_IEEE_FLOAT, format code 3) WAV file from an embedded
/// assembly resource and returns the samples as a <c>float[]</c> array.
///
/// The reader handles only the subset of WAV features used by the
/// <c>GenerateFt8Fixture</c> tool: single-chunk RIFF, 32-bit float, mono or
/// multi-channel (first channel returned if stereo).  It will throw a meaningful
/// <see cref="InvalidDataException"/> for anything it does not support.
/// </summary>
internal static class WavFixtureHelper
{
    /// <summary>
    /// Loads an embedded WAV resource from this assembly and returns its samples as
    /// <c>float[]</c>.
    /// </summary>
    /// <param name="resourceName">
    ///   The partial resource name as it appears in the manifest (e.g. "ft8-sample.wav").
    ///   Resolved to the first manifest resource whose full name ends with the given string.
    /// </param>
    /// <returns>
    ///   A <c>float[]</c> of PCM samples from the WAV file's first channel.
    /// </returns>
    public static float[] LoadEmbeddedWav(string resourceName)
    {
        var asm  = Assembly.GetExecutingAssembly();
        var name = asm.GetManifestResourceNames()
                      .FirstOrDefault(n => n.EndsWith(resourceName, StringComparison.OrdinalIgnoreCase))
                   ?? throw new InvalidOperationException(
                       $"Embedded resource '{resourceName}' not found. " +
                       $"Available: {string.Join(", ", asm.GetManifestResourceNames())}");

        using var stream = asm.GetManifestResourceStream(name)!;
        using var reader = new BinaryReader(stream);

        // ── RIFF header ───────────────────────────────────────────────────────
        var riff = ReadFourCc(reader);
        if (riff != "RIFF")
            throw new InvalidDataException($"Expected 'RIFF', got '{riff}'");

        reader.ReadInt32(); // chunk size (ignored)

        var wave = ReadFourCc(reader);
        if (wave != "WAVE")
            throw new InvalidDataException($"Expected 'WAVE', got '{wave}'");

        // ── Parse chunks until we find fmt and data ───────────────────────────
        ushort audioFormat  = 0;
        ushort channels     = 0;
        int    sampleRate   = 0;
        ushort bitsPerSample = 0;
        float[]? samples    = null;

        while (stream.Position < stream.Length - 8)
        {
            var chunkId   = ReadFourCc(reader);
            var chunkSize = reader.ReadInt32();

            if (chunkId == "fmt ")
            {
                audioFormat   = reader.ReadUInt16();
                channels      = reader.ReadUInt16();
                sampleRate    = reader.ReadInt32();
                reader.ReadInt32();  // byteRate
                reader.ReadUInt16(); // blockAlign
                bitsPerSample = reader.ReadUInt16();

                // Skip any extra fmt bytes (e.g. extensible header)
                int extraBytes = chunkSize - 16;
                if (extraBytes > 0) reader.ReadBytes(extraBytes);
            }
            else if (chunkId == "data")
            {
                if (audioFormat == 0)
                    throw new InvalidDataException("data chunk encountered before fmt chunk");

                if (audioFormat != 3 || bitsPerSample != 32)
                    throw new NotSupportedException(
                        $"Only IEEE float-32 WAV (format=3, bits=32) is supported; " +
                        $"got format={audioFormat}, bits={bitsPerSample}");

                int frameCount  = chunkSize / (channels * 4);
                samples = new float[frameCount];

                for (int i = 0; i < frameCount; i++)
                {
                    float ch0 = reader.ReadSingle(); // take first channel
                    for (int c = 1; c < channels; c++)
                        reader.ReadSingle();         // discard remaining channels
                    samples[i] = ch0;
                }
            }
            else
            {
                // Skip unknown chunk (align to even byte boundary per WAV spec)
                var skip = chunkSize % 2 == 0 ? chunkSize : chunkSize + 1;
                reader.ReadBytes(skip);
            }
        }

        return samples
            ?? throw new InvalidDataException("WAV file contained no 'data' chunk");
    }

    /// <summary>
    /// Loads the lines of an embedded text resource (e.g. "ft8-sample.ref").
    /// Blank lines are excluded; leading/trailing whitespace is trimmed.
    /// </summary>
    public static IReadOnlyList<string> LoadEmbeddedLines(string resourceName)
    {
        var asm  = Assembly.GetExecutingAssembly();
        var name = asm.GetManifestResourceNames()
                      .FirstOrDefault(n => n.EndsWith(resourceName, StringComparison.OrdinalIgnoreCase))
                   ?? throw new InvalidOperationException(
                       $"Embedded resource '{resourceName}' not found.");

        using var stream = asm.GetManifestResourceStream(name)!;
        using var reader = new StreamReader(stream);
        var lines = new List<string>();
        string? line;
        while ((line = reader.ReadLine()) != null)
        {
            line = line.Trim();
            if (line.Length > 0) lines.Add(line);
        }
        return lines;
    }

    private static string ReadFourCc(BinaryReader r)
    {
        var bytes = r.ReadBytes(4);
        return System.Text.Encoding.ASCII.GetString(bytes);
    }
}
