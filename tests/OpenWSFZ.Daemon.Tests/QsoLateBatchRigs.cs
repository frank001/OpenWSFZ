using System.Reflection;
using System.Text.RegularExpressions;
using Microsoft.Extensions.Logging;
using NSubstitute;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using OpenWSFZ.TestSupport;
using OpenWSFZ.Web;

namespace OpenWSFZ.Daemon.Tests;

// Shared rigs for the late-batches-in-qso tests and the batch-1-only integration replay. NFR-021: Q-prefix callsigns only.
// This file deliberately uses nothing that exists only after the change (no BatchNumber, no LateBatch), so the same file
// builds on origin/main 0c7124db for the replay comparison (AC1 / R4).

/// <summary>Controllable clock: the services read it for the window-boundary clamp and the 2.36 s guard.</summary>
internal sealed class QsoRigClock(DateTimeOffset initial) : TimeProvider
{
    public DateTimeOffset Now { get; set; } = initial;
    public override DateTimeOffset GetUtcNow() => Now;
}

/// <summary>Cycle arithmetic for the scripts: cycle n starts at T0 + 15 s x n; even n is the A phase (:00/:30).</summary>
internal static class Cy
{
    public static readonly DateTimeOffset T0 = new(2026, 1, 1, 0, 0, 0, TimeSpan.Zero);
    public static DateTimeOffset At(int n) => T0.AddSeconds(15 * n);

    /// <summary>The time a service processes the batch 1 of cycle n in normal operation: the slot after it, +1 s.</summary>
    public static DateTimeOffset Batch1Time(int n) => At(n + 1).AddSeconds(1);
}

/// <summary>Records every formatted log line and, for each "TX" line, what was sent and the clock at that moment.</summary>
internal sealed class RigLog<T>(Func<DateTimeOffset> clock) : ILogger<T>
{
    private static readonly Regex TxLine = new("TX → \"(?<m>[^\"]*)\" at ", RegexOptions.Compiled);
    private readonly object _gate = new();
    private readonly List<string> _lines = [];
    private readonly List<(DateTimeOffset At, string Message)> _tx = [];

    public IReadOnlyList<string> Lines { get { lock (_gate) return _lines.ToList(); } }
    public IReadOnlyList<(DateTimeOffset At, string Message)> Tx { get { lock (_gate) return _tx.ToList(); } }

    public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
    public bool IsEnabled(LogLevel logLevel) => true;
    public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception,
        Func<TState, Exception?, string> formatter)
    {
        var line = formatter(state, exception);
        lock (_gate)
        {
            _lines.Add(line);
            var m = TxLine.Match(line);
            if (m.Success) _tx.Add((clock(), m.Groups["m"].Value));
        }
    }
}

/// <summary>Reads private fields of a service under test.</summary>
internal static class Peek
{
    public static T Field<T>(object service, string name)
    {
        var f = service.GetType().GetField(name, BindingFlags.NonPublic | BindingFlags.Instance)
                ?? throw new MissingFieldException(service.GetType().Name, name);
        return (T)f.GetValue(service)!;
    }
}

internal abstract class QsoRigBase : IAsyncDisposable
{
    public const string Ours = "Q1OFZ", Grid = "JO33", Partner = "Q1TST", PartnerGrid = "JO22";

    public QsoRigClock Clock { get; } = new(Cy.T0);
    public ObservedDecodeChannel Channel { get; } = ObservedDecodeChannel.Create();
    public IPttController Ptt { get; } = Substitute.For<IPttController>();
    public List<int> AudioLengths { get; } = [];
    /// <summary>A substitute event bus: its received calls show what the service BROADCAST (AC6: Idle stays Idle while an answer is held).</summary>
    public ITxEventBus Bus { get; } = Substitute.For<ITxEventBus>();
    protected CancellationTokenSource Stop { get; } = new();

    protected QsoRigBase()
    {
        Ptt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        Ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        Ptt.When(p => p.LoadAudio(Arg.Any<float[]>())).Do(ci =>
        {
            lock (AudioLengths) AudioLengths.Add(ci.Arg<float[]>().Length);
        });
    }

    protected static IConfigStore Store(TxConfig tx)
    {
        var store = Substitute.For<IConfigStore>();
        store.Current.Returns(new AppConfig() with { Tx = tx });
        store.SaveAsync(Arg.Any<AppConfig>(), Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        return store;
    }

    public static DecodeResult Make(string message, int snr = -5, int freqHz = 897)
        => new(Time: "12:00:00", Snr: snr, Dt: 0.1, FreqHz: freqHz, Message: message);

    /// <summary>Sets the clock to the time the service will process the batch at, queues it, waits until it is PROCESSED.</summary>
    public async Task FeedAsync(DateTimeOffset processedAt, DecodeBatch batch)
    {
        Clock.Now = processedAt;
        Channel.Writer.TryWrite(batch);
        await Poll.UntilAsync(() => Channel.IsProcessedThroughLastDequeue,
            timeout: TimeSpan.FromSeconds(5),
            timeoutMessage: () => "the service never finished processing the batch it dequeued");
    }

    /// <summary>A batch 1 of cycle <paramref name="n"/>, processed at its normal time (the slot after it, +1 s).</summary>
    public Task Batch1Async(int n, params DecodeResult[] results)
        => FeedAsync(Cy.Batch1Time(n), new DecodeBatch(Cy.At(n), results));

    public abstract IReadOnlyList<(DateTimeOffset At, string Message)> Tx { get; }
    public abstract IReadOnlyList<string> LogLines { get; }
    public IReadOnlyList<string> TxMessages => Tx.Select(t => t.Message).ToList();

    public int RetryCount => Peek.Field<int>(Service, "_retryCount");
    public bool SkipNextRetry => Peek.Field<bool>(Service, "_skipNextRetry");
    public CancellationTokenSource TxCts => Peek.Field<CancellationTokenSource>(Service, "_txCts");
    protected abstract object Service { get; }

    /// <summary>The AC10 lines ("late batch N token") in order.</summary>
    public IReadOnlyList<string> LateLines
        => LogLines.Where(l => l.Contains("late batch ")).ToList();

    public abstract ValueTask DisposeAsync();
}

internal sealed class AnswererRig : QsoRigBase
{
    public QsoAnswererService Sut { get; }
    public RigLog<QsoAnswererService> Log { get; }
    protected override object Service => Sut;
    public override IReadOnlyList<(DateTimeOffset At, string Message)> Tx => Log.Tx;
    public override IReadOnlyList<string> LogLines => Log.Lines;

    private AnswererRig(bool autoAnswer, int retryCount)
    {
        Log = new RigLog<QsoAnswererService>(() => Clock.Now);
        var store = Store(new TxConfig
        {
            AutoAnswer = autoAnswer, Callsign = Ours, Grid = Grid, RetryCount = retryCount, WatchdogMinutes = 4,
        });
        Sut = new QsoAnswererService(Channel.Reader, store, Ptt, Bus,
            Substitute.For<IAdifLogWriter>(), new AudioOffsetEventBus(), Log,
            watchdogDurationOverride: TimeSpan.FromMinutes(4), timeProvider: Clock);
    }

    public static async Task<AnswererRig> CreateAsync(bool autoAnswer = true, int retryCount = 2)
    {
        var rig = new AnswererRig(autoAnswer, retryCount);
        await rig.Sut.StartAsync(rig.Stop.Token);
        return rig;
    }

    /// <summary>Idle -> answers the partner's CQ (batch 1 of cycle 0) -> WaitReport; then the batch 1 of our own slot (cycle 1) consumes the skip guard.</summary>
    public async Task ReachWaitReportAsync()
    {
        await Batch1Async(0, Make($"CQ {Partner} {PartnerGrid}"));
        await Poll.WaitForEqualAsync(() => Sut.State, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));
        await Batch1Async(1);   // our own TX slot: nothing heard; consumes the first-empty-cycle guard
    }

    public override async ValueTask DisposeAsync()
    {
        await Stop.CancelAsync();
        await Sut.StopAsync(CancellationToken.None);
        await Ptt.DisposeAsync();
        Stop.Dispose();
    }
}

internal sealed class CallerRig : QsoRigBase
{
    public QsoCallerService Sut { get; }
    public RigLog<QsoCallerService> Log { get; }
    protected override object Service => Sut;
    public override IReadOnlyList<(DateTimeOffset At, string Message)> Tx => Log.Tx;
    public override IReadOnlyList<string> LogLines => Log.Lines;

    private CallerRig(int retryCount)
    {
        Log = new RigLog<QsoCallerService>(() => Clock.Now);
        var store = Store(new TxConfig
        {
            AutoAnswer = true, Callsign = Ours, Grid = Grid, RetryCount = retryCount, WatchdogMinutes = 4,
            CallerPartnerSelect = CallerPartnerSelectMode.First,
        });
        Sut = new QsoCallerService(Channel.Reader, store, Ptt, Bus,
            Substitute.For<IAdifLogWriter>(), new AudioOffsetEventBus(), Log,
            watchdogDurationOverride: TimeSpan.FromMinutes(4), timeProvider: Clock);
    }

    public static async Task<CallerRig> CreateAsync(int retryCount = 2)
    {
        var rig = new CallerRig(retryCount);
        await rig.Sut.StartAsync(rig.Stop.Token);
        return rig;
    }

    /// <summary>Idle -> sends CQ (any batch 1 starts it) -> WaitAnswer; then the batch 1 of our own slot (cycle 1) consumes the skip guard.</summary>
    public async Task ReachWaitAnswerAsync()
    {
        await Batch1Async(0);
        await Poll.WaitForEqualAsync(() => Sut.State, QsoState.WaitReport /* the caller's WaitAnswer */, timeout: TimeSpan.FromSeconds(3));
        await Batch1Async(1);
    }

    public override async ValueTask DisposeAsync()
    {
        await Stop.CancelAsync();
        await Sut.StopAsync(CancellationToken.None);
        await Ptt.DisposeAsync();
        Stop.Dispose();
    }
}
