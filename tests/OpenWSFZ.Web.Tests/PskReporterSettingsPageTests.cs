using System.Net;
using System.Text.RegularExpressions;
using FluentAssertions;
using Microsoft.AspNetCore.Mvc.Testing;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// FR-094 (issue #262): the Settings page's PSK Reporter control, as served. The browser half (ticking, typing, saving against a real daemon)
/// is the committed Playwright acceptance <c>tests/web-ui/settings-psk-reporter.playwright.mjs</c>; the posted key set is also fixed by
/// <c>settings-payload-shape.json</c> and <c>web/js/settingsPayload.test.js</c>.
/// </summary>
public sealed class PskReporterSettingsPageTests : IClassFixture<WebTestFactory>
{
    private const string OptInText =
        "Sends the calls and locators of stations you receive, with your call and locator, to the public PSK Reporter service.";

    private readonly HttpClient _client;

    public PskReporterSettingsPageTests(WebTestFactory factory)
        => _client = factory.CreateClient(new WebApplicationFactoryClientOptions { BaseAddress = new Uri("http://127.0.0.1") });

    private async Task<string> GetAsync(string path)
    {
        var response = await _client.GetAsync(path);
        response.StatusCode.Should().Be(HttpStatusCode.OK, path);
        return await response.Content.ReadAsStringAsync();
    }

    private static string Flatten(string html) => Regex.Replace(Regex.Replace(html, "<[^>]+>", " "), @"\s+", " ");

    [Fact(DisplayName = "FR-094: the Settings page has a checkbox for pskReporter.enabled and an antenna text field, with the stated opt-in text, in the External Programs tab")]
    public async Task Page_HasCheckbox_AntennaField_AndOptInText()
    {
        var html = await GetAsync("/settings.html");

        html.Should().MatchRegex("""<input[^>]*type="checkbox"[^>]*id="psk-reporter-enabled"|<input[^>]*id="psk-reporter-enabled"[^>]*type="checkbox"\s""");
        html.Should().MatchRegex("""<input[^>]*type="text"[^>]*id="psk-reporter-antenna"|<input[^>]*id="psk-reporter-antenna"[^>]*type="text"\s""");
        Flatten(html).Should().Contain(OptInText);

        int tabStart = html.IndexOf("id=\"tab-external-programs\"", StringComparison.Ordinal);
        int tabEnd   = html.IndexOf("<!-- /tab-external-programs -->", StringComparison.Ordinal);
        int box      = html.IndexOf("id=\"psk-reporter-enabled\"", StringComparison.Ordinal);
        (tabStart >= 0 && tabEnd > tabStart && box > tabStart && box < tabEnd).Should().BeTrue("the control sits in the External Programs tab");
    }

    [Fact(DisplayName = "FR-094: host and port are configuration-file only - no input for them on the page, and settings.js posts only enabled and antennaInformation")]
    public async Task HostAndPort_AreNotOnThePage_AndNotPosted()
    {
        var html = await GetAsync("/settings.html");
        var js   = await GetAsync("/js/settings.js");

        html.Should().NotContain("psk-reporter-host").And.NotContain("psk-reporter-port");

        var post = Regex.Match(js, @"const pskReporter = \{(?<body>[^}]*)\}", RegexOptions.Singleline);
        post.Success.Should().BeTrue("settings.js builds a pskReporter object for the POST");
        var keys = Regex.Matches(post.Groups["body"].Value, @"^\s*(\w+):", RegexOptions.Multiline).Select(m => m.Groups[1].Value).ToArray();
        keys.Should().BeEquivalentTo(["enabled", "antennaInformation"]);
    }

    [Fact(DisplayName = "FR-094: the checkbox is unticked until the stored configuration says otherwise (an absent block is the inert default)")]
    public async Task Checkbox_DefaultsUnticked()
    {
        var html = await GetAsync("/settings.html");
        Regex.Match(html, """<input[^>]*id="psk-reporter-enabled"[^>]*>""").Value.Should().NotContain("checked");

        var js = await GetAsync("/js/settings.js");
        js.Should().Contain("pskReporterEnabled.checked = pskRep.enabled ?? false");
    }
}
