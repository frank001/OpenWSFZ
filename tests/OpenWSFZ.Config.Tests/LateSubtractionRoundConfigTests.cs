using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Config;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Config.Tests;

/// <summary>
/// LATE-SUB L1': <c>decoder.lateSubtractionRound</c> defaults to <c>false</c> (an absent key, and a missing decoder section, read false);
/// an explicit value survives a load, an unrelated save and a reload. HK-035: what an ABSENT key deserialises to is checked through the real
/// source-generated deserialisation and the real <see cref="JsonConfigStore"/> path.
/// </summary>
public sealed class LateSubtractionRoundConfigTests
{
    private sealed class TempDirectory : IDisposable
    {
        public string Path { get; } = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "openwsfz-latesub-" + System.IO.Path.GetRandomFileName());
        public TempDirectory() => Directory.CreateDirectory(Path);
        public void Dispose() { try { Directory.Delete(Path, recursive: true); } catch { /* best-effort */ } }
    }

    private static string ConfigPath(TempDirectory dir) => System.IO.Path.Combine(dir.Path, "config.json");

    private static bool Effective(JsonConfigStore store) => (store.Current.Decoder ?? new DecoderConfig()).LateSubtractionRound;

    // Both markers true so no migration rewrites the decoder section: the file under test is read as written.
    private const string MarkersOnly = "\"nhard40MigrationApplied\":true,\"subtractionOnMigrationApplied\":true";

    [Fact(DisplayName = "FR-102: LATE-SUB L1': the code default is false, an absent key reads false, explicit values are read, the wire name is camelCase")]
    public void CodeDefault_IsFalse_AbsentKeyReadsFalse()
    {
        new DecoderConfig().LateSubtractionRound.Should().BeFalse();
        JsonSerializer.Deserialize("""{"decoder":{}}""", ConfigJsonContext.Default.AppConfig)!
            .Decoder!.LateSubtractionRound.Should().BeFalse();
        JsonSerializer.Deserialize("""{"decoder":{"coherentFallbackAudio":"Both"}}""", ConfigJsonContext.Default.AppConfig)!
            .Decoder!.LateSubtractionRound.Should().BeFalse("a body for another key leaves this one at its default");
        JsonSerializer.Deserialize("""{"decoder":{"lateSubtractionRound":true}}""", ConfigJsonContext.Default.AppConfig)!
            .Decoder!.LateSubtractionRound.Should().BeTrue();
        JsonSerializer.Deserialize("""{"decoder":{"lateSubtractionRound":false}}""", ConfigJsonContext.Default.AppConfig)!
            .Decoder!.LateSubtractionRound.Should().BeFalse();

        using var doc = JsonDocument.Parse(JsonSerializer.Serialize(new DecoderConfig { LateSubtractionRound = true }, ConfigJsonContext.Default.DecoderConfig));
        doc.RootElement.GetProperty("lateSubtractionRound").GetBoolean().Should().BeTrue();
    }

    [Fact(DisplayName = "FR-102: LATE-SUB L1': a stored decoder section without the key loads false; saved back it carries the key as false")]
    public async Task StoredWithoutTheKey_LoadsFalse_SavesFalse()
    {
        using var dir = new TempDirectory();
        File.WriteAllText(ConfigPath(dir), "{\"decoder\":{\"kMinScorePass2\":10," + MarkersOnly + "}}");

        var store = new JsonConfigStore(ConfigPath(dir));
        Effective(store).Should().BeFalse();

        await store.SaveAsync(store.Current with { ShowCycleCountdown = !store.Current.ShowCycleCountdown });
        using var written = JsonDocument.Parse(File.ReadAllText(ConfigPath(dir)));
        written.RootElement.GetProperty("decoder").GetProperty("lateSubtractionRound").GetBoolean().Should().BeFalse();
    }

    [Fact(DisplayName = "FR-102: LATE-SUB L1': a config file with no decoder section at all reads false")]
    public void NoDecoderSection_ReadsFalse()
    {
        using var dir = new TempDirectory();
        File.WriteAllText(ConfigPath(dir), "{\"showCycleCountdown\":true," + MarkersOnly + "}");
        Effective(new JsonConfigStore(ConfigPath(dir))).Should().BeFalse();
    }

    [Theory(DisplayName = "FR-102: LATE-SUB L1': an explicit value survives a load, an unrelated save and a reload")]
    [InlineData(true)]
    [InlineData(false)]
    public async Task ExplicitValue_Survives(bool expected)
    {
        using var dir = new TempDirectory();
        File.WriteAllText(ConfigPath(dir), "{\"decoder\":{\"kMinScorePass2\":10,\"lateSubtractionRound\":" + (expected ? "true" : "false") + "," + MarkersOnly + "}}");

        var store = new JsonConfigStore(ConfigPath(dir));
        Effective(store).Should().Be(expected);

        await store.SaveAsync(store.Current with { ShowCycleCountdown = !store.Current.ShowCycleCountdown });
        Effective(new JsonConfigStore(ConfigPath(dir))).Should().Be(expected, "an explicit value is written and read back, not lost to the default");
    }
}
