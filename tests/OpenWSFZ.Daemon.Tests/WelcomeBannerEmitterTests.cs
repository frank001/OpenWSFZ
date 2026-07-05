using FluentAssertions;
using OpenWSFZ.Daemon;
using OpenWSFZ.Web;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="WelcomeBannerEmitter"/> (release-versioning: the banner must
/// report the running build's version, sourced from the repository-root VERSION file via
/// <see cref="AssemblyVersion"/>, alongside the existing loopback URL).
/// </summary>
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
