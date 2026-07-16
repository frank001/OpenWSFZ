using System.Threading.Channels;
using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using NSubstitute;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using OpenWSFZ.Ft8;
using OpenWSFZ.Web;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="QsoCallerService"/> (tasks 5.1–5.14).
///
/// NFR-021: all callsigns use ITU-unallocated Q-prefix (Q1OFZ = ours, Q1TST = partner).
/// </summary>
[Trait("Category", "Unit")]
public sealed class QsoCallerServiceTests
{
    private const string OurCallsign  = "Q1OFZ";
    private const string OurGrid      = "JO33";
    private const string PartnerCall  = "Q1TST";
    private const string PartnerGrid  = "JO22";
    private const int    AudioFreqHz  = 1500;

    // ── SUT builder ───────────────────────────────────────────────────────────

    private static (QsoCallerService sut, ITxEventBus eventBus, IAdifLogWriter adifLog,
                    IPttController ptt, Channel<DecodeBatch> channel, CancellationTokenSource stopCts)
        BuildIsolatedSut(TxConfig txConfig, TimeSpan? watchdogDuration = null,
                         IAdifLogWriter? adifLog = null, IApConstraintSink? decoder = null,
                         ICatState? catState = null, AppConfig? appConfig = null,
                         IDecodeFilterStore? decodeFilterStore = null,
                         TimeProvider? timeProvider = null)
    {
        var ptt = Substitute.For<IPttController>();
        ptt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var store = Substitute.For<IConfigStore>();
        store.Current.Returns((appConfig ?? new AppConfig()) with { Tx = txConfig });
        store.SaveAsync(Arg.Any<AppConfig>(), Arg.Any<CancellationToken>())
             .Returns(Task.CompletedTask);

        var eventBus    = Substitute.For<ITxEventBus>();
        var resolvedLog = adifLog ?? new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);
        var channel     = Channel.CreateUnbounded<DecodeBatch>();
        var stopCts     = new CancellationTokenSource();

        var sut = watchdogDuration.HasValue
            ? new QsoCallerService(
                channel.Reader, store, ptt, eventBus,
                resolvedLog, new AudioOffsetEventBus(),
                NullLogger<QsoCallerService>.Instance,
                watchdogDurationOverride: watchdogDuration.Value,
                decoder: decoder,
                catState: catState,
                decodeFilterStore: decodeFilterStore,
                timeProvider: timeProvider)
            : new QsoCallerService(
                channel.Reader, store, ptt, eventBus,
                resolvedLog, new AudioOffsetEventBus(),
                NullLogger<QsoCallerService>.Instance,
                decoder: decoder,
                catState: catState,
                decodeFilterStore: decodeFilterStore);

        return (sut, eventBus, resolvedLog, ptt, channel, stopCts);
    }

    /// <summary>
    /// Controllable <see cref="TimeProvider"/> so <c>TransmitAsync</c>'s window-boundary
    /// truncation (D-CALLER-021) can be exercised deterministically, mirroring
    /// <c>QsoAnswererServiceTests.FakeTimeProvider</c>.
    /// </summary>
    private sealed class FakeTimeProvider(DateTimeOffset initial) : TimeProvider
    {
        public DateTimeOffset UtcNow { get; set; } = initial;
        public override DateTimeOffset GetUtcNow() => UtcNow;
    }

    /// <summary>Simple mutable <see cref="IDecodeFilterStore"/> test double — no broadcast, just state.</summary>
    private sealed class MutableDecodeFilterStore : IDecodeFilterStore
    {
        public DecodeFilterState Current { get; private set; } = DecodeFilterState.Unfiltered;
        public void Set(DecodeFilterState state) => Current = state;
    }

    private static DecodeResult MakeResponse(string callsign, string grid, WorkedBeforeState contactState)
        => new(
            Time:         "12:00:00",
            Snr:          -5,
            Dt:           0.1,
            FreqHz:       AudioFreqHz,
            Message:      $"{OurCallsign} {callsign} {grid}",
            WorkedBefore: WorkedBeforeInfo.None with { Contact = contactState });

    /// <summary>D-013: minimal fixed-frequency <see cref="ICatState"/> test double, mirroring
    /// the pattern established in <c>DecodeFrequencyGuardTests.StubCatState</c>.</summary>
    private sealed class StubCatState : ICatState
    {
        private readonly double _freq;
        public StubCatState(double freqMHz) => _freq = freqMHz;

        public double?              DialFrequencyMHz => _freq;
        public CatConnectionStatus  Status            => CatConnectionStatus.Connected;
    }

    // ── Wait helpers ──────────────────────────────────────────────────────────

    /// <summary>
    /// Polls <see cref="IQsoController.State"/> on a <see cref="QsoCallerService"/>
    /// (mapped via design.md D8) until it reaches <paramref name="expected"/> or times out.
    /// </summary>
    private static async Task WaitForStateAsync(
        QsoCallerService svc, QsoState expected, TimeSpan? timeout = null)
    {
        var deadline = DateTime.UtcNow + (timeout ?? TimeSpan.FromSeconds(5));
        while (DateTime.UtcNow < deadline)
        {
            if (svc.State == expected) return;
            await Task.Delay(10);
        }
        svc.State.Should().Be(expected, $"state should reach {expected} within timeout");
    }

    /// <summary>
    /// Polls <see cref="QsoCallerService.Keying"/> until it reaches <paramref name="expected"/>
    /// or times out. <c>State</c> and <c>Keying</c> are two independent fields set by two
    /// separate lines of production code (<c>SetStateAndNotify</c> runs before
    /// <c>TransmitAsync</c>'s <c>_keying = true</c>) with no atomicity between them — a single
    /// immediate check right after <see cref="WaitForStateAsync"/> returns is a genuine race
    /// (observed failing on CI's Linux runner, not locally) rather than a fixed-order guarantee.
    /// Poll here the same way <see cref="WaitForStateAsync"/> already polls <c>State</c>.
    /// </summary>
    private static async Task WaitForKeyingAsync(
        QsoCallerService svc, bool expected, TimeSpan? timeout = null)
    {
        var deadline = DateTime.UtcNow + (timeout ?? TimeSpan.FromSeconds(5));
        while (DateTime.UtcNow < deadline)
        {
            if (svc.Keying == expected) return;
            await Task.Delay(10);
        }
        svc.Keying.Should().Be(expected, $"keying should reach {expected} within timeout");
    }

    private static DecodeResult Make(string msg, int freqHz = AudioFreqHz)
        => new(Time: "12:00:00", Snr: -5, Dt: 0.1, FreqHz: freqHz, Message: msg);

    private static void Send(Channel<DecodeBatch> ch, params DecodeResult[] results)
        => ch.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow, results));

    private static void SendAt(Channel<DecodeBatch> ch, DateTimeOffset cycleStart, params DecodeResult[] results)
        => ch.Writer.TryWrite(new DecodeBatch(cycleStart, results));

    // ── 5.13: Role property ───────────────────────────────────────────────────

    [Fact(DisplayName = "5.13: QsoCallerService.Role == QsoRole.Caller")]
    public void Role_IsQsoRoleCaller()
    {
        var tx = new TxConfig { AutoAnswer = false, Callsign = OurCallsign, Grid = OurGrid };
        var (sut, _, _, _, _, _) = BuildIsolatedSut(tx);
        sut.Role.Should().Be(QsoRole.Caller);
    }

    // ── 5.2: TxCq on first batch ─────────────────────────────────────────────

    [Fact(DisplayName = "5.2: Armed service transmits CQ on first batch and reaches WaitAnswer")]
    public async Task TxCq_ArmedService_TransmitsCqAndAdvancesToWaitAnswer()
    {
        var tx = new TxConfig
        {
            AutoAnswer      = true,
            Callsign        = OurCallsign,
            Grid            = OurGrid,
            RetryCount      = 3,
            WatchdogMinutes = 4,
        };
        var (sut, _, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
        await sut.StartAsync(stopCts.Token);

        // Send any batch — triggers CQ transmission from Idle.
        Send(channel, Make("CQ Q2NOISE JO00"));

        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        // Should have KeyDownAsync'd once (the CQ TX).
        await ptt.Received(1).KeyDownAsync(Arg.Any<CancellationToken>());
        sut.State.Should().Be(QsoState.WaitReport); // WaitAnswer maps to WaitReport

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── Keying (dev-task 2026-07-10-tx-btn-live-verify-and-settings-tab-wrap.md item A) ──

    [Fact(DisplayName = "Keying: false by construction before any transmission (armed-but-idle default)")]
    public void Keying_FalseByDefault_BeforeAnyTransmission()
    {
        var tx = new TxConfig { AutoAnswer = false, Callsign = OurCallsign, Grid = OurGrid };
        var (sut, _, _, _, _, _) = BuildIsolatedSut(tx);

        sut.Keying.Should().BeFalse();
    }

    [Fact(DisplayName = "Keying: TransmitAsync brackets KeyDownAsync with keying=true then keying=false")]
    public async Task TransmitAsync_BracketsKeyDownAsync_WithKeyingTrueThenFalse()
    {
        var tx = new TxConfig
        {
            AutoAnswer      = true,
            Callsign        = OurCallsign,
            Grid            = OurGrid,
            RetryCount      = 3,
            WatchdogMinutes = 4,
        };
        var (sut, eventBus, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
        await sut.StartAsync(stopCts.Token);

        sut.Keying.Should().BeFalse(); // armed-but-idle default before the CQ batch below

        // Send any batch — triggers CQ transmission from Idle.
        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        // Keying must have flipped true immediately before KeyDownAsync and false immediately
        // after, bracketing the same TxCq broadcast the pre-existing state machine already
        // makes — this is an additional, independent signal, not a replacement for it.
        // Partner is null throughout (no responder selected yet at CQ time).
        Received.InOrder(() =>
        {
            eventBus.Publish("TxCq",       "caller", Arg.Any<string?>(), true, Arg.Any<string?>(), false);
            eventBus.Publish("TxCq",       "caller", Arg.Any<string?>(), true, Arg.Any<string?>(), true);
            eventBus.Publish("TxCq",       "caller", Arg.Any<string?>(), true, Arg.Any<string?>(), false);
            eventBus.Publish("WaitAnswer", "caller", Arg.Any<string?>(), true, Arg.Any<string?>(), false);
        });

        // By the time WaitAnswer is reached, KeyDownAsync has returned — Keying is back to false.
        sut.Keying.Should().BeFalse();

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── dev-task 2026-07-12-cat-tx-ptt-missing-keyup-after-transmit.md ─────────

    [Fact(DisplayName = "dev-task 2026-07-12: normal transmission calls KeyDownAsync immediately followed by KeyUpAsync, with no intervening state transition")]
    public async Task TransmitAsync_NormalCompletion_KeyUpImmediatelyFollowsKeyDown_NoInterveningStateTransition()
    {
        // Regression test: before this fix, TransmitAsync's normal-completion path never
        // called KeyUpAsync at all — every real TX cycle relied entirely on PttWatchdog's
        // 20 s failsafe to ever release PTT, which broke FT8 slot timing on every single
        // transmission (see dev-tasks/2026-07-12-cat-tx-ptt-missing-keyup-after-transmit.md).
        var tx = new TxConfig
        {
            AutoAnswer      = true,
            Callsign        = OurCallsign,
            Grid            = OurGrid,
            RetryCount      = 3,
            WatchdogMinutes = 4,
        };
        var (sut, eventBus, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));

        // Manually record the interleaved call order across both substitutes. NSubstitute's
        // Received.InOrder does not reliably interleave calls made on two different substitute
        // instances (verified empirically — it throws CallSequenceNotFoundException even for a
        // provably valid subsequence), so this hand-rolled recorder is the robust way to assert
        // strict ordering across ptt and eventBus here.
        var callOrder = new List<string>();
        ptt.KeyDownAsync(Arg.Any<CancellationToken>())
           .Returns(_ => { callOrder.Add("KeyDownAsync"); return Task.CompletedTask; });
        ptt.KeyUpAsync(Arg.Any<CancellationToken>())
           .Returns(_ => { callOrder.Add("KeyUpAsync"); return Task.CompletedTask; });
        eventBus.When(e => e.Publish(
                    Arg.Any<string>(), Arg.Any<string>(), Arg.Any<string?>(),
                    Arg.Any<bool>(), Arg.Any<string?>(), Arg.Any<bool>()))
                .Do(ci => callOrder.Add($"Publish:{ci.ArgAt<string>(0)}:keying={ci.ArgAt<bool>(5)}"));

        await sut.StartAsync(stopCts.Token);

        // Send any batch — triggers CQ transmission from Idle.
        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5)); // WaitAnswer proxy

        // KeyDownAsync must be immediately followed by KeyUpAsync in the recorded call order —
        // nothing else intervenes — proving PTT is released inside TransmitAsync's own
        // normal-completion path, not merely "eventually, from the watchdog".
        var keyDownIndex = callOrder.IndexOf("KeyDownAsync");
        keyDownIndex.Should().BeGreaterThanOrEqualTo(0, "KeyDownAsync must have been called");
        callOrder.Skip(keyDownIndex).Take(2).Should().Equal(
            ["KeyDownAsync", "KeyUpAsync"],
            "KeyUpAsync must run immediately after KeyDownAsync, with no intervening state transition");

        // ...and the WaitAnswer state broadcast (TransmitAsync's caller resuming the state
        // machine) must come strictly after both.
        var waitAnswerIndex = callOrder.FindIndex(c => c.StartsWith("Publish:WaitAnswer", StringComparison.Ordinal));
        waitAnswerIndex.Should().BeGreaterThan(keyDownIndex + 1,
            "the WaitAnswer transition must not be published until after KeyUpAsync has run");

        // Exactly one KeyDownAsync, exactly one KeyUpAsync — no extra calls sneaking in from
        // an abort path, since none was taken.
        await ptt.Received(1).KeyDownAsync(Arg.Any<CancellationToken>());
        await ptt.Received(1).KeyUpAsync(Arg.Any<CancellationToken>());

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "dev-task 2026-07-12: KeyUpAsync still runs when the transmission is cancelled mid-KeyDownAsync")]
    public async Task TransmitAsync_CancelledMidKeyDown_StillCallsKeyUpAsync()
    {
        var tx = new TxConfig
        {
            AutoAnswer      = true,
            Callsign        = OurCallsign,
            Grid            = OurGrid,
            RetryCount      = 3,
            WatchdogMinutes = 4,
        };

        // KeyDownAsync never completes on its own — it only ends when its token is cancelled,
        // so this test proves the finally block (and its KeyUpAsync call) is reached via the
        // cancellation path, not the normal-return path.
        var ptt = Substitute.For<IPttController>();
        ptt.KeyDownAsync(Arg.Any<CancellationToken>())
           .Returns(callInfo => Task.Delay(Timeout.Infinite, callInfo.Arg<CancellationToken>()));
        ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var store = Substitute.For<IConfigStore>();
        store.Current.Returns(new AppConfig() with { Tx = tx });
        store.SaveAsync(Arg.Any<AppConfig>(), Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var eventBus = Substitute.For<ITxEventBus>();
        var channel  = Channel.CreateUnbounded<DecodeBatch>();
        var stopCts  = new CancellationTokenSource();

        var sut = new QsoCallerService(
            channel.Reader, store, ptt, eventBus,
            new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance), new AudioOffsetEventBus(),
            NullLogger<QsoCallerService>.Instance,
            watchdogDurationOverride: TimeSpan.FromSeconds(30));

        await sut.StartAsync(stopCts.Token);

        // Trigger CQ — the service enters TxCq (proxy: TxAnswer) and blocks inside KeyDownAsync.
        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.TxAnswer, timeout: TimeSpan.FromSeconds(5));
        await WaitForKeyingAsync(sut, expected: true, timeout: TimeSpan.FromSeconds(5));

        await ptt.DidNotReceive().KeyUpAsync(Arg.Any<CancellationToken>());

        // Cancel the token ExecuteAsync was started with — this is the token linked into
        // TransmitAsync's `linked` CTS alongside `_txCts`, so it interrupts the in-flight
        // KeyDownAsync directly (deliberately not going through AbortAsync, which has its own,
        // separate KeyUpAsync cleanup call — this test isolates TransmitAsync's own finally
        // block). Because stoppingToken.IsCancellationRequested is now true, ExecuteAsync's
        // `catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)`
        // branch simply breaks the loop rather than routing through SafeAbortToIdleAsync, so
        // any KeyUpAsync call observed here can only have come from TransmitAsync's finally.
        await stopCts.CancelAsync();

        // Poll rather than a fixed delay — the finally block runs asynchronously once the
        // cancellation propagates through Task.Delay.
        var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(5);
        while (DateTime.UtcNow < deadline && ptt.ReceivedCalls().Count(c => c.GetMethodInfo().Name == "KeyUpAsync") == 0)
        {
            await Task.Delay(10);
        }

        await ptt.Received(1).KeyUpAsync(Arg.Any<CancellationToken>());
        sut.Keying.Should().BeFalse("the finally block clears keying even on the cancellation path");

        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── 5.3: WaitAnswer First mode auto-engages ───────────────────────────────

    [Fact(DisplayName = "5.3: WaitAnswer First mode — batch with response auto-advances to TxReport")]
    public async Task WaitAnswer_FirstMode_AutoEngagesFirstResponse()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.First,
            RetryCount          = 3,
            WatchdogMinutes     = 4,
        };
        var (sut, _, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
        await sut.StartAsync(stopCts.Token);

        // Trigger CQ → WaitAnswer.
        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        // Feed a response: {ourCall} {partner} {partnerGrid}.
        Send(channel, Make($"{OurCallsign} {PartnerCall} {PartnerGrid}"));

        // Should advance through TxReport → WaitRr73.
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(5));

        sut.Partner.Should().Be(PartnerCall);

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── f-003-ap-assist-nonstandard-callsigns: H6 AP arming for nonstandard callsigns ────────

    [Fact(DisplayName = "f-003 4.3: AP constraints arm (not disabled) when the answering partner has a nonstandard callsign")]
    public async Task TxReport_NonstandardPartnerCallsign_ArmsApConstraintsInsteadOfDisabling()
    {
        const string nonstandardPartner = "PJ4/K1ABC"; // 9-char compound callsign (f-001/f-003 Gap B)

        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.First,
            RetryCount          = 3,
            WatchdogMinutes     = 4,
        };
        var decoder = Substitute.For<IApConstraintSink>();
        var (sut, _, _, ptt, channel, stopCts) =
            BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30), decoder: decoder);
        await sut.StartAsync(stopCts.Token);

        // Trigger CQ → WaitAnswer.
        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        // Feed a response from a nonstandard/compound callsign.
        Send(channel, Make($"{OurCallsign} {nonstandardPartner} {PartnerGrid}"));

        // Should advance through TxReport → WaitRr73, arming AP constraints along the way.
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(5));
        sut.Partner.Should().Be(nonstandardPartner);

        // NOTE: this calls Ft8CallsignPacker.Pack28 — the very function under test in
        // Ft8CallsignPackerTests.cs — so these are not "independently derived" expected
        // values. This integration test verifies a different concern: that
        // QsoCallerService arms AP with whatever Pack28 produces (rather than disabling
        // AP) when the partner's callsign is nonstandard, and passes the packer's own
        // output through unmodified. Pack28's byte-level correctness is covered
        // independently by Ft8CallsignPackerTests.cs.
        byte[] expectedMycallBits  = Ft8CallsignPacker.Pack28(OurCallsign);
        byte[] expectedHiscallBits = Ft8CallsignPacker.Pack28(nonstandardPartner);
        expectedHiscallBits.Should().NotBeEmpty(
            "the extended packer must be able to hash-encode a nonstandard callsign");

        decoder.Received(1).SetApConstraints(Arg.Is<Ft8ApConstraints>(c =>
            c != null &&
            c.MycallBits.SequenceEqual(expectedMycallBits) &&
            c.HiscallBits.SequenceEqual(expectedHiscallBits)));
        decoder.DidNotReceive().SetApConstraints(null);

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── 5.4: WaitAnswer None mode does NOT auto-advance ──────────────────────

    [Fact(DisplayName = "5.4: WaitAnswer None mode — response in batch does NOT auto-advance")]
    public async Task WaitAnswer_NoneMode_DoesNotAutoEngage()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.None,
            RetryCount          = 0,    // unlimited so no retry fires
            WatchdogMinutes     = 4,
        };
        var (sut, _, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
        await sut.StartAsync(stopCts.Token);

        // Trigger CQ → WaitAnswer.
        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        // Push 3 batches with matching response — A-01 guard + 2 real batches.
        // In None mode none of them should auto-advance.
        for (int i = 0; i < 3; i++)
        {
            Send(channel, Make($"{OurCallsign} {PartnerCall} {PartnerGrid}"));
            await Task.Delay(50);
        }

        await Task.Delay(200); // give time for processing

        // Still in WaitAnswer (WaitReport proxy).
        sut.State.Should().Be(QsoState.WaitReport);
        sut.Partner.Should().BeNull();

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── 5.5: SelectResponderAsync phase semantics ─────────────────────────────

    [Fact(DisplayName = "5.5: SelectResponderAsync — correct phase fires; wrong phase skips; correct follows")]
    public async Task SelectResponderAsync_PhaseSemanticsCorrect()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.None,
            RetryCount          = 0,
            WatchdogMinutes     = 4,
        };
        var (sut, _, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
        await sut.StartAsync(stopCts.Token);

        // Drive to WaitAnswer.
        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        // Drain any wakeup written during the CQ → WaitAnswer transition.
        while (sut._wakeupChannel.Reader.TryRead(out _)) { }

        // responseCycleStart at :15 → B-phase response → A-phase answer (:00 or :30)
        var bPhaseResponse = new DateTimeOffset(2026, 6, 25, 14, 29, 15, TimeSpan.Zero);
        await sut.SelectResponderAsync(PartnerCall, AudioFreqHz, bPhaseResponse, CancellationToken.None);
        // Drain the wakeup that SelectResponderAsync pushed so the service doesn't immediately fire
        // on the wakeup's phase (which depends on clock time and would be non-deterministic).
        // After drain the service must wait for an explicit decode batch from the test.
        while (sut._wakeupChannel.Reader.TryRead(out _)) { }
        await Task.Delay(50); // let the service settle back into Task.WhenAny

        // Feed a B-phase batch (wrong phase) — should NOT fire.
        // A batch whose next cycle is B-phase: CycleStart at :30 → next cycle = :45, which is B-phase.
        var wrongPhaseCycleStart = new DateTimeOffset(2026, 6, 25, 14, 29, 30, TimeSpan.Zero);
        SendAt(channel, wrongPhaseCycleStart, Make("CQ Q2NOISE JO00")); // arbitrary content
        await Task.Delay(150);

        // Should still be in WaitAnswer.
        sut.State.Should().Be(QsoState.WaitReport);

        // Feed an A-phase batch (correct phase: CycleStart :45 → next cycle :00 = A-phase).
        var correctPhaseCycleStart = new DateTimeOffset(2026, 6, 25, 14, 29, 45, TimeSpan.Zero);
        SendAt(channel, correctPhaseCycleStart, Make($"{OurCallsign} {PartnerCall} {PartnerGrid}"));

        // Should advance to WaitRr73 (TxReport then WaitRr73).
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(5));
        sut.Partner.Should().Be(PartnerCall);

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── 5.6: SelectResponderAsync 60s timeout ────────────────────────────────

    /// <summary>
    /// 5.6 — Pending-responder times out after 60 s.
    /// Uses <c>TestSetPendingResponder</c> to arm the fields directly (no wakeup pushed)
    /// so there is no race between the service reading the wakeup channel and the test.
    /// Verifies that when a batch arrives and the pending-responder timestamp is stale
    /// (> 60 s old), the service discards the responder and falls through to retry/skip
    /// rather than firing TxReport.
    /// </summary>
    [Fact(DisplayName = "5.6: SelectResponderAsync — 60s timeout discards pending responder")]
    public async Task SelectResponderAsync_Timeout_DiscardsStaleResponder()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.None,
            RetryCount          = 0,
            WatchdogMinutes     = 4,
        };
        var (sut, _, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
        await sut.StartAsync(stopCts.Token);

        // Drive to WaitAnswer.
        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        // Arm a pending responder with a timestamp 61 s in the past (simulate timeout).
        // Using TestSetPendingResponder so no wakeup batch is pushed — no race.
        var staleSetAt = DateTimeOffset.UtcNow - TimeSpan.FromSeconds(61);
        sut.TestSetPendingResponder(PartnerCall, AudioFreqHz, isAPhase: true, setAt: staleSetAt);

        // Feed a correct-phase batch.  Because the pending responder is expired, the service
        // must discard it and NOT fire TxReport.  Since RetryCount = 0 and _skipNextRetry is
        // true (A-01 guard set after the initial CQ), the batch falls through to the A-01 skip.
        var correctPhaseCycleStart = new DateTimeOffset(2026, 6, 25, 14, 29, 45, TimeSpan.Zero);
        SendAt(channel, correctPhaseCycleStart, Make($"{OurCallsign} {PartnerCall} {PartnerGrid}"));
        await Task.Delay(200);

        // Must remain in WaitAnswer (not have fired TxReport).
        sut.State.Should().Be(QsoState.WaitReport,
            "stale pending responder must be discarded, not used to trigger TxReport");
        ptt.ReceivedCalls()
            .Count(c => c.GetMethodInfo().Name == "KeyDownAsync")
            .Should().Be(1, "only the initial CQ TX must have fired; TxReport must not have fired");

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── 5.7: SelectResponderAsync abort clears pending responder ─────────────

    /// <summary>
    /// 5.7 — Abort while a pending responder is armed clears it.
    /// Uses <c>TestSetPendingResponder</c> to arm the fields without pushing a wakeup,
    /// then calls <c>AbortAsync</c> and verifies the service reaches Idle with partner = null.
    /// No decode batch is sent after abort — the service is stopped before anything
    /// could retrigger the CQ (AutoAnswer=true in the mock store's returned config).
    /// </summary>
    [Fact(DisplayName = "5.7: SelectResponderAsync — abort clears pending responder, no TX fires")]
    public async Task SelectResponderAsync_AbortClearsPendingResponder()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.None,
            RetryCount          = 0,
            WatchdogMinutes     = 4,
        };
        var (sut, _, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
        await sut.StartAsync(stopCts.Token);

        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        // Arm pending responder without wakeup so the service stays blocked in Task.WhenAny.
        sut.TestSetPendingResponder(PartnerCall, AudioFreqHz, isAPhase: true);

        // Abort — must interrupt the blocking wait and clear pending state.
        await sut.AbortAsync();
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));

        // Stop before sending anything to prevent a new CQ from firing (AutoAnswer stays true
        // in the mock config store which doesn't persist SaveAsync calls).
        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);

        sut.State.Should().Be(QsoState.Idle);
        sut.Partner.Should().BeNull("abort must clear the active partner");
        // Only 1 KeyDown in total — the initial CQ; no TxReport fired.
        ptt.ReceivedCalls()
            .Count(c => c.GetMethodInfo().Name == "KeyDownAsync")
            .Should().Be(1, "only the initial CQ TX must have fired; abort must prevent TxReport");

        await ptt.DisposeAsync();
    }

    // ── D-CALLER-021: pending responder fires unconditionally within a correct-phase window ──

    /// <summary>
    /// Task 3.2 — regression test protecting the (already-correct, never-guarded)
    /// pending-responder consumption path in <c>HandleWaitAnswerAsync</c> against a future
    /// contributor adding a lateness guard by analogy with the pattern D-CALLER-021 removed from
    /// <see cref="QsoAnswererService"/>. <c>setAt</c> is backdated 6 s (as if the responder had
    /// been selected 6 s into its window) purely to document intent — this path has never read
    /// "how many seconds into the window" at all, only the phase check and the unrelated 60 s
    /// staleness guard, so backdating by 6 s vs. 0 s should make no observable difference; that
    /// invariant is exactly what this test locks in.
    /// </summary>
    [Fact(DisplayName = "D-CALLER-021: pending responder armed 6 s into its window still fires immediately (no lateness guard)")]
    public async Task SelectResponderAsync_LateButCorrectPhase_FiresImmediately()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.None,
            RetryCount          = 0,
            WatchdogMinutes     = 4,
        };
        var (sut, _, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
        await sut.StartAsync(stopCts.Token);

        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        // TestSetPendingResponder bypasses SelectResponderAsync's wakeup push — no race (5.6/5.7's
        // rationale). setAt backdated 6 s to represent "selected 6 s into its window."
        sut.TestSetPendingResponder(PartnerCall, AudioFreqHz, isAPhase: true,
            setAt: DateTimeOffset.UtcNow - TimeSpan.FromSeconds(6));

        // Correct-phase batch: CycleStart :45 (B-phase) → +15 s = :00 A-phase ✓ (matches 5.6's
        // known-good values).
        var correctPhaseCycleStart = new DateTimeOffset(2026, 6, 25, 14, 29, 45, TimeSpan.Zero);
        SendAt(channel, correctPhaseCycleStart, Make($"{OurCallsign} {PartnerCall} {PartnerGrid}"));

        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(3));
        sut.Partner.Should().Be(PartnerCall);

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── D-CALLER-021: window-boundary transmission truncation (task 5.5, mirrors ──
    // ── QsoAnswererServiceTests' G/H/I/J) ─────────────────────────────────────────

    [Fact(DisplayName = "D-CALLER-021: TransmitAsync — late in window (9 s in) truncates the buffer to the remaining 6 s")]
    public async Task TransmitAsync_LateInWindow_TruncatesBufferToRemainingTime()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.None,
            RetryCount          = 0,
            WatchdogMinutes     = 4,
        };
        // FakeTime starts at 0 s into the window (full, untruncated) so the initial CQ TX below
        // is unaffected; advanced to 9 s in (6.0 s remaining → 6.0 s × 48 000 Hz = 288 000 samples
        // exactly) only for the pending-responder TX this test actually cares about — otherwise
        // BOTH transmissions would share the same fixed truncated length and the "exactly 1 call"
        // assertion below would see 2 matches.
        var fakeTime = new FakeTimeProvider(new DateTimeOffset(2026, 6, 25, 14, 30, 0, TimeSpan.Zero));
        var (sut, _, _, ptt, channel, stopCts) = BuildIsolatedSut(
            tx, watchdogDuration: TimeSpan.FromSeconds(30), timeProvider: fakeTime);
        await sut.StartAsync(stopCts.Token);

        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        fakeTime.UtcNow = new DateTimeOffset(2026, 6, 25, 14, 30, 9, TimeSpan.Zero);
        sut.TestSetPendingResponder(PartnerCall, AudioFreqHz, isAPhase: true);

        var correctPhaseCycleStart = new DateTimeOffset(2026, 6, 25, 14, 29, 45, TimeSpan.Zero);
        SendAt(channel, correctPhaseCycleStart, Make($"{OurCallsign} {PartnerCall} {PartnerGrid}"));

        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(3));
        ptt.Received(1).LoadAudio(Arg.Is<float[]>(s => s.Length == 288_000));

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "D-CALLER-021: TransmitAsync — on-time (0 s in) loads the full, untruncated buffer")]
    public async Task TransmitAsync_OnTime_LoadsFullUntruncatedBuffer()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.None,
            RetryCount          = 0,
            WatchdogMinutes     = 4,
        };
        var fakeTime = new FakeTimeProvider(new DateTimeOffset(2026, 6, 25, 14, 30, 0, TimeSpan.Zero));
        var (sut, _, _, ptt, channel, stopCts) = BuildIsolatedSut(
            tx, watchdogDuration: TimeSpan.FromSeconds(30), timeProvider: fakeTime);
        await sut.StartAsync(stopCts.Token);

        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        sut.TestSetPendingResponder(PartnerCall, AudioFreqHz, isAPhase: true);

        var correctPhaseCycleStart = new DateTimeOffset(2026, 6, 25, 14, 29, 45, TimeSpan.Zero);
        SendAt(channel, correctPhaseCycleStart, Make($"{OurCallsign} {PartnerCall} {PartnerGrid}"));

        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(3));
        // Both the initial CQ and the pending-responder TX fire under the same fixed "0 s in"
        // fakeTime, so both legitimately load the full untruncated buffer — 2 matching calls.
        ptt.Received(2).LoadAudio(Arg.Is<float[]>(s => s.Length == Ft8AudioSynthesiser.TotalSampleCount));

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "D-CALLER-021: TransmitAsync — zero remaining time skips transmission without throwing")]
    public async Task TransmitAsync_ZeroRemainingTime_SkipsTransmissionWithoutThrowing()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.None,
            RetryCount          = 0,
            WatchdogMinutes     = 4,
        };
        // 1 tick (100 ns) before the :15 boundary of the :00 A-phase window — truncates to 0
        // samples at 48 000 Hz (mirrors QsoAnswererServiceTests' identical "I" case).
        var fakeTime = new FakeTimeProvider(
            new DateTimeOffset(2026, 6, 25, 14, 30, 15, TimeSpan.Zero).AddTicks(-1));
        var (sut, _, _, ptt, channel, stopCts) = BuildIsolatedSut(
            tx, watchdogDuration: TimeSpan.FromSeconds(30), timeProvider: fakeTime);
        await sut.StartAsync(stopCts.Token);

        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        sut.TestSetPendingResponder(PartnerCall, AudioFreqHz, isAPhase: true);

        var correctPhaseCycleStart = new DateTimeOffset(2026, 6, 25, 14, 29, 45, TimeSpan.Zero);
        SendAt(channel, correctPhaseCycleStart, Make($"{OurCallsign} {PartnerCall} {PartnerGrid}"));

        // ExecuteTxReportAsync-equivalent flow still advances to WaitRr73 even though TransmitAsync
        // skipped the actual keying — the skip must not throw or otherwise abort the state machine.
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(3));

        ptt.DidNotReceive().LoadAudio(Arg.Any<float[]>());
        await ptt.DidNotReceive().KeyDownAsync(Arg.Any<CancellationToken>());

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "D-CALLER-021: a truncated transmission that goes unanswered still counts toward the retry budget")]
    public async Task TruncatedTransmission_Unanswered_StillCountsTowardRetryBudget()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.None,
            RetryCount          = 2,
            WatchdogMinutes     = 4,
        };
        // FakeTime starts at 0 s in (full) so the initial CQ TX is untruncated; advanced to 9 s in
        // only for the pending-responder TX — see TransmitAsync_LateInWindow's identical rationale.
        var fakeTime = new FakeTimeProvider(new DateTimeOffset(2026, 6, 25, 14, 30, 0, TimeSpan.Zero));
        var (sut, _, _, ptt, channel, stopCts) = BuildIsolatedSut(
            tx, watchdogDuration: TimeSpan.FromSeconds(30), timeProvider: fakeTime);
        await sut.StartAsync(stopCts.Token);

        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        fakeTime.UtcNow = new DateTimeOffset(2026, 6, 25, 14, 30, 9, TimeSpan.Zero);
        sut.TestSetPendingResponder(PartnerCall, AudioFreqHz, isAPhase: true);

        var correctPhaseCycleStart = new DateTimeOffset(2026, 6, 25, 14, 29, 45, TimeSpan.Zero);
        SendAt(channel, correctPhaseCycleStart, Make($"{OurCallsign} {PartnerCall} {PartnerGrid}"));
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(3));
        ptt.Received(1).LoadAudio(Arg.Is<float[]>(s => s.Length == 288_000)); // confirms truncated

        // A-01 skip-then-retry silence pattern (same convention as QsoAnswererServiceTests' J case
        // and this file's own 6.5/6.6-style retry-exhaustion tests): first silence cycle is
        // skipped, second consecutive one fires a retry.
        SendAt(channel, new DateTimeOffset(2026, 6, 25, 14, 30, 15, TimeSpan.Zero));
        await Task.Delay(150);
        await ptt.Received(2).KeyDownAsync(Arg.Any<CancellationToken>()); // CQ + TxReport, no retry yet

        SendAt(channel, new DateTimeOffset(2026, 6, 25, 14, 30, 30, TimeSpan.Zero));
        await Task.Delay(300);
        await ptt.Received(3).KeyDownAsync(Arg.Any<CancellationToken>()); // retry fired
        sut.State.Should().Be(QsoState.WaitRr73, "one retry should not exhaust the retry budget");

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── 5.8: R+report triggers TxRr73 ────────────────────────────────────────

    [Fact(DisplayName = "5.8: HandleWaitRr73Async — R+report from partner triggers TxRr73")]
    public async Task WaitRr73_RogerReportFromPartner_TriggersTxRr73()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.First,
            RetryCount          = 3,
            WatchdogMinutes     = 4,
        };
        var (sut, _, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
        await sut.StartAsync(stopCts.Token);

        // CQ → WaitAnswer → TxReport → WaitRr73.
        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        Send(channel, Make($"{OurCallsign} {PartnerCall} {PartnerGrid}"));
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(5));

        // Feed R+07 from partner to us.
        Send(channel, Make($"{OurCallsign} {PartnerCall} R+07"));

        // Should advance through TxRr73 → Idle (QsoComplete → SafeAbortToIdle).
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));

        // KeyDownAsync: CQ + report + RR73 = 3 transmissions.
        await ptt.Received(3).KeyDownAsync(Arg.Any<CancellationToken>());

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── 5.9: Partner working another station aborts ───────────────────────────

    [Fact(DisplayName = "5.9: HandleWaitRr73Async — partner working another station aborts")]
    public async Task WaitRr73_PartnerWorkingOther_Aborts()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.First,
            RetryCount          = 3,
            WatchdogMinutes     = 4,
        };
        var (sut, eventBus, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
        await sut.StartAsync(stopCts.Token);

        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        Send(channel, Make($"{OurCallsign} {PartnerCall} {PartnerGrid}"));
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(5));

        // Partner sends a message addressed to someone else.
        Send(channel, Make($"Q2OTHER {PartnerCall} -10"));

        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));

        eventBus.Received().Publish(
            "Idle",
            "caller",
            Arg.Any<string?>(),   // partner is null; Arg.Any avoids NSubstitute arg-matcher ordering issue
            false,
            $"Partner {PartnerCall} is working another station");

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── D-CALLER-020: Partner still calling CQ in WaitRr73 must not abort ────

    [Fact(DisplayName = "D-CALLER-020: HandleWaitRr73Async — partner re-transmitting own CQ does not abort — retries then exhausts")]
    public async Task WaitRr73_PartnerStillCallingCq_DoesNotAbort_RetriesInstead()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.First,
            RetryCount          = 2,
            WatchdogMinutes     = 4,
        };
        var (sut, eventBus, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
        await sut.StartAsync(stopCts.Token);

        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        Send(channel, Make($"{OurCallsign} {PartnerCall} {PartnerGrid}"));
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(5));

        // Partner re-transmits their own CQ instead of RR73 — must NOT be treated as "partner is
        // working another station"; they simply haven't decoded our report yet.
        Send(channel, Make($"CQ {PartnerCall} {PartnerGrid}"));
        await Task.Delay(200);
        sut.State.Should().Be(QsoState.WaitRr73,
            "the partner still calling CQ is not evidence they've moved on (D-CALLER-020) — must not abort");

        // The repeated CQ must fall through to the same "no matching message" retry path as
        // genuine silence — drive the identical retry-exhaustion sequence as the answerer-side
        // test (tx.RetryCount = 2; pattern: [skip] [retry1] [skip] [retry2] [skip] [abort]) to
        // prove the existing RetryOrAbortAsync backstop is what eventually ends a one-sided QSO.
        Send(channel, Make($"CQ {PartnerCall} {PartnerGrid}")); // cycle 2: retry 1 TX
        await Task.Delay(150);
        Send(channel, Make($"CQ {PartnerCall} {PartnerGrid}")); // cycle 3: skip — retry 1 TX window
        await Task.Delay(150);
        Send(channel, Make($"CQ {PartnerCall} {PartnerGrid}")); // cycle 4: retry 2 TX
        await Task.Delay(150);
        Send(channel, Make($"CQ {PartnerCall} {PartnerGrid}")); // cycle 5: skip — retry 2 TX window
        await Task.Delay(150);
        Send(channel, Make($"CQ {PartnerCall} {PartnerGrid}")); // cycle 6: retry count exhausted → abort
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));

        eventBus.Received().Publish(
            "Idle",
            "caller",
            Arg.Any<string?>(),
            false,
            $"No response from {PartnerCall} after 2 retries");

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── 5.10: Retry logic ─────────────────────────────────────────────────────

    [Fact(DisplayName = "5.10: WaitAnswer no response — retransmits CQ; exhausted aborts with CQ-retry reason")]
    public async Task WaitAnswer_NoResponse_RetriesCqThenAborts()
    {
        // RetryCount=2 → abort after retryCount reaches 3 (3 > 2).
        // Each cycle: WaitAnswer (A-01=true) → empty (A-01 skip) → empty (retry or abort).
        // Total empty-batch pairs: 2 retransmits + 1 abort = 3 pairs.
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.First,
            RetryCount          = 2,
            WatchdogMinutes     = 4,
        };
        var (sut, eventBus, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
        await sut.StartAsync(stopCts.Token);

        // Arm → CQ → WaitAnswer.
        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        // 3 rounds: (retry 1), (retry 2), (abort).
        for (int i = 0; i < 3; i++)
        {
            // A-01 skip batch (the window right after our own CQ TX).
            Send(channel);
            await Task.Delay(120); // allow service to process the skip

            // Retry/abort-triggering batch.
            Send(channel);

            if (i < 2)
            {
                // Expect re-entry into WaitAnswer after CQ retransmit.
                await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));
            }
            else
            {
                // 3rd trigger: retryCount=3 > 2 → abort.
                await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));
            }
        }

        // The abort reason must mention CQ retries.
        eventBus.Received().Publish(
            "Idle",
            "caller",
            Arg.Any<string?>(),
            false,
            "No response after 2 CQ retries");

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── 5.11: A-01 guard ─────────────────────────────────────────────────────

    [Fact(DisplayName = "5.11: WaitAnswer A-01 guard — first empty cycle is skipped, no retry")]
    public async Task WaitAnswer_A01Guard_FirstEmptyCycleSkipped()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.First,
            RetryCount          = 1,    // only 1 retry allowed
            WatchdogMinutes     = 4,
        };
        var (sut, eventBus, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
        await sut.StartAsync(stopCts.Token);

        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        // A-01 guard: first empty batch after entering WaitAnswer should NOT count as retry.
        Send(channel); // A-01 skip
        await Task.Delay(150);

        // Service should still be in WaitAnswer (not aborted after just 1 empty cycle).
        sut.State.Should().Be(QsoState.WaitReport);

        // Second empty batch → 1 retry fires (retransmits CQ). Goes back to WaitAnswer.
        Send(channel);
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));
        await Task.Delay(100);

        // Third empty batch (after A-01 of the retry) → abort.
        Send(channel); // A-01 of the retry CQ
        await Task.Delay(100);
        Send(channel); // real empty → abort
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── 5.12: Supervised disarm ───────────────────────────────────────────────

    [Fact(DisplayName = "5.12: SafeAbortToIdleAsync — saves AutoAnswer=false; txState has autoAnswerEnabled=false")]
    public async Task SafeAbortToIdleAsync_SavesAutoAnswerFalse_AndBroadcastsDisarmed()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.First,
            RetryCount          = 3,
            WatchdogMinutes     = 4,
        };
        var (sut, eventBus, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
        await sut.StartAsync(stopCts.Token);

        // Start a CQ session.
        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        // Abort the session.
        await sut.AbortAsync();
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(3));

        // The Idle broadcast must carry autoAnswerEnabled=false.
        eventBus.Received().Publish(
            "Idle",
            "caller",
            Arg.Any<string?>(),   // partner is null; Arg.Any avoids NSubstitute arg-matcher ordering issue
            false,
            Arg.Any<string?>());

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── 5.14: SelectResponderAsync no-op on QsoAnswererService ───────────────

    [Fact(DisplayName = "5.14: SelectResponderAsync no-op on QsoAnswererService — does not throw")]
    public async Task AnswererService_SelectResponderAsync_IsNoOp()
    {
        var ptt = Substitute.For<IPttController>();
        ptt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var store = Substitute.For<IConfigStore>();
        store.Current.Returns(new AppConfig() with
        {
            Tx = new TxConfig { AutoAnswer = false, Callsign = OurCallsign, Grid = OurGrid }
        });

        var adifLog = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);
        var channel = Channel.CreateUnbounded<DecodeBatch>();
        var answerer = new QsoAnswererService(
            channel.Reader, store, ptt, new TxEventBus(),
            adifLog, new AudioOffsetEventBus(),
            NullLogger<QsoAnswererService>.Instance);

        // SelectResponderAsync must return without throwing and without changing state.
        var act = async () => await answerer.SelectResponderAsync(
            "Q1TST", 1500.0, DateTimeOffset.UtcNow, CancellationToken.None);

        await act.Should().NotThrowAsync();
        answerer.State.Should().Be(QsoState.Idle);

        await ptt.DisposeAsync();
    }

    // ── D-CALLER-003: None-mode retransmit guard ──────────────────────────────

    /// <summary>
    /// When <c>CallerPartnerSelect = None</c> and a decoded batch contains at least one
    /// message addressed to our callsign, the service must hold in <see cref="QsoState.WaitReport"/>
    /// (i.e. <see cref="CallerState.WaitAnswer"/>) without retransmitting the CQ.
    /// Pre-fix: the service would fall through to <see cref="QsoCallerService.RetryOrAbortAsync"/>
    /// and retransmit CQ on every cycle that lacked a pending responder, closing the operator
    /// click window within milliseconds.
    /// </summary>
    [Fact(DisplayName = "D-CALLER-003 (1): None mode — batch with responder holds in WaitAnswer, no retry TX")]
    public async Task HandleWaitAnswer_NoneMode_HoldsWhenResponderPresent()
    {
        // RetryCount=1 so without the fix the first non-skip cycle would retransmit CQ.
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.None,
            RetryCount          = 1,
            WatchdogMinutes     = 4,
        };
        var (sut, _, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
        await sut.StartAsync(stopCts.Token);

        // Arm service → CQ TX → WaitAnswer.
        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        // A-01 skip: first empty cycle after entering WaitAnswer is always skipped.
        Send(channel);
        await Task.Delay(150);

        // Batch WITH a responder addressed to our callsign — service must hold in WaitAnswer.
        Send(channel, Make($"{OurCallsign} {PartnerCall} {PartnerGrid}"));
        await Task.Delay(200);

        sut.State.Should().Be(QsoState.WaitReport,
            "None mode should hold in WaitAnswer when the batch contains a response to our CQ");
        ptt.ReceivedCalls()
           .Count(c => c.GetMethodInfo().Name == "KeyDownAsync")
           .Should().Be(1, "retry CQ must not fire when the batch contains a responder in None mode");

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    /// <summary>
    /// When <c>CallerPartnerSelect = None</c> and a decoded batch contains <em>no</em> message
    /// addressed to our callsign, the service must still retransmit the CQ (same behaviour as
    /// before the D-CALLER-003 fix, but now conditional on batch content).
    ///
    /// <para>
    /// This test constructs its own SUT with a 100 ms <c>KeyDownAsync</c> delay so that the
    /// <c>TxCq</c> (TxAnswer) state is observable by the polling helpers.  If <c>KeyDownAsync</c>
    /// returns <c>Task.CompletedTask</c> the TxCq window is nanoseconds wide — the poller can
    /// never catch it — so a delay is necessary for reliable state-based synchronisation.
    /// </para>
    /// </summary>
    [Fact(DisplayName = "D-CALLER-003 (2): None mode — empty batch triggers CQ retransmit")]
    public async Task HandleWaitAnswer_NoneMode_RetriesWhenNoBatchResponder()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.None,
            RetryCount          = 3,
            WatchdogMinutes     = 4,
        };

        // Inline SUT: KeyDownAsync takes 100 ms so TxCq state is visible to WaitForStateAsync.
        var ptt = Substitute.For<IPttController>();
        ptt.KeyDownAsync(Arg.Any<CancellationToken>())
           .Returns(c => Task.Delay(100, (CancellationToken)c.Args()[0]));
        ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var store = Substitute.For<IConfigStore>();
        store.Current.Returns(new AppConfig() with { Tx = tx });
        store.SaveAsync(Arg.Any<AppConfig>(), Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var adifLog = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);
        var channel = Channel.CreateUnbounded<DecodeBatch>();
        var stopCts = new CancellationTokenSource();

        var sut = new QsoCallerService(
            channel.Reader, store, ptt, Substitute.For<ITxEventBus>(),
            adifLog, new AudioOffsetEventBus(),
            NullLogger<QsoCallerService>.Instance,
            watchdogDurationOverride: TimeSpan.FromSeconds(30));

        await sut.StartAsync(stopCts.Token);

        // Arm service → CQ TX → WaitAnswer.
        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        // A-01 skip.
        Send(channel);
        await Task.Delay(250); // ample time for A-01 batch to be processed

        // Empty batch (no message addresses our callsign): RetryOrAbortAsync should fire.
        Send(channel);

        // With 100 ms KeyDown delay, TxCq is visible for ~100 ms — catch the transition.
        await WaitForStateAsync(sut, QsoState.TxAnswer, timeout: TimeSpan.FromSeconds(5));
        // Then wait for the retry CQ to complete and return to WaitAnswer.
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        // Two KeyDownAsync calls: initial CQ + retry CQ.
        await ptt.Received(2).KeyDownAsync(Arg.Any<CancellationToken>());
        sut.State.Should().Be(QsoState.WaitReport, "service should re-enter WaitAnswer after CQ retry");

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    /// <summary>
    /// End-to-end None-mode flow: responder-present batch holds the service, then an operator
    /// click via <see cref="QsoCallerService.SelectResponderAsync"/> advances the QSO to
    /// <see cref="QsoState.WaitRr73"/> with the correct partner set.
    /// </summary>
    [Fact(DisplayName = "D-CALLER-003 (3): None mode — operator click after hold advances to TxReport/WaitRr73")]
    public async Task HandleWaitAnswer_NoneMode_FiresTxAfterOperatorClick()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.None,
            RetryCount          = 3,
            WatchdogMinutes     = 4,
        };
        var (sut, _, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
        await sut.StartAsync(stopCts.Token);

        // Arm service → CQ TX → WaitAnswer.
        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        // A-01 skip.
        Send(channel);
        await Task.Delay(150);

        // Batch WITH responder — service holds in WaitAnswer.
        Send(channel, Make($"{OurCallsign} {PartnerCall} {PartnerGrid}"));
        await Task.Delay(200);
        sut.State.Should().Be(QsoState.WaitReport, "service should hold in WaitAnswer");

        // Operator clicks the highlighted decode-table row.
        // Response at :15 → B-phase response → our answer must be A-phase (:00/:30).
        var bPhaseResponseStart = new DateTimeOffset(2026, 6, 25, 14, 29, 15, TimeSpan.Zero);
        await sut.SelectResponderAsync(PartnerCall, AudioFreqHz, bPhaseResponseStart, CancellationToken.None);

        // Drain the wakeup batch pushed by SelectResponderAsync so the service does not
        // fire on a non-deterministic wall-clock phase; the test controls the batch below.
        while (sut._wakeupChannel.Reader.TryRead(out _)) { }
        await Task.Delay(50); // let service settle back into Task.WhenAny

        // Feed an A-phase batch (CycleStart :45 → next cycle :00 = A-phase).
        var aPhaseCycleStart = new DateTimeOffset(2026, 6, 25, 14, 29, 45, TimeSpan.Zero);
        SendAt(channel, aPhaseCycleStart, Make($"{OurCallsign} {PartnerCall} {PartnerGrid}"));

        // Service fires TxReport then enters WaitRr73.
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(5));
        sut.Partner.Should().Be(PartnerCall);

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── TryParseResponder portable-suffix tests (fix-caller-state-bugs) ───────

    [Fact(DisplayName = "TryParseResponder: full compound callsign (PD2FZ/P) is matched")]
    public void TryParseResponder_MatchesFullCallsign()
    {
        // "PD2FZ/P Q1ABC JO22" — destination token is the full compound callsign.
        var result = QsoCallerService.TryParseResponder(
            "PD2FZ/P Q1ABC JO22", "PD2FZ/P",
            out var partner, out _, out _);

        result.Should().BeTrue();
        partner.Should().Be("Q1ABC");
    }

    [Fact(DisplayName = "TryParseResponder: base callsign (PD2FZ) accepted when /P is dropped by decoder")]
    public void TryParseResponder_MatchesBaseCallsignWhenSlashPDropped()
    {
        // "PD2FZ Q1ABC JO22" — decoder stripped /P from the destination token.
        // TryParseResponder must still accept this as a valid response to our CQ.
        var result = QsoCallerService.TryParseResponder(
            "PD2FZ Q1ABC JO22", "PD2FZ/P",
            out var partner, out _, out _);

        result.Should().BeTrue();
        partner.Should().Be("Q1ABC");
    }

    [Fact(DisplayName = "TryParseResponder: non-matching callsign is rejected")]
    public void TryParseResponder_RejectsNonMatchingCallsign()
    {
        // First token is a completely different callsign — must return false.
        var result = QsoCallerService.TryParseResponder(
            "Q9ZZZ Q1ABC JO22", "PD2FZ/P",
            out var partner, out _, out _);

        result.Should().BeFalse();
        partner.Should().BeEmpty();
    }

    // ── TryParseResponder signal-report tests (D-CALLER-001) ─────────────────

    [Fact(DisplayName = "TryParseResponder: accepts positive signal report (+32) as third token")]
    public void TryParseResponder_AcceptsPositiveSignalReport()
    {
        // Some operators answer a CQ with a signal report instead of a grid square.
        // "PD2FZ/P Q1ABC +32" must be accepted; partner must be "Q1ABC".
        var result = QsoCallerService.TryParseResponder(
            "PD2FZ/P Q1ABC +32", "PD2FZ/P",
            out var partner, out _, out _);

        result.Should().BeTrue();
        partner.Should().Be("Q1ABC");
    }

    [Fact(DisplayName = "TryParseResponder: accepts negative signal report (-05) as third token")]
    public void TryParseResponder_AcceptsNegativeSignalReport()
    {
        var result = QsoCallerService.TryParseResponder(
            "PD2FZ Q1ABC -05", "PD2FZ",
            out var partner, out _, out _);

        result.Should().BeTrue();
        partner.Should().Be("Q1ABC");
    }

    [Fact(DisplayName = "TryParseResponder: accepts roger signal report (R+33) as third token")]
    public void TryParseResponder_AcceptsRogerSignalReport()
    {
        var result = QsoCallerService.TryParseResponder(
            "PD2FZ/P Q1ABC R+33", "PD2FZ/P",
            out var partner, out _, out _);

        result.Should().BeTrue();
        partner.Should().Be("Q1ABC");
    }

    [Fact(DisplayName = "TryParseResponder: rejects 73 as third token (not a valid CQ response)")]
    public void TryParseResponder_Rejects73AsThirdToken()
    {
        // "73" is a QSO termination message — must NOT be mistaken for a CQ response.
        var result = QsoCallerService.TryParseResponder(
            "PD2FZ/P Q1ABC 73", "PD2FZ/P",
            out var partner, out _, out _);

        result.Should().BeFalse();
        partner.Should().BeEmpty();
    }

    // ── qso-log-dialog: QsoConfirmation tests (task 6.3) ─────────────────────

    [Fact(DisplayName = "qso-log-dialog 6.3a: QsoConfirmation=true emits PublishQsoReview on TxRr73 entry")]
    public async Task ExecuteTxRr73Async_QsoConfirmationEnabled_PublishesQsoReviewEvent()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.First,
            RetryCount          = 3,
            WatchdogMinutes     = 1,
            QsoConfirmation     = true,
        };
        var mockAdif = Substitute.For<IAdifLogWriter>();
        mockAdif.AppendQsoAsync(Arg.Any<QsoRecord>()).Returns(Task.CompletedTask);

        var (sut, eventBus, _, ptt, channel, stopCts) =
            BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30), adifLog: mockAdif);

        await sut.StartAsync(stopCts.Token);

        // CQ → WaitAnswer (WaitReport) → TxReport → WaitRr73 → TxRr73 → Idle.
        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        Send(channel, Make($"{OurCallsign} {PartnerCall} {PartnerGrid}"));
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(5));

        Send(channel, Make($"{OurCallsign} {PartnerCall} R+07"));
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));

        eventBus.Received(1).PublishQsoReview(
            Arg.Is<QsoRecord>(r => r.PartnerCallsign == PartnerCall),
            Arg.Any<string>(),
            Arg.Any<string>(),
            Arg.Any<string>());

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "qso-log-dialog 6.3b: QsoConfirmation=true skips ADIF AppendQsoAsync")]
    public async Task ExecuteTxRr73Async_QsoConfirmationEnabled_SkipsAdifWrite()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.First,
            RetryCount          = 3,
            WatchdogMinutes     = 1,
            QsoConfirmation     = true,
        };
        var mockAdif = Substitute.For<IAdifLogWriter>();
        mockAdif.AppendQsoAsync(Arg.Any<QsoRecord>()).Returns(Task.CompletedTask);

        var (sut, _, _, ptt, channel, stopCts) =
            BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30), adifLog: mockAdif);

        await sut.StartAsync(stopCts.Token);

        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        Send(channel, Make($"{OurCallsign} {PartnerCall} {PartnerGrid}"));
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(5));

        Send(channel, Make($"{OurCallsign} {PartnerCall} R+07"));
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));

        await mockAdif.DidNotReceive().AppendQsoAsync(Arg.Any<QsoRecord>());

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "qso-log-dialog 6.3c: QsoConfirmation=false still calls ADIF AppendQsoAsync")]
    public async Task ExecuteTxRr73Async_QsoConfirmationDisabled_WritesAdif()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.First,
            RetryCount          = 3,
            WatchdogMinutes     = 1,
            QsoConfirmation     = false,
        };
        var mockAdif = Substitute.For<IAdifLogWriter>();
        mockAdif.AppendQsoAsync(Arg.Any<QsoRecord>()).Returns(Task.CompletedTask);

        var (sut, _, _, ptt, channel, stopCts) =
            BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30), adifLog: mockAdif);

        await sut.StartAsync(stopCts.Token);

        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        Send(channel, Make($"{OurCallsign} {PartnerCall} {PartnerGrid}"));
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(5));

        Send(channel, Make($"{OurCallsign} {PartnerCall} R+07"));
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));

        await mockAdif.Received(1).AppendQsoAsync(Arg.Any<QsoRecord>());

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── fix-adif-partner-grid-capture: partner grid capture for ADIF logging ──

    [Fact(DisplayName = "FR-adif-partner-grid: First-mode auto-engage captures partner grid into QsoRecord.PartnerGrid")]
    public async Task ExecuteTxReportAsync_FirstMode_CapturesPartnerGridIntoQsoRecord()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.First,
            RetryCount          = 3,
            WatchdogMinutes     = 1,
            QsoConfirmation     = false,
        };
        var mockAdif = Substitute.For<IAdifLogWriter>();
        mockAdif.AppendQsoAsync(Arg.Any<QsoRecord>()).Returns(Task.CompletedTask);

        var (sut, _, _, ptt, channel, stopCts) =
            BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30), adifLog: mockAdif);

        await sut.StartAsync(stopCts.Token);

        // CQ → WaitAnswer (WaitReport) → TxReport → WaitRr73 → TxRr73 → Idle.
        // The CQ-answer message includes the partner's grid (Q1TST JO22) — TryParseResponder
        // must surface it and the fix must thread it all the way to the final QsoRecord.
        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        Send(channel, Make($"{OurCallsign} {PartnerCall} {PartnerGrid}"));
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(5));

        Send(channel, Make($"{OurCallsign} {PartnerCall} R+07"));
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));

        await mockAdif.Received(1).AppendQsoAsync(
            Arg.Is<QsoRecord>(r => r.PartnerCallsign == PartnerCall && r.PartnerGrid == PartnerGrid));

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "FR-adif-partner-grid: None-mode manual select (SelectResponderAsync) captures partner grid into QsoRecord.PartnerGrid")]
    public async Task SelectResponderAsync_NoneMode_CapturesPartnerGridIntoQsoRecord()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.None,
            RetryCount          = 0,
            WatchdogMinutes     = 4,
            QsoConfirmation     = false,
        };
        var mockAdif = Substitute.For<IAdifLogWriter>();
        mockAdif.AppendQsoAsync(Arg.Any<QsoRecord>()).Returns(Task.CompletedTask);

        var (sut, _, _, ptt, channel, stopCts) =
            BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30), adifLog: mockAdif);

        await sut.StartAsync(stopCts.Token);

        // Drive to WaitAnswer.
        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        // None-mode auto-track: this batch does NOT auto-advance, but records the responder's
        // raw decode (including the grid) into _recentResponderDecodes — this is what
        // SelectResponderAsync must re-parse to recover the grid, since it receives only a
        // callsign/frequency/cycle-start, not the original decoded message.
        Send(channel, Make($"{OurCallsign} {PartnerCall} {PartnerGrid}"));
        await Task.Delay(150);
        sut.State.Should().Be(QsoState.WaitReport, "None mode must not auto-advance");

        // Drain any wakeup written while draining the above.
        while (sut._wakeupChannel.Reader.TryRead(out _)) { }

        // Operator selects the responder. responseCycleStart at :15 → B-phase response →
        // A-phase answer (:00 or :30), mirroring the 5.5 phase-semantics pattern.
        var bPhaseResponse = new DateTimeOffset(2026, 6, 25, 14, 29, 15, TimeSpan.Zero);
        await sut.SelectResponderAsync(PartnerCall, AudioFreqHz, bPhaseResponse, CancellationToken.None);
        while (sut._wakeupChannel.Reader.TryRead(out _)) { }
        await Task.Delay(50);

        // Feed an A-phase batch (correct phase: CycleStart :45 → next cycle :00 = A-phase) to
        // fire the pending responder.
        var correctPhaseCycleStart = new DateTimeOffset(2026, 6, 25, 14, 29, 45, TimeSpan.Zero);
        SendAt(channel, correctPhaseCycleStart, Make("CQ Q2NOISE JO00")); // content irrelevant — pending-responder path fires on phase alone
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(5));
        sut.Partner.Should().Be(PartnerCall);

        Send(channel, Make($"{OurCallsign} {PartnerCall} R+07"));
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));

        await mockAdif.Received(1).AppendQsoAsync(
            Arg.Is<QsoRecord>(r => r.PartnerCallsign == PartnerCall && r.PartnerGrid == PartnerGrid));

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "FR-adif-partner-grid: bare signal-report answer (no grid sent) yields QsoRecord.PartnerGrid = null, not fabricated")]
    public async Task ExecuteTxReportAsync_NoGridSent_YieldsNullPartnerGrid()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.First,
            RetryCount          = 3,
            WatchdogMinutes     = 1,
            QsoConfirmation     = false,
        };
        var mockAdif = Substitute.For<IAdifLogWriter>();
        mockAdif.AppendQsoAsync(Arg.Any<QsoRecord>()).Returns(Task.CompletedTask);

        var (sut, _, _, ptt, channel, stopCts) =
            BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30), adifLog: mockAdif);

        await sut.StartAsync(stopCts.Token);

        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        // Partner answers with a bare signal report instead of a grid — valid FT8 behaviour.
        // The fix must not invent a grid where none was sent.
        Send(channel, Make($"{OurCallsign} {PartnerCall} -05"));
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(5));

        Send(channel, Make($"{OurCallsign} {PartnerCall} R+07"));
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));

        await mockAdif.Received(1).AppendQsoAsync(
            Arg.Is<QsoRecord>(r => r.PartnerCallsign == PartnerCall && r.PartnerGrid == null));

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── D-013: QSO records must use the live CAT dial frequency, not the stale ──
    //           DecodeLog.DialFrequencyMHz config fallback, when CAT is connected ──

    [Fact(DisplayName = "D-013: live CAT frequency differs from config → ADIF record uses live CAT value")]
    public async Task QsoComplete_LiveCatFrequencyDiffersFromConfig_AdifRecordUsesLiveCatValue()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.First,
            RetryCount          = 3,
            WatchdogMinutes     = 1,
            QsoConfirmation     = false,
        };
        var appConfig = new AppConfig() with
        {
            DecodeLog = new DecodeLogConfig { DialFrequencyMHz = 7.100 }, // stale: 40m
        };
        var catState = new StubCatState(14.074); // live: 20m
        var mockAdif = Substitute.For<IAdifLogWriter>();
        mockAdif.AppendQsoAsync(Arg.Any<QsoRecord>()).Returns(Task.CompletedTask);

        var (sut, _, _, ptt, channel, stopCts) = BuildIsolatedSut(
            tx, watchdogDuration: TimeSpan.FromSeconds(30), adifLog: mockAdif,
            catState: catState, appConfig: appConfig);

        await sut.StartAsync(stopCts.Token);

        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        Send(channel, Make($"{OurCallsign} {PartnerCall} {PartnerGrid}"));
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(5));

        Send(channel, Make($"{OurCallsign} {PartnerCall} R+07"));
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));

        // The completed QsoRecord must carry the live CAT frequency, not the stale config value.
        await mockAdif.Received(1).AppendQsoAsync(
            Arg.Is<QsoRecord>(r => r.DialFrequencyMHz == 14.074));

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "D-013: no ICatState wired up → ADIF record falls back to config value (no regression)")]
    public async Task QsoComplete_NoCatState_FallsBackToConfigValue()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.First,
            RetryCount          = 3,
            WatchdogMinutes     = 1,
            QsoConfirmation     = false,
        };
        var appConfig = new AppConfig() with
        {
            DecodeLog = new DecodeLogConfig { DialFrequencyMHz = 7.100 },
        };
        var mockAdif = Substitute.For<IAdifLogWriter>();
        mockAdif.AppendQsoAsync(Arg.Any<QsoRecord>()).Returns(Task.CompletedTask);

        var (sut, _, _, ptt, channel, stopCts) = BuildIsolatedSut(
            tx, watchdogDuration: TimeSpan.FromSeconds(30), adifLog: mockAdif,
            catState: null, appConfig: appConfig);

        await sut.StartAsync(stopCts.Token);

        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        Send(channel, Make($"{OurCallsign} {PartnerCall} {PartnerGrid}"));
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(5));

        Send(channel, Make($"{OurCallsign} {PartnerCall} R+07"));
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));

        // No CAT wired up (manual-tune operator) — must fall back to the config value unchanged.
        await mockAdif.Received(1).AppendQsoAsync(
            Arg.Is<QsoRecord>(r => r.DialFrequencyMHz == 7.100));

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "D-013: QsoConfirmation=true → qsoReview event also carries the live CAT frequency")]
    public async Task QsoComplete_QsoConfirmationEnabled_ReviewEventCarriesLiveCatFrequency()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.First,
            RetryCount          = 3,
            WatchdogMinutes     = 1,
            QsoConfirmation     = true,
        };
        var appConfig = new AppConfig() with
        {
            DecodeLog = new DecodeLogConfig { DialFrequencyMHz = 7.100 }, // stale: 40m
        };
        var catState = new StubCatState(14.074); // live: 20m
        var mockAdif = Substitute.For<IAdifLogWriter>();
        mockAdif.AppendQsoAsync(Arg.Any<QsoRecord>()).Returns(Task.CompletedTask);

        var (sut, eventBus, _, ptt, channel, stopCts) = BuildIsolatedSut(
            tx, watchdogDuration: TimeSpan.FromSeconds(30), adifLog: mockAdif,
            catState: catState, appConfig: appConfig);

        await sut.StartAsync(stopCts.Token);

        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        Send(channel, Make($"{OurCallsign} {PartnerCall} {PartnerGrid}"));
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(5));

        Send(channel, Make($"{OurCallsign} {PartnerCall} R+07"));
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));

        // The qsoReview event's record must carry the live CAT frequency, not the stale config value.
        eventBus.Received(1).PublishQsoReview(
            Arg.Is<QsoRecord>(r => r.DialFrequencyMHz == 14.074),
            Arg.Any<string>(),
            Arg.Any<string>(),
            Arg.Any<string>());

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── f-004-operator-visibility-improvements: GracefulStopAsync (qso-caller spec) ────────

    [Fact(DisplayName = "f-004: GracefulStopAsync while TxCq does not call KeyUpAsync until the in-progress transmission completes")]
    public async Task GracefulStopAsync_WhileTransmittingCq_DoesNotInterruptThenReturnsToIdle()
    {
        var tx = new TxConfig
        {
            AutoAnswer = true, Callsign = OurCallsign, Grid = OurGrid,
            RetryCount = 3, WatchdogMinutes = 4,
        };

        // Controlled TCS so the "CQ sample" stays in flight until the test releases it —
        // this is the window during which GracefulStopAsync must NOT call KeyUpAsync.
        var keyDownTcs = new TaskCompletionSource();
        var ptt = Substitute.For<IPttController>();
        ptt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(_ => keyDownTcs.Task);
        ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var store = Substitute.For<IConfigStore>();
        store.Current.Returns(new AppConfig() with { Tx = tx });
        store.SaveAsync(Arg.Any<AppConfig>(), Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var eventBus = Substitute.For<ITxEventBus>();
        var channel  = Channel.CreateUnbounded<DecodeBatch>();
        var stopCts  = new CancellationTokenSource();

        var sut = new QsoCallerService(
            channel.Reader, store, ptt, eventBus,
            new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance), new AudioOffsetEventBus(),
            NullLogger<QsoCallerService>.Instance,
            watchdogDurationOverride: TimeSpan.FromSeconds(30));

        await sut.StartAsync(stopCts.Token);

        // Trigger CQ — the service enters TxCq (proxy: TxAnswer) and blocks on KeyDownAsync.
        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.TxAnswer, timeout: TimeSpan.FromSeconds(5));

        // Request a graceful stop while the CQ sample is still "transmitting".
        await sut.GracefulStopAsync();

        // KeyUpAsync must not fire while the sample is still in flight, and the state
        // machine must not jump ahead of the transmission.
        await ptt.DidNotReceive().KeyUpAsync(Arg.Any<CancellationToken>());
        sut.State.Should().Be(QsoState.TxAnswer,
            "the state machine must not transition to Idle until the in-progress TX completes");

        // Let the "sample" finish.
        keyDownTcs.SetResult();

        // The service must proceed through its normal post-TX transition and then, because a
        // graceful stop was requested, go straight to Idle without transmitting again.
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));

        await ptt.Received(1).KeyDownAsync(Arg.Any<CancellationToken>()); // exactly one TX — no retransmission
        // dev-task 2026-07-12-cat-tx-ptt-missing-keyup-after-transmit.md: TransmitAsync's own
        // finally block now calls KeyUpAsync once on every normal-completion TX (the fix under
        // test), and SafeAbortToIdleAsync's unconditional cleanup call fires a second time when
        // the state machine reaches Idle — both are individually safe no-ops on a controller
        // with nothing asserted, so two calls is the correct, expected total here.
        await ptt.Received(2).KeyUpAsync(Arg.Any<CancellationToken>());

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "f-004: GracefulStopAsync while WaitAnswer transitions to Idle without a further batch")]
    public async Task GracefulStopAsync_WhileWaitAnswer_TransitionsToIdlePromptly()
    {
        var tx = new TxConfig
        {
            AutoAnswer = true, Callsign = OurCallsign, Grid = OurGrid,
            RetryCount = 3, WatchdogMinutes = 4,
        };
        var (sut, _, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
        await sut.StartAsync(stopCts.Token);

        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5)); // WaitAnswer proxy

        // No further batch is sent — the wakeup channel (not the decode channel) must be
        // what carries this request to the state machine promptly.
        await sut.GracefulStopAsync();

        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "f-004: GracefulStopAsync while WaitRr73 transitions to Idle without a further batch")]
    public async Task GracefulStopAsync_WhileWaitRr73_TransitionsToIdlePromptly()
    {
        // This is the case the dev-task kickoff specifically flags as easy to forget:
        // WaitRr73 is the state newly added to the wakeup-eligible set for this change.
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.First,
            RetryCount          = 3,
            WatchdogMinutes     = 4,
        };
        var (sut, _, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
        await sut.StartAsync(stopCts.Token);

        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        Send(channel, Make($"{OurCallsign} {PartnerCall} {PartnerGrid}"));
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(5));

        // No further batch is sent — relies entirely on WaitRr73 now being wakeup-eligible.
        await sut.GracefulStopAsync();

        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));
        sut.Partner.Should().BeNull("SafeAbortToIdleAsync clears the partner on return to Idle");

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "f-004: GracefulStopAsync when already Idle is a no-op")]
    public async Task GracefulStopAsync_WhenAlreadyIdle_IsNoOp()
    {
        var tx = new TxConfig { AutoAnswer = false, Callsign = OurCallsign, Grid = OurGrid };
        var (sut, eventBus, _, ptt, _, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
        await sut.StartAsync(stopCts.Token);

        sut.State.Should().Be(QsoState.Idle, "a freshly started, disarmed service starts Idle");

        await sut.GracefulStopAsync();

        // Give the background loop a brief window to (incorrectly) react, then assert nothing did.
        await Task.Delay(100);
        sut.State.Should().Be(QsoState.Idle);
        await ptt.DidNotReceive().KeyUpAsync(Arg.Any<CancellationToken>());
        await ptt.DidNotReceive().KeyDownAsync(Arg.Any<CancellationToken>());

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "f-004: two GracefulStopAsync requests in quick succession are idempotent")]
    public async Task GracefulStopAsync_CalledTwiceInQuickSuccession_ReachesIdleExactlyOnce()
    {
        var tx = new TxConfig
        {
            AutoAnswer = true, Callsign = OurCallsign, Grid = OurGrid,
            RetryCount = 3, WatchdogMinutes = 4,
        };
        var (sut, _, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
        await sut.StartAsync(stopCts.Token);

        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        // Two requests back-to-back — neither call itself may throw, and the service must
        // still land on Idle exactly once (not double-transition, not error).
        var act = async () =>
        {
            await sut.GracefulStopAsync();
            await sut.GracefulStopAsync();
        };
        await act.Should().NotThrowAsync();

        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));

        // Settle briefly and confirm it stays Idle rather than oscillating.
        await Task.Delay(100);
        sut.State.Should().Be(QsoState.Idle);

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── decode-panel-filtering: automation gating (tasks 4.2–4.4) ────────────

    [Fact(DisplayName = "decode-panel-filtering: First mode skips a filtered-out responder in favour of the next one")]
    public async Task WaitAnswer_FirstMode_SkipsFilteredOutResponder()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.First,
            RetryCount          = 3,
            WatchdogMinutes     = 4,
        };
        var filterStore = new MutableDecodeFilterStore();
        var (sut, _, _, ptt, channel, stopCts) =
            BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30), decodeFilterStore: filterStore);
        await sut.StartAsync(stopCts.Token);

        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        // Exclude ThisBand on the Contact axis — Q1TST (ThisBand) is filtered out;
        // Q2ABC (Never, via WorkedBeforeInfo.None) passes.
        filterStore.Set(new DecodeFilterState(
            ContactStates: new HashSet<WorkedBeforeState> { WorkedBeforeState.Never, WorkedBeforeState.DifferentBand }));

        Send(channel,
            MakeResponse(PartnerCall, PartnerGrid, WorkedBeforeState.ThisBand),  // filtered out
            MakeResponse("Q2ABC", "KP20", WorkedBeforeState.Never));             // not filtered out

        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(5));
        sut.Partner.Should().Be("Q2ABC", "the filtered-out responder must be skipped entirely");

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "decode-panel-filtering: First mode — all responses filtered out — cycle treated as empty")]
    public async Task WaitAnswer_FirstMode_AllResponsesFilteredOut_TreatedAsEmptyCycle()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.First,
            RetryCount          = 0, // unlimited — watchdog is the backstop
            WatchdogMinutes     = 4,
        };
        var filterStore = new MutableDecodeFilterStore();
        var (sut, _, _, ptt, channel, stopCts) =
            BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30), decodeFilterStore: filterStore);
        await sut.StartAsync(stopCts.Token);

        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        filterStore.Set(new DecodeFilterState(
            ContactStates: new HashSet<WorkedBeforeState> { WorkedBeforeState.Never, WorkedBeforeState.DifferentBand }));

        Send(channel, MakeResponse(PartnerCall, PartnerGrid, WorkedBeforeState.ThisBand)); // filtered out
        await Task.Delay(300);

        sut.State.Should().Be(QsoState.WaitReport,
            "a cycle where every response is filtered out must behave identically to a cycle with no responses");
        sut.Partner.Should().BeNull();

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "decode-panel-filtering: filter change after engagement does not abort an in-progress QSO")]
    public async Task WaitRr73_FilterChangedAfterEngagement_QsoContinuesUnaffected()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.First,
            RetryCount          = 3,
            WatchdogMinutes     = 4,
        };
        var filterStore = new MutableDecodeFilterStore();
        var (sut, eventBus, _, ptt, channel, stopCts) =
            BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30), decodeFilterStore: filterStore);
        await sut.StartAsync(stopCts.Token);

        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        // Unfiltered at engagement time — the partner is engaged normally.
        Send(channel, MakeResponse(PartnerCall, PartnerGrid, WorkedBeforeState.Never));
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(5));
        sut.Partner.Should().Be(PartnerCall);

        // Now change the filter so the active partner would be filtered out if re-evaluated.
        filterStore.Set(new DecodeFilterState(
            ContactStates: new HashSet<WorkedBeforeState> { WorkedBeforeState.Never, WorkedBeforeState.DifferentBand }));

        // Partner sends a roger report — the QSO must proceed exactly as if the filter had
        // never changed, because the filter is not re-checked once engagement has begun.
        Send(channel, Make($"{OurCallsign} {PartnerCall} R+05"));

        // QsoComplete is transient (entered and exited within the same handler call, same as
        // QsoAnswererService) — by the time polling observes State it has already advanced to
        // Idle, so assert the transient QsoComplete broadcast directly via the event bus to
        // confirm the QSO reached normal completion (not an abort) with the original partner.
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));
        eventBus.Received(1).Publish("QsoComplete", "caller", PartnerCall, true, null);

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "decode-panel-filtering: no IDecodeFilterStore supplied (null) behaves as fully unfiltered")]
    public async Task WaitAnswer_NoFilterStoreSupplied_BehavesAsUnfiltered()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.First,
            RetryCount          = 3,
            WatchdogMinutes     = 4,
        };
        // decodeFilterStore intentionally omitted (null default).
        var (sut, _, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
        await sut.StartAsync(stopCts.Token);

        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        Send(channel, MakeResponse(PartnerCall, PartnerGrid, WorkedBeforeState.ThisBand));

        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(5));
        sut.Partner.Should().Be(PartnerCall,
            "a null IDecodeFilterStore must impose no filtering — no regression for callers not yet updated");

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "decode-panel-filtering: None mode — SelectResponderAsync rejects a filtered-out callsign")]
    public async Task SelectResponderAsync_NoneMode_RejectsFilteredOutCallsign()
    {
        var tx = new TxConfig
        {
            AutoAnswer          = true,
            Callsign            = OurCallsign,
            Grid                = OurGrid,
            CallerPartnerSelect = CallerPartnerSelectMode.None,
            RetryCount          = 3,
            WatchdogMinutes     = 4,
        };
        var filterStore = new MutableDecodeFilterStore();
        var (sut, _, _, ptt, channel, stopCts) =
            BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30), decodeFilterStore: filterStore);
        await sut.StartAsync(stopCts.Token);

        Send(channel, Make("CQ Q2NOISE JO00"));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        // Exclude ThisBand so the upcoming responder decode is filtered out.
        filterStore.Set(new DecodeFilterState(
            ContactStates: new HashSet<WorkedBeforeState> { WorkedBeforeState.Never, WorkedBeforeState.DifferentBand }));

        // Feed the (filtered-out) responder decode so SelectResponderAsync has something to
        // evaluate against — None mode records every recognised responder decode regardless
        // of filter state (highlighting is a frontend concern; this backend gate is separate).
        Send(channel, MakeResponse(PartnerCall, PartnerGrid, WorkedBeforeState.ThisBand));
        await Task.Delay(200); // let HandleWaitAnswerAsync record the decode

        var bPhaseResponse = new DateTimeOffset(2026, 6, 25, 14, 29, 15, TimeSpan.Zero);
        await sut.SelectResponderAsync(PartnerCall, AudioFreqHz, bPhaseResponse, CancellationToken.None);

        // No state transition, no pending responder armed — the call must have been rejected.
        await Task.Delay(200);
        sut.State.Should().Be(QsoState.WaitReport,
            "SelectResponderAsync naming a filtered-out callsign must be rejected outright");
        sut.Partner.Should().BeNull();

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }
}
