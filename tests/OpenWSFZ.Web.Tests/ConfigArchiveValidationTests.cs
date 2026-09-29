using FluentAssertions;
using Microsoft.Extensions.DependencyInjection;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Text;
using System.Text.Json.Nodes;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Part C server side (design D5): validation of <c>cycleAudioArchive</c> follows how
/// <c>CycleArchiveService</c> actually treats each value — see design.md D5 for the reading.
/// </summary>
[Trait("Category", "Integration")]
public sealed class ConfigArchiveValidationTests
{
    private static Task<HttpResponseMessage> PostAsync(HttpClient client, string json)
        => client.PostAsync("/api/v1/config", new StringContent(json, Encoding.UTF8, "application/json"));

    private static async Task<JsonNode> ArchiveAsync(HttpClient client)
        => JsonNode.Parse(await client.GetStringAsync("/api/v1/config"))!["cycleAudioArchive"]!;

    [Theory(DisplayName = "D5: maxSizeMb below 1 is rejected (0 or negative would make the sweep delete the whole archive); nothing is persisted")]
    [InlineData(0)]
    [InlineData(-5)]
    public async Task MaxSizeMb_BelowMinimum_Is400(int value)
    {
        using var factory = new WebTestFactory();
        var client = factory.CreateClient();
        var before = (await ArchiveAsync(client)).ToJsonString();

        (await PostAsync(client, $$"""{ "cycleAudioArchive": { "mode": "all", "maxSizeMb": {{value}} } }"""))
            .StatusCode.Should().Be(HttpStatusCode.BadRequest);

        (await ArchiveAsync(client)).ToJsonString().Should().Be(before);
    }

    [Theory(DisplayName = "D5: maxAgeHours outside [1, 87600] is rejected")]
    [InlineData(0)]
    [InlineData(-1)]
    [InlineData(87_601)]
    [InlineData(int.MaxValue)]
    public async Task MaxAgeHours_OutOfRange_Is400(int value)
    {
        using var factory = new WebTestFactory();
        var client = factory.CreateClient();
        var before = (await ArchiveAsync(client)).ToJsonString();

        (await PostAsync(client, $$"""{ "cycleAudioArchive": { "maxAgeHours": {{value}} } }"""))
            .StatusCode.Should().Be(HttpStatusCode.BadRequest);

        (await ArchiveAsync(client)).ToJsonString().Should().Be(before);
    }

    [Fact(DisplayName = "D5: the boundary values 1 MB, 1 h and 87600 h are accepted")]
    public async Task Boundaries_AreAccepted()
    {
        using var factory = new WebTestFactory();
        var client = factory.CreateClient();

        (await PostAsync(client, """{ "cycleAudioArchive": { "maxSizeMb": 1, "maxAgeHours": 1 } }"""))
            .StatusCode.Should().Be(HttpStatusCode.OK);
        (await PostAsync(client, """{ "cycleAudioArchive": { "maxAgeHours": 87600 } }"""))
            .StatusCode.Should().Be(HttpStatusCode.OK);

        var a = await ArchiveAsync(client);
        a["maxSizeMb"]!.GetValue<int>().Should().Be(1);
        a["maxAgeHours"]!.GetValue<int>().Should().Be(87600);
    }

    [Fact(DisplayName = "D5: a stored out-of-range value (file-edited) does not block an unrelated save, and is left unchanged")]
    public async Task StoredOutOfRange_DoesNotBlockUnrelatedSave()
    {
        using var factory = new WebTestFactory();
        var client = factory.CreateClient();
        await factory.Services.GetRequiredService<IConfigStore>().SaveAsync(new AppConfig
        {
            CycleAudioArchive = new CycleAudioArchiveConfig(maxSizeMb: 0, maxAgeHours: 0),
        });

        (await PostAsync(client, """{ "showCycleCountdown": true }""")).StatusCode.Should().Be(HttpStatusCode.OK);

        var a = await ArchiveAsync(client);
        a["maxSizeMb"]!.GetValue<int>().Should().Be(0, "a save must never change a setting it did not send");
        a["maxAgeHours"]!.GetValue<int>().Should().Be(0);
    }

    [Theory(DisplayName = "Part C: all four modes (off, all, decoded, noDecodes) are accepted and round-trip")]
    [InlineData("off")]
    [InlineData("all")]
    [InlineData("decoded")]
    [InlineData("noDecodes")]
    public async Task AllFourModes_RoundTrip(string mode)
    {
        using var factory = new WebTestFactory();
        var client = factory.CreateClient();

        (await PostAsync(client, $$"""{ "cycleAudioArchive": { "mode": "{{mode}}" } }""")).StatusCode
            .Should().Be(HttpStatusCode.OK);

        (await ArchiveAsync(client))["mode"]!.GetValue<string>().Should().Be(mode);
    }

    [Fact(DisplayName = "Part C: an unknown mode is a 400, not a silent reset")]
    public async Task UnknownMode_Is400()
    {
        using var factory = new WebTestFactory();
        var client = factory.CreateClient();
        await PostAsync(client, """{ "cycleAudioArchive": { "mode": "all" } }""");

        (await PostAsync(client, """{ "cycleAudioArchive": { "mode": "sometimes" } }""")).StatusCode
            .Should().Be(HttpStatusCode.BadRequest);

        (await ArchiveAsync(client))["mode"]!.GetValue<string>().Should().Be("all");
    }

    [Fact(DisplayName = "Part C: an explicit null directory is stored (blank field = default location)")]
    public async Task NullDirectory_IsStored()
    {
        using var factory = new WebTestFactory();
        var client = factory.CreateClient();
        await PostAsync(client, """{ "cycleAudioArchive": { "directory": "X" } }""");

        (await PostAsync(client, """{ "cycleAudioArchive": { "directory": null } }""")).StatusCode
            .Should().Be(HttpStatusCode.OK);

        (await ArchiveAsync(client))["directory"].Should().BeNull();
    }
}
