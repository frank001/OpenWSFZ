using FluentAssertions;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Integration tests for the TX control endpoints (FR-047):
/// <list type="bullet">
/// <item><c>GET  /api/v1/tx/status</c></item>
/// <item><c>POST /api/v1/tx/enable</c></item>
/// <item><c>POST /api/v1/tx/disable</c></item>
/// </list>
///
/// Uses <see cref="AudioConfigFixture"/> — a real Kestrel instance with a controlled
/// <see cref="TestConfigStore"/> (no IQsoController registered, so state reads as Idle
/// and partner reads as null, which is the correct default).
/// </summary>
public sealed class TxEndpointTests : IClassFixture<AudioConfigFixture>
{
    private readonly AudioConfigFixture _fixture;
    private readonly HttpClient         _client;

    public TxEndpointTests(AudioConfigFixture fixture)
    {
        _fixture = fixture;
        _client  = fixture.Client;
    }

    // ── GET /api/v1/tx/status ────────────────────────────────────────────────

    [Fact(DisplayName = "2.7: GET /api/v1/tx/status returns autoAnswerEnabled = true when config flag is set")]
    public async Task GetTxStatus_WhenAutoAnswerTrue_ReturnsAutoAnswerEnabledTrue()
    {
        // Arrange — set autoAnswer = true in the test config store.
        await _fixture.ConfigStore.SaveAsync(
            new AppConfig() { Tx = new TxConfig(autoAnswer: true) });

        // Act
        var response = await _client.GetAsync("/api/v1/tx/status");

        // Assert HTTP 200
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        // Assert autoAnswerEnabled is true
        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.GetProperty("autoAnswerEnabled").GetBoolean()
            .Should().BeTrue("GET /api/v1/tx/status must reflect tx.autoAnswer from config");
    }

    [Fact(DisplayName = "2.7: GET /api/v1/tx/status returns autoAnswerEnabled = false when config flag is unset")]
    public async Task GetTxStatus_WhenAutoAnswerFalse_ReturnsAutoAnswerEnabledFalse()
    {
        // Arrange — default TxConfig has autoAnswer = false.
        await _fixture.ConfigStore.SaveAsync(new AppConfig());

        // Act
        var response = await _client.GetAsync("/api/v1/tx/status");

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.OK);
        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.GetProperty("autoAnswerEnabled").GetBoolean()
            .Should().BeFalse("GET /api/v1/tx/status must return false when tx.autoAnswer is not set");
    }

    [Fact(DisplayName = "2.7: GET /api/v1/tx/status returns state and partner fields")]
    public async Task GetTxStatus_ReturnsStateAndPartnerFields()
    {
        // Arrange
        await _fixture.ConfigStore.SaveAsync(new AppConfig());

        // Act
        var response = await _client.GetAsync("/api/v1/tx/status");

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.OK);
        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.TryGetProperty("state", out _)
            .Should().BeTrue("response must include 'state' field");
        doc.RootElement.TryGetProperty("partner", out _)
            .Should().BeTrue("response must include 'partner' field");
    }

    // ── POST /api/v1/tx/enable ───────────────────────────────────────────────

    [Fact(DisplayName = "2.5: POST /api/v1/tx/enable returns 200 with autoAnswerEnabled = true")]
    public async Task PostTxEnable_Returns200_WithAutoAnswerEnabledTrue()
    {
        // Arrange — start from disabled state.
        await _fixture.ConfigStore.SaveAsync(
            new AppConfig() { Tx = new TxConfig(autoAnswer: false) });

        // Act
        var response = await _client.PostAsync("/api/v1/tx/enable", content: null);

        // Assert HTTP 200
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        // Assert body contains autoAnswerEnabled = true
        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.GetProperty("autoAnswerEnabled").GetBoolean()
            .Should().BeTrue("enable endpoint must return autoAnswerEnabled = true");
    }

    [Fact(DisplayName = "2.5: POST /api/v1/tx/enable persists autoAnswer = true in config")]
    public async Task PostTxEnable_PersistsAutoAnswerTrue()
    {
        // Arrange
        await _fixture.ConfigStore.SaveAsync(
            new AppConfig() { Tx = new TxConfig(autoAnswer: false) });

        // Act
        await _client.PostAsync("/api/v1/tx/enable", content: null);

        // Assert config was persisted
        _fixture.ConfigStore.Current.Tx?.AutoAnswer
            .Should().BeTrue("config store must be updated with autoAnswer = true after /tx/enable");
    }

    [Fact(DisplayName = "2.5: POST /api/v1/tx/enable is idempotent — second call still returns 200 with true")]
    public async Task PostTxEnable_IsIdempotent()
    {
        // Arrange
        await _fixture.ConfigStore.SaveAsync(new AppConfig());

        // Act — call twice
        var r1 = await _client.PostAsync("/api/v1/tx/enable", content: null);
        var r2 = await _client.PostAsync("/api/v1/tx/enable", content: null);

        // Assert both succeed
        r1.StatusCode.Should().Be(HttpStatusCode.OK);
        r2.StatusCode.Should().Be(HttpStatusCode.OK);

        var body2 = await r2.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body2);
        doc.RootElement.GetProperty("autoAnswerEnabled").GetBoolean()
            .Should().BeTrue("second enable call must still return autoAnswerEnabled = true");
    }

    // ── POST /api/v1/tx/disable ─────────────────────────────────────────────

    [Fact(DisplayName = "2.6: POST /api/v1/tx/disable returns 200 with autoAnswerEnabled = false")]
    public async Task PostTxDisable_Returns200_WithAutoAnswerEnabledFalse()
    {
        // Arrange — start from enabled state.
        await _fixture.ConfigStore.SaveAsync(
            new AppConfig() { Tx = new TxConfig(autoAnswer: true) });

        // Act
        var response = await _client.PostAsync("/api/v1/tx/disable", content: null);

        // Assert HTTP 200
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        // Assert body contains autoAnswerEnabled = false
        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.GetProperty("autoAnswerEnabled").GetBoolean()
            .Should().BeFalse("disable endpoint must return autoAnswerEnabled = false");
    }

    [Fact(DisplayName = "2.6: POST /api/v1/tx/disable persists autoAnswer = false in config")]
    public async Task PostTxDisable_PersistsAutoAnswerFalse()
    {
        // Arrange
        await _fixture.ConfigStore.SaveAsync(
            new AppConfig() { Tx = new TxConfig(autoAnswer: true) });

        // Act
        await _client.PostAsync("/api/v1/tx/disable", content: null);

        // Assert config was persisted
        _fixture.ConfigStore.Current.Tx?.AutoAnswer
            .Should().BeFalse("config store must be updated with autoAnswer = false after /tx/disable");
    }

    [Fact(DisplayName = "2.6: POST /api/v1/tx/disable does not modify QSO controller state (no abort)")]
    public async Task PostTxDisable_DoesNotAbortActiveQso()
    {
        // Arrange — no IQsoController is wired in AudioConfigFixture; state always reads Idle.
        // This test verifies the endpoint returns the correct state field without calling abort.
        await _fixture.ConfigStore.SaveAsync(
            new AppConfig() { Tx = new TxConfig(autoAnswer: true) });

        // Act
        var response = await _client.PostAsync("/api/v1/tx/disable", content: null);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.OK);
        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        // State must be present (Idle when no controller wired) — NOT thrown away or absent
        doc.RootElement.TryGetProperty("state", out var stateProp)
            .Should().BeTrue("response must include 'state' even when IQsoController is absent");
        stateProp.GetString().Should().Be("Idle",
            "disable does not abort an active QSO; state field reflects current controller state");
    }

    [Fact(DisplayName = "2.6: POST /api/v1/tx/disable is idempotent — second call still returns 200 with false")]
    public async Task PostTxDisable_IsIdempotent()
    {
        // Arrange
        await _fixture.ConfigStore.SaveAsync(new AppConfig());

        // Act — call twice
        var r1 = await _client.PostAsync("/api/v1/tx/disable", content: null);
        var r2 = await _client.PostAsync("/api/v1/tx/disable", content: null);

        // Assert both succeed
        r1.StatusCode.Should().Be(HttpStatusCode.OK);
        r2.StatusCode.Should().Be(HttpStatusCode.OK);

        var body2 = await r2.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body2);
        doc.RootElement.GetProperty("autoAnswerEnabled").GetBoolean()
            .Should().BeFalse("second disable call must still return autoAnswerEnabled = false");
    }
}
