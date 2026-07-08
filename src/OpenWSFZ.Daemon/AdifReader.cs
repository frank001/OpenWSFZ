using System.Text.RegularExpressions;
using Microsoft.Extensions.Logging;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Minimal, purpose-built ADIF 3.x reader (<c>qso-confirmation</c> capability, design.md
/// Decision 2). Extracts only <c>CALL</c> field values from tagged-field records
/// (<c>&lt;call:N&gt;VALUE</c>), case-insensitively. Not a general-purpose ADIF library:
/// no other field is read, and ADIF's alternate (non-tagged) formats are not supported.
///
/// <para>
/// Parsing is per-line: the leading header block (<c>ADIF Export</c>, <c>&lt;adif_ver:...&gt;</c>,
/// <c>&lt;eoh&gt;</c>) and any other line that carries no <c>&lt;call:...&gt;</c> tag at all is
/// skipped silently (expected, not an error condition). A line that <em>does</em> contain a
/// <c>&lt;call:</c> tag but fails to parse (non-numeric or out-of-range length — e.g. truncated
/// mid-write) is skipped with a Warning logged, and parsing continues with the remaining lines —
/// never fatal to the rest of the file.
/// </para>
/// </summary>
internal static class AdifReader
{
    // Matches "<call:N>" (case-insensitive); the value itself is read positionally
    // (the N characters immediately following the closing '>').
    private static readonly Regex CallTagRegex =
        new(@"<call:(\d+)>", RegexOptions.IgnoreCase | RegexOptions.Compiled);

    /// <summary>
    /// Reads every <c>CALL</c> field value found in the ADIF file at <paramref name="path"/>
    /// (duplicates included — callers that need distinct callsigns should dedupe the result).
    /// A missing file resolves to an empty list, not an error.
    /// </summary>
    public static IReadOnlyList<string> ReadCallsigns(string path, ILogger? logger = null)
    {
        if (!File.Exists(path)) return [];

        string[] lines;
        try
        {
            lines = File.ReadAllLines(path);
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            logger?.LogWarning(ex,
                "qso-confirmation: cannot read ADIF log at '{Path}' — worked-before index will be empty.",
                path);
            return [];
        }

        var results = new List<string>(lines.Length);
        foreach (var line in lines)
        {
            var call = TryExtractCall(line);
            if (call is not null)
            {
                results.Add(call);
                continue;
            }

            // Only warn for lines that look like they were trying to carry a CALL tag but
            // failed to parse — a plain header/comment/other-field-only line carries no
            // "<call:" substring at all and is an expected, silent skip.
            if (line.Contains("<call:", StringComparison.OrdinalIgnoreCase))
            {
                logger?.LogWarning(
                    "qso-confirmation: skipped a malformed/truncated CALL tag while reading ADIF " +
                    "log '{Path}'.", path);
            }
        }

        return results;
    }

    /// <summary>
    /// Attempts to extract a single <c>CALL</c> field value from one line of ADIF text.
    /// Returns <c>null</c> when the line has no <c>&lt;call:N&gt;</c> tag, or the tag's declared
    /// length is non-numeric, non-positive, or runs past the end of the line (truncated).
    /// </summary>
    internal static string? TryExtractCall(string line)
    {
        var match = CallTagRegex.Match(line);
        if (!match.Success) return null;

        if (!int.TryParse(match.Groups[1].Value, out var len) || len <= 0) return null;

        var start = match.Index + match.Length;
        if (start + len > line.Length) return null; // truncated value

        return line.Substring(start, len);
    }
}
