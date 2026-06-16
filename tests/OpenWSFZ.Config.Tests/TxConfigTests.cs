using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Config;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Config.Tests;

/// <summary>
/// Tests for <see cref="TxConfig"/> configuration schema (FR-046).
/// Verifies defaults, round-trip fidelity, clamping behaviour, and JSON key names.
/// </summary>
[Trait("Category", "Unit")]
public sealed class TxConfigTests
{
    // ── Helper ────────────────────────────────────────────────────────────────

    /// <summary>Creates a temporary directory that is deleted when disposed.</summary>
    private sealed class TempDirectory : IDisposable
    {
        public string Path { get; } = System.IO.Path.Combine(
            System.IO.Path.GetTempPath(),
            "openwsfz-txcfg-" + System.IO.Path.GetRandomFileName());

        public TempDirectory() => Directory.CreateDirectory(Path);

        public void Dispose()
        {
            try { Directory.Delete(Path, recursive: true); } catch { /* best-effort */ }
        }
    }

    // ── Scenario: Missing tx key uses defaults ────────────────────────────────

    [Fact(DisplayName = "FR-046: AppConfig without tx key deserialises with Tx = null")]
    public void Load_MissingTxKey_TxIsNull()
    {
        const string json = """{"port":8080}""";
        var config = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)!;

        config.Tx.Should().BeNull("absent tx key must produce null, treated as all defaults");

        // Consumers normalise via (config.Tx ?? new TxConfig()).
        var effective = config.Tx ?? new TxConfig();
        effective.Callsign.Should().Be("Q1OFZ");
        effective.Grid.Should().Be("JO33");
        effective.RetryCount.Should().Be(3);
        effective.WatchdogMinutes.Should().Be(4);
    }

    // ── Scenario: Default values ──────────────────────────────────────────────

    [Fact(DisplayName = "FR-046: TxConfig defaults: callsign=Q1OFZ, grid=JO33, retryCount=3, watchdogMinutes=4, autoAnswer=false")]
    public void Defaults_AreCorrect()
    {
        var tx = new TxConfig();

        tx.AutoAnswer.Should().BeFalse("auto-answer must default to off for safety");
        tx.Callsign.Should().Be("Q1OFZ");
        tx.Grid.Should().Be("JO33");
        tx.RetryCount.Should().Be(3);
        tx.WatchdogMinutes.Should().Be(4);
    }

    [Fact(DisplayName = "FR-050: TxConfig.AutoAnswer default is false — transmit disabled unless operator enables")]
    public void AutoAnswer_DefaultIsFalse()
    {
        new TxConfig().AutoAnswer.Should().BeFalse();
    }

    [Fact(DisplayName = "FR-050: TxConfig.AutoAnswer round-trips through JSON serialisation")]
    public void AutoAnswer_RoundTrips()
    {
        var original = new AppConfig() with { Tx = new TxConfig { AutoAnswer = true } };
        var json   = JsonSerializer.Serialize(original, ConfigJsonContext.Default.AppConfig);
        var loaded = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)!;

        loaded.Tx!.AutoAnswer.Should().BeTrue("autoAnswer=true must survive a JSON round-trip");

        json.Should().Contain("\"autoAnswer\"", "camelCase key name must be used in JSON");
    }

    [Fact(DisplayName = "FR-050: AppConfig without autoAnswer key deserialises with AutoAnswer=false")]
    public void Load_MissingAutoAnswerKey_DefaultsFalse()
    {
        const string json = """{"tx":{"callsign":"Q1OFZ","grid":"JO33","retryCount":3,"watchdogMinutes":4}}""";
        var config = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)!;

        (config.Tx ?? new TxConfig()).AutoAnswer.Should().BeFalse(
            "absent autoAnswer key must default to false so existing configs remain safe");
    }

    // ── Scenario: Round-trip ─────────────────────────────────────────────────

    [Fact(DisplayName = "FR-046: TxConfig round-trips all four fields through JSON serialisation")]
    public void RoundTrip_AllFields_PreservesValues()
    {
        var original = new AppConfig() with
        {
            Tx = new TxConfig
            {
                Callsign        = "Q1TST",
                Grid            = "IO91",
                RetryCount      = 5,
                WatchdogMinutes = 8,
            }
        };

        var json   = JsonSerializer.Serialize(original, ConfigJsonContext.Default.AppConfig);
        var loaded = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)!;

        loaded.Tx.Should().NotBeNull();
        loaded.Tx!.Callsign.Should().Be("Q1TST");
        loaded.Tx.Grid.Should().Be("IO91");
        loaded.Tx.RetryCount.Should().Be(5);
        loaded.Tx.WatchdogMinutes.Should().Be(8);
    }

    // ── Scenario: JSON key names use camelCase ────────────────────────────────

    [Fact(DisplayName = "FR-046: TxConfig serialises with camelCase JSON property names")]
    public void Serialise_TxConfig_UsesCamelCase()
    {
        var config = new AppConfig() with { Tx = new TxConfig() };
        var json   = JsonSerializer.Serialize(config, ConfigJsonContext.Default.AppConfig);

        json.Should().Contain("\"tx\"");
        json.Should().Contain("\"callsign\"");
        json.Should().Contain("\"grid\"");
        json.Should().Contain("\"retryCount\"");
        json.Should().Contain("\"watchdogMinutes\"");
    }

    // ── Scenario: Clamping via JsonConfigStore ────────────────────────────────

    [Fact(DisplayName = "FR-046: JsonConfigStore clamps retryCount < 1 to 1")]
    public void Load_RetryCountBelowMinimum_ClampsToOne()
    {
        using var dir = new TempDirectory();
        var configPath = System.IO.Path.Combine(dir.Path, "config.json");

        // Write config with retryCount = 0 (invalid).
        const string json = """{"tx":{"callsign":"Q1OFZ","grid":"JO33","retryCount":0,"watchdogMinutes":4}}""";
        File.WriteAllText(configPath, json);

        var store = new JsonConfigStore(configPath);

        store.Current.Tx.Should().NotBeNull();
        store.Current.Tx!.RetryCount.Should().Be(1,
            "retryCount 0 is below minimum and must be clamped to 1");
    }

    [Fact(DisplayName = "FR-046: JsonConfigStore clamps watchdogMinutes < 1 to 1")]
    public void Load_WatchdogMinutesBelowMinimum_ClampsToOne()
    {
        using var dir = new TempDirectory();
        var configPath = System.IO.Path.Combine(dir.Path, "config.json");

        // Write config with watchdogMinutes = -5 (invalid).
        const string json = """{"tx":{"callsign":"Q1OFZ","grid":"JO33","retryCount":3,"watchdogMinutes":-5}}""";
        File.WriteAllText(configPath, json);

        var store = new JsonConfigStore(configPath);

        store.Current.Tx.Should().NotBeNull();
        store.Current.Tx!.WatchdogMinutes.Should().Be(1,
            "watchdogMinutes -5 is below minimum and must be clamped to 1");
    }

    [Fact(DisplayName = "FR-046: JsonConfigStore clamps both retryCount and watchdogMinutes when both are invalid")]
    public void Load_BothFieldsBelowMinimum_BothClamped()
    {
        using var dir = new TempDirectory();
        var configPath = System.IO.Path.Combine(dir.Path, "config.json");

        const string json = """{"tx":{"callsign":"Q1OFZ","grid":"JO33","retryCount":0,"watchdogMinutes":0}}""";
        File.WriteAllText(configPath, json);

        var store = new JsonConfigStore(configPath);

        store.Current.Tx.Should().NotBeNull();
        store.Current.Tx!.RetryCount.Should().Be(1,      "retryCount 0 must clamp to 1");
        store.Current.Tx!.WatchdogMinutes.Should().Be(1, "watchdogMinutes 0 must clamp to 1");
    }

    [Fact(DisplayName = "FR-046: JsonConfigStore does not clamp valid retryCount and watchdogMinutes")]
    public void Load_ValidValues_NotClamped()
    {
        using var dir = new TempDirectory();
        var configPath = System.IO.Path.Combine(dir.Path, "config.json");

        const string json = """{"tx":{"callsign":"Q1OFZ","grid":"JO33","retryCount":5,"watchdogMinutes":10}}""";
        File.WriteAllText(configPath, json);

        var store = new JsonConfigStore(configPath);

        store.Current.Tx.Should().NotBeNull();
        store.Current.Tx!.RetryCount.Should().Be(5,       "valid retryCount must not be clamped");
        store.Current.Tx!.WatchdogMinutes.Should().Be(10, "valid watchdogMinutes must not be clamped");
    }

    // ── Scenario: Default config file includes tx section ────────────────────

    [Fact(DisplayName = "FR-046: JsonConfigStore default config file includes tx section with all defaults")]
    public void CreateDefault_WritesFileWithTxSection()
    {
        using var dir = new TempDirectory();
        var configPath = System.IO.Path.Combine(dir.Path, "config.json");

        // Store creates the default file on construction when file is absent.
        _ = new JsonConfigStore(configPath);

        File.Exists(configPath).Should().BeTrue("a default config file must be written");

        var text = File.ReadAllText(configPath);
        text.Should().Contain("\"tx\"",              "default config must include the tx key");
        text.Should().Contain("\"callsign\"",         "default config must include callsign");
        text.Should().Contain("\"retryCount\"",       "default config must include retryCount");
        text.Should().Contain("\"watchdogMinutes\"",  "default config must include watchdogMinutes");
    }

    // ── Scenario: Partial tx object loads without error ──────────────────────

    [Fact(DisplayName = "FR-046: Partial tx JSON (only callsign present) loads without error")]
    public void Load_PartialTxJson_LoadsWithoutError()
    {
        const string json = """{"tx":{"callsign":"Q1TST"}}""";
        AppConfig? config = null;
        var act = () => config = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig);

        act.Should().NotThrow("a partial tx object must deserialise without error");
        config!.Tx.Should().NotBeNull();
        config.Tx!.Callsign.Should().Be("Q1TST",
            "the explicitly-provided callsign field must be correct");
    }

    // ── Task 8.1 / 1.2 — Existing app.json without audio offset fields uses defaults ───

    [Fact(DisplayName = "Task 8.1: TxConfig without rxAudioOffsetHz/txAudioOffsetHz/holdTxFreq deserialises with defaults")]
    public void Load_MissingAudioOffsetFields_UsesDefaults()
    {
        // Existing config JSON that predates the audio-offset feature.
        const string json = """
            {"tx":{"callsign":"Q1OFZ","grid":"JO33","retryCount":3,"watchdogMinutes":4,"autoAnswer":false}}
            """;
        var config = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)!;

        config.Tx.Should().NotBeNull();
        config.Tx!.RxAudioOffsetHz.Should().Be(1500,
            "missing rxAudioOffsetHz must default to 1500");
        config.Tx!.TxAudioOffsetHz.Should().Be(1500,
            "missing txAudioOffsetHz must default to 1500");
        config.Tx!.HoldTxFreq.Should().BeFalse(
            "missing holdTxFreq must default to false");
    }

    // ── Task 8.2 / 1.3 — New audio offset fields round-trip through JSON ────────────

    [Fact(DisplayName = "Task 8.2: TxConfig with audio offset fields round-trips through JSON serialisation")]
    public void RoundTrip_AudioOffsetFields_PreservesValues()
    {
        var original = new AppConfig() with
        {
            Tx = new TxConfig
            {
                RxAudioOffsetHz = 900,
                TxAudioOffsetHz = 1800,
                HoldTxFreq      = true,
            }
        };

        var json   = JsonSerializer.Serialize(original, ConfigJsonContext.Default.AppConfig);
        var loaded = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)!;

        loaded.Tx.Should().NotBeNull();
        loaded.Tx!.RxAudioOffsetHz.Should().Be(900,  "rxAudioOffsetHz must survive a JSON round-trip");
        loaded.Tx!.TxAudioOffsetHz.Should().Be(1800, "txAudioOffsetHz must survive a JSON round-trip");
        loaded.Tx!.HoldTxFreq.Should().BeTrue(       "holdTxFreq must survive a JSON round-trip");

        json.Should().Contain("\"rxAudioOffsetHz\"", "camelCase key name must be used");
        json.Should().Contain("\"txAudioOffsetHz\"", "camelCase key name must be used");
        json.Should().Contain("\"holdTxFreq\"",      "camelCase key name must be used");
    }
}
