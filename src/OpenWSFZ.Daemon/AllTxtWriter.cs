using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Appends decoded FT8 messages to an ALL.TXT file in WSJT-X compatible format
/// after each decode cycle (FR-028).
///
/// <para>
/// Line format (exactly matching WSJT-X ALL.TXT):
/// <code>
/// YYMMDD_HHMMSS     D.DDD Rx FT8 {snr,6} {dt,5:F1} {freq,4} {message}
/// </code>
/// </para>
///
/// <para>
/// The file is opened in append mode, written, and closed once per cycle (D2).
/// File write failures are logged at Warning and do not throw — the decode
/// pipeline and WebSocket broadcast are unaffected (D1).
/// </para>
/// </summary>
public sealed class AllTxtWriter
{
    private readonly IConfigStore         _configStore;
    private readonly ILogger<AllTxtWriter> _logger;

    public AllTxtWriter(IConfigStore configStore, ILogger<AllTxtWriter> logger)
    {
        _configStore = configStore;
        _logger      = logger;
    }

    /// <summary>
    /// Appends one line per result to the configured ALL.TXT file.
    /// Returns immediately if decode logging is disabled or <paramref name="results"/> is empty.
    /// </summary>
    /// <param name="cycleUtc">
    ///   UTC wall-clock time captured immediately before <c>DecodeAsync</c> was called.
    ///   The date component of each line is derived from this value (D3).
    /// </param>
    /// <param name="results">Decoded messages from this cycle.</param>
    public async Task AppendAsync(DateTime cycleUtc, IReadOnlyList<DecodeResult> results)
    {
        var config = _configStore.Current.DecodeLog;

        if (!config.Enabled || results.Count == 0)
            return;

        var path = config.Path;

        try
        {
            // Create parent directories if they do not exist.
            var dir = System.IO.Path.GetDirectoryName(path);
            if (!string.IsNullOrEmpty(dir))
                Directory.CreateDirectory(dir);

            // Open in append mode (create if absent), write all lines, close (D2).
            await using var writer = new StreamWriter(path, append: true, System.Text.Encoding.ASCII)
            {
                NewLine = "\r\n"
            };

            string date     = cycleUtc.ToString("yyMMdd");
            double dialMhz  = config.DialFrequencyMHz;

            foreach (var result in results)
            {
                // "17:29:30" → "172930"
                string timePart = result.Time.Replace(":", "", StringComparison.Ordinal);
                string timestamp = $"{date}_{timePart}";

                // D5: exact WSJT-X column layout.
                string line = $"{timestamp}     {dialMhz:F3} Rx FT8 {result.Snr,6} {result.Dt,4:F1} {result.FreqHz,4} {result.Message}";
                await writer.WriteLineAsync(line);
            }
        }
        catch (IOException ex)
        {
            _logger.LogWarning(ex,
                "FR-028: Failed to write decode log to '{Path}' — {Message}. " +
                "Decode results and WebSocket broadcast are unaffected.",
                path, ex.Message);
        }
        catch (UnauthorizedAccessException ex)
        {
            _logger.LogWarning(ex,
                "FR-028: Access denied writing decode log to '{Path}' — {Message}. " +
                "Decode results and WebSocket broadcast are unaffected.",
                path, ex.Message);
        }
    }
}
