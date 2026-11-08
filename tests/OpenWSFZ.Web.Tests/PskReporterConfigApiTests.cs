using FluentAssertions;
using Microsoft.Extensions.DependencyInjection;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Text;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// FR-088 / T16 (HK-035, issue #262): <c>pskReporter</c> through the config API. The POST is an OVERLAY and merges NESTED objects: a body that
/// names only <c>antennaInformation</c> leaves <c>enabled</c>, <c>host</c> and <c>port</c> as stored, and a body without the block leaves it unchanged.
/// </summary>
[Trait("Category", "Integration")]
public sealed class PskReporterConfigApiTests : IClassFixture<WebTestFactory>
{
    private readonly WebTestFactory _factory;

    public PskReporterConfigApiTests(WebTestFactory factory) => _factory = factory;

    private static StringContent Json(string body) => new(body, Encoding.UTF8, "application/json");

    private static PskReporterConfig Stored() => new(enabled: true, antennaInformation: "Q1 loop", host: "pskreporter.info", port: 14739);

    [Fact(DisplayName = "FR-088: T16: POST {pskReporter:{antennaInformation}} while enabled leaves enabled, host and port as saved")]
    public async Task NestedOverlay_KeepsTheOtherKeys()
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig { PskReporter = Stored() });
        var client = _factory.CreateClient();

        (await client.PostAsync("/api/v1/config", Json("""{"pskReporter":{"antennaInformation":"X"}}"""))).StatusCode.Should().Be(HttpStatusCode.OK);

        store.Current.PskReporter.Should().Be(Stored() with { AntennaInformation = "X" }, "only the named key changed");
    }

    [Fact(DisplayName = "FR-088: T16: a POST without the pskReporter block leaves it unchanged, and an explicit null block means unchanged too")]
    public async Task BodyWithoutTheBlock_LeavesItUnchanged()
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig { PskReporter = Stored() });
        var client = _factory.CreateClient();

        (await client.PostAsync("/api/v1/config", Json("""{"showCycleCountdown":false}"""))).StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.PskReporter.Should().Be(Stored());

        (await client.PostAsync("/api/v1/config", Json("""{"pskReporter":null}"""))).StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.PskReporter.Should().Be(Stored(), "pskReporter is a non-nullable section: null means unchanged");
    }

    [Fact(DisplayName = "FR-088: T16: a POST that sets enabled changes only enabled; the default block stays inert until a POST opts in")]
    public async Task OptIn_ChangesOnlyEnabled()
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig());
        store.Current.PskReporter.Enabled.Should().BeFalse();
        var client = _factory.CreateClient();

        (await client.PostAsync("/api/v1/config", Json("""{"pskReporter":{"enabled":true}}"""))).StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.PskReporter.Should().Be(new PskReporterConfig(enabled: true));
    }
}
