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
        var expected = new AppConfig(AudioDeviceId: "TestMic", Port: 9090);
        File.WriteAllText(
            configPath,
            JsonSerializer.Serialize(expected, ConfigJsonContext.Default.AppConfig));

        // Act
        var store = new JsonConfigStore(configPath);

        // Assert
        store.Current.AudioDeviceId.Should().Be("TestMic");
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
        store.Current.AudioDeviceId.Should().BeNull();
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
        store.Current.AudioDeviceId.Should().BeNull();
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
        store.Current.AudioDeviceId.Should().Be("TestMic",
            "legacy audioDeviceName must be migrated to AudioDeviceId");
    }

    // ── Task 8.3 ─────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-004: JsonConfigStore.SaveAsync writes atomically")]
    public async Task SaveAsync_WritesFile_AndLeavesNoTempFiles()
    {
        using var dir = new TempDirectory();
        var configPath = System.IO.Path.Combine(dir.Path, "config.json");
        var store = new JsonConfigStore(configPath);

        var updated = new AppConfig(AudioDeviceId: "SavedMic", Port: 7070);

        // Act
        await store.SaveAsync(updated);

        // Assert — file contains expected values.
        File.Exists(configPath).Should().BeTrue();
        var onDisk = JsonSerializer.Deserialize(
            File.ReadAllText(configPath),
            ConfigJsonContext.Default.AppConfig);
        onDisk!.AudioDeviceId.Should().Be("SavedMic");
        onDisk.Port.Should().Be(7070);

        // Assert — in-memory current updated.
        store.Current.AudioDeviceId.Should().Be("SavedMic");
        store.Current.Port.Should().Be(7070);

        // Assert — no orphaned temp files remain.
        var files = Directory.GetFiles(dir.Path);
        files.Should().ContainSingle(
            "only the config file should remain — no temp files left behind");
        System.IO.Path.GetFullPath(files[0]).Should().Be(
            System.IO.Path.GetFullPath(configPath));
    }

    // ── FR-019: configurable log level ────────────────────────────────────────

    [Fact(DisplayName = "FR-019: AppConfig.LogLevel defaults to \"Information\"")]
    public void AppConfig_LogLevel_DefaultsToInformation()
    {
        var config = new AppConfig();

        config.LogLevel.Should().Be("Information",
            "the default log level is Information so operators see pipeline events without noise");
    }

    [Fact(DisplayName = "FR-019: AppConfig.LogLevel round-trips via config file")]
    public async Task AppConfig_LogLevel_RoundTrips()
    {
        using var dir = new TempDirectory();
        var configPath = System.IO.Path.Combine(dir.Path, "config.json");
        var store = new JsonConfigStore(configPath);

        await store.SaveAsync(new AppConfig(LogLevel: "Debug"));

        var reloaded = new JsonConfigStore(configPath);
        reloaded.Current.LogLevel.Should().Be("Debug",
            "the LogLevel value must persist through a save/reload cycle");
    }

    [Fact(DisplayName = "FR-019: AppConfig.LogLevel defaults to \"Information\" when field is absent from config file")]
    public void AppConfig_LogLevel_DefaultsToInformation_WhenAbsentFromFile()
    {
        // Simulate a config file written before FR-019 was added.
        using var dir = new TempDirectory();
        var configPath = System.IO.Path.Combine(dir.Path, "config.json");
        File.WriteAllText(configPath, """{"audioDeviceName":"TestMic","port":9090}""");

        var store = new JsonConfigStore(configPath);

        store.Current.LogLevel.Should().Be("Information",
            "a config file without logLevel must load with the default 'Information'");
        store.Current.AudioDeviceId.Should().Be("TestMic",
            "legacy audioDeviceName must be migrated to AudioDeviceId");
    }

    // ── p7: audioDeviceName migration ────────────────────────────────────────────

    [Fact(DisplayName = "FR-025: Legacy audioDeviceName config is migrated to AudioDeviceId on load")]
    public void Load_MigratesLegacyAudioDeviceName_ToAudioDeviceId()
    {
        using var dir = new TempDirectory();
        var configPath = System.IO.Path.Combine(dir.Path, "config.json");

        File.WriteAllText(configPath, """{"audioDeviceName":"LegacyDevice","port":8080}""");

        var store = new JsonConfigStore(configPath);

        store.Current.AudioDeviceId.Should().Be("LegacyDevice",
            "the legacy audioDeviceName value must be promoted to AudioDeviceId");
        store.Current.AudioDeviceFriendlyName.Should().BeNull(
            "no friendly name was stored in the legacy config");
        store.Current.Port.Should().Be(8080);
    }

    [Fact(DisplayName = "FR-025: AudioDeviceFriendlyName round-trips via config file")]
    public async Task AudioDeviceFriendlyName_RoundTrips()
    {
        using var dir = new TempDirectory();
        var configPath = System.IO.Path.Combine(dir.Path, "config.json");
        var store = new JsonConfigStore(configPath);

        await store.SaveAsync(new AppConfig(
            AudioDeviceId:           "{0.0.1.00000000}.{test-guid}",
            AudioDeviceFriendlyName: "Test Microphone"));

        var reloaded = new JsonConfigStore(configPath);
        reloaded.Current.AudioDeviceId.Should().Be("{0.0.1.00000000}.{test-guid}");
        reloaded.Current.AudioDeviceFriendlyName.Should().Be("Test Microphone");
    }

    // ── Task 8.3: audioOutputDeviceId / audioOutputFriendlyName round-trip ───────

    [Fact(DisplayName = "FR-NEW: AppConfig.AudioOutputDeviceId and AudioOutputFriendlyName default to null")]
    public void AppConfig_AudioOutputFields_DefaultToNull()
    {
        var config = new AppConfig();

        config.AudioOutputDeviceId.Should().BeNull(
            "AudioOutputDeviceId must default to null so existing config files load without error");
        config.AudioOutputFriendlyName.Should().BeNull(
            "AudioOutputFriendlyName must default to null so existing config files load without error");
    }

    [Fact(DisplayName = "FR-NEW: Config without audioOutputDeviceId deserialises to null (backward compat)")]
    public void Load_Deserialises_AudioOutputDeviceId_AsNull_WhenFieldAbsentFromFile()
    {
        using var dir = new TempDirectory();
        var configPath = System.IO.Path.Combine(dir.Path, "config.json");

        // Write a config that has no audioOutputDeviceId or audioOutputFriendlyName field.
        File.WriteAllText(configPath, """{"audioDeviceId":"mic","port":8080}""");

        var store = new JsonConfigStore(configPath);

        store.Current.AudioOutputDeviceId.Should().BeNull(
            "a config file written before audio output device support must load with AudioOutputDeviceId: null");
        store.Current.AudioOutputFriendlyName.Should().BeNull(
            "a config file written before audio output device support must load with AudioOutputFriendlyName: null");
    }

    [Fact(DisplayName = "FR-NEW: AudioOutputDeviceId and AudioOutputFriendlyName round-trip via config file")]
    public async Task AudioOutputDevice_RoundTrips()
    {
        using var dir = new TempDirectory();
        var configPath = System.IO.Path.Combine(dir.Path, "config.json");
        var store = new JsonConfigStore(configPath);

        await store.SaveAsync(new AppConfig(
            AudioOutputDeviceId:     "{0.0.0.00000000}.{render-test-guid}",
            AudioOutputFriendlyName: "Speakers (USB Headset)"));

        var reloaded = new JsonConfigStore(configPath);
        reloaded.Current.AudioOutputDeviceId.Should().Be("{0.0.0.00000000}.{render-test-guid}");
        reloaded.Current.AudioOutputFriendlyName.Should().Be("Speakers (USB Headset)");
    }

    // ── p6: LoggingConfig defaults and round-trip ─────────────────────────────────

    [Fact(DisplayName = "FR-022: AppConfig.Logging defaults to file logging disabled")]
    public void AppConfig_Logging_DefaultsToFileDisabled()
    {
        var config = new AppConfig();

        config.Logging.FileEnabled.Should().BeFalse(
            "file logging must be opt-in; operators are not surprised by unexpected files on first run");
        config.Logging.Directory.Should().Be("logs");
        config.Logging.FileLogLevel.Should().Be("Information");
        config.Logging.RotationSchedule.Should().Be("daily");
        config.Logging.MaxFiles.Should().Be(7);
    }

    [Fact(DisplayName = "FR-022: AppConfig.Logging round-trips via config file")]
    public async Task AppConfig_Logging_RoundTrips()
    {
        using var dir = new TempDirectory();
        var configPath = System.IO.Path.Combine(dir.Path, "config.json");
        var store = new JsonConfigStore(configPath);

        var logging = new LoggingConfig { FileEnabled = true, Directory = "C:\\logs", MaxFiles = 3 };
        await store.SaveAsync(new AppConfig() { Logging = logging });

        var reloaded = new JsonConfigStore(configPath);
        reloaded.Current.Logging.FileEnabled.Should().BeTrue();
        reloaded.Current.Logging.Directory.Should().Be("C:\\logs");
        reloaded.Current.Logging.MaxFiles.Should().Be(3);
    }

    [Fact(DisplayName = "FR-022: AppConfig.Logging defaults when logging key absent from config file")]
    public void AppConfig_Logging_Defaults_WhenAbsentFromFile()
    {
        using var dir = new TempDirectory();
        var configPath = System.IO.Path.Combine(dir.Path, "config.json");
        File.WriteAllText(configPath, """{"audioDeviceId":"mic","port":8080}""");

        var store = new JsonConfigStore(configPath);

        store.Current.Logging.FileEnabled.Should().BeFalse(
            "Logging must default to disabled when the key is absent");
    }
}
