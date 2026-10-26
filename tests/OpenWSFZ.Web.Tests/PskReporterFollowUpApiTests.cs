using System.Net;
using System.Text;
using System.Text.Json;
using FluentAssertions;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using OpenWSFZ.Abstractions;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// The #262 follow-up round, web side: T18 the read-only status endpoint (FR-095) and T20 the locator validation and overlay (FR-096).
/// Q-prefix callsigns only (NFR-021); the endpoint body carries counts and a reason code, never a callsign.
/// </summary>
[Trait("Category", "Integration")]
public sealed class PskReporterFollowUpApiTests : IClassFixture<WebTestFactory>
{
    private readonly WebTestFactory _factory;

    public PskReporterFollowUpApiTests(WebTestFactory factory) => _factory = factory;

    private static StringContent Json(string body) => new(body, Encoding.UTF8, "application/json");

    private sealed class StubSource(Func<PskReporterStatus> status) : IPskReporterStatusSource
    {
        public PskReporterStatus GetStatus() => status();
    }

    private static readonly PskReporterWindowCounts NoCounts = new(0, 0, 0, 0, 0, 0, 0, 0);

    private HttpClient ClientWith(Func<PskReporterStatus> status)
        => _factory.WithWebHostBuilder(b => b.ConfigureServices(s =>
        {
            s.RemoveAll<IPskReporterStatusSource>();
            s.AddSingleton<IPskReporterStatusSource>(new StubSource(status));
        })).CreateClient();

    // ── FR-095: T18 the status endpoint ──────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-095: T18: GET /api/v1/psk-reporter/status returns the state, last datagram time and record count, reason code and window counts")]
    public async Task T18_Sending_BodyShape()
    {
        var at = new DateTime(2026, 10, 26, 12, 34, 56, DateTimeKind.Utc);
        var client = ClientWith(() => new PskReporterStatus(PskReporterStates.Sending, at, 40, null, new PskReporterWindowCounts(55, 40, 5, 0, 0, 3, 2, 5)));

        var response = await client.GetAsync("/api/v1/psk-reporter/status");
        response.StatusCode.Should().Be(HttpStatusCode.OK);
        using var doc = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
        var root = doc.RootElement;
        root.GetProperty("state").GetString().Should().Be("sending");
        root.GetProperty("lastDatagramRecords").GetInt32().Should().Be(40);
        root.GetProperty("lastDatagramUtc").GetDateTime().ToUniversalTime().Should().Be(at);
        root.GetProperty("reason").ValueKind.Should().Be(JsonValueKind.Null);
        root.GetProperty("window").GetProperty("seen").GetInt32().Should().Be(55);
        root.GetProperty("window").GetProperty("reported").GetInt32().Should().Be(40);
        root.GetProperty("window").GetProperty("ownCall").GetInt32().Should().Be(2);
    }

    [Theory(DisplayName = "FR-095: T18: the endpoint reports off, waiting and each refusal reason (identity, no-dial, region) exactly as the source states it")]
    [InlineData("off", null)]
    [InlineData("waiting", null)]
    [InlineData("refused", "identity")]
    [InlineData("refused", "no-dial")]
    [InlineData("refused", "region")]
    public async Task T18_StatesAndReasons_AreRelayed(string state, string? reason)
    {
        var client = ClientWith(() => new PskReporterStatus(state, null, 0, reason, NoCounts));
        using var doc = JsonDocument.Parse(await client.GetStringAsync("/api/v1/psk-reporter/status"));
        doc.RootElement.GetProperty("state").GetString().Should().Be(state);
        var r = doc.RootElement.GetProperty("reason");
        (r.ValueKind == JsonValueKind.Null ? null : r.GetString()).Should().Be(reason);
    }

    [Fact(DisplayName = "FR-095: T18: the endpoint reads the source on every request (it moves when the counters move) and its body carries no callsign")]
    public async Task T18_FollowsTheSource_AndCarriesNoCallsign()
    {
        int identity = 0;
        var client = ClientWith(() => new PskReporterStatus(PskReporterStates.Refused, null, 0, PskReporterReasons.Identity,
            new PskReporterWindowCounts(identity, 0, 0, 0, identity, 0, 0, 0)));

        identity = 3;
        var first = await client.GetStringAsync("/api/v1/psk-reporter/status");
        identity = 5;
        var second = await client.GetStringAsync("/api/v1/psk-reporter/status");

        JsonDocument.Parse(first).RootElement.GetProperty("window").GetProperty("identity").GetInt32().Should().Be(3);
        JsonDocument.Parse(second).RootElement.GetProperty("window").GetProperty("identity").GetInt32().Should().Be(5);
        foreach (var body in new[] { first, second })
        {
            using var doc = JsonDocument.Parse(body);
            doc.RootElement.EnumerateObject().Select(p => p.Name).Should().BeEquivalentTo(
                ["state", "lastDatagramUtc", "lastDatagramRecords", "reason", "window"], "counts and a reason code only: no member could carry a callsign");
            doc.RootElement.GetProperty("window").EnumerateObject().Select(p => p.Name).Should().BeEquivalentTo(
                ["seen", "reported", "region", "noDial", "identity", "hashed", "ownCall", "dedup"]);
        }
    }

    [Theory(DisplayName = "FR-095: T18: the status endpoint is read-only: POST, PUT and DELETE are refused")]
    [InlineData("POST")]
    [InlineData("PUT")]
    [InlineData("DELETE")]
    public async Task T18_WriteVerbs_AreRefused(string verb)
    {
        var client = ClientWith(() => new PskReporterStatus("off", null, 0, null, NoCounts));
        var response = await client.SendAsync(new HttpRequestMessage(new HttpMethod(verb), "/api/v1/psk-reporter/status") { Content = Json("{}") });
        response.StatusCode.Should().Be(HttpStatusCode.MethodNotAllowed);
    }

    [Fact(DisplayName = "FR-095: T18: without a running upload service the endpoint answers from the configuration: off when disabled, waiting when enabled")]
    public async Task T18_WithoutService_AnswersFromConfig()
    {
        var factory = _factory.WithWebHostBuilder(b => b.ConfigureServices(s => s.RemoveAll<IPskReporterStatusSource>()));
        var store = factory.Services.GetRequiredService<IConfigStore>();
        var client = factory.CreateClient();

        await store.SaveAsync(new AppConfig { PskReporter = new PskReporterConfig(enabled: false) });
        JsonDocument.Parse(await client.GetStringAsync("/api/v1/psk-reporter/status")).RootElement.GetProperty("state").GetString().Should().Be("off");

        await store.SaveAsync(new AppConfig { PskReporter = new PskReporterConfig(enabled: true) });
        JsonDocument.Parse(await client.GetStringAsync("/api/v1/psk-reporter/status")).RootElement.GetProperty("state").GetString().Should().Be("waiting");
    }

    // ── FR-096: T20 validation and overlay ───────────────────────────────────────────────────────────────────────────

    private static PskReporterConfig Stored() => new(enabled: true, antennaInformation: "Q1 loop", locator: "JO33ab", host: "test.invalid", port: 14739);

    [Theory(DisplayName = "FR-096: T20: the server answers 400 and leaves the stored configuration unchanged for an invalid locator")]
    [InlineData("JO33E")]
    [InlineData("JO33ZZ")]
    [InlineData("1O33ab")]
    [InlineData("JO33abc")]
    public async Task T20_Invalid_Is400_AndUnchanged(string locator)
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig { PskReporter = Stored() });
        var client = _factory.CreateClient();

        var response = await client.PostAsync("/api/v1/config", Json($$$"""{"pskReporter":{"locator":"{{{locator}}}","antennaInformation":"CHANGED"}}"""));

        response.StatusCode.Should().Be(HttpStatusCode.BadRequest);
        store.Current.PskReporter.Should().Be(Stored(), "nothing is persisted when the locator is refused");
    }

    [Theory(DisplayName = "FR-096: T20: the server accepts an empty locator and six valid characters in either case (JO33ab, jo33AB, RR99xx)")]
    [InlineData("")]
    [InlineData("JO33ab")]
    [InlineData("jo33AB")]
    [InlineData("RR99xx")]
    public async Task T20_Valid_IsAccepted_AndStoredAsTyped(string locator)
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig { PskReporter = new PskReporterConfig(enabled: true) });
        var client = _factory.CreateClient();

        (await client.PostAsync("/api/v1/config", Json($$$"""{"pskReporter":{"locator":"{{{locator}}}"}}"""))).StatusCode.Should().Be(HttpStatusCode.OK);

        store.Current.PskReporter.Locator.Should().Be(locator, "stored as typed; normalisation happens on the wire");
    }

    [Fact(DisplayName = "FR-096: T20: a POST of only {pskReporter:{locator}} while enabled keeps enabled, host, port and antennaInformation")]
    public async Task T20_NestedOverlay_KeepsTheOtherKeys()
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig { PskReporter = Stored() });
        var client = _factory.CreateClient();

        (await client.PostAsync("/api/v1/config", Json("""{"pskReporter":{"locator":"JO33ED"}}"""))).StatusCode.Should().Be(HttpStatusCode.OK);

        store.Current.PskReporter.Should().Be(Stored() with { Locator = "JO33ED" });
    }

    [Fact(DisplayName = "FR-096: T20: a stored invalid locator (edited in the file) does not block an unrelated save")]
    public async Task T20_StoredInvalid_DoesNotBlockUnrelatedSave()
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig { PskReporter = Stored() with { Locator = "bad" } });
        var client = _factory.CreateClient();

        (await client.PostAsync("/api/v1/config", Json("""{"pskReporter":{"antennaInformation":"X"}}"""))).StatusCode.Should().Be(HttpStatusCode.OK);
        (await client.PostAsync("/api/v1/config", Json("""{"showCycleCountdown":false}"""))).StatusCode.Should().Be(HttpStatusCode.OK);
    }
}
