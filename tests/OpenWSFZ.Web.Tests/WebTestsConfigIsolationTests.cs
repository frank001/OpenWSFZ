using ConfigPathResolverType = OpenWSFZ.Config.ConfigPathResolver;
using FluentAssertions;
using Xunit;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Proves the Web.Tests process cannot reach the machine's real per-user config
/// (see <see cref="IsolatedConfigModule"/>). The sentinel-APPDATA proof is done at process level
/// (vstest on the built assembly with the per-user roots pointed at a sentinel), because
/// <c>Environment.GetFolderPath</c> does not follow environment variables in-process on Windows.
/// </summary>
public sealed class WebTestsConfigIsolationTests : IClassFixture<WebTestFactory>
{
    private readonly WebTestFactory _factory;

    public WebTestsConfigIsolationTests(WebTestFactory factory) => _factory = factory;

    [Fact(DisplayName = "the Web.Tests process resolves its config path from OPENWSFZ_CONFIG, an isolated temp file, never the platform default")]
    public void ResolvedConfigPath_IsTheIsolatedTempFile()
    {
        var (path, source) = ConfigPathResolverType.Resolve(null);

        source.Should().Contain("OPENWSFZ_CONFIG");
        path.Should().Be(IsolatedConfigModule.ConfigPath);
        Path.GetFullPath(path).Should().StartWith(Path.GetFullPath(Path.GetTempPath()));
        path.Should().NotBe(DefaultPlatformConfigPath());
    }

    [Fact(DisplayName = "starting Program through the factory loads the isolated config: the store creates its files in the temp directory")]
    public void FactoryStart_CreatesItsFilesInTheIsolatedDirectory()
    {
        using var client = _factory.CreateClient();   // forces Program's top-level start-up

        File.Exists(IsolatedConfigModule.ConfigPath).Should().BeTrue(
            "Program's JsonConfigStore must have loaded (and created) the isolated config, not the per-user one");
    }

    private static string DefaultPlatformConfigPath()
        => Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData, Environment.SpecialFolderOption.DoNotVerify),
            "OpenWSFZ", "config.json");
}
