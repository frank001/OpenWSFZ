using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Config;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Config.Tests;

/// <summary>
/// COH-FALLBACK Stage 2 (R10): <c>decoder.coherentFallbackEnabled</c> defaults to <c>false</c>. HK-035: what an ABSENT key deserialises to is
/// checked through the real <see cref="JsonConfigStore"/> load and save path, and an explicit <c>true</c> must survive load, an unrelated
/// save and a reload. All values are synthetic.
/// </summary>
public sealed class CoherentFallbackFlagConfigTests
{
    private sealed class TempDirectory : IDisposable
    {
        public string Path { get; } = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "openwsfz-cohfb-" + System.IO.Path.GetRandomFileName());
        public TempDirectory() => Directory.CreateDirectory(Path);
        public void Dispose() { try { Directory.Delete(Path, recursive: true); } catch { /* best-effort */ } }
    }

    private static string ConfigPath(TempDirectory dir) => System.IO.Path.Combine(dir.Path, "config.json");

    private static bool Effective(JsonConfigStore store) => (store.Current.Decoder ?? new DecoderConfig()).CoherentFallbackEnabled;

    // Both markers true so no migration rewrites the decoder section: the file under test is read as written.
    private const string MarkersOnly = "\"nhard40MigrationApplied\":true,\"subtractionOnMigrationApplied\":true";

    [Fact(DisplayName = "R10: the code default is false, and an absent key reads false (constructor parameter, not a CLR zero by accident)")]
    public void CodeDefault_IsFalse()
    {
        new DecoderConfig().CoherentFallbackEnabled.Should().BeFalse();
        JsonSerializer.Deserialize("""{"decoder":{}}""", ConfigJsonContext.Default.AppConfig)!
            .Decoder!.CoherentFallbackEnabled.Should().BeFalse();
        using var doc = JsonDocument.Parse(JsonSerializer.Serialize(new DecoderConfig { CoherentFallbackEnabled = true }, ConfigJsonContext.Default.DecoderConfig));
        doc.RootElement.GetProperty("coherentFallbackEnabled").GetBoolean().Should().BeTrue("the wire name is camelCase");
    }

    [Fact(DisplayName = "R10: a stored decoder section without the key loads false; saved back it carries the key, false")]
    public async Task StoredWithoutTheKey_LoadsFalse_SavesFalse()
    {
        using var dir = new TempDirectory();
        File.WriteAllText(ConfigPath(dir), "{\"decoder\":{\"kMinScorePass2\":10," + MarkersOnly + "}}");

        var store = new JsonConfigStore(ConfigPath(dir));
        Effective(store).Should().BeFalse();

        await store.SaveAsync(store.Current with { ShowCycleCountdown = !store.Current.ShowCycleCountdown });
        using var written = JsonDocument.Parse(File.ReadAllText(ConfigPath(dir)));
        written.RootElement.GetProperty("decoder").GetProperty("coherentFallbackEnabled").GetBoolean().Should().BeFalse();
    }

    [Fact(DisplayName = "R10: an explicit true survives a load, an unrelated save and a reload")]
    public async Task ExplicitTrue_Survives()
    {
        using var dir = new TempDirectory();
        File.WriteAllText(ConfigPath(dir), "{\"decoder\":{\"kMinScorePass2\":10,\"coherentFallbackEnabled\":true," + MarkersOnly + "}}");

        var store = new JsonConfigStore(ConfigPath(dir));
        Effective(store).Should().BeTrue();

        await store.SaveAsync(store.Current with { ShowCycleCountdown = !store.Current.ShowCycleCountdown });
        Effective(new JsonConfigStore(ConfigPath(dir))).Should().BeTrue();
    }
}
