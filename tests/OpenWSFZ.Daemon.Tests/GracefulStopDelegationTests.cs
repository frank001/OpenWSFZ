using System.Threading.Channels;
using FluentAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using NSubstitute;
using OpenWSFZ.Abstractions;
using OpenWSFZ.TestSupport;
using OpenWSFZ.Web;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Targeted unit tests for the two <c>qso-controller</c> spec scenarios this change adds
/// beyond <see cref="QsoCallerService.GracefulStopAsync"/> itself (already covered in depth
/// by <see cref="QsoCallerServiceTests"/>):
/// <list type="bullet">
/// <item><see cref="QsoAnswererService"/>'s <c>GracefulStopAsync</c> is the default
///   no-op interface implementation.</item>
/// <item><see cref="QsoControllerRouter.GracefulStopAsync"/> forwards to whichever
///   controller is currently active.</item>
/// </list>
/// Not a general-purpose <c>QsoControllerRouter</c> test suite — no such suite exists yet
/// for the router's pre-existing surface (<c>AbortAsync</c>, <c>SwitchToCallerAsync</c>, etc.);
/// that gap predates this change and is out of scope here.
///
/// NFR-021: all callsigns use ITU-unallocated Q-prefix.
/// </summary>
[Trait("Category", "Unit")]
public sealed class GracefulStopDelegationTests
{
    private const string OurCallsign = "Q1OFZ";
    private const string OurGrid     = "JO33";

    [Fact(DisplayName = "qso-controller: QsoAnswererService.GracefulStopAsync is a no-op")]
    public async Task QsoAnswererService_GracefulStopAsync_IsNoOp()
    {
        var ptt      = Substitute.For<IPttController>();
        var store    = Substitute.For<IConfigStore>();
        store.Current.Returns(new AppConfig());
        var eventBus = Substitute.For<ITxEventBus>();
        var adifLog  = Substitute.For<IAdifLogWriter>();

        var answerer = new QsoAnswererService(
            Channel.CreateUnbounded<DecodeBatch>().Reader,
            store, ptt, eventBus, adifLog, new AudioOffsetEventBus(),
            NullLogger<QsoAnswererService>.Instance);

        var stateBefore   = answerer.State;
        var partnerBefore = answerer.Partner;

        // Default interface methods are not inherited into the implementing class's own
        // member list — must call through the interface reference to reach the default body.
        IQsoController controller = answerer;
        await controller.GracefulStopAsync();

        answerer.State.Should().Be(stateBefore, "the default no-op must not alter State");
        answerer.Partner.Should().Be(partnerBefore, "the default no-op must not alter Partner");
        await ptt.DidNotReceive().KeyUpAsync(Arg.Any<CancellationToken>());
    }

    [Fact(DisplayName = "qso-controller: QsoControllerRouter.GracefulStopAsync delegates to the active (Caller) controller")]
    public async Task QsoControllerRouter_GracefulStopAsync_DelegatesToActiveCaller()
    {
        var ptt = Substitute.For<IPttController>();
        ptt.KeyDownAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);
        ptt.KeyUpAsync(Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var tx = new TxConfig
        {
            AutoAnswer      = true,
            Callsign        = OurCallsign,
            Grid            = OurGrid,
            Role            = TxRole.Caller,
            RetryCount      = 3,
            WatchdogMinutes = 4,
        };
        var store = Substitute.For<IConfigStore>();
        store.Current.Returns(new AppConfig() with { Tx = tx });
        store.SaveAsync(Arg.Any<AppConfig>(), Arg.Any<CancellationToken>()).Returns(Task.CompletedTask);

        var eventBus = Substitute.For<ITxEventBus>();
        var adifLog  = Substitute.For<IAdifLogWriter>();
        adifLog.AppendQsoAsync(Arg.Any<QsoRecord>()).Returns(Task.CompletedTask);

        var callerChannel = Channel.CreateUnbounded<DecodeBatch>();
        var answerer = new QsoAnswererService(
            Channel.CreateUnbounded<DecodeBatch>().Reader,
            store, ptt, eventBus, adifLog, new AudioOffsetEventBus(),
            NullLogger<QsoAnswererService>.Instance,
            watchdogDurationOverride: TimeSpan.FromSeconds(30));
        var caller = new QsoCallerService(
            callerChannel.Reader,
            store, ptt, eventBus, adifLog, new AudioOffsetEventBus(),
            NullLogger<QsoCallerService>.Instance,
            watchdogDurationOverride: TimeSpan.FromSeconds(30));

        var router = new QsoControllerRouter(
            answerer, caller, store, eventBus, NullLogger<QsoControllerRouter>.Instance);

        using var stopCts = new CancellationTokenSource();
        await answerer.StartAsync(stopCts.Token);
        await caller.StartAsync(stopCts.Token);

        // tx.Role = Caller ⇒ the router's configured (and initial active) role is Caller.
        router.Role.Should().Be(QsoRole.Caller,
            "the router's active role follows the configured TxRole at construction");

        // Drive the caller (via its own decode channel) into WaitAnswer.
        callerChannel.Writer.TryWrite(new DecodeBatch(
            DateTimeOffset.UtcNow,
            [new DecodeResult(Time: "12:00:00", Snr: -5, Dt: 0.1, FreqHz: 1500, Message: "CQ Q2NOISE JO00")]));

        await Poll.WaitForEqualAsync(() => router.State, QsoState.WaitReport,
            timeout: TimeSpan.FromSeconds(5));
        router.State.Should().Be(QsoState.WaitReport,
            "router.State must proxy the active (Caller) controller's state");

        // Act — call GracefulStopAsync on the ROUTER, not on the caller directly.
        await router.GracefulStopAsync();

        await Poll.WaitForEqualAsync(() => router.State, QsoState.Idle,
            timeout: TimeSpan.FromSeconds(5));

        router.State.Should().Be(QsoState.Idle,
            "QsoControllerRouter.GracefulStopAsync must forward to the active controller's " +
            "GracefulStopAsync — its effect (return to Idle) must be observable through the router");

        await stopCts.CancelAsync();
        await answerer.StopAsync(CancellationToken.None);
        await caller.StopAsync(CancellationToken.None);
        await ptt.DisposeAsync();
    }
}
