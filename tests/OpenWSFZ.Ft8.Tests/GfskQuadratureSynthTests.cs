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
/// Integration smoke-test for the GFSK quadrature PCM-domain SIC (H3b diagnostic,
/// diag-d001-h3b-gfsk-sic, shim 20260009).
///
/// <para>
/// Verifies that <see cref="Ft8Decoder.DecodeAsync"/> successfully produces a non-empty
/// result from the committed <c>synth-qso-01</c> fixture WAV after the GFSK quadrature
/// synthesiser replaces the CP-FSK scalar synthesiser in the inter-pass SIC stage.
/// </para>
///
/// <para>
/// This test is marked <c>[Fact(Skip = "Wired in T2")]</c> for T1: the C source has been
/// updated but the native binary has not yet been rebuilt at shim version 20260009.
/// The <c>Skip</c> attribute is removed in T2 (diag-d001-h3b-gfsk-sic task 2.9), after
/// the binary is rebuilt and <see cref="Ft8LibInterop"/> <c>ExpectedShimVersion</c> is
/// updated to <c>20260009</c>.
/// </para>
///
/// <para>
/// If this test fails after the shim rebuild, the root cause is either a regression in
/// the GFSK quadrature SIC implementation (see <c>ft8_shim.c synth_ft8_gfsk_quad</c> /
/// <c>compute_quadrature_amplitude</c>) or a stale native binary — run the rebuild script
/// (Windows: <c>rebuild_shim_new.bat</c>; Linux: <c>build_linux.sh</c>) then
/// <c>dotnet build</c>.
/// </para>
/// </summary>
public sealed class GfskQuadratureSynthTests
{
    [Fact(DisplayName = "H3b/T2 gate: Ft8Decoder.DecodeAsync with synth-qso-01 returns expected results (shim 20260009 GFSK quadrature SIC)")]
    public async Task DecodeAsync_SynthQso01_ReturnsExpectedResults_GfskQuadratureSic()
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
            "the GFSK quadrature SIC path (shim 20260009) must produce at least one decoded " +
            "message from the synth-qso-01 fixture — a crash, hang, or amplitude near-zero " +
            "that silences all signals would produce an empty result and indicate a regression");

        // Assert 2: all answer-key messages decoded
        var decodedMessages = results.Select(r => r.Message).ToList();
        foreach (string expected in expectedMessages)
        {
            decodedMessages.Should().Contain(expected,
                because: $"synth-qso-01 answer-key expects '{expected}'; " +
                         $"the GFSK quadrature SIC must not suppress pass-0 signals to the " +
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
        Assembly asm     = typeof(GfskQuadratureSynthTests).Assembly;
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
