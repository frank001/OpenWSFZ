using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Config;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Config.Tests;

/// <summary>
/// Unit tests for <see cref="JsonConfigStore"/>, <see cref="ConfigPathResolver"/>,
/// and the default <see cref="AppConfig"/> shape.
/// </summary>
public sealed class JsonConfigStoreTests
{
    // ── Helper ────────────────────────────────────────────────────────────────

    /// <summary>Creates a temporary directory that is deleted when disposed.</summary>
    private sealed class TempDirectory : IDisposable
    {
        public string Path { get; } = System.IO.Path.Combine(
            System.IO.Path.GetTempPath(),
            "openwsfz-test-" + System.IO.Path.GetRandomFileName());

        public TempDirectory() => Directory.CreateDirectory(Path);

        public void Dispose()
        {
            try { Directory.Delete(Path, recursive: true); } catch { /* best-effort */ }
        }
    }

    // ── Task 8.1 ─────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-004: JsonConfigStore loads existing config file")]
    public void Load_ReadsExistingFile_AndReturnsCorrectValues()
    {
        using var dir = new TempDirectory();
        var configPath = System.IO.Path.Combine(dir.Path, "config.json");

        // Write a known config to disk.
        var expected = new AppConfig(AudioDeviceName: "TestMic", Port: 9090);
        File.WriteAllText(
            configPath,
            JsonSerializer.Serialize(expected, ConfigJsonContext.Default.AppConfig));

        // Act
        var store = new JsonConfigStore(configPath);

        // Assert
        store.Current.AudioDeviceName.Should().Be("TestMic");
        store.Current.Port.Should().Be(9090);
    }

    // ── Task 8.2 ─────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-004: JsonConfigStore creates default config when file absent")]
    public void Load_CreatesDefaultFile_WhenFileDoesNotExist()
    {
        using var dir = new TempDirectory();
        var configPath = System.IO.Path.Combine(dir.Path, "sub", "config.json");
        // Neither the file nor its parent sub-directory exist.

        // Act — must not throw.
        var store = new JsonConfigStore(configPath);

        // Assert — defaults returned and file written.
        store.Current.AudioDeviceName.Should().BeNull();
        store.Current.Port.Should().Be(8080);
        File.Exists(configPath).Should().BeTrue("the store should create the default config file");
    }

    // ── Corrupt config (advisory D) ──────────────────────────────────────────

    [Fact(DisplayName = "FR-004: JsonConfigStore returns defaults and does not throw when config file is corrupt")]
    public void Load_ReturnsDefaults_AndDoesNotThrow_WhenFileIsCorrupt()
    {
        using var dir = new TempDirectory();
        var configPath = System.IO.Path.Combine(dir.Path, "config.json");

        // Write garbage to the config file.
        File.WriteAllText(configPath, "{ this is not valid JSON !!!");

        // Act — must not throw; corrupt file must not be overwritten.
        var store = new JsonConfigStore(configPath);

        // Assert — defaults returned.
        store.Current.AudioDeviceName.Should().BeNull();
        store.Current.Port.Should().Be(8080);

        // Assert — file is intact (not overwritten with defaults).
        File.ReadAllText(configPath).Should().Contain("this is not valid JSON",
            "a corrupt config file must be preserved so the operator can recover it");
    }

    // ── FR-018: ShowCycleCountdown ────────────────────────────────────────────

    [Fact(DisplayName = "FR-018: AppConfig.ShowCycleCountdown defaults to false and round-trips via config file")]
    public async Task AppConfig_ShowCycleCountdown_DefaultsFalse_AndRoundTrips()
    {
        // Default value must be false — the testing aid is hidden on first run.
        var defaults = new AppConfig();
        defaults.ShowCycleCountdown.Should().BeFalse(
            "ShowCycleCountdown defaults to false so the cycle timer is hidden unless the operator opts in");

        // Value must persist through a save/reload cycle.
        using var dir = new TempDirectory();
        var configPath = System.IO.Path.Combine(dir.Path, "config.json");
        var store      = new JsonConfigStore(configPath);

        await store.SaveAsync(new AppConfig(ShowCycleCountdown: true));

        var reloaded = new JsonConfigStore(configPath);
        reloaded.Current.ShowCycleCountdown.Should().BeTrue(
            "ShowCycleCountdown: true must persist through the config file");
    }

    [Fact(DisplayName = "FR-018: AppConfig.ShowCycleCountdown defaults to false when field is absent from config file")]
    public void AppConfig_ShowCycleCountdown_DefaultsFalse_WhenAbsentFromFile()
    {
        // Simulate an older config file written before ShowCycleCountdown was added.
        using var dir = new TempDirectory();
        var configPath = System.IO.Path.Combine(dir.Path, "config.json");

        // Write a config that has no showCycleCountdown field.
        File.WriteAllText(configPath, """{"audioDeviceName":"TestMic","port":9090}""");

        var store = new JsonConfigStore(configPath);

        store.Current.ShowCycleCountdown.Should().BeFalse(
            "a config file written before FR-018 existed must load with ShowCycleCountdown: false");
        store.Current.AudioDeviceName.Should().Be("TestMic",
            "other fields must be preserved when ShowCycleCountdown is absent");
    }

    // ── Task 8.3 ─────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-004: JsonConfigStore.SaveAsync writes atomically")]
    public async Task SaveAsync_WritesFile_AndLeavesNoTempFiles()
    {
        using var dir = new TempDirectory();
        var configPath = System.IO.Path.Combine(dir.Path, "config.json");
        var store = new JsonConfigStore(configPath);

        var updated = new AppConfig(AudioDeviceName: "SavedMic", Port: 7070);

        // Act
        await store.SaveAsync(updated);

        // Assert — file contains expected values.
        File.Exists(configPath).Should().BeTrue();
        var onDisk = JsonSerializer.Deserialize(
            File.ReadAllText(configPath),
            ConfigJsonContext.Default.AppConfig);
        onDisk!.AudioDeviceName.Should().Be("SavedMic");
        onDisk.Port.Should().Be(7070);

        // Assert — in-memory current updated.
        store.Current.AudioDeviceName.Should().Be("SavedMic");
        store.Current.Port.Should().Be(7070);

        // Assert — no orphaned temp files remain.
        var files = Directory.GetFiles(dir.Path);
        files.Should().ContainSingle(
            "only the config file should remain — no temp files left behind");
        System.IO.Path.GetFullPath(files[0]).Should().Be(
            System.IO.Path.GetFullPath(configPath));
    }
}
