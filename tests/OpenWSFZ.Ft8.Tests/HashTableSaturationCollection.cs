using System.Collections.Generic;
using System.Linq;
using Xunit;
using Xunit.Abstractions;
using Xunit.Sdk;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Dedicated xUnit collection for <see cref="HashedCallsignResolutionTests"/>, whose
/// <c>HashTableSaturation_RejectsNewEntriesOnceFull_ExistingEntriesSurvive</c> test
/// deliberately and <b>permanently</b> fills the native shim's process-global,
/// never-reset <c>g_session_hash_table</c> (256-slot capacity) with 264 distinct new
/// nonstandard-callsign entries — that is the test's entire point (proving the D3
/// reject-when-full guard fires). See <see cref="RunHashTableSaturationCollectionLastOrderer"/>
/// for why this collection is pinned to run strictly last in the assembly.
/// </summary>
[CollectionDefinition(Name)]
public sealed class HashTableSaturationCollectionDefinition
{
    /// <summary>
    /// The collection name, referenced by both <see cref="HashedCallsignResolutionTests"/>
    /// (via <c>[Collection(Name)]</c>) and <see cref="RunHashTableSaturationCollectionLastOrderer"/>.
    /// </summary>
    public const string Name = "Native hash-table saturation (must run last)";
}

/// <summary>
/// Root-cause fix for the f-003-ap-assist-nonstandard-callsigns flaky-decode-test dev-task
/// (dev-tasks/2026-07-05-f-003-ap-assist-flaky-decode-test.md, AC-1/AC-2/AC-3).
///
/// <para>
/// <b>Root cause (confirmed via repeated full-suite <c>dotnet test</c> runs with TRX
/// timeline capture, not merely hypothesised):</b> <c>dotnet test</c>'s assembly-wide test
/// execution order is <em>not</em> stable across runs in this environment — the same
/// binary, run twice with no code changes, produced two different orderings (confirmed:
/// <c>F003ApAssistNonstandardCallsignDecodeTests</c>'s test ran at TRX index 191, after
/// <c>HashTableSaturation_RejectsNewEntriesOnceFull_ExistingEntriesSurvive</c> at index 37,
/// in a run that failed; and at index 115, before that same saturation test at index 178,
/// in a run that passed). <c>[assembly: CollectionBehavior(DisableTestParallelization =
/// true)]</c> (see <c>AssemblyInfo.cs</c>) guarantees tests never run <em>concurrently</em>
/// (preventing the unsynchronized-native-struct race that attribute's own doc comment
/// describes) but says nothing about the <em>sequence</em> collections run in — xUnit does
/// not otherwise guarantee a stable cross-class ordering absent an explicit orderer.
/// </para>
/// <para>
/// The saturation test fills <c>g_session_hash_table</c> (native, process-global, 256-slot,
/// never reset for the process's lifetime — design D1/D3, no new P/Invoke surface) to
/// capacity with 264 distinct new entries, by design (that is what proves the
/// reject-when-full guard, D3, actually fires). Once <c>tbl->count</c> reaches 256, EVERY
/// subsequent <c>hash_table_add</c> call in the process — regardless of which test or
/// class calls it — is silently dropped (<c>ft8_shim.c</c>'s <c>hash_table_add</c>, the
/// <c>if (tbl->count >= HASH_TABLE_SIZE) { ...; return; }</c> guard). Any test that needs
/// the shim to learn a genuinely <em>new</em> nonstandard-callsign hash entry after that
/// point is affected — including
/// <c>F003ApAssistNonstandardCallsignDecodeTests.ApDecode_NonstandardCallsignCoChannel_RecoversResolvedPlaintext</c>'s
/// cycle-1 Type 4 announcement of a callsign unique to that test. When the saturation test
/// happens to run first, that announcement is silently dropped; cycle 2's AP-assisted
/// decode still succeeds structurally (LDPC converges — the co-channel message is
/// recovered, confirmed via the decoded text <c>"Q1OFZ &lt;...&gt; JO33"</c> observed in a
/// failing run) but the hiscall hash can never resolve to plaintext, so the test's final
/// assertion (which requires the resolved literal callsign, not the placeholder) fails.
/// This is <em>not</em> the LDPC/decode-margin timing sensitivity originally hypothesised
/// in the dev-task write-up (AC-2) — that hypothesis is refuted by the observed failure
/// text itself, which shows a fully successful AP decode of signal A, just with an
/// unresolved hash placeholder instead of a genuine convergence failure.
/// </para>
/// <para>
/// <b>Why this was missed during the initial pre-merge review:</b> a grep for the literal
/// substring <c>PackType4CqAnnounce</c> found "7 call sites" and was read as an upper bound
/// on hash-table insertions. That count is source-line occurrences, not runtime
/// invocations — <see cref="HashedCallsignResolutionTests"/>'s own private
/// <c>BuildPcmFromType4</c> helper is exactly one such call site, yet the saturation test
/// invokes it 264 times at runtime via its announce-phase batching loop, specifically
/// engineered to exceed the 256-slot cap.
/// </para>
/// <para>
/// <b>Fix (managed-code only, no native/shim/algorithm change — same category of fix as
/// the precedent <c>dev-tasks/2026-06-22-fix-ci-tls-ap-contamination.md</c> cross-test
/// native-state pollution bug):</b> pin the entire
/// <see cref="HashedCallsignResolutionTests"/> class — via
/// <c>[Collection(HashTableSaturationCollectionDefinition.Name)]</c> — to a named
/// collection that this orderer always places last among all test collections in the
/// assembly. Every other test that might need a free hash-table slot (including all of
/// <c>D001H6ApDecodeTests</c> and <c>F003ApAssistNonstandardCallsignDecodeTests</c>) is
/// therefore guaranteed to run — and have its hash-table insertions accepted — before the
/// saturation test ever executes, regardless of whatever other ordering nondeterminism
/// xUnit/the VSTest host exhibits among the remaining (default-collection) tests. This
/// does not weaken the saturation test itself: it still fills the table to capacity and
/// still proves the reject-when-full guard fires; it simply never does so before anything
/// else has had its turn.
/// </para>
/// <para>
/// Moving the whole class (not just the one saturation test method) avoids splitting its
/// private helpers (<c>BuildPcmFromType4</c>, <c>BuildPcmFromEncodedMessage</c>,
/// <c>BuildBatchedPcm</c>, <c>BatchFreqsHz</c>) across files, and is safe: none of the
/// class's other tests (cross-cycle/same-cycle resolution, never-announced placeholder)
/// depend on running <em>before</em> any other class — each uses its own fictional
/// callsigns, unique to itself, and asserts only about its own hash entries.
/// </para>
/// </summary>
public sealed class RunHashTableSaturationCollectionLastOrderer : ITestCollectionOrderer
{
    /// <inheritdoc/>
    public IEnumerable<ITestCollection> OrderTestCollections(IEnumerable<ITestCollection> testCollections)
    {
        var collections = testCollections.ToList();

        var runLast = collections
            .Where(c => c.DisplayName == HashTableSaturationCollectionDefinition.Name)
            .ToList();
        var everythingElse = collections
            .Except(runLast)
            .ToList();

        return everythingElse.Concat(runLast);
    }
}
