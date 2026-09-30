using System.Reflection;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Ft8.Interop;
using OpenWSFZ.Ft8.Subfeas;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// tasks.md 4.2 (residual-pass log line) and 6.3 / 6.5 / 6.6 for sub-feas-native-subtraction.
///
/// <para>
/// 6.6 is MANAGED SCOPE ONLY: a native <c>malloc</c>-failure injection would change
/// <c>libft8.dll</c> and is unmet by design. The managed half is covered here (decoder-level, with the
/// log line) and by <see cref="SubtractionPassTests"/> (R2: compute-analytic AV, per-signal rc -1,
/// EncodeMessage failure).
/// </para>
/// </summary>
public sealed class SubtractionLogLineTests
{
    private const int PcmLength = 180_000;
    private const string LineTemplateStart = "Sub-feas residual pass: residualDecodes=";
    private const string Marker = "ZZMARKER";

    // ── 4.2: the log line ─────────────────────────────────────────────────────

    [Fact(DisplayName = "4.2: residual pass finds a new decode -> exactly one line, fields correct")]
    public async Task NewDecode_OneLine_FieldsCorrect()
    {
        var log = new CapturingLogger();
        var interop = new ProbeInterop { Residual = [Msg("Q1DEF Q1UVW EN37")] };

        var result = await SubtractionPass.RunAsync(interop, new float[PcmLength], [Msg("Q1ABC Q1XYZ JO33")], 2, log);

        result.Should().ContainSingle();
        var line = log.Lines().Should().ContainSingle().Subject;
        line.Level.Should().Be(LogLevel.Information);
        line.Text.Should().StartWith(LineTemplateStart + "1 elapsedMs=");
        line.Text.Should().Contain("deadlineAbandoned=False").And.Contain("containedException=False")
            .And.EndWith("fittedSignals=1");
    }

    [Fact(DisplayName = "4.2: flag OFF -> zero lines with this template; flag ON through the decoder -> one")]
    public async Task FlagOff_NoLine_FlagOn_OneLine()
    {
        var logOff = new CapturingLogger();
        var off = new Ft8Decoder(new FakeClock(new DateTime(2026, 6, 14, 1, 0, 0, DateTimeKind.Utc)), logOff,
            interop: new ProbeInterop { Pass0 = [Msg("Q1ABC Q1XYZ JO33")], Residual = [Msg("Q1DEF Q1UVW EN37")] });
        await off.DecodeAsync(LoudPcm(), CancellationToken.None);
        logOff.Lines().Should().BeEmpty("the OFF path must not touch the residual pass at all");

        var logOn = new CapturingLogger();
        var on = new Ft8Decoder(new FakeClock(new DateTime(2026, 6, 14, 1, 0, 0, DateTimeKind.Utc)), logOn,
            interop: new ProbeInterop { Pass0 = [Msg("Q1ABC Q1XYZ JO33")], Residual = [Msg("Q1DEF Q1UVW EN37")] });
        on.SetSubtractionEnabled(true);
        await on.DecodeAsync(LoudPcm(), CancellationToken.None);
        logOn.Lines().Should().ContainSingle();
    }

    [Fact(DisplayName = "4.2: deadline expired -> deadlineAbandoned=True, residualDecodes=0")]
    public async Task DeadlineExpired_Flagged()
    {
        var log = new CapturingLogger();
        var interop = new ProbeInterop { Residual = [Msg("Q1GHI Q1JKL FN20")] };

        await SubtractionPass.RunAsync(interop, new float[PcmLength], [Msg("Q1ABC Q1XYZ JO33")], 2, log,
            deadline: TimeSpan.Zero);

        var line = log.Lines().Should().ContainSingle().Subject;
        line.Text.Should().StartWith(LineTemplateStart + "0 ").And.Contain("deadlineAbandoned=True")
            .And.Contain("containedException=False");
    }

    [Fact(DisplayName = "4.2: contained exception -> containedException=True, residualDecodes=0")]
    public async Task ContainedException_Flagged()
    {
        var log = new CapturingLogger();
        var interop = new ProbeInterop { FitThrows = new InvalidOperationException("rc -1") };

        var result = await SubtractionPass.RunAsync(interop, new float[PcmLength], [Msg("Q1ABC Q1XYZ JO33")], 2, log);

        result.Should().BeEmpty();
        var line = log.Lines().Should().ContainSingle().Subject;
        line.Text.Should().StartWith(LineTemplateStart + "0 ").And.Contain("containedException=True")
            .And.Contain("deadlineAbandoned=False");
    }

    [Fact(DisplayName = "4.2: no re-encodable signals -> one line, fittedSignals=0")]
    public async Task NoReencodable_OneLine_ZeroFitted()
    {
        var log = new CapturingLogger();

        await SubtractionPass.RunAsync(new ProbeInterop(), new float[PcmLength], [Msg("<...> Q1XYZ RR73")], 2, log);

        var line = log.Lines().Should().ContainSingle().Subject;
        line.Text.Should().StartWith(LineTemplateStart + "0 ").And.EndWith("fittedSignals=0");
    }

    [Fact(DisplayName = "4.2: caller cancellation (before start and mid-fit) -> no line")]
    public async Task CallerCancellation_NoLine()
    {
        var pre = new CapturingLogger();
        using var cts1 = new CancellationTokenSource();
        cts1.Cancel();
        var act1 = () => SubtractionPass.RunAsync(new ProbeInterop(), new float[PcmLength],
            [Msg("Q1ABC Q1XYZ JO33")], 2, pre, ct: cts1.Token);
        await act1.Should().ThrowAsync<OperationCanceledException>();
        pre.Lines().Should().BeEmpty();

        var mid = new CapturingLogger();
        using var cts2 = new CancellationTokenSource();
        var interop = new ProbeInterop { OnFit = () => cts2.Cancel() };
        var act2 = () => SubtractionPass.RunAsync(interop, new float[PcmLength],
            [Msg("Q1ABC Q1XYZ JO33"), Msg("Q1DEF Q1UVW EN37"), Msg("Q1GHI Q1JKL FN20")], 1, mid, ct: cts2.Token);
        await act2.Should().ThrowAsync<OperationCanceledException>();
        mid.Lines().Should().BeEmpty();
    }

    [Fact(DisplayName = "4.2: no-text canary -- message text, callsigns and exception text never reach the line (HK-037)")]
    public async Task NoTextCanary()
    {
        // Distinctive markers in pass-0 messages, residual messages, and exception text. Q1-prefix
        // callsigns keep NFR-021; the marker rides in the callsign suffix where it still encodes.
        var log = new CapturingLogger();
        var ok = new ProbeInterop { Residual = [Msg("Q1DEF Q1UVW EN37")] };
        await SubtractionPass.RunAsync(ok, new float[PcmLength], [Msg("Q1ABC Q1XYZ JO33"), Msg($"CQ Q1{Marker} JO33")], 2, log);

        var boom = new ProbeInterop { FitThrows = new InvalidOperationException($"{Marker} Q1ABC secret") };
        await SubtractionPass.RunAsync(boom, new float[PcmLength], [Msg("Q1ABC Q1XYZ JO33")], 2, log);

        var lines = log.Lines();
        lines.Should().HaveCount(2);
        foreach (var l in lines)
        {
            // Strip the template's own fixed text; nothing message-like may remain.
            l.Text.Should().NotContain(Marker).And.NotContain("<").And.NotContain("CQ ").And.NotContain("Q1")
                .And.NotContain("secret").And.NotContain("JO33").And.NotContain("EN37");
        }
    }

    // ── 6.3 ───────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "6.3: AllFitsAgainstOriginalBuffer_NotSequential -- every concurrent fit sees the SAME, unmodified analytic arrays")]
    public async Task AllFitsAgainstOriginalBuffer_NotSequential()
    {
        var interop = new ProbeInterop { RecordAnalytic = true, FitDelayMs = 30, ShatFill = 0.5f };
        var pass0 = new[]
        {
            Msg("Q1ABC Q1XYZ JO33"), Msg("Q1DEF Q1UVW EN37"), Msg("Q1GHI Q1JKL FN20"), Msg("Q1MNO Q1PQR IO91"),
        };

        await SubtractionPass.RunAsync(interop, new float[PcmLength], pass0, maxDegreeOfParallelism: 4, logger: null);

        interop.FitCalls.Should().BeGreaterThanOrEqualTo(3);
        interop.FitSawSameReferences.Should().BeTrue("every fit must receive the one analytic signal ComputeAnalytic returned");
        interop.FitSawUnmodifiedContent.Should().BeTrue(
            "no fit's result (or the running residual) may leak into the analytic arrays other fits read");
    }

    // ── 6.5 ───────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "6.5: MaxPassesUnaffectedBySubtractionFlag -- 2 with the flag OFF and ON; the real DLL reports 2")]
    public async Task MaxPassesUnaffectedBySubtractionFlag()
    {
        var adapter = new Ft8NativeInteropAdapter();
        var decoder = new Ft8Decoder(new FakeClock(new DateTime(2026, 6, 14, 1, 0, 0, DateTimeKind.Utc)), logger: null,
            interop: adapter);

        adapter.MaxDecodePasses.Should().Be(2, "flag OFF");
        // Real native decode of silence: also runs the startup ABI check (native K_MAX_PASSES == managed).
        (await decoder.DecodeAsync(new float[PcmLength], CancellationToken.None)).Should().BeEmpty();
        NativeMaxPasses().Should().Be(2, "ft8_get_max_passes() in the real DLL");

        decoder.SetSubtractionEnabled(true);
        adapter.MaxDecodePasses.Should().Be(2, "flag ON");
        (await decoder.DecodeAsync(new float[PcmLength], CancellationToken.None)).Should().BeEmpty();
        NativeMaxPasses().Should().Be(2, "ft8_get_max_passes() must not depend on the flag");
    }

    // ── 6.6 (managed scope) ───────────────────────────────────────────────────

    [Theory(DisplayName = "6.6 (managed): rc -1 InvalidOperationException from ComputeAnalytic / FitSignal -> pass-0-only, contained line, DecodeAsync does not throw")]
    [InlineData(true)]
    [InlineData(false)]
    public async Task AllocationFailure_FallsBackGracefully_NoCrash(bool inComputeAnalytic)
    {
        var log = new CapturingLogger();
        var rc1 = new InvalidOperationException("rc -1: workspace alloc failed");
        var interop = new ProbeInterop
        {
            Pass0 = [Msg("Q1ABC Q1XYZ JO33")],
            Residual = [Msg("Q1DEF Q1UVW EN37")],
            AnalyticThrows = inComputeAnalytic ? rc1 : null,
            FitThrows = inComputeAnalytic ? null : rc1,
        };
        var decoder = new Ft8Decoder(new FakeClock(new DateTime(2026, 6, 14, 1, 0, 0, DateTimeKind.Utc)), log, interop: interop);
        decoder.SetSubtractionEnabled(true);

        var results = await decoder.DecodeAsync(LoudPcm(), CancellationToken.None);

        results.Should().ContainSingle().Which.Message.Should().Be("Q1ABC Q1XYZ JO33");
        var line = log.Lines().Should().ContainSingle().Subject;
        line.Text.Should().Contain("residualDecodes=0").And.Contain("containedException=True");
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static int NativeMaxPasses()
    {
        var m = typeof(Ft8LibInterop).GetMethod("NativeGetMaxPasses", BindingFlags.NonPublic | BindingFlags.Static)
                ?? throw new InvalidOperationException("NativeGetMaxPasses not found");
        return (int)m.Invoke(null, null)!;
    }

    private static Ft8NativeResult Msg(string message)
        => new() { FreqHz = 1500, Dt = 0.2f, Snr = -10, Message = message };

    private static float[] LoudPcm()
    {
        var pcm = new float[PcmLength];
        Array.Fill(pcm, 0.1f);
        return pcm;
    }

    private sealed class CapturingLogger : ILogger<Ft8Decoder>
    {
        private readonly List<(LogLevel Level, string Text)> _entries = [];
        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => true;
        public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception,
            Func<TState, Exception?, string> formatter)
        {
            lock (_entries) _entries.Add((logLevel, formatter(state, exception)));
        }

        /// <summary>Entries using the 4.2 template (any level).</summary>
        public List<(LogLevel Level, string Text)> Lines()
        {
            lock (_entries) return _entries.Where(e => e.Text.StartsWith(LineTemplateStart)).ToList();
        }
    }

    private sealed class ProbeInterop : IFt8NativeInterop
    {
        public int MaxDecodePasses => 2;
        public Ft8NativeResult[] Pass0 { get; init; } = [];
        public Ft8NativeResult[] Residual { get; init; } = [];
        public Exception? AnalyticThrows { get; init; }
        public Exception? FitThrows { get; init; }
        public Action? OnFit { get; init; }
        public bool RecordAnalytic { get; init; }
        public int FitDelayMs { get; init; }
        public float ShatFill { get; init; }

        private int _decodeCalls;
        private int _fitCalls;
        private float[]? _re, _im;
        private double _reSum, _imSum;
        private int _sameRefs = 1, _sameContent = 1;

        public int FitCalls => Volatile.Read(ref _fitCalls);
        public bool FitSawSameReferences => Volatile.Read(ref _sameRefs) == 1;
        public bool FitSawUnmodifiedContent => Volatile.Read(ref _sameContent) == 1;

        // Decoder-level tests set Pass0 (first call = pass-0); direct SubtractionPass tests leave it empty (every call = residual).
        public Ft8NativeResult[] DecodeAll(float[] pcm)
            => Pass0.Length > 0 && Interlocked.Increment(ref _decodeCalls) == 1 ? Pass0 : Residual;

        public byte[] EncodeMessage(string message)
        {
            var tones = new byte[79];
            Ft8LibInterop.EncodeMessage(message, tones);
            return tones;
        }

        public (float[] Re, float[] Im) SubfeasComputeAnalytic(float[] pcm)
        {
            if (AnalyticThrows is not null) throw AnalyticThrows;
            _re = new float[pcm.Length];
            _im = new float[pcm.Length];
            for (int i = 0; i < pcm.Length; i++) { _re[i] = (i % 7) * 0.25f; _im[i] = (i % 5) * -0.5f; }
            _reSum = _re.Sum(x => (double)x);
            _imSum = _im.Sum(x => (double)x);
            return (_re, _im);
        }

        public (int ReturnCode, float[] Shat) SubfeasFitSignal(
            float[] xARe, float[] xAIm, byte[] tones, float decodedDtS, float decodedFreqHz, IntPtr cancelFlag)
        {
            Interlocked.Increment(ref _fitCalls);
            OnFit?.Invoke();
            if (FitThrows is not null) throw FitThrows;
            if (RecordAnalytic)
            {
                if (!ReferenceEquals(xARe, _re) || !ReferenceEquals(xAIm, _im)) Volatile.Write(ref _sameRefs, 0);
                if (xARe.Sum(x => (double)x) != _reSum || xAIm.Sum(x => (double)x) != _imSum) Volatile.Write(ref _sameContent, 0);
            }
            if (FitDelayMs > 0) Thread.Sleep(FitDelayMs);
            var shat = new float[PcmLength];
            if (ShatFill != 0f) Array.Fill(shat, ShatFill);
            return (0, shat);
        }

        public int[] GetLastPassCounts(int maxPasses) => new int[maxPasses];
        public int[] GetLastCandidateCounts(int maxPasses) => new int[maxPasses];
        public float GetLastNoiseFloorDb() => 0f;
        public int GetHashTableRejectCount() => 0;
        public int GetH12DisplayingCount() => 0;
        public int GetH12AmbiguousCount() => 0;
        public int GetH12DivergentCount() => 0;
        public int GetH12SuppressedCount() => 0;
        public (float[] MeanAbs, float[] PrenormVariance, int[] FailCount) GetLastLlrStats(int maxPasses)
            => (new float[maxPasses], new float[maxPasses], new int[maxPasses]);
        public void SetApBits(byte[] mycallBits, byte[] hiscallBits) { }
        public void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax) { }
        public (float DeltaFreqHz, float DeltaTimeS, float SyncScore, int CoarseDtSamp, int FineDtSamp) RefineCandidate(
            float[] pcm, int coarseFreqHz, float coarseTimeOffsetS) => (0f, 0f, 0f, 0, 0);
        public float[] CoherentLlrAt(float[] pcm, float freqHz, float timeOffsetS) => new float[174];
        public (float[] SignalDb, float[] LocalNoiseDb) GetLastSnrTerms(int maxDecoded)
            => (Array.Empty<float>(), Array.Empty<float>());
    }
}
