using FluentAssertions;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using Microsoft.Extensions.DependencyInjection;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Text;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Web.Tests;

// ── Mock IQsoController for answer-cq endpoint tests ─────────────────────

/// <summary>
/// Controllable <see cref="IQsoController"/> stub for web-layer integration tests.
/// State and Partner are settable so tests can exercise both Idle and non-Idle paths.
/// </summary>
internal sealed class MockQsoController : IQsoController
{
    public QsoState State   { get; set; } = QsoState.Idle;
    public string?  Partner { get; set; }
    public QsoRole  Role    { get; set; } = QsoRole.Answerer;

    /// <summary>
    /// fix-tx-transcript-real-message (TX-D05): settable so tests can confirm
    /// <c>IQsoController.LastTxMessage</c> is threaded through into the various
    /// <c>TxStatusResponse</c>-returning endpoints. Defaults to null (nothing
    /// transmitted yet), matching <see cref="IQsoController.LastTxMessage"/>'s own default.
    /// </summary>
    public string? LastTxMessage { get; set; }

    /// <summary>
    /// Number of times <see cref="GracefulStopAsync"/> has been called
    /// (f-004-operator-visibility-improvements — POST /api/v1/tx/stop-cq tests).
    /// </summary>
    public int GracefulStopCallCount { get; private set; }

    public Task AbortAsync(CancellationToken ct = default) => Task.CompletedTask;

    public Task GracefulStopAsync(CancellationToken ct = default)
    {
        GracefulStopCallCount++;
        return Task.CompletedTask;
    }

    public Task AnswerCqAsync(
        string callsign, double frequencyHz, DateTimeOffset cqCycleStart, CancellationToken ct)
        => Task.CompletedTask;

    public Task SelectResponderAsync(
        string callsign, double frequencyHz, DateTimeOffset responseCycleStart, CancellationToken ct)
        => Task.CompletedTask;

    public Task EngageAtAsync(
        string partnerCallsign, double frequencyHz, DateTimeOffset theirCycleStart,
        EngagePoint point, string rawPayload, int snr, CancellationToken ct)
        => Task.CompletedTask;
}

/// <summary>
/// Fixture that wires a <see cref="MockQsoController"/> into a live Kestrel instance
/// so that <c>POST /api/v1/tx/answer-cq</c> endpoint tests can control the
/// controller's <see cref="QsoState"/>.
/// </summary>
public sealed class TxAnswerCqFixture : IAsyncLifetime
{
    internal readonly TestConfigStore    ConfigStore    = new();
    internal readonly MockQsoController  QsoController  = new();

    private Microsoft.AspNetCore.Builder.WebApplication? _app;
    public  HttpClient Client { get; private set; } = null!;

    public async Task InitializeAsync()
    {
        _app = WebApp.Create(
            port:              0,
            configStore:       ConfigStore,
            configureServices: services =>
                services.AddSingleton<IQsoController>(QsoController));

        await _app.StartAsync();

        var addr = _app.Services
            .GetRequiredService<IServer>()
            .Features.Get<IServerAddressesFeature>()!
            .Addresses.First();

        Client = new HttpClient { BaseAddress = new Uri($"http://127.0.0.1:{new Uri(addr).Port}") };
    }

    public async Task DisposeAsync()
    {
        Client.Dispose();
        if (_app is not null)
        {
            await _app.StopAsync();
            await _app.DisposeAsync();
        }
    }
}

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

    // ── POST /api/v1/tx/abort ────────────────────────────────────────────────

    [Fact(DisplayName = "D-TX-UI-001: POST /api/v1/tx/abort returns 200 JSON body with autoAnswerEnabled = false")]
    public async Task TxAbort_ReturnsJsonBodyWithAutoAnswerEnabledFalse()
    {
        // Arrange — arm TX first.
        await _fixture.ConfigStore.SaveAsync(
            new AppConfig() { Tx = new TxConfig(autoAnswer: true) });

        // Act
        var response = await _client.PostAsync("/api/v1/tx/abort", content: null);

        // Assert HTTP 200
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        // Assert body contains autoAnswerEnabled = false
        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.GetProperty("autoAnswerEnabled").GetBoolean()
            .Should().BeFalse("abort endpoint must return autoAnswerEnabled = false");

        // Assert config was persisted as disarmed
        _fixture.ConfigStore.Current.Tx?.AutoAnswer
            .Should().BeFalse("abort endpoint must persist autoAnswer = false in config");
    }
}

// ── POST /api/v1/tx/answer-cq tests ─────────────────────────────────────────

/// <summary>
/// Integration tests for <c>POST /api/v1/tx/answer-cq</c> (TX-D01).
/// Uses <see cref="TxAnswerCqFixture"/> which wires a <see cref="MockQsoController"/>
/// so the test can control the controller's <see cref="QsoState"/>.
/// NFR-021: all example callsigns use Q-prefix.
/// </summary>
public sealed class TxAnswerCqEndpointTests : IClassFixture<TxAnswerCqFixture>
{
    private readonly TxAnswerCqFixture _fixture;
    private readonly HttpClient        _client;

    public TxAnswerCqEndpointTests(TxAnswerCqFixture fixture)
    {
        _fixture = fixture;
        _client  = fixture.Client;
    }

    private static StringContent JsonBody(string json)
        => new(json, Encoding.UTF8, "application/json");

    private const string ValidBody =
        """{"callsign":"Q1TST","frequencyHz":897.0,"cqCycleStartUtc":"2026-06-22T17:29:15Z"}""";

    // ── Test 7: 200 when Idle ────────────────────────────────────────────────

    [Fact(DisplayName = "7: POST /api/v1/tx/answer-cq returns 200 with autoAnswerEnabled=true when Idle")]
    public async Task PostTxAnswerCq_WhenIdle_Returns200WithAutoAnswerEnabledTrue()
    {
        // Arrange
        _fixture.QsoController.State = QsoState.Idle;

        // Act
        var response = await _client.PostAsync("/api/v1/tx/answer-cq", JsonBody(ValidBody));

        // Assert HTTP 200
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        // Assert body contains autoAnswerEnabled = true
        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.GetProperty("autoAnswerEnabled").GetBoolean()
            .Should().BeTrue("answer-cq endpoint must return autoAnswerEnabled = true on success");

        // Assert 'state' and 'partner' fields are present
        doc.RootElement.TryGetProperty("state",   out _).Should().BeTrue();
        doc.RootElement.TryGetProperty("partner", out _).Should().BeTrue();
    }

    // ── Test 8: 409 when not Idle ────────────────────────────────────────────

    [Fact(DisplayName = "8: POST /api/v1/tx/answer-cq returns 409 Conflict when TX is not Idle")]
    public async Task PostTxAnswerCq_WhenNotIdle_Returns409()
    {
        // Arrange — simulate an active QSO
        _fixture.QsoController.State = QsoState.WaitReport;

        // Act
        var response = await _client.PostAsync("/api/v1/tx/answer-cq", JsonBody(ValidBody));

        // Assert HTTP 409 Conflict
        response.StatusCode.Should().Be(HttpStatusCode.Conflict,
            "answer-cq must refuse with 409 when the controller is not in Idle state");

        // Restore Idle so subsequent tests in this fixture are unaffected.
        _fixture.QsoController.State = QsoState.Idle;
    }

    // ── 5.16: role field in GET /tx/status ───────────────────────────────────

    [Fact(DisplayName = "5.16a: GET /api/v1/tx/status returns role='answerer' when answerer is active")]
    public async Task GetTxStatus_WhenAnswererRole_ReturnsRoleAnswerer()
    {
        _fixture.QsoController.Role  = QsoRole.Answerer;
        _fixture.QsoController.State = QsoState.Idle;

        var response = await _client.GetAsync("/api/v1/tx/status");
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.GetProperty("role").GetString()
            .Should().Be("answerer");
    }

    [Fact(DisplayName = "5.16b: GET /api/v1/tx/status returns role='caller' when caller is active")]
    public async Task GetTxStatus_WhenCallerRole_ReturnsRoleCaller()
    {
        _fixture.QsoController.Role  = QsoRole.Caller;
        _fixture.QsoController.State = QsoState.WaitReport; // simulates WaitAnswer

        var response = await _client.GetAsync("/api/v1/tx/status");
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.GetProperty("role").GetString()
            .Should().Be("caller");

        // Restore defaults for other tests.
        _fixture.QsoController.Role  = QsoRole.Answerer;
        _fixture.QsoController.State = QsoState.Idle;
    }

    // ── fix-tx-transcript-real-message (TX-D05): lastTxMessage field ─────────

    [Fact(DisplayName = "TX-D05: GET /api/v1/tx/status includes lastTxMessage reflecting the active controller's value")]
    public async Task GetTxStatus_ReturnsLastTxMessage_ReflectingActiveController()
    {
        _fixture.QsoController.LastTxMessage = "Q1TST Q1OFZ -05";

        var response = await _client.GetAsync("/api/v1/tx/status");
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.GetProperty("lastTxMessage").GetString()
            .Should().Be("Q1TST Q1OFZ -05");

        // Restore default for other tests.
        _fixture.QsoController.LastTxMessage = null;
    }

    [Fact(DisplayName = "TX-D05: GET /api/v1/tx/status omits/nulls lastTxMessage when nothing has been transmitted yet")]
    public async Task GetTxStatus_ReturnsNullLastTxMessage_WhenNothingTransmittedYet()
    {
        _fixture.QsoController.LastTxMessage = null;

        var response = await _client.GetAsync("/api/v1/tx/status");
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        var prop = doc.RootElement.GetProperty("lastTxMessage");
        prop.ValueKind.Should().Be(JsonValueKind.Null,
            "TxStatusResponse.LastTxMessage has no [JsonIgnore(WhenWritingNull)] like WsTxStateMessage — it is always present, null when unset");
    }
}

/// <summary>
/// Integration tests for POST /api/v1/tx/select-responder (5.15).
/// Uses a dedicated <see cref="TxAnswerCqFixture"/> so the mock controller's Role
/// and State can be set independently per test.
/// </summary>
[Collection("select-responder-tests")]
public sealed class SelectResponderEndpointTests : IClassFixture<TxAnswerCqFixture>
{
    private readonly TxAnswerCqFixture _fixture;

    public SelectResponderEndpointTests(TxAnswerCqFixture fixture)
        => _fixture = fixture;

    private static StringContent SelectResponderBody(
        string callsign = "Q1TST",
        double freqHz   = 1500.0,
        string cycleStart = "2026-06-25T14:29:15Z")
        => new(
            $$$"""{"callsign":"{{{callsign}}}","frequencyHz":{{{freqHz}}},"responseCycleStartUtc":"{{{cycleStart}}}"}""",
            System.Text.Encoding.UTF8, "application/json");

    [Fact(DisplayName = "5.15a: POST /tx/select-responder returns 200 when Caller role and WaitAnswer")]
    public async Task SelectResponder_CallerWaitAnswer_Returns200()
    {
        _fixture.QsoController.Role  = QsoRole.Caller;
        _fixture.QsoController.State = QsoState.WaitReport; // WaitAnswer proxy

        var response = await _fixture.Client.PostAsync(
            "/api/v1/tx/select-responder", SelectResponderBody());

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.GetProperty("role").GetString().Should().Be("caller");
    }

    [Fact(DisplayName = "5.15b: POST /tx/select-responder returns 405 when Answerer role")]
    public async Task SelectResponder_AnswererRole_Returns405()
    {
        _fixture.QsoController.Role  = QsoRole.Answerer;
        _fixture.QsoController.State = QsoState.WaitReport;

        var response = await _fixture.Client.PostAsync(
            "/api/v1/tx/select-responder", SelectResponderBody());

        ((int)response.StatusCode).Should().Be(405);
    }

    [Fact(DisplayName = "5.15c: POST /tx/select-responder returns 409 when Caller but not WaitAnswer")]
    public async Task SelectResponder_CallerNotWaitAnswer_Returns409()
    {
        _fixture.QsoController.Role  = QsoRole.Caller;
        _fixture.QsoController.State = QsoState.Idle; // not WaitAnswer

        var response = await _fixture.Client.PostAsync(
            "/api/v1/tx/select-responder", SelectResponderBody());

        response.StatusCode.Should().Be(HttpStatusCode.Conflict);
    }
}

// ── POST /api/v1/tx/call-cq tests (task 11.9) ────────────────────────────────

/// <summary>
/// Integration tests for <c>POST /api/v1/tx/call-cq</c> (task 11.5).
/// Uses <see cref="TxAnswerCqFixture"/> which provides a <see cref="MockQsoController"/>
/// (no router — exercises the endpoint's fallback path).  The router-specific switching
/// behaviour is covered by unit tests for <see cref="QsoControllerRouter"/> (task 11.9b).
/// NFR-021: all example callsigns use Q-prefix.
/// </summary>
[Collection("call-cq-tests")]
public sealed class CallCqEndpointTests : IClassFixture<TxAnswerCqFixture>
{
    private readonly TxAnswerCqFixture _fixture;

    public CallCqEndpointTests(TxAnswerCqFixture fixture) => _fixture = fixture;

    // ── 11.9a: 200 when Answerer mode and Idle ───────────────────────────────

    [Fact(DisplayName = "11.9a: POST /tx/call-cq returns 200 with role='caller' when Answerer Idle")]
    public async Task CallCq_WhenAnswererIdle_Returns200WithCallerRole()
    {
        // Arrange
        _fixture.QsoController.Role  = QsoRole.Answerer;
        _fixture.QsoController.State = QsoState.Idle;
        await _fixture.ConfigStore.SaveAsync(new AppConfig());

        // Act
        var response = await _fixture.Client.PostAsync("/api/v1/tx/call-cq", content: null);

        // Assert HTTP 200
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        // Assert response body
        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.GetProperty("role").GetString()
            .Should().Be("caller", "call-cq always returns role='caller'");
        doc.RootElement.GetProperty("autoAnswerEnabled").GetBoolean()
            .Should().BeTrue("call-cq must arm AutoAnswer");
    }

    // ── 11.9b: 200 when already Caller Idle ─────────────────────────────────

    [Fact(DisplayName = "11.9b: POST /tx/call-cq returns 200 with role='caller' when already Caller Idle")]
    public async Task CallCq_WhenCallerIdle_Returns200WithCallerRole()
    {
        // Arrange — mock controller already reports Caller role and Idle state.
        _fixture.QsoController.Role  = QsoRole.Caller;
        _fixture.QsoController.State = QsoState.Idle;
        await _fixture.ConfigStore.SaveAsync(new AppConfig());

        // Act
        var response = await _fixture.Client.PostAsync("/api/v1/tx/call-cq", content: null);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.OK);
        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.GetProperty("role").GetString().Should().Be("caller");
        doc.RootElement.GetProperty("autoAnswerEnabled").GetBoolean().Should().BeTrue();
    }

    // ── 11.9c: 409 when TX is busy (any role) ───────────────────────────────

    [Fact(DisplayName = "11.9c: POST /tx/call-cq returns 409 when TX is busy")]
    public async Task CallCq_WhenBusy_Returns409()
    {
        // Arrange — simulate an active QSO.
        _fixture.QsoController.Role  = QsoRole.Answerer;
        _fixture.QsoController.State = QsoState.WaitReport;

        // Act
        var response = await _fixture.Client.PostAsync("/api/v1/tx/call-cq", content: null);

        // Assert HTTP 409 Conflict
        response.StatusCode.Should().Be(HttpStatusCode.Conflict,
            "call-cq must refuse with 409 when a QSO is already in progress");

        // Restore Idle so subsequent tests in this fixture are unaffected.
        _fixture.QsoController.State = QsoState.Idle;
    }

    // ── 11.9d: AutoAnswer is saved to config store ───────────────────────────

    [Fact(DisplayName = "11.9d: POST /tx/call-cq persists autoAnswer=true when no router is wired")]
    public async Task CallCq_WhenNoRouter_PersistsAutoAnswerTrue()
    {
        // Arrange
        _fixture.QsoController.Role  = QsoRole.Answerer;
        _fixture.QsoController.State = QsoState.Idle;
        await _fixture.ConfigStore.SaveAsync(new AppConfig { Tx = new TxConfig(autoAnswer: false) });

        // Act
        await _fixture.Client.PostAsync("/api/v1/tx/call-cq", content: null);

        // Assert config was persisted
        _fixture.ConfigStore.Current.Tx?.AutoAnswer
            .Should().BeTrue("call-cq fallback path must save AutoAnswer=true to config store");

        // Restore
        _fixture.QsoController.State = QsoState.Idle;
    }
}

// ── POST /api/v1/tx/stop-cq tests (qso-controller, f-004-operator-visibility-improvements) ──

/// <summary>
/// Integration tests for <c>POST /api/v1/tx/stop-cq</c> (qso-controller spec).
/// Uses <see cref="TxAnswerCqFixture"/> which provides a <see cref="MockQsoController"/>.
/// Shares the "call-cq-tests" collection with <see cref="CallCqEndpointTests"/> since both
/// mutate the same fixture's shared, non-thread-safe <see cref="MockQsoController"/> state.
/// </summary>
[Collection("call-cq-tests")]
public sealed class StopCqEndpointTests : IClassFixture<TxAnswerCqFixture>
{
    private readonly TxAnswerCqFixture _fixture;

    public StopCqEndpointTests(TxAnswerCqFixture fixture) => _fixture = fixture;

    [Fact(DisplayName = "qso-controller: POST /tx/stop-cq calls GracefulStopAsync and returns 200")]
    public async Task StopCq_WhenControllerRegistered_CallsGracefulStopAndReturns200()
    {
        // Arrange — caller engaged, waiting for an answer (matches the spec scenario).
        _fixture.QsoController.Role  = QsoRole.Caller;
        _fixture.QsoController.State = QsoState.WaitReport; // proxy for CallerState.WaitAnswer

        var callsBefore = _fixture.QsoController.GracefulStopCallCount;

        // Act
        var response = await _fixture.Client.PostAsync("/api/v1/tx/stop-cq", content: null);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.OK);
        _fixture.QsoController.GracefulStopCallCount.Should().Be(callsBefore + 1,
            "POST /api/v1/tx/stop-cq must call GracefulStopAsync on the resolved controller");

        // Restore Idle so subsequent tests in this shared fixture are unaffected.
        _fixture.QsoController.State = QsoState.Idle;
    }

    [Fact(DisplayName = "qso-controller: POST /tx/stop-cq does not hardcode autoAnswerEnabled=false")]
    public async Task StopCq_ReturnsResponse_WithoutHardcodingAutoAnswerFalse()
    {
        // Arrange — TX may still be mid-completion; autoAnswer remains true in config,
        // unlike POST /api/v1/tx/abort which always disarms.
        _fixture.QsoController.Role  = QsoRole.Caller;
        _fixture.QsoController.State = QsoState.WaitReport;
        await _fixture.ConfigStore.SaveAsync(new AppConfig { Tx = new TxConfig(autoAnswer: true) });

        // Act
        var response = await _fixture.Client.PostAsync("/api/v1/tx/stop-cq", content: null);

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.OK);
        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.GetProperty("autoAnswerEnabled").GetBoolean()
            .Should().BeTrue(
                "unlike /abort, stop-cq must not hardcode AutoAnswerEnabled: false — " +
                "the service may still be completing an in-progress TX");

        // Restore Idle so subsequent tests in this shared fixture are unaffected.
        _fixture.QsoController.State = QsoState.Idle;
    }
}

/// <summary>
/// Integration test for <c>POST /api/v1/tx/stop-cq</c> when no <see cref="IQsoController"/>
/// is registered (qso-controller spec: 503 problem response, matching the existing
/// <c>/answer-cq</c>/<c>/select-responder</c> convention).
/// Uses <see cref="AudioConfigFixture"/> (no controller wired), separate from the
/// "call-cq-tests" collection's shared mutable state.
/// </summary>
public sealed class StopCqNoControllerEndpointTests : IClassFixture<AudioConfigFixture>
{
    private readonly AudioConfigFixture _fixture;

    public StopCqNoControllerEndpointTests(AudioConfigFixture fixture) => _fixture = fixture;

    [Fact(DisplayName = "qso-controller: POST /tx/stop-cq returns 503 when no controller is registered")]
    public async Task StopCq_WhenNoControllerRegistered_Returns503()
    {
        var response = await _fixture.Client.PostAsync("/api/v1/tx/stop-cq", content: null);

        response.StatusCode.Should().Be(HttpStatusCode.ServiceUnavailable,
            "stop-cq must return 503 (not throw) when no IQsoController is registered, " +
            "matching the existing /answer-cq and /select-responder convention");
    }
}
