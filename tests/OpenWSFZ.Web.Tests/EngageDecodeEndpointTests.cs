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

// ── Tracking stub ─────────────────────────────────────────────────────────────

/// <summary>
/// <see cref="IQsoController"/> stub that records the most recent call to
/// <see cref="EngageAtAsync"/> so endpoint tests can assert which
/// <see cref="EngagePoint"/> was dispatched.
/// NFR-021: all example callsigns use Q-prefix.
/// </summary>
internal sealed class TrackingMockQsoController : IQsoController
{
    public QsoState State   { get; set; } = QsoState.Idle;
    public string?  Partner { get; set; }
    public QsoRole  Role    { get; set; } = QsoRole.Answerer;

    /// <summary>
    /// Set to (Partner, FrequencyHz, Point) on each <see cref="EngageAtAsync"/> call;
    /// <c>null</c> until the first call or after <see cref="ResetTracking"/>.
    /// </summary>
    public (string Partner, double FrequencyHz, EngagePoint Point)? LastEngageAtCall { get; private set; }

    /// <summary>Clears <see cref="LastEngageAtCall"/> so each test starts from a known state.</summary>
    public void ResetTracking() => LastEngageAtCall = null;

    public Task AbortAsync(CancellationToken ct = default) => Task.CompletedTask;

    public Task AnswerCqAsync(
        string callsign, double frequencyHz, DateTimeOffset cqCycleStart, CancellationToken ct)
        => Task.CompletedTask;

    public Task SelectResponderAsync(
        string callsign, double frequencyHz, DateTimeOffset responseCycleStart, CancellationToken ct)
        => Task.CompletedTask;

    public Task EngageAtAsync(
        string partnerCallsign, double frequencyHz, DateTimeOffset theirCycleStart,
        EngagePoint point, CancellationToken ct)
    {
        LastEngageAtCall = (partnerCallsign, frequencyHz, point);
        return Task.CompletedTask;
    }
}

// ── Fixture ───────────────────────────────────────────────────────────────────

/// <summary>
/// Live Kestrel fixture for <c>POST /api/v1/tx/engage-decode</c> tests.
/// Wires a <see cref="TrackingMockQsoController"/> and sets operator callsign
/// to <c>Q1ABC</c> (ITU-unallocated Q-prefix — NFR-021).
/// </summary>
public sealed class EngageDecodeFixture : IAsyncLifetime
{
    internal readonly TestConfigStore             ConfigStore   = new();
    internal readonly TrackingMockQsoController   QsoController = new();

    private Microsoft.AspNetCore.Builder.WebApplication? _app;
    public  HttpClient Client { get; private set; } = null!;

    public async Task InitializeAsync()
    {
        // Operator callsign must be set before any request so Case B dispatch
        // recognises "Q1ABC" in tokens[0] of the engage-decode message.
        await ConfigStore.SaveAsync(new AppConfig
        {
            Tx = new TxConfig(callsign: "Q1ABC")
        });

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

// ── Tests ─────────────────────────────────────────────────────────────────────

/// <summary>
/// Integration tests for <c>POST /api/v1/tx/engage-decode</c> (D-CALLER-012 / D-CALLER-015).
/// Covers the grid-square dispatch branch added by D-CALLER-015.
/// NFR-021: all example callsigns use Q-prefix.
/// </summary>
public sealed class EngageDecodeEndpointTests : IClassFixture<EngageDecodeFixture>
{
    private readonly EngageDecodeFixture _fixture;
    private readonly HttpClient          _client;

    private const string CycleStart = "2026-06-27T14:30:00Z";

    public EngageDecodeEndpointTests(EngageDecodeFixture fixture)
    {
        _fixture = fixture;
        _client  = fixture.Client;
    }

    private static StringContent EngageBody(string message, double freqHz = 500.0)
        => new(
            $$"""{"message":"{{message}}","frequencyHz":{{freqHz}},"cycleStartUtc":"{{CycleStart}}"}""",
            Encoding.UTF8, "application/json");

    // ── Test A — 4-character Maidenhead grid square ───────────────────────────

    [Fact(DisplayName = "D-CALLER-015-A: OURCALL PARTNER GRID(4) returns 200 and dispatches EngageAt(SendReport)")]
    public async Task EngageDecode_4CharGrid_Returns200AndEngagesAtSendReport()
    {
        // Arrange
        _fixture.QsoController.ResetTracking();
        _fixture.QsoController.State = QsoState.Idle;

        // Act  — "Q1ABC Q9XYZ JO33": partner Q9XYZ answers our CQ with 4-char grid JO33
        var response = await _client.PostAsync(
            "/api/v1/tx/engage-decode", EngageBody("Q1ABC Q9XYZ JO33"));

        // Assert HTTP 200
        response.StatusCode.Should().Be(HttpStatusCode.OK,
            "OURCALL PARTNER GRID(4) is a valid first-exchange row — must return 200");

        // Assert EngageAtAsync was called with SendReport
        _fixture.QsoController.LastEngageAtCall.Should().NotBeNull(
            "EngageAtAsync must be invoked for a grid-square row");
        _fixture.QsoController.LastEngageAtCall!.Value.Point.Should().Be(EngagePoint.SendReport,
            "grid-square response means partner answered our CQ — we reply with our report");
        _fixture.QsoController.LastEngageAtCall!.Value.Partner.Should().Be("Q9XYZ",
            "partner extracted from tokens[1]");
    }

    // ── Test B — 6-character extended grid square ─────────────────────────────

    [Fact(DisplayName = "D-CALLER-015-B: OURCALL PARTNER GRID(6) returns 200 and dispatches EngageAt(SendReport)")]
    public async Task EngageDecode_6CharGrid_Returns200AndEngagesAtSendReport()
    {
        // Arrange
        _fixture.QsoController.ResetTracking();
        _fixture.QsoController.State = QsoState.Idle;

        // Act — 6-character extended grid square (e.g. JO33aa)
        var response = await _client.PostAsync(
            "/api/v1/tx/engage-decode", EngageBody("Q1ABC Q9XYZ JO33aa"));

        // Assert HTTP 200
        response.StatusCode.Should().Be(HttpStatusCode.OK,
            "OURCALL PARTNER GRID(6) is a valid FT8 first-exchange row — must return 200");

        // Assert EngageAtAsync(SendReport) was called
        _fixture.QsoController.LastEngageAtCall.Should().NotBeNull();
        _fixture.QsoController.LastEngageAtCall!.Value.Point.Should().Be(EngagePoint.SendReport,
            "6-char extended grid is semantically identical to 4-char grid for engage purposes");
        _fixture.QsoController.LastEngageAtCall!.Value.Partner.Should().Be("Q9XYZ");
    }

    // ── Test C — Genuinely unrecognised INFO token still returns 422 ──────────

    [Fact(DisplayName = "D-CALLER-015-C: unrecognised INFO token returns 422 and does not call EngageAt")]
    public async Task EngageDecode_UnrecognisedToken_Returns422AndDoesNotCallEngageAt()
    {
        // Arrange
        _fixture.QsoController.ResetTracking();
        _fixture.QsoController.State = QsoState.Idle;

        // "BLAH" — four letters, does not satisfy IsGridSquare (no digit at [2]).
        var response = await _client.PostAsync(
            "/api/v1/tx/engage-decode", EngageBody("Q1ABC Q9XYZ BLAH"));

        // Assert HTTP 422
        ((int)response.StatusCode).Should().Be(422,
            "free-text bleed-through or unknown INFO token must return 422 Unprocessable Entity");

        // Assert EngageAtAsync was NOT called
        _fixture.QsoController.LastEngageAtCall.Should().BeNull(
            "EngageAtAsync must not be invoked for an unrecognised INFO token");
    }

    // ── Test D — Regression: plain-SNR branch still works alongside grid branch

    [Fact(DisplayName = "D-CALLER-015-D: regression — plain SNR info (+07) still returns 200 with EngageAt(SendReport)")]
    public async Task EngageDecode_PlainSnr_StillReturns200AndEngagesAtSendReport()
    {
        // Arrange
        _fixture.QsoController.ResetTracking();
        _fixture.QsoController.State = QsoState.Idle;

        // Act — existing plain-SNR case; must not be disturbed by the new grid branch
        var response = await _client.PostAsync(
            "/api/v1/tx/engage-decode", EngageBody("Q1ABC Q9XYZ +07"));

        // Assert HTTP 200
        response.StatusCode.Should().Be(HttpStatusCode.OK,
            "plain-SNR first exchange must still return 200 after addition of the grid branch");

        // Assert EngageAtAsync(SendReport)
        _fixture.QsoController.LastEngageAtCall.Should().NotBeNull();
        _fixture.QsoController.LastEngageAtCall!.Value.Point.Should().Be(EngagePoint.SendReport,
            "plain SNR in Case B must dispatch EngageAt(SendReport)");
        _fixture.QsoController.LastEngageAtCall!.Value.Partner.Should().Be("Q9XYZ");
    }
}
