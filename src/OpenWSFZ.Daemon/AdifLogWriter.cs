using System.Globalization;
using System.Text;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Appends completed QSO records to an ADIF log file (FR-048).
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
public sealed class AdifLogWriter
{
    private readonly IConfigStore             _configStore;
    private readonly ILogger<AdifLogWriter>   _logger;

    public AdifLogWriter(IConfigStore configStore, ILogger<AdifLogWriter> logger)
    {
        _configStore = configStore;
        _logger      = logger;
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
                "FR-048: ADIF QSO logged — partner: {Partner}, band: {Band}, path: {Path}",
                record.PartnerCallsign,
                DeriveBand(record.DialFrequencyMHz) ?? "unknown",
                path);
        }
        catch (IOException ex)
        {
            _logger.LogWarning(ex,
                "FR-048: Failed to write ADIF log to '{Path}' — QSO state is unaffected.",
                path);
        }
        catch (UnauthorizedAccessException ex)
        {
            _logger.LogWarning(ex,
                "FR-048: Access denied writing ADIF log to '{Path}' — QSO state is unaffected.",
                path);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex,
                "FR-048: Cannot write ADIF log to '{Path}' — QSO state is unaffected.",
                path);
        }
    }

    // ── Path resolution ───────────────────────────────────────────────────────

    /// <summary>
    /// Resolves the ADIF output path from config.  The ADIF file lives in the same
    /// directory as the ALL.TXT decode log, named <c>ADIF.log</c>.
    /// </summary>
    internal string ResolveAdifPath()
    {
        var decodeLogPath = _configStore.Current.DecodeLog.Path;
        var dir           = Path.GetDirectoryName(decodeLogPath);
        return string.IsNullOrEmpty(dir)
            ? "ADIF.log"
            : Path.Combine(dir, "ADIF.log");
    }

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
        Append(sb, "TIME_ON",      record.QsoStartUtc.ToString("HHmm",     CultureInfo.InvariantCulture));
        Append(sb, "QSO_DATE_OFF", record.QsoEndUtc.ToString("yyyyMMdd",   CultureInfo.InvariantCulture));
        Append(sb, "TIME_OFF",     record.QsoEndUtc.ToString("HHmm",       CultureInfo.InvariantCulture));

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

        sb.Append("<EOR>");
        return sb.ToString();
    }

    // ── Band derivation ───────────────────────────────────────────────────────

    /// <summary>
    /// Derives the ITU amateur band name from a dial frequency in MHz.
    /// Returns <c>null</c> when the frequency is zero or outside all known ham bands.
    /// </summary>
    internal static string? DeriveBand(double freqMHz)
    {
        return freqMHz switch
        {
            >= 1.800 and < 2.000   => "160m",
            >= 3.500 and < 4.000   => "80m",
            >= 5.250 and < 5.450   => "60m",
            >= 7.000 and < 7.300   => "40m",
            >= 10.100 and < 10.150 => "30m",
            >= 14.000 and < 14.350 => "20m",
            >= 18.068 and < 18.168 => "17m",
            >= 21.000 and < 21.450 => "15m",
            >= 24.890 and < 24.990 => "12m",
            >= 28.000 and < 29.700 => "10m",
            >= 50.000 and < 54.000 => "6m",
            >= 144.000 and < 148.000 => "2m",
            >= 420.000 and < 450.000 => "70cm",
            _ => null
        };
    }

    // ── Helper ────────────────────────────────────────────────────────────────

    private static void Append(StringBuilder sb, string fieldName, string value)
        => sb.Append($"<{fieldName}:{value.Length}>{value}");
}
