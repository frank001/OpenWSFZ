using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Web;

/// <summary>
/// Pass-through <see cref="IEngagementTargetValidator"/>: allows every candidate unconditionally.
/// Registered by default in <see cref="WebApp.Create"/> for any caller that doesn't wire up
/// <c>OpenWSFZ.Daemon</c>'s region/grammar stores (test fixtures, minimal hosts) — identical in
/// spirit to <see cref="NullAuthPolicy"/> and to the real <c>EngagementTargetValidator</c>'s own
/// behaviour whenever <c>ICallsignRegionStore.IsSeedData</c> is <c>true</c>. The daemon overrides
/// this registration via <c>configureServices</c> with the real, region/grammar-store-backed
/// validator (<c>engagement-target-validation</c> capability).
/// </summary>
public sealed class NullEngagementTargetValidator : IEngagementTargetValidator
{
    /// <inheritdoc/>
    /// <remarks>Always returns <see cref="EngagementValidationResult.Allowed"/>.</remarks>
    public EngagementValidationResult Validate(string callsignToken) => EngagementValidationResult.Allowed;
}
