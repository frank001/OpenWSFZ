using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using FluentAssertions;
using Microsoft.AspNetCore.Mvc.Testing;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Tests for the read-only decoder-parameter page, <c>web/decoder-params.html</c>
/// (decoder-param-readout, shim 20260054, FR-077).
/// <para>
/// This project's web tests are integration tests over the SERVED HTML and static assets
/// (<see cref="StaticAssetsIntegrationTests"/>); there is no DOM library. So these tests assert what a
/// served-text check can honestly assert: the page contains no form control, the "Not included" note
/// is present and complete, the editable settings block is unchanged, and the page script can only
/// issue the one GET. The behaviours that need a real DOM (every API entry rendered with the API's
/// value; no editable control ANYWHERE in the rendered page) are verified with Playwright against a
/// running daemon (tasks.md 7.2) and by <c>web/js/decoderParams.test.js</c> for the data shaping.
/// </para>
/// </summary>
[Trait("Category", "Integration")]
public sealed class DecoderParamsPageTests : IClassFixture<WebTestFactory>
{
    private readonly HttpClient _client;

    public DecoderParamsPageTests(WebTestFactory factory)
    {
        var webDir = Path.Combine(AppContext.BaseDirectory, "web");
        Directory.Exists(webDir).Should().BeTrue($"the 'web/' directory must exist at '{webDir}'");
        _client = factory.CreateClient(new WebApplicationFactoryClientOptions
        {
            BaseAddress = new Uri("http://127.0.0.1"),
            AllowAutoRedirect = true,
        });
    }

    private async Task<string> GetText(string path)
    {
        var response = await _client.GetAsync(path);
        response.StatusCode.Should().Be(HttpStatusCode.OK, $"{path} must be served");
        return await response.Content.ReadAsStringAsync();
    }

    /// <summary>The ids of the "Not included" note's entries. The completion record reports exactly these.</summary>
    private static readonly string[] ExpectedNotIncluded =
    [
        "wf-db-quantisation",
        "hash-probe-multiplier",
        "hash-ambiguity-rule",
        "sync-neighbourhood",
        "waterfall-frontend",
        "bp-tanh-approximation",
        // Added after QA's S1-f(ii) review; ruled TUNING by the Architect (DENSITY-REMEDY spec §13):
        // one entry covering BOTH sites of the noise-floor median, disclosed, not tabled, no rebuild.
        "noise-floor-median",
    ];

    // ── the page is served and carries no control ────────────────────────────

    [Fact(DisplayName = "FR-077: GET /decoder-params.html returns 200 text/html and loads the page script and the shared stylesheet")]
    public async Task Page_IsServed_AndReferencesItsAssets()
    {
        var response = await _client.GetAsync("/decoder-params.html");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        response.Content.Headers.ContentType?.MediaType.Should().Be("text/html");
        var body = await response.Content.ReadAsStringAsync();
        body.Should().Contain("src=\"js/decoderParams.js\"").And.Contain("href=\"css/app.css\"");

        (await _client.GetAsync("/js/decoderParams.js")).StatusCode.Should().Be(HttpStatusCode.OK);
    }

    [Fact(DisplayName = "FR-077: the page contains no input, select, textarea, button or form element")]
    public async Task Page_HasNoEditableControl()
    {
        string html = await GetText("/decoder-params.html");
        string withoutComments = Regex.Replace(html, "<!--.*?-->", "", RegexOptions.Singleline);

        Regex.Matches(withoutComments, @"<\s*(input|select|textarea|button|form)\b", RegexOptions.IgnoreCase)
             .Select(m => m.Value).Should().BeEmpty(
                 "a read-only readout must contain no control that could edit or mutate anything");
        Regex.Matches(withoutComments, @"\son(click|change|input|submit)\s*=", RegexOptions.IgnoreCase)
             .Should().BeEmpty("no inline handler either");
    }

    [Fact(DisplayName = "FR-077: the page script builds no form control and can issue only the one GET (no other verb, no direct fetch)")]
    public async Task PageScript_CanOnlyReadThroughTheGetWrapper()
    {
        string js = await GetText("/js/decoderParams.js");
        string api = await GetText("/js/api.js");

        Regex.Matches(js, @"createElement\(\s*['""](input|select|textarea|button|form)['""]", RegexOptions.IgnoreCase)
             .Should().BeEmpty("the script must not create a form control");
        js.Should().NotContain("fetch(", "the only request is the shared getDecoderParams() wrapper");
        Regex.Matches(js, @"\bmethod\s*:", RegexOptions.IgnoreCase).Should().BeEmpty("no request with an explicit verb");
        js.Should().Contain("getDecoderParams");

        var wrapper = Regex.Match(api, @"export function getDecoderParams\(\)\s*\{(?<body>[^}]*)\}");
        wrapper.Success.Should().BeTrue("api.js must export getDecoderParams()");
        wrapper.Groups["body"].Value.Should().Contain("fetchJson('/api/v1/decoder/params')")
            .And.NotContain("method", "the wrapper is a plain GET");
    }

    // ── the "Not included" note ──────────────────────────────────────────────

    [Fact(DisplayName = "FR-077: the page carries a static \"Not included\" note listing exactly the literals the audit left out, and says no value is derived")]
    public async Task Page_CarriesTheNotIncludedNote()
    {
        string html = await GetText("/decoder-params.html");

        html.Should().Contain("id=\"not-included\"", "an empty note is a statement, a missing one is silence");
        var listed = Regex.Matches(html, @"<li\s+data-status=""not-included""\s+data-literal=""(?<id>[^""]+)""")
                          .Select(m => m.Groups["id"].Value).ToArray();
        listed.Should().BeEquivalentTo(ExpectedNotIncluded,
            "the note must list exactly the numeric tuning literals the D12 audit reports as not tabled");

        // The derived-value statement: a derived value is never excluded as protocol.
        html.Should().Contain("data-literal=\"derived-none\"");
        html.Should().Contain("K_FREQ_OSR").And.Contain("K_TIME_OSR",
            "the 3.125 Hz sub-bin and the half-symbol step are derived from these, not protocol");
    }

    [Fact(DisplayName = "FR-077: every \"Not included\" entry states its location and a reason, and each doubt is marked")]
    public async Task NotIncludedEntries_StateLocationAndReason()
    {
        string html = await GetText("/decoder-params.html");
        var items = Regex.Matches(html, @"<li\s+data-status=""not-included""[^>]*>(?<body>.*?)</li>", RegexOptions.Singleline)
                         .Select(m => m.Groups["body"].Value).ToArray();

        items.Should().HaveCount(ExpectedNotIncluded.Length);
        foreach (string item in items)
        {
            item.Should().MatchRegex(@"\.[ch]</code>:\d+", "each entry must give a file:line location, written <code>file.c</code>:LINE");
            item.Should().Contain("Not tabled", "each entry must say why it is not in the table");
        }
    }

    [Fact(DisplayName = "FR-077: there is exactly ONE noise-floor-median entry, naming both sites and stating the percentile, noise_raw, occupancy and SNR doubt without claiming a defect")]
    public async Task NoiseFloorMedianEntry_CoversBothSites_AndStatesTheDoubt()
    {
        string html = await GetText("/decoder-params.html");

        Regex.Matches(html, @"data-literal=""noise-floor-median""").Should().HaveCount(1,
            "one id for both sites, so a test can hold them together (Architect §13.2)");
        var li = Regex.Match(html, @"<li\s+data-status=""not-included""\s+data-literal=""noise-floor-median"">(?<body>.*?)</li>",
                             RegexOptions.Singleline);
        li.Success.Should().BeTrue("the entry is a not-included <li>");
        // tags stripped and whitespace collapsed: the source wraps sentences across lines
        string text = Regex.Replace(Regex.Replace(li.Groups["body"].Value, "<[^>]+>", " "), @"\s+", " ");

        text.Should().Contain("ft8_shim.c").And.Contain(":1146").And.Contain(":1392",
            "it must name both the global and the local site");
        foreach (string word in new[] { "percentile", "noise_raw", "occupancy", "SNR", "Doubt", "Not tabled" })
            text.Should().ContainEquivalentOf(word, $"the entry must speak to '{word}'");
        text.Should().Contain("same percentile", "the two sites must not diverge");
        text.Should().ContainEquivalentOf("not a finding", "the disclosure is not a claim that 50% is wrong");
        text.Should().Contain("arms no sweep");
        html.Should().Contain("data-literal=\"derived-none\"", "the derived-values statement is kept");
    }

    [Fact(DisplayName = "FR-077: the page says it lists every NUMERIC parameter, and says non-numeric choices are not shown")]
    public async Task Page_ClaimsNumericParametersOnly()
    {
        string html = await GetText("/decoder-params.html");

        html.Should().Contain("Every numeric parameter", "a numeric audit cannot see non-numeric decoder choices");
        html.Should().NotContain("Every parameter of", "the unqualified claim would overstate what the audit can see");
        html.Should().Contain("non-numeric decoder choices");
    }

    /// <summary>Reads a repository source file (found by walking up to OpenWSFZ.slnx), or fails loudly.</summary>
    private static string RepoText(string relative)
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null && !File.Exists(Path.Combine(dir.FullName, "OpenWSFZ.slnx")))
            dir = dir.Parent;
        dir.Should().NotBeNull("the note's claims are checked against the repository sources (no OpenWSFZ.slnx above the test output)");
        return File.ReadAllText(Path.Combine(dir!.FullName, relative.Replace('/', Path.DirectorySeparatorChar)));
    }

    /// <summary>Blanks C comments and string literals (newlines kept), so only CODE is searched.</summary>
    private static string CodeOnly(string source)
        => Regex.Replace(source, @"/\*.*?\*/|//[^\r\n]*|""(?:\\.|[^""\\])*""",
                         m => Regex.Replace(m.Value, @"[^\r\n]", " "), RegexOptions.Singleline);

    [Fact(DisplayName = "FR-077: each literal the \"Not included\" note cites still exists in the source it cites (the note cannot go stale silently)")]
    public void NotIncludedNote_CitesLiteralsThatStillExist()
    {
        string shim    = CodeOnly(RepoText("src/OpenWSFZ.Ft8/Native/ft8_shim.c"));
        string decode  = CodeOnly(RepoText("native/ft8_lib_build/patched/ft8/decode.c"));
        string monitor = CodeOnly(RepoText("native/ft8_lib_build/patched/common/monitor.c"));
        string ldpc    = CodeOnly(RepoText("native/ft8_lib_vendor/ft8/ldpc.c"));

        // If one of these literals is later hoisted and tabled, its entry must leave the note (and the
        // ledger in DecoderParamReadoutTests must gain the row): this failing is the prompt to do that.
        Regex.Matches(shim, @"\*\s*0\.5f\s*-\s*120\.0f").Should().HaveCount(3, "wf-db-quantisation: the three inverse sites in ft8_shim.c");
        monitor.Should().MatchRegex(@"2\s*\*\s*db\s*\+\s*240", "wf-db-quantisation: the encoder it inverts");
        Regex.Matches(shim, @"h10\s*\*\s*23\b").Should().HaveCount(3, "hash-probe-multiplier: three identical sites");
        Regex.Matches(shim, @"multiplicity\s*>=\s*2|count\s*>=\s*2").Should().HaveCountGreaterThanOrEqualTo(3, "hash-ambiguity-rule");
        decode.Should().Contain("p8[sm - 1]").And.Contain("p8[sm + 1]", "sync-neighbourhood");
        monitor.Should().MatchRegex(@"2\.0f\s*/\s*me->nfft", "waterfall-frontend");
        ldpc.Should().Contain("4.97f", "bp-tanh-approximation");

        // noise-floor-median: exactly two sites (global and local), and they MUST carry the same
        // percentile. A divergence is a defect, not a tuning option (Architect §13.2), so this holds
        // the two together: change one and not the other and this fails.
        var median = Regex.Matches(shim, @"if\s*\(\s*cum\s*\*\s*(?<p>\d+)\s*>=\s*\(uint32_t\)total\s*\)");
        median.Should().HaveCount(2, "compute_noise_floor (global) and compute_local_noise_floor_db (local)");
        median.Select(m => m.Groups["p"].Value).Distinct().Should().ContainSingle(
            "the global and local noise-floor estimators must select the same percentile");
    }

    // ── settings.html: one link; the editable block is unchanged ─────────────

    private const string AdvancedBlockPattern = "<details id=\"advanced-decoder-settings\">.*?</details>";

    /// <summary>
    /// SHA-256 of the <c>#advanced-decoder-settings</c> block (line endings normalised to LF, since a
    /// Windows checkout converts them) as it stood BEFORE decoder-param-readout, taken from
    /// <c>git show 6cb98c52:web/settings.html</c> (the change's base commit).
    /// <para>
    /// This is a pin on the pre-change bytes, NOT on the current ones: it can only move if the block is
    /// edited, which is exactly what the "existing Advanced Decoder Settings section is unchanged"
    /// requirement forbids for this change. A later change that legitimately edits the block must move
    /// it, with its own justification.
    /// </para>
    /// </summary>
    private const string AdvancedBlockSha256BeforeThisChange =
        "d564ed25a3739b5410183558a54417202fbcde9e00dd57e5b4c9f67a938255fc";

    [Fact(DisplayName = "FR-077: settings.html links to the page, and its #advanced-decoder-settings block is byte-for-byte unchanged")]
    public async Task SettingsPage_HasOneLink_AndTheEditableBlockIsUnchanged()
    {
        string html = (await GetText("/settings.html")).Replace("\r\n", "\n");

        Regex.Matches(html, "href=\"decoder-params.html\"").Should().HaveCount(1, "exactly one link to the new page");

        var block = Regex.Match(html, AdvancedBlockPattern, RegexOptions.Singleline);
        block.Success.Should().BeTrue("the #advanced-decoder-settings block must still exist");
        Regex.Matches(html, "id=\"advanced-decoder-settings\"").Should().HaveCount(1);

        string sha = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(block.Value))).ToLowerInvariant();
        sha.Should().Be(AdvancedBlockSha256BeforeThisChange,
            "the read-only page sits BESIDE the editable section; it must not change it");

        block.Value.Should().NotContain("decoder-params.html", "the link belongs outside the editable block");
    }
}
