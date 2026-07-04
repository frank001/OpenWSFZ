using System.Text.Json;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Concrete <see cref="ICallsignRegionStore"/> that reads <c>callsign-regions.json</c>,
/// following the <see cref="FrequencyStore"/> pattern. Unlike <see cref="CallsignGrammarStore"/>,
/// a malformed file falls back to <em>empty</em> (Unknown-only) rather than a built-in
/// seed list — a corrupted region file has no safe non-empty default to fall back to,
/// and "Unknown" for every lookup is always a safe, honest advisory answer.
/// </summary>
public sealed class CallsignRegionStore : ICallsignRegionStore
{
    private readonly string                         _path;
    private readonly ILogger<CallsignRegionStore>?  _logger;
    private volatile IReadOnlyList<CallsignRegionEntry> _entries;

    /// <param name="path">Resolved path to <c>callsign-regions.json</c>.</param>
    /// <param name="logger">Optional logger for diagnostics.</param>
    public CallsignRegionStore(string path, ILogger<CallsignRegionStore>? logger = null)
    {
        _path    = path;
        _logger  = logger;
        _entries = []; // Unknown-only until LoadAsync
    }

    /// <inheritdoc/>
    public IReadOnlyList<CallsignRegionEntry> Entries => _entries;

    /// <inheritdoc/>
    public RegionInfo? TryGetRegion(string callsignToken)
    {
        if (string.IsNullOrEmpty(callsignToken)) return null;

        var token = callsignToken.ToUpperInvariant();

        CallsignRegionEntry? best = null;
        foreach (var entry in _entries)
        {
            var len = entry.PrefixStart.Length;
            if (len == 0 || entry.PrefixEnd.Length != len) continue; // malformed entry guard
            if (token.Length < len) continue;

            var candidate = token[..len];
            if (string.CompareOrdinal(candidate, entry.PrefixStart) < 0 ||
                string.CompareOrdinal(candidate, entry.PrefixEnd) > 0)
                continue;

            // Prefer the longest (most specific) matching prefix range.
            if (best is null || len > best.PrefixStart.Length)
                best = entry;
        }

        return best is null
            ? null
            : new RegionInfo(best.Continent, best.Entity, best.Synthetic);
    }

    // ── Startup ───────────────────────────────────────────────────────────────

    /// <summary>
    /// Loads <c>callsign-regions.json</c> from the configured path.
    /// <list type="bullet">
    ///   <item>Absent file → writes <see cref="CallsignRegionDefaults.Entries"/> and uses it.</item>
    ///   <item>Malformed file → logs Warning, all lookups resolve to <c>null</c> ("Unknown")
    ///         until corrected (file NOT overwritten).</item>
    ///   <item>Valid file → loads and uses it.</item>
    /// </list>
    /// </summary>
    public async Task LoadAsync(CancellationToken cancellationToken = default)
    {
        if (!File.Exists(_path))
        {
            _logger?.LogInformation(
                "callsign-regions.json not found at '{Path}' — writing seed region data.", _path);
            try
            {
                await WriteAsync(CallsignRegionDefaults.Entries, cancellationToken);
                _entries = CallsignRegionDefaults.Entries;
            }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
            {
                _logger?.LogWarning(ex,
                    "Cannot write default callsign-regions.json to '{Path}' — " +
                    "using seed region data in memory.", _path);
                _entries = CallsignRegionDefaults.Entries;
            }
            return;
        }

        try
        {
            var json = await File.ReadAllTextAsync(_path, cancellationToken);
            var dto  = JsonSerializer.Deserialize(json, CallsignJsonContext.Default.CallsignRegionsFile);

            if (dto is null)
            {
                _logger?.LogWarning(
                    "callsign-regions.json at '{Path}' deserialised as null — all region " +
                    "lookups resolve to Unknown until corrected (file NOT overwritten).", _path);
                _entries = [];
                return;
            }

            _entries = dto.Entries;
            _logger?.LogInformation(
                "Loaded {Count} region entr{Ies} from '{Path}'.",
                _entries.Count, _entries.Count == 1 ? "y" : "ies", _path);
        }
        catch (JsonException ex)
        {
            _logger?.LogWarning(ex,
                "callsign-regions.json at '{Path}' is malformed — all region lookups resolve " +
                "to Unknown until corrected (file NOT overwritten).", _path);
            _entries = [];
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private async Task WriteAsync(IReadOnlyList<CallsignRegionEntry> entries, CancellationToken cancellationToken)
    {
        var dir = Path.GetDirectoryName(_path)
            ?? throw new InvalidOperationException($"Cannot determine directory for '{_path}'.");

        Directory.CreateDirectory(dir);

        var dto = new CallsignRegionsFile { Entries = [.. entries] };
        var tmp = Path.Combine(dir, Path.GetRandomFileName());
        try
        {
            await using (var stream = new FileStream(
                tmp,
                FileMode.Create,
                FileAccess.Write,
                FileShare.None,
                bufferSize: 4096,
                useAsync: true))
            {
                await JsonSerializer.SerializeAsync(
                    stream, dto, CallsignJsonContext.Default.CallsignRegionsFile, cancellationToken);
            }

            File.Move(tmp, _path, overwrite: true);
        }
        catch
        {
            try { File.Delete(tmp); } catch { /* best-effort */ }
            throw;
        }
    }
}
