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

    [Fact(DisplayName = "FR-032: ConnectAsync opens the serial port and IsConnected becomes true")]
    public async Task ConnectAsync_OpensPort_IsConnectedTrue()
    {
        var port   = Substitute.For<ISerialPort>();
        port.IsOpen.Returns(true);
        var sut = new SerialCatConnection(port);

        await sut.ConnectAsync();

        port.Received(1).Open();
        sut.IsConnected.Should().BeTrue();
    }

    [Fact(DisplayName = "FR-032: ConnectAsync propagates UnauthorizedAccessException when port is in use")]
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

    [Fact(DisplayName = "FR-032: GetDialFrequencyMhzAsync parses FA00014074000; → 14.074 MHz")]
    public async Task GetDialFrequencyMhzAsync_ValidResponse_ReturnsMhz()
    {
        var port = Substitute.For<ISerialPort>();
        port.IsOpen.Returns(true);
        // ReadTo(";") returns the string BEFORE the delimiter
        port.ReadTo(";").Returns("FA00014074000");
        var sut = new SerialCatConnection(port);

        var freq = await sut.GetDialFrequencyMhzAsync();

        freq.Should().BeApproximately(14.074, precision: 1e-9);
        port.Received(1).Write("FA;");
    }

    [Fact(DisplayName = "FR-032: GetDialFrequencyMhzAsync parses FA007074000; (9-digit) → 7.074 MHz")]
    public async Task GetDialFrequencyMhzAsync_NineDigitResponse_ReturnsMhz()
    {
        // Regression: some rig families return 9 Hz digits rather than 11.
        // FA007074000; was observed in the wild (7.074 MHz, 40 m FT8 dial).
        var port = Substitute.For<ISerialPort>();
        port.IsOpen.Returns(true);
        port.ReadTo(";").Returns("FA007074000");
        var sut = new SerialCatConnection(port);

        var freq = await sut.GetDialFrequencyMhzAsync();

        freq.Should().BeApproximately(7.074, precision: 1e-9);
    }

    [Fact(DisplayName = "FR-032: GetDialFrequencyMhzAsync sends FA; without carriage return")]
    public async Task GetDialFrequencyMhzAsync_SendsCommandWithoutCarriageReturn()
    {
        // Regression: "FA;\r" causes Kenwood-compatible rigs to reply with a second
        // ?; error response (to the bare \r), which is then read on the next poll cycle.
        var port = Substitute.For<ISerialPort>();
        port.IsOpen.Returns(true);
        port.ReadTo(";").Returns("FA00014074000");
        var sut = new SerialCatConnection(port);

        await sut.GetDialFrequencyMhzAsync();

        port.Received(1).Write("FA;");
        port.DidNotReceive().Write(Arg.Is<string>(s => s.Contains('\r')));
    }

    [Fact(DisplayName = "FR-032: GetDialFrequencyMhzAsync throws InvalidOperationException when rig returns ? (command error)")]
    public async Task GetDialFrequencyMhzAsync_RigCommandError_Throws()
    {
        // Regression: a stale ?; in the receive buffer (from a prior \r-induced error
        // response) caused an alternating success/failure pattern.
        var port = Substitute.For<ISerialPort>();
        port.IsOpen.Returns(true);
        port.ReadTo(";").Returns("?");
        var sut = new SerialCatConnection(port);

        var act = () => sut.GetDialFrequencyMhzAsync();

        await act.Should().ThrowAsync<InvalidOperationException>()
            .WithMessage("*'?'*");
    }

    [Fact(DisplayName = "FR-032: GetDialFrequencyMhzAsync throws InvalidOperationException on malformed response")]
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

    [Fact(DisplayName = "FR-032: GetDialFrequencyMhzAsync throws InvalidOperationException when response does not start with FA")]
    public async Task GetDialFrequencyMhzAsync_WrongPrefix_Throws()
    {
        var port = Substitute.For<ISerialPort>();
        port.IsOpen.Returns(true);
        port.ReadTo(";").Returns("FB00014074000");   // wrong prefix
        var sut = new SerialCatConnection(port);

        var act = () => sut.GetDialFrequencyMhzAsync();

        await act.Should().ThrowAsync<InvalidOperationException>();
    }

    [Fact(DisplayName = "FR-032: GetDialFrequencyMhzAsync re-throws TimeoutException on read timeout")]
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

    [Fact(DisplayName = "FR-032: DisconnectAsync closes the port and IsConnected becomes false")]
    public async Task DisconnectAsync_ClosesPort()
    {
        var port = Substitute.For<ISerialPort>();
        port.IsOpen.Returns(true);
        var sut = new SerialCatConnection(port);

        await sut.DisconnectAsync();

        port.Received(1).Close();
    }

    [Fact(DisplayName = "FR-032: Dispose closes and disposes the port")]
    public void Dispose_ClosesAndDisposesPort()
    {
        var port = Substitute.For<ISerialPort>();
        port.IsOpen.Returns(true);
        var sut = new SerialCatConnection(port);

        sut.Dispose();

        port.Received(1).Close();
        port.Received(1).Dispose();
    }

    // ── SetDialFrequencyMhzAsync (FR-045) ─────────────────────────────────────

    [Theory(DisplayName = "FR-045: SetDialFrequencyMhzAsync writes correct FA set command")]
    [InlineData(7.074,  "FA00007074000;")]
    [InlineData(14.074, "FA00014074000;")]
    [InlineData(0.001,  "FA00000001000;")]
    public async Task SetDialFrequencyMhzAsync_WritesCorrectCommand(double freqMHz, string expected)
    {
        var port = Substitute.For<ISerialPort>();
        var sut  = new SerialCatConnection(port);

        await sut.SetDialFrequencyMhzAsync(freqMHz);

        port.Received(1).Write(expected);
    }

    // ── Buffer-flush guard (F-003) ────────────────────────────────────────────

    [Fact(DisplayName = "F-003: GetDialFrequencyMhzAsync discards the receive buffer before writing FA; (prevents stale-response pollution)")]
    public async Task GetDialFrequencyMhzAsync_DiscardsInBufferBeforeWritingCommand()
    {
        // Arrange — track call order via side-effects.
        var port      = Substitute.For<ISerialPort>();
        var callOrder = new List<string>();
        port.IsOpen.Returns(true);
        port.ReadTo(";").Returns("FA00014074000");
        port.When(p => p.DiscardInBuffer()).Do(_ => callOrder.Add("discard"));
        port.When(p => p.Write(Arg.Any<string>())).Do(_ => callOrder.Add("write"));

        var sut = new SerialCatConnection(port);

        // Act
        await sut.GetDialFrequencyMhzAsync();

        // Assert — exactly one discard, and it must precede the write.
        port.Received(1).DiscardInBuffer();
        callOrder.Should().Equal(
            new[] { "discard", "write" },
            because: "the receive buffer must be flushed before the FA; query is sent " +
                     "so that any rig response to a preceding SetDialFrequencyMhzAsync call " +
                     "does not pollute the read that follows (F-003)");
    }

    [Fact(DisplayName = "FR-045: SetDialFrequencyMhzAsync does not read back a confirmation")]
    public async Task SetDialFrequencyMhzAsync_DoesNotReadBack()
    {
        var port = Substitute.For<ISerialPort>();
        var sut  = new SerialCatConnection(port);

        await sut.SetDialFrequencyMhzAsync(14.074);

        // ReadTo must never be called — the method is fire-and-forget.
        port.DidNotReceive().ReadTo(Arg.Any<string>());
    }
}
