using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Config;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Config.Tests;

/// <summary>
/// Regression tests for <see cref="LoggingConfig"/>'s <c>[JsonConstructor]</c> guard
/// (dev-tasks/2026-07-29-fix-loggingconfig-null-rotationschedule-crash.md). Mirrors the
/// missing-key-defaults tests already in place for <see cref="ExternalReportingConfig"/> and
/// <see cref="CycleAudioArchiveConfig"/>.
/// </summary>
[Trait("Category", "Unit")]
public sealed class LoggingConfigTests
{
    // ── Round-trip ────────────────────────────────────────────────────────────

    [Fact(DisplayName = "LoggingConfig with all fields set round-trips via ConfigJsonContext")]
    public void LoggingConfig_RoundTrip_PreservesValues()
    {
        var original = new AppConfig() with
        {
            Logging = new LoggingConfig(
                fileEnabled: true,
                directory: "custom-logs",
                fileLogLevel: "Debug",
                rotationSchedule: "weekly",
                rotationTime: "03:30",
                rotationDayOfWeek: "Sunday",
                maxFiles: 14)
        };

        var json   = JsonSerializer.Serialize(original, ConfigJsonContext.Default.AppConfig);
        var loaded = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)!;

        loaded.Logging.Should().NotBeNull();
        loaded.Logging.FileEnabled.Should().BeTrue();
        loaded.Logging.Directory.Should().Be("custom-logs");
        loaded.Logging.FileLogLevel.Should().Be("Debug");
        loaded.Logging.RotationSchedule.Should().Be("weekly");
        loaded.Logging.RotationTime.Should().Be("03:30");
        loaded.Logging.RotationDayOfWeek.Should().Be("Sunday");
        loaded.Logging.MaxFiles.Should().Be(14);
    }

    // ── Missing-key defaults (the regression this dev-task fixes) ─────────────

    [Fact(DisplayName =
        "Regression: a partial logging object (fileEnabled/directory/fileLogLevel only) " +
        "deserialises rotation fields to their documented defaults, not CLR zero-values")]
    public void Load_PartialLoggingObject_UsesRotationDefaults()
    {
        // The exact hand-edit from dev-tasks/2026-07-29-fix-loggingconfig-null-rotationschedule-crash.md
        // §1: fileEnabled/directory/fileLogLevel set, no rotationSchedule/rotationTime/
        // rotationDayOfWeek/maxFiles keys at all.
        const string json = """
            {"port":8080,"logging":{"fileEnabled":true,"directory":"logs","fileLogLevel":"Debug"}}
            """;
        var config = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)!;

        config.Logging.FileEnabled.Should().BeTrue();
        config.Logging.Directory.Should().Be("logs");
        config.Logging.FileLogLevel.Should().Be("Debug");

        // Before the [JsonConstructor] guard, STJ source generation resolved these omitted keys
        // to null/null/null/0 instead of the class's documented defaults — which in turn crashed
        // LogRotationService.CalculateNextBoundary's switch catch-all (see LogRotationServiceTests
        // regression tests).
        config.Logging.RotationSchedule.Should().Be("daily",
            "an omitted rotationSchedule key must resolve to the documented default, not null");
        config.Logging.RotationTime.Should().Be("00:00",
            "an omitted rotationTime key must resolve to the documented default, not null");
        config.Logging.RotationDayOfWeek.Should().Be("Monday",
            "an omitted rotationDayOfWeek key must resolve to the documented default, not null");
        config.Logging.MaxFiles.Should().Be(7,
            "an omitted maxFiles key must resolve to the documented default, not 0");
    }

    [Fact(DisplayName = "AppConfig without a logging key deserialises to null Logging (guarded separately by JsonConfigStore.Load)")]
    public void Load_MissingLoggingKey_DeserialisesToNull()
    {
        // AppConfig's own "logging" property has no [JsonConstructor] of its own covering the
        // whole-object-absent case — that gap is guarded separately, at the whole-object level,
        // in JsonConfigStore.Load (see the "AppConfig-level guard" test below) and in WebApp.cs's
        // POST /api/v1/config handler, exactly as LoggingConfig's own doc comment describes. A
        // raw JsonSerializer.Deserialize call with no "logging" key at all is expected to leave
        // Logging null; this test exists so a future change to that expectation is deliberate,
        // not accidental.
        const string json = """{"port":8080}""";
        var config = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)!;

        config.Logging.Should().BeNull();
    }

    [Fact(DisplayName = "JsonConfigStore null-guard ensures Logging defaults on a config file with no logging key")]
    public void JsonConfigStore_Load_MissingLoggingKey_AppliesNullGuard()
    {
        var dir = Path.Combine(Path.GetTempPath(), "openwsfz-loggingcfg-" + Path.GetRandomFileName());
        Directory.CreateDirectory(dir);
        try
        {
            var configPath = Path.Combine(dir, "config.json");
            File.WriteAllText(configPath, """{"port":9090}""");

            var store = new JsonConfigStore(configPath);

            store.Current.Logging.Should().NotBeNull();
            store.Current.Logging.FileEnabled.Should().BeFalse();
            store.Current.Logging.RotationSchedule.Should().Be("daily");
            store.Current.Logging.RotationTime.Should().Be("00:00");
            store.Current.Logging.RotationDayOfWeek.Should().Be("Monday");
            store.Current.Logging.MaxFiles.Should().Be(7);
        }
        finally
        {
            try { Directory.Delete(dir, recursive: true); } catch { /* best-effort */ }
        }
    }
}
