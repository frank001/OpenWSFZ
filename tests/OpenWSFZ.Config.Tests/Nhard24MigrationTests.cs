using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Config;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Config.Tests;

/// <summary>
/// OSD-FIX R4: the <c>osdNhardMax</c> default moves 40 to 24 and a persisted exactly-40 is migrated once, with the
/// server-owned marker <c>nhard24MigrationApplied</c> (the #199 pattern: "no migration is pending for this install").
/// Every migration case asserts the VALUE, not only the marker. All values are synthetic.
/// </summary>
public sealed class Nhard24MigrationTests
{
    private sealed class TempDirectory : IDisposable
    {
        public string Path { get; } = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "openwsfz-n24-" + System.IO.Path.GetRandomFileName());
        public TempDirectory() => Directory.CreateDirectory(Path);
        public void Dispose() { try { Directory.Delete(Path, recursive: true); } catch { /* best-effort */ } }
    }

    private static string ConfigPath(TempDirectory d) => System.IO.Path.Combine(d.Path, "config.json");

    private static DecoderConfig? OnDisk(string path)
        => JsonSerializer.Deserialize(File.ReadAllText(path), ConfigJsonContext.Default.AppConfig)!.Decoder;

    [Fact(DisplayName = "FR-085: defaults agree at 24 (new DecoderConfig, empty decoder object, absent osdNhardMax key)")]
    public void Defaults_AreTwentyFour_Everywhere()
    {
        new DecoderConfig().OsdNhardMax.Should().Be(24, "the property initialiser");
        JsonSerializer.Deserialize("{}", ConfigJsonContext.Default.DecoderConfig)!.OsdNhardMax.Should().Be(24, "the [JsonConstructor] parameter default");
        JsonSerializer.Deserialize("""{"kMinScorePass2":8}""", ConfigJsonContext.Default.DecoderConfig)!.OsdNhardMax.Should().Be(24, "a partial object");
        new DecoderConfig().Nhard24MigrationApplied.Should().BeFalse();
        JsonSerializer.Deserialize("{}", ConfigJsonContext.Default.DecoderConfig)!.Nhard24MigrationApplied.Should().BeFalse("absent key = not yet migrated");
    }

    [Fact(DisplayName = "FR-085: a fresh install gets 24 with the marker true")]
    public void FreshInstall_IsTwentyFour_MarkerTrue()
    {
        using var dir = new TempDirectory();
        var path = ConfigPath(dir);
        _ = new JsonConfigStore(path);               // first run: writes the default file
        var disk = OnDisk(path)!;
        disk.OsdNhardMax.Should().Be(24);
        disk.Nhard24MigrationApplied.Should().BeTrue("nothing to migrate on a fresh install");
        new JsonConfigStore(path).Current.Decoder!.OsdNhardMax.Should().Be(24, "and it survives a restart");
    }

    [Fact(DisplayName = "FR-085: a persisted 40 with the marker false becomes exactly 24, marker true, written back once")]
    public void Persisted40_MigratesTo24_WrittenOnce()
    {
        using var dir = new TempDirectory();
        var path = ConfigPath(dir);
        File.WriteAllText(path, """{"decoder":{"osdNhardMax":40,"nhard40MigrationApplied":true}}""");

        var store = new JsonConfigStore(path);

        store.Current.Decoder!.OsdNhardMax.Should().Be(24);
        store.Current.Decoder.Nhard24MigrationApplied.Should().BeTrue();
        var disk = OnDisk(path)!;
        disk.OsdNhardMax.Should().Be(24, "written back");
        disk.Nhard24MigrationApplied.Should().BeTrue();

        var stamp = new DateTime(2020, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        File.SetLastWriteTimeUtc(path, stamp);
        var text = File.ReadAllText(path);
        var second = new JsonConfigStore(path);
        second.Current.Decoder!.OsdNhardMax.Should().Be(24);
        File.GetLastWriteTimeUtc(path).Should().Be(stamp, "a second Load writes nothing");
        File.ReadAllText(path).Should().Be(text);
    }

    [Fact(DisplayName = "FR-085: a persisted 40 with the marker already true stays 40 (a deliberate 40 is not re-migrated)")]
    public void Persisted40_MarkerTrue_StaysForty()
    {
        using var dir = new TempDirectory();
        var path = ConfigPath(dir);
        File.WriteAllText(path, """{"decoder":{"osdNhardMax":40,"nhard40MigrationApplied":true,"nhard24MigrationApplied":true}}""");

        new JsonConfigStore(path).Current.Decoder!.OsdNhardMax.Should().Be(40);
    }

    [Theory(DisplayName = "FR-085: a persisted value other than 40 is left alone and still gets the marker (#199)")]
    [InlineData(30)]
    [InlineData(50)]
    [InlineData(55)]
    [InlineData(70)]
    public void NotForty_Untouched_MarkerSet(int nhard)
    {
        using var dir = new TempDirectory();
        var path = ConfigPath(dir);
        File.WriteAllText(path, $"{{\"decoder\":{{\"osdNhardMax\":{nhard},\"nhard40MigrationApplied\":true}}}}");

        var store = new JsonConfigStore(path);

        store.Current.Decoder!.OsdNhardMax.Should().Be(nhard);
        store.Current.Decoder.Nhard24MigrationApplied.Should().BeTrue();
        var disk = OnDisk(path)!;
        disk.OsdNhardMax.Should().Be(nhard);
        disk.Nhard24MigrationApplied.Should().BeTrue("persisted once");
    }

    [Fact(DisplayName = "FR-085: a legacy 60 with no markers chains to 24 in ONE Load, both markers true")]
    public void Legacy60_ChainsTo24_BothMarkers()
    {
        using var dir = new TempDirectory();
        var path = ConfigPath(dir);
        File.WriteAllText(path, """{"decoder":{"osdNhardMax":60}}""");

        var store = new JsonConfigStore(path);

        store.Current.Decoder!.OsdNhardMax.Should().Be(24);
        store.Current.Decoder.Nhard40MigrationApplied.Should().BeTrue();
        store.Current.Decoder.Nhard24MigrationApplied.Should().BeTrue();
        var disk = OnDisk(path)!;
        disk.OsdNhardMax.Should().Be(24);
        disk.Nhard40MigrationApplied.Should().BeTrue();
        disk.Nhard24MigrationApplied.Should().BeTrue();
    }

    [Fact(DisplayName = "FR-085: a 60 with nhard40MigrationApplied true (a deliberate 60) passes through unchanged")]
    public void Sixty_WithNhard40MarkerTrue_Unchanged()
    {
        using var dir = new TempDirectory();
        var path = ConfigPath(dir);
        File.WriteAllText(path, """{"decoder":{"osdNhardMax":60,"nhard40MigrationApplied":true}}""");

        new JsonConfigStore(path).Current.Decoder!.OsdNhardMax.Should().Be(60);
    }

    [Fact(DisplayName = "FR-085: a config with no decoder key gets no decoder section")]
    public void NoDecoderKey_NoSectionCreated()
    {
        using var dir = new TempDirectory();
        var path = ConfigPath(dir);
        File.WriteAllText(path, """{"tx":{}}""");

        new JsonConfigStore(path).Current.Decoder.Should().BeNull();
    }

    [Fact(DisplayName = "FR-085: a decoder section without osdNhardMax resolves to 24 and is marked")]
    public void DecoderWithoutNhardKey_Is24_Marked()
    {
        using var dir = new TempDirectory();
        var path = ConfigPath(dir);
        File.WriteAllText(path, """{"decoder":{"kMinScorePass2":8}}""");

        var store = new JsonConfigStore(path);
        store.Current.Decoder!.OsdNhardMax.Should().Be(24);
        store.Current.Decoder.Nhard24MigrationApplied.Should().BeTrue();
    }

    [Fact(DisplayName = "FR-085: a deliberate 40 set AFTER the migration survives a restart")]
    public async Task DeliberateForty_AfterMigration_SurvivesReload()
    {
        using var dir = new TempDirectory();
        var path = ConfigPath(dir);
        File.WriteAllText(path, """{"decoder":{"osdNhardMax":40,"nhard40MigrationApplied":true}}""");
        var store = new JsonConfigStore(path);
        store.Current.Decoder!.OsdNhardMax.Should().Be(24);

        await store.SaveAsync(store.Current with { Decoder = store.Current.Decoder with { OsdNhardMax = 40 } });

        new JsonConfigStore(path).Current.Decoder!.OsdNhardMax.Should().Be(40);
    }

    [Fact(DisplayName = "FR-085: SaveAsync creating a decoder section from nothing marks it migrated (no 40 can have existed)")]
    public async Task SaveCreatingDecoderSection_MarkerTrue()
    {
        using var dir = new TempDirectory();
        var path = ConfigPath(dir);
        File.WriteAllText(path, """{"tx":{}}""");
        var store = new JsonConfigStore(path);
        store.Current.Decoder.Should().BeNull();

        await store.SaveAsync(store.Current with { Decoder = new DecoderConfig() with { OsdNhardMax = 40 } });

        store.Current.Decoder!.Nhard24MigrationApplied.Should().BeTrue();
        new JsonConfigStore(path).Current.Decoder!.OsdNhardMax.Should().Be(40, "an explicit 40 on a freshly created section must not be reverted");
    }
}
