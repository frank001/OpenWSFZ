namespace OpenWSFZ.Web;

/// <summary>
/// Leader-side ingestion seam for relayed WSJT-X-protocol datagrams
/// (<c>external-reporting-single-connection</c> change). Implemented by
/// <c>ExternalReportingService</c> in <c>OpenWSFZ.Daemon</c> and resolved via DI by
/// <c>POST /api/v1/external-reporting/relay</c>, mirroring <see cref="IExternalReplyTarget"/> and
/// <c>IQsoController</c> — defined here (rather than in <c>OpenWSFZ.Abstractions</c>) so
/// <c>OpenWSFZ.Web</c> can depend on the interface without a project reference to
/// <c>OpenWSFZ.Daemon</c>, which itself already depends on <c>OpenWSFZ.Web</c>.
/// </summary>
public interface IExternalReportingRelayTarget
{
    /// <summary>
    /// <c>true</c> when this instance is currently configured to accept relayed traffic
    /// (<c>externalReporting.enabled</c> is <c>true</c> and <c>externalReporting.role</c> is
    /// <c>"leader"</c>). <c>POST /api/v1/external-reporting/relay</c> returns HTTP 503 without
    /// calling <see cref="EnqueueRelayBatch"/> when this is <c>false</c>.
    /// </summary>
    bool CanAcceptRelay { get; }

    /// <summary>
    /// Enqueues an ordered batch of already-encoded WSJT-X-protocol datagram bytes, received from
    /// one follower's relay POST, onto this leader's single-consumer dispatch queue — so the whole
    /// batch is sent to every enabled target atomically, in the order received, and is never
    /// interleaved with another batch (this leader's own outbound traffic, or a different
    /// follower's relayed batch) mid-dispatch (design.md Decision 3).
    /// </summary>
    /// <param name="followerInstanceId">
    /// The relaying follower's own <c>instanceId</c> — carried for logging/diagnostics only; the
    /// leader never re-encodes or reinterprets the datagram bytes themselves.
    /// </param>
    /// <param name="datagrams">One or more already-encoded datagrams, in send order.</param>
    void EnqueueRelayBatch(string followerInstanceId, IReadOnlyList<byte[]> datagrams);
}
