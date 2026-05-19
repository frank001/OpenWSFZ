using System.Text.RegularExpressions;

namespace TraceabilityCheck;

/// <summary>
/// Parses a <c>traceability-debt.md</c> file and returns the set of requirement IDs
/// that are explicitly acknowledged as pending their implementing phase.
/// IDs in the debt file are excluded from the missing-mapping check but are still
/// validated against REQUIREMENTS.md (stale debt entries surface as an error).
/// </summary>
public static class DebtFileParser
{
    private static readonly Regex IdOnLine = new(@"(?:FR|NFR)-\d{3}", RegexOptions.Compiled);

    /// <summary>
    /// Parses the debt file at <paramref name="path"/> and returns all requirement IDs found.
    /// Returns an empty set when the file does not exist.
    /// Lines starting with <c>#</c> are comments and are skipped in their entirety.
    /// Inline comments (text after the ID, separated by whitespace or <c>#</c>) are ignored.
    /// </summary>
    public static IReadOnlySet<string> Parse(string path)
    {
        if (!File.Exists(path))
        {
            return new HashSet<string>(StringComparer.Ordinal);
        }

        var ids = new HashSet<string>(StringComparer.Ordinal);
        foreach (var line in File.ReadLines(path))
        {
            var trimmed = line.TrimStart();
            if (trimmed.StartsWith('#') || string.IsNullOrWhiteSpace(trimmed))
            {
                continue;
            }

            var match = IdOnLine.Match(trimmed);
            if (match.Success)
            {
                ids.Add(match.Value);
            }
        }

        return ids;
    }
}
