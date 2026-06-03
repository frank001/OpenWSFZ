using FluentAssertions;
using NSubstitute;
using NSubstitute.ExceptionExtensions;
using OpenWSFZ.Rig;
using OpenWSFZ.Rig.Internal;
using System.Net.Sockets;
using Xunit;

namespace OpenWSFZ.Rig.Tests;

/// <summary>
/// Unit tests for <see cref="RigctldConnection"/> (FR-031, FR-032).
/// A stub <see cref="ITcpConnection"/> is injected so no real rigctld is required.
/// </summary>
[Trait("Category", "Unit")]
public sealed class RigctldConnectionTests
{
    private const string Host = "127.0.0.1";
    private const int    Port = 4532;

    // ── ConnectAsync ─────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-032: RigctldConnection ConnectAsync opens TCP and IsConnected becomes true")]
    public async Task ConnectAsync_OpensConnection_IsConnectedTrue()
    {
        var tcp = Substitute.For<ITcpConnection>();
        tcp.IsConnected.Returns(true);
        var sut = new RigctldConnection(Host, Port, tcp);

        await sut.ConnectAsync();

        await tcp.Received(1).ConnectAsync(Host, Port, Arg.Any<CancellationToken>());
        sut.IsConnected.Should().BeTrue();
    }

    [Fact(DisplayName = "FR-032: RigctldConnection ConnectAsync propagates SocketException when rigctld unreachable")]
    public async Task ConnectAsync_ConnectionRefused_Throws()
    {
        var tcp = Substitute.For<ITcpConnection>();
        tcp.ConnectAsync(Arg.Any<string>(), Arg.Any<int>(), Arg.Any<CancellationToken>())
           .ThrowsAsync(new SocketException((int)SocketError.ConnectionRefused));
        var sut = new RigctldConnection(Host, Port, tcp);

        var act = () => sut.ConnectAsync();

        await act.Should().ThrowAsync<SocketException>();
        sut.IsConnected.Should().BeFalse();
    }

    // ── GetDialFrequencyMhzAsync ─────────────────────────────────────────────

    [Fact(DisplayName = "FR-032: RigctldConnection parses 14074000 → 14.074 MHz")]
    public async Task GetDialFrequencyMhzAsync_ValidResponse_ReturnsMhz()
    {
        var tcp = Substitute.For<ITcpConnection>();
        tcp.ReceiveLineAsync(Arg.Any<CancellationToken>()).Returns("14074000");
        var sut = new RigctldConnection(Host, Port, tcp);

        var freq = await sut.GetDialFrequencyMhzAsync();

        freq.Should().BeApproximately(14.074, precision: 1e-9);
        await tcp.Received(1).SendAsync(@"\get_freq" + "\n", Arg.Any<CancellationToken>());
    }

    [Fact(DisplayName = "FR-032: RigctldConnection throws InvalidOperationException on RPRT error response")]
    public async Task GetDialFrequencyMhzAsync_RprtResponse_Throws()
    {
        var tcp = Substitute.For<ITcpConnection>();
        tcp.ReceiveLineAsync(Arg.Any<CancellationToken>()).Returns("RPRT -1");
        var sut = new RigctldConnection(Host, Port, tcp);

        var act = () => sut.GetDialFrequencyMhzAsync();

        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("*RPRT*");
    }

    [Fact(DisplayName = "FR-032: RigctldConnection throws InvalidOperationException on non-numeric response")]
    public async Task GetDialFrequencyMhzAsync_NonNumericResponse_Throws()
    {
        var tcp = Substitute.For<ITcpConnection>();
        tcp.ReceiveLineAsync(Arg.Any<CancellationToken>()).Returns("not-a-number");
        var sut = new RigctldConnection(Host, Port, tcp);

        var act = () => sut.GetDialFrequencyMhzAsync();

        await act.Should().ThrowAsync<InvalidOperationException>();
    }

    [Fact(DisplayName = "FR-032: RigctldConnection throws TimeoutException on receive timeout")]
    public async Task GetDialFrequencyMhzAsync_ReceiveTimeout_Throws()
    {
        var tcp = Substitute.For<ITcpConnection>();
        tcp.ReceiveLineAsync(Arg.Any<CancellationToken>())
           .ThrowsAsync(new TimeoutException("rigctld: no response within 500 ms."));
        var sut = new RigctldConnection(Host, Port, tcp);

        var act = () => sut.GetDialFrequencyMhzAsync();

        await act.Should().ThrowAsync<TimeoutException>();
    }

    // ── DisconnectAsync / Dispose ─────────────────────────────────────────────

    [Fact(DisplayName = "FR-032: RigctldConnection DisconnectAsync closes connection and IsConnected becomes false")]
    public async Task DisconnectAsync_ClosesConnection()
    {
        var tcp = Substitute.For<ITcpConnection>();
        tcp.IsConnected.Returns(true);
        var sut = new RigctldConnection(Host, Port, tcp);
        // Simulate a successful connect first.
        await sut.ConnectAsync();

        await sut.DisconnectAsync();

        tcp.Received(1).Close();
        sut.IsConnected.Should().BeFalse();
    }

    [Fact(DisplayName = "FR-032: RigctldConnection Dispose closes and disposes TCP")]
    public void Dispose_ClosesAndDisposesTcp()
    {
        var tcp = Substitute.For<ITcpConnection>();
        var sut = new RigctldConnection(Host, Port, tcp);

        sut.Dispose();

        tcp.Received().Close();
        tcp.Received(1).Dispose();
    }

    // ── SetDialFrequencyMhzAsync (FR-045) ─────────────────────────────────────

    [Theory(DisplayName = "FR-045: RigctldConnection.SetDialFrequencyMhzAsync sends correct set_freq command")]
    [InlineData(7.074,   @"\set_freq 7074000" + "\n")]
    [InlineData(14.074,  @"\set_freq 14074000" + "\n")]
    [InlineData(0.001,   @"\set_freq 1000" + "\n")]
    public async Task SetDialFrequencyMhzAsync_SendsCorrectCommand(double freqMHz, string expected)
    {
        var tcp = Substitute.For<ITcpConnection>();
        var sut = new RigctldConnection(Host, Port, tcp);

        await sut.SetDialFrequencyMhzAsync(freqMHz);

        await tcp.Received(1).SendAsync(expected, Arg.Any<CancellationToken>());
    }

    [Fact(DisplayName = "FR-045: RigctldConnection.SetDialFrequencyMhzAsync does not await a read-back")]
    public async Task SetDialFrequencyMhzAsync_DoesNotReadBack()
    {
        var tcp = Substitute.For<ITcpConnection>();
        var sut = new RigctldConnection(Host, Port, tcp);

        await sut.SetDialFrequencyMhzAsync(14.074);

        // ReceiveLineAsync must never be called.
        await tcp.DidNotReceive().ReceiveLineAsync(Arg.Any<CancellationToken>());
    }
}
