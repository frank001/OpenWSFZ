using FluentAssertions;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using Microsoft.Extensions.DependencyInjection;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Web.Tests;

// ── Test doubles for POST /api/v1/ptt/test (cat-tx-ptt, task 17.7, FR-057) ────

/// <summary>
/// Controllable <see cref="IQsoController"/> stub with a settable <see cref="Keying"/>,
/// so tests can exercise the endpoint's 409-while-a-real-QSO-is-transmitting guard
/// without needing a real <c>QsoAnswererService</c>/<c>QsoCallerService</c>.
/// </summary>
internal sealed class TestKeyingQsoController : IQsoController
{
    public QsoState State   { get; set; } = QsoState.Idle;
    public string?  Partner { get; set; }
    public QsoRole  Role    { get; set; } = QsoRole.Answerer;
    public bool     Keying  { get; set; }

    public Task AbortAsync(CancellationToken ct = default) => Task.CompletedTask;

    public Task GracefulStopAsync(CancellationToken ct = default) => Task.CompletedTask;

    public Task AnswerCqAsync(
        string callsign, double frequencyHz, DateTimeOffset cqCycleStart, CancellationToken ct)
        => Task.CompletedTask;

    public Task SelectResponderAsync(
        string callsign, double frequencyHz, DateTimeOffset responseCycleStart, CancellationToken ct)
        => Task.CompletedTask;

    public Task EngageAtAsync(
        string partnerCallsign, double frequencyHz, DateTimeOffset theirCycleStart,
        EngagePoint point, CancellationToken ct)
        => Task.CompletedTask;
}

/// <summary>
/// Controllable <see cref="IPttController"/> stub that records the call sequence and can
/// be made to throw from <see cref="KeyDownAsync"/>/<see cref="KeyUpAsync"/>, so tests can
/// exercise the endpoint's pass/error response shape without any real WASAPI, CAT, or
/// serial hardware.
/// </summary>
internal sealed class TestPttController : IPttController
{
    public List<string> Calls { get; } = new();
    public Exception?   ThrowOnKeyDown { get; set; }
    public Exception?   ThrowOnKeyUp   { get; set; }

    public void LoadAudio(float[] samples) => Calls.Add("LoadAudio");

    public Task KeyDownAsync(CancellationToken ct = default)
    {
        Calls.Add("KeyDownAsync");
        if (ThrowOnKeyDown is not null) throw ThrowOnKeyDown;
        return Task.CompletedTask;
    }

    public Task KeyUpAsync(CancellationToken ct = default)
    {
        Calls.Add("KeyUpAsync");
        if (ThrowOnKeyUp is not null) throw ThrowOnKeyUp;
        return Task.CompletedTask;
    }

    public ValueTask DisposeAsync() => ValueTask.CompletedTask;
}

/// <summary>
/// Fixture that wires a <see cref="TestKeyingQsoController"/> and <see cref="TestPttController"/>
/// into a live Kestrel instance (mirrors <c>TxAnswerCqFixture</c>'s pattern) so
/// <c>POST /api/v1/ptt/test</c> tests can control both the "is a real QSO keying" state and
/// the PTT controller's success/failure behaviour without touching real hardware.
/// </summary>
public sealed class PttTestFixture : IAsyncLifetime
{
    internal readonly TestConfigStore         ConfigStore   = new();
    internal readonly TestKeyingQsoController  QsoController = new();
    internal readonly TestPttController        PttController = new();

    private Microsoft.AspNetCore.Builder.WebApplication? _app;
    public  HttpClient Client { get; private set; } = null!;

    public async Task InitializeAsync()
    {
        _app = WebApp.Create(
            port:              0,
            configStore:       ConfigStore,
            configureServices: services =>
                services
                    .AddSingleton<IQsoController>(QsoController)
                    .AddSingleton<IPttController>(PttController));

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
/// Integration tests for <c>POST /api/v1/ptt/test</c> (cat-tx-ptt, task 17.7, FR-057) —
/// the 409-while-keying case, the 409-on-AudioVox case, and the pass/error response shape,
/// matching <see cref="ConfigApiNullGuardTests"/>'s style.
/// </summary>
[Trait("Category", "Integration")]
public sealed class PttTestEndpointTests : IClassFixture<PttTestFixture>
{
    private readonly PttTestFixture _fixture;
    private readonly HttpClient     _client;

    public PttTestEndpointTests(PttTestFixture fixture)
    {
        _fixture = fixture;
        _client  = fixture.Client;

        // Each test starts from a clean slate — IClassFixture shares one instance across
        // all tests in this class (xUnit convention used throughout this test project).
        _fixture.QsoController.Keying = false;
        _fixture.PttController.Calls.Clear();
        _fixture.PttController.ThrowOnKeyDown = null;
        _fixture.PttController.ThrowOnKeyUp   = null;
    }

    [Fact(DisplayName = "FR-057: cat-tx-ptt 17.7, POST /api/v1/ptt/test returns 409 when the running method is AudioVox")]
    public async Task PostPttTest_AudioVoxMethod_Returns409()
    {
        await _fixture.ConfigStore.SaveAsync(new AppConfig { Ptt = new PttConfig { Method = "AudioVox" } });

        var response = await _client.PostAsync("/api/v1/ptt/test", content: null);

        response.StatusCode.Should().Be(HttpStatusCode.Conflict);
        _fixture.PttController.Calls.Should().BeEmpty(
            "AudioVox has nothing to test — the controller must never be touched");
    }

    [Fact(DisplayName = "FR-057: cat-tx-ptt 17.7, POST /api/v1/ptt/test returns 409 while a real QSO is keying")]
    public async Task PostPttTest_WhileKeying_Returns409()
    {
        await _fixture.ConfigStore.SaveAsync(new AppConfig { Ptt = new PttConfig { Method = "CatCommand" } });
        _fixture.QsoController.Keying = true;

        var response = await _client.PostAsync("/api/v1/ptt/test", content: null);

        response.StatusCode.Should().Be(HttpStatusCode.Conflict);
        var body = await response.Content.ReadAsStringAsync();
        body.Should().Contain("transmitting",
            "the 409 response must explain why — a real QSO is currently transmitting");
        _fixture.PttController.Calls.Should().BeEmpty(
            "a Test click racing a real transmission must never touch the shared IPttController " +
            "singleton — this is the regression guard for the safety finding behind task 17.2");
    }

    [Fact(DisplayName = "FR-057: cat-tx-ptt 17.7, POST /api/v1/ptt/test returns pass and pulses PTT when the method is testable")]
    public async Task PostPttTest_TestableMethod_ReturnsPassAndPulsesPtt()
    {
        await _fixture.ConfigStore.SaveAsync(new AppConfig { Ptt = new PttConfig { Method = "CatCommand" } });

        var response = await _client.PostAsync("/api/v1/ptt/test", content: null);

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.GetProperty("result").GetString().Should().Be("pass");

        _fixture.PttController.Calls.Should().Equal(["LoadAudio", "KeyDownAsync", "KeyUpAsync"],
            "the endpoint must load a (silent) buffer, assert, then release — in that order");
    }

    [Fact(DisplayName = "FR-057: cat-tx-ptt 17.7, POST /api/v1/ptt/test returns error (HTTP 200) when the pulse throws")]
    public async Task PostPttTest_ControllerThrows_ReturnsErrorWithHttp200()
    {
        await _fixture.ConfigStore.SaveAsync(new AppConfig { Ptt = new PttConfig { Method = "SerialRtsDtr" } });
        _fixture.PttController.ThrowOnKeyDown = new InvalidOperationException("port in use");

        var response = await _client.PostAsync("/api/v1/ptt/test", content: null);

        response.StatusCode.Should().Be(HttpStatusCode.OK,
            "a real CAT/serial failure during the pulse is an expected, handleable outcome — " +
            "not a server error, so it must not surface as HTTP 500");
        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.GetProperty("result").GetString().Should().Be("error");
        doc.RootElement.GetProperty("message").GetString().Should().Be("port in use");
    }
}
