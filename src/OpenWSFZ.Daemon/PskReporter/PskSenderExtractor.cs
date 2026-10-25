using System.Text.RegularExpressions;

namespace OpenWSFZ.Daemon.PskReporter;

/// <summary>The sender of a decoded message, as it will be reported.</summary>
/// <param name="Callsign">Exactly as decoded, prefixes and suffixes included.</param>
/// <param name="Locator">Only when the message carries a grid in the grid position; never carried over from another message.</param>
internal sealed record PskSender(string Callsign, string? Locator);

/// <summary>Why a message's sender was not extracted.</summary>
internal enum PskSenderRejection
{
    /// <summary>A hashed callsign (<c>&lt;...&gt;</c>, also a hash the decoder resolved to text) is in the message.</summary>
    Hashed,

    /// <summary>A keyword, free text, telemetry or anything that is not one of the recognised forms.</summary>
    Unparseable,

    /// <summary>The sender is the station's own call (compared on the base call).</summary>
    OwnCall,
}

/// <summary>
/// Strict sender extraction for the PSK Reporter upload (issue #262, FR-090): tokens are CLASSIFIED, never counted, and there is
/// no fallback to token 0 (the addressee). Deliberately separate from <c>Ft8Decoder.ExtractPrimaryCallsignToken</c>, which counts
/// tokens, falls back to token 0 and strips suffixes: right for a region lookup, wrong for a public spot.
/// </summary>
internal static class PskSenderExtractor
{
    /// <summary>A CQ modifier is at most this many letters (<c>DX</c>, <c>POTA</c>, <c>NA</c> ...).</summary>
    private const int MaxModifierLetters = 4;

    /// <summary>... or exactly this many digits (a CQ zone or frequency hint such as <c>CQ 123</c>).</summary>
    private const int ModifierDigits = 3;

    /// <summary>The longest callsign token accepted (a prefix, a base call and a suffix).</summary>
    private const int MaxCallsignLength = 13;

    private static readonly Regex CallsignRegex = new(@"^[A-Z0-9]+(/[A-Z0-9]+)*$", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
    private static readonly Regex GridRegex     = new(@"^[A-R]{2}[0-9]{2}$",       RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
    private static readonly Regex ReportRegex   = new(@"^R?[+-][0-9]{2}$",         RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
    private static readonly Regex ModifierRegex = new($"^([A-Z]{{1,{MaxModifierLetters}}}|[0-9]{{{ModifierDigits}}})$", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);

    /// <summary>
    /// Classifies <paramref name="message"/>. On success <paramref name="sender"/> is set; otherwise <paramref name="rejection"/> says
    /// why. <paramref name="ownCallsign"/> is the station's call; the comparison uses the base call, case-insensitively.
    /// </summary>
    public static bool TryExtract(string message, string ownCallsign, out PskSender? sender, out PskSenderRejection rejection)
    {
        sender = null;
        var tokens = message.Split(' ', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);

        if (tokens.Length < 2 || message.Contains(';'))
        {
            rejection = tokens.Any(IsHash) ? PskSenderRejection.Hashed : PskSenderRejection.Unparseable;
            return false;
        }
        if (tokens.Any(IsHash))
        {
            rejection = PskSenderRejection.Hashed;
            return false;
        }

        PskSender? found = tokens[0].Equals("CQ", StringComparison.OrdinalIgnoreCase)
            ? FromCq(tokens)
            : FromStandard(tokens);

        if (found is null)
        {
            rejection = PskSenderRejection.Unparseable;
            return false;
        }
        if (BaseCall(found.Callsign).Equals(BaseCall(ownCallsign), StringComparison.OrdinalIgnoreCase))
        {
            rejection = PskSenderRejection.OwnCall;
            return false;
        }

        sender    = found;
        rejection = default;
        return true;
    }

    /// <summary>
    /// <c>CQ [modifier] &lt;call&gt; [grid]</c>. A token with a digit and a letter is the call; the modifier slot takes only a short
    /// letters-only or three-digit token.
    /// </summary>
    private static PskSender? FromCq(string[] t)
    {
        int i = 1;
        if (i < t.Length && ModifierRegex.IsMatch(t[i]) && !IsCallsign(t[i])) i++;
        if (i >= t.Length || !IsCallsign(t[i])) return null;
        string call = t[i++];

        string? grid = null;
        if (i < t.Length)
        {
            if (!IsGrid(t[i])) return null;
            grid = t[i++];
        }
        return i == t.Length ? new PskSender(call, grid) : null;
    }

    /// <summary><c>&lt;to&gt; &lt;from&gt; &lt;extension&gt;</c> (or <c>&lt;to&gt; &lt;from&gt; R &lt;grid&gt;</c>): the sender is token 1, and the extension must be a recognised one.</summary>
    private static PskSender? FromStandard(string[] t)
    {
        if (t.Length < 3 || t.Length > 4 || !IsCallsign(t[0]) || !IsCallsign(t[1])) return null;

        // The 4-token form <to> <from> R <grid> (Architect spec 12, N-2): the sender is token 1 and the grid token 3.
        if (t.Length == 4)
            return t[2].Equals("R", StringComparison.OrdinalIgnoreCase) && IsGrid(t[3]) ? new PskSender(t[1], t[3]) : null;

        string ext = t[2];
        if (IsGrid(ext)) return new PskSender(t[1], ext);
        bool known = ReportRegex.IsMatch(ext)
            || ext.Equals("RRR", StringComparison.OrdinalIgnoreCase)
            || ext.Equals("RR73", StringComparison.OrdinalIgnoreCase)
            || ext.Equals("73", StringComparison.Ordinal);
        return known ? new PskSender(t[1], null) : null;
    }

    private static bool IsHash(string token) => token.StartsWith('<') || token.EndsWith('>');

    /// <summary>A callsign has at least one digit and one letter (so <c>DX</c>, <c>123</c> and <c>RR73</c>-like tokens are not calls).</summary>
    private static bool IsCallsign(string token)
        => token.Length is >= 3 and <= MaxCallsignLength
           && CallsignRegex.IsMatch(token)
           && token.Any(char.IsDigit) && token.Any(char.IsLetter)
           && !IsGrid(token);

    /// <summary>A four-character locator, and never <c>RR73</c> (which matches the pattern but is the closing message).</summary>
    private static bool IsGrid(string token)
        => GridRegex.IsMatch(token) && !token.Equals("RR73", StringComparison.OrdinalIgnoreCase);

    /// <summary>
    /// The call with any prefix and suffix removed: of the slash-separated parts that look like a call, the longest (<c>DL/Q1OFZ/P</c>
    /// gives <c>Q1OFZ</c>; <c>VP9/Q1OFZ</c> gives <c>Q1OFZ</c>).
    /// </summary>
    internal static string BaseCall(string call)
    {
        var parts = call.Split('/', StringSplitOptions.RemoveEmptyEntries);
        var candidates = parts.Where(p => p.Any(char.IsDigit) && p.Any(char.IsLetter)).ToList();
        if (candidates.Count == 0) return call;
        return candidates.OrderByDescending(p => p.Length).First();
    }
}
