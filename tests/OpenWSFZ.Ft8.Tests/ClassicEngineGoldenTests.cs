using System.Text;
using System.Text.RegularExpressions;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Interop;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// DR-2 step 2a (FR-108), test 4: the classic decoder is BYTE-IDENTICAL to the base while <c>decoder.engine</c> is absent or "classic". This file uses
/// ONLY the API that exists on the base build, so the very same file was run against <c>origin/main</c> first (<c>452af459</c>) and
/// <see cref="Golden"/> is what that run recorded; it was then pasted here and the file run again on this branch. The recording is every native call the
/// decoder made (name and argument summary, in order), every batch it published (number, text, path, tag), and every log line it wrote (the elapsed
/// milliseconds normalised, nothing else), for a plain decode and a staged decode, each with the residual pass off and on. Q-prefix calls only (NFR-021).
/// No delay anywhere: every decode is awaited, never slept on.
/// </summary>
public sealed class ClassicEngineGoldenTests
{
    /// <summary>A fake native layer that records every call it receives and returns fixed results.</summary>
    private sealed class RecordingInterop(List<string> calls) : IFt8NativeInterop
    {
        private static Ft8NativeResult Native(string message, int freq, float dt, int snr)
            => new() { FreqHz = freq, Dt = dt, Snr = snr, Message = message };

        private readonly Ft8NativeResult[] _results =
        [
            Native("CQ Q1ABC JO22", 1200, 0.2f, -12),
            Native("Q2DEF Q3GHI -07", 1800, 0.4f, -15),
        ];

        public int MaxDecodePasses => 2;
        public Ft8NativeResult[] DecodeAll(float[] pcm) { calls.Add($"DecodeAll(len={pcm.Length})"); return _results; }
        public int[] GetLastPassCounts(int maxPasses) { calls.Add($"GetLastPassCounts({maxPasses})"); return [_results.Length, 0]; }
        public int[] GetLastCandidateCounts(int maxPasses) { calls.Add($"GetLastCandidateCounts({maxPasses})"); return [_results.Length, 0]; }
        public float GetLastNoiseFloorDb() { calls.Add("GetLastNoiseFloorDb"); return -70.0f; }
        public int GetHashTableRejectCount() { calls.Add("GetHashTableRejectCount"); return 0; }
        public int GetH12DisplayingCount() { calls.Add("GetH12DisplayingCount"); return 0; }
        public int GetH12AmbiguousCount() { calls.Add("GetH12AmbiguousCount"); return 0; }
        public int GetH12DivergentCount() { calls.Add("GetH12DivergentCount"); return 0; }
        public int GetH12SuppressedCount() { calls.Add("GetH12SuppressedCount"); return 0; }
        public (float[] MeanAbs, float[] PrenormVariance, int[] FailCount) GetLastLlrStats(int maxPasses)
        { calls.Add($"GetLastLlrStats({maxPasses})"); return (new float[maxPasses], new float[maxPasses], new int[maxPasses]); }
        public void SetApBits(byte[] mycallBits, byte[] hiscallBits) => calls.Add($"SetApBits({mycallBits.Length},{hiscallBits.Length})");
        public void SetCqApEnabled(bool enabled) => calls.Add($"SetCqApEnabled({enabled})");
        public (int Attempts, int Decodes, int OsdEntries) GetLastCqApStats() { calls.Add("GetLastCqApStats"); return (0, 0, 0); }
        public void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax) => calls.Add("SetDecodeParams");
        public (float DeltaFreqHz, float DeltaTimeS, float SyncScore, int CoarseDtSamp, int FineDtSamp) RefineCandidate(
            float[] pcm, int coarseFreqHz, float coarseTimeOffsetS) { calls.Add("RefineCandidate"); return (0f, 0f, 0f, 0, 0); }
        public float[] CoherentLlrAt(float[] pcm, float freqHz, float timeOffsetS) { calls.Add("CoherentLlrAt"); return new float[174]; }
        public (float[] SignalDb, float[] LocalNoiseDb) GetLastSnrTerms(int maxDecoded) { calls.Add($"GetLastSnrTerms({maxDecoded})"); return ([], []); }
        public byte[] EncodeMessage(string message) { calls.Add("EncodeMessage"); return new byte[79]; }
        public (float[] Re, float[] Im) SubfeasComputeAnalytic(float[] pcm)
        { calls.Add($"SubfeasComputeAnalytic(len={pcm.Length})"); return (new float[180_000], new float[180_000]); }
        public (int ReturnCode, float[] Shat) SubfeasFitSignal(
            float[] xARe, float[] xAIm, byte[] tones, float decodedDtS, float decodedFreqHz, IntPtr cancelFlag)
        { calls.Add("SubfeasFitSignal"); return (0, new float[180_000]); }
        // The bound is max(1, ProcessorCount - 2): it depends on the host, so the recording keeps the call and not the number.
        public void SubfeasPoolConfigure(int bound) => calls.Add("SubfeasPoolConfigure(N)");
        public void SubfeasPoolShutdown() => calls.Add("SubfeasPoolShutdown");
        public void SetDiagnosticsEnabled(bool enabled) => calls.Add($"SetDiagnosticsEnabled({enabled})");
    }

    private sealed class CapturingLogger(List<string> lines) : ILogger<Ft8Decoder>
    {
        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => true;
        public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception, Func<TState, Exception?, string> formatter)
            => lines.Add($"{logLevel}: {Regex.Replace(formatter(state, exception), @"(elapsed|elapsedMs)=\d+", "$1=N")}");
    }

    private static float[] LoudPcm()
    {
        var pcm = new float[180_000];
        Array.Fill(pcm, 0.1f);
        return pcm;
    }

    private static string Describe(IEnumerable<DecodeResult> batch)
        => string.Join(" | ", batch.Select(r => $"{r.FreqHz}Hz {r.Snr}dB dt={r.Dt:F1} path={r.Path} ap={r.ApKind} '{r.Message}'"));

    /// <summary>
    /// Runs the four recorded cycles on a decoder made by <paramref name="configure"/> (which sets nothing for the base recording) and returns the
    /// recording as text.
    /// </summary>
    internal static async Task<string> RecordAsync(Action<Ft8Decoder>? configure = null)
    {
        var sb = new StringBuilder();
        var start = new DateTime(2026, 11, 24, 12, 0, 0, DateTimeKind.Utc);

        foreach (bool subtraction in new[] { false, true })
        foreach (bool staged in new[] { false, true })
        {
            var calls = new List<string>();
            var logs  = new List<string>();
            var decoder = new Ft8Decoder(new FakeClock(start), new CapturingLogger(logs), new RecordingInterop(calls));
            decoder.SetSubtractionEnabled(subtraction);
            configure?.Invoke(decoder);

            sb.AppendLine($"== subtraction={subtraction} staged={staged}");
            if (staged)
            {
                await decoder.DecodeStagedAsync(LoudPcm(), start, "20m", (n, batch) =>
                {
                    sb.AppendLine($"batch {n}: {Describe(batch)}");
                    return Task.CompletedTask;
                });
            }
            else
            {
                var results = await decoder.DecodeAsync(LoudPcm(), start, "20m");
                sb.AppendLine($"returned: {Describe(results)}");
            }
            sb.AppendLine("calls:").AppendLine(string.Join(Environment.NewLine, calls.Select(c => "  " + c)));
            sb.AppendLine("logs:").AppendLine(string.Join(Environment.NewLine, logs.Select(l => "  " + l)));
        }
        return sb.ToString().Replace("\r\n", "\n");
    }

    [Fact(DisplayName = "FR-108: DR-2 test 4: with decoder.engine absent the classic decoder's native calls, batches and log lines equal the base build's recording")]
    public async Task AbsentKey_EqualsTheBaseRecording()
    {
        string actual = await RecordAsync();
        actual.Should().Be(GoldenText);
    }

    /// <summary><see cref="Golden"/> as text: the raw-string literal leaves out the newline before its closing quotes.</summary>
    internal static string GoldenText => Golden.Replace("\r\n", "\n") + "\n";

    /// <summary>What <c>origin/main</c> <c>452af459</c> recorded for <see cref="RecordAsync"/> (see the class summary).</summary>
    internal const string Golden = """
== subtraction=False staged=False
returned: 1200Hz -12dB dt=0.2 path=0 ap=None 'CQ Q1ABC JO22' | 1800Hz -15dB dt=0.4 path=0 ap=None 'Q2DEF Q3GHI -07'
calls:
  SetApBits(0,0)
  SetCqApEnabled(False)
  DecodeAll(len=180000)
  GetLastPassCounts(2)
  GetLastCandidateCounts(2)
  GetLastNoiseFloorDb
  GetLastLlrStats(2)
  GetHashTableRejectCount
  GetH12DisplayingCount
  GetH12AmbiguousCount
  GetH12DivergentCount
  GetH12SuppressedCount
logs:
  Debug: Starting decode for cycle 12:00:00; pcm = 180000 samples, RMS = 1.000E-001.
  Debug: Iterative subtraction: pass 1 of 2, 2 candidates found, 2 decoded.
  Debug: Iterative subtraction: pass 2 of 2, 0 candidates found, 0 decoded.
  Debug: Iterative subtraction: pass 1 LDPC fail stats — failCands=0 meanAbsLLR=0.000 prenormVar=0.0000
  Debug: Iterative subtraction: pass 2 LDPC fail stats — failCands=0 meanAbsLLR=0.000 prenormVar=0.0000
  Information: Cycle 12:00:00: 2 decode(s) found, elapsed=N ms.
  Information: Cycle 12:00:00: hashTableRejectCount=0 (process-lifetime cumulative).
  Information: Cycle 12:00:00: h12Displaying=0 h12Ambiguous=0 h12Divergent=0 h12Suppressed=0 (process-lifetime cumulative).
  Information: Cycle 12:00:00: noise_floor=-70.0 dB (waterfall histogram median).
== subtraction=False staged=True
batch 1: 1200Hz -12dB dt=0.2 path=0 ap=None 'CQ Q1ABC JO22' | 1800Hz -15dB dt=0.4 path=0 ap=None 'Q2DEF Q3GHI -07'
calls:
  SetApBits(0,0)
  SetCqApEnabled(False)
  DecodeAll(len=180000)
  GetLastPassCounts(2)
  GetLastCandidateCounts(2)
  GetLastNoiseFloorDb
  GetLastLlrStats(2)
  GetHashTableRejectCount
  GetH12DisplayingCount
  GetH12AmbiguousCount
  GetH12DivergentCount
  GetH12SuppressedCount
logs:
  Debug: Starting decode for cycle 12:00:00; pcm = 180000 samples, RMS = 1.000E-001.
  Debug: Iterative subtraction: pass 1 of 2, 2 candidates found, 2 decoded.
  Debug: Iterative subtraction: pass 2 of 2, 0 candidates found, 0 decoded.
  Debug: Iterative subtraction: pass 1 LDPC fail stats — failCands=0 meanAbsLLR=0.000 prenormVar=0.0000
  Debug: Iterative subtraction: pass 2 LDPC fail stats — failCands=0 meanAbsLLR=0.000 prenormVar=0.0000
  Information: Cycle 12:00:00: 2 decode(s) found, elapsed=N ms.
  Information: Cycle 12:00:00: hashTableRejectCount=0 (process-lifetime cumulative).
  Information: Cycle 12:00:00: h12Displaying=0 h12Ambiguous=0 h12Divergent=0 h12Suppressed=0 (process-lifetime cumulative).
  Information: Cycle 12:00:00: noise_floor=-70.0 dB (waterfall histogram median).
== subtraction=True staged=False
returned: 1200Hz -12dB dt=0.2 path=0 ap=None 'CQ Q1ABC JO22' | 1800Hz -15dB dt=0.4 path=0 ap=None 'Q2DEF Q3GHI -07'
calls:
  SetApBits(0,0)
  SetCqApEnabled(False)
  DecodeAll(len=180000)
  GetLastPassCounts(2)
  GetLastCandidateCounts(2)
  GetLastNoiseFloorDb
  GetLastLlrStats(2)
  EncodeMessage
  EncodeMessage
  SubfeasComputeAnalytic(len=180000)
  SubfeasPoolConfigure(N)
  SubfeasFitSignal
  SubfeasFitSignal
  SetApBits(0,0)
  SetDiagnosticsEnabled(False)
  SetCqApEnabled(False)
  DecodeAll(len=180000)
  SetDiagnosticsEnabled(True)
  SetApBits(0,0)
  SetCqApEnabled(False)
  EncodeMessage
  EncodeMessage
  GetHashTableRejectCount
  GetH12DisplayingCount
  GetH12AmbiguousCount
  GetH12DivergentCount
  GetH12SuppressedCount
logs:
  Debug: Starting decode for cycle 12:00:00; pcm = 180000 samples, RMS = 1.000E-001.
  Information: Sub-feas residual pass: residualDecodes=0 elapsedMs=N deadlineAbandoned=False containedException=False fittedSignals=2
  Debug: Iterative subtraction: pass 1 of 2, 2 candidates found, 2 decoded.
  Debug: Iterative subtraction: pass 2 of 2, 0 candidates found, 0 decoded.
  Debug: Iterative subtraction: pass 1 LDPC fail stats — failCands=0 meanAbsLLR=0.000 prenormVar=0.0000
  Debug: Iterative subtraction: pass 2 LDPC fail stats — failCands=0 meanAbsLLR=0.000 prenormVar=0.0000
  Information: Cycle 12:00:00: 2 decode(s) found, elapsed=N ms.
  Information: Cycle 12:00:00: hashTableRejectCount=0 (process-lifetime cumulative).
  Information: Cycle 12:00:00: h12Displaying=0 h12Ambiguous=0 h12Divergent=0 h12Suppressed=0 (process-lifetime cumulative).
  Information: Cycle 12:00:00: noise_floor=-70.0 dB (waterfall histogram median).
== subtraction=True staged=True
batch 1: 1200Hz -12dB dt=0.2 path=0 ap=None 'CQ Q1ABC JO22' | 1800Hz -15dB dt=0.4 path=0 ap=None 'Q2DEF Q3GHI -07'
calls:
  SetApBits(0,0)
  SetCqApEnabled(False)
  DecodeAll(len=180000)
  GetLastPassCounts(2)
  GetLastCandidateCounts(2)
  GetLastNoiseFloorDb
  GetLastLlrStats(2)
  GetHashTableRejectCount
  GetH12DisplayingCount
  GetH12AmbiguousCount
  GetH12DivergentCount
  GetH12SuppressedCount
  EncodeMessage
  EncodeMessage
  SubfeasComputeAnalytic(len=180000)
  SubfeasPoolConfigure(N)
  SubfeasFitSignal
  SubfeasFitSignal
  SetApBits(0,0)
  SetDiagnosticsEnabled(False)
  SetCqApEnabled(False)
  DecodeAll(len=180000)
  SetDiagnosticsEnabled(True)
  SetApBits(0,0)
  SetCqApEnabled(False)
  EncodeMessage
  EncodeMessage
logs:
  Debug: Starting decode for cycle 12:00:00; pcm = 180000 samples, RMS = 1.000E-001.
  Debug: Iterative subtraction: pass 1 of 2, 2 candidates found, 2 decoded.
  Debug: Iterative subtraction: pass 2 of 2, 0 candidates found, 0 decoded.
  Debug: Iterative subtraction: pass 1 LDPC fail stats — failCands=0 meanAbsLLR=0.000 prenormVar=0.0000
  Debug: Iterative subtraction: pass 2 LDPC fail stats — failCands=0 meanAbsLLR=0.000 prenormVar=0.0000
  Information: Cycle 12:00:00: 2 decode(s) found, elapsed=N ms.
  Information: Cycle 12:00:00: hashTableRejectCount=0 (process-lifetime cumulative).
  Information: Cycle 12:00:00: h12Displaying=0 h12Ambiguous=0 h12Divergent=0 h12Suppressed=0 (process-lifetime cumulative).
  Information: Cycle 12:00:00: noise_floor=-70.0 dB (waterfall histogram median).
  Information: Sub-feas residual pass: residualDecodes=0 elapsedMs=N deadlineAbandoned=False containedException=False fittedSignals=2
""";
}
