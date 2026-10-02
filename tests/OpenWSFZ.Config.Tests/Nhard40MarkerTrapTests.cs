using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Config;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Config.Tests;

/// <summary>
/// QA's test of the "nhard40 marker trap" the Architect read in <c>JsonConfigStore.Load</c> (JsonConfigStore.cs, the M2 migration):
/// the marker <c>decoder.nhard40MigrationApplied</c> is set to <c>true</c> ONLY when the 60 -> 40 migration actually fires, so on a
/// config that never held a 60 it stays <c>false</c> for ever. If an operator then sets <c>osdNhardMax</c> to 60 on purpose and the daemon
/// restarts, the migration (which matches <c>OsdNhardMax: 60, Nhard40MigrationApplied: false</c>) rewrites the operator's choice to 40.
/// These tests assert the CORRECT behaviour (an explicit 60 survives a save and a reload); a failure is the trap.
/// All values are synthetic.
/// </summary>
public sealed class Nhard40MarkerTrapTests
{
    private sealed class TempDirectory : IDisposable
    {
        public string Path { get; } = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "openwsfz-marker-" + System.IO.Path.GetRandomFileName());
        public TempDirectory() => Directory.CreateDirectory(Path);
        public void Dispose() { try { Directory.Delete(Path, recursive: true); } catch { /* best-effort */ } }
    }

    private static AppConfig WithNhard(AppConfig c, int nhard)
        => c with { Decoder = (c.Decoder ?? new DecoderConfig()) with { OsdNhardMax = nhard } };

    [Fact(DisplayName = "TRAP: fresh install, operator explicitly sets osdNhardMax 60 via a save: it must survive a restart (reload)")]
    public async Task FreshInstall_ExplicitSixty_SurvivesReload()
    {
        using var dir = new TempDirectory();
        var path = System.IO.Path.Combine(dir.Path, "config.json");

        var first = new JsonConfigStore(path);                       // fresh install: defaults written, marker never set
        await first.SaveAsync(WithNhard(first.Current, 60));         // the operator deliberately chooses 60 (Settings save)
        first.Current.Decoder!.OsdNhardMax.Should().Be(60, "the save itself keeps what the operator chose");
        first.Current.Decoder.Nhard40MigrationApplied.Should().BeTrue("no migration is pending on a fresh install (#199), so Load sets the marker");

        var afterRestart = new JsonConfigStore(path);                // daemon restarts: Load() runs the M2 migration check

        afterRestart.Current.Decoder!.OsdNhardMax.Should().Be(60,
            "an explicit 60 chosen AFTER the migration era must not be migrated back to 40 on reload");
    }

    [Fact(DisplayName = "TRAP: a config that was already at the default 40 (never held a 60): an explicit 60 must survive a reload")]
    public async Task ConfigAtDefault40_ExplicitSixty_SurvivesReload()
    {
        using var dir = new TempDirectory();
        var path = System.IO.Path.Combine(dir.Path, "config.json");
        var seed = new AppConfig { Decoder = new DecoderConfig() };  // osdNhardMax at the code default (40), marker false
        File.WriteAllText(path, JsonSerializer.Serialize(seed, ConfigJsonContext.Default.AppConfig));

        var store = new JsonConfigStore(path);
        store.Current.Decoder!.OsdNhardMax.Should().Be(40);
        await store.SaveAsync(WithNhard(store.Current, 60));

        new JsonConfigStore(path).Current.Decoder!.OsdNhardMax.Should().Be(60,
            "the operator's explicit 60 must not be reverted just because the marker was never set");
    }

    [Fact(DisplayName = "CONTROL: a pre-migration config (60, marker false) migrates once to 40 and the guard then protects a later explicit 60")]
    public async Task PreMigrationConfig_MigratesOnce_ThenGuardProtectsLaterSixty()
    {
        using var dir = new TempDirectory();
        var path = System.IO.Path.Combine(dir.Path, "config.json");
        var legacy = new AppConfig { Decoder = new DecoderConfig() with { OsdNhardMax = 60, Nhard40MigrationApplied = false } };
        File.WriteAllText(path, JsonSerializer.Serialize(legacy, ConfigJsonContext.Default.AppConfig));

        var migrated = new JsonConfigStore(path);                    // the intended case: 60 -> 40 once, marker true, written back
        migrated.Current.Decoder!.OsdNhardMax.Should().Be(40);
        migrated.Current.Decoder.Nhard40MigrationApplied.Should().BeTrue();

        await migrated.SaveAsync(WithNhard(migrated.Current, 60));   // operator sets 60 AFTER the migration
        new JsonConfigStore(path).Current.Decoder!.OsdNhardMax.Should().Be(60, "the marker is true here, so the guard works");
    }

    [Fact(DisplayName = "#199: a second Load of an already-marked config writes nothing (content and modification time unchanged)")]
    public void SecondLoad_WritesNothing()
    {
        using var dir = new TempDirectory();
        var path = System.IO.Path.Combine(dir.Path, "config.json");
        File.WriteAllText(path, """{"decoder":{"osdNhardMax":55}}""");

        _ = new JsonConfigStore(path);                       // first Load: sets the marker, writes back once
        var textAfterFirst = File.ReadAllText(path);
        textAfterFirst.Should().Contain("nhard40MigrationApplied");
        var stamp = new DateTime(2020, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        File.SetLastWriteTimeUtc(path, stamp);

        _ = new JsonConfigStore(path);                       // second Load: must not touch the file

        File.ReadAllText(path).Should().Be(textAfterFirst);
        File.GetLastWriteTimeUtc(path).Should().Be(stamp, "an idempotent Load must not rewrite the file");
    }

    [Theory(DisplayName = "#199: a non-60 value is left untouched and the marker is persisted once")]
    [InlineData(40)]
    [InlineData(55)]
    public void NonSixty_ValueUntouched_MarkerPersisted(int nhard)
    {
        using var dir = new TempDirectory();
        var path = System.IO.Path.Combine(dir.Path, "config.json");
        File.WriteAllText(path, $"{{\"decoder\":{{\"osdNhardMax\":{nhard}}}}}");

        new JsonConfigStore(path);

        var onDisk = JsonSerializer.Deserialize(File.ReadAllText(path), ConfigJsonContext.Default.AppConfig)!;
        onDisk.Decoder!.OsdNhardMax.Should().Be(nhard);
        onDisk.Decoder.Nhard40MigrationApplied.Should().BeTrue();
    }
}
