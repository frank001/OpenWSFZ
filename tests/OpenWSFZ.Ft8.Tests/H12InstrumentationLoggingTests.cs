using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Ft8;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// f001-sup-b-instrumented-suppression-sizing (shim 20260047): <see cref="Ft8Decoder.DecodeAsync"/>
/// must log <c>h12Displaying</c>/<c>h12Ambiguous</c>/<c>h12Divergent</c> once per cycle at
/// Information level, alongside the existing <c>hashTableRejectCount</c> line, per spec Sec.3.3's
/// exact required format — so a raw daemon log can reconstruct the <c>S</c>-over-time curve spec
/// Sec.6.2 needs without ad hoc <c>GET /api/v1/status</c> polling mid-session.
///
/// <para>
/// Uses the <see cref="IFt8NativeInterop"/> injection seam (same pattern as
/// <see cref="HashTableRejectCountLoggingTests"/>) so the native DLL is never loaded and the
/// returned counts are fully controlled by the test.
/// </para>
/// </summary>
public sealed class H12InstrumentationLoggingTests
{
    // ── Test double ───────────────────────────────────────────────────────────

    /// <summary>
    /// Fake interop returning fixed, caller-controlled 12-bit-path counts and an empty decode
    /// result set — this test only cares about the h12 log line, not decode output.
    /// </summary>
    private sealed class FixedH12CountsInterop(int displaying, int ambiguous, int divergent) : IFt8NativeInterop
    {
        public int MaxDecodePasses => 2;

        public Ft8NativeResult[] DecodeAll(float[] pcm) => [];

        public int[]  GetLastPassCounts(int maxPasses)      => [0, 0];
        public int[]  GetLastCandidateCounts(int maxPasses) => [0, 0];
        public float  GetLastNoiseFloorDb()                  => -70.0f;
        public int    GetHashTableRejectCount()              => 0;
        public int    GetH12DisplayingCount()                => displaying;
        public int    GetH12AmbiguousCount()                 => ambiguous;
        public int    GetH12DivergentCount()                 => divergent;
        public (float[] MeanAbs, float[] PrenormVariance, int[] FailCount) GetLastLlrStats(int maxPasses)
            => (new float[maxPasses], new float[maxPasses], new int[maxPasses]);

        public void SetApBits(byte[] mycallBits, byte[] hiscallBits) { /* no-op */ }
        public void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax) { /* no-op */ }

        public (float DeltaFreqHz, float DeltaTimeS, float SyncScore, int CoarseDtSamp, int FineDtSamp) RefineCandidate(
            float[] pcm, int coarseFreqHz, float coarseTimeOffsetS) => (0f, 0f, 0f, 0, 0);

        public float[] CoherentLlrAt(float[] pcm, float freqHz, float timeOffsetS) => new float[174];

        public (float[] SignalDb, float[] LocalNoiseDb) GetLastSnrTerms(int maxDecoded)
            => (Array.Empty<float>(), Array.Empty<float>());
    }

    /// <summary>
    /// <see cref="ILogger{T}"/> that records every log entry for assertion — local to this file
    /// rather than shared, mirroring <see cref="HashTableRejectCountLoggingTests"/>'s equivalent
    /// test double.
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
    /// must not be tripped, or DecodeAsync returns before reaching the h12 log line.
    /// </summary>
    private static float[] BuildLoudPcm()
    {
        var pcm = new float[180_000];
        for (int i = 0; i < pcm.Length; i++)
            pcm[i] = 0.1f;
        return pcm;
    }

    // ── Tests ─────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "SUP-B: DecodeAsync logs h12Displaying/h12Ambiguous/h12Divergent at Information level once per cycle")]
    public async Task DecodeAsync_EveryCycle_LogsH12CountsAtInformation()
    {
        const int displaying = 17;
        const int ambiguous  = 5;
        const int divergent  = 2;
        var logger  = new RecordingLogger<Ft8Decoder>();
        var interop = new FixedH12CountsInterop(displaying, ambiguous, divergent);
        var decoder = new Ft8Decoder(
            new FakeClock(new DateTime(2026, 8, 30, 9, 0, 0, DateTimeKind.Utc)),
            logger,
            interop);

        await decoder.DecodeAsync(BuildLoudPcm(), CancellationToken.None);

        logger.Entries.Should().Contain(
            e => e.Level == LogLevel.Information
                 && e.Message.Contains("h12Displaying")
                 && e.Message.Contains("h12Ambiguous")
                 && e.Message.Contains("h12Divergent")
                 && e.Message.Contains(displaying.ToString())
                 && e.Message.Contains(ambiguous.ToString())
                 && e.Message.Contains(divergent.ToString()),
            "h12Displaying/h12Ambiguous/h12Divergent must be logged at Information level every " +
            "cycle (the same cadence and level as the existing hashTableRejectCount line), " +
            "carrying the values the three new getters actually returned, so a raw daemon log " +
            "can reconstruct the S-over-time curve without needing ad hoc /api/v1/status polling");
    }

    [Fact(DisplayName = "SUP-B: h12 log line reflects all-zero counts, not just truthy non-zero ones")]
    public async Task DecodeAsync_ZeroH12Counts_LogsZeroExplicitly()
    {
        var logger  = new RecordingLogger<Ft8Decoder>();
        var interop = new FixedH12CountsInterop(displaying: 0, ambiguous: 0, divergent: 0);
        var decoder = new Ft8Decoder(
            new FakeClock(new DateTime(2026, 8, 30, 9, 0, 0, DateTimeKind.Utc)),
            logger,
            interop);

        await decoder.DecodeAsync(BuildLoudPcm(), CancellationToken.None);

        logger.Entries.Should().Contain(
            e => e.Level == LogLevel.Information
                 && e.Message.Contains("h12Displaying=0")
                 && e.Message.Contains("h12Ambiguous=0")
                 && e.Message.Contains("h12Divergent=0"),
            "all-zero h12 counts must still be logged explicitly every cycle (regular cadence, " +
            "not conditional on a non-zero/truthy value) so a session's early cycles establish a " +
            "proper baseline for the later S-over-time trend this logging exists to support");
    }
}
