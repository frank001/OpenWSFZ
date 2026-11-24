using FluentAssertions;
using Microsoft.Extensions.DependencyInjection;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Text;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// COH-RES-CAND v2 (FR-104): <c>decoder.coherentFallbackResidualCandidates</c> through the config API. HK-035: the POST is an overlay (a body without the key
/// keeps the stored value; a body with only the key changes only it).
/// </summary>
[Trait("Category", "Integration")]
public sealed class CoherentFallbackResidualCandidatesApiTests : IClassFixture<WebTestFactory>
{
    private readonly WebTestFactory _factory;

    public CoherentFallbackResidualCandidatesApiTests(WebTestFactory factory) => _factory = factory;

    private static StringContent Json(string body) => new(body, Encoding.UTF8, "application/json");

    [Fact(DisplayName = "FR-104: COH-RES-CAND v2: serialised as a boolean; an absent key reads false, an explicit true reads true")]
    public void WireFormat()
    {
        var json = JsonSerializer.Serialize(new DecoderConfig { CoherentFallbackResidualCandidates = true }, AppJsonContext.Default.DecoderConfig);
        json.Should().Contain("\"coherentFallbackResidualCandidates\":true");
        JsonSerializer.Deserialize(json, AppJsonContext.Default.DecoderConfig)!.CoherentFallbackResidualCandidates.Should().BeTrue();
        JsonSerializer.Deserialize("""{"kMinScorePass2":10}""", AppJsonContext.Default.DecoderConfig)!.CoherentFallbackResidualCandidates.Should().BeFalse("an absent key reads false (default OFF)");
    }

    [Fact(DisplayName = "FR-104: COH-RES-CAND v2: POST /api/v1/config is an overlay - posting only the key changes only that key; a body without it keeps it")]
    public async Task PostConfig_Overlay_ChangesOnlyThatKey()
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig() with { Decoder = new DecoderConfig { KMinScorePass2 = 11, CoherentFallbackAudio = CoherentFallbackAudio.Residual, CoherentFallbackResidualCandidates = false } });
        var client = _factory.CreateClient();

        var r1 = await client.PostAsync("/api/v1/config", Json("""{"decoder":{"coherentFallbackResidualCandidates":true}}"""));
        r1.StatusCode.Should().Be(HttpStatusCode.OK);
        var d = store.Current.Decoder!;
        d.CoherentFallbackResidualCandidates.Should().BeTrue();
        d.KMinScorePass2.Should().Be(11, "only the key in the body changed");
        d.CoherentFallbackAudio.Should().Be(CoherentFallbackAudio.Residual, "only the key in the body changed");

        var r2 = await client.PostAsync("/api/v1/config", Json("""{"decoder":{"kMinScorePass2":12}}"""));
        r2.StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder!.KMinScorePass2.Should().Be(12);
        store.Current.Decoder.CoherentFallbackResidualCandidates.Should().BeTrue("a partial POST leaves an explicit true as it was");

        var r3 = await client.PostAsync("/api/v1/config", Json("""{"decoder":{"coherentFallbackResidualCandidates":false}}"""));
        r3.StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder!.CoherentFallbackResidualCandidates.Should().BeFalse();
        store.Current.Decoder.KMinScorePass2.Should().Be(12);
    }
}
