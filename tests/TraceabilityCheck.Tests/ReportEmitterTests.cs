using FluentAssertions;
using TraceabilityCheck;
using Xunit;

namespace TraceabilityCheck.Tests;

public sealed class ReportEmitterTests
{
    [Fact(DisplayName = "P0-Tool: Report file is produced even when the run fails due to unmapped requirements")]
    public void Emit_FailingResult_StillWritesReportFile()
    {
        var mapping = new Dictionary<string, IReadOnlyList<string>>
        {
            ["FR-001"] = new List<string>(),   // unmapped
            ["FR-002"] = new List<string> { "FR-002: Some test" },
        };
        var result = new AnalysisResult(
            Mapping: mapping,
            UnmappedIds: new[] { "FR-001" },
            StaleReferences: Array.Empty<(string, string)>());

        var path = Path.Combine(Path.GetTempPath(), $"traceability-test-{Guid.NewGuid():N}.md");
        try
        {
            ReportEmitter.Emit(path, result);

            File.Exists(path).Should().BeTrue();
            var content = File.ReadAllText(path);
            content.Should().Contain("FR-001");
            content.Should().Contain("FAIL");
        }
        finally
        {
            if (File.Exists(path))
            {
                File.Delete(path);
            }
        }
    }

    [Fact(DisplayName = "P0-Tool: Report file contains PASS when all requirements are mapped")]
    public void Emit_PassingResult_ContainsPassStatus()
    {
        var mapping = new Dictionary<string, IReadOnlyList<string>>
        {
            ["FR-001"] = new List<string> { "FR-001: Some test" },
        };
        var result = new AnalysisResult(
            Mapping: mapping,
            UnmappedIds: Array.Empty<string>(),
            StaleReferences: Array.Empty<(string, string)>());

        var path = Path.Combine(Path.GetTempPath(), $"traceability-test-{Guid.NewGuid():N}.md");
        try
        {
            ReportEmitter.Emit(path, result);

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
