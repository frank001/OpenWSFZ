using FluentAssertions;
using Microsoft.Extensions.DependencyInjection;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Text;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// COH-FALLBACK Stage 2 (R10, HK-035): <c>decoder.coherentFallbackEnabled</c> through the config API. The POST is an OVERLAY: a body that
/// does not carry the key leaves it as it was; one that carries it changes only it. Default false.
/// </summary>
[Trait("Category", "Integration")]
public sealed class CoherentFallbackFlagApiTests : IClassFixture<WebTestFactory>
{
    private readonly WebTestFactory _factory;

    public CoherentFallbackFlagApiTests(WebTestFactory factory) => _factory = factory;

    private static StringContent Json(string body) => new(body, Encoding.UTF8, "application/json");

    [Fact(DisplayName = "R10: POST /api/v1/config is an overlay for coherentFallbackEnabled - a body without the key keeps true, one with it changes only it")]
    public async Task PostConfig_Overlay_KeepsAndChangesTheFlag()
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig() with { Decoder = new DecoderConfig { CoherentFallbackEnabled = true } });
        var client = _factory.CreateClient();

        var r1 = await client.PostAsync("/api/v1/config", Json("""{"decoder":{"kMinScorePass2":12}}"""));
        r1.StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder!.KMinScorePass2.Should().Be(12);
        store.Current.Decoder.CoherentFallbackEnabled.Should().BeTrue("the overlay keeps keys the body does not carry");

        var r2 = await client.PostAsync("/api/v1/config", Json("""{"decoder":{"coherentFallbackEnabled":false}}"""));
        r2.StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder.CoherentFallbackEnabled.Should().BeFalse();
        store.Current.Decoder.KMinScorePass2.Should().Be(12, "only the key in the body changed");
    }

    [Fact(DisplayName = "R10: an overlay POST of an unrelated key leaves a stored false false, and one that sets true turns it on without touching the depth")]
    public async Task PostConfig_Overlay_FalseStaysFalse_TrueTurnsOn()
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig() with { Decoder = new DecoderConfig { DecodingDepth = DecodingDepth.Normal } });
        var client = _factory.CreateClient();

        (await client.PostAsync("/api/v1/config", Json("""{"decoder":{"kMinScorePass2":13}}"""))).StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder!.CoherentFallbackEnabled.Should().BeFalse("the default does not turn on through an unrelated overlay POST");

        (await client.PostAsync("/api/v1/config", Json("""{"decoder":{"coherentFallbackEnabled":true}}"""))).StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder.CoherentFallbackEnabled.Should().BeTrue();
        store.Current.Decoder.DecodingDepth.Should().Be(DecodingDepth.Normal, "the other decoder keys are unchanged");
    }
}
