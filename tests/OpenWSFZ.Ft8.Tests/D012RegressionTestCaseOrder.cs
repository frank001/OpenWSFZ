using System.Collections.Generic;
using System.Linq;
using Xunit.Abstractions;
using Xunit.Sdk;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Test-case orderer for <see cref="HashedCallsignResolutionTests"/>, applied via
/// <c>[TestCaseOrderer(...)]</c> on that class, guaranteeing
/// <c>RepeatAnnouncement_OfAlreadyKnownCallsign_DoesNotIncrementRejectCount</c>
/// (the D-012 regression test — dev-tasks/2026-07-06-d-012-hash-table-reject-count-overcounting.md)
/// always runs strictly AFTER
/// <c>HashTableSizing_264DistinctCallsigns_AllResolveWithZeroRejects</c> within that class.
///
/// <para>
/// <b>Why this is needed:</b> the D-012 regression test reuses the saturation test's own
/// guaranteed-resolvable early entry ("Q000000", its <c>callsigns[0]</c>) as the "already known"
/// callsign it re-announces, rather than storing a fresh one of its own. The native hash table
/// is process-global and never reset for the process's lifetime (design D1/D3) — once the
/// table has been permanently filled to its <c>HASH_TABLE_SIZE</c> capacity (256 when this was
/// written; 4096 since g2/shim 20260038, and only the opt-in saturation test reaches it now),
/// NO test that runs afterward can ever get a genuinely new callsign stored; it can only reuse
/// an entry already proven present. xUnit does not guarantee method-execution order within a class by default
/// (the <see cref="RunHashTableSaturationCollectionLastOrderer"/> already present in this suite
/// only controls CROSS-class/collection order, not intra-class order — a distinction confirmed
/// the hard way when an earlier draft of the D-012 test, written without this orderer, was
/// observed to run AFTER the saturation test and find its own fresh callsign silently rejected
/// by an already-full table). This orderer removes that hazard deterministically, following the
/// same "pin the fragile ordering explicitly, don't hope for the best" precedent as
/// <see cref="RunHashTableSaturationCollectionLastOrderer"/> itself.
/// </para>
/// <para>
/// All other test cases in the class keep their original relative order (LINQ's
/// <c>OrderBy</c> is a stable sort); only these two methods are pinned relative to each other,
/// both sorted after everything else in the class.
/// </para>
/// </summary>
public sealed class RunD012RegressionAfterSaturationTestCaseOrderer : ITestCaseOrderer
{
    private const string SizingTestMethodName =
        "HashTableSizing_264DistinctCallsigns_AllResolveWithZeroRejects";
    private const string D012RegressionTestMethodName =
        "RepeatAnnouncement_OfAlreadyKnownCallsign_DoesNotIncrementRejectCount";

    /// <summary>
    /// The opt-in g2 saturation test (<c>OPENWSFZ_RUN_G2_SATURATION=1</c>). When it does run it
    /// permanently fills the process-global table to its 4096-slot capacity, so it must be ranked
    /// strictly after BOTH tests above — the sizing test asserts a reject delta of exactly zero
    /// and would fail outright if a saturated table preceded it.
    /// </summary>
    private const string G2SaturationTestMethodName =
        "HashTableSaturation_AtG2Capacity_RejectsNewEntriesWithoutCorruptingExistingOnes";

    /// <inheritdoc/>
    public IEnumerable<TTestCase> OrderTestCases<TTestCase>(IEnumerable<TTestCase> testCases)
        where TTestCase : ITestCase
    {
        return testCases.OrderBy(tc => Rank(tc));
    }

    private static int Rank(ITestCase testCase) => testCase.TestMethod.Method.Name switch
    {
        SizingTestMethodName => 1,
        D012RegressionTestMethodName => 2,
        G2SaturationTestMethodName => 3,
        _ => 0,
    };
}
