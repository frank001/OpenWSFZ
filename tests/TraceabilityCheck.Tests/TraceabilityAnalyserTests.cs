using FluentAssertions;
using TraceabilityCheck;
using Xunit;

namespace TraceabilityCheck.Tests;

public sealed class TraceabilityAnalyserTests
{
    [Fact(DisplayName = "P0-Tool: All requirements mapped passes the run with IsSuccess = true")]
    public void Analyse_AllMapped_IsSuccess()
    {
        var ids = new HashSet<string> { "FR-001", "FR-002" };
        var tests = new[]
        {
            new TestEntry("FR-001: First requirement test", "assembly.dll"),
            new TestEntry("FR-002: Second requirement test", "assembly.dll"),
        };

        var result = new TraceabilityAnalyser(ids, tests).Analyse();

        result.IsSuccess.Should().BeTrue();
        result.UnmappedIds.Should().BeEmpty();
        result.StaleReferences.Should().BeEmpty();
    }

    [Fact(DisplayName = "P0-Tool: Unmapped requirement fails the run and names the unmapped ID")]
    public void Analyse_UnmappedRequirement_FailsAndNamesId()
    {
        var ids = new HashSet<string> { "FR-001", "FR-002" };
        var tests = new[]
        {
            new TestEntry("FR-001: Only first is covered", "assembly.dll"),
        };

        var result = new TraceabilityAnalyser(ids, tests).Analyse();

        result.IsSuccess.Should().BeFalse();
        result.UnmappedIds.Should().ContainSingle(id => id == "FR-002");
    }

    [Fact(DisplayName = "P0-Tool: Test referencing a deleted requirement surfaces a stale reference")]
    public void Analyse_StaleReference_FailsAndNamesTestAndId()
    {
        var ids = new HashSet<string> { "FR-001" };
        var tests = new[]
        {
            new TestEntry("FR-001: Valid test", "assembly.dll"),
            new TestEntry("FR-999: Test referencing nonexistent ID", "assembly.dll"),
        };

        var result = new TraceabilityAnalyser(ids, tests).Analyse();

        result.IsSuccess.Should().BeFalse();
        result.StaleReferences.Should().ContainSingle(r => r.Id == "FR-999");
    }

    [Fact(DisplayName = "P0-Tool: Tests without leading IDs are ignored by the analyser")]
    public void Analyse_TestsWithoutIds_AreIgnored()
    {
        var ids = new HashSet<string> { "FR-001" };
        var tests = new[]
        {
            new TestEntry("FR-001: Valid test", "assembly.dll"),
            new TestEntry("A test with no ID prefix at all", "assembly.dll"),
        };

        var result = new TraceabilityAnalyser(ids, tests).Analyse();

        result.IsSuccess.Should().BeTrue();
    }

    [Fact(DisplayName = "P0-Tool: Empty requirement set with no tests produces a passing result")]
    public void Analyse_EmptyIdsAndTests_IsSuccess()
    {
        var ids = new HashSet<string>();
        var tests = Array.Empty<TestEntry>();

        var result = new TraceabilityAnalyser(ids, tests).Analyse();

        result.IsSuccess.Should().BeTrue();
    }

    [Fact(DisplayName = "P0-Tool: One test can map multiple requirements simultaneously")]
    public void Analyse_MultiIdTest_MapsMultipleRequirements()
    {
        var ids = new HashSet<string> { "FR-001", "NFR-002" };
        var tests = new[]
        {
            new TestEntry("FR-001, NFR-002: Covers both requirements", "assembly.dll"),
        };

        var result = new TraceabilityAnalyser(ids, tests).Analyse();

        result.IsSuccess.Should().BeTrue();
        result.Mapping["FR-001"].Should().ContainSingle();
        result.Mapping["NFR-002"].Should().ContainSingle();
    }
}
