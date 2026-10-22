using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Config;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Config.Tests;

/// <summary>
/// third-pass-deep (#240), the default flip of 2026-10-19 (the Captain: "default option ON"): <c>decoder.decodingDepth</c> defaults
/// to <c>Deep</c>. HK-035: what an ABSENT key deserialises to is checked through the real <see cref="JsonConfigStore"/> load and save
/// path. An explicit <c>"Normal"</c> must survive load, an unrelated save and a reload. All values are synthetic.
/// </summary>
public sealed class DecodingDepthDefaultTests
{
    private sealed class TempDirectory : IDisposable
    {
        public string Path { get; } = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "openwsfz-depth-" + System.IO.Path.GetRandomFileName());
        public TempDirectory() => Directory.CreateDirectory(Path);
        public void Dispose() { try { Directory.Delete(Path, recursive: true); } catch { /* best-effort */ } }
    }

    private static string ConfigPath(TempDirectory dir) => System.IO.Path.Combine(dir.Path, "config.json");

    private static DecodingDepth Effective(JsonConfigStore store) => (store.Current.Decoder ?? new DecoderConfig()).DecodingDepth;

    // Both markers true so no migration rewrites the decoder section: the file under test is read as written.
    private const string MarkersOnly = "\"nhard40MigrationApplied\":true,\"subtractionOnMigrationApplied\":true";

    [Fact(DisplayName = "#240: the DecoderConfig code default is Deep, and an absent key in a bare JSON document reads Deep")]
    public void CodeDefault_IsDeep()
    {
        new DecoderConfig().DecodingDepth.Should().Be(DecodingDepth.Deep);
        JsonSerializer.Deserialize("""{"decoder":{}}""", ConfigJsonContext.Default.AppConfig)!
            .Decoder!.DecodingDepth.Should().Be(DecodingDepth.Deep, "an absent key resolves to the default (constructor parameter, not zeroed)");
    }

    [Fact(DisplayName = "#240 4a: a stored config whose decoder object has NO decodingDepth key loads as Deep (real store load path)")]
    public void StoredDecoderWithoutTheKey_LoadsDeep()
    {
        using var dir = new TempDirectory();
        File.WriteAllText(ConfigPath(dir), "{\"decoder\":{\"kMinScorePass2\":10,\"osdCorrThreshold\":0.1,\"osdNhardMax\":24," + MarkersOnly + "}}");

        var store = new JsonConfigStore(ConfigPath(dir));

        Effective(store).Should().Be(DecodingDepth.Deep);
    }

    [Fact(DisplayName = "#240 4b: a key-absent file, loaded and saved back, still reads Deep and now carries decodingDepth Deep")]
    public async Task KeyAbsent_SavedBack_WritesDeep()
    {
        using var dir = new TempDirectory();
        File.WriteAllText(ConfigPath(dir), "{\"decoder\":{\"kMinScorePass2\":10," + MarkersOnly + "}}");

        var store = new JsonConfigStore(ConfigPath(dir));
        await store.SaveAsync(store.Current with { ShowCycleCountdown = !store.Current.ShowCycleCountdown });

        using var written = JsonDocument.Parse(File.ReadAllText(ConfigPath(dir)));
        written.RootElement.GetProperty("decoder").GetProperty("decodingDepth").GetString().Should().Be("Deep");
        Effective(new JsonConfigStore(ConfigPath(dir))).Should().Be(DecodingDepth.Deep);
    }

    [Fact(DisplayName = "#240 4c: a stored explicit Normal loads Normal and stays Normal across 2 reloads and a save that does not touch it")]
    public async Task StoredExplicitNormal_StaysNormal()
    {
        using var dir = new TempDirectory();
        File.WriteAllText(ConfigPath(dir), "{\"decoder\":{\"decodingDepth\":\"Normal\"," + MarkersOnly + "}}");

        Effective(new JsonConfigStore(ConfigPath(dir))).Should().Be(DecodingDepth.Normal);
        Effective(new JsonConfigStore(ConfigPath(dir))).Should().Be(DecodingDepth.Normal);

        var store = new JsonConfigStore(ConfigPath(dir));
        await store.SaveAsync(store.Current with { ShowCycleCountdown = !store.Current.ShowCycleCountdown });
        Effective(new JsonConfigStore(ConfigPath(dir))).Should().Be(DecodingDepth.Normal, "an unrelated save cannot turn the opt-out back on");
    }

    [Fact(DisplayName = "#240: no decoder section at all, and a fresh install, read Deep")]
    public void NoDecoderSection_And_FreshInstall_ReadDeep()
    {
        using var dir = new TempDirectory();
        File.WriteAllText(ConfigPath(dir), """{"port":8080}""");
        Effective(new JsonConfigStore(ConfigPath(dir))).Should().Be(DecodingDepth.Deep);

        using var fresh = new TempDirectory();
        Effective(new JsonConfigStore(ConfigPath(fresh))).Should().Be(DecodingDepth.Deep);
    }
}
