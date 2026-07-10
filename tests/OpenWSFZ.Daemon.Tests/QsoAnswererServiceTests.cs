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
/// Unit tests for <see cref="QsoAnswererService"/> (tasks 6.1–6.15).
///
/// All tests inject decode batches via a <see cref="Channel{T}"/> and observe
/// state transitions via the <see cref="QsoAnswererService.State"/> and
/// <see cref="QsoAnswererService.Partner"/> properties.  The <see cref="IPttController"/>
/// is mocked so no audio hardware is required.
///
/// NFR-021: all callsigns use ITU-unallocated Q-prefix (Q1OFZ = ours, Q1TST = partner).
/// </summary>
[Trait("Category", "Unit")]
public sealed class QsoAnswererServiceTests : IAsyncLifetime
{
    private const string OurCallsign  = "Q1OFZ";
    private const string OurGrid      = "JO33";
    private const string PartnerCall  = "Q1TST";
    private const string PartnerGrid  = "JO22";
    private const int    AudioFreqHz  = 897;

    // ── Helpers ───────────────────────────────────────────────────────────────

    private readonly Channel<DecodeBatch> _channel =
        Channel.CreateUnbounded<DecodeBatch>();

    private readonly IPttController _ptt = Substitute.For<IPttController>();

    private QsoAnswererService?      _sut;
    private CancellationTokenSource? _stopCts;

    public async Task InitializeAsync()
    {
        _ptt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        _ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var store   = Substitute.For<IConfigStore>();
        store.Current.Returns(new AppConfig() with
        {
            Tx = new TxConfig
            {
                AutoAnswer      = true,          // enabled for all TX-exercising tests
                Callsign        = OurCallsign,
                Grid            = OurGrid,
                RetryCount      = 2,
                WatchdogMinutes = 4,
            }
        });

        var adifLog = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);
        // D-CALLER-013: inject a FakeTimeProvider at the start of an A-phase window
        // (second = 0 → 0 s into the window ≤ MaxLateStartSeconds = 1.5 s) so the
        // late-start guard always passes for the shared SUT.
        // Tests that determine phase from the real clock (D-TX-UI-007 wakeup tests)
        // use DateTimeOffset.UtcNow directly inside AnswerCqAsync — they are not
        // affected by this override.
        var earlyInWindow = new FakeTimeProvider(
            new DateTimeOffset(2026, 1, 1, 0, 0, 0, TimeSpan.Zero)); // :00 = A-phase, 0 s in
        _sut    = new QsoAnswererService(_channel.Reader, store, _ptt, new TxEventBus(),
                      adifLog, new AudioOffsetEventBus(), NullLogger<QsoAnswererService>.Instance,
                      watchdogDurationOverride: TimeSpan.FromMinutes(4),
                      timeProvider: earlyInWindow);
        _stopCts = new CancellationTokenSource();

        // Start the service background loop.
        await _sut.StartAsync(_stopCts.Token);
    }

    public async Task DisposeAsync()
    {
        if (_stopCts is not null)
        {
            await _stopCts.CancelAsync();
            _stopCts.Dispose();
        }
        if (_sut is not null)
            await _sut.StopAsync(CancellationToken.None);

        await _ptt.DisposeAsync();
    }

    private static DecodeResult Make(string msg, int freqHz = AudioFreqHz)
        => new(Time: "12:00:00", Snr: -5, Dt: 0.1, FreqHz: freqHz, Message: msg);

    /// <summary>
    /// Write a batch to the shared channel with an arbitrary UtcNow timestamp.
    /// Use the timestamp overload for phase-sensitive tests.
    /// </summary>
    private void Send(params DecodeResult[] results)
        => _channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow, results));

    /// <summary>
    /// Write a batch with an explicit cycle-start timestamp (for phase-sensitive tests).
    /// </summary>
    private void Send(DateTimeOffset cycleStart, params DecodeResult[] results)
        => _channel.Writer.TryWrite(new DecodeBatch(cycleStart, results));

    private static async Task WaitForStateAsync(
        QsoAnswererService svc, QsoState expected,
        TimeSpan? timeout = null)
    {
        var deadline = DateTime.UtcNow + (timeout ?? TimeSpan.FromSeconds(3));
        while (DateTime.UtcNow < deadline)
        {
            if (svc.State == expected) return;
            await Task.Delay(10);
        }
        throw new TimeoutException(
            $"Expected state {expected} but was {svc!.State} after {(timeout ?? TimeSpan.FromSeconds(3)).TotalSeconds:F1} s.");
    }

    // ── Task 6.2: initial state ───────────────────────────────────────────────

    [Fact(DisplayName = "FR-050: QsoAnswererService starts in Idle state with null partner")]
    public void InitialState_IsIdleWithNullPartner()
    {
        _sut!.State.Should().Be(QsoState.Idle);
        _sut!.Partner.Should().BeNull();
    }

    // ── AutoAnswer guard ─────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-050: CQ is ignored and no TX occurs when AutoAnswer is false")]
    public async Task Idle_AutoAnswerDisabled_CqIgnored()
    {
        // Build a separate service instance with AutoAnswer = false.
        var disabledStore = Substitute.For<IConfigStore>();
        disabledStore.Current.Returns(new AppConfig() with
        {
            Tx = new TxConfig
            {
                AutoAnswer      = false,          // ← the point of this test
                Callsign        = OurCallsign,
                Grid            = OurGrid,
                RetryCount      = 2,
                WatchdogMinutes = 4,
            }
        });

        var pttDisabled  = Substitute.For<IPttController>();
        pttDisabled.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        pttDisabled.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var channel  = Channel.CreateUnbounded<DecodeBatch>();
        var adifLog  = new AdifLogWriter(disabledStore, NullLogger<AdifLogWriter>.Instance);
        var sut      = new QsoAnswererService(channel.Reader, disabledStore, pttDisabled,
                           new TxEventBus(), adifLog, new AudioOffsetEventBus(),
                           NullLogger<QsoAnswererService>.Instance);

        using var stopCts = new CancellationTokenSource();
        await sut.StartAsync(stopCts.Token);

        // Send a CQ — must be completely ignored.
        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow, [Make($"CQ {PartnerCall} {PartnerGrid}")]));
        await Task.Delay(300);

        sut.State.Should().Be(QsoState.Idle,
            "AutoAnswer=false must suppress all CQ responses");
        await pttDisabled.DidNotReceive().KeyDownAsync(Arg.Any<CancellationToken>());

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await pttDisabled.DisposeAsync();
    }

    [Fact(DisplayName = "FR-050: CQ is ignored when AutoAnswer=true but callsign/grid are empty (crash guard)")]
    public async Task Idle_EmptyCallsignOrGrid_CqIgnored()
    {
        // Reproduces the live crash: AutoAnswer enabled but callsign/grid not configured.
        var unconfiguredStore = Substitute.For<IConfigStore>();
        unconfiguredStore.Current.Returns(new AppConfig() with
        {
            Tx = new TxConfig
            {
                AutoAnswer      = true,
                Callsign        = "",          // ← unconfigured (would produce malformed FT8 message)
                Grid            = "",          // ← unconfigured
                RetryCount      = 2,
                WatchdogMinutes = 4,
            }
        });

        var pttEmpty = Substitute.For<IPttController>();
        pttEmpty.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        pttEmpty.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var channel = Channel.CreateUnbounded<DecodeBatch>();
        var adifLog = new AdifLogWriter(unconfiguredStore, NullLogger<AdifLogWriter>.Instance);
        var sut     = new QsoAnswererService(channel.Reader, unconfiguredStore, pttEmpty,
                          new TxEventBus(), adifLog, new AudioOffsetEventBus(),
                          NullLogger<QsoAnswererService>.Instance);

        using var stopCts = new CancellationTokenSource();
        await sut.StartAsync(stopCts.Token);

        // A CQ arrives — must be suppressed because callsign/grid are empty.
        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow, [Make($"CQ {PartnerCall} {PartnerGrid}")]));
        await Task.Delay(300);

        sut.State.Should().Be(QsoState.Idle,
            "empty callsign/grid must suppress TX even when auto-answer is enabled");
        await pttEmpty.DidNotReceive().KeyDownAsync(Arg.Any<CancellationToken>());

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await pttEmpty.DisposeAsync();
    }

    // ── f-003-ap-assist-nonstandard-callsigns: H6 AP arming for nonstandard callsigns ────────

    [Fact(DisplayName = "f-003 4.3: AP constraints arm (not disabled) when the CQ caller has a nonstandard callsign")]
    public async Task WaitReport_NonstandardPartnerCallsign_ArmsApConstraintsInsteadOfDisabling()
    {
        const string nonstandardPartner = "PJ4/K1ABC"; // 9-char compound callsign (f-001/f-003 Gap B)

        var store = Substitute.For<IConfigStore>();
        store.Current.Returns(new AppConfig() with
        {
            Tx = new TxConfig
            {
                AutoAnswer      = true,
                Callsign        = OurCallsign,
                Grid            = OurGrid,
                RetryCount      = 2,
                WatchdogMinutes = 4,
            }
        });

        var ptt = Substitute.For<IPttController>();
        ptt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var decoder = Substitute.For<IApConstraintSink>();
        var channel = Channel.CreateUnbounded<DecodeBatch>();
        var adifLog = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);
        var sut     = new QsoAnswererService(channel.Reader, store, ptt,
                          new TxEventBus(), adifLog, new AudioOffsetEventBus(),
                          NullLogger<QsoAnswererService>.Instance, decoder: decoder);

        using var stopCts = new CancellationTokenSource();
        await sut.StartAsync(stopCts.Token);

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [Make($"CQ {nonstandardPartner} {PartnerGrid}")]));

        await WaitForStateAsync(sut, QsoState.WaitReport);
        sut.Partner.Should().Be(nonstandardPartner);

        // NOTE: this calls Ft8CallsignPacker.Pack28 — the very function under test in
        // Ft8CallsignPackerTests.cs — so these are not "independently derived" expected
        // values. This integration test verifies a different concern: that
        // QsoAnswererService.ApplyApConstraints() arms AP with whatever Pack28 produces
        // (rather than disabling AP) when the partner's callsign is nonstandard, and
        // passes the packer's own output through unmodified. Pack28's byte-level
        // correctness is covered independently by Ft8CallsignPackerTests.cs.
        byte[] expectedMycallBits   = Ft8CallsignPacker.Pack28(OurCallsign);
        byte[] expectedHiscallBits  = Ft8CallsignPacker.Pack28(nonstandardPartner);
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

    // ── Task 6.4: CQ detection ────────────────────────────────────────────────

    [Fact(DisplayName = "6.4: CQ in Idle triggers TxAnswer then WaitReport")]
    public async Task Idle_CqReceived_AdvancesToWaitReport()
    {
        Send(Make($"CQ {PartnerCall} {PartnerGrid}"));

        await WaitForStateAsync(_sut!, QsoState.WaitReport);
        _sut!.Partner.Should().Be(PartnerCall,
            "partner should be set to the CQ caller callsign");

        // Verify PTT was used once (for TxAnswer transmission).
        await _ptt.Received(1).KeyDownAsync(Arg.Any<CancellationToken>());
    }

    [Fact(DisplayName = "6.4: Multiple CQs in same batch — first selected")]
    public async Task Idle_MultipleCqs_FirstSelected()
    {
        var other = "Q2ABC";
        Send(Make($"CQ {PartnerCall} {PartnerGrid}"),
             Make($"CQ {other} KP20", freqHz: 1100));

        await WaitForStateAsync(_sut!, QsoState.WaitReport);
        _sut!.Partner.Should().Be(PartnerCall,
            "only the first CQ in the batch should be answered");
        await _ptt.Received(1).KeyDownAsync(Arg.Any<CancellationToken>());
    }

    [Fact(DisplayName = "6.4: Non-CQ decode in Idle does not trigger TX")]
    public async Task Idle_NonCqMessage_StaysIdle()
    {
        Send(Make($"Q2ABC {PartnerCall} +05")); // not a CQ
        await Task.Delay(200);

        _sut!.State.Should().Be(QsoState.Idle,
            "a non-CQ message must not trigger any transmission");
        await _ptt.DidNotReceive().KeyDownAsync(Arg.Any<CancellationToken>());
    }

    // ── Task 6.6: WaitReport ──────────────────────────────────────────────────

    [Fact(DisplayName = "6.6: Signal report from partner → TxReport → WaitRr73")]
    public async Task WaitReport_SignalReport_AdvancesToWaitRr73()
    {
        // Reach WaitReport.
        Send(Make($"CQ {PartnerCall} {PartnerGrid}"));
        await WaitForStateAsync(_sut!, QsoState.WaitReport);

        // Partner sends report to us.
        Send(Make($"{OurCallsign} {PartnerCall} +05"));
        await WaitForStateAsync(_sut!, QsoState.WaitRr73);

        // Two TX calls: TxAnswer + TxReport.
        await _ptt.Received(2).KeyDownAsync(Arg.Any<CancellationToken>());
    }

    [Fact(DisplayName = "6.6: Early RR73 in WaitReport skips directly to QsoComplete/Idle")]
    public async Task WaitReport_EarlyRr73_SkipsToIdle()
    {
        // Reach WaitReport.
        Send(Make($"CQ {PartnerCall} {PartnerGrid}"));
        await WaitForStateAsync(_sut!, QsoState.WaitReport);

        // Partner sends RR73 early (skipping report exchange).
        Send(Make($"{OurCallsign} {PartnerCall} RR73"));
        await WaitForStateAsync(_sut!, QsoState.Idle);

        // Three TX calls: TxAnswer + Tx73 (TxReport skipped), then Idle.
        await _ptt.Received(2).KeyDownAsync(Arg.Any<CancellationToken>());
    }

    [Fact(DisplayName = "6.6: Early RRR in WaitReport is also accepted")]
    public async Task WaitReport_EarlyRrr_SkipsToIdle()
    {
        Send(Make($"CQ {PartnerCall} {PartnerGrid}"));
        await WaitForStateAsync(_sut!, QsoState.WaitReport);

        Send(Make($"{OurCallsign} {PartnerCall} RRR"));
        await WaitForStateAsync(_sut!, QsoState.Idle);

        await _ptt.Received(2).KeyDownAsync(Arg.Any<CancellationToken>());
    }

    [Fact(DisplayName = "6.6: Partner working another station in WaitReport → abort to Idle")]
    public async Task WaitReport_PartnerWorksOther_AbortsToIdle()
    {
        Send(Make($"CQ {PartnerCall} {PartnerGrid}"));
        await WaitForStateAsync(_sut!, QsoState.WaitReport);

        // Partner sends to a third station.
        Send(Make($"Q2OTHER {PartnerCall} +03"));
        await WaitForStateAsync(_sut!, QsoState.Idle,
            timeout: TimeSpan.FromSeconds(3));
    }

    [Fact(DisplayName = "6.6: No matching decode in WaitReport → retry; after max retries → Idle")]
    public async Task WaitReport_NoResponse_RetriesThenAborts()
    {
        // tx.RetryCount = 2 (set in InitializeAsync).
        Send(Make($"CQ {PartnerCall} {PartnerGrid}"));
        await WaitForStateAsync(_sut!, QsoState.WaitReport);

        // A-01: _skipNextRetry is re-armed after every TX (including retries), so each
        // retry TX is followed by one skipped cycle before the next retry can fire.
        // Pattern: [skip] [retry1] [skip] [retry2] [skip] [abort]  — 6 cycles total.
        Send(Make("CQ Q2NOISE IO91")); // cycle 1: skip — initial TX window
        await Task.Delay(150);
        Send(Make("CQ Q2NOISE IO91")); // cycle 2: retry 1 TX
        await Task.Delay(150);
        Send(Make("CQ Q2NOISE IO91")); // cycle 3: skip — retry 1 TX window
        await Task.Delay(150);
        Send(Make("CQ Q2NOISE IO91")); // cycle 4: retry 2 TX
        await Task.Delay(150);
        Send(Make("CQ Q2NOISE IO91")); // cycle 5: skip — retry 2 TX window
        await Task.Delay(150);
        Send(Make("CQ Q2NOISE IO91")); // cycle 6: retry count exhausted → abort
        await WaitForStateAsync(_sut!, QsoState.Idle,
            timeout: TimeSpan.FromSeconds(5));
    }

    // ── A-01 skip-first-cycle guard tests (tasks 2.1–2.5) ─────────────────────

    [Fact(DisplayName = "A-01 2.1: WaitReport — first empty cycle is skipped (no retry, counter = 0)")]
    public async Task WaitReport_FirstEmptyCycle_IsSkipped()
    {
        // Reach WaitReport.
        Send(Make($"CQ {PartnerCall} {PartnerGrid}"));
        await WaitForStateAsync(_sut!, QsoState.WaitReport);

        // One irrelevant batch — silence guard fires because we were just transmitting.
        Send(Make("CQ Q2NOISE IO91"));
        await Task.Delay(200);

        // State stays WaitReport; only 1 TX (TxAnswer) — no retry fired.
        _sut!.State.Should().Be(QsoState.WaitReport,
            "the first empty cycle must be skipped by the A-01 guard");
        await _ptt.Received(1).KeyDownAsync(Arg.Any<CancellationToken>());
    }

    [Fact(DisplayName = "A-01 2.2: WaitReport — second consecutive empty cycle triggers retry (counter = 1)")]
    public async Task WaitReport_SecondEmptyCycle_FiresRetry()
    {
        // Reach WaitReport.
        Send(Make($"CQ {PartnerCall} {PartnerGrid}"));
        await WaitForStateAsync(_sut!, QsoState.WaitReport);

        // First cycle: skipped by the A-01 guard.
        Send(Make("CQ Q2NOISE IO91"));
        await Task.Delay(150);

        // Second cycle: retry must fire.
        Send(Make("CQ Q2NOISE IO91"));
        await Task.Delay(300); // allow retry TX to complete

        // TxAnswer (1) + retry TX (1) = 2 total.
        await _ptt.Received(2).KeyDownAsync(Arg.Any<CancellationToken>());
        _sut!.State.Should().Be(QsoState.WaitReport, "one retry should not exhaust the retry budget");
    }

    [Fact(DisplayName = "A-01 2.3: WaitRr73 — first empty cycle is skipped (no retry)")]
    public async Task WaitRr73_FirstEmptyCycle_IsSkipped()
    {
        // Full path to WaitRr73.
        Send(Make($"CQ {PartnerCall} {PartnerGrid}"));
        await WaitForStateAsync(_sut!, QsoState.WaitReport);

        Send(Make($"{OurCallsign} {PartnerCall} +05"));
        await WaitForStateAsync(_sut!, QsoState.WaitRr73);

        // One irrelevant batch in WaitRr73.
        Send(Make("CQ Q2NOISE IO91"));
        await Task.Delay(200);

        // State stays WaitRr73; only 2 TX so far (TxAnswer + TxReport) — no retry fired.
        _sut!.State.Should().Be(QsoState.WaitRr73,
            "the first empty cycle in WaitRr73 must be skipped by the A-01 guard");
        await _ptt.Received(2).KeyDownAsync(Arg.Any<CancellationToken>());
    }

    [Fact(DisplayName = "A-01 2.4: WaitRr73 — second consecutive empty cycle triggers retry")]
    public async Task WaitRr73_SecondEmptyCycle_FiresRetry()
    {
        // Full path to WaitRr73.
        Send(Make($"CQ {PartnerCall} {PartnerGrid}"));
        await WaitForStateAsync(_sut!, QsoState.WaitReport);

        Send(Make($"{OurCallsign} {PartnerCall} +05"));
        await WaitForStateAsync(_sut!, QsoState.WaitRr73);

        // First cycle: skipped.
        Send(Make("CQ Q2NOISE IO91"));
        await Task.Delay(150);

        // Second cycle: retry must fire.
        Send(Make("CQ Q2NOISE IO91"));
        await Task.Delay(300); // allow retry TX to complete

        // TxAnswer (1) + TxReport (1) + retry TX (1) = 3 total.
        await _ptt.Received(3).KeyDownAsync(Arg.Any<CancellationToken>());
        _sut!.State.Should().Be(QsoState.WaitRr73, "one retry should not exhaust the retry budget");
    }

    [Fact(DisplayName = "A-01 2.6: WaitReport — silence cycle after retry TX is skipped; fourth cycle triggers second retry")]
    public async Task WaitReport_SilenceAfterRetry_IsSkipped()
    {
        // Reach WaitReport.
        Send(Make($"CQ {PartnerCall} {PartnerGrid}"));
        await WaitForStateAsync(_sut!, QsoState.WaitReport);

        // Cycle 1: skipped by A-01 guard (our initial TX window).
        Send(Make("CQ Q2NOISE IO91"));
        await Task.Delay(150);

        // Cycle 2: retry TX fires (2 KeyDownAsync total so far).
        Send(Make("CQ Q2NOISE IO91"));
        await Task.Delay(300); // allow retry TX to complete

        // Cycle 3: our retry TX window — must be SKIPPED, not another retry.
        Send(Make("CQ Q2NOISE IO91"));
        await Task.Delay(200);

        // Still only 2 KeyDownAsync (TxAnswer + first retry); no second retry yet.
        await _ptt.Received(2).KeyDownAsync(Arg.Any<CancellationToken>());
        _sut!.State.Should().Be(QsoState.WaitReport,
            "the silence cycle immediately after a retry TX must be skipped, not counted as a miss");

        // Cycle 4: second retry must now fire.
        Send(Make("CQ Q2NOISE IO91"));
        await Task.Delay(300);

        await _ptt.Received(3).KeyDownAsync(Arg.Any<CancellationToken>());
    }

    [Fact(DisplayName = "A-01 2.7: WaitRr73 — silence cycle after retry TX is skipped; fourth cycle triggers second retry")]
    public async Task WaitRr73_SilenceAfterRetry_IsSkipped()
    {
        // Full path to WaitRr73.
        Send(Make($"CQ {PartnerCall} {PartnerGrid}"));
        await WaitForStateAsync(_sut!, QsoState.WaitReport);

        Send(Make($"{OurCallsign} {PartnerCall} +05"));
        await WaitForStateAsync(_sut!, QsoState.WaitRr73);

        // Cycle 1: skipped by A-01 guard (our TxReport window).
        Send(Make("CQ Q2NOISE IO91"));
        await Task.Delay(150);

        // Cycle 2: retry TX fires (3 KeyDownAsync: TxAnswer + TxReport + retry).
        Send(Make("CQ Q2NOISE IO91"));
        await Task.Delay(300);

        // Cycle 3: our retry TX window — must be SKIPPED.
        Send(Make("CQ Q2NOISE IO91"));
        await Task.Delay(200);

        await _ptt.Received(3).KeyDownAsync(Arg.Any<CancellationToken>());
        _sut!.State.Should().Be(QsoState.WaitRr73,
            "the silence cycle immediately after a retry TX in WaitRr73 must be skipped");

        // Cycle 4: second retry fires.
        Send(Make("CQ Q2NOISE IO91"));
        await Task.Delay(300);

        await _ptt.Received(4).KeyDownAsync(Arg.Any<CancellationToken>());
    }

    [Fact(DisplayName = "A-01 2.5: WaitReport — matching response in first cycle advances state; no retry; flag cleared")]
    public async Task WaitReport_MatchingResponseInFirstCycle_AdvancesNormally()
    {
        // Reach WaitReport (_skipNextRetry = true at this point).
        Send(Make($"CQ {PartnerCall} {PartnerGrid}"));
        await WaitForStateAsync(_sut!, QsoState.WaitReport);

        // First cycle contains the partner's signal report — must clear the guard and advance.
        Send(Make($"{OurCallsign} {PartnerCall} +05"));
        await WaitForStateAsync(_sut!, QsoState.WaitRr73);

        // TxAnswer + TxReport = 2 TX (no spurious retry TX).
        await _ptt.Received(2).KeyDownAsync(Arg.Any<CancellationToken>());
        _sut!.State.Should().Be(QsoState.WaitRr73,
            "a matching response in the first cycle must advance the state machine normally");
    }

    [Fact(DisplayName = "6.6: Message addressed to wrong callsign in WaitReport is ignored")]
    public async Task WaitReport_WrongDest_IsIgnored()
    {
        Send(Make($"CQ {PartnerCall} {PartnerGrid}"));
        await WaitForStateAsync(_sut!, QsoState.WaitReport);

        // A third-party exchange that doesn't involve us or our partner.
        // Neither dest nor src matches Q1OFZ or Q1TST — state machine must ignore it.
        Send(Make($"Q2WRONG Q3OTHER +05"));
        await Task.Delay(200);

        _sut!.State.Should().Be(QsoState.WaitReport,
            "a third-party message with no relation to this QSO must be ignored");
    }

    // ── Task 6.8: WaitRr73 ────────────────────────────────────────────────────

    [Fact(DisplayName = "6.8: RR73 in WaitRr73 → Tx73 → Idle (full exchange)")]
    public async Task WaitRr73_Rr73Received_CompletesQso()
    {
        // Full exchange: CQ → answer → report → roger → RR73 → 73 → Idle.
        Send(Make($"CQ {PartnerCall} {PartnerGrid}"));
        await WaitForStateAsync(_sut!, QsoState.WaitReport);

        Send(Make($"{OurCallsign} {PartnerCall} +05"));
        await WaitForStateAsync(_sut!, QsoState.WaitRr73);

        Send(Make($"{OurCallsign} {PartnerCall} RR73"));
        await WaitForStateAsync(_sut!, QsoState.Idle);

        // Three TX calls: TxAnswer + TxReport + Tx73.
        await _ptt.Received(3).KeyDownAsync(Arg.Any<CancellationToken>());
    }

    [Fact(DisplayName = "6.8: RRR accepted as equivalent to RR73 in WaitRr73")]
    public async Task WaitRr73_RrrAccepted()
    {
        Send(Make($"CQ {PartnerCall} {PartnerGrid}"));
        await WaitForStateAsync(_sut!, QsoState.WaitReport);

        Send(Make($"{OurCallsign} {PartnerCall} +05"));
        await WaitForStateAsync(_sut!, QsoState.WaitRr73);

        Send(Make($"{OurCallsign} {PartnerCall} RRR"));
        await WaitForStateAsync(_sut!, QsoState.Idle);

        await _ptt.Received(3).KeyDownAsync(Arg.Any<CancellationToken>());
    }

    // ── Task 8.5 / 4.1: HoldTxFreq=false → TX at caller's freq; TxAudioOffsetHz updated ──

    [Fact(DisplayName = "Task 8.5: QsoAnswererService with holdTxFreq=false answers CQ at caller's freqHz and updates TxAudioOffsetHz")]
    public async Task Idle_HoldTxFreqFalse_UpdatesTxAudioOffsetHz()
    {
        const int cqFreqHz = 1234;

        var store = Substitute.For<IConfigStore>();
        store.Current.Returns(new AppConfig() with
        {
            Tx = new TxConfig
            {
                AutoAnswer      = true,
                Callsign        = OurCallsign,
                Grid            = OurGrid,
                RetryCount      = 2,
                WatchdogMinutes = 4,
                HoldTxFreq      = false,   // ← the default; answerer must auto-update cursor
                TxAudioOffsetHz = 1500,
                RxAudioOffsetHz = 1500,
            }
        });

        // SaveAsync must return Task.CompletedTask so the async service path doesn't throw.
        store.SaveAsync(Arg.Any<AppConfig>(), Arg.Any<CancellationToken>())
             .Returns(Task.CompletedTask);

        var ptt = Substitute.For<IPttController>();
        ptt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var channel = Channel.CreateUnbounded<DecodeBatch>();
        var adifLog = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);
        var sut     = new QsoAnswererService(
            channel.Reader, store, ptt, new TxEventBus(),
            adifLog, new AudioOffsetEventBus(),
            NullLogger<QsoAnswererService>.Instance);

        using var stopCts = new CancellationTokenSource();
        await sut.StartAsync(stopCts.Token);

        // CQ from partner at cqFreqHz.
        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", -5, 0.1, cqFreqHz, $"CQ {PartnerCall} {PartnerGrid}")]));

        // Wait until the service has answered and entered WaitReport.
        await WaitForStateAsync(sut, QsoState.WaitReport);

        // Assert: SaveAsync was called with TxAudioOffsetHz equal to the caller's freqHz.
        await store.Received(1).SaveAsync(
            Arg.Is<AppConfig>(c => c.Tx != null && c.Tx.TxAudioOffsetHz == cqFreqHz),
            Arg.Any<CancellationToken>());

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── Task 8.6 / 4.2: HoldTxFreq=true → TX at operator freq; config not modified ──

    [Fact(DisplayName = "Task 8.6: QsoAnswererService with holdTxFreq=true uses TxAudioOffsetHz from config and does not modify it")]
    public async Task Idle_HoldTxFreqTrue_UsesTxAudioOffsetHzFromConfig()
    {
        const int cqFreqHz      = 897;
        const int operatorFreqHz = 1500;

        var store = Substitute.For<IConfigStore>();
        store.Current.Returns(new AppConfig() with
        {
            Tx = new TxConfig
            {
                AutoAnswer      = true,
                Callsign        = OurCallsign,
                Grid            = OurGrid,
                RetryCount      = 2,
                WatchdogMinutes = 4,
                HoldTxFreq      = true,             // ← locked to operator-set frequency
                TxAudioOffsetHz = operatorFreqHz,   // operator set 1500 Hz
                RxAudioOffsetHz = 1500,
            }
        });

        store.SaveAsync(Arg.Any<AppConfig>(), Arg.Any<CancellationToken>())
             .Returns(Task.CompletedTask);

        var ptt = Substitute.For<IPttController>();
        ptt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var channel = Channel.CreateUnbounded<DecodeBatch>();
        var adifLog = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);
        var sut     = new QsoAnswererService(
            channel.Reader, store, ptt, new TxEventBus(),
            adifLog, new AudioOffsetEventBus(),
            NullLogger<QsoAnswererService>.Instance);

        using var stopCts = new CancellationTokenSource();
        await sut.StartAsync(stopCts.Token);

        // CQ from partner at cqFreqHz (which differs from operatorFreqHz).
        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", -5, 0.1, cqFreqHz, $"CQ {PartnerCall} {PartnerGrid}")]));

        await WaitForStateAsync(sut, QsoState.WaitReport);

        // Assert: SaveAsync was NOT called with a modified TxAudioOffsetHz.
        // When HoldTxFreq=true the cursor must stay at the operator-set position.
        await store.DidNotReceive().SaveAsync(
            Arg.Is<AppConfig>(c => c.Tx != null && c.Tx.TxAudioOffsetHz != operatorFreqHz),
            Arg.Any<CancellationToken>());

        // Also confirm PTT was used (the service did transmit — at the operator freq).
        await ptt.Received(1).KeyDownAsync(Arg.Any<CancellationToken>());

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── Task 6.12: AbortAsync ─────────────────────────────────────────────────

    [Fact(DisplayName = "6.12: AbortAsync in Idle is a no-op")]
    public async Task AbortAsync_WhenIdle_IsNoOp()
    {
        _sut!.State.Should().Be(QsoState.Idle);
        await _sut.AbortAsync();
        _sut!.State.Should().Be(QsoState.Idle);
        await _ptt.DidNotReceive().KeyUpAsync(Arg.Any<CancellationToken>());
    }

    // ── Task 6.4 — Static parser tests ───────────────────────────────────────

    [Theory(DisplayName = "TryParseCq: recognises valid CQ messages")]
    [InlineData("CQ Q1TST JO22",  "Q1TST", "JO22")]
    [InlineData("CQ Q1TST",       "Q1TST", null)]
    [InlineData("cq q1tst jo22",  "q1tst", "jo22")]
    public void TryParseCq_ValidCq_ReturnsTrue(string msg, string expCall, string? expGrid)
    {
        bool result = QsoAnswererService.TryParseCq(msg, out var callsign, out var grid);

        result.Should().BeTrue();
        callsign.Should().Be(expCall);
        grid.Should().Be(expGrid);
    }

    [Theory(DisplayName = "TryParseCq: rejects non-CQ messages")]
    [InlineData("Q1OFZ Q1TST +05")]
    [InlineData("Q1OFZ Q1TST RR73")]
    [InlineData("")]
    public void TryParseCq_NonCq_ReturnsFalse(string msg)
    {
        QsoAnswererService.TryParseCq(msg, out _, out _).Should().BeFalse();
    }

    [Theory(DisplayName = "IsSignalReport: recognises FT8 signal report payloads")]
    [InlineData("+05",  true)]
    [InlineData("-12",  true)]
    [InlineData("R+00", true)]
    [InlineData("R-05", true)]
    [InlineData("RR73", false)]
    [InlineData("73",   false)]
    [InlineData("JO33", false)]
    public void IsSignalReport_VariousPayloads_CorrectResult(string payload, bool expected)
    {
        QsoAnswererService.IsSignalReport(payload).Should().Be(expected);
    }

    // ── D-007: abort during TX must not advance state or write ADIF ───────────

    [Fact(DisplayName = "D-007: AbortAsync during TX stops state machine at Idle; no ADIF written")]
    public async Task Abort_DuringTx_ResolvesToIdleWithoutAdif()
    {
        // Arrange: PTT that blocks KeyDownAsync until the token is cancelled, then
        // returns *normally* (no throw) — simulating the race where KeyUp stops audio
        // (cancels the token) but KeyDownAsync itself returns rather than throwing.
        // The test uses a TCS to synchronise so that AbortAsync is called deterministically
        // while KeyDownAsync is in progress (not before or after).
        var txInProgressTcs = new TaskCompletionSource();
        var txCallCount     = 0;

        var racyPtt = Substitute.For<IPttController>();
        racyPtt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(async ci =>
        {
            var n  = Interlocked.Increment(ref txCallCount);
            var ct = ci.Arg<CancellationToken>();
            if (n == 1)
                return; // TxAnswer: complete immediately so the test can reach WaitReport.

            // TxReport (n ≥ 2): block until the token is cancelled, then return normally.
            // This is the "racy" KeyDownAsync behaviour described in D-007.
            var waitTcs = new TaskCompletionSource();
            using var reg = ct.Register(() => waitTcs.TrySetResult());
            txInProgressTcs.TrySetResult(); // tell the test thread KeyDown is now in flight
            if (!ct.IsCancellationRequested)
                await waitTcs.Task.WaitAsync(TimeSpan.FromSeconds(5));
            // Return normally (no exception) — the core of the D-007 race.
        });
        racyPtt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var store = Substitute.For<IConfigStore>();
        store.Current.Returns(new AppConfig() with
        {
            Tx = new TxConfig
            {
                AutoAnswer      = true,
                Callsign        = OurCallsign,
                Grid            = OurGrid,
                RetryCount      = 3,
                WatchdogMinutes = 4,
            }
        });

        var adifLog = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);
        var channel = Channel.CreateUnbounded<DecodeBatch>();
        var sut     = new QsoAnswererService(channel.Reader, store, racyPtt, new TxEventBus(),
                          adifLog, new AudioOffsetEventBus(),
                          NullLogger<QsoAnswererService>.Instance);

        using var stopCts = new CancellationTokenSource();
        await sut.StartAsync(stopCts.Token);

        // Reach WaitReport.
        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, $"CQ {PartnerCall} {PartnerGrid}")]));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));

        // Trigger TxReport TX.
        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", +5, 0.1, AudioFreqHz, $"{OurCallsign} {PartnerCall} +05")]));

        // Wait until KeyDownAsync is definitely in progress before aborting.
        await txInProgressTcs.Task.WaitAsync(TimeSpan.FromSeconds(3));
        await sut.AbortAsync(); // cancels _txCts → linked token cancelled → KeyDown unblocks → returns normally

        // Assert: service returns to Idle (D-007 fix: ThrowIfCancellationRequested propagates abort).
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(3));
        sut.State.Should().Be(QsoState.Idle, "abort must win the race against TX completion");
        sut.Partner.Should().BeNull("partner must be cleared on abort");

        // Note (R-3): ADIF assertion removed — AppendQsoAsync is only reached via ExecuteTx73Async
        // which requires an RR73/RRR message; this test never injects one, so File.Exists was
        // always true and could not catch a regression. ADIF-on-abort coverage belongs in a
        // dedicated test that drives the service all the way to Tx73 and aborts mid-TX.

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await racyPtt.DisposeAsync();
    }

    // ── D-008: watchdog fires before retry count exhaustion ──────────────────

    [Fact(DisplayName = "D-008: Watchdog fires before retry count is exhausted when partner goes silent")]
    public async Task Watchdog_FiresBeforeRetryExhaustion_WhenPartnerSilent()
    {
        // Arrange: very short watchdog so the test does not wait 60 s.
        // RetryCount=100 — if D-008 is present, retries reset the watchdog on every cycle
        // and Idle is never reached as long as the channel keeps being fed.
        // If D-008 is fixed, the watchdog fires independently at ~300 ms.
        var watchdogDuration = TimeSpan.FromMilliseconds(300);

        var ptt = Substitute.For<IPttController>();
        ptt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var store = Substitute.For<IConfigStore>();
        store.Current.Returns(new AppConfig() with
        {
            Tx = new TxConfig
            {
                AutoAnswer      = true,
                Callsign        = OurCallsign,
                Grid            = OurGrid,
                RetryCount      = 100,   // enormous — watchdog must fire long before this
                WatchdogMinutes = 4,     // overridden by watchdogDuration below
            }
        });

        var adifLog = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);
        var channel = Channel.CreateUnbounded<DecodeBatch>();

        var sut = new QsoAnswererService(channel.Reader, store, ptt, new TxEventBus(),
                      adifLog, new AudioOffsetEventBus(),
                      NullLogger<QsoAnswererService>.Instance,
                      watchdogDurationOverride: watchdogDuration);

        using var stopCts = new CancellationTokenSource();
        await sut.StartAsync(stopCts.Token);

        // Trigger CQ answer → WaitReport.
        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, $"CQ {PartnerCall} {PartnerGrid}")]));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));

        // Feed non-CQ noise continuously so retries keep cycling without pause.
        // IMPORTANT: must NOT be a CQ — when the watchdog fires and the service returns to
        // Idle, a queued CQ would cause HandleIdleAsync to immediately answer it and re-enter
        // TxAnswer, making Idle invisible to the 10 ms polling loop regardless of wait timeout.
        // "Q2NOISE Q3NOISE -10" is an FT8 exchange message: TryParseCq returns false → Idle
        // is stable; TryParseMessage returns a non-partner/non-us decode → retry fires. ✓
        //
        // With the D-008 fix:  watchdog fires at ~300 ms → service reaches Idle and stays there.
        // With the D-008 bug:  every retry resets the watchdog; Idle is never reached while the
        //                      feeder runs → WaitForStateAsync times out.
        using var feedCts = new CancellationTokenSource(TimeSpan.FromSeconds(2));
        var feedTask = Task.Run(async () =>
        {
            while (!feedCts.IsCancellationRequested)
            {
                channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
                    [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, "Q2NOISE Q3NOISE -10")]));
                try   { await Task.Delay(10, feedCts.Token); }
                catch (OperationCanceledException) { break; }
            }
        });

        // Deadline distinguishes the two paths (1 500 ms < 2 000 ms feeder window).
        // Fixed:  watchdog fires → Idle reached and stays Idle (non-CQ noise) → poll catches it.
        // Buggy:  every retry resets the watchdog; Idle is never reached while feeder runs (2 s) →
        //         TimeoutException at 1 500 ms (safely below the 2 000 ms feeder window).
        // WaitForStateAsync throws on timeout, so reaching the next line is the assertion.
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromMilliseconds(1500));

        // Cancel the feeder after confirming Idle.
        feedCts.Cancel();
        await feedTask;

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── GUI polish batch item 2: retry TX-colour under-report ────────────────
    //
    // #tx-enable-btn (tx-state-indicators spec) derives its colour from the broadcast `state`
    // alone. Prior to this fix, a retry retransmission stayed silently inside `WaitReport`/
    // `WaitRr73` (dark red) even while audio was actively playing. The fix brackets the
    // retransmission with a `Tx*` broadcast immediately before and the original `Wait*`
    // broadcast immediately after — mirroring QsoCallerService.RetryOrAbortAsync's WaitAnswer
    // retry (SetStateAndNotify(TxCq) / retransmit / SetStateAndNotify(WaitAnswer)).

    [Fact(DisplayName = "GUI polish 2: WaitReport retry brackets retransmission with TxAnswer / WaitReport")]
    public async Task WaitReport_Retry_BracketsRetransmissionWithTxAnswer()
    {
        var txCfg = new TxConfig
        {
            AutoAnswer      = true,
            Callsign        = OurCallsign,
            Grid            = OurGrid,
            RetryCount      = 2,
            WatchdogMinutes = 4,
        };
        var (sut, eventBus, _, ptt, channel, stopCts) =
            BuildIsolatedSut(txCfg, watchdogDuration: TimeSpan.FromSeconds(30));
        await sut.StartAsync(stopCts.Token);

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, $"CQ {PartnerCall} {PartnerGrid}")]));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));
        eventBus.ClearReceivedCalls(); // only interested in the retry's own broadcasts below

        // A-01 skip cycle, then the real retry-triggering cycle.
        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, "CQ Q2NOISE IO91")]));
        await Task.Delay(150);
        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, "CQ Q2NOISE IO91")]));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));
        await Task.Delay(50); // let the trailing post-retransmit publish settle

        Received.InOrder(() =>
        {
            eventBus.Publish("TxAnswer",   "answerer", PartnerCall, true, Arg.Any<string?>());
            eventBus.Publish("WaitReport", "answerer", PartnerCall, true, Arg.Any<string?>());
        });

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "GUI polish 2: WaitRr73 retry brackets retransmission with TxReport / WaitRr73")]
    public async Task WaitRr73_Retry_BracketsRetransmissionWithTxReport()
    {
        var txCfg = new TxConfig
        {
            AutoAnswer      = true,
            Callsign        = OurCallsign,
            Grid            = OurGrid,
            RetryCount      = 2,
            WatchdogMinutes = 4,
        };
        var (sut, eventBus, _, ptt, channel, stopCts) =
            BuildIsolatedSut(txCfg, watchdogDuration: TimeSpan.FromSeconds(30));
        await sut.StartAsync(stopCts.Token);

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, $"CQ {PartnerCall} {PartnerGrid}")]));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(5));

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, $"{OurCallsign} {PartnerCall} +05")]));
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(5));
        eventBus.ClearReceivedCalls(); // only interested in the retry's own broadcasts below

        // A-01 skip cycle, then the real retry-triggering cycle.
        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, "CQ Q2NOISE IO91")]));
        await Task.Delay(150);
        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, "CQ Q2NOISE IO91")]));
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(5));
        await Task.Delay(50); // let the trailing post-retransmit publish settle

        Received.InOrder(() =>
        {
            eventBus.Publish("TxReport", "answerer", PartnerCall, true, Arg.Any<string?>());
            eventBus.Publish("WaitRr73", "answerer", PartnerCall, true, Arg.Any<string?>());
        });

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── Mutable config store helper (phase-aware pending-target tests) ────────

    /// <summary>
    /// Simple mutable <see cref="IConfigStore"/> used in pending-target tests that
    /// need to observe side-effects of <see cref="IConfigStore.SaveAsync"/>.
    /// </summary>
    private sealed class MutableConfigStore : IConfigStore
    {
        private AppConfig _current;
        public MutableConfigStore(AppConfig initial) => _current = initial;
        public AppConfig Current => _current;
        public event Action<AppConfig>? OnSaved;
        public Task SaveAsync(AppConfig config, CancellationToken ct = default)
        {
            _current = config;
            OnSaved?.Invoke(config);
            return Task.CompletedTask;
        }
    }

    /// <summary>
    /// Config store that delays every <see cref="SaveAsync"/> call by a fixed amount —
    /// used to deterministically reproduce the D-TX-UI-006 async-save race.
    /// </summary>
    private sealed class SlowConfigStore : IConfigStore
    {
        private AppConfig _current;
        private readonly TimeSpan _delay;
        public SlowConfigStore(AppConfig initial, TimeSpan delay) { _current = initial; _delay = delay; }
        public AppConfig Current => _current;
        public event Action<AppConfig>? OnSaved;
        public async Task SaveAsync(AppConfig config, CancellationToken ct = default)
        {
            await Task.Delay(_delay, ct).ConfigureAwait(false);
            _current = config;
            OnSaved?.Invoke(config);
        }
    }

    // ── AnswerCqAsync — phase-determination tests ─────────────────────────────

    [Fact(DisplayName = "AnswerCqAsync: CQ at B-phase (:15) — fires TX when next A-phase batch arrives")]
    public async Task AnswerCqAsync_WhenIdle_BPhaseAnswer_SetsPendingAPhase()
    {
        // CQ station was transmitting at B-phase (:15) → answer phase is A (:00 / :30).
        var cqCycleStart = new DateTimeOffset(2026, 6, 22, 17, 29, 15, TimeSpan.Zero); // :15 = B-phase

        await _sut!.AnswerCqAsync(PartnerCall, AudioFreqHz, cqCycleStart, CancellationToken.None);
        // Drain the wakeup before sending the test batch.  If the wakeup fires TX first and the
        // batch then arrives in WaitReport carrying a CQ-from-partner, HandleWaitReportAsync would
        // interpret it as "partner working another station" and abort back to Idle (race failure).
        // Draining eliminates that path; the batch fires TX from the pending-target path instead.
        _sut!._wakeupChannel.Reader.TryRead(out _);

        // Feed a batch with CycleStart at :15 (B-phase) so that CycleStart + 15 s = :30 (A-phase).
        // The framer emits a cycle's batch at the END of that cycle; the phase check therefore
        // evaluates (CycleStart + 15 s), not CycleStart itself (D-TX-UI-007 fix).
        // Use a noise message: safe in WaitReport if the wakeup wins the drain race (fallback).
        var bPhaseStart = new DateTimeOffset(2026, 6, 22, 17, 30, 15, TimeSpan.Zero); // :15 B-phase → +15 s = :30 A-phase
        Send(bPhaseStart,
             new DecodeResult(Time: "17:30:15", Snr: -5, Dt: 0.1, FreqHz: AudioFreqHz,
                 Message: $"Q2NOISE Q3NOISE -10"));

        await WaitForStateAsync(_sut!, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));
        _sut!.Partner.Should().Be(PartnerCall, "pending target callsign must become the active partner");
        await _ptt.Received(1).KeyDownAsync(Arg.Any<CancellationToken>());
    }

    [Fact(DisplayName = "AnswerCqAsync: CQ at A-phase (:00) — fires TX when next B-phase batch arrives")]
    public async Task AnswerCqAsync_WhenIdle_APhaseAnswer_SetsPendingBPhase()
    {
        // CQ station was at A-phase (:00) → answer phase is B (:15 / :45).
        var cqCycleStart = new DateTimeOffset(2026, 6, 22, 17, 30, 0, TimeSpan.Zero); // :00 = A-phase

        await _sut!.AnswerCqAsync(PartnerCall, AudioFreqHz, cqCycleStart, CancellationToken.None);
        // Drain the wakeup before sending the test batch to prevent the CQ-from-partner batch
        // from landing in WaitReport (which would trigger "partner working another station").
        _sut!._wakeupChannel.Reader.TryRead(out _);

        // Feed a batch with CycleStart at :00 (A-phase) so that CycleStart + 15 s = :15 (B-phase).
        // The framer emits a cycle's batch at the END of that cycle; the phase check therefore
        // evaluates (CycleStart + 15 s), not CycleStart itself (D-TX-UI-007 fix).
        // Use a noise message: safe in WaitReport if the wakeup wins the drain race (fallback).
        var aPhaseStart = new DateTimeOffset(2026, 6, 22, 17, 30, 0, TimeSpan.Zero); // :00 A-phase → +15 s = :15 B-phase
        Send(aPhaseStart,
             new DecodeResult(Time: "17:30:00", Snr: -5, Dt: 0.1, FreqHz: AudioFreqHz,
                 Message: $"Q2NOISE Q3NOISE -10"));

        await WaitForStateAsync(_sut!, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));
        _sut!.Partner.Should().Be(PartnerCall);
        await _ptt.Received(1).KeyDownAsync(Arg.Any<CancellationToken>());
    }

    [Fact(DisplayName = "HandleIdle: pending target — wrong phase batch does not fire TX")]
    public async Task HandleIdle_PendingTarget_WrongPhase_DoesNotFire()
    {
        // Set pending target via reflection — bypassing AnswerCqAsync avoids the wakeup batch.
        // The wakeup fires with the current wall-clock phase which may or may not match; relying
        // on a drain to beat the background loop is a known race.  The wakeup is tested separately
        // by D-TX-UI-007; this test verifies only that a wrong-phase BATCH doesn't fire TX.
        var type  = typeof(QsoAnswererService);
        var flags = System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance;
        type.GetField("_pendingTargetCallsign",    flags)!.SetValue(_sut, PartnerCall);
        type.GetField("_pendingTargetFrequencyHz", flags)!.SetValue(_sut, (double)AudioFreqHz);
        type.GetField("_pendingTargetIsAPhase",    flags)!.SetValue(_sut, true);  // A-phase answer
        type.GetField("_pendingTargetSetAt",       flags)!.SetValue(_sut, DateTimeOffset.UtcNow);

        // Feed a batch with CycleStart at :30 (A-phase) so that CycleStart + 15 s = :45 (B-phase).
        // B-phase ≠ pending A-phase → phase check fails → no TX (D-TX-UI-007 convention).
        var wrongPhaseStart = new DateTimeOffset(2026, 6, 22, 17, 29, 30, TimeSpan.Zero); // :30 A-phase → +15 s = :45 B-phase ≠ A-phase pending
        Send(wrongPhaseStart,
             new DecodeResult(Time: "17:29:30", Snr: -5, Dt: 0.1, FreqHz: AudioFreqHz,
                 Message: $"CQ Q2NOISE IO91"));
        await Task.Delay(300);

        _sut!.State.Should().Be(QsoState.Idle, "wrong-phase batch must NOT trigger the pending TX");
        await _ptt.DidNotReceive().KeyDownAsync(Arg.Any<CancellationToken>());
    }

    [Fact(DisplayName = "HandleIdle: pending target — correct phase batch fires TX")]
    public async Task HandleIdle_PendingTarget_CorrectPhase_Fires()
    {
        // CQ at :15 (B-phase) → answer phase is A (:00 / :30).
        var cqCycleStart = new DateTimeOffset(2026, 6, 22, 17, 29, 15, TimeSpan.Zero);
        await _sut!.AnswerCqAsync(PartnerCall, AudioFreqHz, cqCycleStart, CancellationToken.None);

        // Feed a batch with CycleStart at :15 (B-phase) so that CycleStart + 15 s = :30 (A-phase).
        // A-phase == pending A-phase → phase check passes → TX fires (D-TX-UI-007 convention).
        var correctPhaseStart = new DateTimeOffset(2026, 6, 22, 17, 30, 15, TimeSpan.Zero); // :15 B-phase → +15 s = :30 A-phase
        Send(correctPhaseStart,
             new DecodeResult(Time: "17:30:15", Snr: -5, Dt: 0.1, FreqHz: AudioFreqHz,
                 Message: $"CQ Q2NOISE IO91"));

        await WaitForStateAsync(_sut!, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));
        _sut!.Partner.Should().Be(PartnerCall);
        await _ptt.Received(1).KeyDownAsync(Arg.Any<CancellationToken>());
    }

    [Fact(DisplayName = "HandleIdle: pending target — silent A-phase batch (empty results) still fires TX (D-TX-UI-004)")]
    public async Task HandleIdle_PendingTarget_SilentAPhase_FiresTx()
    {
        // D-TX-UI-004 root cause: a silence-guard cycle (RMS below threshold → empty batch)
        // was given the wrong phase because the fallback UtcNow snap returned the emission
        // time (at the NEXT boundary), not the cycle-start time.
        // Fix: DecodeBatch.CycleStart carries the authoritative timestamp; no UtcNow fallback.

        // CQ at :15 (B-phase) → answer phase is A (:00 / :30).
        var cqCycleStart = new DateTimeOffset(2026, 6, 22, 17, 29, 15, TimeSpan.Zero); // :15 = B-phase
        await _sut!.AnswerCqAsync(PartnerCall, AudioFreqHz, cqCycleStart, CancellationToken.None);

        // Feed an EMPTY batch whose CycleStart + 15 s is A-phase — the silence guard fired,
        // but the phase is correct.  TX must fire despite the empty results list.
        // CycleStart :15 (B-phase) → + 15 s = :30 (A-phase) → matches pending A-phase ✓
        _channel.Writer.TryWrite(new DecodeBatch(
            new DateTimeOffset(2026, 6, 22, 17, 30, 15, TimeSpan.Zero),  // :15 B-phase → +15 s = :30 A-phase
            Array.Empty<DecodeResult>()));

        await WaitForStateAsync(_sut!, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));
        _sut!.Partner.Should().Be(PartnerCall,
            "a silent A-phase cycle must still trigger the pending TX (D-TX-UI-004 fix)");
        await _ptt.Received(1).KeyDownAsync(Arg.Any<CancellationToken>());
    }

    [Fact(DisplayName = "HandleIdle: pending target > 60 s old is cleared; no TX fires")]
    public async Task HandleIdle_PendingTarget_TimedOut_ClearsAndDoesNotFire()
    {
        // Set pending target directly via reflection — bypassing AnswerCqAsync avoids the wakeup
        // batch that AnswerCqAsync writes.  If the wakeup fires TX before the test can backdate
        // _pendingTargetSetAt, the assertion would incorrectly see WaitReport.
        // The wakeup behaviour is tested separately by the D-TX-UI-007 tests.
        var type  = typeof(QsoAnswererService);
        var flags = System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance;
        type.GetField("_pendingTargetCallsign",    flags)!.SetValue(_sut, PartnerCall);
        type.GetField("_pendingTargetFrequencyHz", flags)!.SetValue(_sut, (double)AudioFreqHz);
        type.GetField("_pendingTargetIsAPhase",    flags)!.SetValue(_sut, true);  // A-phase answer
        // Pre-backdate SetAt to simulate a 65-second-old pending target.
        type.GetField("_pendingTargetSetAt",       flags)!
            .SetValue(_sut, DateTimeOffset.UtcNow.AddSeconds(-65));

        // Feed the correct-phase batch (CycleStart + 15 s = A-phase) — should be discarded due to timeout.
        var correctPhaseStart = new DateTimeOffset(2026, 6, 22, 17, 30, 15, TimeSpan.Zero); // :15 B-phase → +15 s = :30 A-phase
        Send(correctPhaseStart,
             new DecodeResult(Time: "17:30:15", Snr: -5, Dt: 0.1, FreqHz: AudioFreqHz,
                 Message: $"CQ Q2NOISE IO91"));
        await Task.Delay(400);

        _sut!.State.Should().Be(QsoState.Idle, "expired pending target must be discarded without TX");
        await _ptt.DidNotReceive().KeyDownAsync(Arg.Any<CancellationToken>());
    }

    [Fact(DisplayName = "TxAbort: AbortAsync clears pending target; no subsequent TX")]
    public async Task TxAbort_ClearsPendingTarget()
    {
        // Fresh instance with a mutable store so SaveAsync side-effects persist.
        var config = new AppConfig() with
        {
            Tx = new TxConfig
            {
                AutoAnswer      = true,
                Callsign        = OurCallsign,
                Grid            = OurGrid,
                RetryCount      = 2,
                WatchdogMinutes = 4,
            }
        };
        var store   = new MutableConfigStore(config);
        var ptt     = Substitute.For<IPttController>();
        ptt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var channel = Channel.CreateUnbounded<DecodeBatch>();
        var adifLog = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);
        // D-CALLER-013: FakeTimeProvider at second=0 so the late-start guard always passes.
        var earlyInWindow = new FakeTimeProvider(
            new DateTimeOffset(2026, 1, 1, 0, 0, 0, TimeSpan.Zero));
        var sut     = new QsoAnswererService(channel.Reader, store, ptt, new TxEventBus(),
                          adifLog, new AudioOffsetEventBus(),
                          NullLogger<QsoAnswererService>.Instance,
                          watchdogDurationOverride: TimeSpan.FromMinutes(4),
                          timeProvider: earlyInWindow);
        using var stopCts = new CancellationTokenSource();
        await sut.StartAsync(stopCts.Token);

        // Arm a pending CQ target (CQ at :15 → answer phase is A).
        var cqCycleStart = new DateTimeOffset(2026, 6, 22, 17, 29, 15, TimeSpan.Zero);
        await sut.AnswerCqAsync(PartnerCall, AudioFreqHz, cqCycleStart, CancellationToken.None);

        // Fire the pending target by delivering the correct-phase batch.
        // CycleStart :15 (B-phase) → + 15 s = :30 (A-phase) → matches pending A-phase ✓ (D-TX-UI-007).
        channel.Writer.TryWrite(new DecodeBatch(
            new DateTimeOffset(2026, 6, 22, 17, 30, 15, TimeSpan.Zero),  // :15 B-phase → +15 s = :30 A-phase
            [new DecodeResult(Time: "17:30:15", Snr: -5, Dt: 0.1, FreqHz: AudioFreqHz,
             Message: $"CQ Q2NOISE IO91")]));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));

        // Abort the active QSO — SafeAbortToIdleAsync clears _pendingTargetCallsign.
        await sut.AbortAsync();
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(3));

        // Feed another A-phase batch. No pending target remains; AutoAnswer=false after abort
        // also suppresses the CQ-scan path. No further TX should fire.
        channel.Writer.TryWrite(new DecodeBatch(
            new DateTimeOffset(2026, 6, 22, 17, 30, 30, TimeSpan.Zero),  // A-phase (:30)
            [new DecodeResult(Time: "17:30:30", Snr: -5, Dt: 0.1, FreqHz: AudioFreqHz,
             Message: $"CQ Q2NOISE IO91")]));
        await Task.Delay(400);

        sut.State.Should().Be(QsoState.Idle, "abort must clear pending target; no TX fires");
        await ptt.Received(1).KeyDownAsync(Arg.Any<CancellationToken>()); // only TxAnswer TX

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── D-TX-UI-001 / D-TX-UI-003: supervised single-QSO disarm ─────────────

    [Fact(DisplayName = "D-TX-UI-001: AbortAsync during active QSO saves autoAnswer = false in config")]
    public async Task AbortAsync_WhenActiveQso_SetsAutoAnswerFalseInConfig()
    {
        var store = Substitute.For<IConfigStore>();
        store.Current.Returns(new AppConfig() with
        {
            Tx = new TxConfig { AutoAnswer = true, Callsign = OurCallsign, Grid = OurGrid,
                                RetryCount = 2, WatchdogMinutes = 4 }
        });
        var ptt = Substitute.For<IPttController>();
        ptt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var channel = Channel.CreateUnbounded<DecodeBatch>();
        var adifLog = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);
        var sut     = new QsoAnswererService(channel.Reader, store, ptt, new TxEventBus(),
                          adifLog, new AudioOffsetEventBus(),
                          NullLogger<QsoAnswererService>.Instance);
        using var stopCts = new CancellationTokenSource();
        await sut.StartAsync(stopCts.Token);

        // Reach WaitReport (QSO in progress).
        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, $"CQ {PartnerCall} {PartnerGrid}")]));
        await WaitForStateAsync(sut, QsoState.WaitReport);

        // Abort and confirm return to Idle.
        await sut.AbortAsync();
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(3));

        // SafeAbortToIdleAsync must have saved autoAnswer = false.
        await store.Received().SaveAsync(
            Arg.Is<AppConfig>(c => c.Tx != null && c.Tx.AutoAnswer == false),
            Arg.Any<CancellationToken>());

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "D-TX-UI-003: QSO completion saves autoAnswer = false in config")]
    public async Task QsoComplete_SetsAutoAnswerFalseInConfig()
    {
        var store = Substitute.For<IConfigStore>();
        store.Current.Returns(new AppConfig() with
        {
            Tx = new TxConfig { AutoAnswer = true, Callsign = OurCallsign, Grid = OurGrid,
                                RetryCount = 2, WatchdogMinutes = 4 }
        });
        var ptt = Substitute.For<IPttController>();
        ptt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var channel = Channel.CreateUnbounded<DecodeBatch>();
        var adifLog = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);
        var sut     = new QsoAnswererService(channel.Reader, store, ptt, new TxEventBus(),
                          adifLog, new AudioOffsetEventBus(),
                          NullLogger<QsoAnswererService>.Instance);
        using var stopCts = new CancellationTokenSource();
        await sut.StartAsync(stopCts.Token);

        // Drive the full exchange: CQ → WaitReport → TxReport → WaitRr73 → Tx73 → Idle.
        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, $"CQ {PartnerCall} {PartnerGrid}")]));
        await WaitForStateAsync(sut, QsoState.WaitReport);

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", +5, 0.1, AudioFreqHz, $"{OurCallsign} {PartnerCall} +05")]));
        await WaitForStateAsync(sut, QsoState.WaitRr73);

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", +5, 0.1, AudioFreqHz, $"{OurCallsign} {PartnerCall} RR73")]));
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));

        // QsoComplete path (SafeAbortToIdleAsync) must save autoAnswer = false.
        await store.Received().SaveAsync(
            Arg.Is<AppConfig>(c => c.Tx != null && c.Tx.AutoAnswer == false),
            Arg.Any<CancellationToken>());

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "D-TX-UI-003: Retry exhaustion saves autoAnswer = false in config")]
    public async Task RetryExhausted_SetsAutoAnswerFalseInConfig()
    {
        var store = Substitute.For<IConfigStore>();
        store.Current.Returns(new AppConfig() with
        {
            Tx = new TxConfig { AutoAnswer = true, Callsign = OurCallsign, Grid = OurGrid,
                                RetryCount = 2, WatchdogMinutes = 4 }
        });
        var ptt = Substitute.For<IPttController>();
        ptt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var channel = Channel.CreateUnbounded<DecodeBatch>();
        var adifLog = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);
        var sut     = new QsoAnswererService(channel.Reader, store, ptt, new TxEventBus(),
                          adifLog, new AudioOffsetEventBus(),
                          NullLogger<QsoAnswererService>.Instance);
        using var stopCts = new CancellationTokenSource();
        await sut.StartAsync(stopCts.Token);

        // Reach WaitReport, then let retries exhaust (RetryCount = 2 → 6 noise cycles).
        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, $"CQ {PartnerCall} {PartnerGrid}")]));
        await WaitForStateAsync(sut, QsoState.WaitReport);

        // Six noise cycles: [skip] [retry1] [skip] [retry2] [skip] [abort].
        for (int i = 0; i < 6; i++)
        {
            channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
                [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, "Q2NOISE Q3NOISE -10")]));
            await Task.Delay(150);
        }

        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));

        // SafeAbortToIdleAsync on retry exhaustion must save autoAnswer = false.
        await store.Received().SaveAsync(
            Arg.Is<AppConfig>(c => c.Tx != null && c.Tx.AutoAnswer == false),
            Arg.Any<CancellationToken>());

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── D-TX-UI-005: double-click guard (manual verification) ───────────────
    // AC-8a: a human double-click (~150 ms apart) on a CQ row must produce exactly ONE
    // POST /api/v1/tx/answer-cq.  This is enforced by the `inFlight` flag in web/js/main.js
    // which is reset only after a 400 ms setTimeout on success (D-TX-UI-005 fix).
    // Automated coverage is not feasible at this layer; verify manually by clicking a CQ row
    // rapidly and confirming a single POST in the server log.  See also: the `inFlight` guard
    // comment in web/js/main.js line ~271.

    // ── D-TX-UI-007: wakeup channel tests ────────────────────────────────────

    [Fact(DisplayName = "D-TX-UI-007: wakeup batch fires TX in the current cycle window (no main-channel batch needed)")]
    public async Task HandleIdle_PendingTarget_Wakeup_FiresInCurrentCycle()
    {
        // Determine the current FT8 cycle phase at test time.
        // Set the pending phase to MATCH so the wakeup (which carries the current phase) fires TX.
        //
        // Phase-boundary caveat: if the test thread is pre-empted for ~100 ms between computing
        // nowIsAPhase and AnswerCqAsync writing the wakeup, a 15-second cycle boundary may cross,
        // making the wakeup carry the FOLLOWING phase and causing this test to time out.  The
        // probability is ≈ 0.67 % per run (100 ms / 15 000 ms).  If this test becomes flaky,
        // add a short delay after the phase sample to step clear of the boundary.
        bool nowIsAPhase = (DateTimeOffset.UtcNow.Second / 15 * 15) % 30 == 0;

        // CQ is at the OPPOSITE phase so that AnswerCqAsync sets pendingIsAPhase = nowIsAPhase.
        var cqCycleStart = nowIsAPhase
            ? new DateTimeOffset(2026, 6, 22, 17, 29, 15, TimeSpan.Zero)  // B-phase CQ → A-phase answer
            : new DateTimeOffset(2026, 6, 22, 17, 30, 0,  TimeSpan.Zero); // A-phase CQ → B-phase answer

        await _sut!.AnswerCqAsync(PartnerCall, AudioFreqHz, cqCycleStart, CancellationToken.None);
        // No main-channel batch — TX must fire from the wakeup batch alone.
        await WaitForStateAsync(_sut!, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(2));
        await _ptt.Received(1).KeyDownAsync(Arg.Any<CancellationToken>());
    }

    [Fact(DisplayName = "D-TX-UI-007: wakeup batch skips wrong phase; TX fires from subsequent correct-phase batch")]
    public async Task HandleIdle_PendingTarget_Wakeup_SkipsWrongPhase()
    {
        // Pending phase = OPPOSITE of current phase → wakeup is wrong phase → skips.
        bool nowIsAPhase = (DateTimeOffset.UtcNow.Second / 15 * 15) % 30 == 0;
        // CQ is at the SAME phase as now → answer = opposite = !nowIsAPhase.
        var cqCycleStart = nowIsAPhase
            ? new DateTimeOffset(2026, 6, 22, 17, 30, 0,  TimeSpan.Zero) // A-phase CQ → B-phase answer
            : new DateTimeOffset(2026, 6, 22, 17, 29, 15, TimeSpan.Zero); // B-phase CQ → A-phase answer
        bool pendingIsAPhase = !nowIsAPhase;

        await _sut!.AnswerCqAsync(PartnerCall, AudioFreqHz, cqCycleStart, CancellationToken.None);

        // Drain the wakeup to enforce the "wakeup skips" scenario deterministically.
        _sut!._wakeupChannel.Reader.TryRead(out _);

        // Push a correct-phase batch from the main channel — TX must fire from this batch.
        // CycleStart chosen so that CycleStart + 15 s == the pending phase boundary.
        var correctPhaseCycleStart = pendingIsAPhase
            ? new DateTimeOffset(2026, 6, 22, 17, 30, 15, TimeSpan.Zero)  // :15 B-phase → +15 s = :30 A-phase
            : new DateTimeOffset(2026, 6, 22, 17, 30, 0,  TimeSpan.Zero); // :00 A-phase → +15 s = :15 B-phase

        Send(correctPhaseCycleStart,
             new DecodeResult(Time: "17:30:00", Snr: -5, Dt: 0.1, FreqHz: AudioFreqHz,
                 Message: $"CQ Q2NOISE IO91"));

        await WaitForStateAsync(_sut!, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));
        await _ptt.Received(1).KeyDownAsync(Arg.Any<CancellationToken>());
    }

    // ── D-TX-UI-006 regression ────────────────────────────────────────────────

    [Fact(DisplayName = "D-TX-UI-006: pending target fires even when SaveAsync(AutoAnswer=true) is delayed (slow-save regression)")]
    public async Task HandleIdle_PendingTarget_FiresWhenAutoAnswerSaveIsDelayed()
    {
        // Verifies that HandleIdleAsync does NOT gate on tx.AutoAnswer for the pending-target path.
        // Simulates the race: AnswerCqAsync sets _pendingTargetCallsign synchronously but its
        // SaveAsync(AutoAnswer=true) is delayed 200 ms. The A-phase batch is delivered before the
        // save completes → AutoAnswer is still false in config when HandleIdleAsync runs.
        // Before the fix: pending target silently discarded. After fix: TX fires regardless.

        // Arrange: store whose saves are delayed 200 ms (longer than batch delivery below).
        var config = new AppConfig() with
        {
            Tx = new TxConfig
            {
                AutoAnswer      = false,   // starts false; save "hasn't completed" during the race
                Callsign        = OurCallsign,
                Grid            = OurGrid,
                RetryCount      = 2,
                WatchdogMinutes = 4,
            }
        };
        var slowStore = new SlowConfigStore(config, TimeSpan.FromMilliseconds(200));

        var ptt = Substitute.For<IPttController>();
        ptt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var channel = Channel.CreateUnbounded<DecodeBatch>();
        var adifLog = new AdifLogWriter(slowStore, NullLogger<AdifLogWriter>.Instance);
        // D-CALLER-013: FakeTimeProvider at second=0 so the late-start guard passes.
        var earlyInWindow = new FakeTimeProvider(
            new DateTimeOffset(2026, 1, 1, 0, 0, 0, TimeSpan.Zero));
        var sut     = new QsoAnswererService(channel.Reader, slowStore, ptt, new TxEventBus(),
                          adifLog, new AudioOffsetEventBus(),
                          NullLogger<QsoAnswererService>.Instance,
                          watchdogDurationOverride: TimeSpan.FromMinutes(4),
                          timeProvider: earlyInWindow);
        using var stopCts = new CancellationTokenSource();
        await sut.StartAsync(stopCts.Token);

        // Arm pending target — SaveAsync(AutoAnswer=true) starts but takes 200 ms.
        // cqCycleStart at :15 (B-phase) → answer fires on next A-phase (:00/:30).
        var armTask = sut.AnswerCqAsync(
            PartnerCall, AudioFreqHz,
            new DateTimeOffset(2026, 6, 22, 17, 29, 15, TimeSpan.Zero),
            CancellationToken.None);

        // Deliver a batch immediately — before the 200 ms save completes.
        // AutoAnswer is still false in slowStore.Current at this moment.
        // CycleStart :15 (B-phase) → + 15 s = :30 (A-phase) → matches pending A-phase (D-TX-UI-007).
        channel.Writer.TryWrite(new DecodeBatch(
            new DateTimeOffset(2026, 6, 22, 17, 30, 15, TimeSpan.Zero),
            Array.Empty<DecodeResult>()));

        await armTask; // let AnswerCqAsync finish (save completes after batch processing)

        // Assert: TX must fire into WaitReport despite the save lag.
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));
        await ptt.Received(1).KeyDownAsync(Arg.Any<CancellationToken>());

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── D-TX-002: unlimited retries (RetryCount = 0) ─────────────────────────

    [Fact(DisplayName = "D-TX-002: RetryCount = 0 never aborts — watchdog is the backstop")]
    public async Task RetryOrAbortAsync_RetryCount0_NeverAbortsAfterMultipleEmptyCycles()
    {
        // Build an isolated instance with RetryCount = 0 (unlimited) and a very long watchdog.
        // The watchdog is overridden to 10 seconds so the test completes in reasonable time,
        // but we only feed a few empty cycles — far fewer than would trigger even a normal retry.
        var ptt = Substitute.For<IPttController>();
        ptt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var store = Substitute.For<IConfigStore>();
        store.Current.Returns(new AppConfig() with
        {
            Tx = new TxConfig
            {
                AutoAnswer      = true,
                Callsign        = OurCallsign,
                Grid            = OurGrid,
                RetryCount      = 0,   // unlimited — must never abort due to retry exhaustion
                WatchdogMinutes = 1,   // overridden below
            }
        });

        var adifLog = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);
        var channel = Channel.CreateUnbounded<DecodeBatch>();

        // Override watchdog to 10 s so the test doesn't need to wait 1 minute.
        var sut = new QsoAnswererService(channel.Reader, store, ptt, new TxEventBus(),
                      adifLog, new AudioOffsetEventBus(),
                      NullLogger<QsoAnswererService>.Instance,
                      watchdogDurationOverride: TimeSpan.FromSeconds(10));

        using var stopCts = new CancellationTokenSource();
        await sut.StartAsync(stopCts.Token);

        // Trigger CQ → WaitReport.
        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, $"CQ {PartnerCall} {PartnerGrid}")]));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));

        // Feed 6 empty batches — more than the default RetryCount=3 would tolerate.
        // With RetryCount=3 the service would abort after ~4 cycles (skip + 3 retries).
        // With RetryCount=0 the service must stay in WaitReport (or retransmit each cycle).
        for (int i = 0; i < 6; i++)
        {
            channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
                [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, "Q2NOISE Q3NOISE -10")]));
            await Task.Delay(50);
        }

        // Allow the last batch to be processed.
        await Task.Delay(200);

        // Service must still be in WaitReport (retransmitting), NOT Idle (aborted).
        // If it is Idle, RetryCount=0 was treated as finite (old clamp to 1 bug).
        sut.State.Should().NotBe(QsoState.Idle,
            "RetryCount=0 means unlimited retries; the service must not abort to Idle after 6 empty cycles");

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "D-TX-002: RetryCount = 3 aborts to Idle after retry exhaustion")]
    public async Task RetryOrAbortAsync_RetryCount3_AbortsAfterExhaustion()
    {
        // Verify that a finite RetryCount still triggers abort at the right cycle.
        // This is a regression guard: the unlimited-RetryCount=0 change must not
        // disable the finite-retry abort path.
        var ptt = Substitute.For<IPttController>();
        ptt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var store = Substitute.For<IConfigStore>();
        store.Current.Returns(new AppConfig() with
        {
            Tx = new TxConfig
            {
                AutoAnswer      = true,
                Callsign        = OurCallsign,
                Grid            = OurGrid,
                RetryCount      = 3,
                WatchdogMinutes = 4,
            }
        });

        var adifLog = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);
        var channel = Channel.CreateUnbounded<DecodeBatch>();

        var sut = new QsoAnswererService(channel.Reader, store, ptt, new TxEventBus(),
                      adifLog, new AudioOffsetEventBus(),
                      NullLogger<QsoAnswererService>.Instance,
                      watchdogDurationOverride: TimeSpan.FromSeconds(10));

        using var stopCts = new CancellationTokenSource();
        await sut.StartAsync(stopCts.Token);

        // Trigger CQ → WaitReport.
        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, $"CQ {PartnerCall} {PartnerGrid}")]));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));

        // Feed a continuous stream of empty (noise) batches; service must abort within 2 s.
        using var feedCts = new CancellationTokenSource(TimeSpan.FromSeconds(2));
        var feedTask = Task.Run(async () =>
        {
            while (!feedCts.IsCancellationRequested)
            {
                channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
                    [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, "Q2NOISE Q3NOISE -10")]));
                try   { await Task.Delay(10, feedCts.Token); }
                catch (OperationCanceledException) { break; }
            }
        });

        // With RetryCount=3, the abort must happen well within the 2 s feeder window.
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromMilliseconds(1500));
        feedCts.Cancel();
        await feedTask;

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── FR-UX-002: abort reason emitted on txState Idle transition ────────────

    /// <summary>
    /// Builds an isolated <see cref="QsoAnswererService"/> wired to an
    /// <see cref="ITxEventBus"/> substitute so that <c>Publish</c> calls can be inspected.
    /// </summary>
    private static (QsoAnswererService sut, ITxEventBus eventBus, IAdifLogWriter adifLog,
                    IPttController ptt, Channel<DecodeBatch> channel, CancellationTokenSource stopCts)
        BuildIsolatedSut(
            TxConfig                  txConfig,
            TimeSpan                  watchdogDuration,
            IAdifLogWriter?           adifLog = null,
            ICatState?                catState = null,
            AppConfig?                appConfig = null)
    {
        var ptt = Substitute.For<IPttController>();
        ptt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var store = Substitute.For<IConfigStore>();
        store.Current.Returns((appConfig ?? new AppConfig()) with { Tx = txConfig });
        // SaveAsync is called by SafeAbortToIdleAsync (disarm) and AnswerCqAsync (arm);
        // return Task.CompletedTask for both so the service does not stall on a null Task.
        store.SaveAsync(Arg.Any<AppConfig>(), Arg.Any<CancellationToken>())
             .Returns(Task.CompletedTask);

        var eventBus    = Substitute.For<ITxEventBus>();
        var resolvedLog = adifLog ?? new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);
        var channel     = Channel.CreateUnbounded<DecodeBatch>();
        var stopCts     = new CancellationTokenSource();

        var sut = new QsoAnswererService(
            channel.Reader, store, ptt, eventBus,
            resolvedLog, new AudioOffsetEventBus(),
            NullLogger<QsoAnswererService>.Instance,
            watchdogDurationOverride: watchdogDuration,
            catState: catState);

        return (sut, eventBus, resolvedLog, ptt, channel, stopCts);
    }

    /// <summary>D-013: minimal fixed-frequency <see cref="ICatState"/> test double, mirroring
    /// the pattern established in <c>DecodeFrequencyGuardTests.StubCatState</c>.</summary>
    private sealed class StubCatState : ICatState
    {
        private readonly double _freq;
        public StubCatState(double freqMHz) => _freq = freqMHz;

        public double?              DialFrequencyMHz => _freq;
        public CatConnectionStatus  Status            => CatConnectionStatus.Connected;
    }

    [Fact(DisplayName = "FR-UX-002: watchdog expiry publishes Idle with 'Watchdog timeout' abort reason")]
    public async Task SafeAbortToIdleAsync_WatchdogTimeout_EmitsAbortReason()
    {
        var txCfg = new TxConfig
        {
            AutoAnswer      = true,
            Callsign        = OurCallsign,
            Grid            = OurGrid,
            RetryCount      = 0,    // unlimited — only the watchdog terminates the session
            WatchdogMinutes = 1,    // overridden to 300 ms below
        };
        var (sut, eventBus, _, ptt, channel, stopCts) =
            BuildIsolatedSut(txCfg, watchdogDuration: TimeSpan.FromMilliseconds(300));

        await sut.StartAsync(stopCts.Token);

        // Trigger CQ → TxAnswer → WaitReport.
        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, $"CQ {PartnerCall} {PartnerGrid}")]));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));

        // Feed no further batches — watchdog fires after 300 ms and drives the service to Idle.
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(3));

        // The Idle publish must carry "Watchdog timeout" as the abort reason.
        eventBus.Received().Publish(
            "Idle",
            "answerer",
            Arg.Any<string?>(),
            false,
            "Watchdog timeout");

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "FR-UX-002: operator AbortAsync publishes Idle with 'Operator abort' abort reason")]
    public async Task SafeAbortToIdleAsync_OperatorAbort_EmitsAbortReason()
    {
        var txCfg = new TxConfig
        {
            AutoAnswer      = true,
            Callsign        = OurCallsign,
            Grid            = OurGrid,
            RetryCount      = 0,    // unlimited — only an explicit abort terminates the session
            WatchdogMinutes = 1,    // overridden to 30 s — well beyond test duration
        };
        var (sut, eventBus, _, ptt, channel, stopCts) =
            BuildIsolatedSut(txCfg, watchdogDuration: TimeSpan.FromSeconds(30));

        await sut.StartAsync(stopCts.Token);

        // Trigger CQ → TxAnswer → WaitReport.
        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, $"CQ {PartnerCall} {PartnerGrid}")]));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));

        // Operator presses the Abort button — simulated via AbortAsync().
        await sut.AbortAsync();
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(3));

        // The Idle publish must carry "Operator abort" as the abort reason.
        eventBus.Received().Publish(
            "Idle",
            "answerer",
            Arg.Any<string?>(),
            false,
            "Operator abort");

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "FR-UX-002: normal 73 QSO completion publishes Idle with null abort reason")]
    public async Task SafeAbortToIdleAsync_NormalCompletion_NoAbortReason()
    {
        var txCfg = new TxConfig
        {
            AutoAnswer      = true,
            Callsign        = OurCallsign,
            Grid            = OurGrid,
            RetryCount      = 3,
            WatchdogMinutes = 1,    // overridden to 30 s — well beyond test duration
        };
        var (sut, eventBus, _, ptt, channel, stopCts) =
            BuildIsolatedSut(txCfg, watchdogDuration: TimeSpan.FromSeconds(30));

        await sut.StartAsync(stopCts.Token);

        // Drive the full exchange: CQ → TxAnswer → WaitReport → TxReport → WaitRr73 → Tx73 → Idle.
        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, $"CQ {PartnerCall} {PartnerGrid}")]));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", +5, 0.1, AudioFreqHz, $"{OurCallsign} {PartnerCall} +05")]));
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(3));

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", +5, 0.1, AudioFreqHz, $"{OurCallsign} {PartnerCall} RR73")]));
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));

        // The Idle publish on normal QSO completion must carry a null abort reason
        // (no entry is added to the TX history log — FR-UX-002).
        eventBus.Received().Publish(
            "Idle",
            "answerer",
            Arg.Any<string?>(),
            false,
            Arg.Is<string?>(r => r == null));

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── qso-log-dialog: QsoConfirmation tests (tasks 5.3–5.5) ────────────────

    [Fact(DisplayName = "qso-log-dialog 5.3: QsoConfirmation=true emits PublishQsoReview on Tx73 entry")]
    public async Task ExecuteTx73Async_QsoConfirmationEnabled_PublishesQsoReviewEvent()
    {
        var txCfg = new TxConfig
        {
            AutoAnswer      = true,
            Callsign        = OurCallsign,
            Grid            = OurGrid,
            RetryCount      = 3,
            WatchdogMinutes = 1,
            QsoConfirmation = true,
        };
        var mockAdif = Substitute.For<IAdifLogWriter>();
        mockAdif.AppendQsoAsync(Arg.Any<QsoRecord>()).Returns(Task.CompletedTask);

        var (sut, eventBus, _, ptt, channel, stopCts) =
            BuildIsolatedSut(txCfg, watchdogDuration: TimeSpan.FromSeconds(30), adifLog: mockAdif);

        await sut.StartAsync(stopCts.Token);

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, $"CQ {PartnerCall} {PartnerGrid}")]));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", +5, 0.1, AudioFreqHz, $"{OurCallsign} {PartnerCall} +05")]));
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(3));

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", +5, 0.1, AudioFreqHz, $"{OurCallsign} {PartnerCall} RR73")]));
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));

        // PublishQsoReview must have been called exactly once.
        eventBus.Received(1).PublishQsoReview(
            Arg.Is<QsoRecord>(r => r.PartnerCallsign == PartnerCall),
            Arg.Any<string>(),
            Arg.Any<string>(),
            Arg.Any<string>());

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "qso-log-dialog 5.4: QsoConfirmation=true skips ADIF AppendQsoAsync")]
    public async Task ExecuteTx73Async_QsoConfirmationEnabled_SkipsAdifWrite()
    {
        var txCfg = new TxConfig
        {
            AutoAnswer      = true,
            Callsign        = OurCallsign,
            Grid            = OurGrid,
            RetryCount      = 3,
            WatchdogMinutes = 1,
            QsoConfirmation = true,
        };
        var mockAdif = Substitute.For<IAdifLogWriter>();
        mockAdif.AppendQsoAsync(Arg.Any<QsoRecord>()).Returns(Task.CompletedTask);

        var (sut, _, _, ptt, channel, stopCts) =
            BuildIsolatedSut(txCfg, watchdogDuration: TimeSpan.FromSeconds(30), adifLog: mockAdif);

        await sut.StartAsync(stopCts.Token);

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, $"CQ {PartnerCall} {PartnerGrid}")]));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", +5, 0.1, AudioFreqHz, $"{OurCallsign} {PartnerCall} +05")]));
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(3));

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", +5, 0.1, AudioFreqHz, $"{OurCallsign} {PartnerCall} RR73")]));
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));

        // AppendQsoAsync must NOT have been called when confirmation is enabled.
        await mockAdif.DidNotReceive().AppendQsoAsync(Arg.Any<QsoRecord>());

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "qso-log-dialog 5.5: QsoConfirmation=false still calls ADIF AppendQsoAsync")]
    public async Task ExecuteTx73Async_QsoConfirmationDisabled_WritesAdif()
    {
        var txCfg = new TxConfig
        {
            AutoAnswer      = true,
            Callsign        = OurCallsign,
            Grid            = OurGrid,
            RetryCount      = 3,
            WatchdogMinutes = 1,
            QsoConfirmation = false,
        };
        var mockAdif = Substitute.For<IAdifLogWriter>();
        mockAdif.AppendQsoAsync(Arg.Any<QsoRecord>()).Returns(Task.CompletedTask);

        var (sut, _, _, ptt, channel, stopCts) =
            BuildIsolatedSut(txCfg, watchdogDuration: TimeSpan.FromSeconds(30), adifLog: mockAdif);

        await sut.StartAsync(stopCts.Token);

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, $"CQ {PartnerCall} {PartnerGrid}")]));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", +5, 0.1, AudioFreqHz, $"{OurCallsign} {PartnerCall} +05")]));
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(3));

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", +5, 0.1, AudioFreqHz, $"{OurCallsign} {PartnerCall} RR73")]));
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));

        // AppendQsoAsync must have been called exactly once when confirmation is disabled.
        await mockAdif.Received(1).AppendQsoAsync(Arg.Any<QsoRecord>());

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── D-013: QSO records must use the live CAT dial frequency, not the stale ──
    //           DecodeLog.DialFrequencyMHz config fallback, when CAT is connected ──

    [Fact(DisplayName = "D-013: live CAT frequency differs from config → ADIF record uses live CAT value")]
    public async Task QsoComplete_LiveCatFrequencyDiffersFromConfig_AdifRecordUsesLiveCatValue()
    {
        var txCfg = new TxConfig
        {
            AutoAnswer      = true,
            Callsign        = OurCallsign,
            Grid            = OurGrid,
            RetryCount      = 3,
            WatchdogMinutes = 1,
            QsoConfirmation = false,
        };
        var appConfig = new AppConfig() with
        {
            DecodeLog = new DecodeLogConfig { DialFrequencyMHz = 7.100 }, // stale: 40m
        };
        var catState  = new StubCatState(14.074); // live: 20m
        var mockAdif  = Substitute.For<IAdifLogWriter>();
        mockAdif.AppendQsoAsync(Arg.Any<QsoRecord>()).Returns(Task.CompletedTask);

        var (sut, _, _, ptt, channel, stopCts) = BuildIsolatedSut(
            txCfg, watchdogDuration: TimeSpan.FromSeconds(30), adifLog: mockAdif,
            catState: catState, appConfig: appConfig);

        await sut.StartAsync(stopCts.Token);

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, $"CQ {PartnerCall} {PartnerGrid}")]));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", +5, 0.1, AudioFreqHz, $"{OurCallsign} {PartnerCall} +05")]));
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(3));

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", +5, 0.1, AudioFreqHz, $"{OurCallsign} {PartnerCall} RR73")]));
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
        var txCfg = new TxConfig
        {
            AutoAnswer      = true,
            Callsign        = OurCallsign,
            Grid            = OurGrid,
            RetryCount      = 3,
            WatchdogMinutes = 1,
            QsoConfirmation = false,
        };
        var appConfig = new AppConfig() with
        {
            DecodeLog = new DecodeLogConfig { DialFrequencyMHz = 7.100 },
        };
        var mockAdif  = Substitute.For<IAdifLogWriter>();
        mockAdif.AppendQsoAsync(Arg.Any<QsoRecord>()).Returns(Task.CompletedTask);

        var (sut, _, _, ptt, channel, stopCts) = BuildIsolatedSut(
            txCfg, watchdogDuration: TimeSpan.FromSeconds(30), adifLog: mockAdif,
            catState: null, appConfig: appConfig);

        await sut.StartAsync(stopCts.Token);

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, $"CQ {PartnerCall} {PartnerGrid}")]));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", +5, 0.1, AudioFreqHz, $"{OurCallsign} {PartnerCall} +05")]));
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(3));

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", +5, 0.1, AudioFreqHz, $"{OurCallsign} {PartnerCall} RR73")]));
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
        var txCfg = new TxConfig
        {
            AutoAnswer      = true,
            Callsign        = OurCallsign,
            Grid            = OurGrid,
            RetryCount      = 3,
            WatchdogMinutes = 1,
            QsoConfirmation = true,
        };
        var appConfig = new AppConfig() with
        {
            DecodeLog = new DecodeLogConfig { DialFrequencyMHz = 7.100 }, // stale: 40m
        };
        var catState  = new StubCatState(14.074); // live: 20m
        var mockAdif  = Substitute.For<IAdifLogWriter>();
        mockAdif.AppendQsoAsync(Arg.Any<QsoRecord>()).Returns(Task.CompletedTask);

        var (sut, eventBus, _, ptt, channel, stopCts) = BuildIsolatedSut(
            txCfg, watchdogDuration: TimeSpan.FromSeconds(30), adifLog: mockAdif,
            catState: catState, appConfig: appConfig);

        await sut.StartAsync(stopCts.Token);

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, $"CQ {PartnerCall} {PartnerGrid}")]));
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", +5, 0.1, AudioFreqHz, $"{OurCallsign} {PartnerCall} +05")]));
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(3));

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [new DecodeResult("12:00:00", +5, 0.1, AudioFreqHz, $"{OurCallsign} {PartnerCall} RR73")]));
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

    [Fact(DisplayName = "D-013 AC-4: end-to-end — CAT connected on 20m writes <BAND:3>20m to ADIF.log, not stale 40m")]
    public async Task QsoComplete_CatConnectedOn20m_AdifFileHasCorrectBand()
    {
        var tempDir = Path.Combine(Path.GetTempPath(), "openwsfz-d013-test-" + Path.GetRandomFileName());
        Directory.CreateDirectory(tempDir);
        try
        {
            var txCfg = new TxConfig
            {
                AutoAnswer      = true,
                Callsign        = OurCallsign,
                Grid            = OurGrid,
                RetryCount      = 3,
                WatchdogMinutes = 1,
                QsoConfirmation = false,
            };
            var allTxtPath = Path.Combine(tempDir, "ALL.TXT");
            var appConfig  = new AppConfig() with
            {
                DecodeLog = new DecodeLogConfig
                {
                    Enabled          = true,
                    Path             = allTxtPath,
                    DialFrequencyMHz = 7.100, // stale: 40m — must NOT end up in the file
                },
            };
            var catState  = new StubCatState(14.074); // live: 20m — must end up in the file
            var store     = Substitute.For<IConfigStore>();
            store.Current.Returns(appConfig with { Tx = txCfg });
            store.SaveAsync(Arg.Any<AppConfig>(), Arg.Any<CancellationToken>())
                 .Returns(Task.CompletedTask);
            var realAdifLog = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);

            var ptt = Substitute.For<IPttController>();
            ptt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
            ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

            var channel = Channel.CreateUnbounded<DecodeBatch>();
            var stopCts = new CancellationTokenSource();
            var sut = new QsoAnswererService(
                channel.Reader, store, ptt, new TxEventBus(),
                realAdifLog, new AudioOffsetEventBus(),
                NullLogger<QsoAnswererService>.Instance,
                watchdogDurationOverride: TimeSpan.FromSeconds(30),
                catState: catState);

            await sut.StartAsync(stopCts.Token);

            channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
                [new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, $"CQ {PartnerCall} {PartnerGrid}")]));
            await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));

            channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
                [new DecodeResult("12:00:00", +5, 0.1, AudioFreqHz, $"{OurCallsign} {PartnerCall} +05")]));
            await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(3));

            channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
                [new DecodeResult("12:00:00", +5, 0.1, AudioFreqHz, $"{OurCallsign} {PartnerCall} RR73")]));
            await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromSeconds(5));

            await stopCts.CancelAsync();
            await sut.StopAsync(CancellationToken.None);
            await ptt.DisposeAsync();

            var adifPath = Path.Combine(tempDir, "ADIF.log");
            File.Exists(adifPath).Should().BeTrue("the completed QSO must have been written to ADIF.log");
            var content = await File.ReadAllTextAsync(adifPath);
            content.Should().Contain("<BAND:3>20m", "the live CAT frequency (20m) must win, not the stale config value");
            content.Should().NotContain("<BAND:3>40m", "the stale config-frozen band must never be written while CAT is connected");
        }
        finally
        {
            try { Directory.Delete(tempDir, recursive: true); } catch { /* best-effort */ }
        }
    }

    // ── D-CALLER-013: late-start guard (MaxLateStartSeconds = 1.5 s) ─────────

    /// <summary>
    /// Controllable <see cref="TimeProvider"/> used by D-CALLER-013 tests so the late-start
    /// guard can be exercised without sleeping through real 15-second FT8 windows.
    /// </summary>
    private sealed class FakeTimeProvider(DateTimeOffset initial) : TimeProvider
    {
        public DateTimeOffset UtcNow { get; set; } = initial;
        public override DateTimeOffset GetUtcNow() => UtcNow;
    }

    /// <summary>
    /// Builds an isolated <see cref="QsoAnswererService"/> with both a watchdog override and
    /// a <see cref="FakeTimeProvider"/>, plus a store whose SaveAsync is a no-op.
    /// </summary>
    private static (QsoAnswererService sut, IPttController ptt,
                    Channel<DecodeBatch> channel, CancellationTokenSource stopCts)
        BuildLateStartSut(FakeTimeProvider fakeTime)
    {
        var ptt = Substitute.For<IPttController>();
        ptt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var store = Substitute.For<IConfigStore>();
        store.Current.Returns(new AppConfig() with
        {
            Tx = new TxConfig
            {
                AutoAnswer      = true,
                Callsign        = OurCallsign,
                Grid            = OurGrid,
                RetryCount      = 2,
                WatchdogMinutes = 4,
            }
        });
        store.SaveAsync(Arg.Any<AppConfig>(), Arg.Any<CancellationToken>())
             .Returns(Task.CompletedTask);

        var channel = Channel.CreateUnbounded<DecodeBatch>();
        var adifLog = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);
        var sut     = new QsoAnswererService(
            channel.Reader, store, ptt, new TxEventBus(),
            adifLog, new AudioOffsetEventBus(),
            NullLogger<QsoAnswererService>.Instance,
            watchdogDurationOverride: TimeSpan.FromSeconds(30),
            timeProvider: fakeTime);

        return (sut, ptt, channel, new CancellationTokenSource());
    }

    [Fact(DisplayName = "D-CALLER-013 A: Pending target — late click (5 s in) is deferred; fires at next occurrence")]
    public async Task PendingTarget_LateStart_IsDeferred_ThenFiresNextCycle()
    {
        // FakeTime = 5 s into the :00 A-phase window (17:30:05).
        // RoundDownTo15s(17:30:05) = 17:30:00 → secondsIntoWindow = 5.0 > 1.5 → late.
        var fakeTime = new FakeTimeProvider(
            new DateTimeOffset(2026, 6, 27, 17, 30, 5, TimeSpan.Zero));
        var (sut, ptt, channel, stopCts) = BuildLateStartSut(fakeTime);
        await sut.StartAsync(stopCts.Token);

        // Arm pending target: CQ at B-phase (:15) → answer phase is A (:00/:30).
        await sut.AnswerCqAsync(PartnerCall, AudioFreqHz,
            new DateTimeOffset(2026, 6, 27, 17, 29, 15, TimeSpan.Zero),
            CancellationToken.None);
        sut._wakeupChannel.Reader.TryRead(out _); // drain wakeup to prevent early fire

        // Batch 1: CycleStart :45 (B-phase) → +15 s = :00 A-phase ✓ (phase check passes).
        // FakeTime is 5 s into the A-phase window → late-start guard fires → defer.
        channel.Writer.TryWrite(new DecodeBatch(
            new DateTimeOffset(2026, 6, 27, 17, 29, 45, TimeSpan.Zero),
            Array.Empty<DecodeResult>()));
        await Task.Delay(300);

        sut.State.Should().Be(QsoState.Idle,
            "late-start guard must defer TX and leave state Idle");
        await ptt.DidNotReceive().KeyDownAsync(Arg.Any<CancellationToken>());

        // Advance FakeTime to 0.5 s into the next A-phase window (17:30:30.5).
        // 0.5 s ≤ 1.5 s → guard passes → TX must fire.
        fakeTime.UtcNow = new DateTimeOffset(2026, 6, 27, 17, 30, 30, 500, TimeSpan.Zero);

        // Batch 2: CycleStart :15 (B-phase) → +15 s = :30 A-phase ✓ (same phase, next occurrence).
        channel.Writer.TryWrite(new DecodeBatch(
            new DateTimeOffset(2026, 6, 27, 17, 30, 15, TimeSpan.Zero),
            Array.Empty<DecodeResult>()));

        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));
        await ptt.Received(1).KeyDownAsync(Arg.Any<CancellationToken>());

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "D-CALLER-013 B: Pending target — timely click (0.5 s in) fires immediately")]
    public async Task PendingTarget_TimelyStart_FiresImmediately()
    {
        // FakeTime = 0.5 s into the :00 A-phase window.
        // 0.5 s ≤ 1.5 s → guard does not defer → TX fires on the first correct-phase batch.
        var fakeTime = new FakeTimeProvider(
            new DateTimeOffset(2026, 6, 27, 17, 30, 0, 500, TimeSpan.Zero));
        var (sut, ptt, channel, stopCts) = BuildLateStartSut(fakeTime);
        await sut.StartAsync(stopCts.Token);

        // Arm pending target: CQ at B-phase (:15) → answer phase is A (:00/:30).
        await sut.AnswerCqAsync(PartnerCall, AudioFreqHz,
            new DateTimeOffset(2026, 6, 27, 17, 29, 15, TimeSpan.Zero),
            CancellationToken.None);
        sut._wakeupChannel.Reader.TryRead(out _); // drain wakeup

        // Batch: CycleStart :45 (B-phase) → +15 s = :00 A-phase ✓.
        // FakeTime is 0.5 s in → guard passes → TX fires immediately.
        channel.Writer.TryWrite(new DecodeBatch(
            new DateTimeOffset(2026, 6, 27, 17, 29, 45, TimeSpan.Zero),
            Array.Empty<DecodeResult>()));

        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));
        await ptt.Received(1).KeyDownAsync(Arg.Any<CancellationToken>());

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "D-CALLER-013 C: Jump-in — late double-click (5 s in) is deferred; fires at next occurrence")]
    public async Task JumpIn_LateStart_IsDeferred_ThenFiresNextCycle()
    {
        // FakeTime = 5 s into the :00 A-phase window → late for A-phase TX.
        var fakeTime = new FakeTimeProvider(
            new DateTimeOffset(2026, 6, 27, 17, 30, 5, TimeSpan.Zero));
        var (sut, ptt, channel, stopCts) = BuildLateStartSut(fakeTime);
        await sut.StartAsync(stopCts.Token);

        // EngageAtAsync: partner decoded at B-phase (:15) → _jumpIsAPhase = !B = A.
        await sut.EngageAtAsync(
            PartnerCall, AudioFreqHz,
            new DateTimeOffset(2026, 6, 27, 17, 29, 15, TimeSpan.Zero), // their B-phase decode
            EngagePoint.SendReport,
            CancellationToken.None);
        sut._wakeupChannel.Reader.TryRead(out _); // drain wakeup

        // Batch 1: CycleStart :45 (B-phase) → +15 s = :00 A-phase ✓ (phase check passes).
        // FakeTime is 5 s into the A-phase window → late-start guard fires → defer.
        channel.Writer.TryWrite(new DecodeBatch(
            new DateTimeOffset(2026, 6, 27, 17, 29, 45, TimeSpan.Zero),
            Array.Empty<DecodeResult>()));
        await Task.Delay(300);

        sut.State.Should().Be(QsoState.Idle,
            "late-start guard must defer jump-in TX and leave state Idle");
        await ptt.DidNotReceive().KeyDownAsync(Arg.Any<CancellationToken>());

        // Advance FakeTime to 0.3 s into the next A-phase window.
        fakeTime.UtcNow = new DateTimeOffset(2026, 6, 27, 17, 30, 30, 300, TimeSpan.Zero);

        // Batch 2: same phase, next occurrence → guard passes → TX fires.
        channel.Writer.TryWrite(new DecodeBatch(
            new DateTimeOffset(2026, 6, 27, 17, 30, 15, TimeSpan.Zero),
            Array.Empty<DecodeResult>()));

        // Jump-in at SendReport enters WaitRr73 (transmits R+00 then waits for RR73).
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(3));
        await ptt.Received(1).KeyDownAsync(Arg.Any<CancellationToken>());

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "D-CALLER-013 D: Jump-in — timely double-click (0.2 s in) fires immediately")]
    public async Task JumpIn_TimelyStart_FiresImmediately()
    {
        // FakeTime = 0.2 s into the :00 A-phase window.
        // 0.2 s ≤ 1.5 s → guard does not defer → TX fires on the first correct-phase batch.
        var fakeTime = new FakeTimeProvider(
            new DateTimeOffset(2026, 6, 27, 17, 30, 0, 200, TimeSpan.Zero));
        var (sut, ptt, channel, stopCts) = BuildLateStartSut(fakeTime);
        await sut.StartAsync(stopCts.Token);

        // EngageAtAsync: partner decoded at B-phase (:15) → _jumpIsAPhase = A.
        await sut.EngageAtAsync(
            PartnerCall, AudioFreqHz,
            new DateTimeOffset(2026, 6, 27, 17, 29, 15, TimeSpan.Zero),
            EngagePoint.SendReport,
            CancellationToken.None);
        sut._wakeupChannel.Reader.TryRead(out _); // drain wakeup

        // Batch: CycleStart :45 (B-phase) → +15 s = :00 A-phase ✓.
        // FakeTime is 0.2 s in → guard passes → TX fires immediately.
        channel.Writer.TryWrite(new DecodeBatch(
            new DateTimeOffset(2026, 6, 27, 17, 29, 45, TimeSpan.Zero),
            Array.Empty<DecodeResult>()));

        // Jump-in at SendReport: transmit R+00, enter WaitRr73.
        await WaitForStateAsync(sut, QsoState.WaitRr73, timeout: TimeSpan.FromSeconds(3));
        await ptt.Received(1).KeyDownAsync(Arg.Any<CancellationToken>());

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    // ── decode-panel-filtering: automation gating (tasks 3.2–3.4) ────────────

    /// <summary>Simple mutable <see cref="IDecodeFilterStore"/> test double — no broadcast, just state.</summary>
    private sealed class MutableDecodeFilterStore : IDecodeFilterStore
    {
        public DecodeFilterState Current { get; private set; } = DecodeFilterState.Unfiltered;
        public void Set(DecodeFilterState state) => Current = state;
    }

    private static DecodeResult MakeCq(string callsign, string grid, WorkedBeforeState contactState)
        => new(
            Time:         "12:00:00",
            Snr:          -5,
            Dt:           0.1,
            FreqHz:       AudioFreqHz,
            Message:      $"CQ {callsign} {grid}",
            WorkedBefore: WorkedBeforeInfo.None with { Contact = contactState });

    private async Task<(QsoAnswererService Sut, IPttController Ptt, Channel<DecodeBatch> Channel,
                         CancellationTokenSource StopCts, MutableDecodeFilterStore FilterStore)>
        BuildFilteredSutAsync()
    {
        var store = Substitute.For<IConfigStore>();
        store.Current.Returns(new AppConfig() with
        {
            Tx = new TxConfig
            {
                AutoAnswer      = true,
                Callsign        = OurCallsign,
                Grid            = OurGrid,
                RetryCount      = 2,
                WatchdogMinutes = 4,
            }
        });
        store.SaveAsync(Arg.Any<AppConfig>(), Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var ptt = Substitute.For<IPttController>();
        ptt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var channel     = Channel.CreateUnbounded<DecodeBatch>();
        var adifLog     = new AdifLogWriter(store, NullLogger<AdifLogWriter>.Instance);
        var filterStore = new MutableDecodeFilterStore();
        var earlyInWindow = new FakeTimeProvider(
            new DateTimeOffset(2026, 1, 1, 0, 0, 0, TimeSpan.Zero));
        var sut = new QsoAnswererService(channel.Reader, store, ptt, new TxEventBus(),
                      adifLog, new AudioOffsetEventBus(), NullLogger<QsoAnswererService>.Instance,
                      watchdogDurationOverride: TimeSpan.FromMinutes(4),
                      timeProvider: earlyInWindow,
                      catState: null,
                      decodeFilterStore: filterStore);

        var stopCts = new CancellationTokenSource();
        await sut.StartAsync(stopCts.Token);

        return (sut, ptt, channel, stopCts, filterStore);
    }

    [Fact(DisplayName = "decode-panel-filtering: filtered-out CQ is skipped, next non-filtered CQ engaged instead")]
    public async Task Idle_FilteredOutCq_SkippedInFavourOfNextCq()
    {
        var (sut, ptt, channel, stopCts, filterStore) = await BuildFilteredSutAsync();

        // Exclude ThisBand on the Contact axis — Q1TST (ThisBand) is filtered out;
        // Q2ABC (Never, via WorkedBeforeInfo.None) passes.
        filterStore.Set(new DecodeFilterState(
            ContactStates: new HashSet<WorkedBeforeState> { WorkedBeforeState.Never, WorkedBeforeState.DifferentBand }));

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
        [
            MakeCq(PartnerCall, PartnerGrid, WorkedBeforeState.ThisBand),  // filtered out
            MakeCq("Q2ABC", "KP20", WorkedBeforeState.Never),              // not filtered out
        ]));

        await WaitForStateAsync(sut, QsoState.WaitReport);
        sut.Partner.Should().Be("Q2ABC", "the filtered-out CQ must be skipped entirely");

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "decode-panel-filtering: all-filtered-out cycle behaves identically to an empty cycle")]
    public async Task Idle_AllCqsFilteredOut_StaysIdleNoTransmit()
    {
        var (sut, ptt, channel, stopCts, filterStore) = await BuildFilteredSutAsync();

        filterStore.Set(new DecodeFilterState(
            ContactStates: new HashSet<WorkedBeforeState> { WorkedBeforeState.Never, WorkedBeforeState.DifferentBand }));

        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
        [
            MakeCq(PartnerCall, PartnerGrid, WorkedBeforeState.ThisBand), // filtered out — only CQ in cycle
        ]));
        await Task.Delay(300);

        sut.State.Should().Be(QsoState.Idle,
            "a cycle where every CQ is filtered out must behave identically to a cycle with no CQs");
        await ptt.DidNotReceive().KeyDownAsync(Arg.Any<CancellationToken>());

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "decode-panel-filtering: filter change after engagement does not abort an in-progress QSO")]
    public async Task WaitReport_FilterChangedAfterEngagement_QsoContinuesUnaffected()
    {
        var (sut, ptt, channel, stopCts, filterStore) = await BuildFilteredSutAsync();

        // Unfiltered at engagement time — Q1TST is answered normally.
        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
        [
            MakeCq(PartnerCall, PartnerGrid, WorkedBeforeState.Never),
        ]));
        await WaitForStateAsync(sut, QsoState.WaitReport);
        sut.Partner.Should().Be(PartnerCall);

        // Now change the filter so the active partner would be filtered out if re-evaluated.
        filterStore.Set(new DecodeFilterState(
            ContactStates: new HashSet<WorkedBeforeState> { WorkedBeforeState.Never, WorkedBeforeState.DifferentBand }));

        // Partner sends a signal report — the QSO must proceed exactly as if the filter had
        // never changed, because the filter is not re-checked once engagement has begun.
        channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [Make($"{OurCallsign} {PartnerCall} -05")]));

        await WaitForStateAsync(sut, QsoState.WaitRr73);
        sut.Partner.Should().Be(PartnerCall, "an in-progress QSO must not be aborted by a filter change");

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }

    [Fact(DisplayName = "decode-panel-filtering: no IDecodeFilterStore supplied (null) behaves as fully unfiltered")]
    public async Task Idle_NoFilterStoreSupplied_BehavesAsUnfiltered()
    {
        // The shared _sut (InitializeAsync) is constructed without a decodeFilterStore argument.
        _channel.Writer.TryWrite(new DecodeBatch(DateTimeOffset.UtcNow,
            [MakeCq(PartnerCall, PartnerGrid, WorkedBeforeState.ThisBand)]));

        await WaitForStateAsync(_sut!, QsoState.WaitReport);
        _sut!.Partner.Should().Be(PartnerCall,
            "a null IDecodeFilterStore must impose no filtering — no regression for callers not yet updated");
    }
}
