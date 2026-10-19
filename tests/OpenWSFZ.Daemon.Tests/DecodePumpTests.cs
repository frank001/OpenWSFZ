using System.Threading.Channels;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using NSubstitute;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using OpenWSFZ.TestSupport;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Two-stage publish, the pump half (sub-feas-speed-redesign design.md D9; tasks.md 13.10/13.11 tests (a) to (f), (i)).
/// <see cref="DecodePump"/> is driven with recording delegates in place of the real bus, ALL.TXT writer, archive,
/// filter store and consumer channels, and a fake decoder in place of <c>Ft8Decoder</c>, so nothing here needs the
/// daemon host.
///
/// <para>🔒 NFR-021 / HK-037: synthetic Q-prefix messages; assertions on counts, order and identity, no log text.</para>
/// </summary>
[Trait("Category", "Unit")]
public sealed class DecodePumpTests
{
    private static readonly DateTime Cycle1 = new(2026, 9, 30, 12, 0, 0, DateTimeKind.Utc);
    private static readonly DateTime Cycle2 = Cycle1.AddSeconds(15);
    private const double Dial = 14.074;

    private static DecodeResult R(string message, int freq = 1500)
        => new(Time: "12:00:00", Snr: -10, Dt: 0.2, FreqHz: freq, Message: message);

    /// <summary>Everything the pump publishes to, recorded in call order.</summary>
    private sealed class Rig
    {
        public readonly List<string> Events = [];
        public readonly List<IReadOnlyList<DecodeResult>> Panel = [];
        public readonly List<(DateTime Stamp, IReadOnlyList<DecodeResult> Results)> AllTxt = [];
        public readonly List<(DateTime Stamp, int Count)> Archive = [];
        public readonly List<string> Admitted = [];
        public readonly Channel<DecodeBatch> Answerer = Channel.CreateUnbounded<DecodeBatch>();
        public readonly Channel<DecodeBatch> Caller   = Channel.CreateUnbounded<DecodeBatch>();
        public readonly Channel<DecodeBatch> External = Channel.CreateUnbounded<DecodeBatch>();
        public bool FlagOn;
        public double? CurrentDial = Dial;
        public Func<float[], DateTime, string?, Func<IReadOnlyList<DecodeResult>, Task>, Task<IReadOnlyList<DecodeResult>>>? TwoStage;
        public Func<DateTime, IReadOnlyList<DecodeResult>>? Single;
        public Func<IReadOnlyList<DecodeResult>, IReadOnlyList<DecodeResult>> Suppress = r => r;
        public int SingleCalls, TwoStageCalls, StagedCalls;
        public bool Deep;
        public Func<Func<int, IReadOnlyList<DecodeResult>, Task>, Task>? Staged;

        public DecodePump Build() => new(new DecodePumpDependencies(
            CurrentDialFrequency:     () => CurrentDial,
            FallbackDialFrequency:    () => 0.0,
            DeriveBand:               _ => "20m",
            SubtractionEnabled:       () => FlagOn,
            DecodeSingleBatch:        (pcm, cs, band, _) =>
            {
                lock (Events) { SingleCalls++; Events.Add($"decode-single:{cs:mm:ss}"); }
                return Task.FromResult(Single!(cs));
            },
            DecodeTwoStage:           async (pcm, cs, band, publishFirst, _) =>
            {
                lock (Events) { TwoStageCalls++; Events.Add($"decode-start:{cs:mm:ss}"); }
                return await TwoStage!(pcm, cs, band, publishFirst);
            },
            ApplyNoiseSuppression:    r => Suppress(r),
            PublishToPanel:           r => { lock (Events) { Panel.Add(r); Events.Add($"panel:{r.Count}"); } return Task.CompletedTask; },
            AppendAllTxt:             (stamp, dial, r) => { lock (Events) { AllTxt.Add((stamp, r)); Events.Add($"alltxt:{r.Count}"); } return Task.CompletedTask; },
            EnqueueArchive:           (pcm, cs, closed, count, dial) => { lock (Events) { Archive.Add((cs, count)); Events.Add($"archive:{count}"); } },
            AdmitNewValues:           r => { lock (Events) { Admitted.Add(r.Message); Events.Add("admit"); } return null; },
            PublishFilterState:       _ => { },
            AnswererChannel:          Answerer.Writer,
            CallerChannel:            Caller.Writer,
            ExternalReportingChannel: External.Writer,
            Logger:                   NullLogger.Instance)
        {
            // third-pass-deep (#240): the staged entry, used only while Deep is on (and the residual pass is).
            DecodeStaged = async (pcm, cs, band, publishBatch, _) =>
            {
                lock (Events) { StagedCalls++; Events.Add($"decode-staged:{cs:mm:ss}"); }
                await Staged!(publishBatch);
            },
            DecodingDeep = () => Deep,
        });

        public static async IAsyncEnumerable<(float[] Pcm, DateTime CycleStart, double? DialFrequency)> Windows(
            params DateTime[] cycles)
        {
            foreach (var c in cycles)
                yield return (new float[180_000], c, Dial);
            await Task.CompletedTask;
        }

        public List<DecodeBatch> Drain(Channel<DecodeBatch> ch)
        {
            var l = new List<DecodeBatch>();
            while (ch.Reader.TryRead(out var b)) l.Add(b);
            return l;
        }
    }

    private static Func<float[], DateTime, string?, Func<IReadOnlyList<DecodeResult>, Task>, Task<IReadOnlyList<DecodeResult>>>
        TwoBatches(IReadOnlyList<DecodeResult> b1, IReadOnlyList<DecodeResult> b2)
        => async (_, _, _, publish) => { await publish(b1); return b2; };

    // ── S3 (a): the answerer and caller receive exactly one batch per flag-ON cycle ──

    [Fact(DisplayName = "S3(a) [late-batches-in-qso: policy reversed]: flag ON — the answerer and caller receive batch 1 then batch 2 of the cycle, numbered 1 and 2")]
    public async Task AnswererAndCaller_Batch1ThenBatch2_Numbered()
    {
        var rig = new Rig { FlagOn = true };
        var b1 = new[] { R("CQ Q1ABC JO33") };
        var b2 = new[] { R("CQ Q1DEF EN37", 2100) };
        rig.TwoStage = TwoBatches(b1, b2);

        await rig.Build().RunAsync(Rig.Windows(Cycle1), CancellationToken.None);

        var answerer = rig.Drain(rig.Answerer);
        var caller   = rig.Drain(rig.Caller);
        answerer.Should().HaveCount(2, "batch 2 now reaches the answerer, as a supplementary batch");
        caller.Should().HaveCount(2);
        answerer[0].Results.Should().Equal(b1);
        answerer[0].BatchNumber.Should().Be(1);
        answerer[1].Results.Should().Equal(b2);
        answerer[1].BatchNumber.Should().Be(2);
        caller[0].Results.Should().Equal(b1);
        caller[0].BatchNumber.Should().Be(1);
        caller[1].Results.Should().Equal(b2);
        caller[1].BatchNumber.Should().Be(2);
        answerer[0].CycleStart.Should().Be(new DateTimeOffset(Cycle1, TimeSpan.Zero));
        answerer[1].CycleStart.Should().Be(answerer[0].CycleStart, "same cycle");
    }

    // ── S3 (b): _lastIdleDecodeBatch after a flag-ON cycle equals batch 1 (real answerer) ──

    [Fact(DisplayName = "S3(b)+(h) [late-batches-in-qso: policy reversed]: the real answerer's idle snapshot is batch 1 plus batch 2 of the cycle, so a reply naming a pass-0 station and a reply naming a batch-2 station both engage")]
    public async Task RealAnswerer_SnapshotMergesBatch2_ExternalReplyForBothStationsEngages()
    {
        var rig = new Rig { FlagOn = true };
        var b1 = new[] { R("CQ Q1ABC JO33") };
        var b2 = new[] { R("CQ Q1DEF EN37", 2100) };
        rig.TwoStage = TwoBatches(b1, b2);
        await rig.Build().RunAsync(Rig.Windows(Cycle1), CancellationToken.None);

        await using var sut = await AnswererHarness.CreateAsync();
        // The pump's answerer channel is drained into the real service exactly as Program.cs wires it.
        foreach (var batch in rig.Drain(rig.Answerer)) sut.Channel.Writer.TryWrite(batch);
        await sut.WaitForIdleSnapshotAsync(expectedResultCount: 2);

        (await sut.Service.TryEngageExternal("Q1DEF")).Should().BeTrue(
            "a station heard only in batch 2 is in the merged snapshot: the reply engages (late-batches-in-qso D4)");
        sut.Service._wakeupChannel.Reader.TryRead(out _);
        // A second reply is refused only because the first one already engaged (state no longer Idle): re-create to check the other station.
        await using var sut2 = await AnswererHarness.CreateAsync();
        foreach (var batch in rig2Batches(b1, b2)) sut2.Channel.Writer.TryWrite(batch);
        await sut2.WaitForIdleSnapshotAsync(expectedResultCount: 2);
        (await sut2.Service.TryEngageExternal("Q1ABC")).Should().BeTrue(
            "the pass-0 station is still engageable: batch 2 appended to the snapshot, it did not replace it");
        sut2.Service._wakeupChannel.Reader.TryRead(out _);
    }

    private static IEnumerable<DecodeBatch> rig2Batches(DecodeResult[] b1, DecodeResult[] b2)
    {
        var cs = new DateTimeOffset(Cycle1, TimeSpan.Zero);
        yield return new DecodeBatch(cs, b1, 1);
        yield return new DecodeBatch(cs, b2, 2);
    }

    // ── S3 (c): ALL.TXT holds batch 1's lines then batch 2's, same stamp ──

    [Fact(DisplayName = "S3(c): ALL.TXT gets batch 1 then batch 2, both under the same cycle stamp, unfiltered")]
    public async Task AllTxt_Batch1ThenBatch2_SameStamp_Unfiltered()
    {
        var rig = new Rig { FlagOn = true };
        var b1 = new[] { R("CQ Q1ABC JO33") };
        var b2 = new[] { R("CQ Q1DEF EN37", 2100), R("Q1GHI Q1JKL -05", 900) };
        rig.TwoStage = TwoBatches(b1, b2);
        // Suppression hides Q1JKL's row from the panel and the consumers, but ALL.TXT is never filtered.
        rig.Suppress = r => r.Where(x => !x.Message.Contains("Q1JKL")).ToList();

        await rig.Build().RunAsync(Rig.Windows(Cycle1), CancellationToken.None);

        rig.AllTxt.Select(a => a.Stamp).Should().Equal(Cycle1, Cycle1);
        rig.AllTxt[0].Results.Should().Equal(b1);
        rig.AllTxt[1].Results.Should().Equal(b2, "ALL.TXT always receives the unfiltered results");
        rig.Panel[1].Should().HaveCount(1, "the panel only gets what decode-noise-suppression lets through");
        rig.AllTxt.SelectMany(a => a.Results).Select(r => r.Message).Should().OnlyHaveUniqueItems();
    }

    // ── S3 (d): the panel receives two decode events and shows the union ──

    [Fact(DisplayName = "S3(d): the panel receives two decode events (batch 1 then batch 2): appended, never replaced")]
    public async Task Panel_TwoEvents_Union()
    {
        var rig = new Rig { FlagOn = true };
        var b1 = new[] { R("CQ Q1ABC JO33") };
        var b2 = new[] { R("CQ Q1DEF EN37", 2100) };
        rig.TwoStage = TwoBatches(b1, b2);

        await rig.Build().RunAsync(Rig.Windows(Cycle1), CancellationToken.None);

        rig.Panel.Should().HaveCount(2);
        rig.Panel[0].Should().Equal(b1);
        rig.Panel[1].Should().Equal(b2);
        rig.Panel.SelectMany(p => p).Select(r => r.Message).Should().BeEquivalentTo(["CQ Q1ABC JO33", "CQ Q1DEF EN37"]);
    }

    // ── S3 (e) and P-6: the archive enqueues once, at batch 1, with the pass-0 count ──

    [Fact(DisplayName = "S3(e): the cycle-audio archive enqueues exactly once per flag-ON cycle, at batch 1, with the pass-0 count")]
    public async Task Archive_OncePerCycle_WithPass0Count()
    {
        var rig = new Rig { FlagOn = true };
        rig.TwoStage = TwoBatches([R("CQ Q1ABC JO33"), R("Q1AAA Q1BBB -01", 900)], [R("CQ Q1DEF EN37", 2100)]);

        await rig.Build().RunAsync(Rig.Windows(Cycle1), CancellationToken.None);

        rig.Archive.Should().Equal([(Cycle1, 2)], "decodeCount is the pass-0 count, not the union");
    }

    // ── S3 (f) and P-9: flag OFF is one publish per cycle, through the single-batch path ──

    [Fact(DisplayName = "S3(f): flag OFF — one publish per cycle, the single-batch decode, in the original order")]
    public async Task FlagOff_OnePublishPerCycle_OriginalOrder()
    {
        var rig = new Rig { FlagOn = false, Single = _ => [R("CQ Q1ABC JO33")] };

        await rig.Build().RunAsync(Rig.Windows(Cycle1, Cycle2), CancellationToken.None);

        rig.TwoStageCalls.Should().Be(0, "flag OFF never touches the two-batch machinery");
        rig.SingleCalls.Should().Be(2);
        rig.Panel.Should().HaveCount(2);
        rig.AllTxt.Should().HaveCount(2);
        rig.Archive.Should().HaveCount(2);
        rig.Drain(rig.Answerer).Should().HaveCount(2);
        rig.Drain(rig.Caller).Should().HaveCount(2);
        rig.Drain(rig.External).Should().HaveCount(2);
        // The order the inline pump always used: panel, ALL.TXT, archive, admission (per result).
        rig.Events.Take(5).Should().Equal("decode-single:00:00", "panel:1", "alltxt:1", "archive:1", "admit");
    }

    // ── P-2 / P-4: batch 2 only when there is one; it reaches admission and external reporting ──

    [Fact(DisplayName = "P-2: nothing is published for batch 2 when the pass was abandoned or found nothing new")]
    public async Task NoBatch2_NothingPublished()
    {
        var rig = new Rig { FlagOn = true };
        rig.TwoStage = TwoBatches([R("CQ Q1ABC JO33")], []);

        await rig.Build().RunAsync(Rig.Windows(Cycle1), CancellationToken.None);

        rig.Panel.Should().ContainSingle();
        rig.AllTxt.Should().ContainSingle();
        rig.Drain(rig.External).Should().ContainSingle();
    }

    [Fact(DisplayName = "P-4 [late-batches-in-qso: policy reversed]: batch 2 reaches decode-filter admission, the external-reporting channel, and (as batch number 2) the answerer and caller channels")]
    public async Task Batch2_AdmissionExternalReportingAndQsoServices()
    {
        var rig = new Rig { FlagOn = true };
        rig.TwoStage = TwoBatches([R("CQ Q1ABC JO33")], [R("CQ Q1DEF EN37", 2100)]);

        await rig.Build().RunAsync(Rig.Windows(Cycle1), CancellationToken.None);

        rig.Admitted.Should().Equal("CQ Q1ABC JO33", "CQ Q1DEF EN37");
        var external = rig.Drain(rig.External);
        external.Should().HaveCount(2);
        external[1].Results.Select(r => r.Message).Should().Equal("CQ Q1DEF EN37");
        external[1].CycleStart.Should().Be(external[0].CycleStart, "same cycle");
        external[1].BatchNumber.Should().Be(2);
        var answerer = rig.Drain(rig.Answerer);
        var caller   = rig.Drain(rig.Caller);
        answerer.Select(b => b.BatchNumber).Should().Equal(1, 2);
        caller.Select(b => b.BatchNumber).Should().Equal(1, 2);
        answerer[1].Results.Select(r => r.Message).Should().Equal("CQ Q1DEF EN37");
        caller[1].Results.Select(r => r.Message).Should().Equal("CQ Q1DEF EN37");
    }

    // ── S3 (i) and P-7: the pump stays serial ──

    [Fact(DisplayName = "S3(i): the pump starts no next window before batch 2 is published or the pass is abandoned")]
    public async Task Pump_StaysSerial()
    {
        var rig = new Rig { FlagOn = true };
        var release = new TaskCompletionSource();
        int call = 0;
        rig.TwoStage = async (_, cs, _, publish) =>
        {
            if (Interlocked.Increment(ref call) == 1)
            {
                await publish([R("CQ Q1ABC JO33")]);
                await release.Task;                       // the residual pass is still running
                return [R("CQ Q1DEF EN37", 2100)];
            }
            await publish([R("Q1AAA Q1BBB -01", 900)]);
            return [];
        };

        var run = rig.Build().RunAsync(Rig.Windows(Cycle1, Cycle2), CancellationToken.None);

        await Poll.UntilAsync(() => rig.Panel.Count >= 1, timeout: TimeSpan.FromSeconds(2), timeoutMessage: () => "batch 1 was never published");
        await Task.Delay(300);
        lock (rig.Events)
            rig.Events.Should().NotContain("decode-start:00:15", "window 2 must not be decoded while window 1's pass runs");
        release.SetResult();
        await run;

        var starts = rig.Events.Where(e => e.StartsWith("decode-start") || e.StartsWith("panel")).ToList();
        // window 1's batch 2 (the second panel:1) is published before window 2's decode starts
        starts.Should().Equal(["decode-start:00:00", "panel:1", "panel:1", "decode-start:00:15", "panel:1"]);
    }

    // ── robustness ──

    [Fact(DisplayName = "A decode error in one window is logged and the pump carries on with the next window")]
    public async Task DecodeError_PumpContinues()
    {
        var rig = new Rig { FlagOn = true };
        int call = 0;
        rig.TwoStage = async (_, _, _, publish) =>
        {
            if (Interlocked.Increment(ref call) == 1) throw new InvalidOperationException("boom");
            await publish([R("CQ Q1ABC JO33")]);
            return [];
        };

        await rig.Build().RunAsync(Rig.Windows(Cycle1, Cycle2), CancellationToken.None);

        rig.Panel.Should().ContainSingle("the second window was still decoded and published");
    }

    [Fact(DisplayName = "A window whose dial frequency changed during capture is discarded (FR-032), before any decode")]
    public async Task DialFrequencyChange_WindowDiscarded()
    {
        var rig = new Rig { FlagOn = true, CurrentDial = 7.074 };
        rig.TwoStage = TwoBatches([R("CQ Q1ABC JO33")], []);

        await rig.Build().RunAsync(Rig.Windows(Cycle1), CancellationToken.None);

        rig.TwoStageCalls.Should().Be(0);
        rig.Panel.Should().BeEmpty();
    }

    // ── shared: a real QsoAnswererService, as in QsoAnswererServiceExternalReplyTests ──

    internal sealed class AnswererHarness : IAsyncDisposable
    {
        public required QsoAnswererService Service { get; init; }
        public required Channel<DecodeBatch> Channel { get; init; }
        public required IPttController Ptt { get; init; }
        public required RecordingLogger Log { get; init; }
        public required CancellationTokenSource Cts { get; init; }

        public static async Task<AnswererHarness> CreateAsync(bool autoAnswer = false)
        {
            var config = new AppConfig() with
            {
                Tx = new TxConfig { AutoAnswer = autoAnswer, Callsign = "Q1OFZ", Grid = "JO33", RetryCount = 2, WatchdogMinutes = 4 },
            };
            var store = new MutableConfigStore(config);
            var ptt = Substitute.For<IPttController>();
            ptt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
            ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
            var channel = System.Threading.Channels.Channel.CreateUnbounded<DecodeBatch>();
            var log = new RecordingLogger();
            var service = new QsoAnswererService(channel.Reader, store, ptt, new OpenWSFZ.Web.TxEventBus(),
                new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance), new OpenWSFZ.Web.AudioOffsetEventBus(), log,
                watchdogDurationOverride: TimeSpan.FromMinutes(4), timeProvider: null, catState: null, decodeFilterStore: null);
            var cts = new CancellationTokenSource();
            await service.StartAsync(cts.Token);
            return new AnswererHarness { Service = service, Channel = channel, Ptt = ptt, Log = log, Cts = cts };
        }

        public async Task WaitForIdleSnapshotAsync(int expectedResultCount = 0)
        {
            var field = typeof(QsoAnswererService).GetField("_lastIdleDecodeBatch",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)!;
            await Poll.UntilAsync(
                () => field.GetValue(Service) is DecodeBatch snap && snap.Results.Count >= expectedResultCount,
                timeout: TimeSpan.FromSeconds(2),
                timeoutMessage: () => "the answerer never recorded the expected batch(es)");
        }

        public async ValueTask DisposeAsync()
        {
            await Cts.CancelAsync();
            await Service.StopAsync(CancellationToken.None);
            await Ptt.DisposeAsync();
            Cts.Dispose();
        }
    }

    internal sealed class MutableConfigStore(AppConfig initial) : IConfigStore
    {
        private AppConfig _current = initial;
        public AppConfig Current => _current;
        public event Action<AppConfig>? OnSaved;
        public Task SaveAsync(AppConfig config, CancellationToken ct = default)
        {
            _current = config;
            OnSaved?.Invoke(config);
            return Task.CompletedTask;
        }
    }

    internal sealed class RecordingLogger : ILogger<QsoAnswererService>
    {
        private readonly List<string> _entries = [];
        public IReadOnlyList<string> Entries { get { lock (_entries) return _entries.ToList(); } }
        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => true;
        public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception,
            Func<TState, Exception?, string> formatter)
        {
            lock (_entries) _entries.Add(formatter(state, exception));
        }
    }
    // ── third-pass-deep (#240): batch 3 ─────────────────────────────────────────────────────────────

    [Fact(DisplayName = "Third pass: Deep + flag ON — the staged entry is used instead of the two-stage one; batch 1 reaches every consumer, batches 2 and 3 the batch-2 sinks and (late-batches-in-qso) the answerer and caller, numbered 2 and 3")]
    public async Task Deep_StagedEntry_Batch3GoesWhereBatch2Goes()
    {
        var rig = new Rig { FlagOn = true, Deep = true };
        var b1 = new[] { R("CQ Q1ABC JO33") };
        var b2 = new[] { R("CQ Q1DEF EN37", 2100) };
        var b3 = new[] { R("CQ Q1GHI FN20", 2400) };
        rig.Staged = async publish =>
        {
            await publish(1, b1);
            await publish(2, b2);
            await publish(3, b3);
        };

        await rig.Build().RunAsync(Rig.Windows(Cycle1), CancellationToken.None);

        rig.StagedCalls.Should().Be(1);
        rig.TwoStageCalls.Should().Be(0, "Deep takes the staged entry");
        rig.SingleCalls.Should().Be(0);
        rig.Panel.Should().HaveCount(3);
        rig.Panel[0].Should().Equal(b1);
        rig.Panel[1].Should().Equal(b2);
        rig.Panel[2].Should().Equal(b3);
        rig.AllTxt.Select(a => a.Results.Count).Should().Equal(1, 1, 1);
        rig.AllTxt.Select(a => a.Stamp).Should().OnlyContain(t => t == Cycle1, "all three batches carry the cycle's stamp");
        rig.Admitted.Should().Equal("CQ Q1ABC JO33", "CQ Q1DEF EN37", "CQ Q1GHI FN20");
        rig.Archive.Should().ContainSingle("the archive runs once per cycle, at batch 1");

        var answerer = rig.Drain(rig.Answerer);
        var caller   = rig.Drain(rig.Caller);
        answerer.Select(b => b.BatchNumber).Should().Equal(1, 2, 3);
        caller.Select(b => b.BatchNumber).Should().Equal(1, 2, 3);
        answerer.Select(b => b.Results[0].Message).Should().Equal("CQ Q1ABC JO33", "CQ Q1DEF EN37", "CQ Q1GHI FN20");
        caller.Select(b => b.Results[0].Message).Should().Equal("CQ Q1ABC JO33", "CQ Q1DEF EN37", "CQ Q1GHI FN20");
        var external = rig.Drain(rig.External);
        external.Select(b => b.Results.Count).Should().Equal(1, 1, 1);
        external.Select(b => b.BatchNumber).Should().Equal(1, 2, 3);
    }

    [Fact(DisplayName = "Third pass: Deep with no batch 2 or 3 (staged entry delivers batch 1 only) — a single, ordinary batch-1 publish")]
    public async Task Deep_OnlyBatch1_IsOrdinary()
    {
        var rig = new Rig { FlagOn = true, Deep = true };
        var b1 = new[] { R("CQ Q1ABC JO33") };
        rig.Staged = async publish => { await publish(1, b1); };

        await rig.Build().RunAsync(Rig.Windows(Cycle1), CancellationToken.None);

        rig.Panel.Should().ContainSingle();
        rig.Drain(rig.Answerer).Should().ContainSingle();
    }

    [Fact(DisplayName = "Third pass: Normal (Deep off) — the two-stage entry as ever, the staged entry never called")]
    public async Task Normal_UsesTwoStageEntry()
    {
        var rig = new Rig { FlagOn = true, Deep = false };
        rig.TwoStage = TwoBatches([R("CQ Q1ABC JO33")], [R("CQ Q1DEF EN37", 2100)]);
        rig.Staged = _ => throw new InvalidOperationException("must not be called");

        await rig.Build().RunAsync(Rig.Windows(Cycle1), CancellationToken.None);

        rig.TwoStageCalls.Should().Be(1);
        rig.StagedCalls.Should().Be(0);
        rig.Panel.Should().HaveCount(2);
    }

    [Fact(DisplayName = "Third pass: Deep but the residual flag OFF — the ordinary single batch, no staged entry")]
    public async Task Deep_WithFlagOff_IsSingleBatch()
    {
        var rig = new Rig { FlagOn = false, Deep = true };
        rig.Single = _ => [R("CQ Q1ABC JO33")];
        rig.Staged = _ => throw new InvalidOperationException("must not be called");

        await rig.Build().RunAsync(Rig.Windows(Cycle1), CancellationToken.None);

        rig.SingleCalls.Should().Be(1);
        rig.StagedCalls.Should().Be(0);
    }
}
