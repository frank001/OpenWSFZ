using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Config;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Config.Tests;

/// <summary>
/// DR-2 step 2a (FR-108): <c>decoder.engine</c> defaults to <c>classic</c> (an absent key, a missing decoder section and any unrecognised value read
/// classic); <c>lean</c> is read; the key round-trips and survives an unrelated save; <c>decoder.threads</c> defaults to 2 and is clamped to 1 to 8.
/// HK-035: what an ABSENT key deserialises to is checked through the real source-generated deserialisation and the real <see cref="JsonConfigStore"/>
/// path.
/// </summary>
public sealed class LeanEngineConfigTests
{
    private sealed class TempDirectory : IDisposable
    {
        public string Path { get; } = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "openwsfz-lean-" + System.IO.Path.GetRandomFileName());
        public TempDirectory() => Directory.CreateDirectory(Path);
        public void Dispose() { try { Directory.Delete(Path, recursive: true); } catch { /* best-effort */ } }
    }

    private static string ConfigPath(TempDirectory dir) => System.IO.Path.Combine(dir.Path, "config.json");

    private static DecoderConfig Decoder(JsonConfigStore store) => store.Current.Decoder ?? new DecoderConfig();

    // Both markers true so no migration rewrites the decoder section: the file under test is read as written.
    private const string MarkersOnly = "\"nhard40MigrationApplied\":true,\"subtractionOnMigrationApplied\":true";

    [Fact(DisplayName = "FR-108: DR-2 D4: the code default is classic and automatic threads (0), an absent key reads classic, 'lean' is read, the wire names are camelCase")]
    public void CodeDefault_IsClassic_AbsentKeyReadsClassic()
    {
        new DecoderConfig().Engine.Should().Be("classic");
        new DecoderConfig().GetEngineKind().Should().Be(DecoderEngine.Classic);
        new DecoderConfig().Threads.Should().Be(0);

        JsonSerializer.Deserialize("""{"decoder":{}}""", ConfigJsonContext.Default.AppConfig)!
            .Decoder!.GetEngineKind().Should().Be(DecoderEngine.Classic);
        JsonSerializer.Deserialize("""{}""", ConfigJsonContext.Default.AppConfig)!
            .Decoder.Should().BeNull("no decoder section: the daemon falls back to a new DecoderConfig, which is classic");
        JsonSerializer.Deserialize("""{"decoder":{"cqApEnabled":true}}""", ConfigJsonContext.Default.AppConfig)!
            .Decoder!.GetEngineKind().Should().Be(DecoderEngine.Classic, "a body for another key leaves this one at its default");
        JsonSerializer.Deserialize("""{"decoder":{"engine":"lean"}}""", ConfigJsonContext.Default.AppConfig)!
            .Decoder!.GetEngineKind().Should().Be(DecoderEngine.Lean);
        JsonSerializer.Deserialize("""{"decoder":{"engine":"classic"}}""", ConfigJsonContext.Default.AppConfig)!
            .Decoder!.GetEngineKind().Should().Be(DecoderEngine.Classic);
        JsonSerializer.Deserialize("""{"decoder":{"threads":4}}""", ConfigJsonContext.Default.AppConfig)!
            .Decoder!.Threads.Should().Be(4);

        using var doc = JsonDocument.Parse(JsonSerializer.Serialize(new DecoderConfig { Engine = "lean", Threads = 3 }, ConfigJsonContext.Default.DecoderConfig));
        doc.RootElement.GetProperty("engine").GetString().Should().Be("lean");
        doc.RootElement.GetProperty("threads").GetInt32().Should().Be(3);
        doc.RootElement.TryGetProperty("engineKind", out _).Should().BeFalse("the computed readers are not serialised");
        doc.RootElement.TryGetProperty("effectiveThreads", out _).Should().BeFalse();
    }

    [Theory(DisplayName = "FR-108: DR-2 D4: an unknown, empty or differently cased value reads as documented: only the word 'lean' is lean")]
    [InlineData("turbo", DecoderEngine.Classic)]
    [InlineData("", DecoderEngine.Classic)]
    [InlineData("LEAN", DecoderEngine.Lean)]
    [InlineData("lean ", DecoderEngine.Lean)]
    [InlineData("leanest", DecoderEngine.Classic)]
    public void UnknownValue_ReadsClassic(string value, DecoderEngine expected)
    {
        using var dir = new TempDirectory();
        File.WriteAllText(ConfigPath(dir), "{\"decoder\":{\"kMinScorePass2\":10,\"engine\":" + JsonSerializer.Serialize(value) + "," + MarkersOnly + "}}");

        Decoder(new JsonConfigStore(ConfigPath(dir))).GetEngineKind().Should().Be(expected);
    }

    [Fact(DisplayName = "FR-108: DR-2 D4: a stored decoder section without the key loads classic; saved back it carries the key as classic")]
    public async Task StoredWithoutTheKey_LoadsClassic_SavesClassic()
    {
        using var dir = new TempDirectory();
        File.WriteAllText(ConfigPath(dir), "{\"decoder\":{\"kMinScorePass2\":10," + MarkersOnly + "}}");

        var store = new JsonConfigStore(ConfigPath(dir));
        Decoder(store).GetEngineKind().Should().Be(DecoderEngine.Classic);

        await store.SaveAsync(store.Current with { ShowCycleCountdown = !store.Current.ShowCycleCountdown });
        using var written = JsonDocument.Parse(File.ReadAllText(ConfigPath(dir)));
        written.RootElement.GetProperty("decoder").GetProperty("engine").GetString().Should().Be("classic");
        written.RootElement.GetProperty("decoder").GetProperty("threads").GetInt32().Should().Be(0);
    }

    [Theory(DisplayName = "FR-108: DR-2 D4: an explicit engine value round-trips: it survives a load, an unrelated save and a reload, kept as written")]
    [InlineData("lean")]
    [InlineData("classic")]
    [InlineData("turbo")]
    public async Task ExplicitValue_Survives(string value)
    {
        using var dir = new TempDirectory();
        File.WriteAllText(ConfigPath(dir), "{\"decoder\":{\"kMinScorePass2\":10,\"engine\":\"" + value + "\",\"threads\":5," + MarkersOnly + "}}");

        var store = new JsonConfigStore(ConfigPath(dir));
        Decoder(store).Engine.Should().Be(value);

        await store.SaveAsync(store.Current with { ShowCycleCountdown = !store.Current.ShowCycleCountdown });
        var reloaded = Decoder(new JsonConfigStore(ConfigPath(dir)));
        reloaded.Engine.Should().Be(value, "an unrelated save does not rewrite the key (even an unknown word is kept as the operator wrote it)");
        reloaded.Threads.Should().Be(5);
    }

    [Fact(DisplayName = "FR-108: DR-2 2d D5: the code default of effort is normal, an absent key reads normal, 'fast' is read, a body for another key leaves it, the wire name is camelCase")]
    public void Effort_DefaultIsNormal_AbsentKeyReadsNormal()
    {
        new DecoderConfig().Effort.Should().Be("normal");
        new DecoderConfig().GetEffortKind().Should().Be(DecoderEffort.Normal);
        JsonSerializer.Deserialize("""{"decoder":{}}""", ConfigJsonContext.Default.AppConfig)!.Decoder!.GetEffortKind().Should().Be(DecoderEffort.Normal);
        JsonSerializer.Deserialize("""{"decoder":{"engine":"lean"}}""", ConfigJsonContext.Default.AppConfig)!.Decoder!.GetEffortKind().Should().Be(DecoderEffort.Normal, "a body for another key leaves it at its default");
        JsonSerializer.Deserialize("""{"decoder":{"effort":"fast"}}""", ConfigJsonContext.Default.AppConfig)!.Decoder!.GetEffortKind().Should().Be(DecoderEffort.Fast);
        JsonSerializer.Deserialize("""{"decoder":{"effort":"warp"}}""", ConfigJsonContext.Default.AppConfig)!.Decoder!.GetEffortKind().Should().Be(DecoderEffort.Normal, "an unknown value reads normal");

        using var doc = JsonDocument.Parse(JsonSerializer.Serialize(new DecoderConfig { Effort = "fast" }, ConfigJsonContext.Default.DecoderConfig));
        doc.RootElement.GetProperty("effort").GetString().Should().Be("fast");
        doc.RootElement.TryGetProperty("effortKind", out _).Should().BeFalse("the computed reader is not serialised");
    }

    [Theory(DisplayName = "FR-108: DR-2 2d D5: an explicit effort value round-trips kept as written (an unknown word too), and a decoder section without the key saves back as normal")]
    [InlineData("fast")]
    [InlineData("normal")]
    [InlineData("warp")]
    public async Task Effort_ExplicitValue_Survives(string value)
    {
        using var dir = new TempDirectory();
        File.WriteAllText(ConfigPath(dir), "{\"decoder\":{\"kMinScorePass2\":10,\"effort\":\"" + value + "\"," + MarkersOnly + "}}");
        var store = new JsonConfigStore(ConfigPath(dir));
        Decoder(store).Effort.Should().Be(value);
        await store.SaveAsync(store.Current with { ShowCycleCountdown = !store.Current.ShowCycleCountdown });
        Decoder(new JsonConfigStore(ConfigPath(dir))).Effort.Should().Be(value, "an unrelated save does not rewrite the key");

        using var dir2 = new TempDirectory();
        File.WriteAllText(ConfigPath(dir2), "{\"decoder\":{\"kMinScorePass2\":10," + MarkersOnly + "}}");
        var store2 = new JsonConfigStore(ConfigPath(dir2));
        await store2.SaveAsync(store2.Current with { ShowCycleCountdown = !store2.Current.ShowCycleCountdown });
        using var written = JsonDocument.Parse(File.ReadAllText(ConfigPath(dir2)));
        written.RootElement.GetProperty("decoder").GetProperty("effort").GetString().Should().Be("normal");
    }

    [Fact(DisplayName = "FR-108: threads default auto: DefaultThreads is 0, an absent key reads as auto, a hand-edited value is respected or clamped (never turned into auto)")]
    public void Threads_DefaultIsAuto_AndClamp()
    {
        DecoderConfig.DefaultThreads.Should().Be(0);
        DecoderConfig.AutoThreads.Should().Be(0);
        JsonSerializer.Deserialize("""{"decoder":{}}""", ConfigJsonContext.Default.AppConfig)!.Decoder!.Threads.Should().Be(0);
        new DecoderConfig().Threads.Should().Be(0);
        new DecoderConfig { Threads = 6 }.ResolveThreads(64).Should().Be(6);
        new DecoderConfig { Threads = 1 }.ResolveThreads(64).Should().Be(1);
        new DecoderConfig { Threads = 16 }.ResolveThreads(64).Should().Be(16);
        new DecoderConfig { Threads = 20 }.ResolveThreads(64).Should().Be(16);
        new DecoderConfig { Threads = -5 }.ResolveThreads(64).Should().Be(1);
        new DecoderConfig { Threads = 20 }.ClampedThreads.Should().Be(16);
        new DecoderConfig { Threads = -5 }.ClampedThreads.Should().Be(1);
        new DecoderConfig { Threads = 0 }.ClampedThreads.Should().Be(0);
    }

    [Theory(DisplayName = "FR-108: threads default auto: ResolveThreads(0, processors) is min(processors, 16), at least 1")]
    [InlineData(1, 1)]
    [InlineData(2, 2)]
    [InlineData(4, 4)]
    [InlineData(8, 8)]
    [InlineData(16, 16)]
    [InlineData(17, 16)]
    [InlineData(64, 16)]
    [InlineData(0, 1)]
    public void ResolveThreads_Auto_IsMinOfProcessorsAndSixteen(int processors, int expected)
    {
        new DecoderConfig { Threads = 0 }.ResolveThreads(processors).Should().Be(expected);
        DecoderConfig.ResolveThreads(DecoderConfig.AutoThreads, processors).Should().Be(expected);
    }
}
