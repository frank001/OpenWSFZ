using System.Text.RegularExpressions;

namespace TraceabilityCheck;

/// <summary>
/// Parses a REQUIREMENTS.md file and extracts FR-### / NFR-### identifiers.
/// </summary>
public static class RequirementsParser
{
    // Matches a valid requirement ID: exactly "FR-" or "NFR-" (uppercase) + 3 digits.
    private static readonly Regex ValidId = new(@"\b((?:FR|NFR)-\d{3})\b", RegexOptions.Compiled);

    // Matches any token that resembles a requirement ID (case-insensitive prefix, any digit count).
    // Used to detect malformed IDs: wrong case, wrong digit count, or any combination.
    private static readonly Regex AnyIdAttempt = new(
        @"\b([Ff][Rr]|[Nn][Ff][Rr])-(\d+)\b",
        RegexOptions.Compiled);

    /// <summary>
    /// Extracts all valid requirement IDs from <paramref name="content"/>.
    /// Throws <see cref="FormatException"/> on the first malformed identifier found.
    /// A token is malformed when it resembles an ID (case-insensitive FR/NFR prefix + digits)
    /// but does not match the canonical form (uppercase, exactly three digits).
    /// </summary>
    public static IReadOnlySet<string> Parse(string content)
    {
        // Scan every ID-like token; reject any that don't match the canonical form.
        foreach (Match attempt in AnyIdAttempt.Matches(content))
        {
            var prefix = attempt.Groups[1].Value;   // e.g. "fr", "NFR", "Fr"
            var digits = attempt.Groups[2].Value;   // e.g. "001", "1", "1234"

            bool correctCase = prefix is "FR" or "NFR";
            bool correctDigits = digits.Length == 3;

            if (!correctCase || !correctDigits)
            {
                throw new FormatException(
                    $"Malformed requirement identifier '{attempt.Value}' found in REQUIREMENTS.md. " +
                    "Identifiers must match FR-### or NFR-### (uppercase prefix, exactly three digits).");
            }
        }

        var ids = new HashSet<string>(StringComparer.Ordinal);
        foreach (Match m in ValidId.Matches(content))
        {
            ids.Add(m.Groups[1].Value);
        }

        return ids;
    }
}
