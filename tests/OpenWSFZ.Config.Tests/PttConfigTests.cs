using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Config;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Config.Tests;

/// <summary>
/// Tests for <see cref="PttConfig"/> configuration schema (FR-056, task 2.5).
/// Verifies defaults, round-trip fidelity, the JSON key name contract, and that
/// existing config files without a <c>ptt</c> key deserialise without error to
/// today's VOX-only behaviour.
/// </summary>
[Trait("Category", "Unit")]
public sealed class PttConfigTests
{
    private sealed class TempDirectory : IDisposable
    {
        public string Path { get; } = System.IO.Path.Combine(
            System.IO.Path.GetTempPath(),
            "openwsfz-pttcfg-" + System.IO.Path.GetRandomFileName());

        public TempDirectory() => Directory.CreateDirectory(Path);

        public void Dispose()
        {
            try { Directory.Delete(Path, recursive: true); } catch { /* best-effort */ }
        }
    }

    // ── Scenario: Missing ptt key uses defaults (task 2.5) ────────────────────

    [Fact(DisplayName = "FR-056: AppConfig without ptt key deserialises without error and Ptt.Method is AudioVox")]
    public void Load_MissingPttKey_UsesDefaults()
    {
        const string json = """{"port":8080}""";
        var config = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)!;

        // Direct STJ deserialisation may return null for a non-nullable init property when
        // its key is absent (same source-gen quirk documented for RemoteAccess/DecodeLog/etc.
        // above) — consumers use (config.Ptt ?? new PttConfig()); JsonConfigStore's own
        // null-guard (see below) covers the load path used by the running daemon.
        var effective = config.Ptt ?? new PttConfig();
        effective.Method.Should().Be("AudioVox");
    }

    [Fact(DisplayName = "FR-056: JsonConfigStore null-guard ensures Ptt.Method=AudioVox on old config")]
    public void JsonConfigStore_Load_MissingPttKey_AppliesNullGuard()
    {
        using var dir = new TempDirectory();
        var configPath = System.IO.Path.Combine(dir.Path, "config.json");

        // Write a pre-cat-tx-ptt config file (no ptt key).
        File.WriteAllText(configPath, """{"port":9090}""");

        var store = new JsonConfigStore(configPath);

        store.Current.Ptt.Should().NotBeNull(
            "JsonConfigStore null-guard must produce a non-null Ptt for old config files");
        store.Current.Ptt.Method.Should().Be("AudioVox",
            "missing ptt key must default to Method=AudioVox — today's VOX-only behaviour");
    }

    // ── Scenario: ptt round-trips correctly ───────────────────────────────────

    [Fact(DisplayName = "FR-056: PttConfig round-trips all six fields through JSON serialisation")]
    public void RoundTrip_AllFields_PreservesValues()
    {
        var original = new AppConfig() with
        {
            Ptt = new PttConfig
            {
                Method            = "CatCommand",
                SerialPort        = "COM12",
                SerialLine        = "Dtr",
                LeadTimeMs        = 75,
                TailTimeMs        = 120,
                WatchdogTimeoutMs = 15000,
            }
        };

        var json   = JsonSerializer.Serialize(original, ConfigJsonContext.Default.AppConfig);
        var loaded = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)!;

        loaded.Ptt.Should().NotBeNull();
        loaded.Ptt.Method.Should().Be("CatCommand");
        loaded.Ptt.SerialPort.Should().Be("COM12");
        loaded.Ptt.SerialLine.Should().Be("Dtr");
        loaded.Ptt.LeadTimeMs.Should().Be(75);
        loaded.Ptt.TailTimeMs.Should().Be(120);
        loaded.Ptt.WatchdogTimeoutMs.Should().Be(15000);
    }

    // ── Scenario: JSON key names use camelCase ─────────────────────────────────

    [Fact(DisplayName = "FR-056: PttConfig serialises with camelCase JSON property names")]
    public void Serialise_PttConfig_UsesCamelCase()
    {
        var config = new AppConfig() with { Ptt = new PttConfig() };
        var json   = JsonSerializer.Serialize(config, ConfigJsonContext.Default.AppConfig);

        json.Should().Contain("\"ptt\"");
        json.Should().Contain("\"method\"");
        json.Should().Contain("\"serialPort\"");
        json.Should().Contain("\"serialLine\"");
        json.Should().Contain("\"leadTimeMs\"");
        json.Should().Contain("\"tailTimeMs\"");
        json.Should().Contain("\"watchdogTimeoutMs\"");
    }

    // ── Scenario: Default values ──────────────────────────────────────────────

    [Fact(DisplayName = "FR-056: PttConfig defaults: method=AudioVox, serialLine=Rts, leadTimeMs=50, tailTimeMs=50, watchdogTimeoutMs=20000")]
    public void Defaults_AreCorrect()
    {
        var ptt = new PttConfig();
        ptt.Method.Should().Be("AudioVox");
        ptt.SerialLine.Should().Be("Rts");
        ptt.LeadTimeMs.Should().Be(50);
        ptt.TailTimeMs.Should().Be(50);
        ptt.WatchdogTimeoutMs.Should().Be(20000);
        ptt.SerialPort.Should().NotBeNullOrEmpty();
    }

    // ── Scenario: Partial ptt object loads without error ─────────────────────

    [Fact(DisplayName = "FR-056: Partial ptt JSON (only method present) loads without error")]
    public void Load_PartialPttJson_LoadsWithoutError()
    {
        const string json = """{"ptt":{"method":"SerialRtsDtr"}}""";
        AppConfig? config = null;
        var act = () => config = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig);

        act.Should().NotThrow("a partial ptt object must deserialise without error");
        config!.Ptt.Should().NotBeNull();
        config.Ptt.Method.Should().Be("SerialRtsDtr", "the explicitly-provided method field must be correct");
    }

    [Fact(DisplayName = "FR-056: JsonConfigStore default-config file includes ptt section")]
    public void JsonConfigStore_CreateDefault_IncludesPttSection()
    {
        using var dir = new TempDirectory();
        var configPath = System.IO.Path.Combine(dir.Path, "config.json");

        _ = new JsonConfigStore(configPath);

        File.Exists(configPath).Should().BeTrue("a default config file must be written");

        var text = File.ReadAllText(configPath);
        text.Should().Contain("\"ptt\"", "default config must include ptt key");

        var loaded = JsonSerializer.Deserialize(text, ConfigJsonContext.Default.AppConfig)!;
        var ptt = loaded.Ptt ?? new PttConfig();
        ptt.Method.Should().Be("AudioVox", "default ptt.method must be AudioVox");
    }
}
