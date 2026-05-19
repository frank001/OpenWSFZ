using FluentAssertions;
using LicenseInventoryCheck;
using Xunit;

namespace LicenseInventoryCheck.Tests;

public sealed class LicenceReportEmitterTests
{
    [Fact(DisplayName = "P0-Tool: Report file is produced even when the run fails due to a policy violation")]
    public void Emit_WithViolations_StillWritesReportFile()
    {
        var entries = new[]
        {
            new DependencyEntry("SomeBadLib", "1.0.0", "GPL-3.0-only", DependencyKind.NuGet, "assets.json"),
        };
        var violations = new[] { "SomeBadLib 1.0.0: licence 'GPL-3.0-only' is not on the allow-list." };
        var path = Path.Combine(Path.GetTempPath(), $"lic-report-{Guid.NewGuid():N}.md");

        try
        {
            LicenceReportEmitter.Emit(path, entries, violations);

            File.Exists(path).Should().BeTrue();
            var content = File.ReadAllText(path);
            content.Should().Contain("FAIL");
            content.Should().Contain("SomeBadLib");
        }
        finally
        {
            if (File.Exists(path))
            {
                File.Delete(path);
            }
        }
    }

    [Fact(DisplayName = "P0-Tool: Report file contains PASS status when no violations exist")]
    public void Emit_NoViolations_ContainsPassStatus()
    {
        var entries = new[]
        {
            new DependencyEntry("xunit", "2.9.3", "MIT", DependencyKind.NuGet, "assets.json"),
        };
        var path = Path.Combine(Path.GetTempPath(), $"lic-report-{Guid.NewGuid():N}.md");

        try
        {
            LicenceReportEmitter.Emit(path, entries, Array.Empty<string>());

            var content = File.ReadAllText(path);
            content.Should().Contain("PASS");
        }
        finally
        {
            if (File.Exists(path))
            {
                File.Delete(path);
            }
        }
    }
}
