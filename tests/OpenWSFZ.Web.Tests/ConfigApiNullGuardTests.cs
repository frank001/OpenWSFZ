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
}
