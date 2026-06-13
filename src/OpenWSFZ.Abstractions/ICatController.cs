namespace OpenWSFZ.Abstractions;

/// <summary>
/// Lifecycle-control surface for the CAT polling subsystem (FR-034).
/// Implemented by <c>CatPollingService</c>; injected into the web layer via DI
/// so that <c>POST /api/v1/cat/retry</c> can clear the failure suspension without
/// depending on the Daemon assembly.
/// </summary>
public interface ICatController
{
    /// <summary>
    /// Signals the poll loop to immediately attempt a reconnect on its next
    /// iteration, clearing any prior failure suspension without requiring a
    /// config change.  Safe to call from any thread; the poll loop consumes the
    /// signal on its next tick.
    /// </summary>
    void TriggerRetry();
}
