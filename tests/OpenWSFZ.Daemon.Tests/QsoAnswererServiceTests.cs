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

    // ── Nested helpers ────────────────────────────────────────────────────────

    /// <summary>Creates a temporary directory that is deleted when disposed.</summary>
    private sealed class TempDirectory : IDisposable
    {
        public string Path { get; } = System.IO.Path.Combine(
            System.IO.Path.GetTempPath(),
            "openwsfz-test-" + System.IO.Path.GetRandomFileName());

        public TempDirectory() => Directory.CreateDirectory(Path);

        public void Dispose()
        {
            try { Directory.Delete(Path, recursive: true); } catch { /* best-effort */ }
        }
    }

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

        using var adifDir = new TempDirectory();
        var adifStore     = Substitute.For<IConfigStore>();
        adifStore.Current.Returns(store.Current with
        {
            DecodeLog = new DecodeLogConfig { Path = System.IO.Path.Combine(adifDir.Path, "ALL.TXT") }
        });
        var adifLog = new AdifLogWriter(adifStore, NullLogger<AdifLogWriter>.Instance);
        var channel = Channel.CreateUnbounded<IReadOnlyList<DecodeResult>>();
        var sut     = new QsoAnswererService(channel.Reader, store, racyPtt, new TxEventBus(),
                          adifLog, NullLogger<QsoAnswererService>.Instance);

        using var stopCts = new CancellationTokenSource();
        await sut.StartAsync(stopCts.Token);

        // Reach WaitReport.
        channel.Writer.TryWrite([new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz, $"CQ {PartnerCall} {PartnerGrid}")]);
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));

        // Trigger TxReport TX.
        channel.Writer.TryWrite([new DecodeResult("12:00:00", +5, 0.1, AudioFreqHz, $"{OurCallsign} {PartnerCall} +05")]);

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
        var channel = Channel.CreateUnbounded<IReadOnlyList<DecodeResult>>();

        var sut = new QsoAnswererService(channel.Reader, store, ptt, new TxEventBus(),
                      adifLog, NullLogger<QsoAnswererService>.Instance,
                      watchdogDurationOverride: watchdogDuration);

        using var stopCts = new CancellationTokenSource();
        await sut.StartAsync(stopCts.Token);

        // Trigger CQ answer → WaitReport.
        channel.Writer.TryWrite([new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz,
            $"CQ {PartnerCall} {PartnerGrid}")]);
        await WaitForStateAsync(sut, QsoState.WaitReport, timeout: TimeSpan.FromSeconds(3));

        // Feed noise continuously so retries keep cycling without pause.
        // With the D-008 fix:  watchdog fires ~300 ms after WaitReport → Idle by ~400 ms.
        // With the D-008 bug:  every retry resets the watchdog to 300 ms; the channel never
        //                      empties; Idle is never reached → WaitForStateAsync times out.
        using var feedCts = new CancellationTokenSource(TimeSpan.FromSeconds(2));
        var feedTask = Task.Run(async () =>
        {
            while (!feedCts.IsCancellationRequested)
            {
                channel.Writer.TryWrite([new DecodeResult("12:00:00", -5, 0.1, AudioFreqHz,
                    "CQ Q2NOISE IO91")]);
                try   { await Task.Delay(10, feedCts.Token); }
                catch (OperationCanceledException) { break; }
            }
        });

        // Deadline distinguishes the two paths (1 500 ms < 2 000 ms feeder window).
        // Fixed:  watchdog fires → Idle reached within ~300–500 ms even on a slow CI runner →
        //         WaitForStateAsync returns normally.
        // Buggy:  every retry resets the watchdog; Idle is never reached while feeder runs (2 s) →
        //         TimeoutException at 1 500 ms (safely below the 2 000 ms feeder window).
        // WaitForStateAsync throws on timeout, so reaching the next line is the assertion.
        await WaitForStateAsync(sut, QsoState.Idle, timeout: TimeSpan.FromMilliseconds(1500));

        // Cancel the feeder AFTER confirming Idle. No state assertion here: the continuous feeder
        // may have already queued another CQ that the service will answer, transitioning back to
        // TxAnswer before sut.State can be read — a spurious race, not a D-008 regression.
        feedCts.Cancel();
        await feedTask;

        await stopCts.CancelAsync();
        await sut.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }
}
