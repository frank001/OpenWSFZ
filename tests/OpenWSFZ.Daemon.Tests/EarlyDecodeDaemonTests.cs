using System.Threading.Channels;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using OpenWSFZ.TestSupport;
using OpenWSFZ.Web;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// decode-early-batch-panel (#122 step 4, phase 4a; FR-083), the daemon half: the matcher (task 6.1), the coordinator
/// and the early service (5.2), the decode gate and the pump (5.1, 5.4), and the flag-OFF characterisation (5.4).
/// Everything is driven with recording delegates: no host, no native library, no clock, no real delay.
///
/// <para>🔒 NFR-021 / HK-037: synthetic Q-prefix messages; assertions on counts, order and identity; the only log text
/// read is the R7 line's field names, never a message.</para>
/// </summary>
[Trait("Category", "Unit")]
public sealed class EarlyDecodeDaemonTests
{
    private static readonly DateTime Cycle1 = new(2026, 10, 3, 12, 0, 0, DateTimeKind.Utc);
    private static readonly DateTime Cycle2 = Cycle1.AddSeconds(15);
    private const double Dial = 14.074;

    private static DecodeResult R(string message, int freq = 1500)
        => new(Time: "12:00:00", Snr: -10, Dt: 0.2, FreqHz: freq, Message: message);

    private static EarlyRow E(long id, string message, int freq = 1500) => new(id, R(message, freq));

    // ── 6.1 the matcher ───────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-083: 6.1a same text within 10 Hz confirms, and carries the index of the final row that replaces it")]
    public void Matcher_SameTextWithin10Hz_Confirms()
    {
        var res = EarlyDecodeMatcher.Match([E(1, "CQ Q1ABC JO33", 1500)], [R("CQ Q9ZZZ AA11", 700), R("CQ Q1ABC JO33", 1510)]);

        res.Should().ContainSingle();
        res[0].Should().Be(new EarlyResolution(1, EarlyResolution.Confirmed, 1));
    }

    [Theory(DisplayName = "FR-083: 6.1b more than 10 Hz apart, or a different text, is unconfirmed")]
    [InlineData("CQ Q1ABC JO33", 1511)]
    [InlineData("CQ Q1ABC JO34", 1500)]
    public void Matcher_TooFarOrDifferent_Unconfirmed(string finalText, int finalFreq)
    {
        var res = EarlyDecodeMatcher.Match([E(1, "CQ Q1ABC JO33", 1500)], [R(finalText, finalFreq)]);

        res.Should().ContainSingle().Which.Should().Be(new EarlyResolution(1, EarlyResolution.Unconfirmed));
    }

    [Fact(DisplayName = "FR-083: 6.1c two candidates: the smaller |Δf| wins, and a tie goes to the earlier early row")]
    public void Matcher_TwoCandidates_SmallestDeltaThenEarlier()
    {
        // Smallest |Δf| wins even when it is the later early row.
        var near = EarlyDecodeMatcher.Match([E(1, "CQ Q1ABC JO33", 1495), E(2, "CQ Q1ABC JO33", 1502)], [R("CQ Q1ABC JO33", 1500)]);
        near.Should().Equal(new EarlyResolution(1, EarlyResolution.Unconfirmed), new EarlyResolution(2, EarlyResolution.Confirmed, 0));

        // A tie in |Δf| goes to the earlier early row.
        var tie = EarlyDecodeMatcher.Match([E(1, "CQ Q1ABC JO33", 1495), E(2, "CQ Q1ABC JO33", 1505)], [R("CQ Q1ABC JO33", 1500)]);
        tie.Should().Equal(new EarlyResolution(1, EarlyResolution.Confirmed, 0), new EarlyResolution(2, EarlyResolution.Unconfirmed));
    }

    [Fact(DisplayName = "FR-083: 6.1d one-to-one: an early row confirms at most one final row and the reverse (a repeated text)")]
    public void Matcher_RepeatedText_IsOneToOne()
    {
        // Two final rows of the same text, one early row: only the first final row is replaced; the early row is not reused.
        var oneEarly = EarlyDecodeMatcher.Match([E(1, "CQ Q1ABC JO33", 1500)], [R("CQ Q1ABC JO33", 1500), R("CQ Q1ABC JO33", 1502)]);
        oneEarly.Should().ContainSingle().Which.Should().Be(new EarlyResolution(1, EarlyResolution.Confirmed, 0));

        // Two early rows, two final rows of the same text: each final row takes the nearest still-free early row.
        var two = EarlyDecodeMatcher.Match(
            [E(1, "CQ Q1ABC JO33", 1500), E(2, "CQ Q1ABC JO33", 1800)],
            [R("CQ Q1ABC JO33", 1799), R("CQ Q1ABC JO33", 1501)]);
        two.Should().Equal(new EarlyResolution(1, EarlyResolution.Confirmed, 1), new EarlyResolution(2, EarlyResolution.Confirmed, 0));
    }

    [Fact(DisplayName = "FR-083: 6.1e an empty final batch resolves every early row as unconfirmed; no early rows resolve nothing")]
    public void Matcher_EmptyBatches()
    {
        EarlyDecodeMatcher.Match([E(1, "CQ Q1ABC JO33"), E(2, "CQ Q1DEF EN37", 2000)], [])
            .Should().OnlyContain(r => r.Outcome == EarlyResolution.Unconfirmed).And.HaveCount(2);
        EarlyDecodeMatcher.Match([], [R("CQ Q1ABC JO33")]).Should().BeEmpty();
    }

    [Fact(DisplayName = "FR-083: 6.1f the matcher is deterministic: the same inputs give the same resolutions every time")]
    public void Matcher_IsDeterministic()
    {
        var early = new[] { E(1, "CQ Q1ABC JO33", 1500), E(2, "CQ Q1ABC JO33", 1505), E(3, "Q1AAA Q1BBB -01", 900) };
        var final = new[] { R("Q1AAA Q1BBB -01", 905), R("CQ Q1ABC JO33", 1503), R("CQ Q1ABC JO33", 1499) };
        var first = EarlyDecodeMatcher.Match(early, final);
        for (int i = 0; i < 50; i++) EarlyDecodeMatcher.Match(early, final).Should().Equal(first);
    }

    // ── Recording rig: the pump, the coordinator and the service share one set of recorders ───────────────────

    private sealed class ListLogger : ILogger
    {
        public readonly List<string> Lines = [];
        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel logLevel) => true;
        public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception,
            Func<TState, Exception?, string> formatter) { lock (Lines) Lines.Add(formatter(state, exception)); }
    }

    private sealed class Rig
    {
        public readonly List<string> Events = [];
        public readonly List<IReadOnlyList<DecodeResult>> Panel = [];
        public readonly List<(IReadOnlyList<DecodeResult> Results, IReadOnlyList<EarlyResolution>? Resolves)> Frames = [];
        public readonly List<IReadOnlyList<EarlyRow>> EarlyFrames = [];
        public readonly List<(DateTime Stamp, IReadOnlyList<DecodeResult> Results)> AllTxt = [];
        public readonly List<(DateTime Stamp, int Count)> Archive = [];
        public readonly List<string> Admitted = [];
        public readonly Channel<DecodeBatch> Answerer = Channel.CreateUnbounded<DecodeBatch>();
        public readonly Channel<DecodeBatch> Caller   = Channel.CreateUnbounded<DecodeBatch>();
        public readonly Channel<DecodeBatch> External = Channel.CreateUnbounded<DecodeBatch>();
        public readonly ListLogger Log = new();
        public double? CurrentDial = Dial;
        public Func<DateTime, Task<IReadOnlyList<DecodeResult>>> FinalDecode = _ => Task.FromResult<IReadOnlyList<DecodeResult>>([]);
        public Func<DateTime, Task<IReadOnlyList<DecodeResult>>> EarlyDecode = _ => Task.FromResult<IReadOnlyList<DecodeResult>>([]);
        public Func<IReadOnlyList<DecodeResult>, IReadOnlyList<DecodeResult>> Suppress = r => r;
        public Action? OnDeriveBand;
        public Action? OnEarlyPublish;
        public int EarlyDecodeCalls, FinalDecodeCalls;

        public EarlyDecodeCoordinator NewCoordinator() => new(Log, (results, resolves) =>
        {
            lock (Events) { Frames.Add((results, resolves)); Events.Add($"frame:{results.Count}:{resolves?.Count.ToString() ?? "-"}"); }
            return Task.CompletedTask;
        });

        public DecodePump BuildPump(EarlyDecodeCoordinator? early) => new(new DecodePumpDependencies(
            CurrentDialFrequency:     () => CurrentDial,
            FallbackDialFrequency:    () => 0.0,
            DeriveBand:               _ => { OnDeriveBand?.Invoke(); return "20m"; },
            SubtractionEnabled:       () => false,
            DecodeSingleBatch:        async (pcm, cs, band, _) =>
            {
                lock (Events) { FinalDecodeCalls++; Events.Add($"decode-single:{cs:mm:ss}"); }
                return await FinalDecode(cs);
            },
            DecodeTwoStage:           (pcm, cs, band, publishFirst, _) => throw new InvalidOperationException("flag is OFF in this rig"),
            ApplyNoiseSuppression:    r => Suppress(r),
            PublishToPanel:           r => { lock (Events) { Panel.Add(r); Events.Add($"panel:{r.Count}"); } return Task.CompletedTask; },
            AppendAllTxt:             (stamp, dial, r) => { lock (Events) { AllTxt.Add((stamp, r)); Events.Add($"alltxt:{r.Count}"); } return Task.CompletedTask; },
            EnqueueArchive:           (pcm, cs, closed, count, dial) => { lock (Events) { Archive.Add((cs, count)); Events.Add($"archive:{count}"); } },
            AdmitNewValues:           r => { lock (Events) { Admitted.Add(r.Message); Events.Add("admit"); } return null; },
            PublishFilterState:       _ => { },
            AnswererChannel:          Answerer.Writer,
            CallerChannel:            Caller.Writer,
            ExternalReportingChannel: External.Writer,
            Logger:                   Log)
        { Early = early });

        public EarlyDecodeService BuildService(EarlyDecodeCoordinator coordinator) => new(coordinator, new EarlyDecodeServiceDependencies(
            CurrentDialFrequency:  () => CurrentDial,
            FallbackDialFrequency: () => 0.0,
            DeriveBand:            _ => "20m",
            DecodeEarly:           async (pcm, cs, band, _) =>
            {
                lock (Events) { EarlyDecodeCalls++; Events.Add($"decode-early:{cs:mm:ss}"); }
                return await EarlyDecode(cs);
            },
            ApplyNoiseSuppression: r => Suppress(r),
            PublishEarlyToPanel:   rows => { OnEarlyPublish?.Invoke(); lock (Events) { EarlyFrames.Add(rows); Events.Add($"early-frame:{rows.Count}"); } return Task.CompletedTask; },
            Logger:                Log));

        public static async IAsyncEnumerable<(float[] Pcm, DateTime CycleStart, double? DialFrequency)> Windows(params DateTime[] cycles)
        {
            foreach (var c in cycles) yield return (new float[180_000], c, Dial);
            await Task.CompletedTask;
        }

        public List<DecodeBatch> Drain(Channel<DecodeBatch> ch)
        {
            var l = new List<DecodeBatch>();
            while (ch.Reader.TryRead(out var b)) l.Add(b);
            return l;
        }
    }

    // ── 5.4 flag OFF: the same calls in the same order as the pre-change pump ─────────────────────────────────

    [Fact(DisplayName = "FR-083: 5.4a flag OFF (A1): with the early machinery wired and no early window, the pump makes the same calls in the same order as the pump without it")]
    public async Task FlagOff_WiredButIdle_IsCallForCallIdenticalToUnwired()
    {
        static async Task<Rig> RunAsync(bool wired)
        {
            var rig = new Rig { FinalDecode = _ => Task.FromResult<IReadOnlyList<DecodeResult>>([R("CQ Q1ABC JO33"), R("Q1AAA Q1BBB -01", 900)]) };
            await rig.BuildPump(wired ? rig.NewCoordinator() : null).RunAsync(Rig.Windows(Cycle1, Cycle2), CancellationToken.None);
            return rig;
        }

        var unwired = await RunAsync(wired: false);
        var wired   = await RunAsync(wired: true);

        wired.Events.Should().Equal(unwired.Events, "same calls, same order");
        wired.Frames.Should().BeEmpty("no early rows: the ordinary PublishToPanel call is made, never the resolves frame");
        wired.Panel.Select(p => p.Count).Should().Equal(unwired.Panel.Select(p => p.Count));
        wired.AllTxt.Select(a => (a.Stamp, a.Results.Count)).Should().Equal(unwired.AllTxt.Select(a => (a.Stamp, a.Results.Count)));
        wired.Archive.Should().Equal(unwired.Archive);
        wired.Drain(wired.Answerer).Select(b => b.Results.Count).Should().Equal(unwired.Drain(unwired.Answerer).Select(b => b.Results.Count));
        wired.Log.Lines.Should().NotContain(l => l.StartsWith("Early decode:"), "no early window, no R7 line");
    }

    // ── 5.2 / 5.4 the early service ───────────────────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-083: 5.4b the early service skips, counted, when the decode gate is held, and never queues")]
    public async Task EarlyService_GateHeld_SkipsAndDoesNotDecode()
    {
        var rig = new Rig();
        var coordinator = rig.NewCoordinator();
        await coordinator.Gate.WaitAsync();                       // an ordinary decode is running
        try
        {
            await rig.BuildService(coordinator).HandleAsync(new float[180_000], Cycle1, Dial, CancellationToken.None);
        }
        finally { coordinator.Gate.Release(); }

        rig.EarlyDecodeCalls.Should().Be(0);
        rig.EarlyFrames.Should().BeEmpty();
        coordinator.Gate.CurrentCount.Should().Be(1, "the service released nothing it did not take");

        coordinator.NoteFinalDecodeStarted(Cycle1, 0);
        rig.Log.Lines.Should().ContainSingle(l => l.StartsWith("Early decode:") && l.Contains("skipped=1") && l.Contains("decoderBusy"));
    }

    [Fact(DisplayName = "FR-083: 5.4c the early service skips when the dial frequency changed since the window opened")]
    public async Task EarlyService_DialFrequencyChanged_Skips()
    {
        var rig = new Rig { CurrentDial = 7.074 };                // the window opened at 14.074
        var coordinator = rig.NewCoordinator();

        await rig.BuildService(coordinator).HandleAsync(new float[180_000], Cycle1, Dial, CancellationToken.None);

        rig.EarlyDecodeCalls.Should().Be(0);
        rig.EarlyFrames.Should().BeEmpty();
        coordinator.NoteFinalDecodeStarted(Cycle1, 0);
        rig.Log.Lines.Should().ContainSingle(l => l.Contains("dialFrequencyChanged"));
    }

    [Fact(DisplayName = "FR-083: 5.4d the early service publishes the early rows to the panel only, through the same visibility filter, with fresh unique ids")]
    public async Task EarlyService_PublishesFilteredRows_ToThePanelOnly()
    {
        var rig = new Rig
        {
            EarlyDecode = _ => Task.FromResult<IReadOnlyList<DecodeResult>>([R("CQ Q1ABC JO33"), R("CQ Q1HID EN37", 2000), R("Q1AAA Q1BBB -01", 900)]),
            Suppress    = r => r.Where(x => !x.Message.Contains("Q1HID")).ToList(),
        };
        var coordinator = rig.NewCoordinator();
        var service = rig.BuildService(coordinator);

        await service.HandleAsync(new float[180_000], Cycle1, Dial, CancellationToken.None);
        await service.HandleAsync(new float[180_000], Cycle2, Dial, CancellationToken.None);

        rig.EarlyFrames.Should().HaveCount(2);
        rig.EarlyFrames[0].Select(r => r.Decode.Message).Should().Equal(["CQ Q1ABC JO33", "Q1AAA Q1BBB -01"], "the hidden row never flashes up early");
        rig.EarlyFrames.SelectMany(f => f).Select(r => r.EarlyId).Should().OnlyHaveUniqueItems();
        coordinator.Gate.CurrentCount.Should().Be(1, "the gate is released after the decode");

        // Panel only: nothing but the early frames exists; no ALL.TXT, archive, admission or consumer channel was touched.
        rig.AllTxt.Should().BeEmpty();
        rig.Archive.Should().BeEmpty();
        rig.Admitted.Should().BeEmpty();
        rig.Drain(rig.Answerer).Should().BeEmpty();
        rig.Drain(rig.Caller).Should().BeEmpty();
        rig.Drain(rig.External).Should().BeEmpty();
        rig.Panel.Should().BeEmpty("the ordinary panel call is for batch 1 only");
    }

    [Fact(DisplayName = "FR-083: 5.4e a faulting early decode is a counted skip, releases the gate, and never throws out of the service")]
    public async Task EarlyService_DecodeFaults_SkipsAndReleasesTheGate()
    {
        var rig = new Rig { EarlyDecode = _ => throw new InvalidOperationException("native fault") };
        var coordinator = rig.NewCoordinator();

        await rig.BuildService(coordinator).HandleAsync(new float[180_000], Cycle1, Dial, CancellationToken.None);

        coordinator.Gate.CurrentCount.Should().Be(1);
        coordinator.NoteFinalDecodeStarted(Cycle1, 0);
        rig.Log.Lines.Should().Contain(l => l.StartsWith("Early decode:") && l.Contains("skipped=1") && l.Contains("error"));
    }

    // ── 5.1 / 5.4 the decode gate and the final decode ────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-083: 5.4f the ordinary decode waits for a running early decode, and the cycle's one R7 line reports finalWaitMs")]
    public async Task FinalDecode_WaitsForARunningEarlyDecode_AndReportsFinalWait()
    {
        var rig = new Rig();
        var coordinator = rig.NewCoordinator();

        // The early decode starts and blocks inside the decode call, holding the gate.
        var earlyEntered = new TaskCompletionSource();
        var earlyRelease = new TaskCompletionSource();
        rig.EarlyDecode = async _ =>
        {
            earlyEntered.SetResult();
            await earlyRelease.Task;
            lock (rig.Events) rig.Events.Add("early-decode-returned");
            return [R("CQ Q1ABC JO33")];
        };
        var earlyTask = rig.BuildService(coordinator).HandleAsync(new float[180_000], Cycle1, Dial, CancellationToken.None);
        await earlyEntered.Task;

        // The pump starts the same cycle's final decode while the early decode still runs. It reaches the gate right
        // after DeriveBand: the early decode is released only then, so a pump with no gate would decode before it.
        var pumpAtGate = new TaskCompletionSource();
        rig.OnDeriveBand = () => pumpAtGate.TrySetResult();
        rig.FinalDecode  = _ => Task.FromResult<IReadOnlyList<DecodeResult>>([R("CQ Q1ABC JO33")]);
        var pumpTask = rig.BuildPump(coordinator).RunAsync(Rig.Windows(Cycle1), CancellationToken.None);
        await pumpAtGate.Task;
        earlyRelease.SetResult();
        await earlyTask;
        await pumpTask;

        var events = rig.Events.ToList();
        events.IndexOf("early-decode-returned").Should().BeLessThan(events.IndexOf($"decode-single:{Cycle1:mm:ss}"),
            "the ordinary decode never starts while an early decode holds the gate");
        coordinator.Gate.CurrentCount.Should().Be(1);

        // The R7 line: one per cycle, aggregates only, with finalWaitMs.
        rig.Log.Lines.Where(l => l.StartsWith("Early decode:")).Should().ContainSingle()
            .Which.Should().Contain("finalWaitMs=").And.Contain("skipped=0").And.Contain("n=1");
    }

    [Fact(DisplayName = "FR-083: 5.4f2 the early service holds the gate until the early batch is recorded, so a final decode waiting on the gate always finds it")]
    public async Task EarlyService_HoldsTheGateUntilTheBatchIsRecorded()
    {
        var rig = new Rig { EarlyDecode = _ => Task.FromResult<IReadOnlyList<DecodeResult>>([R("CQ Q1ABC JO33")]) };
        var coordinator = rig.NewCoordinator();
        int gateCountWhenPublished = -1;
        rig.OnEarlyPublish = () => gateCountWhenPublished = coordinator.Gate.CurrentCount;   // runs after RecordEarly

        await rig.BuildService(coordinator).HandleAsync(new float[180_000], Cycle1, Dial, CancellationToken.None);

        gateCountWhenPublished.Should().Be(0, "the gate is still held when the batch has been recorded and the panel frame leaves");
        coordinator.Gate.CurrentCount.Should().Be(1, "and it is released afterwards");

        // The recorded batch is what the final decode sees the moment it gets the gate.
        coordinator.NoteFinalDecodeStarted(Cycle1, 0);
        rig.Log.Lines.Should().ContainSingle(l => l.StartsWith("Early decode:") && l.Contains("n=1"));
    }

    // ── 5.2 / 6.2 batch 1 resolves the early rows in ONE frame ─────────────────────────────────────────────────

    [Fact(DisplayName = "FR-083: 5.4g with early rows for the cycle, batch 1 goes out as ONE frame carrying the resolves list; the ordinary panel call is not made")]
    public async Task Batch1_WithEarlyRows_IsOneFrameWithResolves()
    {
        var rig = new Rig
        {
            EarlyDecode = _ => Task.FromResult<IReadOnlyList<DecodeResult>>([R("CQ Q1ABC JO33", 1500), R("Q1AAA Q1BBB -01", 900)]),
            FinalDecode = _ => Task.FromResult<IReadOnlyList<DecodeResult>>([R("CQ Q1NEW EN37", 2100), R("CQ Q1ABC JO33", 1504)]),
        };
        var coordinator = rig.NewCoordinator();
        await rig.BuildService(coordinator).HandleAsync(new float[180_000], Cycle1, Dial, CancellationToken.None);
        long idConfirmed   = rig.EarlyFrames[0][0].EarlyId;
        long idUnconfirmed = rig.EarlyFrames[0][1].EarlyId;

        await rig.BuildPump(coordinator).RunAsync(Rig.Windows(Cycle1), CancellationToken.None);

        rig.Panel.Should().BeEmpty("with early rows the plain decode frame is replaced by the one that carries resolves");
        var frame = rig.Frames.Should().ContainSingle().Subject;
        frame.Results.Select(r => r.Message).Should().Equal("CQ Q1NEW EN37", "CQ Q1ABC JO33");
        frame.Resolves.Should().Equal(
            new EarlyResolution(idConfirmed, EarlyResolution.Confirmed, 1),
            new EarlyResolution(idUnconfirmed, EarlyResolution.Unconfirmed));

        // The early rows reached nothing else: ALL.TXT, archive, admission and the consumer channels hold batch 1 only.
        rig.AllTxt.Should().ContainSingle().Which.Results.Select(r => r.Message).Should().Equal("CQ Q1NEW EN37", "CQ Q1ABC JO33");
        rig.Archive.Should().Equal([(Cycle1, 2)]);
        rig.Admitted.Should().Equal("CQ Q1NEW EN37", "CQ Q1ABC JO33");
        rig.Drain(rig.Answerer).Should().ContainSingle().Which.Results.Should().HaveCount(2);
        rig.Drain(rig.Caller).Should().ContainSingle();
        rig.Drain(rig.External).Should().ContainSingle();
    }

    [Fact(DisplayName = "FR-083: 5.4h an empty batch 1 still resolves the cycle: every early row becomes unconfirmed")]
    public async Task EmptyBatch1_ResolvesEveryEarlyRowUnconfirmed()
    {
        var rig = new Rig
        {
            EarlyDecode = _ => Task.FromResult<IReadOnlyList<DecodeResult>>([R("CQ Q1ABC JO33")]),
            FinalDecode = _ => Task.FromResult<IReadOnlyList<DecodeResult>>([]),
        };
        var coordinator = rig.NewCoordinator();
        await rig.BuildService(coordinator).HandleAsync(new float[180_000], Cycle1, Dial, CancellationToken.None);

        await rig.BuildPump(coordinator).RunAsync(Rig.Windows(Cycle1), CancellationToken.None);

        var frame = rig.Frames.Should().ContainSingle().Subject;
        frame.Results.Should().BeEmpty();
        frame.Resolves.Should().ContainSingle().Which.Outcome.Should().Be(EarlyResolution.Unconfirmed);
    }

    [Fact(DisplayName = "FR-083: 5.4i a discarded cycle (dial frequency changed) resolves its early rows as unconfirmed, so none stays marked early forever")]
    public async Task DiscardedCycle_ResolvesEarlyRowsUnconfirmed()
    {
        var rig = new Rig { EarlyDecode = _ => Task.FromResult<IReadOnlyList<DecodeResult>>([R("CQ Q1ABC JO33")]) };
        var coordinator = rig.NewCoordinator();
        await rig.BuildService(coordinator).HandleAsync(new float[180_000], Cycle1, Dial, CancellationToken.None);

        rig.CurrentDial = 7.074;                                  // the band changed before the window closed
        await rig.BuildPump(coordinator).RunAsync(Rig.Windows(Cycle1), CancellationToken.None);

        rig.FinalDecodeCalls.Should().Be(0, "the cycle is discarded");
        var frame = rig.Frames.Should().ContainSingle().Subject;
        frame.Results.Should().BeEmpty();
        frame.Resolves.Should().ContainSingle().Which.Outcome.Should().Be(EarlyResolution.Unconfirmed);
    }

    [Fact(DisplayName = "FR-083: 5.4j a decode error resolves the cycle's early rows as unconfirmed")]
    public async Task DecodeError_ResolvesEarlyRowsUnconfirmed()
    {
        var rig = new Rig
        {
            EarlyDecode = _ => Task.FromResult<IReadOnlyList<DecodeResult>>([R("CQ Q1ABC JO33")]),
            FinalDecode = _ => throw new InvalidOperationException("final decode failed"),
        };
        var coordinator = rig.NewCoordinator();
        await rig.BuildService(coordinator).HandleAsync(new float[180_000], Cycle1, Dial, CancellationToken.None);

        await rig.BuildPump(coordinator).RunAsync(Rig.Windows(Cycle1), CancellationToken.None);

        rig.Frames.Should().ContainSingle().Which.Resolves.Should().ContainSingle().Which.Outcome.Should().Be(EarlyResolution.Unconfirmed);
        coordinator.Gate.CurrentCount.Should().Be(1, "the gate is released on the error path too");
    }

    [Fact(DisplayName = "FR-083: 5.4k an early batch whose final batch never came is resolved unconfirmed when the next cycle's early batch arrives")]
    public async Task StaleEarlyBatch_IsResolvedWhenTheNextCycleArrives()
    {
        var rig = new Rig { EarlyDecode = _ => Task.FromResult<IReadOnlyList<DecodeResult>>([R("CQ Q1ABC JO33")]) };
        var coordinator = rig.NewCoordinator();
        var service = rig.BuildService(coordinator);

        await service.HandleAsync(new float[180_000], Cycle1, Dial, CancellationToken.None);
        await service.HandleAsync(new float[180_000], Cycle2, Dial, CancellationToken.None);

        var frame = rig.Frames.Should().ContainSingle("cycle 1's rows were left behind and are resolved now").Subject;
        frame.Results.Should().BeEmpty();
        frame.Resolves.Should().ContainSingle().Which.Outcome.Should().Be(EarlyResolution.Unconfirmed);
    }

    // ── Stress: contention for many cycles, forced cancellation ───────────────────────────────────────────────

    [Fact(DisplayName = "FR-083: 5.4l stress: early and ordinary decodes contending for 300 cycles are never concurrent, the gate always comes back, and a forced cancellation leaves it free")]
    public async Task Stress_EarlyAndOrdinaryDecodes_NeverOverlap()
    {
        int running = 0, maxRunning = 0, overlaps = 0;
        async Task<IReadOnlyList<DecodeResult>> Decode(DateTime cs)
        {
            int now = Interlocked.Increment(ref running);
            if (now > 1) Interlocked.Increment(ref overlaps);
            int seen;
            while ((seen = Volatile.Read(ref maxRunning)) < now && Interlocked.CompareExchange(ref maxRunning, now, seen) != seen) { }
            await Task.Yield();                                    // let the other side try to run
            await Task.Yield();
            Interlocked.Decrement(ref running);
            return [R("CQ Q1ABC JO33", 1500 + cs.Second)];
        }

        var rig = new Rig { EarlyDecode = Decode, FinalDecode = Decode };
        var coordinator = rig.NewCoordinator();
        var service = rig.BuildService(coordinator);
        var pump    = rig.BuildPump(coordinator);

        var cycles = Enumerable.Range(0, 300).Select(i => Cycle1.AddSeconds(15 * i)).ToArray();

        // The early windows and the ordinary windows are two independent streams racing each other.
        using var cts = new CancellationTokenSource();
        var earlyTask = service.RunAsync(Rig.Windows(cycles), cts.Token);
        var pumpTask  = pump.RunAsync(Rig.Windows(cycles), cts.Token);
        await Task.WhenAll(earlyTask, pumpTask);

        overlaps.Should().Be(0, "the decode gate makes an early decode and an ordinary decode mutually exclusive");
        maxRunning.Should().Be(1);
        rig.FinalDecodeCalls.Should().Be(300, "the ordinary decode waits, it is never skipped");
        (rig.EarlyDecodeCalls).Should().BeLessThanOrEqualTo(300);
        coordinator.Gate.CurrentCount.Should().Be(1, "every acquire was matched by a release");

        // Forced cancellation: cancel while both loops still have work, and require both to stop and the gate to be free.
        var rig2 = new Rig { EarlyDecode = Decode, FinalDecode = Decode };
        var coordinator2 = rig2.NewCoordinator();
        using var cts2 = new CancellationTokenSource();
        rig2.OnDeriveBand = () => { if (rig2.FinalDecodeCalls >= 20) cts2.Cancel(); };
        var t1 = rig2.BuildService(coordinator2).RunAsync(Rig.Windows(cycles), cts2.Token);
        var t2 = rig2.BuildPump(coordinator2).RunAsync(Rig.Windows(cycles), cts2.Token);
        await Task.WhenAll(t1, t2);
        coordinator2.Gate.CurrentCount.Should().Be(1, "a cancelled run leaves the gate free");
    }
}
