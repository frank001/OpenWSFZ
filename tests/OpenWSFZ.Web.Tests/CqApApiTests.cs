using FluentAssertions;
using Microsoft.Extensions.DependencyInjection;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Text;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// CQ-AP: <c>decoder.cqApEnabled</c> through the config API. HK-035: the POST is an overlay (a body without the key keeps the stored value; a body
/// with only the key changes only it). No Settings-page control exists, so the API is the only way to set it.
/// </summary>
[Trait("Category", "Integration")]
public sealed class CqApApiTests : IClassFixture<WebTestFactory>
{
    private readonly WebTestFactory _factory;

    public CqApApiTests(WebTestFactory factory) => _factory = factory;

    private static StringContent Json(string body) => new(body, Encoding.UTF8, "application/json");

    [Fact(DisplayName = "FR-103: CQ-AP D2: serialised as a boolean; an absent key reads false, an explicit true reads true")]
    public void WireFormat()
    {
        var json = JsonSerializer.Serialize(new DecoderConfig { CqApEnabled = true }, AppJsonContext.Default.DecoderConfig);
        json.Should().Contain("\"cqApEnabled\":true");
        JsonSerializer.Deserialize(json, AppJsonContext.Default.DecoderConfig)!.CqApEnabled.Should().BeTrue();
        JsonSerializer.Deserialize("""{"kMinScorePass2":10}""", AppJsonContext.Default.DecoderConfig)!.CqApEnabled.Should().BeFalse("an absent key reads false (default OFF)");
    }

    [Fact(DisplayName = "FR-103: CQ-AP D2: POST /api/v1/config is an overlay - a partial post leaves the flag as it was, a post with only the key changes only it")]
    public async Task PostConfig_Overlay_ChangesOnlyThatKey()
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig() with { Decoder = new DecoderConfig { KMinScorePass2 = 11, CqApEnabled = true } });
        var client = _factory.CreateClient();

        // A partial post that does not mention the key leaves an explicit true as it was.
        var r1 = await client.PostAsync("/api/v1/config", Json("""{"decoder":{"kMinScorePass2":12}}"""));
        r1.StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder!.KMinScorePass2.Should().Be(12);
        store.Current.Decoder.CqApEnabled.Should().BeTrue("an overlay without the key keeps an explicit true");

        // A post with only the key changes only it.
        var r2 = await client.PostAsync("/api/v1/config", Json("""{"decoder":{"cqApEnabled":false}}"""));
        r2.StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder!.CqApEnabled.Should().BeFalse();
        store.Current.Decoder.KMinScorePass2.Should().Be(12, "only the key in the body changed");

        var r3 = await client.PostAsync("/api/v1/config", Json("""{"decoder":{"cqApEnabled":true}}"""));
        r3.StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder!.CqApEnabled.Should().BeTrue();
        store.Current.Decoder.KMinScorePass2.Should().Be(12);
    }
}
