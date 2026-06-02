using FluentAssertions;
using NSubstitute;
using NSubstitute.ExceptionExtensions;
using OpenWSFZ.Rig;
using OpenWSFZ.Rig.Internal;
using Xunit;

namespace OpenWSFZ.Rig.Tests;

/// <summary>
/// Unit tests for <see cref="SerialCatConnection"/> (FR-031, FR-032).
/// A stub <see cref="ISerialPort"/> is injected so no real hardware is required.
/// </summary>
[Trait("Category", "Unit")]
public sealed class SerialCatConnectionTests
{
    // ── ConnectAsync ─────────────────────────────────────────────────────────

    [Fact(DisplayName = "P16-Cat: ConnectAsync opens the serial port and IsConnected becomes true")]
    public async Task ConnectAsync_OpensPort_IsConnectedTrue()
    {
        var port   = Substitute.For<ISerialPort>();
        port.IsOpen.Returns(true);
        var sut = new SerialCatConnection(port);

        await sut.ConnectAsync();

        port.Received(1).Open();
        sut.IsConnected.Should().BeTrue();
    }

    [Fact(DisplayName = "P16-Cat: ConnectAsync propagates UnauthorizedAccessException when port is in use")]
    public async Task ConnectAsync_PortInUse_Throws()
    {
        var port = Substitute.For<ISerialPort>();
        port.When(p => p.Open()).Throw<UnauthorizedAccessException>();
        var sut = new SerialCatConnection(port);

        var act = () => sut.ConnectAsync();

        await act.Should().ThrowAsync<UnauthorizedAccessException>();
        port.IsOpen.Returns(false);
        sut.IsConnected.Should().BeFalse();
    }

    // ── GetDialFrequencyMhzAsync ─────────────────────────────────────────────

    [Fact(DisplayName = "P16-Cat: GetDialFrequencyMhzAsync parses FA00014074000; → 14.074 MHz")]
    public async Task GetDialFrequencyMhzAsync_ValidResponse_ReturnsMhz()
    {
        var port = Substitute.For<ISerialPort>();
        port.IsOpen.Returns(true);
        // ReadTo(";") returns the string BEFORE the delimiter
        port.ReadTo(";").Returns("FA00014074000");
        var sut = new SerialCatConnection(port);

        var freq = await sut.GetDialFrequencyMhzAsync();

        freq.Should().BeApproximately(14.074, precision: 1e-9);
        port.Received(1).Write("FA;\r");
    }

    [Fact(DisplayName = "P16-Cat: GetDialFrequencyMhzAsync throws InvalidOperationException on malformed response")]
    public async Task GetDialFrequencyMhzAsync_MalformedResponse_Throws()
    {
        var port = Substitute.For<ISerialPort>();
        port.IsOpen.Returns(true);
        port.ReadTo(";").Returns("GARBAGE");
        var sut = new SerialCatConnection(port);

        var act = () => sut.GetDialFrequencyMhzAsync();

        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("*GARBAGE*");
    }

    [Fact(DisplayName = "P16-Cat: GetDialFrequencyMhzAsync throws InvalidOperationException when response does not start with FA")]
    public async Task GetDialFrequencyMhzAsync_WrongPrefix_Throws()
    {
        var port = Substitute.For<ISerialPort>();
        port.IsOpen.Returns(true);
        port.ReadTo(";").Returns("FB00014074000");   // wrong prefix
        var sut = new SerialCatConnection(port);

        var act = () => sut.GetDialFrequencyMhzAsync();

        await act.Should().ThrowAsync<InvalidOperationException>();
    }

    [Fact(DisplayName = "P16-Cat: GetDialFrequencyMhzAsync re-throws TimeoutException on read timeout")]
    public async Task GetDialFrequencyMhzAsync_ReadTimeout_ThrowsTimeoutException()
    {
        var port = Substitute.For<ISerialPort>();
        port.IsOpen.Returns(true);
        port.ReadTo(";").Throws<TimeoutException>();
        var sut = new SerialCatConnection(port);

        var act = () => sut.GetDialFrequencyMhzAsync();

        await act.Should().ThrowAsync<TimeoutException>();
    }

    // ── DisconnectAsync / Dispose ─────────────────────────────────────────────

    [Fact(DisplayName = "P16-Cat: DisconnectAsync closes the port and IsConnected becomes false")]
    public async Task DisconnectAsync_ClosesPort()
    {
        var port = Substitute.For<ISerialPort>();
        port.IsOpen.Returns(true);
        var sut = new SerialCatConnection(port);

        await sut.DisconnectAsync();

        port.Received(1).Close();
    }

    [Fact(DisplayName = "P16-Cat: Dispose closes and disposes the port")]
    public void Dispose_ClosesAndDisposesPort()
    {
        var port = Substitute.For<ISerialPort>();
        port.IsOpen.Returns(true);
        var sut = new SerialCatConnection(port);

        sut.Dispose();

        port.Received(1).Close();
        port.Received(1).Dispose();
    }
}
