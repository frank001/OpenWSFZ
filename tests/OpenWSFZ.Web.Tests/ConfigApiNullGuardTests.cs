using FluentAssertions;
using System.Net;
using System.Text;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Regression tests for D-010: <c>POST /api/v1/config</c> must never persist a
/// <c>null</c> <c>logging</c> or <c>decodeLog</c> section into the live in-memory
/// config, even when the request body omits those keys entirely.
///
/// <para>
/// Payloads here are built as raw JSON strings via <see cref="StringContent"/>,
/// NOT <c>new AppConfig() with {...}</c> — the latter always populates
/// <c>Logging</c>/<c>DecodeLog</c> through the C# property initialisers and would
/// never reproduce the System.Text.Json source-generation quirk where an omitted
/// key deserialises a non-nullable init property to <c>null</c> instead of falling
/// back to its initialiser.
/// </para>
/// </summary>
[Trait("Category", "Integration")]
public sealed class ConfigApiNullGuardTests : IClassFixture<WebTestFactory>
{
    private readonly WebTestFactory _factory;

    public ConfigApiNullGuardTests(WebTestFactory factory) => _factory = factory;

    [Fact(DisplayName = "D-010 AC-1: POST omitting \"decodeLog\" key does not persist a null DecodeLog")]
    public async Task PostConfig_OmittingDecodeLogKey_DoesNotPersistNullDecodeLog()
    {
        var client  = _factory.CreateClient();
        var content = new StringContent(
            """{ "audioDeviceId": "test-device" }""",
            Encoding.UTF8, "application/json");

        var postResp = await client.PostAsync("/api/v1/config", content);
        postResp.StatusCode.Should().Be(HttpStatusCode.OK,
            "a request body omitting decodeLog must still be accepted");

        var getResp = await client.GetAsync("/api/v1/config");
        getResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var json = await getResp.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(json);

        doc.RootElement.TryGetProperty("decodeLog", out var decodeLogElement).Should().BeTrue(
            "GET /api/v1/config must include the decodeLog key");
        decodeLogElement.ValueKind.Should().NotBe(JsonValueKind.Null,
            "a POST body omitting \"decodeLog\" must never leave IConfigStore.Current.DecodeLog null " +
            "(D-010: this null persists and crashes every subsequent AllTxtWriter.AppendAsync call)");

        // Must be default DecodeLogConfig values (Enabled = false), not merely non-null.
        decodeLogElement.GetProperty("enabled").GetBoolean().Should().BeFalse(
            "the recovered DecodeLog must be the default DecodeLogConfig(), i.e. disabled");
    }

    [Fact(DisplayName = "D-010 AC-2: POST omitting \"logging\" key does not persist a null Logging")]
    public async Task PostConfig_OmittingLoggingKey_DoesNotPersistNullLogging()
    {
        var client  = _factory.CreateClient();
        var content = new StringContent(
            """{ "audioDeviceId": "test-device" }""",
            Encoding.UTF8, "application/json");

        var postResp = await client.PostAsync("/api/v1/config", content);
        postResp.StatusCode.Should().Be(HttpStatusCode.OK,
            "a request body omitting logging must still be accepted");

        var getResp = await client.GetAsync("/api/v1/config");
        getResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var json = await getResp.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(json);

        doc.RootElement.TryGetProperty("logging", out var loggingElement).Should().BeTrue(
            "GET /api/v1/config must include the logging key");
        loggingElement.ValueKind.Should().NotBe(JsonValueKind.Null,
            "a POST body omitting \"logging\" must never leave IConfigStore.Current.Logging null");
    }

    [Fact(DisplayName = "D-010-class AC-3: POST omitting \"decodeNoiseSuppression\" key does not persist a null DecodeNoiseSuppression")]
    public async Task PostConfig_OmittingDecodeNoiseSuppressionKey_DoesNotPersistNullDecodeNoiseSuppression()
    {
        var client  = _factory.CreateClient();
        var content = new StringContent(
            """{ "audioDeviceId": "test-device" }""",
            Encoding.UTF8, "application/json");

        var postResp = await client.PostAsync("/api/v1/config", content);
        postResp.StatusCode.Should().Be(HttpStatusCode.OK,
            "a request body omitting decodeNoiseSuppression must still be accepted");

        var getResp = await client.GetAsync("/api/v1/config");
        getResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var json = await getResp.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(json);

        doc.RootElement.TryGetProperty("decodeNoiseSuppression", out var decodeNoiseSuppressionElement)
            .Should().BeTrue("GET /api/v1/config must include the decodeNoiseSuppression key");
        decodeNoiseSuppressionElement.ValueKind.Should().NotBe(JsonValueKind.Null,
            "a POST body omitting \"decodeNoiseSuppression\" must never leave " +
            "IConfigStore.Current.DecodeNoiseSuppression null (this class of bug crashes every " +
            "subsequent DecodeNoiseSuppressionFilter.Apply call in the decode-pump loop before " +
            "AllTxtWriter.AppendAsync is reached)");

        // Must be default DecodeNoiseSuppressionConfig values, not merely non-null.
        decodeNoiseSuppressionElement.GetProperty("suppressUnknownRegion").ValueKind.Should().Be(
            JsonValueKind.Null,
            "the recovered DecodeNoiseSuppression must be the default DecodeNoiseSuppressionConfig(), " +
            "i.e. SuppressUnknownRegion unset");
        decodeNoiseSuppressionElement.GetProperty("suppressSynthetic").GetBoolean().Should().BeTrue(
            "the recovered DecodeNoiseSuppression must be the default DecodeNoiseSuppressionConfig(), " +
            "i.e. SuppressSynthetic = true");
    }

    [Fact(DisplayName = "gridtracker-udp-reporting: POST omitting \"externalReporting\" key does not persist a null ExternalReporting")]
    public async Task PostConfig_OmittingExternalReportingKey_DoesNotPersistNullExternalReporting()
    {
        var client  = _factory.CreateClient();
        var content = new StringContent(
            """{ "audioDeviceId": "test-device" }""",
            Encoding.UTF8, "application/json");

        var postResp = await client.PostAsync("/api/v1/config", content);
        postResp.StatusCode.Should().Be(HttpStatusCode.OK,
            "a request body omitting externalReporting must still be accepted");

        var getResp = await client.GetAsync("/api/v1/config");
        getResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var json = await getResp.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(json);

        doc.RootElement.TryGetProperty("externalReporting", out var extRepElement).Should().BeTrue(
            "GET /api/v1/config must include the externalReporting key");
        extRepElement.ValueKind.Should().NotBe(JsonValueKind.Null,
            "a POST body omitting \"externalReporting\" must never leave " +
            "IConfigStore.Current.ExternalReporting null (this class of bug crashes " +
            "ExternalReportingService.Reconcile, called synchronously from IConfigStore.OnSaved " +
            "on every subsequent POST /api/v1/config)");

        // Must be default ExternalReportingConfig values, not merely non-null.
        extRepElement.GetProperty("enabled").GetBoolean().Should().BeFalse(
            "the recovered ExternalReporting must be the default ExternalReportingConfig(), i.e. disabled");
    }

    [Fact(DisplayName = "cat-tx-ptt AC-1: POST omitting \"ptt\" key does not persist a null Ptt")]
    public async Task PostConfig_OmittingPttKey_DoesNotPersistNullPtt()
    {
        var client  = _factory.CreateClient();
        var content = new StringContent(
            """{ "audioDeviceId": "test-device" }""",
            Encoding.UTF8, "application/json");

        var postResp = await client.PostAsync("/api/v1/config", content);
        postResp.StatusCode.Should().Be(HttpStatusCode.OK,
            "a request body omitting ptt must still be accepted — the Settings page never sends " +
            "a \"ptt\" key at all (design.md Decision 6: no speculative UI), so every ordinary " +
            "Settings-page save must not be rejected");

        var getResp = await client.GetAsync("/api/v1/config");
        getResp.StatusCode.Should().Be(HttpStatusCode.OK);

        var json = await getResp.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(json);

        doc.RootElement.TryGetProperty("ptt", out var pttElement).Should().BeTrue(
            "GET /api/v1/config must include the ptt key");
        pttElement.ValueKind.Should().NotBe(JsonValueKind.Null,
            "a POST body omitting \"ptt\" must never leave IConfigStore.Current.Ptt null " +
            "(silently reverts CAT-command/serial RTS-DTR PTT to VOX with no warning, and risks a " +
            "stuck-key NullReferenceException in CatPttController/SerialRtsDtrPttController.KeyDownAsync " +
            "if a CAT/serial controller is already the active singleton)");

        // Freshly-initialised store: Current.Ptt is still the untouched default at this
        // point, so falling back to it (rather than a hardcoded new PttConfig()) produces
        // the same observable defaults as before. See the AC-2 test below for the case
        // that actually distinguishes the two fallbacks — a previously-persisted non-default
        // Ptt surviving an unrelated save.
        pttElement.GetProperty("method").GetString().Should().Be("AudioVox");
        pttElement.GetProperty("serialLine").GetString().Should().Be("Rts");
        pttElement.GetProperty("leadTimeMs").GetInt32().Should().Be(50);
        pttElement.GetProperty("tailTimeMs").GetInt32().Should().Be(50);
        pttElement.GetProperty("watchdogTimeoutMs").GetInt32().Should().Be(20000);
    }

    [Fact(DisplayName =
        "cat-tx-ptt AC-2: an unrelated Settings-page save does not revert a previously-persisted " +
        "non-default ptt.method back to AudioVox")]
    public async Task PostConfig_UnrelatedSave_PreservesPreviouslyPersistedPtt()
    {
        // This is the actual hardware-acceptance symptom (dev-tasks/2026-07-12-cat-tx-ptt-null-
        // ptt-config-guard.md, "Case A"): a null-guard that falls back to a hardcoded
        // `new PttConfig()` stops the crash but does NOT stop every ordinary Settings-page
        // save — even one that has nothing to do with PTT — from silently discarding an
        // operator's manually-configured "CatCommand"/"SerialRtsDtr" ptt.method, because
        // web/js/settings.js never sends a "ptt" key in the first place. The fix must fall
        // back to the already-persisted IConfigStore.Current.Ptt instead, so an omitted
        // "ptt" key is a true no-op rather than an implicit reset to defaults.
        var client = _factory.CreateClient();

        try
        {
            // Seed a non-default, previously-persisted Ptt section (simulates an operator
            // having configured CAT-command PTT, whether via a prior POST that did include
            // "ptt" or a hand-edited config.json picked up at daemon startup).
            var seedContent = new StringContent(
                """
                {
                  "audioDeviceId": "test-device",
                  "ptt": {
                    "method": "CatCommand",
                    "serialPort": "COM9",
                    "serialLine": "Dtr",
                    "leadTimeMs": 75,
                    "tailTimeMs": 75,
                    "watchdogTimeoutMs": 15000
                  }
                }
                """,
                Encoding.UTF8, "application/json");
            (await client.PostAsync("/api/v1/config", seedContent)).StatusCode
                .Should().Be(HttpStatusCode.OK);

            // Sanity-check the seed actually took.
            var seededJson = await (await client.GetAsync("/api/v1/config")).Content.ReadAsStringAsync();
            using (var seededDoc = JsonDocument.Parse(seededJson))
            {
                seededDoc.RootElement.GetProperty("ptt").GetProperty("method").GetString()
                    .Should().Be("CatCommand", "the seed POST must have taken effect before testing preservation");
            }

            // Now perform an ordinary, unrelated Settings-page save — a real save always
            // omits "ptt" entirely, so this reproduces exactly what web/js/settings.js sends.
            var unrelatedSaveContent = new StringContent(
                """{ "audioDeviceId": "test-device", "showCycleCountdown": true }""",
                Encoding.UTF8, "application/json");
            (await client.PostAsync("/api/v1/config", unrelatedSaveContent)).StatusCode
                .Should().Be(HttpStatusCode.OK);

            var afterJson = await (await client.GetAsync("/api/v1/config")).Content.ReadAsStringAsync();
            using var afterDoc = JsonDocument.Parse(afterJson);
            var pttAfter = afterDoc.RootElement.GetProperty("ptt");

            pttAfter.GetProperty("method").GetString().Should().Be("CatCommand",
                "an unrelated Settings-page save must not silently revert ptt.method to AudioVox " +
                "— this is the exact hardware-acceptance symptom (\"the radio never enables TX\") " +
                "this test guards against");
            pttAfter.GetProperty("serialPort").GetString().Should().Be("COM9");
            pttAfter.GetProperty("serialLine").GetString().Should().Be("Dtr");
            pttAfter.GetProperty("leadTimeMs").GetInt32().Should().Be(75);
            pttAfter.GetProperty("tailTimeMs").GetInt32().Should().Be(75);
            pttAfter.GetProperty("watchdogTimeoutMs").GetInt32().Should().Be(15000);
        }
        finally
        {
            // Restore Current.Ptt to the default before returning control to the shared
            // WebTestFactory (IClassFixture — one instance for this whole test class), so
            // this test's seeded state can never leak into AC-1 or any other test in this
            // class regardless of xUnit's execution order.
            var resetContent = new StringContent(
                """{ "audioDeviceId": "test-device", "ptt": { "method": "AudioVox" } }""",
                Encoding.UTF8, "application/json");
            await client.PostAsync("/api/v1/config", resetContent);
        }
    }
}
