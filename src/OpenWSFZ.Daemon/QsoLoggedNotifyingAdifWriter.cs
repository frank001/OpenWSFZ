using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Decorates the real <see cref="AdifLogWriter"/> so every successful call to
/// <see cref="IAdifLogWriter.AppendQsoAsync"/> also notifies <see cref="ExternalReportingService"/>
/// to emit an outbound WSJT-X QSOLogged datagram (<c>external-reporting</c> capability,
/// "Outbound QSOLogged message" requirement).
///
/// <para>
/// This is the single choke point every ADIF-write call site goes through:
/// <c>QsoAnswererService</c>'s/<c>QsoCallerService</c>'s direct-write path
/// (<c>tx.qsoConfirmation=false</c>) and <c>WebApp</c>'s <c>POST /api/v1/tx/log-qso</c>
/// (<c>tx.qsoConfirmation=true</c>, the default) both resolve <see cref="IAdifLogWriter"/> from
/// DI — decorating the interface registration, rather than hooking each call site individually,
/// guarantees coverage without risking a missed site. A QSO aborted by watchdog or operator never
/// calls <see cref="AppendQsoAsync"/> at all, so it correctly never triggers a QSOLogged datagram
/// either (mirrors FR-051's own "no record on abort" rule).
/// </para>
/// </summary>
public sealed class QsoLoggedNotifyingAdifWriter(
    IAdifLogWriter             inner,
    ExternalReportingService   externalReporting) : IAdifLogWriter
{
    /// <inheritdoc/>
    public async Task AppendQsoAsync(QsoRecord record)
    {
        await inner.AppendQsoAsync(record).ConfigureAwait(false);
        externalReporting.NotifyQsoLogged(record);
    }
}
