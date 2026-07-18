using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Daemon;
using Xunit;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Regression test for the live incident that motivated <c>engagement-target-validation</c>
/// (proposal.md's "Why": 2026-07-16, <c>logs/openswfz-20260716T194057Z.log:686-761</c> — the
/// daemon engaged and transmitted twice to <c>6KER05BPPBQ</c>, a decoded token that is not a
/// plausible amateur radio callsign, before the operator manually aborted).
/// <para>
/// Task 6.2: proves both halves of the fix together — (a) decode acceptance
/// (<c>callsign-structure-validation</c>) is completely unaffected, so the token still reaches
/// <c>ALL.TXT</c> and the decode panel exactly as before, and (b) the new engagement-time gate
/// rejects it, which is the actual defect fix.
/// </para>
/// </summary>
public sealed class EngagementTargetValidationRegressionTests
{
    private const string IncidentToken = "6KER05BPPBQ";

    [Fact(DisplayName = "FR-060: engagement-target-validation 6.2a: the incident token is still decode-accepted — ALL.TXT/decode-panel visibility is completely unaffected")]
    public void IncidentToken_DecodeAcceptance_Unaffected()
    {
        // Same shape check callsign-structure-validation already applies to every decode —
        // must still return true (plausible / accepted), exactly as it did the night of the
        // incident. This capability must never change decode acceptance.
        Ft8Decoder.IsPlausibleMessage($"PD2FZ {IncidentToken} -05").Should().BeTrue(
            "engagement-target-validation must not alter callsign-structure-validation's decode " +
            "acceptance — the token was genuinely decoded and displayed on the night of the incident");
    }

    [Fact(DisplayName = "FR-060: engagement-target-validation 6.2b: the incident token is rejected for engagement once real region data is loaded")]
    public void IncidentToken_EngagementValidation_Rejected()
    {
        // "6K" = Republic of Korea — a genuine entry, confirmed live against the loaded
        // country-files.com data the night of the incident.
        var regionStore = new FixedCallsignRegionStore(
            [new CallsignRegionEntry("6K", "6K", "Republic of Korea", "AS", null, null)],
            isSeedData: false);
        var grammarStore = FixedCallsignGrammarStore.Default;

        var validator = new EngagementTargetValidator(regionStore, grammarStore);

        var result = validator.Validate(IncidentToken);

        result.IsAllowed.Should().BeFalse(
            "the matched '6K' prefix's remainder 'ER05BPPBQ' does not fit the digit-run+suffix " +
            "grammar — this is exactly the gap that let tonight's transmission through");
    }
}
