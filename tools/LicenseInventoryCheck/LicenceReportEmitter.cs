using System.Text;

namespace LicenseInventoryCheck;

/// <summary>Emits the <c>licence-inventory.md</c> report file.</summary>
public static class LicenceReportEmitter
{
    public static void Emit(
        string reportPath,
        IReadOnlyList<DependencyEntry> entries,
        IReadOnlyList<string> violations)
    {
        var sb = new StringBuilder();
        sb.AppendLine("# Licence Inventory Report");
        sb.AppendLine();
        sb.AppendLine($"Generated: {DateTime.UtcNow:yyyy-MM-dd HH:mm:ss} UTC");
        sb.AppendLine();

        if (violations.Count == 0)
        {
            sb.AppendLine("**Status: PASS** — all dependencies use allowed licences.");
        }
        else
        {
            sb.AppendLine("**Status: FAIL**");
            sb.AppendLine();
            sb.AppendLine("## Policy Violations");
            foreach (var v in violations)
            {
                sb.AppendLine($"- {v}");
            }
        }

        sb.AppendLine();
        sb.AppendLine("## Dependency Inventory");
        sb.AppendLine();
        sb.AppendLine("| Name | Version | Licence | Kind | Provenance |");
        sb.AppendLine("|---|---|---|---|---|");

        foreach (var e in entries.OrderBy(e => e.Name, StringComparer.OrdinalIgnoreCase))
        {
            sb.AppendLine($"| {e.Name} | {e.Version} | {e.Licence} | {e.Kind} | {e.Provenance} |");
        }

        var dir = Path.GetDirectoryName(reportPath);
        if (!string.IsNullOrEmpty(dir))
        {
            Directory.CreateDirectory(dir);
        }

        File.WriteAllText(reportPath, sb.ToString(), Encoding.UTF8);
    }
}
