using FluentAssertions;
using Microsoft.Extensions.DependencyInjection;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Text;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// XC-BUILD (FR-105): <c>decoder.crossCyclePrior</c> and <c>decoder.crossCyclePriorShadow</c> through the config API. HK-035: the POST is an overlay (a body without the keys keeps the stored values; a body with only
/// one key changes only it).
/// </summary>
[Trait("Category", "Integration")]
public sealed class CrossCyclePriorApiTests : IClassFixture<WebTestFactory>
{
    private readonly WebTestFactory _factory;

    public CrossCyclePriorApiTests(WebTestFactory factory) => _factory = factory;

    private static StringContent Json(string body) => new(body, Encoding.UTF8, "application/json");

    [Fact(DisplayName = "FR-105: XC-BUILD: both keys are serialised as booleans; an absent key reads false, an explicit true reads true")]
    public void WireFormat()
    {
        var json = JsonSerializer.Serialize(new DecoderConfig { CrossCyclePrior = true, CrossCyclePriorShadow = true }, AppJsonContext.Default.DecoderConfig);
        json.Should().Contain("\"crossCyclePrior\":true").And.Contain("\"crossCyclePriorShadow\":true");
        var back = JsonSerializer.Deserialize(json, AppJsonContext.Default.DecoderConfig)!;
        back.CrossCyclePrior.Should().BeTrue();
        back.CrossCyclePriorShadow.Should().BeTrue();
        var absent = JsonSerializer.Deserialize("""{"kMinScorePass2":10}""", AppJsonContext.Default.DecoderConfig)!;
        absent.CrossCyclePrior.Should().BeFalse("an absent key reads false (default OFF)");
        absent.CrossCyclePriorShadow.Should().BeFalse();
    }

    [Fact(DisplayName = "FR-105: XC-BUILD: POST /api/v1/config is an overlay - posting only one key changes only that key; a body without them keeps them")]
    public async Task PostConfig_Overlay_ChangesOnlyThatKey()
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig() with { Decoder = new DecoderConfig { KMinScorePass2 = 11, CqApEnabled = true, CrossCyclePrior = false, CrossCyclePriorShadow = false } });
        var client = _factory.CreateClient();

        var r1 = await client.PostAsync("/api/v1/config", Json("""{"decoder":{"crossCyclePrior":true}}"""));
        r1.StatusCode.Should().Be(HttpStatusCode.OK);
        var d = store.Current.Decoder!;
        d.CrossCyclePrior.Should().BeTrue();
        d.CrossCyclePriorShadow.Should().BeFalse("only the key in the body changed");
        d.KMinScorePass2.Should().Be(11, "only the key in the body changed");
        d.CqApEnabled.Should().BeTrue("only the key in the body changed");

        var r2 = await client.PostAsync("/api/v1/config", Json("""{"decoder":{"kMinScorePass2":12}}"""));
        r2.StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder!.KMinScorePass2.Should().Be(12);
        store.Current.Decoder.CrossCyclePrior.Should().BeTrue("a partial POST leaves an explicit true as it was");

        var r3 = await client.PostAsync("/api/v1/config", Json("""{"decoder":{"crossCyclePriorShadow":true}}"""));
        r3.StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder!.CrossCyclePriorShadow.Should().BeTrue();
        store.Current.Decoder.CrossCyclePrior.Should().BeTrue("posting the shadow key leaves the main key as it was");

        var r4 = await client.PostAsync("/api/v1/config", Json("""{"decoder":{"crossCyclePrior":false}}"""));
        r4.StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder!.CrossCyclePrior.Should().BeFalse();
        store.Current.Decoder.CrossCyclePriorShadow.Should().BeTrue();
        store.Current.Decoder.KMinScorePass2.Should().Be(12);
    }
}
