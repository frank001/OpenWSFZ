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
}
