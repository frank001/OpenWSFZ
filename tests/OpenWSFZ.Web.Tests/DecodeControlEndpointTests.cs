using FluentAssertions;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Web.Tests;

// FR-017: DecodeControlEndpointTests

/// <summary>
/// Integration tests for <c>POST /api/v1/decode/start</c> and
/// <c>POST /api/v1/decode/stop</c> (FR-017).
///
/// Uses <see cref="AudioConfigFixture"/> (defined in AudioConfigIntegrationTests.cs)
/// — a real Kestrel instance with a controlled <see cref="TestConfigStore"/>.
/// </summary>
public sealed class DecodeControlEndpointTests : IClassFixture<AudioConfigFixture>
{
    private readonly AudioConfigFixture _fixture;
    private readonly HttpClient         _client;

    public DecodeControlEndpointTests(AudioConfigFixture fixture)
    {
        _fixture = fixture;
        _client  = fixture.Client;
    }

    // ── POST /api/v1/decode/stop ──────────────────────────────────────────

    [Fact(DisplayName = "FR-017: POST /api/v1/decode/stop returns 200 and sets DecodingEnabled = false")]
    public async Task PostDecodeStop_ReturnsOk_AndSetsDecodingEnabledFalse()
    {
        // Arrange — start from a known enabled state.
        await _fixture.ConfigStore.SaveAsync(
            new AppConfig(AudioDeviceId: "hw:0,0", DecodingEnabled: true));

        // Act
        var response = await _client.PostAsync("/api/v1/decode/stop", content: null);

        // Assert HTTP 200
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        // Assert response body reflects the updated state
        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.GetProperty("decodingEnabled").GetBoolean()
            .Should().BeFalse("stop endpoint must set DecodingEnabled = false");

        // Assert the store was actually persisted
        _fixture.ConfigStore.Current.DecodingEnabled.Should().BeFalse(
            "the config store must be persisted by the stop endpoint");
    }

    // ── POST /api/v1/decode/start — no device configured ─────────────────

    [Fact(DisplayName = "FR-017: POST /api/v1/decode/start with no device returns 400")]
    public async Task PostDecodeStart_WithNoDevice_ReturnsBadRequest()
    {
        // Arrange — no audio device.
        await _fixture.ConfigStore.SaveAsync(
            new AppConfig(AudioDeviceId: null, DecodingEnabled: false));

        // Act
        var response = await _client.PostAsync("/api/v1/decode/start", content: null);

        // Assert HTTP 400
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest,
            "starting decoding without a device must be rejected");

        // Assert the config was NOT modified
        _fixture.ConfigStore.Current.DecodingEnabled.Should().BeFalse(
            "config must not be mutated when the start request is rejected");
    }

    // ── POST /api/v1/decode/start — device configured ─────────────────────

    [Fact(DisplayName = "FR-017: POST /api/v1/decode/start with device returns 200 and sets DecodingEnabled = true")]
    public async Task PostDecodeStart_WithDevice_ReturnsOk_AndSetsDecodingEnabledTrue()
    {
        // Arrange — device present, decoding currently disabled.
        await _fixture.ConfigStore.SaveAsync(
            new AppConfig(AudioDeviceId: "hw:0,0", DecodingEnabled: false));

        // Act
        var response = await _client.PostAsync("/api/v1/decode/start", content: null);

        // Assert HTTP 200
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        // Assert response body reflects the updated state
        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.GetProperty("decodingEnabled").GetBoolean()
            .Should().BeTrue("start endpoint must set DecodingEnabled = true");

        // Assert the store was actually persisted
        _fixture.ConfigStore.Current.DecodingEnabled.Should().BeTrue(
            "the config store must be persisted by the start endpoint");
    }

    // ── f-005: decode/start and decode/stop responses carry hashTableRejectCount ──

    [Fact(DisplayName = "f-005: POST /api/v1/decode/start and /stop responses each include hashTableRejectCount")]
    public async Task PostDecodeStartAndStop_ResponsesIncludeHashTableRejectCount()
    {
        // decode/start and decode/stop each construct their OWN DaemonStatus in WebApp.cs —
        // separate construction sites from GET /api/v1/status — so a wiring bug in either one
        // specifically would not be caught by the /status test. Assert both independently
        // (f-005-hash-table-saturation-diagnostic, dev-task §3.2 / design.md Risk 1).
        await _fixture.ConfigStore.SaveAsync(
            new AppConfig(AudioDeviceId: "hw:0,0", DecodingEnabled: false));

        var startResponse = await _client.PostAsync("/api/v1/decode/start", content: null);
        startResponse.StatusCode.Should().Be(HttpStatusCode.OK);
        using (var startDoc = JsonDocument.Parse(await startResponse.Content.ReadAsStringAsync()))
        {
            startDoc.RootElement.TryGetProperty("hashTableRejectCount", out var startProp)
                .Should().BeTrue("decode/start response must include hashTableRejectCount (f-005)");
            startProp.GetInt32().Should().BeGreaterThanOrEqualTo(0,
                "the reject count is a non-negative counter, present even at 0");
        }

        var stopResponse = await _client.PostAsync("/api/v1/decode/stop", content: null);
        stopResponse.StatusCode.Should().Be(HttpStatusCode.OK);
        using (var stopDoc = JsonDocument.Parse(await stopResponse.Content.ReadAsStringAsync()))
        {
            stopDoc.RootElement.TryGetProperty("hashTableRejectCount", out var stopProp)
                .Should().BeTrue("decode/stop response must include hashTableRejectCount (f-005)");
            stopProp.GetInt32().Should().BeGreaterThanOrEqualTo(0,
                "the reject count is a non-negative counter, present even at 0");
        }
    }

    // ── GET /api/v1/status reflects DecodingEnabled ───────────────────────

    [Fact(DisplayName = "FR-017: GET /api/v1/status reflects DecodingEnabled from config")]
    public async Task GetStatus_ReflectsDecodingEnabled()
    {
        // Arrange — explicitly set decoding disabled.
        await _fixture.ConfigStore.SaveAsync(
            new AppConfig(AudioDeviceId: "hw:0,0", DecodingEnabled: false));

        // Act
        var response = await _client.GetAsync("/api/v1/status");

        // Assert HTTP 200
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        // Assert the decodingEnabled field is present and correct
        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.TryGetProperty("decodingEnabled", out var prop)
            .Should().BeTrue("status response must include decodingEnabled field (FR-017)");
        prop.GetBoolean()
            .Should().BeFalse("decodingEnabled must reflect the persisted config value");
    }
}
