using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Default <see cref="IEngagementTargetValidator"/> implementation
/// (<c>engagement-target-validation</c> capability, design.md Decision 3). Reuses
/// <see cref="ICallsignRegionStore.TryMatchPrefix"/> and <see cref="ICallsignGrammarStore.Current"/>
/// verbatim — no second copy of the region table or the grammar's digit-run/suffix limits.
/// </summary>
public sealed class EngagementTargetValidator : IEngagementTargetValidator
{
    private readonly ICallsignRegionStore  _regionStore;
    private readonly ICallsignGrammarStore _grammarStore;

    public EngagementTargetValidator(ICallsignRegionStore regionStore, ICallsignGrammarStore grammarStore)
    {
        _regionStore  = regionStore;
        _grammarStore = grammarStore;
    }

    /// <inheritdoc/>
    public EngagementValidationResult Validate(string callsignToken)
    {
        // Decision 2: gate is inactive while only the compiled-in seed table is loaded — today's
        // fully permissive engagement behaviour is preserved unchanged.
        if (_regionStore.IsSeedData) return EngagementValidationResult.Allowed;

        if (string.IsNullOrWhiteSpace(callsignToken)) return EngagementValidationResult.Allowed;

        // Evaluate the base callsign only — same portable-suffix handling as
        // callsign-structure-validation (task 2.1's shared helper, no second copy of this split).
        var baseCall = CallsignTokenHelpers.StripPortableSuffix(callsignToken).ToUpperInvariant();

        var match = _regionStore.TryMatchPrefix(baseCall);
        if (match is null) return EngagementValidationResult.Allowed; // unlisted prefix ≠ invalid

        var matchedPrefix = baseCall[..match.MatchedPrefixLength];
        var remainder     = baseCall[match.MatchedPrefixLength..];
        if (RemainderFitsGrammar(remainder, matchedPrefix, _grammarStore.Current))
            return EngagementValidationResult.Allowed;

        return EngagementValidationResult.Rejected(
            $"'{callsignToken}' matched region prefix '{matchedPrefix}' ({match.Region.Entity}) but " +
            $"the remainder '{remainder}' is not a valid digit-run+suffix.");
    }

    /// <summary>
    /// Validates the portion of the base callsign after the matched region prefix.
    /// </summary>
    /// <remarks>
    /// Real region-store data (country-files.com) commonly breaks a single DXCC entity down by
    /// call-district, with the mandatory call-area digit baked directly into the matched prefix
    /// itself — e.g. a genuine Spanish callsign like <c>EC5M</c> matches the region-store entry
    /// <c>"EC5"</c> (a specific Spanish call district), not a bare <c>"EC"</c>. In that case the
    /// remainder (<c>"M"</c>) no longer owns a digit to contribute: the callsign's mandatory digit
    /// is already accounted for, just inside the matched prefix rather than after it.
    /// <para>
    /// <b>Correction (found live, dev-task 2026-07-17-engagement-target-validation-qa-review-findings,
    /// Finding D):</b> a digit inside the matched prefix does not <em>always</em> mean the whole
    /// mandatory call-area digit was consumed — some DXCC entities are themselves digit-leading as
    /// part of the entity identifier, not the call-district marker, with the callsign's real
    /// call-area digit still to come <em>after</em> the matched prefix. E.g. Monaco's region-store
    /// entry is <c>"3A"</c>, but genuine Monaco calls are always <c>3A2...</c> — the <c>'2'</c> is
    /// the real call-area digit, still owned by the remainder. Picking exactly one remainder shape
    /// from whether the prefix contains a digit therefore rejected genuine calls of this shape.
    /// Fixed by trying <em>both</em> remainder shapes whenever the matched prefix carries a digit —
    /// letters-only suffix (the <c>EC5</c> case, digit fully consumed by the prefix) or
    /// digit-run-then-suffix (the <c>3A</c> case, prefix digit is only part of the entity
    /// identifier) — and rejecting only if neither fits.
    /// </para>
    /// </remarks>
    private static bool RemainderFitsGrammar(string remainder, string matchedPrefix, CallsignGrammarConfig config)
    {
        if (ContainsDigit(matchedPrefix))
        {
            // The matched prefix carries a digit, but it's ambiguous whether that digit is the
            // callsign's whole mandatory call-area digit (remainder is then suffix-only, e.g.
            // "EC5" + "M") or just part of a digit-leading entity identifier with the real
            // call-area digit still to come (remainder then still owns a digit-run, e.g.
            // "3A" + "2XYZ"). Accept either shape; reject only if neither fits.
            return IsValidSuffix(remainder, config) || FitsDigitRunThenSuffix(remainder, config);
        }

        // Standard path: a purely alphabetic matched prefix — the remainder must supply the
        // mandatory digit-run itself.
        return FitsDigitRunThenSuffix(remainder, config);
    }

    /// <summary>
    /// A digit-run of 1 to <see cref="CallsignGrammarConfig.DigitRunMax"/> digits immediately at
    /// the start of <paramref name="remainder"/>, followed by 0 to
    /// <see cref="CallsignGrammarConfig.SuffixLengthMax"/> letters, consuming the entire remainder.
    /// </summary>
    private static bool FitsDigitRunThenSuffix(string remainder, CallsignGrammarConfig config)
    {
        if (remainder.Length == 0) return false; // must have at least the mandatory digit(s)

        int i          = 0;
        int digitCount = 0;
        while (i < remainder.Length && char.IsAsciiDigit(remainder[i]) && digitCount < config.DigitRunMax)
        {
            i++;
            digitCount++;
        }
        if (digitCount == 0) return false; // remainder must start with a digit

        // A digit immediately following the capped run means the true digit-run exceeds
        // DigitRunMax — reject rather than silently truncating it.
        if (i < remainder.Length && char.IsAsciiDigit(remainder[i])) return false;

        return IsValidSuffix(remainder[i..], config);
    }

    private static bool ContainsDigit(string s)
    {
        foreach (char c in s)
            if (char.IsAsciiDigit(c)) return true;
        return false;
    }

    /// <summary>0 to <see cref="CallsignGrammarConfig.SuffixLengthMax"/> letters, nothing else.</summary>
    private static bool IsValidSuffix(string suffix, CallsignGrammarConfig config)
    {
        if (suffix.Length > config.SuffixLengthMax) return false;
        foreach (char c in suffix)
            if (!char.IsAsciiLetter(c)) return false;
        return true;
    }
}
