using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="EngagementTargetValidator"/> (<c>engagement-target-validation</c>
/// capability, task 3.4). Exercises all five spec scenarios directly against the validator, using
/// the exact <c>6KER05BPPBQ</c> shape from the live incident that motivated this capability
/// (proposal.md's "Why").
/// </summary>
public sealed class EngagementTargetValidatorTests
{
    private static EngagementTargetValidator MakeValidator(
        IReadOnlyList<CallsignRegionEntry> entries, bool isSeedData = false)
        => new(new FixedRegionStore(entries, isSeedData), new FixedGrammarStore());

    [Fact(DisplayName = "FR-060: engagement-target-validation 3.4: real prefix with a valid remainder is Allowed")]
    public void Validate_RealPrefixValidRemainder_Allowed()
    {
        var validator = MakeValidator([new("DL", "DL", "Germany", "EU", null, null)]);

        var result = validator.Validate("DL1ABC");

        result.IsAllowed.Should().BeTrue();
        result.RejectionReason.Should().BeNull();
    }

    // ── Regression: matched prefix carries the call-area digit itself (found live 2026-07-17) ──
    //
    // Real country-files.com data commonly breaks a single DXCC entity down by call-district,
    // baking the mandatory call-area digit directly into the matched region-store prefix (e.g.
    // "EC5" for a specific Spanish call district) rather than leaving it for the remainder to
    // supply. The Captain hit this live: a genuine callsign, EC5M, was rejected on every single
    // engage attempt because the original algorithm unconditionally required the remainder to
    // itself start with a digit — see EngagementTargetValidator.RemainderFitsGrammar's remarks.

    [Fact(DisplayName = "FR-060: engagement-target-validation regression: matched prefix already carrying the call-area digit (EC5) is Allowed with a letters-only remainder")]
    public void Validate_MatchedPrefixContainsDigit_LettersOnlyRemainder_Allowed()
    {
        var validator = MakeValidator([new("EC5", "EC5", "Spain", "EU", null, null)]);

        var result = validator.Validate("EC5M");

        result.IsAllowed.Should().BeTrue(
            "the matched prefix 'EC5' already carries the mandatory call-area digit — the " +
            "remainder 'M' does not need to supply a second one");
        result.RejectionReason.Should().BeNull();
    }

    [Fact(DisplayName = "FR-060: engagement-target-validation regression: matched prefix containing the digit still rejects a remainder that isn't letters-only")]
    public void Validate_MatchedPrefixContainsDigit_RemainderWithDigit_Rejected()
    {
        var validator = MakeValidator([new("EC5", "EC5", "Spain", "EU", null, null)]);

        // A second, unexpected digit after a prefix that already supplied the call-area digit —
        // must not be silently permitted by the fix above.
        var result = validator.Validate("EC5A1B");

        result.IsAllowed.Should().BeFalse();
    }

    [Fact(DisplayName = "FR-060: engagement-target-validation regression: matched prefix containing the digit still enforces SuffixLengthMax on the remainder")]
    public void Validate_MatchedPrefixContainsDigit_RemainderTooLong_Rejected()
    {
        var validator = MakeValidator([new("EC5", "EC5", "Spain", "EU", null, null)]);

        // "ABCDEFG" is 7 letters — one over the default SuffixLengthMax of 6.
        var result = validator.Validate("EC5ABCDEFG");

        result.IsAllowed.Should().BeFalse();
    }

    [Fact(DisplayName = "FR-060: engagement-target-validation regression: an exact match against a digit-carrying prefix (empty remainder) is Allowed")]
    public void Validate_MatchedPrefixContainsDigit_EmptyRemainder_Allowed()
    {
        var validator = MakeValidator([new("EC5", "EC5", "Spain", "EU", null, null)]);

        var result = validator.Validate("EC5");

        result.IsAllowed.Should().BeTrue("zero suffix letters is valid — the digit-carrying prefix alone already satisfies the grammar");
    }

    // ── Regression: matched prefix's digit is part of the entity identifier, not the whole
    // call-area digit — the callsign's real call-area digit still follows in the remainder
    // (found live 2026-07-17, dev-task ...-qa-review-findings, Finding D).
    //
    // Monaco's region-store entry is "3A", but genuine Monaco calls are always "3A2...": the '2'
    // is the mandatory call-area digit, still owned by the remainder, not consumed by the prefix.
    // Picking exactly one remainder shape from "does the prefix contain a digit" (Finding A's fix)
    // rejected this shape outright, because it assumed a prefix digit always meant the whole
    // call-area digit had already been consumed.

    [Fact(DisplayName = "FR-060: engagement-target-validation regression: matched prefix's digit is only part of the entity identifier (3A/Monaco) — remainder still supplies the real call-area digit and is Allowed")]
    public void Validate_MatchedPrefixContainsDigit_RemainderSuppliesRealCallAreaDigit_Allowed()
    {
        var validator = MakeValidator([new("3A", "3A", "Monaco", "EU", null, null)]);

        var result = validator.Validate("3A2XYZ");

        result.IsAllowed.Should().BeTrue(
            "a genuine Monaco callsign is always '3A2...' — the '2' is the real call-area digit, " +
            "still owned by the remainder even though the matched prefix '3A' already contains a " +
            "digit of its own");
        result.RejectionReason.Should().BeNull();
    }

    [Fact(DisplayName = "FR-060: engagement-target-validation regression: matched prefix's digit-run boundary lands inside the callsign's true digit-run (TM1/hypothetical) — remainder is still Allowed")]
    public void Validate_MatchedPrefixDigitRunBoundaryInsideTrueDigitRun_Allowed()
    {
        // Illustrative shape from the live-verification dev-task's "structural hypothesis": a
        // region-table entry whose prefix boundary lands inside, rather than exactly before or
        // after, the callsign's own digit-run.
        var validator = MakeValidator([new("TM1", "TM1", "France (hypothetical district)", "EU", null, null)]);

        var result = validator.Validate("TM100XYZ");

        result.IsAllowed.Should().BeTrue(
            "the remainder '00XYZ' fits digit-run('00') + suffix('XYZ') even though the matched " +
            "prefix 'TM1' already contains a digit of its own");
    }

    [Fact(DisplayName = "FR-060: engagement-target-validation regression: digit-carrying prefix with a remainder that fits neither shape is still Rejected")]
    public void Validate_MatchedPrefixContainsDigit_RemainderFitsNeitherShape_Rejected()
    {
        // Same shape as the original 6KER05BPPBQ incident: matched prefix contains a digit, and
        // the remainder is neither letters-only nor a valid digit-run+suffix — the OR'd fix must
        // not silently widen acceptance beyond these two shapes.
        var validator = MakeValidator([new("6K", "6K", "Republic of Korea", "AS", null, null)]);

        var result = validator.Validate("6KER05BPPBQ");

        result.IsAllowed.Should().BeFalse(
            "the remainder 'ER05BPPBQ' fits neither the letters-only-suffix shape nor the " +
            "digit-run+suffix shape");
    }

    [Fact(DisplayName = "FR-060: engagement-target-validation 3.4: real prefix '6K' with an invalid remainder (live incident shape) is Rejected")]
    public void Validate_RealPrefixInvalidRemainder_Rejected()
    {
        // "6K" = Republic of Korea, a genuine entry — confirmed live against country-files.com data.
        var validator = MakeValidator([new("6K", "6K", "Republic of Korea", "AS", null, null)]);

        var result = validator.Validate("6KER05BPPBQ");

        result.IsAllowed.Should().BeFalse(
            "the remainder 'ER05BPPBQ' begins with letters, not the mandatory digit-run");
        result.RejectionReason.Should().NotBeNullOrEmpty();
    }

    [Fact(DisplayName = "FR-060: engagement-target-validation 3.4: no prefix match at all is Allowed (absence is not evidence of invalidity)")]
    public void Validate_NoPrefixMatch_Allowed()
    {
        var validator = MakeValidator([new("DL", "DL", "Germany", "EU", null, null)]);

        var result = validator.Validate("ZZ9XYZ");

        result.IsAllowed.Should().BeTrue();
    }

    [Fact(DisplayName = "FR-060: engagement-target-validation 3.4: IsSeedData true allows any token unconditionally")]
    public void Validate_SeedDataLoaded_AllowsAnyToken()
    {
        var validator = MakeValidator(
            [new("6K", "6K", "Republic of Korea", "AS", null, null)], isSeedData: true);

        var result = validator.Validate("6KER05BPPBQ");

        result.IsAllowed.Should().BeTrue("the gate must no-op entirely while only seed data is loaded");
    }

    [Fact(DisplayName = "FR-060: engagement-target-validation 3.4: a portable-suffix token is validated on the base callsign only")]
    public void Validate_PortableSuffixToken_ValidatesBaseCallOnly()
    {
        var validator = MakeValidator([new("DL", "DL", "Germany", "EU", null, null)]);

        // Base call "DL1ABC" fits the grammar (digit-run "1" + suffix "ABC"); the "/QRP" portable
        // suffix must be ignored entirely, not fed into the grammar check.
        var result = validator.Validate("DL1ABC/QRP");

        result.IsAllowed.Should().BeTrue();
    }

    [Fact(DisplayName = "FR-060: engagement-target-validation 3.4: a portable-suffix token with an invalid base call is still Rejected")]
    public void Validate_PortableSuffixToken_InvalidBaseCall_Rejected()
    {
        var validator = MakeValidator([new("6K", "6K", "Republic of Korea", "AS", null, null)]);

        var result = validator.Validate("6KER05BPPBQ/P");

        result.IsAllowed.Should().BeFalse();
    }

    // ── Local test doubles ────────────────────────────────────────────────────

    private sealed class FixedRegionStore : ICallsignRegionStore
    {
        private readonly IReadOnlyList<CallsignRegionEntry> _entries;

        public FixedRegionStore(IReadOnlyList<CallsignRegionEntry> entries, bool isSeedData)
        {
            _entries    = entries;
            IsSeedData  = isSeedData;
        }

        public IReadOnlyList<CallsignRegionEntry> Entries => _entries;
        public bool IsSeedData { get; }

        public RegionInfo? TryGetRegion(string callsignToken) => TryMatchPrefix(callsignToken)?.Region;

        public CallsignRegionMatch? TryMatchPrefix(string callsignToken)
        {
            if (string.IsNullOrEmpty(callsignToken)) return null;
            var token = callsignToken.ToUpperInvariant();

            CallsignRegionEntry? best = null;
            foreach (var entry in _entries)
            {
                var len = entry.PrefixStart.Length;
                if (len == 0 || entry.PrefixEnd.Length != len) continue;
                if (token.Length < len) continue;

                var candidate = token[..len];
                if (string.CompareOrdinal(candidate, entry.PrefixStart) < 0 ||
                    string.CompareOrdinal(candidate, entry.PrefixEnd) > 0)
                    continue;

                if (best is null || len > best.PrefixStart.Length)
                    best = entry;
            }

            if (best is null) return null;
            var region = new RegionInfo(best.Continent, best.Entity, best.Synthetic, best.CqZone, best.ItuZone);
            return new CallsignRegionMatch(region, best.PrefixStart.Length);
        }

        public Task SaveAsync(IReadOnlyList<CallsignRegionEntry> entries, CancellationToken cancellationToken = default)
            => throw new NotSupportedException("Not needed by these tests.");
    }

    private sealed class FixedGrammarStore : ICallsignGrammarStore
    {
        public CallsignGrammarConfig Current => CallsignGrammarConfig.BuiltInDefault;
    }
}
