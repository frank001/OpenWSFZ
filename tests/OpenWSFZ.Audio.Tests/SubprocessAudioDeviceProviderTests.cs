using FluentAssertions;
using OpenWSFZ.Audio;
using OpenWSFZ.Abstractions;
using Xunit;

namespace OpenWSFZ.Audio.Tests;

public sealed class SubprocessAudioDeviceProviderTests
{
    // ── Task 7.1 ─────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-003: GetDevicesAsync returns empty list when subprocess exits non-zero")]
    public async Task GetDevicesAsync_ReturnsEmpty_WhenSubprocessExitsNonZero()
    {
        // Arrange: use a shell invocation that reliably exits 1 on all platforms.
        var (cmd, args) = OperatingSystem.IsWindows()
            ? ("cmd", new[] { "/c", "exit 1" })
            : ("/bin/sh", new[] { "-c", "exit 1" });

        var provider = new SubprocessAudioDeviceProvider(cmd, args, _ => [new AudioDeviceInfo("x", "x")]);

        // Act
        var devices = await provider.GetDevicesAsync();

        // Assert
        devices.Should().BeEmpty("a non-zero exit code must produce an empty list");
    }

    // ── Task 7.2 ─────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-003: GetDevicesAsync returns empty list when tool is absent")]
    public async Task GetDevicesAsync_ReturnsEmpty_WhenToolIsAbsent()
    {
        // Arrange: command that cannot possibly exist.
        var provider = new SubprocessAudioDeviceProvider(
            "__openwsfz_nonexistent_binary_xyz__",
            [],
            _ => [new AudioDeviceInfo("x", "x")]);

        // Act
        var devices = await provider.GetDevicesAsync();

        // Assert
        devices.Should().BeEmpty("a missing binary must produce an empty list without throwing");
    }

    // ── Task 7.3 ─────────────────────────────────────────────────────────────

    [Fact(DisplayName = "FR-003: SubprocessAudioDeviceProvider parses arecord output correctly")]
    public void ParseArecordOutput_ReturnsCorrectDevices_ForSampleOutput()
    {
        // Arrange: representative arecord --list-devices output.
        const string sample = """
            **** List of CAPTURE Hardware Devices ****
            card 0: PCH [HDA Intel PCH], device 0: ALC892 Analog [ALC892 Analog]
              Subdevices: 1/1
              Subdevice #0: subdevice #0
            card 1: USB [Generic USB Audio], device 0: USB Audio [USB Audio]
              Subdevices: 1/1
              Subdevice #0: subdevice #0
            """;

        // Act
        var devices = SubprocessAudioDeviceProvider.ParseArecordOutput(sample);

        // Assert
        devices.Should().HaveCount(2);

        devices[0].Id.Should().Be("hw:0,0");
        devices[0].Name.Should().Be("HDA Intel PCH");

        devices[1].Id.Should().Be("hw:1,0");
        devices[1].Name.Should().Be("Generic USB Audio");
    }
}
