using FluentAssertions;
using OpenWSFZ.Ft8;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Ft8Decoder: Ft8DecoderFixtureTests
///
/// Full-pipeline integration test using an embedded WAV fixture.
/// Skipped until ft8-sample.wav is committed to Fixtures/ (task 8.1–8.2).
/// </summary>
public sealed class Ft8DecoderFixtureTests
{
    [Fact(Skip = "WAV fixture not yet committed — see task 8.1")]
    public async Task DecodeAsync_WavFixture_ReturnsKnownDecodes()
    {
        // Load the WAV fixture from embedded resources.
        var assembly = typeof(Ft8DecoderFixtureTests).Assembly;
        const string resourceName = "OpenWSFZ.Ft8.Tests.Fixtures.ft8-sample.raw";

        await using var stream = assembly.GetManifestResourceStream(resourceName)
            ?? throw new InvalidOperationException($"Embedded resource '{resourceName}' not found.");

        // Read raw 32-bit float LE PCM (15 s × 12 000 Hz = 180 000 samples).
        const int sampleCount = 180_000;
        var pcm = new float[sampleCount];
        var bytes = new byte[sampleCount * 4];
        _ = await stream.ReadAsync(bytes.AsMemory());
        Buffer.BlockCopy(bytes, 0, pcm, 0, bytes.Length);

        // Load reference decodes.
        const string refResource = "OpenWSFZ.Ft8.Tests.Fixtures.ft8-sample.ref";
        await using var refStream = assembly.GetManifestResourceStream(refResource)
            ?? throw new InvalidOperationException($"Reference file '{refResource}' not found.");
        using var reader = new StreamReader(refStream);
        var referenceMessages = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        string? line;
        while ((line = await reader.ReadLineAsync()) is not null)
        {
            if (!string.IsNullOrWhiteSpace(line))
                referenceMessages.Add(line.Trim());
        }

        // Decode.
        var clock   = new FakeClock(new DateTime(2026, 5, 21, 15, 30, 0, DateTimeKind.Utc));
        var decoder = new Ft8Decoder(clock);
        var results = await decoder.DecodeAsync(pcm, CancellationToken.None);

        results.Should().NotBeEmpty("the fixture should contain at least one decodable FT8 message");
        var decodedMessages = results.Select(r => r.Message).ToHashSet();
        decodedMessages.Should().IntersectWith(referenceMessages,
            "at least one decoded message should match the reference file");
    }

    [Fact]
    public async Task DecodeAsync_SilentPcm_ReturnsEmptyList()
    {
        var clock   = new FakeClock(new DateTime(2026, 5, 21, 15, 30, 0, DateTimeKind.Utc));
        var decoder = new Ft8Decoder(clock);
        var pcm     = new float[180_000]; // all zeros

        var results = await decoder.DecodeAsync(pcm, CancellationToken.None);

        results.Should().BeEmpty("silence should produce no decoded messages");
    }

    [Fact]
    public async Task DecodeAsync_Cancelled_ThrowsOperationCancelled()
    {
        var clock   = new FakeClock(new DateTime(2026, 5, 21, 15, 30, 0, DateTimeKind.Utc));
        var decoder = new Ft8Decoder(clock);
        var pcm     = new float[180_000];

        using var cts = new CancellationTokenSource();
        cts.Cancel();

        var act = async () => await decoder.DecodeAsync(pcm, cts.Token);
        await act.Should().ThrowAsync<OperationCanceledException>();
    }
}
