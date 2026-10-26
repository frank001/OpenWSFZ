using System.Text.RegularExpressions;

namespace OpenWSFZ.Abstractions;

/// <summary>
/// Rules for the optional 6-character PSK Reporter receiver locator (<c>pskReporter.locator</c>, FR-096).
/// </summary>
public static partial class PskLocator
{
    /// <summary>Number of characters in the locator accepted by <c>pskReporter.locator</c>.</summary>
    public const int Length = 6;

    /// <summary>Number of leading characters (the 4-character grid square) that must equal <c>tx.grid</c>.</summary>
    public const int SquareLength = 4;

    [GeneratedRegex("^[A-Ra-r]{2}[0-9]{2}[A-Xa-x]{2}$")]
    private static partial Regex ValidPattern();

    /// <summary>True when <paramref name="locator"/> is empty (the default, no locator) or six valid Maidenhead characters.</summary>
    public static bool IsValidOrEmpty(string? locator)
        => string.IsNullOrEmpty(locator) || IsValid(locator);

    /// <summary>True when <paramref name="locator"/> is exactly six valid Maidenhead characters (either case).</summary>
    public static bool IsValid(string? locator)
        => locator is { Length: Length } && ValidPattern().IsMatch(locator);

    /// <summary>The wire form: first 4 characters upper case, last 2 lower case (<c>jo33ED</c> becomes <c>JO33ed</c>).</summary>
    public static string Normalise(string locator)
        => locator[..SquareLength].ToUpperInvariant() + locator[SquareLength..].ToLowerInvariant();

    /// <summary>True when the first 4 characters of <paramref name="locator"/> equal <paramref name="grid"/> (case-insensitive; only the grid's own first 4 characters are compared).</summary>
    public static bool MatchesGrid(string locator, string? grid)
        => grid is { } g && g.Length >= SquareLength && locator.Length >= SquareLength
           && string.Equals(locator[..SquareLength], g[..SquareLength], StringComparison.OrdinalIgnoreCase);
}
