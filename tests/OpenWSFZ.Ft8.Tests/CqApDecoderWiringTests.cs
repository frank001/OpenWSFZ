using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// CQ-AP: the managed wiring of <c>decoder.cqApEnabled</c> (D2 flag, D5 filter, D6 tag and log line), against a fake native layer so every case is
/// exact. Q-prefix calls only (NFR-021). No delay anywhere: the decode is awaited, never slept on.
/// </summary>
public sealed class CqApDecoderWiringTests
{
    private const int CqApAttemptsPerCall = 7;

    private static Ft8NativeResult Native(string message, ApKind kind = ApKind.None, int freq = 1500)
        => new() { FreqHz = freq, Dt = 0.2f, Snr = -19, Message = message, ApKind = kind };

    /// <summary>A fake native layer: fixed results, records the flag as it stood at every <c>DecodeAll</c>, reports a fixed attempt count per call.</summary>
    private sealed class Fake(params Ft8NativeResult[] results) : IFt8NativeInterop
    {
        private bool _flag;
        public List<bool> FlagAtDecode { get; } = [];

        public int MaxDecodePasses => 2;
        public Ft8NativeResult[] DecodeAll(float[] pcm) { FlagAtDecode.Add(_flag); return results; }
        public void SetCqApEnabled(bool enabled) => _flag = enabled;
        public (int Attempts, int Decodes, int OsdEntries) GetLastCqApStats()
            => (_flag ? CqApAttemptsPerCall : 0, results.Count(r => r.ApKind == ApKind.Cq), 0);

        public int[] GetLastPassCounts(int maxPasses)      => [results.Length, 0];
        public int[] GetLastCandidateCounts(int maxPasses) => [results.Length, 0];
        public float GetLastNoiseFloorDb()                  => -70.0f;
        public int   GetHashTableRejectCount()              => 0;
        public int GetH12DisplayingCount() => 0;
        public int GetH12AmbiguousCount()  => 0;
        public int GetH12DivergentCount()  => 0;
        public int GetH12SuppressedCount() => 0;
        public (float[] MeanAbs, float[] PrenormVariance, int[] FailCount) GetLastLlrStats(int maxPasses)
            => (new float[maxPasses], new float[maxPasses], new int[maxPasses]);
        public void SetApBits(byte[] mycallBits, byte[] hiscallBits) { /* no-op */ }
        public void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax) { /* no-op */ }
        public (float DeltaFreqHz, float DeltaTimeS, float SyncScore, int CoarseDtSamp, int FineDtSamp) RefineCandidate(
            float[] pcm, int coarseFreqHz, float coarseTimeOffsetS) => (0f, 0f, 0f, 0, 0);
        public float[] CoherentLlrAt(float[] pcm, float freqHz, float timeOffsetS) => new float[174];
        public (float[] SignalDb, float[] LocalNoiseDb) GetLastSnrTerms(int maxDecoded) => ([], []);
        public byte[] EncodeMessage(string message) => new byte[79];
        public (float[] Re, float[] Im) SubfeasComputeAnalytic(float[] pcm) => (new float[180_000], new float[180_000]);
        public (int ReturnCode, float[] Shat) SubfeasFitSignal(
            float[] xARe, float[] xAIm, byte[] tones, float decodedDtS, float decodedFreqHz, IntPtr cancelFlag) => (0, new float[180_000]);
    }

    private sealed class CapturingLogger : ILogger<Ft8Decoder>
    {
        public List<(LogLevel Level, string Message)> Entries { get; } = [];
        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => true;
        public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception, Func<TState, Exception?, string> formatter)
            => Entries.Add((logLevel, formatter(state, exception)));
    }

    private static float[] LoudPcm()
    {
        var pcm = new float[180_000];
        Array.Fill(pcm, 0.1f);
        return pcm;
    }

    private static (Ft8Decoder Decoder, CapturingLogger Log) Build(IFt8NativeInterop interop)
    {
        var log = new CapturingLogger();
        var decoder = new Ft8Decoder(new FakeClock(new DateTime(2026, 11, 10, 12, 0, 0, DateTimeKind.Utc)), log, interop);
        return (decoder, log);
    }

    private static IEnumerable<string> CqApLines(CapturingLogger log)
        => log.Entries.Where(e => e.Level == LogLevel.Information && e.Message.Contains("cq-ap:")).Select(e => e.Message);

    // ── D2: the flag ─────────────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-103: CQ-AP D2: the decoder's flag starts false, and the config default is false (an absent key reads false)")]
    public void Flag_DefaultsToFalse()
    {
        var (decoder, _) = Build(new Fake());
        decoder.CqApEnabled.Should().BeFalse();
        new DecoderConfig().CqApEnabled.Should().BeFalse();
    }

    [Fact(DisplayName = "FR-103: CQ-AP D2: the flag reaches the native layer on the decoding thread before every DecodeAll - false by default, true when set, and it follows a change on the next cycle")]
    public async Task Flag_ReachesNative_BeforeEveryDecode()
    {
        var fake = new Fake(Native("CQ Q1ABC JO22"));
        var (decoder, _) = Build(fake);

        await decoder.DecodeAsync(LoudPcm(), CancellationToken.None);
        decoder.SetCqApEnabled(true);
        await decoder.DecodeAsync(LoudPcm(), CancellationToken.None);
        await decoder.DecodeAsync(LoudPcm(), CancellationToken.None);
        decoder.SetCqApEnabled(false);
        await decoder.DecodeAsync(LoudPcm(), CancellationToken.None);

        fake.FlagAtDecode.Should().Equal(false, true, true, false);
    }

    // ── D6: tag and log line ─────────────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-103: CQ-AP D6: every decode carries ApKind from the native result to the DecodeResult (cq stays cq, the rest none)")]
    public async Task Tag_ReachesTheDecodeResult()
    {
        var (decoder, _) = Build(new Fake(Native("CQ Q1ABC JO22", ApKind.Cq, 1200), Native("Q2DEF Q3GHI JO22", ApKind.None, 1800)));
        decoder.SetCqApEnabled(true);

        var results = await decoder.DecodeAsync(LoudPcm(), CancellationToken.None);

        results.Single(r => r.Message == "CQ Q1ABC JO22").ApKind.Should().Be(ApKind.Cq);
        results.Single(r => r.Message == "Q2DEF Q3GHI JO22").ApKind.Should().Be(ApKind.None);
    }

    [Fact(DisplayName = "FR-103: CQ-AP D6: with the flag on one Information line per cycle 'cq-ap: attempts=N decodes=M', counts only; M counts the decodes PUBLISHED")]
    public async Task LogLine_OnePerCycle_WithCounts()
    {
        var (decoder, log) = Build(new Fake(Native("CQ Q1ABC JO22", ApKind.Cq), Native("Q2DEF Q3GHI JO22")));
        decoder.SetCqApEnabled(true);

        await decoder.DecodeAsync(LoudPcm(), CancellationToken.None);

        var lines = CqApLines(log).ToList();
        lines.Should().ContainSingle();
        lines[0].Should().EndWith($"cq-ap: attempts={CqApAttemptsPerCall} decodes=1");
        foreach (var (_, message) in log.Entries)
            foreach (var call in new[] { "Q1ABC", "Q2DEF", "Q3GHI", "JO22" })
                message.Should().NotContain(call, "counts only, never a callsign or a message");
    }

    [Fact(DisplayName = "FR-103: CQ-AP D6: with the flag OFF there is no cq-ap line at all")]
    public async Task LogLine_AbsentWhenOff()
    {
        var (decoder, log) = Build(new Fake(Native("CQ Q1ABC JO22", ApKind.Cq)));

        await decoder.DecodeAsync(LoudPcm(), CancellationToken.None);

        CqApLines(log).Should().BeEmpty();
        log.Entries.Should().NotContain(e => e.Message.Contains("cq-ap"));
    }

    [Fact(DisplayName = "FR-103: CQ-AP D6: a cycle with no CQ-AP decode still logs the line (attempts=N decodes=0)")]
    public async Task LogLine_ZeroDecodes()
    {
        var (decoder, log) = Build(new Fake(Native("Q2DEF Q3GHI JO22")));
        decoder.SetCqApEnabled(true);

        await decoder.DecodeAsync(LoudPcm(), CancellationToken.None);

        CqApLines(log).Should().ContainSingle().Which.Should().EndWith($"cq-ap: attempts={CqApAttemptsPerCall} decodes=0");
    }

    // ── D5: the filter is unchanged ──────────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-103: CQ-AP D5: a CQ-AP decode that fails IsPlausibleMessage is dropped like any other, and is not counted as published")]
    public async Task ImplausibleCqApDecode_IsDropped()
    {
        // A 12-character base call after CQ is beyond the protocol maximum (D-011): the plausibility filter rejects it whatever produced it.
        var (decoder, log) = Build(new Fake(Native("CQ ETRHB0I3RYOX", ApKind.Cq, 1100), Native("CQ Q1ABC JO22", ApKind.Cq, 1300)));
        decoder.SetCqApEnabled(true);

        var results = await decoder.DecodeAsync(LoudPcm(), CancellationToken.None);

        results.Select(r => r.Message).Should().Equal("CQ Q1ABC JO22");
        CqApLines(log).Should().ContainSingle().Which.Should().EndWith($"decodes=1");
    }

    [Fact(DisplayName = "FR-103: CQ-AP D5: a CQ-AP decode whose text was already published in the cycle is de-duplicated by text like any other")]
    public async Task DuplicateText_IsDeduplicated()
    {
        var (decoder, _) = Build(new Fake(Native("CQ Q1ABC JO22", ApKind.None, 1100), Native("CQ Q1ABC JO22", ApKind.Cq, 1900)));
        decoder.SetCqApEnabled(true);

        var results = await decoder.DecodeAsync(LoudPcm(), CancellationToken.None);

        results.Should().ContainSingle();
        results[0].ApKind.Should().Be(ApKind.None, "the first occurrence is the one published");
    }
}
