using FluentAssertions;
using OpenWSFZ.Daemon;
using OpenWSFZ.Web;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Groups tests that mutate the process-wide <see cref="Console.Out"/> via
/// <see cref="Console.SetOut"/>. xUnit runs distinct collections (by default, one per test
/// class) in parallel; two tests swapping the same global <c>Console.Out</c> concurrently could
/// silently steal or corrupt each other's captured output. <c>DisableParallelization</c> confines
/// that hazard to this collection — every current and future test class that intercepts
/// <c>Console.Out</c> should join it — without disabling parallelism for the rest of the
/// assembly (contrast with <c>OpenWSFZ.Ft8.Tests</c>'s assembly-wide
/// <c>CollectionBehavior(DisableTestParallelization = true)</c>, which is warranted there by a
/// shared native hash table but would be needless overkill here).
/// </summary>
[CollectionDefinition("Console output", DisableParallelization = true)]
public sealed class ConsoleOutputCollection
{
}

/// <summary>
/// Unit tests for <see cref="WelcomeBannerEmitter"/> (release-versioning: the banner must
/// report the running build's version, sourced from the repository-root VERSION file via
/// <see cref="AssemblyVersion"/>, alongside the existing loopback URL).
/// </summary>
[Collection("Console output")]
public sealed class WelcomeBannerEmitterTests
{
    [Fact]
    public void Emit_IncludesLoopbackUrlWithGivenPort()
    {
        var originalOut = Console.Out;
        try
        {
            using var writer = new StringWriter();
            Console.SetOut(writer);

            WelcomeBannerEmitter.Emit(8080);

            writer.ToString().Should().Contain("http://127.0.0.1:8080");
        }
        finally
        {
            Console.SetOut(originalOut);
        }
    }

    [Fact]
    public void Emit_IncludesCurrentAssemblyVersion()
    {
        var originalOut = Console.Out;
        try
        {
            using var writer = new StringWriter();
            Console.SetOut(writer);

            WelcomeBannerEmitter.Emit(8080);

            writer.ToString().Should().Contain(AssemblyVersion.Get());
        }
        finally
        {
            Console.SetOut(originalOut);
        }
    }

    // ── daemon-background-mode 4.3/4.4 ──────────────────────────────────────────

    [Fact(DisplayName = "daemon-background-mode 4.3: isBackgroundWorker: false (default) still writes the banner")]
    public void Emit_NotBackgroundWorker_StillWritesBanner()
    {
        var originalOut = Console.Out;
        try
        {
            using var writer = new StringWriter();
            Console.SetOut(writer);

            WelcomeBannerEmitter.Emit(8080, isBackgroundWorker: false);

            writer.ToString().Should().Contain("http://127.0.0.1:8080");
        }
        finally
        {
            Console.SetOut(originalOut);
        }
    }

    [Fact(DisplayName = "daemon-background-mode 4.3: isBackgroundWorker: true writes nothing to stdout")]
    public void Emit_BackgroundWorker_WritesNothing()
    {
        var originalOut = Console.Out;
        try
        {
            using var writer = new StringWriter();
            Console.SetOut(writer);

            WelcomeBannerEmitter.Emit(8080, isBackgroundWorker: true);

            writer.ToString().Should().BeEmpty(
                "a background worker has no console guaranteed valid to write to — the banner " +
                "must be skipped entirely, not attempted");
        }
        finally
        {
            Console.SetOut(originalOut);
        }
    }

    [Fact(DisplayName =
        "daemon-background-mode 4.4: isBackgroundWorker: true does not throw even when stdout would fail")]
    public void Emit_BackgroundWorker_DoesNotThrow_EvenWhenStdoutWouldFail()
    {
        var originalOut = Console.Out;
        try
        {
            // Simulates stdout being in a state that would otherwise fail a raw Console.Write
            // (design.md Decision 6 — Console.Out/Error point at invalid handles once
            // FreeConsole() has run on Windows). The guarded call site must never reach this
            // writer at all when isBackgroundWorker is true.
            Console.SetOut(new ThrowingTextWriter());

            var act = () => WelcomeBannerEmitter.Emit(8080, isBackgroundWorker: true);

            act.Should().NotThrow();
        }
        finally
        {
            Console.SetOut(originalOut);
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
