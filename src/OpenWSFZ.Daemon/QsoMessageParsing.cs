using System;
using System.Linq;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Shared dest-token normalisation for F-001 R5's L2 (bracket-strip) fix.
///
/// <para>
/// The native FT8 encoder wraps a hashed (nonstandard) callsign it could not resolve to a
/// real string in angle brackets, e.g. <c>&lt;PD2FZ&gt;</c> (<c>message.c:604-611</c>,
/// <c>add_brackets()</c> — read for method only, no line copied). Comparing that bracketed
/// token against our plain-string own callsign with a literal <see cref="string.Equals(string)"/>
/// always fails, so a correctly resolved own-call reference was silently never recognised as
/// "addressed to us" (L2, GH #60 / <c>qa/rr-study/2026-08-27-1531-*.md</c> Sec.0).
/// </para>
///
/// <para>
/// This type is Shape (B) from the F-001 R5 L1+L2 developer slice
/// (<c>dev-tasks/2026-08-27-1645-f001-r5-l1l2-developer-slice.md</c> Sec.2): normalisation
/// happens locally at each comparison site (<c>QsoAnswererService</c>
/// <c>HandleWaitReportAsync</c>/<c>HandleWaitRr73Async</c>, <c>QsoCallerService</c>
/// <c>HandleWaitRr73Async</c>), not inside <c>TryParseMessage</c> — so log lines that print
/// the raw <c>dest</c> token stay byte-identical to before this change. A single shared
/// helper makes "every comparison site moved together" mechanically checkable rather than
/// relying on review to catch a missed call site.
/// </para>
/// </summary>
internal static class QsoMessageParsing
{
    /// <summary>
    /// Strips one leading <c>&lt;</c> and one matching trailing <c>&gt;</c> from
    /// <paramref name="token"/> (e.g. <c>&lt;PD2FZ&gt;</c> → <c>PD2FZ</c>). A token with no
    /// surrounding brackets — the common case, a plain callsign — is returned unchanged.
    /// </summary>
    internal static string StripBrackets(string token)
    {
        if (token.Length >= 2 && token[0] == '<' && token[^1] == '>')
            return token[1..^1];

        return token;
    }

    /// <summary>
    /// True if <paramref name="callsign"/> is the native encoder's failure-to-resolve marker
    /// (all-dot, e.g. <c>...</c> — what <c>&lt;...&gt;</c> becomes after
    /// <see cref="StripBrackets"/>) or empty. Per the F-001 R5 Sec.2 constraint: this is NOT a
    /// callsign and must never compare equal to anything, including another all-dot marker or
    /// an empty string — the one place a mistake here is silent and severe (it turns "we could
    /// not resolve who this is" into "this is addressed to us").
    /// </summary>
    internal static bool IsUnresolvedHashMarker(string callsign)
        => string.IsNullOrEmpty(callsign) || callsign.All(static c => c == '.');

    /// <summary>
    /// True if <paramref name="dest"/> — a raw message token, optionally bracket-wrapped —
    /// refers to <paramref name="ours"/> (our own configured callsign), ordinal
    /// case-insensitive, after stripping brackets and rejecting the unresolved-hash marker
    /// (F-001 R5 L2, Sec.2's guard applied first).
    /// </summary>
    internal static bool DestMatchesOwnCallsign(string dest, string ours)
    {
        var stripped = StripBrackets(dest);
        if (IsUnresolvedHashMarker(stripped))
            return false;

        return stripped.Equals(ours, StringComparison.OrdinalIgnoreCase);
    }
}
