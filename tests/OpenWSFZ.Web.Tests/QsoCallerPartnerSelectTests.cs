using FluentAssertions;
using OpenWSFZ.Abstractions;
using System.Net;
using System.Text;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Integration tests for <c>POST /api/v1/tx/caller-partner-select</c> (FR-PILEUP-001).
/// Verifies that the endpoint persists the mode to config, returns 200 with the
/// updated callerPartnerSelect field, and rejects invalid mode strings with 400.
///
/// Uses <see cref="TxAnswerCqFixture"/> — a real Kestrel instance backed by
/// <see cref="TestConfigStore"/> and <see cref="MockQsoController"/>.
/// </summary>
[Collection("caller-partner-select-tests")]
public sealed class QsoCallerPartnerSelectTests : IClassFixture<TxAnswerCqFixture>
{
    private readonly TxAnswerCqFixture _fixture;

    public QsoCallerPartnerSelectTests(TxAnswerCqFixture fixture)
        => _fixture = fixture;

    private static StringContent ModeBody(string mode)
        => new($$"""{"mode":"{{mode}}"}""", Encoding.UTF8, "application/json");

    // ── Test 1: None → 200, persists CallerPartnerSelectMode.None ────────────

    [Fact(DisplayName = "FR-PILEUP-001a: POST /tx/caller-partner-select None → 200, callerPartnerSelect='None', config saved")]
    public async Task PostCallerPartnerSelect_None_UpdatesConfigAndReturns200()
    {
        // Arrange — start from the default First.
        await _fixture.ConfigStore.SaveAsync(new AppConfig
        {
            Tx = new TxConfig(callerPartnerSelect: CallerPartnerSelectMode.First),
        });

        // Act
        var response = await _fixture.Client.PostAsync(
            "/api/v1/tx/caller-partner-select", ModeBody("None"));

        // Assert HTTP 200
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        // Assert response body callerPartnerSelect = "None"
        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.GetProperty("callerPartnerSelect").GetString()
            .Should().Be("None",
                "endpoint must echo the new mode in the response");

        // Assert config was persisted
        _fixture.ConfigStore.Current.Tx?.CallerPartnerSelect
            .Should().Be(CallerPartnerSelectMode.None,
                "config store must be updated with CallerPartnerSelectMode.None");
    }

    // ── Test 2: First → 200, persists CallerPartnerSelectMode.First ──────────

    [Fact(DisplayName = "FR-PILEUP-001b: POST /tx/caller-partner-select First → 200, callerPartnerSelect='First', config saved")]
    public async Task PostCallerPartnerSelect_First_UpdatesConfigAndReturns200()
    {
        // Arrange — start from None so we can confirm the round-trip.
        await _fixture.ConfigStore.SaveAsync(new AppConfig
        {
            Tx = new TxConfig(callerPartnerSelect: CallerPartnerSelectMode.None),
        });

        // Act
        var response = await _fixture.Client.PostAsync(
            "/api/v1/tx/caller-partner-select", ModeBody("First"));

        // Assert HTTP 200
        response.StatusCode.Should().Be(HttpStatusCode.OK);

        // Assert response body callerPartnerSelect = "First"
        var body = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(body);
        doc.RootElement.GetProperty("callerPartnerSelect").GetString()
            .Should().Be("First");

        // Assert config was persisted
        _fixture.ConfigStore.Current.Tx?.CallerPartnerSelect
            .Should().Be(CallerPartnerSelectMode.First);
    }

    // ── Test 3: Invalid mode → 400 ───────────────────────────────────────────

    [Fact(DisplayName = "FR-PILEUP-001c: POST /tx/caller-partner-select with invalid mode → 400")]
    public async Task PostCallerPartnerSelect_InvalidMode_Returns400()
    {
        // Act
        var response = await _fixture.Client.PostAsync(
            "/api/v1/tx/caller-partner-select", ModeBody("Banana"));

        // Assert HTTP 400
        response.StatusCode.Should().Be(HttpStatusCode.BadRequest,
            "endpoint must reject mode values other than 'First' and 'None'");
    }
}
