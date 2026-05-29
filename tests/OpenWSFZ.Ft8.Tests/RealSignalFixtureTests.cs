using System;
using System.Collections.Generic;
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
/// FR-029: Real-signal fixture integration test — the authoritative correctness oracle
/// for the FT8 decoder.
///
/// Each fixture is a real off-air WAV recording captured via WSJT-X Save All on
/// 7.074 MHz (12 kHz mono int16 PCM). Each WAV is paired with an answer-key
/// subset listing the strongest signals WSJT-X decoded from the identical
/// recording. This test asserts that <see cref="Ft8Decoder.DecodeAsync"/> recovers
/// those signals.
///
/// <para><strong>This test is expected to be RED</strong> until the decoder is
/// fixed in a follow-on change (Phase 2A — port <c>ft8_lib</c>, or Phase 2B —
/// patch). A red result here is not a broken test — it is the measurement proving
/// the decoder cannot decode real off-air FT8 signals, as documented in
/// <c>RECOVERY_PLAN.md</c> and <c>findings.md</c>.</para>
///
/// <para>Gate G6 (NFR-016): this test runs in CI on every push and PR to
/// <c>main</c>. Once the decoder is fixed in a later change and this test goes
/// green, it must remain green — any regression that makes it red again will
/// block merge.</para>
/// </summary>
public sealed class RealSignalFixtureTests
{
    // ── Fixture data ──────────────────────────────────────────────────────────

    /// <summary>
    /// Provides the three committed real-signal fixture WAVs and their
    /// WSJT-X answer-key subsets as xUnit theory data.
    /// </summary>
    public static IEnumerable<object[]> Fixtures()
    {
        yield return new object[] { "260528_235745", new DateTime(2026, 5, 28, 23, 57, 45, DateTimeKind.Utc) };
        yield return new object[] { "260529_000030", new DateTime(2026, 5, 29,  0,  0, 30, DateTimeKind.Utc) };
        yield return new object[] { "260529_000200", new DateTime(2026, 5, 29,  0,  2,  0, DateTimeKind.Utc) };
    }

    // ── Gate test ─────────────────────────────────────────────────────────────

    [WindowsOnlyTheory(DisplayName = "FR-029: FT8 decoder recovers known real off-air signals from committed WAV fixture (G6 gate — NFR-016)")]
    [MemberData(nameof(Fixtures))]
    public async Task DecodeAsync_RealSignalFixture_ContainsAnswerKeyMessages(
        string fixtureId,
        DateTime cycleUtc)
    {
        // ── Load embedded WAV ─────────────────────────────────────────────────
        float[] pcm = LoadEmbeddedWav($"Fixtures/{fixtureId}.wav");

        // ── Load embedded answer-key subset ──────────────────────────────────
        string[] expectedMessages = LoadEmbeddedAnswerKey($"Fixtures/{fixtureId}.expected.txt");

        expectedMessages.Should().NotBeEmpty(
            "the answer-key file must contain at least one expected message");

        // ── Decode ────────────────────────────────────────────────────────────
        var clock   = new FakeClock(cycleUtc);
        var decoder = new Ft8Decoder(clock);
        var results = await decoder.DecodeAsync(pcm, CancellationToken.None);

        var decodedMessages = results.Select(r => r.Message).ToList();

        // ── Assert answer-key subset is recovered ─────────────────────────────
        // Each expected message must appear in the decoded results.
        // This test is expected RED until the decoder is fixed (RECOVERY_PLAN.md §5).
        foreach (string expected in expectedMessages)
        {
            decodedMessages.Should().Contain(expected,
                because: $"fixture '{fixtureId}' — WSJT-X decoded '{expected}' from the same audio; " +
                         $"a correct FT8 decoder must recover it. " +
                         $"Currently decoded: [{string.Join(", ", decodedMessages)}]");
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

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
        Assembly asm  = typeof(RealSignalFixtureTests).Assembly;
        string asmName = asm.GetName().Name!;

        // Resource names use dots as separators and replace slashes
        string resourceName = $"{asmName}.{resourceSuffix.Replace('/', '.')}";

        Stream? stream = asm.GetManifestResourceStream(resourceName);
        if (stream is null)
        {
            // Try alternative naming (underscores may be preserved)
            string[] allNames = asm.GetManifestResourceNames();
            stream = allNames
                .Where(n => n.EndsWith(resourceSuffix.Replace('/', '.'), StringComparison.OrdinalIgnoreCase))
                .Select(n => asm.GetManifestResourceStream(n))
                .FirstOrDefault(s => s is not null);
        }

        return stream
               ?? throw new InvalidOperationException(
                   $"Embedded resource '{resourceName}' not found. " +
                   $"Available: [{string.Join(", ", asm.GetManifestResourceNames())}]");
    }
}
