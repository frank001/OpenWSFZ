namespace OpenWSFZ.Abstractions;

/// <summary>The states the Settings page shows next to the PSK Reporter checkbox (FR-095).</summary>
public static class PskReporterStates
{
    /// <summary>The upload is disabled.</summary>
    public const string Off = "off";

    /// <summary>Enabled, no datagram sent yet and nothing is being refused.</summary>
    public const string Waiting = "waiting";

    /// <summary>Enabled and a datagram has been sent.</summary>
    public const string Sending = "sending";

    /// <summary>Enabled but every decode seen is being excluded for one of the reasons below.</summary>
    public const string Refused = "refused";
}

/// <summary>Reason codes of the <see cref="PskReporterStates.Refused"/> state.</summary>
public static class PskReporterReasons
{
    /// <summary>The receiver call or locator is a placeholder.</summary>
    public const string Identity = "identity";

    /// <summary>No usable dial frequency.</summary>
    public const string NoDial = "no-dial";

    /// <summary>Unknown or synthetic region.</summary>
    public const string Region = "region";
}

/// <summary>Counts of one send window (no callsign, ever).</summary>
public sealed record PskReporterWindowCounts(
    int Seen, int Reported, int Region, int NoDial, int Identity, int Hashed, int OwnCall, int Dedup);

/// <summary>
/// The read-only status body of <c>GET /api/v1/psk-reporter/status</c>: counts and a reason code, no callsign.
/// </summary>
/// <param name="State">One of <see cref="PskReporterStates"/>.</param>
/// <param name="LastDatagramUtc">UTC time of the last datagram sent, or null.</param>
/// <param name="LastDatagramRecords">Sender records in that datagram.</param>
/// <param name="Reason">One of <see cref="PskReporterReasons"/> when <see cref="State"/> is refused, else null.</param>
/// <param name="Window">The counters of the window in progress and the last closed one, summed (the figures behind the state).</param>
public sealed record PskReporterStatus(
    string State, DateTime? LastDatagramUtc, int LastDatagramRecords, string? Reason, PskReporterWindowCounts Window);

/// <summary>Source of the PSK Reporter status (implemented by the daemon's service from the same counters as the window log line).</summary>
public interface IPskReporterStatusSource
{
    /// <summary>The current status.</summary>
    PskReporterStatus GetStatus();
}
