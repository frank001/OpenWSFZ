using System.Text.RegularExpressions;
using Microsoft.Extensions.Logging;

namespace OpenWSFZ.Daemon;

/// <summary>
/// A single ADIF record's <c>CALL</c> and <c>BAND</c> field values, as extracted by
/// <see cref="AdifReader.ReadEntries"/> (<c>qso-confirmation-band-awareness</c> design.md
/// Decision 3).
/// </summary>
/// <param name="Call">The record's <c>CALL</c> field value — always present (a record with no
/// parseable <c>CALL</c> is skipped entirely, never yields an entry).</param>
/// <param name="Band">
/// The record's <c>BAND</c> field value, or <c>null</c> when the tag is missing or
/// unparseable — not a skip condition, only <c>CALL</c> being unparseable skips the record.
/// </param>
internal readonly record struct AdifLogEntry(string Call, string? Band);

/// <summary>
/// Minimal, purpose-built ADIF 3.x reader (<c>qso-confirmation</c> capability, design.md
/// Decision 2; widened by <c>qso-confirmation-band-awareness</c> design.md Decision 3 to also
/// extract <c>BAND</c>). Extracts only <c>CALL</c> and <c>BAND</c> field values from
/// tagged-field records (<c>&lt;call:N&gt;VALUE</c>, <c>&lt;band:N&gt;VALUE</c>),
/// case-insensitively. Not a general-purpose ADIF library: no other field is read, and ADIF's
/// alternate (non-tagged) formats are not supported.
///
/// <para>
/// Parsing is per-line: the leading header block (<c>ADIF Export</c>, <c>&lt;adif_ver:...&gt;</c>,
/// <c>&lt;eoh&gt;</c>) and any other line that carries no <c>&lt;call:...&gt;</c> tag at all is
/// skipped silently (expected, not an error condition). A line that <em>does</em> contain a
/// <c>&lt;call:</c> tag but fails to parse (non-numeric or out-of-range length — e.g. truncated
/// mid-write) is skipped with a Warning logged, and parsing continues with the remaining lines —
/// never fatal to the rest of the file. A line whose <c>CALL</c> parses but whose <c>BAND</c>
/// tag is missing or unparseable still yields an entry, with <see cref="AdifLogEntry.Band"/>
/// <c>null</c> — this is not a skip condition.
/// </para>
/// </summary>
internal static class AdifReader
{
    // Matches "<call:N>" / "<band:N>" (case-insensitive); the value itself is read positionally
    // (the N characters immediately following the closing '>').
    private static readonly Regex CallTagRegex =
        new(@"<call:(\d+)>", RegexOptions.IgnoreCase | RegexOptions.Compiled);

    private static readonly Regex BandTagRegex =
        new(@"<band:(\d+)>", RegexOptions.IgnoreCase | RegexOptions.Compiled);

    /// <summary>
    /// Reads every ADIF record found in the file at <paramref name="path"/> that carries a
    /// parseable <c>CALL</c> field (duplicates included — callers that need distinct callsigns
    /// should dedupe the result), pairing each with its <c>BAND</c> field when present and
    /// parseable. A missing file resolves to an empty list, not an error.
    /// </summary>
    public static IReadOnlyList<AdifLogEntry> ReadEntries(string path, ILogger? logger = null)
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

        var results = new List<AdifLogEntry>(lines.Length);
        foreach (var line in lines)
        {
            var call = TryExtractCall(line);
            if (call is not null)
            {
                var band = TryExtractBand(line);
                results.Add(new AdifLogEntry(call, band));
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
    internal static string? TryExtractCall(string line) => TryExtractTag(line, CallTagRegex);

    /// <summary>
    /// Attempts to extract a single <c>BAND</c> field value from one line of ADIF text.
    /// Returns <c>null</c> when the line has no <c>&lt;band:N&gt;</c> tag, or the tag's declared
    /// length is non-numeric, non-positive, or runs past the end of the line (truncated) — this
    /// is not an error condition for the record as a whole (design.md Decision 3).
    /// </summary>
    internal static string? TryExtractBand(string line) => TryExtractTag(line, BandTagRegex);

    private static string? TryExtractTag(string line, Regex tagRegex)
    {
        var match = tagRegex.Match(line);
        if (!match.Success) return null;

        if (!int.TryParse(match.Groups[1].Value, out var len) || len <= 0) return null;

        var start = match.Index + match.Length;
        if (start + len > line.Length) return null; // truncated value

        return line.Substring(start, len);
    }
}
