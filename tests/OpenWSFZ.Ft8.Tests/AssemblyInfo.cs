using Xunit;

// f-001-hashed-callsign-resolution (shim 20260031): the native callsign hash table used by
// ft8_decode_all is now a process-global static (g_session_hash_table) instead of a per-call
// stack-local one, so every decode across every test class in this assembly reads/writes the
// SAME unsynchronized native struct. xUnit's default collection-per-class parallelism would let
// two test classes call ft8_decode_all/EncodeMessage at literally the same wall-clock moment,
// racing on hash_table_add/hash_table_lookup's multi-step (index compute -> probe -> write)
// logic. Disabling test parallelization for the whole assembly restores the "one caller at a
// time" invariant the native shim's design assumes (design.md D1), eliminating that race for
// every current and future test that touches the native shim.
[assembly: CollectionBehavior(DisableTestParallelization = true)]

// f-003-ap-assist-nonstandard-callsigns flaky-decode-test fix (dev-tasks/2026-07-05-f-003-ap-
// assist-flaky-decode-test.md): DisableTestParallelization (above) guarantees tests never run
// CONCURRENTLY, but says nothing about the SEQUENCE collections run in — confirmed by repeated
// full-suite runs that this assembly's cross-class test order is NOT stable across `dotnet test`
// invocations. HashedCallsignResolutionTests.HashTableSaturation_RejectsNewEntriesOnceFull_
// ExistingEntriesSurvive deliberately and permanently fills the shared, never-reset native hash
// table to its 256-slot capacity; any test that runs after it and needs a fresh slot silently
// fails to have its entry stored. This orderer pins that class's dedicated collection
// (HashTableSaturationCollectionDefinition) to run strictly last, so every other test gets its
// turn at a non-exhausted table first. See RunHashTableSaturationCollectionLastOrderer's doc
// comment (HashTableSaturationCollection.cs) for the full root-cause writeup.
[assembly: TestCollectionOrderer(
    "OpenWSFZ.Ft8.Tests.RunHashTableSaturationCollectionLastOrderer", "OpenWSFZ.Ft8.Tests")]
