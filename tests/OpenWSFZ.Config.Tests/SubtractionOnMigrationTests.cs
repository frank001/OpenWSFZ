using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Config;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Config.Tests;

/// <summary>
/// SUB-FEAS default-ON (v0.54), acceptance rows A1 to A4 of the QA handoff
/// <c>dev-tasks/2026-10-02-sub-feas-default-on.md</c>: <c>decoder.subtractionEnabled</c> defaults to
/// <c>true</c>, a persisted <c>false</c> is migrated to <c>true</c> once, and the marker
/// <c>decoder.subtractionOnMigrationApplied</c> means "no migration is pending for this install"
/// (the #199 rule), so an operator's later deliberate OFF survives a restart. All values are synthetic.
/// </summary>
/// <remarks>
/// The class is in its own collection because one test captures <c>Console.Error</c> (a process-global).
/// </remarks>
[Collection("ConsoleError")]
public sealed class SubtractionOnMigrationTests
{
    private sealed class TempDirectory : IDisposable
    {
        public string Path { get; } = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "openwsfz-subon-" + System.IO.Path.GetRandomFileName());
        public TempDirectory() => Directory.CreateDirectory(Path);
        public void Dispose() { try { Directory.Delete(Path, recursive: true); } catch { /* best-effort */ } }
    }

    private static string ConfigPath(TempDirectory dir) => System.IO.Path.Combine(dir.Path, "config.json");

    private static AppConfig OnDisk(string path)
        => JsonSerializer.Deserialize(File.ReadAllText(path), ConfigJsonContext.Default.AppConfig)!;

    private static bool EffectiveSubtraction(JsonConfigStore store)
        => (store.Current.Decoder ?? new DecoderConfig()).SubtractionEnabled;

    [Fact(DisplayName = "A0: the DecoderConfig code default is subtractionEnabled true and the marker default is false")]
    public void CodeDefaults()
    {
        new DecoderConfig().SubtractionEnabled.Should().BeTrue();
        new DecoderConfig().SubtractionOnMigrationApplied.Should().BeFalse(
            "a legacy file without the key must deserialise to false so a genuine legacy OFF is migrated once");
        JsonSerializer.Deserialize("""{"decoder":{}}""", ConfigJsonContext.Default.AppConfig)!
            .Decoder!.SubtractionEnabled.Should().BeTrue("an absent key resolves to the new default");
    }

    [Fact(DisplayName = "A1: no config file: loaded subtractionEnabled is true and the marker is true on disk after the first load")]
    public void NoConfigFile_On_MarkerTrueOnDisk()
    {
        using var dir = new TempDirectory();
        var path = ConfigPath(dir);

        var store = new JsonConfigStore(path);

        EffectiveSubtraction(store).Should().BeTrue();
        var disk = OnDisk(path).Decoder;
        disk.Should().NotBeNull();
        disk!.SubtractionEnabled.Should().BeTrue();
        disk.SubtractionOnMigrationApplied.Should().BeTrue("a fresh install must never carry marker false");
    }

    [Fact(DisplayName = "A2: legacy subtractionEnabled false with no marker: migrated to true, marker true, written to disk, one stderr line")]
    public void LegacyFalse_MigratesOnce_WritesBack_OneStderrLine()
    {
        using var dir = new TempDirectory();
        var path = ConfigPath(dir);
        File.WriteAllText(path, """{"decoder":{"subtractionEnabled":false}}""");

        var original = Console.Error;
        var captured = new StringWriter();
        Console.SetError(captured);
        JsonConfigStore store;
        try { store = new JsonConfigStore(path); }
        finally { Console.SetError(original); }

        store.Current.Decoder!.SubtractionEnabled.Should().BeTrue();
        store.Current.Decoder.SubtractionOnMigrationApplied.Should().BeTrue();
        var disk = OnDisk(path).Decoder!;
        disk.SubtractionEnabled.Should().BeTrue("the migration is written back at once");
        disk.SubtractionOnMigrationApplied.Should().BeTrue();

        var lines = captured.ToString().Split('\n', StringSplitOptions.RemoveEmptyEntries)
            .Where(l => l.Contains("subtractionEnabled: migrated")).ToArray();
        lines.Should().HaveCount(1, "exactly one stderr line on migration");
        lines[0].Should().Contain("false -> true").And.Contain("to false",
            "the line names the old and new value and how to turn it off");
    }

    [Fact(DisplayName = "A3: subtractionEnabled false with the marker true stays false across 2 reloads")]
    public void FalseWithMarkerTrue_StaysFalse_AcrossTwoReloads()
    {
        using var dir = new TempDirectory();
        var path = ConfigPath(dir);
        File.WriteAllText(path, """{"decoder":{"subtractionEnabled":false,"subtractionOnMigrationApplied":true,"nhard40MigrationApplied":true}}""");

        EffectiveSubtraction(new JsonConfigStore(path)).Should().BeFalse();
        EffectiveSubtraction(new JsonConfigStore(path)).Should().BeFalse();
    }

    [Fact(DisplayName = "A4: fresh install, operator saves subtractionEnabled false, reload twice: stays false (the #199 trap, for this flag)")]
    public async Task FreshInstall_ExplicitOff_SurvivesTwoReloads()
    {
        using var dir = new TempDirectory();
        var path = ConfigPath(dir);

        var first = new JsonConfigStore(path);
        await first.SaveAsync(first.Current with
        {
            Decoder = (first.Current.Decoder ?? new DecoderConfig()) with { SubtractionEnabled = false },
        });

        EffectiveSubtraction(new JsonConfigStore(path)).Should().BeFalse("an explicit OFF must not be migrated back to ON");
        EffectiveSubtraction(new JsonConfigStore(path)).Should().BeFalse();
    }

    [Fact(DisplayName = "A4b: a section created from nothing by a save (store held no decoder section) carries the marker true")]
    public async Task SaveCreatingDecoderSection_MarkerTrue()
    {
        using var dir = new TempDirectory();
        var path = ConfigPath(dir);
        File.WriteAllText(path, """{"port":8080}""");   // legacy file with no decoder section
        var store = new JsonConfigStore(path);
        store.Current.Decoder.Should().BeNull();

        await store.SaveAsync(store.Current with { Decoder = new DecoderConfig() with { SubtractionEnabled = false } });

        OnDisk(path).Decoder!.SubtractionOnMigrationApplied.Should().BeTrue();
        EffectiveSubtraction(new JsonConfigStore(path)).Should().BeFalse();
    }

    [Fact(DisplayName = "A4c: a decoder section already at the default ON with the marker false: the load sets the marker, a later OFF survives")]
    public async Task DefaultOnSectionMarkerFalse_LaterOffSurvives()
    {
        using var dir = new TempDirectory();
        var path = ConfigPath(dir);
        File.WriteAllText(path, """{"decoder":{"subtractionEnabled":true}}""");

        var store = new JsonConfigStore(path);
        store.Current.Decoder!.SubtractionOnMigrationApplied.Should().BeTrue();
        await store.SaveAsync(store.Current with { Decoder = store.Current.Decoder with { SubtractionEnabled = false } });

        EffectiveSubtraction(new JsonConfigStore(path)).Should().BeFalse();
    }

    [Fact(DisplayName = "a second Load of an already-migrated config writes nothing (content and modification time unchanged)")]
    public void SecondLoad_WritesNothing()
    {
        using var dir = new TempDirectory();
        var path = ConfigPath(dir);
        File.WriteAllText(path, """{"decoder":{"subtractionEnabled":false}}""");

        _ = new JsonConfigStore(path);                       // migrates, writes back once
        var textAfterFirst = File.ReadAllText(path);
        textAfterFirst.Should().Contain("subtractionOnMigrationApplied");
        var stamp = new DateTime(2020, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        File.SetLastWriteTimeUtc(path, stamp);

        _ = new JsonConfigStore(path);                       // second load: must not touch the file

        File.ReadAllText(path).Should().Be(textAfterFirst);
        File.GetLastWriteTimeUtc(path).Should().Be(stamp, "an idempotent Load must not rewrite the file");
    }

    [Fact(DisplayName = "a legacy subtractionEnabled false plus a legacy osdNhardMax 60 migrate in one write")]
    public void LegacyFalseAndLegacy60_MigrateInOneWrite()
    {
        using var dir = new TempDirectory();
        var path = ConfigPath(dir);
        File.WriteAllText(path, """{"decoder":{"osdNhardMax":60,"subtractionEnabled":false}}""");

        var store = new JsonConfigStore(path);

        store.Current.Decoder!.OsdNhardMax.Should().Be(40);
        store.Current.Decoder.SubtractionEnabled.Should().BeTrue();
        var disk = OnDisk(path).Decoder!;
        disk.OsdNhardMax.Should().Be(40);
        disk.SubtractionEnabled.Should().BeTrue();
        disk.Nhard40MigrationApplied.Should().BeTrue();
        disk.SubtractionOnMigrationApplied.Should().BeTrue("both markers are on disk after the one load");

        // One write: nothing further is rewritten by a second load.
        var text = File.ReadAllText(path);
        var stamp = new DateTime(2020, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        File.SetLastWriteTimeUtc(path, stamp);
        _ = new JsonConfigStore(path);
        File.ReadAllText(path).Should().Be(text);
        File.GetLastWriteTimeUtc(path).Should().Be(stamp);
    }

    [Fact(DisplayName = "a file with no decoder key still writes nothing on Load (there is no section to carry a marker)")]
    public void NoDecoderKey_NothingWritten()
    {
        using var dir = new TempDirectory();
        var path = ConfigPath(dir);
        File.WriteAllText(path, """{"port":8080}""");

        var store = new JsonConfigStore(path);

        store.Current.Decoder.Should().BeNull();
        File.ReadAllText(path).Should().NotContain("subtractionOnMigrationApplied");
    }
}
