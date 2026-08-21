using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Ft8;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// tasks.md 8.4 (fix-cycle-boundary-clock-drift): <see cref="Ft8Decoder.DecodeAsync"/> must log
/// <c>hashTableRejectCount</c> once per cycle at Information level, alongside the existing
/// decode-elapsed-time line, so a future live endurance run can reconcile it from the raw daemon
/// log the same way decode elapsed time already can — instead of needing ad hoc
/// <c>GET /api/v1/status</c> polling mid-session
/// (dev-tasks/2026-07-24-cycleframer-correction-not-converging-live-evidence.md, Evidence 5 and
/// its 8.2 reconciliation addendum, which found this specific gap: elapsed time was already
/// reconcilable from the raw log, hashTableRejectCount was not).
///
/// <para>
/// Uses the <see cref="IFt8NativeInterop"/> injection seam (same pattern as
/// <see cref="D005MessageTrimTests"/>) so the native DLL is never loaded and the returned
/// reject-count value is fully controlled by the test, independent of
/// <see cref="HashTableRejectCountTests"/>'s real-shim run-order constraints.
/// </para>
/// </summary>
public sealed class HashTableRejectCountLoggingTests
{
    // ── Test double ───────────────────────────────────────────────────────────

    /// <summary>
    /// Fake interop returning a fixed, caller-controlled hash-table reject count and an empty
    /// decode result set — this test only cares about the reject-count log line, not decode
    /// output.
    /// </summary>
    private sealed class FixedRejectCountInterop(int rejectCount) : IFt8NativeInterop
    {
        public int MaxDecodePasses => 2;

        public Ft8NativeResult[] DecodeAll(float[] pcm) => [];

        public int[]  GetLastPassCounts(int maxPasses)      => [0, 0];
        public int[]  GetLastCandidateCounts(int maxPasses) => [0, 0];
        public float  GetLastNoiseFloorDb()                  => -70.0f;
        public int    GetHashTableRejectCount()              => rejectCount;
        public (float[] MeanAbs, float[] PrenormVariance, int[] FailCount) GetLastLlrStats(int maxPasses)
            => (new float[maxPasses], new float[maxPasses], new int[maxPasses]);

        public void SetApBits(byte[] mycallBits, byte[] hiscallBits) { /* no-op */ }
        public void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax) { /* no-op */ }

        public (float DeltaFreqHz, float DeltaTimeS, float SyncScore, int CoarseDtSamp, int FineDtSamp) RefineCandidate(
            float[] pcm, int coarseFreqHz, float coarseTimeOffsetS) => (0f, 0f, 0f, 0, 0);

        public float[] CoherentLlrAt(float[] pcm, float freqHz, float timeOffsetS) => new float[174];
    }

    /// <summary>
    /// <see cref="ILogger{T}"/> that records every log entry for assertion — local to this file
    /// rather than shared, mirroring <c>CycleFramerTests</c>' and <c>OpenWSFZ.Audio.Tests</c>'
    /// equivalent test doubles.
    /// </summary>
    private sealed class RecordingLogger<T> : ILogger<T>
    {
        private readonly List<(LogLevel Level, string Message)> _entries = new();
        private readonly object _lock = new();

        public IReadOnlyList<(LogLevel Level, string Message)> Entries
        {
            get { lock (_lock) return [.. _entries]; }
        }

        IDisposable? ILogger.BeginScope<TState>(TState state) => null;
        bool ILogger.IsEnabled(LogLevel logLevel) => true;

        void ILogger.Log<TState>(
            LogLevel logLevel,
            EventId eventId,
            TState state,
            Exception? exception,
            Func<TState, Exception?, string> formatter)
        {
            var msg = formatter(state, exception);
            lock (_lock) _entries.Add((logLevel, msg));
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    /// <summary>
    /// Returns a 180 000-sample PCM buffer well above the silence guard (1e-6 RMS) — the guard
    /// must not be tripped, or DecodeAsync returns before reaching the reject-count log line.
    /// </summary>
    private static float[] BuildLoudPcm()
    {
        var pcm = new float[180_000];
        for (int i = 0; i < pcm.Length; i++)
            pcm[i] = 0.1f;
        return pcm;
    }

    // ── Tests ─────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "tasks.md 8.4: DecodeAsync logs hashTableRejectCount at Information level once per cycle")]
    public async Task DecodeAsync_EveryCycle_LogsHashTableRejectCountAtInformation()
    {
        const int rejectCount = 42;
        var logger  = new RecordingLogger<Ft8Decoder>();
        var interop = new FixedRejectCountInterop(rejectCount);
        var decoder = new Ft8Decoder(
            new FakeClock(new DateTime(2026, 7, 24, 9, 0, 0, DateTimeKind.Utc)),
            logger,
            interop);

        await decoder.DecodeAsync(BuildLoudPcm(), CancellationToken.None);

        logger.Entries.Should().Contain(
            e => e.Level == LogLevel.Information
                 && e.Message.Contains("hashTableRejectCount")
                 && e.Message.Contains(rejectCount.ToString()),
            "hashTableRejectCount must be logged at Information level every cycle (the same " +
            "cadence and level as the existing decode-elapsed-time line), carrying the value " +
            "GetHashTableRejectCount() actually returned, so a raw daemon log can reconstruct a " +
            "session-long trend without needing ad hoc /api/v1/status polling");
    }

    [Fact(DisplayName = "tasks.md 8.4: hashTableRejectCount log line reflects a zero count, not just a truthy non-zero one")]
    public async Task DecodeAsync_ZeroRejectCount_LogsZeroExplicitly()
    {
        var logger  = new RecordingLogger<Ft8Decoder>();
        var interop = new FixedRejectCountInterop(rejectCount: 0);
        var decoder = new Ft8Decoder(
            new FakeClock(new DateTime(2026, 7, 24, 9, 0, 0, DateTimeKind.Utc)),
            logger,
            interop);

        await decoder.DecodeAsync(BuildLoudPcm(), CancellationToken.None);

        logger.Entries.Should().Contain(
            e => e.Level == LogLevel.Information
                 && e.Message.Contains("hashTableRejectCount=0"),
            "a zero reject count must still be logged explicitly every cycle (regular cadence, " +
            "not conditional on a non-zero/truthy value) so a session's early, unsaturated " +
            "cycles establish a proper baseline for the later trend analysis this logging exists " +
            "to support");
    }
}
