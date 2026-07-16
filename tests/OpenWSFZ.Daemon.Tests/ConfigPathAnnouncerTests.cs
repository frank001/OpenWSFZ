using FluentAssertions;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="ConfigPathAnnouncer"/> (daemon-background-mode, tasks 4.2/4.4).
/// Joins the "Console output" collection (<see cref="ConsoleOutputCollection"/>, defined in
/// <c>WelcomeBannerEmitterTests.cs</c>) since this class also swaps the process-wide
/// <see cref="Console.Error"/>.
/// </summary>
[Collection("Console output")]
public sealed class ConfigPathAnnouncerTests
{
    [Fact(DisplayName = "daemon-background-mode 4.2: isBackgroundWorker: false (default) still writes the config-path line")]
    public void Announce_NotBackgroundWorker_StillWrites()
    {
        var originalError = Console.Error;
        try
        {
            using var writer = new StringWriter();
            Console.SetError(writer);

            ConfigPathAnnouncer.Announce("env", "/tmp/app.json", isBackgroundWorker: false);

            writer.ToString().Should().Contain("[OpenWSFZ] Config: env → /tmp/app.json");
        }
        finally
        {
            Console.SetError(originalError);
        }
    }

    [Fact(DisplayName = "daemon-background-mode 4.2: isBackgroundWorker: true writes nothing to stderr")]
    public void Announce_BackgroundWorker_WritesNothing()
    {
        var originalError = Console.Error;
        try
        {
            using var writer = new StringWriter();
            Console.SetError(writer);

            ConfigPathAnnouncer.Announce("env", "/tmp/app.json", isBackgroundWorker: true);

            writer.ToString().Should().BeEmpty(
                "a background worker may already be console-detached by the time this would " +
                "run — the line must be skipped entirely, not attempted");
        }
        finally
        {
            Console.SetError(originalError);
        }
    }

    [Fact(DisplayName =
        "daemon-background-mode 4.4: isBackgroundWorker: true does not throw even when stderr would fail")]
    public void Announce_BackgroundWorker_DoesNotThrow_EvenWhenStderrWouldFail()
    {
        var originalError = Console.Error;
        try
        {
            Console.SetError(new ThrowingTextWriter());

            var act = () => ConfigPathAnnouncer.Announce("env", "/tmp/app.json", isBackgroundWorker: true);

            act.Should().NotThrow();
        }
        finally
        {
            Console.SetError(originalError);
        }
    }

    /// <summary>A <see cref="TextWriter"/> that throws on any write — see the test above.</summary>
    private sealed class ThrowingTextWriter : TextWriter
    {
        public override System.Text.Encoding Encoding => System.Text.Encoding.UTF8;

        public override void Write(string? value) =>
            throw new InvalidOperationException("Simulated invalid console handle.");

        public override void WriteLine(string? value) =>
            throw new InvalidOperationException("Simulated invalid console handle.");
    }
}
