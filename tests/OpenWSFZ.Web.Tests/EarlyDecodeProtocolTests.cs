using System.Net.Http.Json;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using FluentAssertions;
using Microsoft.Extensions.DependencyInjection;
using OpenWSFZ.Abstractions;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// decode-early-batch-panel (FR-083) tasks 6.2 and 7.2: the panel protocol and the config fields.
///
/// <para>
/// 🔴 The existing <c>decode</c> frame must stay <b>byte-identical</b> when no early rows are involved (acceptance A1).
/// The expected literal below is the frame's shape before the early decode existed: the same record, camelCase, nulls
/// written, no <c>resolves</c> key. 🔒 NFR-021: synthetic Q-prefix messages only.
/// </para>
/// </summary>
public sealed class EarlyDecodeProtocolTests
{
    private static readonly DecodeResult Row = new("15:30:00", -12, 0.3, 1234, "Q1AW Q1TTT EN43");

    private const string RowJson =
        """{"time":"15:30:00","snr":-12,"dt":0.3,"freqHz":1234,"message":"Q1AW Q1TTT EN43","region":null,"workedBefore":null,"band":null}""";

    [Fact(DisplayName = "FR-083: 6.2a the decode frame with no early rows is byte-identical to the pre-change frame (no resolves key at all)")]
    public void DecodeFrame_WithoutResolves_IsTheUnchangedShape()
    {
        var json = JsonSerializer.Serialize(new WsDecodeMessage("decode", [Row]), AppJsonContext.Default.WsDecodeMessage);

        json.Should().Be("{\"type\":\"decode\",\"payload\":[" + RowJson + "]}");
        json.Should().NotContain("resolves");
    }

    [Fact(DisplayName = "FR-083: 6.2b the hub's broadcast path with resolves null writes that same unchanged frame")]
    public void DecodeFrame_ResolvesNull_EqualsTheOverloadWithNoResolves()
    {
        var plain = JsonSerializer.Serialize(new WsDecodeMessage("decode", [Row]), AppJsonContext.Default.WsDecodeMessage);
        var nulled = JsonSerializer.Serialize(new WsDecodeMessage("decode", [Row], Resolves: null), AppJsonContext.Default.WsDecodeMessage);

        nulled.Should().Be(plain);
    }

    [Fact(DisplayName = "FR-083: 6.2c the decode frame carries the optional resolves list: confirmed with the final index, unconfirmed without one")]
    public void DecodeFrame_WithResolves_CarriesTheList()
    {
        var resolves = new List<EarlyResolution>
        {
            new(7, EarlyResolution.Confirmed, 0),
            new(8, EarlyResolution.Unconfirmed),
        };
        var json = JsonSerializer.Serialize(new WsDecodeMessage("decode", [Row], resolves), AppJsonContext.Default.WsDecodeMessage);

        json.Should().Be("{\"type\":\"decode\",\"payload\":[" + RowJson + "],\"resolves\":["
                       + "{\"earlyId\":7,\"outcome\":\"confirmed\",\"finalIndex\":0},"
                       + "{\"earlyId\":8,\"outcome\":\"unconfirmed\"}]}");
    }

    [Fact(DisplayName = "FR-083: 6.2d an empty batch 1 with resolves is a valid decode frame")]
    public void DecodeFrame_EmptyBatchWithResolves()
    {
        var json = JsonSerializer.Serialize(
            new WsDecodeMessage("decode", [], [new EarlyResolution(9, EarlyResolution.Unconfirmed)]),
            AppJsonContext.Default.WsDecodeMessage);

        json.Should().Be("{\"type\":\"decode\",\"payload\":[],\"resolves\":[{\"earlyId\":9,\"outcome\":\"unconfirmed\"}]}");
    }

    [Fact(DisplayName = "FR-083: 6.2e the decode-early frame is its own message type, each row carrying its earlyId")]
    public void EarlyFrame_Shape()
    {
        var json = JsonSerializer.Serialize(
            new WsEarlyDecodeMessage("decode-early", [new EarlyRow(7, Row)]), AppJsonContext.Default.WsEarlyDecodeMessage);

        json.Should().Be("{\"type\":\"decode-early\",\"payload\":[{\"earlyId\":7,\"decode\":" + RowJson + "}]}");
    }

    // ── config (7.2) ──────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-083: 7.2a the defaults are earlyDecodeEnabled TRUE (ON by default, the Captain's decision of 2026-10-04) and earlyDecodeCutSeconds 2.0")]
    public void Defaults()
    {
        var d = new DecoderConfig();
        d.EarlyDecodeEnabled.Should().BeTrue("ON by default");
        d.EarlyDecodeCutSeconds.Should().Be(2.0);
        DecoderConfig.MinEarlyDecodeCutSeconds.Should().Be(0.5);
        DecoderConfig.MaxEarlyDecodeCutSeconds.Should().Be(3.0);
    }
}

/// <summary>The early-decode config fields through <c>POST /api/v1/config</c> (clamp, overlay, HK-035).</summary>
[Trait("Category", "Integration")]
public sealed class EarlyDecodeConfigApiTests : IClassFixture<WebTestFactory>
{
    private readonly WebTestFactory _factory;

    public EarlyDecodeConfigApiTests(WebTestFactory factory) => _factory = factory;

    private async Task<HttpResponseMessage> PostAsync(string decoderJson)
    {
        var client = _factory.CreateClient();
        var body = "{\"decoder\":{\"kMinScorePass2\":10,\"osdCorrThreshold\":0.10,\"osdNhardMax\":40" + decoderJson + "}}";
        return await client.PostAsync("/api/v1/config", new StringContent(body, Encoding.UTF8, "application/json"));
    }

    [Fact(DisplayName = "FR-083: 7.2b a POST that sets earlyDecodeEnabled and earlyDecodeCutSeconds stores them")]
    public async Task Post_SetsBothFields()
    {
        var resp = await PostAsync(",\"earlyDecodeEnabled\":true,\"earlyDecodeCutSeconds\":2.5");

        resp.StatusCode.Should().Be(System.Net.HttpStatusCode.OK);
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        store.Current.Decoder!.EarlyDecodeEnabled.Should().BeTrue();
        store.Current.Decoder.EarlyDecodeCutSeconds.Should().Be(2.5);
    }

    [Theory(DisplayName = "FR-083: 7.2c earlyDecodeCutSeconds is clamped to 0.5 to 3.0")]
    [InlineData("9", 3.0)]
    [InlineData("0.1", 0.5)]
    [InlineData("-4", 0.5)]
    [InlineData("0.5", 0.5)]
    [InlineData("3", 3.0)]
    public async Task Post_ClampsTheCut(string sent, double expected)
    {
        var resp = await PostAsync(",\"earlyDecodeCutSeconds\":" + sent);

        resp.StatusCode.Should().Be(System.Net.HttpStatusCode.OK);
        var loaded = await resp.Content.ReadFromJsonAsync(AppJsonContext.Default.AppConfig);
        loaded!.Decoder!.EarlyDecodeCutSeconds.Should().Be(expected);
    }

    [Fact(DisplayName = "FR-083: 7.2d (HK-035) a partial POST that omits both fields leaves them as they were")]
    public async Task PartialPost_LeavesBothFieldsAsTheyWere()
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig() with
        {
            Decoder = new DecoderConfig { EarlyDecodeEnabled = true, EarlyDecodeCutSeconds = 1.5 },
        });

        var resp = await PostAsync("");                           // the decoder section, without either early field

        resp.StatusCode.Should().Be(System.Net.HttpStatusCode.OK);
        store.Current.Decoder!.EarlyDecodeEnabled.Should().BeTrue("an overlay keeps what the body did not mention");
        store.Current.Decoder.EarlyDecodeCutSeconds.Should().Be(1.5);

        // And a POST with no decoder section at all leaves them too.
        var client = _factory.CreateClient();
        (await client.PostAsync("/api/v1/config", new StringContent("{}", Encoding.UTF8, "application/json")))
            .StatusCode.Should().Be(System.Net.HttpStatusCode.OK);
        store.Current.Decoder!.EarlyDecodeEnabled.Should().BeTrue();
        store.Current.Decoder.EarlyDecodeCutSeconds.Should().Be(1.5);
    }

    [Fact(DisplayName = "FR-083: 7.2e (HK-035) a stored DEFAULT (true, never set by anyone) survives a partial POST that does not name the field")]
    public async Task PartialPost_KeepsTheDefaultTrue()
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig() with { Decoder = new DecoderConfig() });
        store.Current.Decoder!.EarlyDecodeEnabled.Should().BeTrue("precondition: the code default");

        var resp = await PostAsync("");

        resp.StatusCode.Should().Be(System.Net.HttpStatusCode.OK);
        store.Current.Decoder!.EarlyDecodeEnabled.Should().BeTrue();
    }

    [Fact(DisplayName = "FR-083: 7.2f a POST of earlyDecodeEnabled false turns it off and persists, and a later partial POST keeps it off")]
    public async Task ExplicitFalse_TurnsItOff_AndStaysOff()
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig() with { Decoder = new DecoderConfig() });

        var off = await PostAsync(",\"earlyDecodeEnabled\":false");

        off.StatusCode.Should().Be(System.Net.HttpStatusCode.OK);
        store.Current.Decoder!.EarlyDecodeEnabled.Should().BeFalse();
        var loaded = await off.Content.ReadFromJsonAsync(AppJsonContext.Default.AppConfig);
        loaded!.Decoder!.EarlyDecodeEnabled.Should().BeFalse("the response shows the stored value");

        (await PostAsync("")).StatusCode.Should().Be(System.Net.HttpStatusCode.OK);   // a partial POST that does not name it
        store.Current.Decoder!.EarlyDecodeEnabled.Should().BeFalse("an explicit false is not reset by a save that does not mention it");
    }
}

/// <summary>The early frames through a real WebSocket, to prove the hub sends them to the panel.</summary>
public sealed class EarlyDecodeWebSocketTests : IClassFixture<RealServerFixture>
{
    private readonly RealServerFixture _fixture;

    public EarlyDecodeWebSocketTests(RealServerFixture fixture) => _fixture = fixture;

    private Uri WsUri() => new($"ws://127.0.0.1:{_fixture.Port}/api/v1/ws");

    private static async Task<string?> ReadFrameOfTypeAsync(ClientWebSocket ws, string type)
    {
        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(5));
        var buf = new byte[16 * 1024];
        while (true)
        {
            var sb = new StringBuilder();
            WebSocketReceiveResult r;
            do
            {
                r = await ws.ReceiveAsync(buf, cts.Token);
                sb.Append(Encoding.UTF8.GetString(buf, 0, r.Count));
            } while (!r.EndOfMessage);

            using var doc = JsonDocument.Parse(sb.ToString());
            if (doc.RootElement.GetProperty("type").GetString() == type) return sb.ToString();
        }
    }

    [Fact(DisplayName = "FR-083: 6.2f a WebSocket client receives the decode-early frame, and the decode frame with resolves, from the event bus")]
    public async Task Client_ReceivesEarlyFrame_AndResolvingDecodeFrame()
    {
        using var ws = new ClientWebSocket();
        await ws.ConnectAsync(WsUri(), CancellationToken.None);

        var bus = new DecodeEventBus(_fixture.AppScope);
        var row = new DecodeResult("15:30:00", -12, 0.3, 1234, "Q1AW Q1TTT EN43");

        await bus.PublishEarly([new EarlyRow(41, row)]);
        var early = await ReadFrameOfTypeAsync(ws, "decode-early");
        using (var doc = JsonDocument.Parse(early!))
        {
            var first = doc.RootElement.GetProperty("payload")[0];
            first.GetProperty("earlyId").GetInt64().Should().Be(41);
            first.GetProperty("decode").GetProperty("message").GetString().Should().Be("Q1AW Q1TTT EN43");
        }

        await bus.Publish([row], [new EarlyResolution(41, EarlyResolution.Confirmed, 0)]);
        var final = await ReadFrameOfTypeAsync(ws, "decode");
        using (var doc = JsonDocument.Parse(final!))
        {
            var resolves = doc.RootElement.GetProperty("resolves");
            resolves.GetArrayLength().Should().Be(1);
            resolves[0].GetProperty("earlyId").GetInt64().Should().Be(41);
            resolves[0].GetProperty("outcome").GetString().Should().Be("confirmed");
            resolves[0].GetProperty("finalIndex").GetInt32().Should().Be(0);
        }

        // The ordinary overload still writes no resolves key.
        await bus.Publish([row]);
        var plain = await ReadFrameOfTypeAsync(ws, "decode");
        plain.Should().NotContain("resolves");
    }
}
