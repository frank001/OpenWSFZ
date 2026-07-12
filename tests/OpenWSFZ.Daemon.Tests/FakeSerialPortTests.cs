using FluentAssertions;
using OpenWSFZ.Rig.Internal;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for the <see cref="ISerialPort"/> RTS/DTR contract (FR-056, task 12.5),
/// exercised via <see cref="FakeSerialPort"/> — the hand-written test double
/// <c>SerialRtsDtrPttController</c>'s own unit tests (task 12.7) build on. Verifies the
/// double faithfully models independent, observable RTS/DTR line state before other
/// tests trust it.
/// </summary>
[Trait("Category", "Unit")]
public sealed class FakeSerialPortTests
{
    [Fact(DisplayName = "CatTx-Ptt: RtsEnable and DtrEnable both default to false")]
    public void Defaults_BothLinesFalse()
    {
        var port = new FakeSerialPort();

        port.RtsEnable.Should().BeFalse();
        port.DtrEnable.Should().BeFalse();
    }

    [Fact(DisplayName = "CatTx-Ptt: RtsEnable is independently settable and observable")]
    public void RtsEnable_SetTrue_ObservedTrue_DtrUnaffected()
    {
        var port = new FakeSerialPort();

        port.RtsEnable = true;

        port.RtsEnable.Should().BeTrue();
        port.DtrEnable.Should().BeFalse("setting RTS must not affect the independent DTR line");
    }

    [Fact(DisplayName = "CatTx-Ptt: DtrEnable is independently settable and observable")]
    public void DtrEnable_SetTrue_ObservedTrue_RtsUnaffected()
    {
        var port = new FakeSerialPort();

        port.DtrEnable = true;

        port.DtrEnable.Should().BeTrue();
        port.RtsEnable.Should().BeFalse("setting DTR must not affect the independent RTS line");
    }

    [Fact(DisplayName = "CatTx-Ptt: RtsEnable/DtrEnable can be de-asserted after being asserted")]
    public void Lines_CanBeToggledBackToFalse()
    {
        var port = new FakeSerialPort { RtsEnable = true, DtrEnable = true };

        port.RtsEnable = false;
        port.DtrEnable = false;

        port.RtsEnable.Should().BeFalse();
        port.DtrEnable.Should().BeFalse();
    }

    [Fact(DisplayName = "CatTx-Ptt: Open() sets IsOpen true; Close() sets IsOpen false and increments CloseCallCount")]
    public void OpenClose_TracksLifecycle()
    {
        var port = new FakeSerialPort();

        port.Open();
        port.IsOpen.Should().BeTrue();

        port.Close();
        port.IsOpen.Should().BeFalse();
        port.CloseCallCount.Should().Be(1);
    }

    [Fact(DisplayName = "CatTx-Ptt: Open() throws the configured ThrowOnOpen exception and IsOpen remains false")]
    public void Open_ThrowOnOpenConfigured_Throws()
    {
        var port = new FakeSerialPort { ThrowOnOpen = new UnauthorizedAccessException("port in use") };

        var act = () => port.Open();

        act.Should().Throw<UnauthorizedAccessException>().WithMessage("port in use");
        port.IsOpen.Should().BeFalse();
    }

    [Fact(DisplayName = "CatTx-Ptt: Write() records every write in order")]
    public void Write_RecordsHistoryInOrder()
    {
        var port = new FakeSerialPort();

        port.Write("first");
        port.Write("second");

        port.Written.Should().Equal("first", "second");
    }

    [Fact(DisplayName = "CatTx-Ptt: Dispose() increments DisposeCallCount")]
    public void Dispose_IncrementsCallCount()
    {
        var port = new FakeSerialPort();

        port.Dispose();

        port.DisposeCallCount.Should().Be(1);
    }
}
