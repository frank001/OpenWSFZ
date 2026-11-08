using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Config;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Config.Tests;

/// <summary>
/// COH-RES-CAND (FR-103): <c>decoder.coherentFallbackResidualCandidates</c> defaults to <c>false</c> (an absent key, and a missing decoder section, read
/// false); an explicit value survives a load, an unrelated save and a reload. HK-035: what an ABSENT key deserialises to is checked through the real
/// source-generated deserialisation and the real <see cref="JsonConfigStore"/> path.
/// </summary>
public sealed class CoherentFallbackResidualCandidatesConfigTests
{
    private sealed class TempDirectory : IDisposable
    {
        public string Path { get; } = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "openwsfz-cohrescand-" + System.IO.Path.GetRandomFileName());
        public TempDirectory() => Directory.CreateDirectory(Path);
        public void Dispose() { try { Directory.Delete(Path, recursive: true); } catch { /* best-effort */ } }
    }

    private static string ConfigPath(TempDirectory dir) => System.IO.Path.Combine(dir.Path, "config.json");

    private static bool Effective(JsonConfigStore store) => (store.Current.Decoder ?? new DecoderConfig()).CoherentFallbackResidualCandidates;

    // Both markers true so no migration rewrites the decoder section: the file under test is read as written.
    private const string MarkersOnly = "\"nhard40MigrationApplied\":true,\"subtractionOnMigrationApplied\":true";

    [Fact(DisplayName = "FR-103: COH-RES-CAND: the code default is false, an absent key reads false, explicit values are read, the wire name is camelCase")]
    public void CodeDefault_IsFalse_AbsentKeyReadsFalse()
    {
        new DecoderConfig().CoherentFallbackResidualCandidates.Should().BeFalse();
        JsonSerializer.Deserialize("""{"decoder":{}}""", ConfigJsonContext.Default.AppConfig)!
            .Decoder!.CoherentFallbackResidualCandidates.Should().BeFalse();
        JsonSerializer.Deserialize("""{"decoder":{"coherentFallbackResidualUngated":true}}""", ConfigJsonContext.Default.AppConfig)!
            .Decoder!.CoherentFallbackResidualCandidates.Should().BeFalse("a body for another key leaves this one at its default");
        JsonSerializer.Deserialize("""{"decoder":{"coherentFallbackResidualCandidates":true}}""", ConfigJsonContext.Default.AppConfig)!
            .Decoder!.CoherentFallbackResidualCandidates.Should().BeTrue();
        JsonSerializer.Deserialize("""{"decoder":{"coherentFallbackResidualCandidates":false}}""", ConfigJsonContext.Default.AppConfig)!
            .Decoder!.CoherentFallbackResidualCandidates.Should().BeFalse();

        using var doc = JsonDocument.Parse(JsonSerializer.Serialize(new DecoderConfig { CoherentFallbackResidualCandidates = true }, ConfigJsonContext.Default.DecoderConfig));
        doc.RootElement.GetProperty("coherentFallbackResidualCandidates").GetBoolean().Should().BeTrue();
    }

    [Fact(DisplayName = "FR-103: COH-RES-CAND: a stored decoder section without the key loads false; saved back it carries the key as false; an explicit true survives an unrelated save")]
    public async Task StoredWithoutTheKey_LoadsFalse_ExplicitTrueSurvives()
    {
        using var absent = new TempDirectory();
        File.WriteAllText(ConfigPath(absent), "{\"decoder\":{\"kMinScorePass2\":10," + MarkersOnly + "}}");
        var store = new JsonConfigStore(ConfigPath(absent));
        Effective(store).Should().BeFalse();
        await store.SaveAsync(store.Current with { ShowCycleCountdown = !store.Current.ShowCycleCountdown });
        using (var written = JsonDocument.Parse(File.ReadAllText(ConfigPath(absent))))
            written.RootElement.GetProperty("decoder").GetProperty("coherentFallbackResidualCandidates").GetBoolean().Should().BeFalse();

        using var explicitOn = new TempDirectory();
        File.WriteAllText(ConfigPath(explicitOn), "{\"decoder\":{\"kMinScorePass2\":10,\"coherentFallbackResidualCandidates\":true," + MarkersOnly + "}}");
        var store2 = new JsonConfigStore(ConfigPath(explicitOn));
        Effective(store2).Should().BeTrue();
        await store2.SaveAsync(store2.Current with { ShowCycleCountdown = !store2.Current.ShowCycleCountdown });
        Effective(new JsonConfigStore(ConfigPath(explicitOn))).Should().BeTrue("an unrelated save keeps the explicit value");
    }
}
