using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Config;
using System.Text.Json;
using Xunit;

namespace OpenWSFZ.Config.Tests;

/// <summary>
/// FR-088 (issue #262): the <c>pskReporter</c> block is inert by default. An absent block, an absent key and an old config file all load as
/// <c>enabled</c> false, empty antenna, host <c>report.pskreporter.info</c>, port 4739, and saving writes those values back (HK-035: checked through
/// the real source-generated deserialisation and the real <see cref="JsonConfigStore"/>). All values are synthetic.
/// </summary>
public sealed class PskReporterConfigTests
{
    private sealed class TempDirectory : IDisposable
    {
        public string Path { get; } = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "openwsfz-psk-" + System.IO.Path.GetRandomFileName());
        public TempDirectory() => Directory.CreateDirectory(Path);
        public void Dispose() { try { Directory.Delete(Path, recursive: true); } catch { /* best-effort */ } }
    }

    private static string ConfigPath(TempDirectory dir) => System.IO.Path.Combine(dir.Path, "config.json");

    [Fact(DisplayName = "FR-088: T8: the code defaults are inert (enabled false, empty antenna, report.pskreporter.info, 4739) and an absent key takes them, not the CLR zeros")]
    public void Defaults_AreInert_AbsentKeysTakeThem()
    {
        var d = new PskReporterConfig();
        d.Enabled.Should().BeFalse();
        d.AntennaInformation.Should().BeEmpty();
        d.Host.Should().Be("report.pskreporter.info");
        d.Port.Should().Be(4739);

        var empty = JsonSerializer.Deserialize("""{"pskReporter":{}}""", ConfigJsonContext.Default.AppConfig)!.PskReporter;
        empty.Should().Be(d, "STJ source generation must not hand back port 0");

        var partial = JsonSerializer.Deserialize("""{"pskReporter":{"antennaInformation":"Q1 test"}}""", ConfigJsonContext.Default.AppConfig)!.PskReporter;
        partial.Enabled.Should().BeFalse();
        partial.Port.Should().Be(4739);
        partial.Host.Should().Be("report.pskreporter.info");
        partial.AntennaInformation.Should().Be("Q1 test");
    }

    [Fact(DisplayName = "FR-088: T8: a stored configuration without the pskReporter key loads as the defaults and saving it writes them back")]
    public async Task StoredWithoutTheBlock_LoadsDefaults_SavesThem()
    {
        using var dir = new TempDirectory();
        File.WriteAllText(ConfigPath(dir), "{\"showCycleCountdown\":true}");

        var store = new JsonConfigStore(ConfigPath(dir));
        store.Current.PskReporter.Should().NotBeNull().And.Be(new PskReporterConfig());

        await store.SaveAsync(store.Current with { ShowCycleCountdown = false });
        using var written = JsonDocument.Parse(File.ReadAllText(ConfigPath(dir)));
        var block = written.RootElement.GetProperty("pskReporter");
        block.GetProperty("enabled").GetBoolean().Should().BeFalse();
        block.GetProperty("antennaInformation").GetString().Should().BeEmpty();
        block.GetProperty("host").GetString().Should().Be("report.pskreporter.info");
        block.GetProperty("port").GetInt32().Should().Be(4739);
    }

    [Fact(DisplayName = "FR-088: T8: an explicit null block loads as the defaults, and an enabled block with a test-listener port survives a save and a reload")]
    public async Task NullBlock_LoadsDefaults_ExplicitValuesSurvive()
    {
        using var dir = new TempDirectory();
        File.WriteAllText(ConfigPath(dir), "{\"pskReporter\":null}");
        new JsonConfigStore(ConfigPath(dir)).Current.PskReporter.Should().Be(new PskReporterConfig());

        File.WriteAllText(ConfigPath(dir), "{\"pskReporter\":{\"enabled\":true,\"antennaInformation\":\"Q1 loop\",\"host\":\"pskreporter.info\",\"port\":14739}}");
        var store = new JsonConfigStore(ConfigPath(dir));
        await store.SaveAsync(store.Current with { ShowCycleCountdown = !store.Current.ShowCycleCountdown });

        new JsonConfigStore(ConfigPath(dir)).Current.PskReporter
            .Should().Be(new PskReporterConfig(enabled: true, antennaInformation: "Q1 loop", host: "pskreporter.info", port: 14739));
    }
}
