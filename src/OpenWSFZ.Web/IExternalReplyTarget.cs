namespace OpenWSFZ.Web;

/// <summary>
/// Routes an inbound WSJT-X-protocol Reply command (<c>external-reporting</c> capability,
/// gridtracker-udp-reporting change) to whichever QSO role service is currently active.
/// Implemented by <c>QsoControllerRouter</c> in <c>OpenWSFZ.Daemon</c>.
///
/// <para>
/// Defined in <c>OpenWSFZ.Web</c> (rather than <c>OpenWSFZ.Abstractions</c>), mirroring
/// <see cref="IQsoRoleSwitcher"/>, so the inbound UDP listener (in <c>OpenWSFZ.Daemon</c>) can
/// resolve this via DI without introducing a project reference cycle, and so a future consumer
/// in <c>OpenWSFZ.Web</c> itself (there is none today) could resolve it the same way.
/// </para>
/// </summary>
public interface IExternalReplyTarget
{
    /// <summary>
    /// Attempts to engage <paramref name="callsign"/> exactly as an operator manually selecting
    /// that station would. Delegates to <c>QsoAnswererService.TryEngageExternal</c> when the
    /// active role is Answerer, or to the existing, unmodified
    /// <c>QsoCallerService.SelectResponderAsync</c> seam when the active role is Caller.
    /// </summary>
    /// <param name="callsign">Callsign named by the inbound Reply datagram.</param>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>
    /// <c>true</c> if the callsign was engaged; <c>false</c> if it does not correspond to a
    /// currently engageable station (unknown, filtered out, or the service is not in a state
    /// that accepts a new engagement).
    /// </returns>
    Task<bool> TryEngageAsync(string callsign, CancellationToken ct = default);
}
