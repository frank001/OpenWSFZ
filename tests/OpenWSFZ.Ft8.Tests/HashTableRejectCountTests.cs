using System.Linq;
using FluentAssertions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Tests for the read-only native hash-table reject counter surfaced by
/// <see cref="Ft8LibInterop.GetHashTableRejectCount"/>
/// (f-005-hash-table-saturation-diagnostic, shim 20260032), exercising the real native shim
/// directly (no mocking), like <see cref="HashedCallsignResolutionTests"/>.
///
/// <para>
/// <b>Run-order dependency (deliberate):</b> this class is intentionally NOT a member of
/// <see cref="HashTableSaturationCollectionDefinition"/>. That collection is pinned to run
/// strictly last by <see cref="RunHashTableSaturationCollectionLastOrderer"/> precisely
/// because its saturation test is the <em>only</em> test in the assembly that fills the
/// process-global 256-slot hash table to capacity and thereby causes any reject-when-full
/// events. Every other test — including this one — therefore runs while the table is still
/// unsaturated, so the reject counter is deterministically <c>0</c> here regardless of xUnit's
/// otherwise-unstable cross-class ordering. (See <c>HashTableSaturationCollection.cs</c> for
/// the full root-cause writeup of why that pin exists.)
/// </para>
/// <para>
/// All fictional callsigns use unique names not used elsewhere in the suite (NFR-021: Q-prefix
/// synthetic calls only).
/// </para>
/// </summary>
public sealed class HashTableRejectCountTests
{
    private const double DefaultFreqHz = 1500.0;

    // ── 4.1: counter reads zero before any saturation has occurred ────────────

    [Fact(DisplayName = "f-005: reject count is zero when the table has never been full (no discard has occurred)")]
    public void GetHashTableRejectCount_BeforeAnySaturation_ReturnsZero()
    {
        // This class never runs after the pinned-last saturation test, and no other test in
        // the assembly fills the 256-slot table, so no Type 4 announcement has ever been
        // discarded at this point — the counter must still read its fresh-process value of 0.
        Ft8LibInterop.GetHashTableRejectCount().Should().Be(0,
            "with the table never at capacity, no announcement has been rejected, so the " +
            "managed-layer reject-count read must return 0 (spec: reject count is zero when " +
            "the table has never been full)");
    }

    // ── 4.3: reading the counter has no side effects on hash resolution ───────

    [Fact(DisplayName = "f-005: reading the reject count does not reset it or disturb subsequent hash resolution")]
    public void ReadingRejectCount_HasNoSideEffects_StoredCallsignStillResolves()
    {
        const string nonstd = "Q0RDONLY"; // fictional, 8 chars, unique to this test

        // Cycle 1 — announce the callsign so it is stored in the persistent hash table.
        float[] pcm1 = BuildPcmFromType4(nonstd, DefaultFreqHz);
        var results1 = Ft8LibInterop.DecodeAll(pcm1);
        results1.Should().Contain(r => r.Message.Contains(nonstd),
            "cycle 1 must decode the Type 4 announcement and store the callsign's hash");

        // Read the counter repeatedly. Per design D3 the getter is read-only: it must neither
        // reset the counter (repeated reads return the same value) nor mutate the hash table.
        int read1 = Ft8LibInterop.GetHashTableRejectCount();
        int read2 = Ft8LibInterop.GetHashTableRejectCount();
        read2.Should().Be(read1, "reading the counter must not reset it (D3 — no reset-on-read)");

        // Cycle 2 — reference the stored callsign by hash. If reading the counter had corrupted
        // or cleared the table, this cross-cycle resolution would fail.
        float[] pcm2 = BuildPcmFromEncodedMessage($"Q1RDO2 {nonstd} JO33", DefaultFreqHz);
        var results2 = Ft8LibInterop.DecodeAll(pcm2);
        results2.Should().Contain(r => r.Message.Contains(nonstd),
            "the callsign stored in cycle 1 must still resolve in cycle 2 — reading the reject " +
            "count must not alter the hash table's contents or resolution behaviour");

        // And a read after resolution still returns the same value: neither the read nor the
        // intervening resolution path touched the counter.
        Ft8LibInterop.GetHashTableRejectCount().Should().Be(read1,
            "neither reading the counter nor performing a hash lookup may change its value");
    }

    // ── Helpers (mirrors HashedCallsignResolutionTests' private builders) ──────

    private static float[] BuildPcmFromType4(string nonstandardCallsign, double baseFreqHz)
    {
        byte[] bits = TestFt8Encoder.PackType4CqAnnounce(nonstandardCallsign);
        byte[] info = TestFt8Encoder.AppendCrc14(bits);
        byte[] cw   = TestFt8Encoder.LdpcEncode(info);
        int[]  syms = TestFt8Encoder.BitsToSymbols(cw);
        return TestFt8Encoder.SymbolsToPcm(syms, baseFreqHz);
    }

    private static float[] BuildPcmFromEncodedMessage(string message, double baseFreqHz)
    {
        var tones = new byte[Ft8LibInterop.EncodedToneCount];
        Ft8LibInterop.EncodeMessage(message, tones);
        int[] syms = new int[tones.Length];
        for (int i = 0; i < tones.Length; i++) syms[i] = tones[i];
        return TestFt8Encoder.SymbolsToPcm(syms, baseFreqHz);
    }
}
