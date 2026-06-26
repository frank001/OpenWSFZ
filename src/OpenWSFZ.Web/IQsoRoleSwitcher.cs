namespace OpenWSFZ.Web;

/// <summary>
/// Optional service that allows runtime switching of the active QSO controller role
/// without a daemon restart.  Implemented by <c>QsoControllerRouter</c> in
/// <c>OpenWSFZ.Daemon</c> when both role services are registered.
///
/// <para>
/// Defined in <c>OpenWSFZ.Web</c> (rather than <c>OpenWSFZ.Abstractions</c>) so that
/// <see cref="WebApp"/> route handlers can resolve it without introducing a project
/// reference from <c>OpenWSFZ.Web</c> to <c>OpenWSFZ.Daemon</c>.
/// </para>
/// </summary>
public interface IQsoRoleSwitcher
{
    /// <summary>
    /// Switches the active QSO controller role to Caller and arms <c>AutoAnswer</c>
    /// so the caller transmits CQ on the next FT8 cycle.  If the active role is
    /// already Caller, only arms <c>AutoAnswer</c> (idempotent).
    /// </summary>
    Task SwitchToCallerAsync(CancellationToken ct = default);
}
