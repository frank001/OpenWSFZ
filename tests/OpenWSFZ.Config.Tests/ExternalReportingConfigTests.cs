using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Config;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Config.Tests;

/// <summary>
/// Tests for <see cref="ExternalReportingConfig"/>/<see cref="ExternalReportingTarget"/> and the
/// <see cref="AppConfig.ExternalReporting"/> property introduced by the
/// gridtracker-udp-reporting change (task 1.4).
/// </summary>
[Trait("Category", "Unit")]
public sealed class ExternalReportingConfigTests
{
    /// <summary>Creates a temporary directory that is deleted when disposed.</summary>
    private sealed class TempDirectory : IDisposable
    {
        public string Path { get; } = System.IO.Path.Combine(
            System.IO.Path.GetTempPath(),
            "openwsfz-extrep-" + System.IO.Path.GetRandomFileName());

        public TempDirectory() => Directory.CreateDirectory(Path);

        public void Dispose()
        {
            try { Directory.Delete(Path, recursive: true); } catch { /* best-effort */ }
        }
    }

    // ── Round-trip ────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-052: ExternalReportingConfig with two targets round-trips via ConfigJsonContext")]
    public void ExternalReportingConfig_RoundTrip_PreservesValues()
    {
        var original = new AppConfig() with
        {
            ExternalReporting = new ExternalReportingConfig(
                enabled: true,
                targets:
                [
                    new ExternalReportingTarget(name: "GridTracker2", host: "127.0.0.1", port: 2237, enabled: true),
                    new ExternalReportingTarget(name: "JTAlert",      host: "127.0.0.1", port: 2238, enabled: false),
                ],
                honourInboundCommands: true,
                restrictExternalRepliesToDecodeFilter: true)
        };

        var json   = JsonSerializer.Serialize(original, ConfigJsonContext.Default.AppConfig);
        var loaded = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)!;

        loaded.ExternalReporting.Should().NotBeNull();
        loaded.ExternalReporting.Enabled.Should().BeTrue();
        loaded.ExternalReporting.HonourInboundCommands.Should().BeTrue();
        loaded.ExternalReporting.RestrictExternalRepliesToDecodeFilter.Should().BeTrue();
        loaded.ExternalReporting.Targets.Should().HaveCount(2);
        loaded.ExternalReporting.Targets[0].Name.Should().Be("GridTracker2");
        loaded.ExternalReporting.Targets[0].Port.Should().Be(2237);
        loaded.ExternalReporting.Targets[1].Enabled.Should().BeFalse();

        json.Should().Contain("\"externalReporting\"");
        json.Should().Contain("\"honourInboundCommands\"");
        json.Should().Contain("\"restrictExternalRepliesToDecodeFilter\"");
    }

    [Fact(DisplayName = "fix-external-reporting-clear-and-reply-filter: missing restrictExternalRepliesToDecodeFilter key on an existing externalReporting object defaults to false")]
    public void Load_MissingRestrictExternalRepliesToDecodeFilterKey_DefaultsFalse()
    {
        const string json = """
            {"port":8080,"externalReporting":{"enabled":true,"targets":[],"honourInboundCommands":true}}
            """;
        var config = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)!;

        config.ExternalReporting.RestrictExternalRepliesToDecodeFilter.Should().BeFalse(
            "a pre-existing config file written before this field existed must preserve the new " +
            "default (external Reply honoured regardless of the decode-panel filter)");
    }

    // ── Missing-key defaults ──────────────────────────────────────────────────

    [Fact(DisplayName = "FR-052: AppConfig without externalReporting key deserialises with fully-inert defaults")]
    public void Load_MissingExternalReportingKey_UsesDefaults()
    {
        const string json = """{"port":8080}""";
        var config = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)!;

        var effective = config.ExternalReporting ?? new ExternalReportingConfig();
        effective.Enabled.Should().BeFalse();
        effective.Targets.Should().BeEmpty();
        effective.HonourInboundCommands.Should().BeFalse();
    }

    [Fact(DisplayName = "JsonConfigStore null-guard ensures ExternalReporting defaults on old config")]
    public void JsonConfigStore_Load_MissingExternalReportingKey_AppliesNullGuard()
    {
        using var dir = new TempDirectory();
        var configPath = System.IO.Path.Combine(dir.Path, "config.json");

        File.WriteAllText(configPath, """{"port":9090}""");

        var store = new JsonConfigStore(configPath);

        store.Current.ExternalReporting.Should().NotBeNull();
        store.Current.ExternalReporting.Enabled.Should().BeFalse();
        store.Current.ExternalReporting.Targets.Should().BeEmpty();
    }

    [Fact(DisplayName = "JsonConfigStore default-config file includes externalReporting section")]
    public void JsonConfigStore_CreateDefault_IncludesExternalReportingSection()
    {
        using var dir = new TempDirectory();
        var configPath = System.IO.Path.Combine(dir.Path, "config.json");

        _ = new JsonConfigStore(configPath);

        File.Exists(configPath).Should().BeTrue();

        var text = File.ReadAllText(configPath);
        text.Should().Contain("\"externalReporting\"");

        var loaded = JsonSerializer.Deserialize(text, ConfigJsonContext.Default.AppConfig)!;
        var extRep = loaded.ExternalReporting ?? new ExternalReportingConfig();
        extRep.Enabled.Should().BeFalse();
        extRep.Targets.Should().BeEmpty();
    }

    [Fact(DisplayName = "A target entry deserialises with correct field values")]
    public void Load_SingleTarget_DeserialisesCorrectly()
    {
        const string json = """
            {"port":8080,"externalReporting":{"enabled":true,"targets":[
                {"name":"GridTracker2","host":"192.168.1.5","port":2237,"enabled":true}
            ],"honourInboundCommands":false}}
            """;
        var config = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)!;

        config.ExternalReporting.Targets.Should().ContainSingle();
        var t = config.ExternalReporting.Targets[0];
        t.Name.Should().Be("GridTracker2");
        t.Host.Should().Be("192.168.1.5");
        t.Port.Should().Be(2237);
        t.Enabled.Should().BeTrue();
    }
}
