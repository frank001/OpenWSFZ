using FluentAssertions;
using Microsoft.Extensions.DependencyInjection;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Text;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// COH-MULTISET (HK-035): <c>decoder.coherentFallbackMultiSet</c> through the config API. The POST is an OVERLAY: a body that does not carry the
/// key leaves it as it was (true stays true), one that carries it changes only it. There is no Settings-page control for it.
/// </summary>
[Trait("Category", "Integration")]
public sealed class CoherentFallbackMultiSetApiTests : IClassFixture<WebTestFactory>
{
    private readonly WebTestFactory _factory;

    public CoherentFallbackMultiSetApiTests(WebTestFactory factory) => _factory = factory;

    private static StringContent Json(string body) => new(body, Encoding.UTF8, "application/json");

    [Fact(DisplayName = "COH-MULTISET: POST /api/v1/config is an overlay for coherentFallbackMultiSet - a body without the key keeps true, one with it changes only it")]
    public async Task PostConfig_Overlay_KeepsAndChangesTheFlag()
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig() with { Decoder = new DecoderConfig { CoherentFallbackMultiSet = true } });
        var client = _factory.CreateClient();

        var r1 = await client.PostAsync("/api/v1/config", Json("""{"decoder":{"kMinScorePass2":12}}"""));
        r1.StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder!.KMinScorePass2.Should().Be(12);
        store.Current.Decoder.CoherentFallbackMultiSet.Should().BeTrue("the overlay keeps a key the body does not carry");

        var r2 = await client.PostAsync("/api/v1/config", Json("""{"decoder":{"coherentFallbackEnabled":false}}"""));
        r2.StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder.CoherentFallbackMultiSet.Should().BeTrue("a body for the other flag does not touch this one");

        var r3 = await client.PostAsync("/api/v1/config", Json("""{"decoder":{"coherentFallbackMultiSet":false}}"""));
        r3.StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder.CoherentFallbackMultiSet.Should().BeFalse();
        store.Current.Decoder.KMinScorePass2.Should().Be(12, "only the key in the body changed");
        store.Current.Decoder.CoherentFallbackEnabled.Should().BeFalse("the other flag is as the earlier POST left it");
    }

    [Fact(DisplayName = "COH-MULTISET: an overlay POST of an unrelated key leaves a stored false false (the default is not re-applied), and one that sets true turns it on")]
    public async Task PostConfig_Overlay_FalseStaysFalse_TrueTurnsOn()
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig() with { Decoder = new DecoderConfig { CoherentFallbackMultiSet = false } });
        var client = _factory.CreateClient();

        (await client.PostAsync("/api/v1/config", Json("""{"decoder":{"kMinScorePass2":13}}"""))).StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder!.CoherentFallbackMultiSet.Should().BeFalse();

        (await client.PostAsync("/api/v1/config", Json("""{"decoder":{"coherentFallbackMultiSet":true}}"""))).StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder.CoherentFallbackMultiSet.Should().BeTrue();
        store.Current.Decoder.KMinScorePass2.Should().Be(13);
    }
}
