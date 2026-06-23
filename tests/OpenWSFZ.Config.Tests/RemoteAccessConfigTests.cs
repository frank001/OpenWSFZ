using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Config;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Config.Tests;

/// <summary>
/// Tests for <see cref="RemoteAccessConfig"/> and the <see cref="AppConfig.RemoteAccess"/>
/// property introduced in the lan-remote-access phase.
/// Tasks 7.5 – 7.6.
/// </summary>
[Trait("Category", "Unit")]
public sealed class RemoteAccessConfigTests
{
    // ── Helper ────────────────────────────────────────────────────────────────

    /// <summary>Creates a temporary directory that is deleted when disposed.</summary>
    private sealed class TempDirectory : IDisposable
    {
        public string Path { get; } = System.IO.Path.Combine(
            System.IO.Path.GetTempPath(),
            "openwsfz-racfg-" + System.IO.Path.GetRandomFileName());

        public TempDirectory() => Directory.CreateDirectory(Path);

        public void Dispose()
        {
            try { Directory.Delete(Path, recursive: true); } catch { /* best-effort */ }
        }
    }

    // ── 7.5 — RemoteAccessConfig JSON round-trip ─────────────────────────────

    [Fact(DisplayName = "7.5: RemoteAccessConfig(true, \"test\") round-trips via AppJsonContext")]
    public void RemoteAccessConfig_RoundTrip_PreservesValues()
    {
        var original = new AppConfig() with
        {
            RemoteAccess = new RemoteAccessConfig(enabled: true, passphrase: "test")
        };

        var json   = JsonSerializer.Serialize(original, ConfigJsonContext.Default.AppConfig);
        var loaded = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)!;

        loaded.RemoteAccess.Should().NotBeNull();
        loaded.RemoteAccess.Enabled.Should().BeTrue("Enabled = true must survive a JSON round-trip");
        loaded.RemoteAccess.Passphrase.Should().Be("test", "passphrase must survive a JSON round-trip");

        json.Should().Contain("\"remoteAccess\"",  "camelCase key must be used in JSON");
        json.Should().Contain("\"enabled\"",        "camelCase field must be present");
        json.Should().Contain("\"passphrase\"",     "camelCase field must be present");
    }

    [Fact(DisplayName = "7.5b: RemoteAccessConfig(false, null) serialises with expected keys and defaults")]
    public void RemoteAccessConfig_Defaults_SerialisedCorrectly()
    {
        var config = new AppConfig();

        var json   = JsonSerializer.Serialize(config, ConfigJsonContext.Default.AppConfig);
        var loaded = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)!;

        // Verify the key is present in the wire format.
        json.Should().Contain("\"remoteAccess\"", "remoteAccess key must always be present");
        json.Should().Contain("\"enabled\"",      "enabled field must be serialised");
        json.Should().Contain("\"passphrase\"",   "passphrase field must be serialised");

        // Verify the default values survive a round-trip (avoids whitespace sensitivity).
        var ra = loaded.RemoteAccess ?? new RemoteAccessConfig();
        ra.Enabled.Should().BeFalse("default Enabled must be false");
        ra.Passphrase.Should().BeNull("default Passphrase must be null");
    }

    // ── 7.6 — AppConfig backward-compat: missing remoteAccess key ────────────

    [Fact(DisplayName = "7.6: AppConfig without remoteAccess key deserialises with Enabled=false, Passphrase=null")]
    public void Load_MissingRemoteAccessKey_UsesDefaults()
    {
        const string json = """{"port":8080}""";
        var config = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)!;

        // Without the null-guard in JsonConfigStore.Load, RemoteAccess may be null here
        // because STJ source-gen doesn't call the property initialiser for absent keys.
        // The null-guard test (7.6b) covers the JsonConfigStore path.
        // Direct STJ deserialization may return null; accept either null or default.
        var effective = config.RemoteAccess ?? new RemoteAccessConfig();
        effective.Enabled.Should().BeFalse("absent remoteAccess key must default to Enabled=false");
        effective.Passphrase.Should().BeNull("absent remoteAccess key must default to Passphrase=null");
    }

    [Fact(DisplayName = "7.6b: JsonConfigStore null-guard ensures RemoteAccess.Enabled=false on old config")]
    public void JsonConfigStore_Load_MissingRemoteAccessKey_AppliesNullGuard()
    {
        using var dir = new TempDirectory();
        var configPath = System.IO.Path.Combine(dir.Path, "config.json");

        // Write a pre-LAN-access config file (no remoteAccess key).
        File.WriteAllText(configPath, """{"port":9090}""");

        var store = new JsonConfigStore(configPath);

        store.Current.RemoteAccess.Should().NotBeNull(
            "JsonConfigStore null-guard must produce a non-null RemoteAccess for old config files");
        store.Current.RemoteAccess.Enabled.Should().BeFalse(
            "missing remoteAccess key must default to Enabled=false");
        store.Current.RemoteAccess.Passphrase.Should().BeNull(
            "missing remoteAccess key must default to Passphrase=null");
    }

    [Fact(DisplayName = "7.6c: JsonConfigStore default-config file includes remoteAccess section")]
    public void JsonConfigStore_CreateDefault_IncludesRemoteAccessSection()
    {
        using var dir = new TempDirectory();
        var configPath = System.IO.Path.Combine(dir.Path, "config.json");

        // Store creates the default file on construction when file is absent.
        _ = new JsonConfigStore(configPath);

        File.Exists(configPath).Should().BeTrue("a default config file must be written");

        var text = File.ReadAllText(configPath);
        text.Should().Contain("\"remoteAccess\"",  "default config must include remoteAccess key");
        text.Should().Contain("\"enabled\"",       "enabled field must be present in default config");
        text.Should().Contain("\"passphrase\"",    "passphrase field must be present in default config");

        // Parse to verify the actual default values (avoids whitespace sensitivity from WriteIndented).
        var loaded = JsonSerializer.Deserialize(text, ConfigJsonContext.Default.AppConfig)!;
        var ra = loaded.RemoteAccess ?? new RemoteAccessConfig();
        ra.Enabled.Should().BeFalse("default remoteAccess.enabled must be false");
        ra.Passphrase.Should().BeNull("default remoteAccess.passphrase must be null");
    }

    [Fact(DisplayName = "7.6d: enabled=false with passphrase set deserialises without error")]
    public void Load_EnabledFalseWithPassphrase_LoadsCorrectly()
    {
        const string json = """{"port":8080,"remoteAccess":{"enabled":false,"passphrase":"secret"}}""";
        var config = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)!;

        var ra = config.RemoteAccess ?? new RemoteAccessConfig();
        ra.Enabled.Should().BeFalse("enabled=false must deserialise correctly");
        ra.Passphrase.Should().Be("secret", "passphrase must deserialise even when enabled=false");
    }
}
