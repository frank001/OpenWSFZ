namespace OpenWSFZ.Abstractions;

/// <summary>
/// Outcome of <see cref="IEngagementTargetValidator.Validate"/>: either <see cref="Allowed"/> or
/// <see cref="Rejected"/> carrying an operator-facing reason. Not a positive verdict on the
/// callsign's genuineness — only that nothing in the region-anchored grammar check found it
/// implausible (<c>engagement-target-validation</c> capability).
/// </summary>
/// <param name="IsAllowed"><c>true</c> when the candidate may be armed as a TX-engagement target.</param>
/// <param name="RejectionReason">
/// Human-readable reason the candidate was rejected, or <c>null</c> when <see cref="IsAllowed"/> is
/// <c>true</c>.
/// </param>
public sealed record EngagementValidationResult(bool IsAllowed, string? RejectionReason)
{
    /// <summary>The candidate may be armed as a TX-engagement target.</summary>
    public static EngagementValidationResult Allowed { get; } = new(true, null);

    /// <summary>The candidate must not be armed as a TX-engagement target, for <paramref name="reason"/>.</summary>
    public static EngagementValidationResult Rejected(string reason) => new(false, reason);
}

/// <summary>
/// Gates whether a decoded callsign token may be armed as a live TX-engagement target — manual
/// <c>POST /api/v1/tx/engage-decode</c>, automated CQ auto-answer arming
/// (<c>QsoAnswererService</c>), or automated responder matching (<c>QsoCallerService</c>).
/// Distinct from, and strictly narrower than, decode acceptance
/// (<c>callsign-structure-validation</c>) — a token this validator rejects is still decoded,
/// logged to <c>ALL.TXT</c>, and displayed in the decode panel exactly as before.
/// <c>engagement-target-validation</c> capability; see design.md Decision 3.
/// </summary>
public interface IEngagementTargetValidator
{
    /// <summary>
    /// Validates <paramref name="callsignToken"/> against the region-anchored callsign grammar
    /// check. Always <see cref="EngagementValidationResult.Allowed"/> while
    /// <see cref="ICallsignRegionStore.IsSeedData"/> is <c>true</c> (gate inactive — see the
    /// capability's spec for the full algorithm).
    /// </summary>
    EngagementValidationResult Validate(string callsignToken);
}
