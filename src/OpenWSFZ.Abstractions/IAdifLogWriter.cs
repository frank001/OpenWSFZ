namespace OpenWSFZ.Abstractions;

/// <summary>
/// Abstraction for writing QSO records to an ADIF log file (qso-log-dialog).
/// Separating the interface from the concrete <c>AdifLogWriter</c> class allows
/// the <c>POST /api/v1/tx/log-qso</c> web endpoint to append ADIF entries without
/// creating a direct dependency from <c>OpenWSFZ.Web</c> to <c>OpenWSFZ.Daemon</c>.
/// </summary>
public interface IAdifLogWriter
{
    /// <summary>
    /// Appends a single completed QSO record to the ADIF log file.
    /// </summary>
    /// <param name="record">The completed QSO data.</param>
    Task AppendQsoAsync(QsoRecord record);
}
