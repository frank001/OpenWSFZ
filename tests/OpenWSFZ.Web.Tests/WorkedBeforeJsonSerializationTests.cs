using System.Text.Json;
using FluentAssertions;
using OpenWSFZ.Abstractions;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Diagnostic/regression test for the <c>qso-confirmation-band-awareness</c> wire format: the
/// Captain reported every worked-before indicator rendering empty in the live UI after this
/// change, even for stations that should have matched. This verifies the actual JSON produced
/// by <see cref="AppJsonContext"/>'s source-generated serializer for <see cref="WorkedBeforeInfo"/>
/// matches what <c>web/js/main.js</c> expects (<c>"never"</c>/<c>"differentBand"</c>/<c>"thisBand"</c>
/// lowerCamelCase strings), rather than assuming the enum converter is honoured.
/// </summary>
[Trait("Category", "Unit")]
public sealed class WorkedBeforeJsonSerializationTests
{
    [Fact(DisplayName = "WorkedBeforeInfo serialises WorkedBeforeState as lowerCamelCase strings, not integers")]
    public void Serialize_WorkedBeforeInfo_ProducesExpectedStringValues()
    {
        var info = new WorkedBeforeInfo(
            Contact:   WorkedBeforeState.ThisBand,
            Country:   WorkedBeforeState.DifferentBand,
            Continent: WorkedBeforeState.Never,
            CqZone:    WorkedBeforeState.ThisBand,
            ItuZone:   WorkedBeforeState.DifferentBand);

        var json = JsonSerializer.Serialize(info, AppJsonContext.Default.WorkedBeforeInfo);

        json.Should().Contain("\"contact\":\"thisBand\"");
        json.Should().Contain("\"country\":\"differentBand\"");
        json.Should().Contain("\"continent\":\"never\"");
        json.Should().Contain("\"cqZone\":\"thisBand\"");
        json.Should().Contain("\"ituZone\":\"differentBand\"");
    }

    [Fact(DisplayName = "DecodeResult round-trips WorkedBefore through AppJsonContext without loss")]
    public void RoundTrip_DecodeResultWithWorkedBefore_PreservesValues()
    {
        var original = new DecodeResult(
            Time: "12:00:00", Snr: 5, Dt: 0.1, FreqHz: 1000, Message: "CQ Q1ABC FN42",
            Region: null,
            WorkedBefore: new WorkedBeforeInfo(
                WorkedBeforeState.ThisBand, WorkedBeforeState.Never, WorkedBeforeState.DifferentBand,
                WorkedBeforeState.Never, WorkedBeforeState.ThisBand));

        var json = JsonSerializer.Serialize(original, AppJsonContext.Default.DecodeResult);
        var roundTripped = JsonSerializer.Deserialize(json, AppJsonContext.Default.DecodeResult);

        roundTripped!.WorkedBefore.Should().Be(original.WorkedBefore);
    }
}
