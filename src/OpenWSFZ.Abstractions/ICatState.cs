namespace OpenWSFZ.Abstractions;

/// <summary>
/// Read-only view of live CAT telemetry (FR-032, FR-033).
/// Implemented by <c>OpenWSFZ.Daemon.CatState</c> and registered as a singleton in DI.
///
/// <para>
/// Thread-safety contract: all members MAY be read from any thread without
/// external synchronisation. The implementation guarantees torn-read-free access.
/// </para>
/// </summary>
public interface ICatState
{
    /// <summary>
    /// Live VFO-A dial frequency in MHz as reported by the rig, or <c>null</c> when
    /// CAT is disabled, in error, or no successful poll has completed yet (FR-032).
    /// </summary>
    double? DialFrequencyMHz { get; }

    /// <summary>Current CAT connection state (FR-033).</summary>
    CatConnectionStatus Status { get; }
}
