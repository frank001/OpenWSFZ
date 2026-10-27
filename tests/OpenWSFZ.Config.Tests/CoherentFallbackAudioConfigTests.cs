using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Config;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Config.Tests;

/// <summary>
/// COH-FB-AUDIO: <c>decoder.coherentFallbackAudio</c> defaults to <c>Residual</c> (an absent key, and a missing decoder section, read Residual); an explicit
/// <c>Original</c> / <c>Residual</c> / <c>Both</c> is read by name (case-insensitively) and survives a load, an unrelated save and a reload. HK-035: what an
/// ABSENT key deserialises to is checked through the real source-generated deserialisation and the real <see cref="JsonConfigStore"/> path.
/// </summary>
public sealed class CoherentFallbackAudioConfigTests
{
    private sealed class TempDirectory : IDisposable
    {
        public string Path { get; } = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "openwsfz-cohaudio-" + System.IO.Path.GetRandomFileName());
        public TempDirectory() => Directory.CreateDirectory(Path);
        public void Dispose() { try { Directory.Delete(Path, recursive: true); } catch { /* best-effort */ } }
    }

    private static string ConfigPath(TempDirectory dir) => System.IO.Path.Combine(dir.Path, "config.json");

    private static CoherentFallbackAudio Effective(JsonConfigStore store) => (store.Current.Decoder ?? new DecoderConfig()).CoherentFallbackAudio;

    // Both markers true so no migration rewrites the decoder section: the file under test is read as written.
    private const string MarkersOnly = "\"nhard40MigrationApplied\":true,\"subtractionOnMigrationApplied\":true";

    [Fact(DisplayName = "FR-099: COH-FB-AUDIO: the code default is Residual, an absent key reads Residual, explicit values are read by name (any case), the wire name is camelCase")]
    public void CodeDefault_IsResidual_AbsentKeyReadsResidual()
    {
        new DecoderConfig().CoherentFallbackAudio.Should().Be(CoherentFallbackAudio.Residual);
        JsonSerializer.Deserialize("""{"decoder":{}}""", ConfigJsonContext.Default.AppConfig)!
            .Decoder!.CoherentFallbackAudio.Should().Be(CoherentFallbackAudio.Residual);
        JsonSerializer.Deserialize("""{"decoder":{"coherentFallbackEnabled":true}}""", ConfigJsonContext.Default.AppConfig)!
            .Decoder!.CoherentFallbackAudio.Should().Be(CoherentFallbackAudio.Residual, "a body for another flag leaves this one at its default");
        foreach (var (name, expected) in new[]
        {
            ("Original", CoherentFallbackAudio.Original), ("Residual", CoherentFallbackAudio.Residual), ("Both", CoherentFallbackAudio.Both),
            ("original", CoherentFallbackAudio.Original), ("BOTH", CoherentFallbackAudio.Both),
        })
        {
            string json = "{\"decoder\":{\"coherentFallbackAudio\":\"" + name + "\"}}";
            JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)!
                .Decoder!.CoherentFallbackAudio.Should().Be(expected, name);
        }

        using var doc = JsonDocument.Parse(JsonSerializer.Serialize(new DecoderConfig { CoherentFallbackAudio = CoherentFallbackAudio.Both }, ConfigJsonContext.Default.DecoderConfig));
        doc.RootElement.GetProperty("coherentFallbackAudio").GetString().Should().Be("Both", "serialised by name");
    }

    [Fact(DisplayName = "FR-099: COH-FB-AUDIO: a stored decoder section without the key loads Residual; saved back it carries the key")]
    public async Task StoredWithoutTheKey_LoadsResidual_SavesResidual()
    {
        using var dir = new TempDirectory();
        File.WriteAllText(ConfigPath(dir), "{\"decoder\":{\"kMinScorePass2\":10," + MarkersOnly + "}}");

        var store = new JsonConfigStore(ConfigPath(dir));
        Effective(store).Should().Be(CoherentFallbackAudio.Residual);

        await store.SaveAsync(store.Current with { ShowCycleCountdown = !store.Current.ShowCycleCountdown });
        using var written = JsonDocument.Parse(File.ReadAllText(ConfigPath(dir)));
        written.RootElement.GetProperty("decoder").GetProperty("coherentFallbackAudio").GetString().Should().Be("Residual");
    }

    [Fact(DisplayName = "FR-099: COH-FB-AUDIO: a config file with no decoder section at all reads Residual")]
    public void NoDecoderSection_ReadsResidual()
    {
        using var dir = new TempDirectory();
        File.WriteAllText(ConfigPath(dir), "{\"showCycleCountdown\":true," + MarkersOnly + "}");
        Effective(new JsonConfigStore(ConfigPath(dir))).Should().Be(CoherentFallbackAudio.Residual);
    }

    [Theory(DisplayName = "FR-099: COH-FB-AUDIO: an explicit value survives a load, an unrelated save and a reload")]
    [InlineData("Original", CoherentFallbackAudio.Original)]
    [InlineData("Residual", CoherentFallbackAudio.Residual)]
    [InlineData("Both", CoherentFallbackAudio.Both)]
    public async Task ExplicitValue_Survives(string name, CoherentFallbackAudio expected)
    {
        using var dir = new TempDirectory();
        File.WriteAllText(ConfigPath(dir), "{\"decoder\":{\"kMinScorePass2\":10,\"coherentFallbackAudio\":\"" + name + "\"," + MarkersOnly + "}}");

        var store = new JsonConfigStore(ConfigPath(dir));
        Effective(store).Should().Be(expected);

        await store.SaveAsync(store.Current with { ShowCycleCountdown = !store.Current.ShowCycleCountdown });
        Effective(new JsonConfigStore(ConfigPath(dir))).Should().Be(expected, "an explicit value is written and read back, not lost to the default");
    }
}
