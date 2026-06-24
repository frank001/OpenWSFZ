using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Config;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Config.Tests;

/// <summary>
/// Tests for <see cref="DecoderConfig"/> and the <see cref="AppConfig.Decoder"/>
/// property introduced in the decoder-settings-page phase.
/// Tasks 7.1.
/// </summary>
[Trait("Category", "Unit")]
public sealed class DecoderConfigTests
{
    // ── 7.1a — DecoderConfig JSON round-trip ─────────────────────────────────

    [Fact(DisplayName = "7.1a: DecoderConfig(k=15, corr=0.20f, nhard=70) round-trips via ConfigJsonContext")]
    public void DecoderConfig_RoundTrip_PreservesValues()
    {
        var original = new AppConfig() with
        {
            Decoder = new DecoderConfig(kMinScorePass2: 15, osdCorrThreshold: 0.20f, osdNhardMax: 70)
        };

        var json   = JsonSerializer.Serialize(original, ConfigJsonContext.Default.AppConfig);
        var loaded = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)!;

        loaded.Decoder.Should().NotBeNull();
        loaded.Decoder!.KMinScorePass2  .Should().Be(15,    "KMinScorePass2 = 15 must survive a JSON round-trip");
        loaded.Decoder!.OsdCorrThreshold.Should().BeApproximately(0.20f, 1e-6f, "OsdCorrThreshold = 0.20 must survive a JSON round-trip");
        loaded.Decoder!.OsdNhardMax     .Should().Be(70,    "OsdNhardMax = 70 must survive a JSON round-trip");

        json.Should().Contain("\"decoder\"",           "camelCase key must be used in JSON");
        json.Should().Contain("\"kMinScorePass2\"",    "camelCase field must be present");
        json.Should().Contain("\"osdCorrThreshold\"",  "camelCase field must be present");
        json.Should().Contain("\"osdNhardMax\"",       "camelCase field must be present");
    }

    // ── 7.1b — Missing-field defaults via [JsonConstructor] path ────────────

    [Fact(DisplayName = "7.1b: Deserialising '{}' produces D-009 calibrated defaults (kMinScorePass2=10, osdCorrThreshold=0.10, osdNhardMax=60)")]
    public void DecoderConfig_EmptyJson_YieldsCalibRatedDefaults()
    {
        // STJ source-gen ignores C# init-property defaults for absent JSON fields.
        // Lesson 6 pattern: [JsonConstructor] with parameter defaults is the authoritative fix.
        const string emptyDecoder = """{"decoder":{}}""";

        var config = JsonSerializer.Deserialize(emptyDecoder, ConfigJsonContext.Default.AppConfig)!;
        var dec    = config.Decoder ?? new DecoderConfig();

        dec.KMinScorePass2  .Should().Be(10,   "empty decoder object must default kMinScorePass2 to 10 (D-009)");
        dec.OsdCorrThreshold.Should().BeApproximately(0.10f, 1e-6f, "empty decoder object must default osdCorrThreshold to 0.10 (D-009)");
        dec.OsdNhardMax     .Should().Be(60,   "empty decoder object must default osdNhardMax to 60 (D-009)");
    }

    // ── 7.1c — AppConfig backward-compat: missing decoder key ───────────────

    [Fact(DisplayName = "7.1c: AppConfig without decoder key deserialises with Decoder=null → effective defaults")]
    public void Load_MissingDecoderKey_UsesEffectiveDefaults()
    {
        const string json = """{"port":8080}""";
        var config = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)!;

        // Decoder is intentionally nullable; absent key → null.
        // Consumers use (config.Decoder ?? new DecoderConfig()) to get non-null.
        var effective = config.Decoder ?? new DecoderConfig();
        effective.KMinScorePass2  .Should().Be(10,   "absent decoder key → effective kMinScorePass2 = 10");
        effective.OsdCorrThreshold.Should().BeApproximately(0.10f, 1e-6f, "absent decoder key → effective osdCorrThreshold = 0.10");
        effective.OsdNhardMax     .Should().Be(60,   "absent decoder key → effective osdNhardMax = 60");
    }

    // ── 7.1d — JsonConfigStore default-config file includes decoder section ──

    [Fact(DisplayName = "7.1d: JsonConfigStore.CreateDefault includes decoder section with calibrated defaults")]
    public void JsonConfigStore_CreateDefault_IncludesDecoderSection()
    {
        using var dir = new TempDecoderDirectory();
        var configPath = System.IO.Path.Combine(dir.Path, "config.json");

        // Store creates the default file on construction when file is absent.
        _ = new JsonConfigStore(configPath);

        File.Exists(configPath).Should().BeTrue("a default config file must be written");

        var text = File.ReadAllText(configPath);
        text.Should().Contain("\"decoder\"",           "default config must include decoder key");
        text.Should().Contain("\"kMinScorePass2\"",    "kMinScorePass2 field must be present in default config");
        text.Should().Contain("\"osdCorrThreshold\"",  "osdCorrThreshold field must be present in default config");
        text.Should().Contain("\"osdNhardMax\"",       "osdNhardMax field must be present in default config");

        var loaded = JsonSerializer.Deserialize(text, ConfigJsonContext.Default.AppConfig)!;
        var dec    = loaded.Decoder ?? new DecoderConfig();
        dec.KMinScorePass2  .Should().Be(10,   "default decoder.kMinScorePass2 must be 10");
        dec.OsdCorrThreshold.Should().BeApproximately(0.10f, 1e-6f, "default decoder.osdCorrThreshold must be 0.10");
        dec.OsdNhardMax     .Should().Be(60,   "default decoder.osdNhardMax must be 60");
    }

    // ── Helper ────────────────────────────────────────────────────────────────

    /// <summary>Creates a temporary directory that is deleted when disposed.</summary>
    private sealed class TempDecoderDirectory : IDisposable
    {
        public string Path { get; } = System.IO.Path.Combine(
            System.IO.Path.GetTempPath(),
            "openwsfz-deccfg-" + System.IO.Path.GetRandomFileName());

        public TempDecoderDirectory() => Directory.CreateDirectory(Path);

        public void Dispose()
        {
            try { Directory.Delete(Path, recursive: true); } catch { /* best-effort */ }
        }
    }
}
