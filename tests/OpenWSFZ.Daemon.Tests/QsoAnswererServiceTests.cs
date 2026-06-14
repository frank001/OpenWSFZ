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

    [Fact(DisplayName = "6.2: Service starts in Idle state with null partner")]
    public void InitialState_IsIdleWithNullPartner()
    {
        _sut!.State.Should().Be(QsoState.Idle);
        _sut!.Partner.Should().BeNull();
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

        // 3 silent cycles (initial + 2 retries = 3 batches total, then abort).
        Send(Make("CQ Q2NOISE IO91")); // noise — no match
        await Task.Delay(100);        // let retry 1 tx complete
        Send(Make("CQ Q2NOISE IO91")); // still no match
        await Task.Delay(100);
        Send(Make("CQ Q2NOISE IO91")); // retry 2 exhausted
        await WaitForStateAsync(_sut!, QsoState.Idle,
            timeout: TimeSpan.FromSeconds(5));
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
