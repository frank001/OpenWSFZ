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
