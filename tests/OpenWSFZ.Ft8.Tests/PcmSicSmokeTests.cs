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
/// Integration smoke-test for the PCM-domain SIC H3 diagnostic (diag-d001-pcm-sic, T2 gate).
///
/// <para>
/// Verifies that <see cref="Ft8Decoder.DecodeAsync"/> successfully produces a non-empty result
/// from the committed <c>synth-qso-01</c> fixture WAV (the same fixture used by
/// <see cref="RealSignalFixtureTests"/>) after the PCM-residual waterfall rebuild change.
/// </para>
///
/// <para>
/// This test is specifically gated on shim version 20260008. If the native binary is stale
/// (still at 20260006 or 20260007), the <see cref="Ft8LibInterop"/> ABI self-test will throw
/// <see cref="InvalidOperationException"/> before any decode call is attempted and this test
/// will fail with a clear diagnostic message.
/// </para>
///
/// <para>
/// The test must remain GREEN before T2 is merged. If it fails after the shim rebuild, the
/// root cause is either a regression in the PCM-domain SIC implementation (see
/// <c>ft8_shim.c synth_ft8_cpsfc</c> / <c>compute_projection_amplitude</c>) or a stale
/// native binary (run <c>rebuild_shim_new.bat</c> on Windows or <c>build_linux.sh</c> on
/// Linux, then <c>dotnet build</c>).
/// </para>
/// </summary>
public sealed class PcmSicSmokeTests
{
    [Fact(DisplayName = "H3/T2 gate: Ft8Decoder.DecodeAsync with synth-qso-01 returns non-empty results (shim 20260008 PCM-SIC integration)")]
    public async Task DecodeAsync_SynthQso01_ReturnsNonEmptyResults()
    {
        // Arrange — load the synth-qso-01 fixture (same WAV used by RealSignalFixtureTests)
        float[] pcm = LoadEmbeddedWav("Fixtures/synth-qso-01.wav");
        string[] expectedMessages = LoadEmbeddedAnswerKey("Fixtures/synth-qso-01.expected.txt");

        expectedMessages.Should().NotBeEmpty("the answer-key file must contain at least one expected message");

        var clock   = new FakeClock(new DateTime(2026, 5, 28, 23, 57, 45, DateTimeKind.Utc));
        var decoder = new Ft8Decoder(clock);

        // Act
        var results = await decoder.DecodeAsync(pcm, CancellationToken.None);

        // Assert 1: non-empty
        results.Should().NotBeEmpty(
            "the PCM-domain SIC path (shim 20260008) must produce at least one decoded message " +
            "from the synth-qso-01 fixture — a crash, hang, or all-zero residual that silences " +
            "all signals would produce an empty result and indicate a regression in T2");

        // Assert 2: expected messages present
        var decodedMessages = results.Select(r => r.Message).ToList();
        foreach (string expected in expectedMessages)
        {
            decodedMessages.Should().Contain(expected,
                because: $"synth-qso-01 answer-key expects '{expected}'; " +
                         $"the PCM-domain SIC waterfall rebuild must not suppress pass-0 signals " +
                         $"to the point that they are completely lost from the combined result set. " +
                         $"Currently decoded: [{string.Join(", ", decodedMessages)}]");
        }
    }

    // ── Helpers (mirrors RealSignalFixtureTests) ──────────────────────────────

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
        Assembly asm      = typeof(PcmSicSmokeTests).Assembly;
        string   asmName  = asm.GetName().Name!;
        string   resName  = $"{asmName}.{resourceSuffix.Replace('/', '.')}";

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
