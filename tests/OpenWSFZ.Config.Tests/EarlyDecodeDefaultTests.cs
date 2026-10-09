using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Config;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Config.Tests;

/// <summary>
/// decode-early-batch-panel (FR-083), the default flip of 2026-10-04 (the Captain: "default on"): <c>decoder.earlyDecodeEnabled</c>
/// defaults to <c>true</c>. HK-035: what an ABSENT key deserialises to is checked through the real <see cref="JsonConfigStore"/>
/// load path, not only on the record. <see cref="DecoderConfig"/> has an all-optional <c>[JsonConstructor]</c>; the early fields are
/// init properties outside it, so an omitted key must keep the property initialiser (<c>true</c>), and an explicit
/// <c>false</c> must stay <c>false</c> across restarts. All values are synthetic.
/// </summary>
public sealed class EarlyDecodeDefaultTests
{
    private sealed class TempDirectory : IDisposable
    {
        public string Path { get; } = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "openwsfz-early-" + System.IO.Path.GetRandomFileName());
        public TempDirectory() => Directory.CreateDirectory(Path);
        public void Dispose() { try { Directory.Delete(Path, recursive: true); } catch { /* best-effort */ } }
    }

    private static string ConfigPath(TempDirectory dir) => System.IO.Path.Combine(dir.Path, "config.json");

    /// <summary>The value the framer's provider in <c>Program.cs</c> reads: <c>Current.Decoder ?? new DecoderConfig()</c>.</summary>
    private static bool Effective(JsonConfigStore store) => (store.Current.Decoder ?? new DecoderConfig()).EarlyDecodeEnabled;

    // Both markers true so no migration rewrites the decoder section: the file under test is read as written.
    private const string MarkersOnly = "\"nhard40MigrationApplied\":true,\"subtractionOnMigrationApplied\":true";

    [Fact(DisplayName = "FR-083: the DecoderConfig code default is earlyDecodeEnabled true, and an absent key in a bare JSON document reads true")]
    public void CodeDefault_IsTrue()
    {
        new DecoderConfig().EarlyDecodeEnabled.Should().BeTrue();
        JsonSerializer.Deserialize("""{"decoder":{}}""", ConfigJsonContext.Default.AppConfig)!
            .Decoder!.EarlyDecodeEnabled.Should().BeTrue("an absent key resolves to the new default (property initialiser, not zeroed by the constructor)");
    }

    [Fact(DisplayName = "FR-083: a stored config whose decoder object has NO earlyDecodeEnabled key loads as true (real store load path)")]
    public void StoredDecoderWithoutTheKey_LoadsTrue()
    {
        using var dir = new TempDirectory();
        File.WriteAllText(ConfigPath(dir), "{\"decoder\":{\"kMinScorePass2\":10,\"osdCorrThreshold\":0.1,\"osdNhardMax\":40," + MarkersOnly + "}}");

        var store = new JsonConfigStore(ConfigPath(dir));

        store.Current.Decoder.Should().NotBeNull();
        store.Current.Decoder!.EarlyDecodeEnabled.Should().BeTrue();
        store.Current.Decoder.EarlyDecodeCutSeconds.Should().Be(2.0, "the cut's default is likewise unchanged by an absent key");
        Effective(store).Should().BeTrue();
    }

    [Fact(DisplayName = "FR-083: a stored explicit earlyDecodeEnabled false loads as false, and stays false across 2 reloads and a save that does not touch it")]
    public async Task StoredExplicitFalse_StaysFalse()
    {
        using var dir = new TempDirectory();
        File.WriteAllText(ConfigPath(dir), "{\"decoder\":{\"earlyDecodeEnabled\":false," + MarkersOnly + "}}");

        Effective(new JsonConfigStore(ConfigPath(dir))).Should().BeFalse();
        Effective(new JsonConfigStore(ConfigPath(dir))).Should().BeFalse();

        var store = new JsonConfigStore(ConfigPath(dir));
        await store.SaveAsync(store.Current with { ShowCycleCountdown = !store.Current.ShowCycleCountdown });   // an unrelated save
        Effective(new JsonConfigStore(ConfigPath(dir))).Should().BeFalse("a save that does not name the field cannot turn it back on");
    }

    [Fact(DisplayName = "FR-083: a stored config with NO decoder section at all reads true through the framer provider's expression")]
    public void NoDecoderSection_ReadsTrue()
    {
        using var dir = new TempDirectory();
        File.WriteAllText(ConfigPath(dir), """{"port":8080}""");

        var store = new JsonConfigStore(ConfigPath(dir));

        // The store may create a decoder section on load (a fresh install does) or leave it null (an older file); either way it is ON.
        Effective(store).Should().BeTrue();
    }

    [Fact(DisplayName = "FR-083: no config file at all (a fresh install) is ON, and the file written has no explicit false")]
    public void FreshInstall_IsOn()
    {
        using var dir = new TempDirectory();

        var store = new JsonConfigStore(ConfigPath(dir));

        Effective(store).Should().BeTrue();
        File.ReadAllText(ConfigPath(dir)).Should().NotContain("\"earlyDecodeEnabled\":false");
    }
}
