using FluentAssertions;
using Microsoft.Extensions.DependencyInjection;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Text;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// COH-FB-AUDIO: <c>decoder.coherentFallbackAudio</c> through the config API. HK-035: the POST is an overlay (a body without the key keeps the stored
/// value; a body with only the key changes only it); the value is on the wire by name; an invalid name behaves exactly as an invalid
/// <c>decodingDepth</c> does (no new behaviour).
/// </summary>
[Trait("Category", "Integration")]
public sealed class CoherentFallbackAudioApiTests : IClassFixture<WebTestFactory>
{
    private readonly WebTestFactory _factory;

    public CoherentFallbackAudioApiTests(WebTestFactory factory) => _factory = factory;

    private static StringContent Json(string body) => new(body, Encoding.UTF8, "application/json");

    [Fact(DisplayName = "FR-099: COH-FB-AUDIO: serialised by name; an absent key reads Both")]
    public void WireFormat()
    {
        var json = JsonSerializer.Serialize(new DecoderConfig { CoherentFallbackAudio = CoherentFallbackAudio.Both }, AppJsonContext.Default.DecoderConfig);
        json.Should().Contain("\"coherentFallbackAudio\":\"Both\"");
        JsonSerializer.Deserialize(json, AppJsonContext.Default.DecoderConfig)!.CoherentFallbackAudio.Should().Be(CoherentFallbackAudio.Both);
        JsonSerializer.Deserialize("""{"kMinScorePass2":10}""", AppJsonContext.Default.DecoderConfig)!
            .CoherentFallbackAudio.Should().Be(CoherentFallbackAudio.Both);
    }

    [Fact(DisplayName = "FR-099: COH-FB-AUDIO: POST /api/v1/config is an overlay - posting only the key changes only that key; a body without it keeps it")]
    public async Task PostConfig_Overlay_ChangesOnlyThatKey()
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig() with { Decoder = new DecoderConfig { KMinScorePass2 = 11, CoherentFallbackMultiSet = false } });
        var client = _factory.CreateClient();

        var r1 = await client.PostAsync("/api/v1/config", Json("""{"decoder":{"coherentFallbackAudio":"Both"}}"""));
        r1.StatusCode.Should().Be(HttpStatusCode.OK);
        var d = store.Current.Decoder!;
        d.CoherentFallbackAudio.Should().Be(CoherentFallbackAudio.Both);
        d.KMinScorePass2.Should().Be(11, "only the key in the body changed");
        d.CoherentFallbackMultiSet.Should().BeFalse("only the key in the body changed");
        d.DecodingDepth.Should().Be(DecodingDepth.Deep);

        var r2 = await client.PostAsync("/api/v1/config", Json("""{"decoder":{"kMinScorePass2":12}}"""));
        r2.StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder!.KMinScorePass2.Should().Be(12);
        store.Current.Decoder.CoherentFallbackAudio.Should().Be(CoherentFallbackAudio.Both, "an overlay without the key keeps an explicit value");

        var r3 = await client.PostAsync("/api/v1/config", Json("""{"decoder":{"coherentFallbackAudio":"original"}}"""));
        r3.StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder!.CoherentFallbackAudio.Should().Be(CoherentFallbackAudio.Original, "names are read case-insensitively");
    }

    [Fact(DisplayName = "FR-099: COH-FB-AUDIO: an invalid value is not accepted, behaves exactly as an invalid decodingDepth does, and changes nothing")]
    public async Task PostConfig_InvalidValue_BehavesLikeOtherEnums()
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig() with { Decoder = new DecoderConfig { CoherentFallbackAudio = CoherentFallbackAudio.Both } });
        var client = _factory.CreateClient();

        var bad = await client.PostAsync("/api/v1/config", Json("""{"decoder":{"coherentFallbackAudio":"Everything"}}"""));
        var badDepth = await client.PostAsync("/api/v1/config", Json("""{"decoder":{"decodingDepth":"Everything"}}"""));

        ((int)bad.StatusCode).Should().Be((int)badDepth.StatusCode, "an invalid name for this enum behaves exactly as for decodingDepth");
        bad.StatusCode.Should().NotBe(HttpStatusCode.OK);
        store.Current.Decoder!.CoherentFallbackAudio.Should().Be(CoherentFallbackAudio.Both, "the refused body changed nothing");
    }
}
