using FluentAssertions;
using Microsoft.Extensions.DependencyInjection;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// third-pass-deep (#240 step 1, B1 / B6): <c>decoder.decodingDepth</c> through the config API (overlay, name on the
/// wire) and the read-back of the depth in use plus the third pass's counters on <c>GET /api/v1/status</c>.
/// </summary>
[Trait("Category", "Integration")]
public sealed class DecodingDepthApiTests : IClassFixture<WebTestFactory>
{
    private readonly WebTestFactory _factory;

    public DecodingDepthApiTests(WebTestFactory factory) => _factory = factory;

    [Fact(DisplayName = "B1: decoder.decodingDepth is serialised by name, and an absent key reads Normal")]
    public void DecodingDepth_WireFormat()
    {
        var deepJson = JsonSerializer.Serialize(
            new DecoderConfig { DecodingDepth = DecodingDepth.Deep }, AppJsonContext.Default.DecoderConfig);
        deepJson.Should().Contain("\"decodingDepth\":\"Deep\"");
        JsonSerializer.Deserialize(deepJson, AppJsonContext.Default.DecoderConfig)!
            .DecodingDepth.Should().Be(DecodingDepth.Deep);

        JsonSerializer.Deserialize("""{"kMinScorePass2":10}""", AppJsonContext.Default.DecoderConfig)!
            .DecodingDepth.Should().Be(DecodingDepth.Normal, "a config file written before the key existed loads Normal");
    }

    [Fact(DisplayName = "B1: POST /api/v1/config is an overlay for decodingDepth — a body without the key keeps the stored value, one with it changes only it")]
    public async Task PostConfig_Overlay_KeepsAndChangesDecodingDepth()
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig() with { Decoder = new DecoderConfig { DecodingDepth = DecodingDepth.Deep } });
        var client = _factory.CreateClient();

        // A decoder body that does not mention the key must not reset it (HK-035: overlay, not replace).
        const string withoutKey = """{"decoder":{"kMinScorePass2":12}}""";
        var r1 = await client.PostAsync("/api/v1/config", new StringContent(withoutKey, Encoding.UTF8, "application/json"));
        r1.StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder!.KMinScorePass2.Should().Be(12);
        store.Current.Decoder.DecodingDepth.Should().Be(DecodingDepth.Deep, "the overlay keeps keys the body does not carry");

        const string toNormal = """{"decoder":{"decodingDepth":"Normal"}}""";
        var r2 = await client.PostAsync("/api/v1/config", new StringContent(toNormal, Encoding.UTF8, "application/json"));
        r2.StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder.DecodingDepth.Should().Be(DecodingDepth.Normal);
        store.Current.Decoder.KMinScorePass2.Should().Be(12, "only the key in the body changed");
    }

    [Fact(DisplayName = "B1+B6: GET /api/v1/status reports thirdPass with the depth in use (Normal by default) and the counters, all 0")]
    public async Task Status_ReportsThirdPass()
    {
        var client = _factory.CreateClient();

        var resp = await client.GetAsync("/api/v1/status");

        resp.StatusCode.Should().Be(HttpStatusCode.OK);
        using var doc = JsonDocument.Parse(await resp.Content.ReadAsStringAsync());
        doc.RootElement.TryGetProperty("thirdPass", out var tp).Should().BeTrue("status carries the third pass block");
        tp.GetProperty("decodingDepth").GetString().Should().Be("Normal");
        foreach (var name in new[] { "runs", "skippedNoNew", "skippedAbandoned", "abandoned", "failed", "decodes" })
            tp.GetProperty(name).GetInt64().Should().Be(0, $"thirdPass.{name} stays 0 while the depth is Normal");
    }
}
