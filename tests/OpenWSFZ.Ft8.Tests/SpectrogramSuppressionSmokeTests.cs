using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Threading;
using System.Threading.Tasks;
using FluentAssertions;
using OpenWSFZ.Ft8;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Integration smoke-test for the two-pass spectrogram-domain soft-SNR tile suppression
/// path (H5 constant tuning, diag-d001-h5-suppression-tuning, shim 20260011).
///
/// <para>
/// Verifies that <see cref="Ft8Decoder.DecodeAsync"/> successfully produces a non-empty
/// result from the committed <c>synth-qso-01</c> fixture WAV and that every message in
/// the answer key is decoded, with the suppression ramp shifted to [−15, +5] dB
/// (75% suppression at 0 dB SNR vs 25% in H4).
/// </para>
///
/// <para>
/// This test is the H5 smoke-gate: it runs against the rebuilt native binary at shim
/// version 20260011, with <c>Ft8LibInterop.ExpectedShimVersion</c> set to
/// <c>20260011</c>.
/// </para>
///
/// <para>
/// If this test fails, the root cause is either a regression in the spectrogram
/// suppression path (see <c>ft8_shim.c suppress_candidate_tiles</c>) or a stale
/// native binary — run the rebuild script
/// (Windows: <c>rebuild_shim_new.bat</c>; Linux: <c>build_linux.sh</c>) then
/// <c>dotnet build</c>.
/// </para>
/// </summary>
public sealed class SpectrogramSuppressionSmokeTests
{
    [Fact(DisplayName = "H5 smoke: Ft8Decoder.DecodeAsync with synth-qso-01 returns expected results (shim 20260011 suppression ramp [−15, +5])")]
    public async Task DecodeAsync_SynthQso01_ReturnsExpectedResults_SpectrogramSuppression()
    {
        // Arrange — load the synth-qso-01 fixture (same WAV used by PcmSicSmokeTests)
        float[] pcm = LoadEmbeddedWav("Fixtures/synth-qso-01.wav");
        string[] expectedMessages = LoadEmbeddedAnswerKey("Fixtures/synth-qso-01.expected.txt");

        expectedMessages.Should().NotBeEmpty("the answer-key file must contain at least one expected message");

        var clock   = new FakeClock(new DateTime(2026, 5, 28, 23, 57, 45, DateTimeKind.Utc));
        var decoder = new Ft8Decoder(clock);

        // Act
        var results = await decoder.DecodeAsync(pcm, CancellationToken.None);

        // Assert 1: non-empty
        results.Should().NotBeEmpty(
            "the spectrogram suppression path (shim 20260011, ramp [−15, +5]) must produce at least one decoded " +
            "message from the synth-qso-01 fixture — a crash, hang, or suppression failure " +
            "that silences all signals would produce an empty result and indicate a regression");

        // Assert 2: all answer-key messages decoded
        var decodedMessages = results.Select(r => r.Message).ToList();
        foreach (string expected in expectedMessages)
        {
            decodedMessages.Should().Contain(expected,
                because: $"synth-qso-01 answer-key expects '{expected}'; " +
                         $"spectrogram suppression must not attenuate pass-0 signals to the " +
                         $"point they are completely lost from the combined result set. " +
                         $"Currently decoded: [{string.Join(", ", decodedMessages)}]");
        }
    }

    // ── Helpers (mirrors PcmSicSmokeTests) ──────────────────────────────────

    private static float[] LoadEmbeddedWav(string resourceSuffix)
    {
        using Stream stream = OpenEmbeddedResource(resourceSuffix);
        return WavReader.Read(stream);
    }

    private static string[] LoadEmbeddedAnswerKey(string resourceSuffix)
    {
        using Stream stream = OpenEmbeddedResource(resourceSuffix);
        using var reader    = new StreamReader(stream);
        return reader.ReadToEnd()
                     .Split('\n', StringSplitOptions.RemoveEmptyEntries)
                     .Select(l => l.Trim())
                     .Where(l => l.Length > 0 && !l.StartsWith('#'))
                     .ToArray();
    }

    private static Stream OpenEmbeddedResource(string resourceSuffix)
    {
        Assembly asm     = typeof(SpectrogramSuppressionSmokeTests).Assembly;
        string   asmName = asm.GetName().Name!;
        string   resName = $"{asmName}.{resourceSuffix.Replace('/', '.')}";

        Stream? stream = asm.GetManifestResourceStream(resName);
        if (stream is null)
        {
            string[] all = asm.GetManifestResourceNames();
            stream = all
                .Where(n => n.EndsWith(resourceSuffix.Replace('/', '.'), StringComparison.OrdinalIgnoreCase))
                .Select(n => asm.GetManifestResourceStream(n))
                .FirstOrDefault(s => s is not null);
        }

        return stream
               ?? throw new InvalidOperationException(
                   $"Embedded resource '{resName}' not found. " +
                   $"Available: [{string.Join(", ", asm.GetManifestResourceNames())}]");
    }
}
