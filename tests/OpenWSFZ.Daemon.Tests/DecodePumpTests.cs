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
        public int SingleCalls, TwoStageCalls;

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
            Logger:                   NullLogger.Instance));

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

    [Fact(DisplayName = "S3(a): flag ON — the answerer and caller receive exactly one batch per cycle, and it is batch 1")]
    public async Task AnswererAndCaller_ExactlyOneBatch_IsBatch1()
    {
        var rig = new Rig { FlagOn = true };
        var b1 = new[] { R("CQ Q1ABC JO33") };
        var b2 = new[] { R("CQ Q1DEF EN37", 2100) };
        rig.TwoStage = TwoBatches(b1, b2);

        await rig.Build().RunAsync(Rig.Windows(Cycle1), CancellationToken.None);

        var answerer = rig.Drain(rig.Answerer);
        var caller   = rig.Drain(rig.Caller);
        answerer.Should().ContainSingle();
        caller.Should().ContainSingle();
        answerer[0].Results.Should().Equal(b1, "the answerer's idle snapshot after a flag-ON cycle is batch 1 (P-5)");
        caller[0].Results.Should().Equal(b1);
        answerer[0].CycleStart.Should().Be(new DateTimeOffset(Cycle1, TimeSpan.Zero));
    }

    // ── S3 (b): _lastIdleDecodeBatch after a flag-ON cycle equals batch 1 (real answerer) ──

    [Fact(DisplayName = "S3(b)+(h): the real answerer's idle snapshot equals batch 1, so a reply naming a pass-0 station still engages and a reply naming a batch-2 station is ignored")]
    public async Task RealAnswerer_SnapshotIsBatch1_ExternalReplyForBatch2StationIgnored()
    {
        var rig = new Rig { FlagOn = true };
        var b1 = new[] { R("CQ Q1ABC JO33") };
        var b2 = new[] { R("CQ Q1DEF EN37", 2100) };
        rig.TwoStage = TwoBatches(b1, b2);
        await rig.Build().RunAsync(Rig.Windows(Cycle1), CancellationToken.None);

        await using var sut = await AnswererHarness.CreateAsync();
        // The pump's answerer channel is drained into the real service exactly as Program.cs wires it.
        foreach (var batch in rig.Drain(rig.Answerer)) sut.Channel.Writer.TryWrite(batch);
        await sut.WaitForIdleSnapshotAsync();

        (await sut.Service.TryEngageExternal("Q1DEF")).Should().BeFalse(
            "a station heard only in batch 2 is not in the answerer's snapshot: the reply is ignored (P-5)");
        sut.Log.Entries.Should().Contain(e => e.Contains("is not present as a CQ in the most recent decode batch"),
            "with the existing log line");

        (await sut.Service.TryEngageExternal("Q1ABC")).Should().BeTrue(
            "the pass-0 station is still engageable: batch 2 did not overwrite the snapshot");
        sut.Service._wakeupChannel.Reader.TryRead(out _);
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

    [Fact(DisplayName = "P-4: batch 2 reaches decode-filter admission and the external-reporting channel (and only that channel of the three)")]
    public async Task Batch2_AdmissionAndExternalReporting()
    {
        var rig = new Rig { FlagOn = true };
        rig.TwoStage = TwoBatches([R("CQ Q1ABC JO33")], [R("CQ Q1DEF EN37", 2100)]);

        await rig.Build().RunAsync(Rig.Windows(Cycle1), CancellationToken.None);

        rig.Admitted.Should().Equal("CQ Q1ABC JO33", "CQ Q1DEF EN37");
        var external = rig.Drain(rig.External);
        external.Should().HaveCount(2);
        external[1].Results.Select(r => r.Message).Should().Equal("CQ Q1DEF EN37");
        external[1].CycleStart.Should().Be(external[0].CycleStart, "same cycle");
        rig.Drain(rig.Answerer).Should().ContainSingle();
        rig.Drain(rig.Caller).Should().ContainSingle();
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

        public async Task WaitForIdleSnapshotAsync()
        {
            var field = typeof(QsoAnswererService).GetField("_lastIdleDecodeBatch",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)!;
            await Poll.UntilAsync(() => field.GetValue(Service) is not null, timeout: TimeSpan.FromSeconds(2),
                timeoutMessage: () => "the answerer never recorded a batch");
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
}
