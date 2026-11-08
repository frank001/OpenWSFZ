using FluentAssertions;
using Microsoft.Extensions.DependencyInjection;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Text;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// COH-GATE-G R-F4: <c>decoder.coherentFallbackResidualUngated</c> through the config API. HK-035: the POST is an overlay (a body without the key keeps the
/// stored value; a body with only the key changes only it).
/// </summary>
[Trait("Category", "Integration")]
public sealed class CoherentFallbackResidualUngatedApiTests : IClassFixture<WebTestFactory>
{
    private readonly WebTestFactory _factory;

    public CoherentFallbackResidualUngatedApiTests(WebTestFactory factory) => _factory = factory;

    private static StringContent Json(string body) => new(body, Encoding.UTF8, "application/json");

    [Fact(DisplayName = "FR-101: COH-GATE-G R-F4: serialised as a boolean; an absent key reads false")]
    public void WireFormat()
    {
        var json = JsonSerializer.Serialize(new DecoderConfig { CoherentFallbackResidualUngated = true }, AppJsonContext.Default.DecoderConfig);
        json.Should().Contain("\"coherentFallbackResidualUngated\":true");
        JsonSerializer.Deserialize(json, AppJsonContext.Default.DecoderConfig)!.CoherentFallbackResidualUngated.Should().BeTrue();
        JsonSerializer.Deserialize("""{"kMinScorePass2":10}""", AppJsonContext.Default.DecoderConfig)!.CoherentFallbackResidualUngated.Should().BeFalse();
    }

    [Fact(DisplayName = "FR-101: COH-GATE-G R-F4: POST /api/v1/config is an overlay - posting only the key changes only that key; a body without it keeps it")]
    public async Task PostConfig_Overlay_ChangesOnlyThatKey()
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig() with { Decoder = new DecoderConfig { KMinScorePass2 = 11, CoherentFallbackAudio = CoherentFallbackAudio.Residual } });
        var client = _factory.CreateClient();

        var r1 = await client.PostAsync("/api/v1/config", Json("""{"decoder":{"coherentFallbackResidualUngated":true}}"""));
        r1.StatusCode.Should().Be(HttpStatusCode.OK);
        var d = store.Current.Decoder!;
        d.CoherentFallbackResidualUngated.Should().BeTrue();
        d.KMinScorePass2.Should().Be(11, "only the key in the body changed");
        d.CoherentFallbackAudio.Should().Be(CoherentFallbackAudio.Residual, "only the key in the body changed");

        var r2 = await client.PostAsync("/api/v1/config", Json("""{"decoder":{"kMinScorePass2":12}}"""));
        r2.StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder!.KMinScorePass2.Should().Be(12);
        store.Current.Decoder.CoherentFallbackResidualUngated.Should().BeTrue("an overlay without the key keeps an explicit value");

        var r3 = await client.PostAsync("/api/v1/config", Json("""{"decoder":{"coherentFallbackResidualUngated":false}}"""));
        r3.StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder!.CoherentFallbackResidualUngated.Should().BeFalse();
    }
}
