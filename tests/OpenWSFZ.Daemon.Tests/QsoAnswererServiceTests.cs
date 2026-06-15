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

    private readonly Channel<IReadOnlyList<DecodeResult>> _channel =
        Channel.CreateUnbounded<IReadOnlyList<DecodeResult>>();

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
        _sut    = new QsoAnswererService(_channel.Reader, store, _ptt, new TxEventBus(),
                      adifLog, NullLogger<QsoAnswererService>.Instance);
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

    private void Send(params DecodeResult[] results)
        => _channel.Writer.TryWrite(results);

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

        var channel  = Channel.CreateUnbounded<IReadOnlyList<DecodeResult>>();
        var adifLog  = new AdifLogWriter(disabledStore, NullLogger<AdifLogWriter>.Instance);
        var sut      = new QsoAnswererService(channel.Reader, disabledStore, pttDisabled,
                           new TxEventBus(), adifLog, NullLogger<QsoAnswererService>.Instance);

        using var stopCts = new CancellationTokenSource();
        await sut.StartAsync(stopCts.Token);

        // Send a CQ — must be completely ignored.
        channel.Writer.TryWrite([Make($"CQ {PartnerCall} {PartnerGrid}")]);
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

        var channel = Channel.CreateUnbounded<IReadOnlyList<DecodeResult>>();
        var adifLog = new AdifLogWriter(unconfiguredStore, NullLogger<AdifLogWriter>.Instance);
        var sut     = new QsoAnswererService(channel.Reader, unconfiguredStore, pttEmpty,
                          new TxEventBus(), adifLog, NullLogger<QsoAnswererService>.Instance);

        using var stopCts = new CancellationTokenSource();
        await sut.StartAsync(stopCts.Token);

        // A CQ arrives — must be suppressed because callsign/grid are empty.
        channel.Writer.TryWrite([Make($"CQ {PartnerCall} {PartnerGrid}")]);
        await Task.Delay(300);

        sut.State.Should().Be(QsoState.Idle,
            "empty callsign/grid must suppress TX even when auto-answer is enabled");
        await pttEmpty.DidNotReceive().KeyDownAsync(Arg.Any<CancellationToken>());

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await pttEmpty.DisposeAsync();
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

        // A-01: 4 silent cycles needed — cycle 1 is skipped (our own TX window);
        //       cycles 2 and 3 fire retries 1 and 2; cycle 4 exhausts the counter → abort.
        Send(Make("CQ Q2NOISE IO91")); // cycle 1: skip (A-01 guard)
        await Task.Delay(150);
        Send(Make("CQ Q2NOISE IO91")); // cycle 2: retry 1 TX
        await Task.Delay(150);         // let retry 1 TX complete
        Send(Make("CQ Q2NOISE IO91")); // cycle 3: retry 2 TX
        await Task.Delay(150);         // let retry 2 TX complete
        Send(Make("CQ Q2NOISE IO91")); // cycle 4: retry count exhausted → abort
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
}
