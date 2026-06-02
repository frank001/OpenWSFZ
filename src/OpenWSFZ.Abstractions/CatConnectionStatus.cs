namespace OpenWSFZ.Abstractions;

/// <summary>
/// Represents the live state of the CAT rig connection (FR-031, FR-033).
/// </summary>
public enum CatConnectionStatus
{
    /// <summary>CAT is disabled in configuration (<c>cat.enabled = false</c>).</summary>
    Disabled,

    /// <summary>CAT is enabled and <see cref="IRadioConnection.ConnectAsync"/> is in progress.</summary>
    Connecting,

    /// <summary>A connection is established and frequency polling is active.</summary>
    Connected,

    /// <summary>
    /// A connection or polling failure occurred.
    /// The service will retry automatically after the back-off interval (FR-034).
    /// </summary>
    Error,
}
