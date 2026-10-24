using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Config;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Config.Tests;

/// <summary>
/// COH-MULTISET: <c>decoder.coherentFallbackMultiSet</c> defaults to <c>false</c> (an absent key reads false; an explicit true survives load,
/// an unrelated save and a reload). HK-035: what an ABSENT key deserialises to is checked through the real source-generated deserialisation and
/// the real <see cref="JsonConfigStore"/> path. All values are synthetic.
/// </summary>
public sealed class CoherentFallbackMultiSetConfigTests
{
    private sealed class TempDirectory : IDisposable
    {
        public string Path { get; } = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "openwsfz-cohms-" + System.IO.Path.GetRandomFileName());
        public TempDirectory() => Directory.CreateDirectory(Path);
        public void Dispose() { try { Directory.Delete(Path, recursive: true); } catch { /* best-effort */ } }
    }

    private static string ConfigPath(TempDirectory dir) => System.IO.Path.Combine(dir.Path, "config.json");

    private static bool Effective(JsonConfigStore store) => (store.Current.Decoder ?? new DecoderConfig()).CoherentFallbackMultiSet;

    // Both markers true so no migration rewrites the decoder section: the file under test is read as written.
    private const string MarkersOnly = "\"nhard40MigrationApplied\":true,\"subtractionOnMigrationApplied\":true";

    [Fact(DisplayName = "COH-MULTISET: the code default is false, an absent key reads false (also with the fallback flag present), an explicit true is read, the wire name is camelCase")]
    public void CodeDefault_IsFalse_AbsentKeyReadsFalse_ExplicitTrueIsRead()
    {
        new DecoderConfig().CoherentFallbackMultiSet.Should().BeFalse();
        JsonSerializer.Deserialize("""{"decoder":{}}""", ConfigJsonContext.Default.AppConfig)!
            .Decoder!.CoherentFallbackMultiSet.Should().BeFalse("an absent key reads false");
        JsonSerializer.Deserialize("""{"decoder":{"coherentFallbackEnabled":true}}""", ConfigJsonContext.Default.AppConfig)!
            .Decoder!.CoherentFallbackMultiSet.Should().BeFalse("turning the fallback on does not turn the sets on");
        JsonSerializer.Deserialize("""{"decoder":{"coherentFallbackMultiSet":true}}""", ConfigJsonContext.Default.AppConfig)!
            .Decoder!.CoherentFallbackMultiSet.Should().BeTrue();
        using var doc = JsonDocument.Parse(JsonSerializer.Serialize(new DecoderConfig { CoherentFallbackMultiSet = true }, ConfigJsonContext.Default.DecoderConfig));
        doc.RootElement.GetProperty("coherentFallbackMultiSet").GetBoolean().Should().BeTrue();
    }

    [Fact(DisplayName = "COH-MULTISET: a stored decoder section without the key loads false; saved back it carries the key, false")]
    public async Task StoredWithoutTheKey_LoadsFalse_SavesFalse()
    {
        using var dir = new TempDirectory();
        File.WriteAllText(ConfigPath(dir), "{\"decoder\":{\"kMinScorePass2\":10," + MarkersOnly + "}}");

        var store = new JsonConfigStore(ConfigPath(dir));
        Effective(store).Should().BeFalse();

        await store.SaveAsync(store.Current with { ShowCycleCountdown = !store.Current.ShowCycleCountdown });
        using var written = JsonDocument.Parse(File.ReadAllText(ConfigPath(dir)));
        written.RootElement.GetProperty("decoder").GetProperty("coherentFallbackMultiSet").GetBoolean().Should().BeFalse();
    }

    [Fact(DisplayName = "COH-MULTISET: a config file with no decoder section at all reads false")]
    public void NoDecoderSection_ReadsFalse()
    {
        using var dir = new TempDirectory();
        File.WriteAllText(ConfigPath(dir), "{\"showCycleCountdown\":true," + MarkersOnly + "}");
        Effective(new JsonConfigStore(ConfigPath(dir))).Should().BeFalse();
    }

    [Fact(DisplayName = "COH-MULTISET: an explicit true survives a load, an unrelated save and a reload")]
    public async Task ExplicitTrue_Survives()
    {
        using var dir = new TempDirectory();
        File.WriteAllText(ConfigPath(dir), "{\"decoder\":{\"kMinScorePass2\":10,\"coherentFallbackMultiSet\":true," + MarkersOnly + "}}");

        var store = new JsonConfigStore(ConfigPath(dir));
        Effective(store).Should().BeTrue();

        await store.SaveAsync(store.Current with { ShowCycleCountdown = !store.Current.ShowCycleCountdown });
        Effective(new JsonConfigStore(ConfigPath(dir))).Should().BeTrue("an explicit true is written and read back, not lost to the default");
    }
}
