using FluentAssertions;
using Microsoft.Extensions.DependencyInjection;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Net.Http.Json;
using System.Text;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// OSD-FIX R4: the config API accepts osdNhardMax in [24, 100] (the lowest value TEST measured is the lowest allowed), and the
/// server-owned marker nhard24MigrationApplied survives a Settings-shaped save. All values are synthetic.
/// </summary>
[Trait("Category", "Integration")]
public sealed class Nhard24ApiTests : IClassFixture<WebTestFactory>
{
    private readonly WebTestFactory _factory;
    public Nhard24ApiTests(WebTestFactory factory) => _factory = factory;

    private async Task<int> PostNhardAsync(int nhard)
    {
        var client = _factory.CreateClient();
        var body = $"{{\"decoder\":{{\"kMinScorePass2\":10,\"osdCorrThreshold\":0.10,\"osdNhardMax\":{nhard}}}}}";
        var resp = await client.PostAsync("/api/v1/config", new StringContent(body, Encoding.UTF8, "application/json"));
        resp.StatusCode.Should().Be(HttpStatusCode.OK);
        var loaded = await resp.Content.ReadFromJsonAsync(AppJsonContext.Default.AppConfig);
        return loaded!.Decoder!.OsdNhardMax;
    }

    [Theory(DisplayName = "FR-085: POST osdNhardMax is accepted in [24, 100] and clamped outside it")]
    [InlineData(24, 24)]
    [InlineData(30, 30)]
    [InlineData(100, 100)]
    [InlineData(23, 24)]
    [InlineData(0, 24)]
    [InlineData(101, 100)]
    public async Task Post_OsdNhardMax_Range(int posted, int expected)
        => (await PostNhardAsync(posted)).Should().Be(expected);

    [Fact(DisplayName = "FR-085: a Settings-shaped POST (no markers on the wire) leaves nhard24MigrationApplied as stored, and 24 stays 24")]
    public async Task SettingsSave_KeepsStoredNhard24Marker_AndTwentyFour()
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig() with
        {
            Decoder = new DecoderConfig(osdNhardMax: 24, nhard40MigrationApplied: true, nhard24MigrationApplied: true),
        });
        (await PostNhardAsync(24)).Should().Be(24, "the first Settings save must not turn 24 into 30");
        store.Current.Decoder!.Nhard24MigrationApplied.Should().BeTrue("the stored value is kept");

        await store.SaveAsync(new AppConfig() with
        {
            Decoder = new DecoderConfig(osdNhardMax: 40, nhard40MigrationApplied: true, nhard24MigrationApplied: false),
        });
        _ = await PostNhardAsync(40);
        store.Current.Decoder!.Nhard24MigrationApplied.Should().BeFalse("a body without the marker cannot set it");
    }

    [Fact(DisplayName = "FR-085: a body that sends nhard24MigrationApplied cannot change the stored marker")]
    public async Task BodyMarker_CannotChangeStored()
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig() with
        {
            Decoder = new DecoderConfig(osdNhardMax: 40, nhard40MigrationApplied: true, nhard24MigrationApplied: false),
        });
        var client = _factory.CreateClient();
        const string body = """{"decoder":{"osdNhardMax":40,"nhard24MigrationApplied":true}}""";
        (await client.PostAsync("/api/v1/config", new StringContent(body, Encoding.UTF8, "application/json")))
            .StatusCode.Should().Be(HttpStatusCode.OK);
        store.Current.Decoder!.Nhard24MigrationApplied.Should().BeFalse();
    }

    [Fact(DisplayName = "FR-085: a POST that CREATES the decoder section stores nhard24MigrationApplied true")]
    public async Task PostCreatingDecoderSection_MarkerTrue()
    {
        var store = _factory.Services.GetRequiredService<IConfigStore>();
        await store.SaveAsync(new AppConfig() with { Decoder = null });
        store.Current.Decoder.Should().BeNull();

        _ = await PostNhardAsync(40);

        store.Current.Decoder!.OsdNhardMax.Should().Be(40);
        store.Current.Decoder.Nhard24MigrationApplied.Should().BeTrue("no persisted 40 can have existed");
    }

    [Fact(DisplayName = "FR-085: settings.html allows 24 (min=24, max=100) and states the [24-100] range")]
    public async Task SettingsPage_InputRangeAllows24()
    {
        var html = await _factory.CreateClient().GetStringAsync("/settings.html");
        var start = html.IndexOf("id=\"decoder-nhard\"", StringComparison.Ordinal);
        start.Should().BeGreaterThan(0);
        var tag = html.Substring(start, 120);
        tag.Should().Contain("min=\"24\"").And.Contain("max=\"100\"");
        html.Should().NotContain("[30–100]").And.Contain("[24–100]");
    }

    [Fact(DisplayName = "FR-085: settings.js falls back to 24, not 40")]
    public async Task SettingsScript_FallbackIs24()
    {
        var js = await _factory.CreateClient().GetStringAsync("/js/settings.js");
        js.Should().Contain("dec.osdNhardMax      ?? 24").And.Contain("decoderNhardRaw : 24,").And.Contain("decoderNhard.value = '24';");
        js.Should().NotContain("dec.osdNhardMax      ?? 40");
    }
}
