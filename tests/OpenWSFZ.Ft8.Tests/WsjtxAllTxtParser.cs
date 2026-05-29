using System;
using System.Collections.Generic;
using System.IO;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Parses a WSJT-X (or OpenWSFZ daemon) ALL.TXT decode log file into a
/// per-timestamp dictionary of decoded message strings.
///
/// ALL.TXT line format (both WSJT-X and OpenWSFZ AllTxtWriter):
/// <code>
/// YYMMDD_HHMMSS     D.DDD Rx FT8  snr    dt  freq message text here
/// </code>
/// Fields are whitespace-separated; the message is everything from field index 7
/// onward, joined with a single space.
/// </summary>
internal static class WsjtxAllTxtParser
{
    /// <summary>
    /// Reads the file at <paramref name="path"/> and returns a dictionary keyed
    /// by timestamp string (e.g. <c>"260528_235745"</c>) whose values are the
    /// lists of decoded message strings for that cycle.
    /// </summary>
    public static Dictionary<string, List<string>> Parse(string path)
    {
        var result = new Dictionary<string, List<string>>(StringComparer.Ordinal);

        foreach (string line in File.ReadLines(path))
        {
            string trimmed = line.Trim();
            if (trimmed.Length == 0 || trimmed.StartsWith('#'))
                continue;

            string[] parts = trimmed.Split(
                new[] { ' ', '\t' },
                StringSplitOptions.RemoveEmptyEntries);

            // Minimum fields: timestamp, freq, Rx, FT8, snr, dt, audioHz, msg…
            if (parts.Length < 8)
                continue;

            string timestamp = parts[0]; // e.g. "260528_235745"
            // parts[3] should be "FT8" — skip lines that are not FT8 decodes
            if (parts[3] != "FT8")
                continue;

            string message = string.Join(" ", parts, 7, parts.Length - 7);

            if (!result.TryGetValue(timestamp, out var list))
            {
                list = new List<string>();
                result[timestamp] = list;
            }
            list.Add(message);
        }

        return result;
    }
}
