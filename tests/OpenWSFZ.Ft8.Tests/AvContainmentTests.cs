using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Ft8;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Tests for the SEH AV containment path (D-006 / fix/seh-av-containment, 20260013).
///
/// <para>
/// These tests exercise <see cref="Ft8Decoder.DecodeAsync"/> via a
/// <see cref="IFt8NativeInterop"/> test double that throws
/// <see cref="NativeAccessViolationException"/>, simulating an access violation
/// caught by the native shim's SEH wrapper.  The real native DLL is not loaded.
/// </para>
///
/// <para>
/// Checklist items covered:
/// <list type="bullet">
///   <item>B-2 — WARNING log emitted with cycle timestamp.</item>
///   <item>R-1 — <c>GetLastPassCounts</c> / <c>GetLastNoiseFloorDb</c> are
///     NOT called on the AV path (TLS state unreliable after AV).</item>
///   <item>R-2 — <see cref="Ft8Decoder.DecodeAsync"/> returns empty results
///     (not throws) when an AV is simulated.</item>
/// </list>
/// </para>
///
/// <para>
/// <strong>f-001-hashed-callsign-resolution (shim 20260031) coverage gap, documented per
/// that change's tasks.md 3.5:</strong> the session-scoped callsign hash table's
/// exception-path safety requirement — that <c>g_session_hash_table</c>'s contents
/// survive a caught access violation untouched, with only the thread-local
/// <c>tls_hash_table</c> pointer detached (design D2) — cannot be exercised by this test
/// class, because <see cref="ThrowingNativeInterop"/> is a pure C# fake that throws
/// <see cref="NativeAccessViolationException"/> without ever calling into the real native
/// shim; there is no mechanism here (or elsewhere in this suite) to force a genuine
/// access violation mid-decode inside <c>ft8_decode_all</c>. This is covered instead by
/// careful code review of the exception path: the <c>__except</c> handler (ft8_shim.c,
/// end of <c>ft8_decode_all</c>) only ever executes <c>tls_hash_table = NULL;</c> — it
/// does not call <c>hash_table_init</c> on <c>g_session_hash_table</c>, and no other code
/// path writes to that table from the exception handler, so its contents are provably
/// unreachable from the AV path. See design.md D2 for the full reasoning.
/// </para>
/// </summary>
public sealed class AvContainmentTests
{
    // ── Test doubles ─────────────────────────────────────────────────────────

    /// <summary>
    /// Fake interop that always throws <see cref="NativeAccessViolationException"/>
    /// from <see cref="DecodeAll"/>, simulating an AV in the native pipeline.
    /// Tracks whether the TLS-query methods were incorrectly called after the AV.
    /// </summary>
    private sealed class ThrowingNativeInterop : IFt8NativeInterop
    {
        public int  MaxDecodePasses                { get; } = 2;
        public bool GetLastPassCountsCalled        { get; private set; }
        public bool GetLastCandidateCountsCalled   { get; private set; }
        public bool GetLastNoiseFloorDbCalled      { get; private set; }
        public bool GetLastLlrStatsCalled          { get; private set; }
        public bool SetApBitsCalled                { get; private set; }

        public Ft8NativeResult[] DecodeAll(float[] pcm)
            => throw new NativeAccessViolationException();

        public int[] GetLastPassCounts(int maxPasses)
        {
            GetLastPassCountsCalled = true;
            return [];
        }

        public int[] GetLastCandidateCounts(int maxPasses)
        {
            GetLastCandidateCountsCalled = true;
            return [];
        }

        public float GetLastNoiseFloorDb()
        {
            GetLastNoiseFloorDbCalled = true;
            return 0f;
        }

        public int GetHashTableRejectCount() => 0;

        public (float[] MeanAbs, float[] PrenormVariance, int[] FailCount) GetLastLlrStats(int maxPasses)
        {
            GetLastLlrStatsCalled = true;
            return ([], [], []);
        }

        public void SetApBits(byte[] mycallBits, byte[] hiscallBits)
        {
            SetApBitsCalled = true;
        }

        public void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax) { /* no-op */ }
    }

    /// <summary>
    /// Minimal ILogger implementation that records every structured log entry.
    /// </summary>
    private sealed class CapturingLogger<T> : ILogger<T>
    {
        public List<(LogLevel Level, string Message)> Entries { get; } = [];

        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => true;

        public void Log<TState>(
            LogLevel                        logLevel,
            EventId                         eventId,
            TState                          state,
            Exception?                      exception,
            Func<TState, Exception?, string> formatter)
            => Entries.Add((logLevel, formatter(state, exception)));
    }

    // ── Tests ─────────────────────────────────────────────────────────────────

    /// <summary>
    /// R-2: DecodeAsync must return an empty list (not throw) when the native
    /// pipeline raises an access violation.  The caller must not see an exception.
    /// </summary>
    [Fact(DisplayName = "R-2: DecodeAsync returns empty results (not throws) when native AV fires")]
    public async Task DecodeAsync_NativeAv_ReturnsEmptyResults()
    {
        var clock   = new FakeClock(new DateTime(2026, 6, 14, 15, 30, 0, DateTimeKind.Utc));
        var logger  = new CapturingLogger<Ft8Decoder>();
        var interop = new ThrowingNativeInterop();
        var decoder = new Ft8Decoder(clock, logger, interop);

        var results = await decoder.DecodeAsync(BuildLoudPcm(), CancellationToken.None);

        results.Should().BeEmpty(
            "an AV in the native pipeline must cause the cycle to skip with empty results; " +
            "no exception should propagate to the caller");
    }

    /// <summary>
    /// B-2: DecodeAsync must log exactly one WARNING-level entry that includes
    /// the cycle timestamp when an AV is caught.  The cycle timestamp allows
    /// the event to be correlated with band activity logs for D-006 investigation.
    /// </summary>
    [Fact(DisplayName = "B-2: DecodeAsync logs a WARNING with the cycle timestamp on native AV")]
    public async Task DecodeAsync_NativeAv_LogsWarningWithTimestamp()
    {
        var clock   = new FakeClock(new DateTime(2026, 6, 14, 15, 30, 0, DateTimeKind.Utc));
        var logger  = new CapturingLogger<Ft8Decoder>();
        var interop = new ThrowingNativeInterop();
        var decoder = new Ft8Decoder(clock, logger, interop);

        await decoder.DecodeAsync(BuildLoudPcm(), CancellationToken.None);

        // Exactly one WARNING must appear.
        logger.Entries
            .Where(e => e.Level == LogLevel.Warning)
            .Should().ContainSingle(
                "exactly one WARNING must be logged when the native AV path is taken");

        // The WARNING message must include the cycle timestamp (HH:mm:ss).
        string warnMsg = logger.Entries.First(e => e.Level == LogLevel.Warning).Message;
        warnMsg.Should().Contain("15:30:00",
            "the WARNING must include the cycle start timestamp so the event can be " +
            "correlated with band activity logs during D-006 root-cause investigation");
    }

    /// <summary>
    /// R-1: The TLS-query methods (<c>GetLastPassCounts</c>, <c>GetLastNoiseFloorDb</c>,
    /// <c>GetLastLlrStats</c>) must NOT be called when an AV fires, because TLS state
    /// is unreliable after an access violation.  The exception-propagation mechanism
    /// must short-circuit the lambda before those calls are reached.
    /// </summary>
    [Fact(DisplayName = "R-1: TLS query methods are NOT called after native AV")]
    public async Task DecodeAsync_NativeAv_DoesNotCallTlsQueriesAfterAv()
    {
        var clock   = new FakeClock(new DateTime(2026, 6, 14, 15, 30, 0, DateTimeKind.Utc));
        var logger  = new CapturingLogger<Ft8Decoder>();
        var interop = new ThrowingNativeInterop();
        var decoder = new Ft8Decoder(clock, logger, interop);

        await decoder.DecodeAsync(BuildLoudPcm(), CancellationToken.None);

        interop.GetLastPassCountsCalled.Should().BeFalse(
            "TLS state (pass counts) is unreliable after an AV; " +
            "calling GetLastPassCounts on the AV path would log stale data");
        interop.GetLastCandidateCountsCalled.Should().BeFalse(
            "TLS state (candidate counts) is unreliable after an AV; " +
            "calling GetLastCandidateCounts on the AV path would log stale data");
        interop.GetLastNoiseFloorDbCalled.Should().BeFalse(
            "TLS state (noise floor) is unreliable after an AV; " +
            "calling GetLastNoiseFloorDb on the AV path would log stale data");
        interop.GetLastLlrStatsCalled.Should().BeFalse(
            "TLS state (LLR stats) is unreliable after an AV; " +
            "calling GetLastLlrStats on the AV path would log stale data");
        interop.SetApBitsCalled.Should().BeTrue(
            "Ft8Decoder now calls SetApBits unconditionally inside the Task.Run " +
            "lambda before DecodeAll — with no AP constraints active it calls " +
            "SetApBits([], []) to clear any TLS residue from a prior cycle; " +
            "this happens BEFORE DecodeAll throws the AV, so SetApBitsCalled is true");
    }

    // ── Helper ────────────────────────────────────────────────────────────────

    /// <summary>
    /// Returns a 180 000-sample PCM buffer with constant amplitude well above
    /// the silence guard threshold (1e-6f RMS), so the silence-guard short-circuit
    /// in <see cref="Ft8Decoder.DecodeAsync"/> does not intercept before the
    /// interop call is reached.
    /// </summary>
    private static float[] BuildLoudPcm()
    {
        var pcm = new float[180_000];
        for (int i = 0; i < pcm.Length; i++)
            pcm[i] = 0.1f;  // RMS = 0.1f >> 1e-6f threshold
        return pcm;
    }
}
