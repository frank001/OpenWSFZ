namespace OpenWSFZ.Abstractions;

/// <summary>
/// The TX role the daemon is configured to operate in.
/// Persisted in <see cref="TxConfig.Role"/>; a restart is required when the role changes.
/// </summary>
public enum TxRole
{
    /// <summary>Respond to incoming CQ calls (default).</summary>
    Answerer = 0,

    /// <summary>Originate CQ calls.</summary>
    Caller = 1,
}
