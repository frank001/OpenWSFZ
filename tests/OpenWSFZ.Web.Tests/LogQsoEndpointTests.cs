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

// ── Test doubles ─────────────────────────────────────────────────────────────

/// <summary>
/// No-op <see cref="IAdifLogWriter"/> used in <see cref="WebTestFactory"/> to satisfy
/// the DI registration without touching the filesystem.
/// </summary>
internal sealed class NullAdifLogWriter : IAdifLogWriter
{
    public Task AppendQsoAsync(QsoRecord record) => Task.CompletedTask;
}

// ── Spy IAdifLogWriter ────────────────────────────────────────────────────────

/// <summary>
/// Recording <see cref="IAdifLogWriter"/> that captures all <see cref="AppendQsoAsync"/>
/// calls so tests can assert the record fields without touching the filesystem.
/// </summary>
internal sealed class SpyAdifLogWriter : IAdifLogWriter
{
    private readonly List<QsoRecord> _records = [];

    /// <summary>All records appended since the spy was created.</summary>
    public IReadOnlyList<QsoRecord> Records => _records;

    public Task AppendQsoAsync(QsoRecord record)
    {
        _records.Add(record);
        return Task.CompletedTask;
    }
}

// ── Fixture ───────────────────────────────────────────────────────────────────

/// <summary>
/// Fixture for <c>POST /api/v1/tx/log-qso</c> tests (qso-log-dialog, tasks 7.3–7.4).
/// Starts a real Kestrel instance with a spy <see cref="IAdifLogWriter"/> so tests
/// can assert that the ADIF record is constructed correctly and passed to the writer.
/// </summary>
public sealed class LogQsoFixture : IAsyncLifetime
{
    internal readonly TestConfigStore  ConfigStore   = new();
    internal readonly SpyAdifLogWriter AdifSpy       = new();

    private Microsoft.AspNetCore.Builder.WebApplication? _app;
    public  HttpClient Client { get; private set; } = null!;

    public async Task InitializeAsync()
    {
        _app = WebApp.Create(
            port:           0,
            configStore:    ConfigStore,
            adifLogWriter:  AdifSpy);

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
/// Integration tests for <c>POST /api/v1/tx/log-qso</c> (qso-log-dialog, tasks 7.3–7.4).
/// </summary>
[Trait("Category", "Integration")]
public sealed class LogQsoEndpointTests : IClassFixture<LogQsoFixture>
{
    private readonly LogQsoFixture _fixture;
    private readonly HttpClient    _client;

    // Q-prefix callsigns only (NFR-021 — no real callsigns in VCS).
    private const string Partner  = "Q1TST";
    private const string Operator = "Q1OFZ";

    private static readonly StringContent ValidBody = new(
        JsonSerializer.Serialize(new
        {
            callsign         = Partner,
            grid             = "JO22",
            rstSent          = "+00",
            rstRcvd          = "+05",
            startUtc         = "2026-06-27T14:29:15Z",
            endUtc           = "2026-06-27T14:30:00Z",
            freqMHz          = 14.074,
            operatorCallsign = Operator,
            name             = (string?)null,
            txPower          = (string?)null,
            comment          = (string?)null,
            propMode         = (string?)null,
            exchSent         = (string?)null,
            exchRcvd         = (string?)null,
            retainTxPower    = false,
            retainComment    = false,
            retainPropMode   = false,
        }),
        Encoding.UTF8,
        "application/json");

    public LogQsoEndpointTests(LogQsoFixture fixture)
    {
        _fixture = fixture;
        _client  = fixture.Client;
    }

    [Fact(DisplayName = "qso-log-dialog 7.3a: POST /api/v1/tx/log-qso with valid body returns 200 OK")]
    public async Task PostLogQso_ValidBody_Returns200()
    {
        var response = await _client.PostAsync("/api/v1/tx/log-qso", ValidBody);

        response.StatusCode.Should().Be(HttpStatusCode.OK);

        var body = await response.Content.ReadFromJsonAsync<JsonElement>();
        body.GetProperty("logged").GetBoolean().Should().BeTrue();
    }

    [Fact(DisplayName = "qso-log-dialog 7.3b: POST /api/v1/tx/log-qso passes QsoRecord to IAdifLogWriter")]
    public async Task PostLogQso_ValidBody_PassesRecordToAdifWriter()
    {
        var initialCount = _fixture.AdifSpy.Records.Count;

        var body = new StringContent(
            JsonSerializer.Serialize(new
            {
                callsign         = "Q2LOG",
                grid             = "JO33",
                rstSent          = "+00",
                rstRcvd          = "-05",
                startUtc         = "2026-06-27T15:00:00Z",
                endUtc           = "2026-06-27T15:00:15Z",
                freqMHz          = 7.074,
                operatorCallsign = Operator,
                name             = "John",
                txPower          = "100",
                comment          = (string?)null,
                propMode         = "TR",
                exchSent         = (string?)null,
                exchRcvd         = (string?)null,
                retainTxPower    = false,
                retainComment    = false,
                retainPropMode   = false,
            }),
            Encoding.UTF8,
            "application/json");

        await _client.PostAsync("/api/v1/tx/log-qso", body);

        var records = _fixture.AdifSpy.Records;
        records.Should().HaveCount(initialCount + 1);

        var record = records[initialCount];
        record.PartnerCallsign.Should().Be("Q2LOG");
        record.PartnerGrid.Should().Be("JO33");
        record.RstSent.Should().Be("+00");
        record.RstRcvd.Should().Be("-05");
        record.DialFrequencyMHz.Should().BeApproximately(7.074, 0.001);
        record.OperatorCallsign.Should().Be(Operator);
        record.PartnerName.Should().Be("John");
        record.TxPower.Should().Be("100");
        record.PropMode.Should().Be("TR");
    }

    [Fact(DisplayName = "qso-log-dialog 7.3c: POST /api/v1/tx/log-qso with malformed JSON returns 400")]
    public async Task PostLogQso_MalformedJson_Returns400()
    {
        var bad = new StringContent("{not valid json", Encoding.UTF8, "application/json");
        var response = await _client.PostAsync("/api/v1/tx/log-qso", bad);

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact(DisplayName = "qso-log-dialog 7.3d: POST /api/v1/tx/log-qso with invalid startUtc returns 400")]
    public async Task PostLogQso_InvalidStartUtc_Returns400()
    {
        var body = new StringContent(
            JsonSerializer.Serialize(new
            {
                callsign         = Partner,
                grid             = (string?)null,
                rstSent          = "+00",
                rstRcvd          = "+05",
                startUtc         = "not-a-date",
                endUtc           = "2026-06-27T14:30:00Z",
                freqMHz          = 14.074,
                operatorCallsign = Operator,
                name             = (string?)null,
                txPower          = (string?)null,
                comment          = (string?)null,
                propMode         = (string?)null,
                exchSent         = (string?)null,
                exchRcvd         = (string?)null,
                retainTxPower    = false,
                retainComment    = false,
                retainPropMode   = false,
            }),
            Encoding.UTF8,
            "application/json");

        var response = await _client.PostAsync("/api/v1/tx/log-qso", body);

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
    }

    [Fact(DisplayName = "qso-log-dialog 7.3e: POST /api/v1/tx/log-qso retain flags update TxConfig retained fields")]
    public async Task PostLogQso_RetainFlags_UpdatesConfigRetainedFields()
    {
        var body = new StringContent(
            JsonSerializer.Serialize(new
            {
                callsign         = Partner,
                grid             = (string?)null,
                rstSent          = "+00",
                rstRcvd          = "+05",
                startUtc         = "2026-06-27T16:00:00Z",
                endUtc           = "2026-06-27T16:00:15Z",
                freqMHz          = 14.074,
                operatorCallsign = Operator,
                name             = (string?)null,
                txPower          = "50",
                comment          = (string?)null,
                propMode         = "ES",
                exchSent         = (string?)null,
                exchRcvd         = (string?)null,
                retainTxPower    = true,
                retainComment    = false,
                retainPropMode   = true,
            }),
            Encoding.UTF8,
            "application/json");

        var response = await _client.PostAsync("/api/v1/tx/log-qso", body);
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        // Config should now hold the retained values.
        var saved = _fixture.ConfigStore.Current.Tx;
        saved!.RetainedTxPower.Should().Be("50");
        saved.RetainedPropMode.Should().Be("ES");
        // RetainedComment was not flagged — should remain default.
        saved.RetainedComment.Should().Be(string.Empty);
    }
}
