using FluentAssertions;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using Microsoft.Extensions.DependencyInjection;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Net.Http.Json;
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

    /// <summary>
    /// Set to the callsign on each <see cref="AnswerCqAsync"/> call (engagement-target-validation,
    /// task 4.4 — lets tests assert a rejected CQ-row target never reaches this call);
    /// <c>null</c> until the first call or after <see cref="ResetTracking"/>.
    /// </summary>
    public string? LastAnswerCqCallsign { get; private set; }

    /// <summary>
    /// Incremented on each <see cref="AbortAsync"/> call (Finding F, dev-task
    /// 2026-07-17-engagement-target-validation-qa-review-findings — lets tests assert a rejected
    /// engagement target's prior in-progress QSO is never aborted before the operator confirms);
    /// <c>0</c> until the first call or after <see cref="ResetTracking"/>.
    /// </summary>
    public int AbortCallCount { get; private set; }

    /// <summary>Clears all tracked calls so each test starts from a known state.</summary>
    public void ResetTracking()
    {
        LastEngageAtCall     = null;
        LastAnswerCqCallsign = null;
        AbortCallCount       = 0;
    }

    public Task AbortAsync(CancellationToken ct = default)
    {
        AbortCallCount++;
        return Task.CompletedTask;
    }

    public Task AnswerCqAsync(
        string callsign, double frequencyHz, DateTimeOffset cqCycleStart, CancellationToken ct)
    {
        LastAnswerCqCallsign = callsign;
        return Task.CompletedTask;
    }

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

/// <summary>
/// Test double for <see cref="IEngagementTargetValidator"/> (engagement-target-validation, task
/// 4.4) whose verdict is fully test-controlled via <see cref="Rule"/>. Defaults to allowing every
/// candidate — same as <c>NullEngagementTargetValidator</c> — so tests that don't set
/// <see cref="Rule"/> see today's fully permissive behaviour unchanged.
/// </summary>
internal sealed class FakeEngagementTargetValidator : IEngagementTargetValidator
{
    public Func<string, EngagementValidationResult>? Rule { get; set; }

    public EngagementValidationResult Validate(string callsignToken)
        => Rule?.Invoke(callsignToken) ?? EngagementValidationResult.Allowed;
}

// ── Fixture ───────────────────────────────────────────────────────────────────

/// <summary>
/// Live Kestrel fixture for <c>POST /api/v1/tx/engage-decode</c> tests.
/// Wires a <see cref="TrackingMockQsoController"/> and sets operator callsign
/// to <c>Q1ABC</c> (ITU-unallocated Q-prefix — NFR-021).
/// </summary>
public sealed class EngageDecodeFixture : IAsyncLifetime
{
    internal readonly TestConfigStore                 ConfigStore         = new();
    internal readonly TrackingMockQsoController       QsoController       = new();
    internal readonly FakeEngagementTargetValidator   EngagementValidator = new();

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
            {
                services.AddSingleton<IQsoController>(QsoController);
                // engagement-target-validation (task 4.4): overrides WebApp.Create's default
                // pass-through registration so tests can drive Rejected/Allowed per test.
                services.AddSingleton<IEngagementTargetValidator>(EngagementValidator);
            });

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

    private static StringContent EngageBody(string message, double freqHz = 500.0, bool confirm = false)
        => new(
            $$"""{"message":"{{message}}","frequencyHz":{{freqHz}},"cycleStartUtc":"{{CycleStart}}","confirm":{{(confirm ? "true" : "false")}}}""",
            Encoding.UTF8, "application/json");

    // ── Test A — 4-character Maidenhead grid square ───────────────────────────

    [Fact(DisplayName = "D-CALLER-015-A: OURCALL PARTNER GRID(4) returns 200 and dispatches EngageAt(SendReport)")]
    public async Task EngageDecode_4CharGrid_Returns200AndEngagesAtSendReport()
    {
        // Arrange
        _fixture.QsoController.ResetTracking();
        _fixture.EngagementValidator.Rule = null; // engagement-target-validation: allow-all baseline
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
        _fixture.EngagementValidator.Rule = null; // engagement-target-validation: allow-all baseline
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
        _fixture.EngagementValidator.Rule = null; // engagement-target-validation: allow-all baseline
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
        _fixture.EngagementValidator.Rule = null; // engagement-target-validation: allow-all baseline
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

    // ── Tests E/F — engagement-target-validation (task 4.4) ───────────────────

    [Fact(DisplayName = "engagement-target-validation 4.4: rejected CQ-row target returns 409 with requiresConfirmation and does not call AnswerCqAsync")]
    public async Task EngageDecode_CqRow_RejectedTarget_Returns409AndDoesNotEngage()
    {
        // Arrange
        _fixture.QsoController.ResetTracking();
        _fixture.QsoController.State = QsoState.Idle;
        _fixture.EngagementValidator.Rule =
            callsign => callsign == "Q6KERBOGUS"
                ? EngagementValidationResult.Rejected("implausible callsign shape")
                : EngagementValidationResult.Allowed;

        // Act — "CQ Q6KERBOGUS JO22": a CQ row whose callsign the validator rejects.
        var response = await _client.PostAsync(
            "/api/v1/tx/engage-decode", EngageBody("CQ Q6KERBOGUS JO22"));

        // Assert HTTP 409 with the confirmation-required body.
        ((int)response.StatusCode).Should().Be(409,
            "a rejected engagement target must be a soft block, not silently proceed or 500");
        var body = await response.Content.ReadFromJsonAsync<JsonElement>();
        body.GetProperty("requiresConfirmation").GetBoolean().Should().BeTrue();
        body.GetProperty("reason").GetString().Should().Contain("implausible callsign shape");

        // Assert AnswerCqAsync was never called for the rejected target.
        _fixture.QsoController.LastAnswerCqCallsign.Should().BeNull(
            "a rejected CQ-row target must never reach AnswerCqAsync");
    }

    [Fact(DisplayName = "engagement-target-validation 4.4: confirmed retry after a 409 proceeds and calls EngageAtAsync")]
    public async Task EngageDecode_DirectedMessage_RejectedThenConfirmed_ProceedsAndEngages()
    {
        // Arrange
        _fixture.QsoController.ResetTracking();
        _fixture.QsoController.State = QsoState.Idle;
        _fixture.EngagementValidator.Rule =
            callsign => callsign == "Q6KERBOGUS"
                ? EngagementValidationResult.Rejected("implausible callsign shape")
                : EngagementValidationResult.Allowed;

        // Act 1 — first request without confirm: expect 409, no engagement.
        var firstResponse = await _client.PostAsync(
            "/api/v1/tx/engage-decode", EngageBody("Q1ABC Q6KERBOGUS +07"));

        ((int)firstResponse.StatusCode).Should().Be(409);
        _fixture.QsoController.LastEngageAtCall.Should().BeNull(
            "the first, unconfirmed request must not arm or transmit");

        // Act 2 — repeat with confirm:true: expect 200 and EngageAtAsync(SendReport) called.
        _fixture.QsoController.State = QsoState.Idle; // engage-decode aborts first if not Idle
        var secondResponse = await _client.PostAsync(
            "/api/v1/tx/engage-decode", EngageBody("Q1ABC Q6KERBOGUS +07", confirm: true));

        secondResponse.StatusCode.Should().Be(HttpStatusCode.OK,
            "a confirmed retry must proceed exactly as an Allowed target would");
        _fixture.QsoController.LastEngageAtCall.Should().NotBeNull();
        _fixture.QsoController.LastEngageAtCall!.Value.Partner.Should().Be("Q6KERBOGUS");
        _fixture.QsoController.LastEngageAtCall!.Value.Point.Should().Be(EngagePoint.SendReport);
    }

    [Fact(DisplayName = "engagement-target-validation 4.4: an Allowed target is unaffected — 200 and EngageAtAsync called as before")]
    public async Task EngageDecode_AllowedTarget_Unaffected()
    {
        // Arrange
        _fixture.QsoController.ResetTracking();
        _fixture.QsoController.State = QsoState.Idle;
        _fixture.EngagementValidator.Rule = _ => EngagementValidationResult.Allowed;

        // Act
        var response = await _client.PostAsync(
            "/api/v1/tx/engage-decode", EngageBody("Q1ABC Q9XYZ +07"));

        // Assert
        response.StatusCode.Should().Be(HttpStatusCode.OK);
        _fixture.QsoController.LastEngageAtCall.Should().NotBeNull();
        _fixture.QsoController.LastEngageAtCall!.Value.Partner.Should().Be("Q9XYZ");
    }

    // ── Finding F — dev-task 2026-07-17-engagement-target-validation-qa-review-findings ───────
    //
    // A rejected engagement target must never abort a prior in-progress QSO before the operator
    // has a chance to see the confirmation prompt. Both regression tests below start the fixture
    // from a non-Idle state with an active partner — the gap this finding identified had no
    // coverage anywhere in the existing suite, since every other test in this file starts from Idle.

    [Fact(DisplayName = "engagement-target-validation Finding F: rejected CQ-row target leaves an active in-progress QSO completely untouched")]
    public async Task EngageDecode_CqRow_RejectedTarget_NonIdleStart_DoesNotAbortActiveQso()
    {
        // Arrange — an active QSO already in progress with a different partner.
        _fixture.QsoController.ResetTracking();
        _fixture.QsoController.State   = QsoState.WaitReport;
        _fixture.QsoController.Partner = "Q1EXISTING";
        _fixture.EngagementValidator.Rule =
            callsign => callsign == "Q6KERBOGUS"
                ? EngagementValidationResult.Rejected("implausible callsign shape")
                : EngagementValidationResult.Allowed;

        // Act — "CQ Q6KERBOGUS JO22": a CQ row whose callsign the validator rejects, no confirm.
        var response = await _client.PostAsync(
            "/api/v1/tx/engage-decode", EngageBody("CQ Q6KERBOGUS JO22"));

        // Assert HTTP 409.
        ((int)response.StatusCode).Should().Be(409);

        // Assert the prior in-progress QSO was never touched: AbortAsync must not have been
        // called, and state/partner must be exactly what they were before the request.
        _fixture.QsoController.AbortCallCount.Should().Be(0,
            "a rejected, unconfirmed engagement target must not abort a prior in-progress QSO — " +
            "the operator hasn't seen the confirmation prompt yet");
        _fixture.QsoController.State.Should().Be(QsoState.WaitReport,
            "the active QSO's state must be unchanged by a rejected engagement attempt");
        _fixture.QsoController.Partner.Should().Be("Q1EXISTING",
            "the active QSO's partner must be unchanged by a rejected engagement attempt");
        _fixture.QsoController.LastAnswerCqCallsign.Should().BeNull(
            "a rejected CQ-row target must never reach AnswerCqAsync");

        // Cleanup so subsequent tests in this shared fixture start from a known state.
        _fixture.QsoController.State   = QsoState.Idle;
        _fixture.QsoController.Partner = null;
    }

    [Fact(DisplayName = "engagement-target-validation Finding F: rejected directed-message target leaves an active in-progress QSO completely untouched")]
    public async Task EngageDecode_DirectedMessage_RejectedTarget_NonIdleStart_DoesNotAbortActiveQso()
    {
        // Arrange — an active QSO already in progress with a different partner.
        _fixture.QsoController.ResetTracking();
        _fixture.QsoController.State   = QsoState.WaitRr73;
        _fixture.QsoController.Partner = "Q1EXISTING";
        _fixture.EngagementValidator.Rule =
            callsign => callsign == "Q6KERBOGUS"
                ? EngagementValidationResult.Rejected("implausible callsign shape")
                : EngagementValidationResult.Allowed;

        // Act — "Q1ABC Q6KERBOGUS +07": a directed first-exchange row whose target is rejected.
        var response = await _client.PostAsync(
            "/api/v1/tx/engage-decode", EngageBody("Q1ABC Q6KERBOGUS +07"));

        // Assert HTTP 409.
        ((int)response.StatusCode).Should().Be(409);

        // Assert the prior in-progress QSO was never touched.
        _fixture.QsoController.AbortCallCount.Should().Be(0,
            "a rejected, unconfirmed engagement target must not abort a prior in-progress QSO");
        _fixture.QsoController.State.Should().Be(QsoState.WaitRr73,
            "the active QSO's state must be unchanged by a rejected engagement attempt");
        _fixture.QsoController.Partner.Should().Be("Q1EXISTING",
            "the active QSO's partner must be unchanged by a rejected engagement attempt");
        _fixture.QsoController.LastEngageAtCall.Should().BeNull(
            "a rejected directed-message target must never reach EngageAtAsync");

        // Cleanup so subsequent tests in this shared fixture start from a known state.
        _fixture.QsoController.State   = QsoState.Idle;
        _fixture.QsoController.Partner = null;
    }
}
