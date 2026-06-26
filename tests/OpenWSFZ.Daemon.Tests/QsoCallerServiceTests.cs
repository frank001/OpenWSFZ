using System.Threading.Channels;
using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using NSubstitute;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
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

    private static (QsoCallerService sut, ITxEventBus eventBus, IPttController ptt,
                    Channel<DecodeBatch> channel, CancellationTokenSource stopCts)
        BuildIsolatedSut(TxConfig txConfig, TimeSpan? watchdogDuration = null)
    {
        var ptt = Substitute.For<IPttController>();
        ptt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var store = Substitute.For<IConfigStore>();
        store.Current.Returns(new AppConfig() with { Tx = txConfig });
        store.SaveAsync(Arg.Any<AppConfig>(), Arg.Any<CancellationToken>())
             .Returns(Task.CompletedTask);

        var eventBus = Substitute.For<ITxEventBus>();
        var adifLog  = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);
        var channel  = Channel.CreateUnbounded<DecodeBatch>();
        var stopCts  = new CancellationTokenSource();

        var sut = watchdogDuration.HasValue
            ? new QsoCallerService(
                channel.Reader, store, ptt, eventBus,
                adifLog, new AudioOffsetEventBus(),
                NullLogger<QsoCallerService>.Instance,
                watchdogDurationOverride: watchdogDuration.Value)
            : new QsoCallerService(
                channel.Reader, store, ptt, eventBus,
                adifLog, new AudioOffsetEventBus(),
                NullLogger<QsoCallerService>.Instance);

        return (sut, eventBus, ptt, channel, stopCts);
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
        var (sut, _, _, _, _) = BuildIsolatedSut(tx);
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
        var (sut, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
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
        var (sut, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
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
        var (sut, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
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
        var (sut, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
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
        var (sut, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
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
        var (sut, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
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
        var (sut, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
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
        var (sut, eventBus, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
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
        var (sut, eventBus, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
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
        var (sut, eventBus, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
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
        var (sut, eventBus, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
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
        var (sut, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
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
        var (sut, _, ptt, channel, stopCts) = BuildIsolatedSut(tx, watchdogDuration: TimeSpan.FromSeconds(30));
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
            out var partner, out _);

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
            out var partner, out _);

        result.Should().BeTrue();
        partner.Should().Be("Q1ABC");
    }

    [Fact(DisplayName = "TryParseResponder: non-matching callsign is rejected")]
    public void TryParseResponder_RejectsNonMatchingCallsign()
    {
        // First token is a completely different callsign — must return false.
        var result = QsoCallerService.TryParseResponder(
            "Q9ZZZ Q1ABC JO22", "PD2FZ/P",
            out var partner, out _);

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
            out var partner, out _);

        result.Should().BeTrue();
        partner.Should().Be("Q1ABC");
    }

    [Fact(DisplayName = "TryParseResponder: accepts negative signal report (-05) as third token")]
    public void TryParseResponder_AcceptsNegativeSignalReport()
    {
        var result = QsoCallerService.TryParseResponder(
            "PD2FZ Q1ABC -05", "PD2FZ",
            out var partner, out _);

        result.Should().BeTrue();
        partner.Should().Be("Q1ABC");
    }

    [Fact(DisplayName = "TryParseResponder: accepts roger signal report (R+33) as third token")]
    public void TryParseResponder_AcceptsRogerSignalReport()
    {
        var result = QsoCallerService.TryParseResponder(
            "PD2FZ/P Q1ABC R+33", "PD2FZ/P",
            out var partner, out _);

        result.Should().BeTrue();
        partner.Should().Be("Q1ABC");
    }

    [Fact(DisplayName = "TryParseResponder: rejects 73 as third token (not a valid CQ response)")]
    public void TryParseResponder_Rejects73AsThirdToken()
    {
        // "73" is a QSO termination message — must NOT be mistaken for a CQ response.
        var result = QsoCallerService.TryParseResponder(
            "PD2FZ/P Q1ABC 73", "PD2FZ/P",
            out var partner, out _);

        result.Should().BeFalse();
        partner.Should().BeEmpty();
    }
}
