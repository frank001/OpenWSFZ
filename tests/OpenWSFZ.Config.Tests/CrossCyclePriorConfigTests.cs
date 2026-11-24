using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Config;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Config.Tests;

/// <summary>
/// XC-BUILD (FR-105): <c>decoder.crossCyclePrior</c> and <c>decoder.crossCyclePriorShadow</c> default to <c>false</c> (an absent key, and a missing decoder section, read false); an explicit value survives a
/// load, an unrelated save and a reload. HK-035: what an ABSENT key deserialises to is checked through the real source-generated deserialisation and the real <see cref="JsonConfigStore"/> path.
/// </summary>
public sealed class CrossCyclePriorConfigTests
{
    private sealed class TempDirectory : IDisposable
    {
        public string Path { get; } = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "openwsfz-xcprior-" + System.IO.Path.GetRandomFileName());
        public TempDirectory() => Directory.CreateDirectory(Path);
        public void Dispose() { try { Directory.Delete(Path, recursive: true); } catch { /* best-effort */ } }
    }

    private static string ConfigPath(TempDirectory dir) => System.IO.Path.Combine(dir.Path, "config.json");

    // Both markers true so no migration rewrites the decoder section: the file under test is read as written.
    private const string MarkersOnly = "\"nhard40MigrationApplied\":true,\"subtractionOnMigrationApplied\":true";

    [Fact(DisplayName = "FR-105: XC-BUILD: the code default is false for both keys, an absent key reads false, explicit values are read, the wire names are camelCase")]
    public void CodeDefault_IsFalse_AbsentKeyReadsFalse()
    {
        new DecoderConfig().CrossCyclePrior.Should().BeFalse();
        new DecoderConfig().CrossCyclePriorShadow.Should().BeFalse();
        var absent = JsonSerializer.Deserialize("""{"decoder":{}}""", ConfigJsonContext.Default.AppConfig)!.Decoder!;
        absent.CrossCyclePrior.Should().BeFalse();
        absent.CrossCyclePriorShadow.Should().BeFalse();
        var other = JsonSerializer.Deserialize("""{"decoder":{"cqApEnabled":true}}""", ConfigJsonContext.Default.AppConfig)!.Decoder!;
        other.CrossCyclePrior.Should().BeFalse("a body for another key leaves these at their default");
        var on = JsonSerializer.Deserialize("""{"decoder":{"crossCyclePrior":true,"crossCyclePriorShadow":true}}""", ConfigJsonContext.Default.AppConfig)!.Decoder!;
        on.CrossCyclePrior.Should().BeTrue();
        on.CrossCyclePriorShadow.Should().BeTrue();
        var mixed = JsonSerializer.Deserialize("""{"decoder":{"crossCyclePrior":true,"crossCyclePriorShadow":false}}""", ConfigJsonContext.Default.AppConfig)!.Decoder!;
        mixed.CrossCyclePrior.Should().BeTrue();
        mixed.CrossCyclePriorShadow.Should().BeFalse();

        using var doc = JsonDocument.Parse(JsonSerializer.Serialize(new DecoderConfig { CrossCyclePrior = true, CrossCyclePriorShadow = true }, ConfigJsonContext.Default.DecoderConfig));
        doc.RootElement.GetProperty("crossCyclePrior").GetBoolean().Should().BeTrue();
        doc.RootElement.GetProperty("crossCyclePriorShadow").GetBoolean().Should().BeTrue();
    }

    [Fact(DisplayName = "FR-105: XC-BUILD: a stored decoder section without the keys loads false; saved back it carries both as false; explicit true values survive an unrelated save")]
    public async Task StoredWithoutTheKeys_LoadFalse_ExplicitTrueSurvives()
    {
        using var absent = new TempDirectory();
        File.WriteAllText(ConfigPath(absent), "{\"decoder\":{\"kMinScorePass2\":10," + MarkersOnly + "}}");
        var store = new JsonConfigStore(ConfigPath(absent));
        (store.Current.Decoder ?? new DecoderConfig()).CrossCyclePrior.Should().BeFalse();
        (store.Current.Decoder ?? new DecoderConfig()).CrossCyclePriorShadow.Should().BeFalse();
        await store.SaveAsync(store.Current with { ShowCycleCountdown = !store.Current.ShowCycleCountdown });
        using (var written = JsonDocument.Parse(File.ReadAllText(ConfigPath(absent))))
        {
            written.RootElement.GetProperty("decoder").GetProperty("crossCyclePrior").GetBoolean().Should().BeFalse();
            written.RootElement.GetProperty("decoder").GetProperty("crossCyclePriorShadow").GetBoolean().Should().BeFalse();
        }

        using var explicitOn = new TempDirectory();
        File.WriteAllText(ConfigPath(explicitOn), "{\"decoder\":{\"kMinScorePass2\":10,\"crossCyclePrior\":true,\"crossCyclePriorShadow\":true," + MarkersOnly + "}}");
        var store2 = new JsonConfigStore(ConfigPath(explicitOn));
        store2.Current.Decoder!.CrossCyclePrior.Should().BeTrue();
        store2.Current.Decoder!.CrossCyclePriorShadow.Should().BeTrue();
        await store2.SaveAsync(store2.Current with { ShowCycleCountdown = !store2.Current.ShowCycleCountdown });
        var reloaded = new JsonConfigStore(ConfigPath(explicitOn)).Current.Decoder!;
        reloaded.CrossCyclePrior.Should().BeTrue("an unrelated save keeps the explicit value");
        reloaded.CrossCyclePriorShadow.Should().BeTrue();
    }
}
