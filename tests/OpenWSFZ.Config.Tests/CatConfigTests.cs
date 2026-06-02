using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Config;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Config.Tests;

/// <summary>
/// Tests for <see cref="CatConfig"/> configuration schema (FR-031).
/// Verifies defaults, round-trip fidelity, and the JSON key name contract.
/// </summary>
[Trait("Category", "Unit")]
public sealed class CatConfigTests
{
    // ── Scenario: Missing cat key uses defaults ────────────────────────────────

    [Fact(DisplayName = "P16-Cat: AppConfig without cat key deserialises with Cat = null (disabled)")]
    public void Load_MissingCatKey_CatIsNull()
    {
        const string json = """{"port":8080}""";
        var config = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)!;

        config.Cat.Should().BeNull("absent cat key should produce null, treated as disabled");
        // Consumers use (config.Cat ?? new CatConfig()) to get a non-null default.
        var effective = config.Cat ?? new CatConfig();
        effective.Enabled.Should().BeFalse();
    }

    // ── Scenario: cat round-trips correctly ───────────────────────────────────

    [Fact(DisplayName = "P16-Cat: CatConfig round-trips all seven fields through JSON serialisation")]
    public void RoundTrip_AllFields_PreservesValues()
    {
        var original = new AppConfig() with
        {
            Cat = new CatConfig
            {
                Enabled             = true,
                RigModel            = "RigCtld",
                SerialPort          = "COM9",
                BaudRate            = 4800,
                RigctldHost         = "192.168.1.10",
                RigctldPort         = 1234,
                PollIntervalSeconds = 5,
            }
        };

        var json   = JsonSerializer.Serialize(original, ConfigJsonContext.Default.AppConfig);
        var loaded = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)!;

        loaded.Cat.Should().NotBeNull();
        loaded.Cat!.Enabled.Should().BeTrue();
        loaded.Cat.RigModel.Should().Be("RigCtld");
        loaded.Cat.SerialPort.Should().Be("COM9");
        loaded.Cat.BaudRate.Should().Be(4800);
        loaded.Cat.RigctldHost.Should().Be("192.168.1.10");
        loaded.Cat.RigctldPort.Should().Be(1234);
        loaded.Cat.PollIntervalSeconds.Should().Be(5);
    }

    // ── Scenario: JSON key names use camelCase ─────────────────────────────────

    [Fact(DisplayName = "P16-Cat: CatConfig serialises with camelCase JSON property names")]
    public void Serialise_CatConfig_UsesCamelCase()
    {
        var config = new AppConfig() with { Cat = new CatConfig { Enabled = false } };
        var json   = JsonSerializer.Serialize(config, ConfigJsonContext.Default.AppConfig);

        json.Should().Contain("\"cat\"");
        json.Should().Contain("\"enabled\"");
        json.Should().Contain("\"rigModel\"");
        json.Should().Contain("\"serialPort\"");
        json.Should().Contain("\"baudRate\"");
        json.Should().Contain("\"rigctldHost\"");
        json.Should().Contain("\"rigctldPort\"");
        json.Should().Contain("\"pollIntervalSeconds\"");
    }

    // ── Scenario: Default values ──────────────────────────────────────────────

    [Fact(DisplayName = "P16-Cat: CatConfig defaults: enabled=false, rigModel=SerialCat, baudRate=9600, rigctldHost=127.0.0.1, rigctldPort=4532, pollIntervalSeconds=1")]
    public void Defaults_AreCorrect()
    {
        var cat = new CatConfig();
        cat.Enabled.Should().BeFalse();
        cat.RigModel.Should().Be("SerialCat");
        cat.BaudRate.Should().Be(9600);
        cat.RigctldHost.Should().Be("127.0.0.1");
        cat.RigctldPort.Should().Be(4532);
        cat.PollIntervalSeconds.Should().Be(1);
    }

    // ── Scenario: Partial cat object loads without error ─────────────────────

    [Fact(DisplayName = "P16-Cat: Partial cat JSON (only enabled present) loads without error and sets enabled correctly")]
    public void Load_PartialCatJson_LoadsWithoutError()
    {
        // STJ source-generation does NOT call record property initializers for missing JSON
        // keys — missing numeric fields receive the type default (0), missing strings receive
        // null. The spec requirement is "loads without error" (no exception thrown) and that
        // the explicitly-provided field is correctly parsed. CatPollingService handles zero/null
        // field values gracefully at runtime via its clamping and error-handling logic.
        const string json = """{"cat":{"enabled":true}}""";
        AppConfig? config = null;
        var act = () => config = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig);

        act.Should().NotThrow("a partial cat object must deserialise without error");
        config!.Cat.Should().NotBeNull();
        config.Cat!.Enabled.Should().BeTrue("the explicitly-provided enabled field must be correct");
    }
}
