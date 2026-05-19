using System.Text;

namespace TraceabilityCheck;

/// <summary>Emits the <c>traceability.md</c> report file.</summary>
public static class ReportEmitter
{
    public static void Emit(string reportPath, AnalysisResult result, IReadOnlySet<string>? debtIds = null)
    {
        var sb = new StringBuilder();
        sb.AppendLine("# Traceability Report");
        sb.AppendLine();
        sb.AppendLine($"Generated: {DateTime.UtcNow:yyyy-MM-dd HH:mm:ss} UTC");
        sb.AppendLine();

        if (result.IsSuccess)
        {
            sb.AppendLine("**Status: PASS** — all requirement IDs are mapped.");
        }
        else
        {
            sb.AppendLine("**Status: FAIL**");
            if (result.UnmappedIds.Count > 0)
            {
                sb.AppendLine();
                sb.AppendLine("## Unmapped Requirements");
                foreach (var id in result.UnmappedIds)
                {
                    sb.AppendLine($"- {id}");
                }
            }

            if (result.StaleReferences.Count > 0)
            {
                sb.AppendLine();
                sb.AppendLine("## Stale References");
                foreach (var (id, testName) in result.StaleReferences)
                {
                    sb.AppendLine($"- `{id}` referenced by: {testName}");
                }
            }
        }

        sb.AppendLine();
        sb.AppendLine("## Requirement Coverage");
        sb.AppendLine();
        sb.AppendLine("| ID | Status | Tests |");
        sb.AppendLine("|---|---|---|");

        foreach (var (id, tests) in result.Mapping.OrderBy(kv => kv.Key, StringComparer.Ordinal))
        {
            if (tests.Count == 0)
            {
                bool isDebt = debtIds?.Contains(id) ?? false;
                var status = isDebt ? "⏳ pending (debt)" : "❌ unmapped";
                sb.AppendLine($"| {id} | {status} | — |");
            }
            else
            {
                var testList = string.Join("; ", tests.Select(t => $"`{t}`"));
                sb.AppendLine($"| {id} | ✅ mapped | {testList} |");
            }
        }

        // Write even on failure — per spec: "report SHALL still be written to disk".
        var dir = Path.GetDirectoryName(reportPath);
        if (!string.IsNullOrEmpty(dir))
        {
            Directory.CreateDirectory(dir);
        }

        File.WriteAllText(reportPath, sb.ToString(), Encoding.UTF8);
    }
}
