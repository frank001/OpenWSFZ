using System.Globalization;
using System.Text;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Appends completed QSO records to an ADIF log file (FR-051).
///
/// <para>
/// The output file is placed in the same directory as the ALL.TXT decode log
/// (<c>decodeLog.path</c> from <see cref="IConfigStore"/>), named <c>ADIF.log</c>.
/// If <c>decodeLog.path</c> has no directory component the ADIF file is created
/// in the current working directory.
/// </para>
///
/// <para>
/// Each QSO record uses the ADIF tagged-field format:
/// <code>
///   &lt;FIELD_NAME:length&gt;value
/// </code>
/// and is terminated by <c>&lt;EOR&gt;\r\n</c> (a blank line between records is
/// not emitted — most logging software accepts either style).
/// </para>
///
/// <para>
/// Write failures are logged at Warning and do not throw — the QSO state machine
/// is not affected (task 7.7).
/// </para>
/// </summary>
public sealed class AdifLogWriter : IAdifLogWriter
{
    private readonly IConfigStore             _configStore;
    private readonly ILogger<AdifLogWriter>   _logger;
    private readonly IWorkedBeforeIndex?      _workedBeforeIndex;

    /// <param name="configStore">Resolves the ADIF output path (same directory as ALL.TXT).</param>
    /// <param name="logger">Structured logger for write successes/failures.</param>
    /// <param name="workedBeforeIndex">
    /// Optional live worked-before index (<c>qso-confirmation</c> capability). When supplied,
    /// a successful write registers the just-logged partner callsign into the index so the very
    /// next decode of that station resolves "worked before" without a daemon restart. A failed
    /// write never registers the callsign. When <c>null</c>, existing callers that do not wire
    /// this up keep today's behaviour (no worked-before tracking).
    /// </param>
    public AdifLogWriter(
        IConfigStore           configStore,
        ILogger<AdifLogWriter> logger,
        IWorkedBeforeIndex?    workedBeforeIndex = null)
    {
        _configStore       = configStore;
        _logger            = logger;
        _workedBeforeIndex = workedBeforeIndex;
    }

    // ── Public API ────────────────────────────────────────────────────────────

    /// <summary>
    /// Appends a single completed QSO record to the ADIF log file.
    /// </summary>
    /// <param name="record">The completed QSO data.</param>
    public async Task AppendQsoAsync(QsoRecord record)
    {
        var path = ResolveAdifPath();

        try
        {
            var dir = Path.GetDirectoryName(path);
            if (!string.IsNullOrEmpty(dir))
                Directory.CreateDirectory(dir);

            var adif = BuildAdifRecord(record);

            await using var writer = new StreamWriter(path, append: true, Encoding.ASCII)
            {
                NewLine = "\r\n"
            };
            await writer.WriteLineAsync(adif);

            _logger.LogInformation(
                "FR-051: ADIF QSO logged — partner: {Partner}, band: {Band}, path: {Path}",
                record.PartnerCallsign,
                DeriveBand(record.DialFrequencyMHz) ?? "unknown",
                path);

            // qso-confirmation: register the just-logged callsign (and the band it was worked
            // on — already computed above for this record's own BAND tag) into the live
            // worked-before index so the very next decode of this station resolves "worked
            // before" without a daemon restart or a re-read of ADIF.log
            // (qso-confirmation-band-awareness design.md Decision 5). Only reached on a
            // successful write — a failed write below never registers the callsign.
            _workedBeforeIndex?.Register(record.PartnerCallsign, DeriveBand(record.DialFrequencyMHz));
        }
        catch (IOException ex)
        {
            _logger.LogWarning(ex,
                "FR-051: Failed to write ADIF log to '{Path}' — QSO state is unaffected.",
                path);
        }
        catch (UnauthorizedAccessException ex)
        {
            _logger.LogWarning(ex,
                "FR-051: Access denied writing ADIF log to '{Path}' — QSO state is unaffected.",
                path);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex,
                "FR-051: Cannot write ADIF log to '{Path}' — QSO state is unaffected.",
                path);
        }
    }

    // ── Path resolution ───────────────────────────────────────────────────────

    /// <summary>
    /// Resolves the ADIF output path from config.  The ADIF file lives in the same
    /// directory as the ALL.TXT decode log, named <c>ADIF.log</c>.
    /// Delegates to <see cref="AdifPathResolver"/> (shared with <see cref="WorkedBeforeIndex"/>,
    /// <c>qso-confirmation</c> capability) so both components always agree on the path.
    /// </summary>
    internal string ResolveAdifPath() => AdifPathResolver.Resolve(_configStore);

    // ── ADIF record builder ───────────────────────────────────────────────────

    /// <summary>
    /// Builds the ADIF record string (single line, no trailing newline).
    /// </summary>
    internal static string BuildAdifRecord(QsoRecord record)
    {
        var sb = new StringBuilder(256);

        // Partner fields
        Append(sb, "CALL",         record.PartnerCallsign);
        if (!string.IsNullOrWhiteSpace(record.PartnerGrid))
            Append(sb, "GRIDSQUARE", record.PartnerGrid);

        // RST
        Append(sb, "RST_SENT", record.RstSent);
        Append(sb, "RST_RCVD", record.RstRcvd);

        // QSO timing (UTC)
        Append(sb, "QSO_DATE",     record.QsoStartUtc.ToString("yyyyMMdd", CultureInfo.InvariantCulture));
        Append(sb, "TIME_ON",      record.QsoStartUtc.ToString("HHmmss",   CultureInfo.InvariantCulture));
        Append(sb, "QSO_DATE_OFF", record.QsoEndUtc.ToString("yyyyMMdd",   CultureInfo.InvariantCulture));
        Append(sb, "TIME_OFF",     record.QsoEndUtc.ToString("HHmmss",     CultureInfo.InvariantCulture));

        // Operator
        Append(sb, "OPERATOR",       record.OperatorCallsign);
        Append(sb, "MY_GRIDSQUARE",  record.OperatorGrid);

        // Mode
        Append(sb, "MODE", "FT8");

        // Frequency and band (omitted when dial freq is 0.0)
        if (record.DialFrequencyMHz != 0.0)
        {
            var freqStr = record.DialFrequencyMHz.ToString("F6", CultureInfo.InvariantCulture)
                                                  .TrimEnd('0').TrimEnd('.');
            Append(sb, "FREQ", freqStr);

            var band = DeriveBand(record.DialFrequencyMHz);
            if (band is not null)
                Append(sb, "BAND", band);
        }

        // Optional enrichment fields (qso-log-dialog) — only written when non-null and non-empty.
        if (!string.IsNullOrEmpty(record.PartnerName)) Append(sb, "NAME",       record.PartnerName);
        if (!string.IsNullOrEmpty(record.TxPower))     Append(sb, "TX_PWR",     record.TxPower);
        if (!string.IsNullOrEmpty(record.Comment))     Append(sb, "COMMENT",    record.Comment);
        if (!string.IsNullOrEmpty(record.PropMode))    Append(sb, "PROP_MODE",  record.PropMode);
        if (!string.IsNullOrEmpty(record.ExchSent))    Append(sb, "STX_STRING", record.ExchSent);
        if (!string.IsNullOrEmpty(record.ExchRcvd))    Append(sb, "SRX_STRING", record.ExchRcvd);

        sb.Append("<EOR>");
        return sb.ToString();
    }

    // ── Band derivation ───────────────────────────────────────────────────────

    /// <summary>
    /// Derives the ITU amateur band name from a dial frequency in MHz.
    /// Returns <c>null</c> when the frequency is zero or outside all known ham bands.
    /// Forwards to the shared <see cref="BandTable"/> (<c>qso-confirmation-band-awareness</c>
    /// design.md Decision 4) so this writer's own <c>BAND</c> tag and the decode pump's
    /// "current active band" resolution never drift onto two different tables.
    /// </summary>
    internal static string? DeriveBand(double freqMHz) => BandTable.DeriveBand(freqMHz);

    // ── Helper ────────────────────────────────────────────────────────────────

    private static void Append(StringBuilder sb, string fieldName, string value)
        => sb.Append($"<{fieldName}:{value.Length}>{value}");
}
