using FluentAssertions;
using TraceabilityCheck;
using Xunit;

namespace TraceabilityCheck.Tests;

/// <summary>
/// Tests for debt-exclusion behaviour in <see cref="TraceabilityAnalyser"/>.
/// Task 4.10 extension — grace-period / debt-file scenarios.
/// </summary>
public sealed class TraceabilityAnalyserDebtTests
{
    // -------------------------------------------------------------------------
    // Grace-period exclusion (C1 check)
    // -------------------------------------------------------------------------

    [Fact(DisplayName = "P0-Tool: Debt ID without a test is excluded from the missing-mapping failure")]
    public void Analyse_UnmappedDebtId_IsNotReportedAsMissing()
    {
        var ids = new HashSet<string> { "FR-001", "FR-002" };
        var tests = new[]
        {
            new TestEntry("FR-001: Covered requirement", "assembly.dll"),
        };
        // FR-002 has no test, but is listed as debt.
        var debtIds = new HashSet<string> { "FR-002" };

        var result = new TraceabilityAnalyser(ids, tests, debtIds).Analyse();

        result.IsSuccess.Should().BeTrue();
        result.UnmappedIds.Should().NotContain("FR-002");
    }

    [Fact(DisplayName = "P0-Tool: Non-debt unmapped ID still fails even when a debt file is present")]
    public void Analyse_NonDebtUnmappedId_StillFails()
    {
        var ids = new HashSet<string> { "FR-001", "FR-002", "FR-003" };
        var tests = new[]
        {
            new TestEntry("FR-001: Covered requirement", "assembly.dll"),
        };
        // FR-002 is in debt (excluded). FR-003 is not in debt and has no test.
        var debtIds = new HashSet<string> { "FR-002" };

        var result = new TraceabilityAnalyser(ids, tests, debtIds).Analyse();

        result.IsSuccess.Should().BeFalse();
        result.UnmappedIds.Should().ContainSingle(id => id == "FR-003");
        result.UnmappedIds.Should().NotContain("FR-002");
    }

    [Fact(DisplayName = "P0-Tool: All requirements in debt with no tests produces a passing result")]
    public void Analyse_AllIdsInDebt_NoTests_IsSuccess()
    {
        var ids = new HashSet<string> { "FR-001", "NFR-001" };
        var tests = Array.Empty<TestEntry>();
        var debtIds = new HashSet<string> { "FR-001", "NFR-001" };

        var result = new TraceabilityAnalyser(ids, tests, debtIds).Analyse();

        result.IsSuccess.Should().BeTrue();
        result.UnmappedIds.Should().BeEmpty();
    }

    [Fact(DisplayName = "P0-Tool: Debt ID that is also covered by a test counts as mapped (debt entry is redundant but harmless)")]
    public void Analyse_DebtIdAlsoCovered_IsStillMappedSuccessfully()
    {
        var ids = new HashSet<string> { "FR-001" };
        var tests = new[]
        {
            new TestEntry("FR-001: This requirement now has a test", "assembly.dll"),
        };
        // FR-001 is in debt AND has a test — the debt entry is redundant but must not cause a failure.
        var debtIds = new HashSet<string> { "FR-001" };

        var result = new TraceabilityAnalyser(ids, tests, debtIds).Analyse();

        result.IsSuccess.Should().BeTrue();
        result.Mapping["FR-001"].Should().ContainSingle();
    }

    // -------------------------------------------------------------------------
    // Stale debt check
    // -------------------------------------------------------------------------

    [Fact(DisplayName = "P0-Tool: Stale debt ID (not in REQUIREMENTS.md) is reported as a stale reference")]
    public void Analyse_StaleDebtId_IsReportedAsStaleReference()
    {
        var ids = new HashSet<string> { "FR-001" };
        var tests = new[]
        {
            new TestEntry("FR-001: Valid test", "assembly.dll"),
        };
        // FR-999 is in the debt file but does not exist in REQUIREMENTS.md.
        var debtIds = new HashSet<string> { "FR-001", "FR-999" };

        var result = new TraceabilityAnalyser(ids, tests, debtIds).Analyse();

        result.IsSuccess.Should().BeFalse();
        result.StaleReferences.Should().ContainSingle(r => r.Id == "FR-999");
    }

    [Fact(DisplayName = "P0-Tool: Stale debt reference names the debt file as the source in the stale-reference report")]
    public void Analyse_StaleDebtId_ReportsDebtFileAsSource()
    {
        var ids = new HashSet<string> { "FR-001" };
        var tests = new[]
        {
            new TestEntry("FR-001: Valid test", "assembly.dll"),
        };
        var debtIds = new HashSet<string> { "FR-001", "NFR-999" };

        var result = new TraceabilityAnalyser(ids, tests, debtIds).Analyse();

        result.StaleReferences
            .Should().ContainSingle(r => r.Id == "NFR-999")
            .Which.TestName.Should().Contain("debt");
    }

    // -------------------------------------------------------------------------
    // Null / empty debt set
    // -------------------------------------------------------------------------

    [Fact(DisplayName = "P0-Tool: Passing null debtIds to TraceabilityAnalyser behaves identically to an empty set")]
    public void Analyse_NullDebtIds_BehavesLikeEmptySet()
    {
        var ids = new HashSet<string> { "FR-001" };
        var tests = new[]
        {
            new TestEntry("FR-001: Valid test", "assembly.dll"),
        };

        // null debtIds — constructor should default to empty set.
        var result = new TraceabilityAnalyser(ids, tests, debtIds: null).Analyse();

        result.IsSuccess.Should().BeTrue();
    }
}
