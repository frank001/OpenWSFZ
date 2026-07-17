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
    private readonly SemaphoreSlim                  _saveLock = new(1, 1);
    private volatile IReadOnlyList<CallsignRegionEntry> _entries;
    // engagement-target-validation (design.md Decision 2): starts true; flips to false once a
    // SaveAsync (refresh) succeeds, or once an on-disk callsign-regions.json is loaded whose own
    // persisted "isSeedData" marker says false — never flips back to true from an in-session read.
    // A malformed-file or write-failure fallback to the seed table does NOT count as "loaded real
    // data", so IsSeedData correctly stays true in those cases. (Finding E, dev-task
    // 2026-07-17-engagement-target-validation-qa-review-findings: provenance must come from the
    // file's own content, not merely from the file existing — see LoadAsync's remarks.)
    private volatile bool _isSeedData = true;

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
    public bool IsSeedData => _isSeedData;

    /// <inheritdoc/>
    public RegionInfo? TryGetRegion(string callsignToken) => TryMatchPrefix(callsignToken)?.Region;

    /// <inheritdoc/>
    public CallsignRegionMatch? TryMatchPrefix(string callsignToken)
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

        if (best is null) return null;

        var region = new RegionInfo(best.Continent, best.Entity, best.Synthetic, best.CqZone, best.ItuZone);
        return new CallsignRegionMatch(region, best.PrefixStart.Length);
    }

    /// <inheritdoc/>
    /// <remarks>
    /// region-lookup-data-refresh (f-006): reuses the same atomic write-to-temp-then-rename
    /// logic as the missing-file seed path in <see cref="LoadAsync"/>. A <see cref="SemaphoreSlim"/>
    /// serialises concurrent callers so two simultaneous saves cannot race on the final
    /// <see cref="File.Move(string, string, bool)"/> to the shared destination path — mirroring
    /// <see cref="FrequencyStore.SaveAsync"/>. <see cref="Entries"/> is assigned only after
    /// <see cref="WriteAsync"/> completes successfully, so a failed write leaves the previous
    /// in-memory table (and on-disk file) unchanged.
    /// <para>
    /// Discovered live during f-006's own manual end-to-end verification (task 5.2): the
    /// pre-existing, unconditional <c>region-lookup</c> requirement "Synthetic Q-prefix
    /// callsigns resolve to a distinct synthetic region" has no carve-out for a runtime refresh,
    /// yet a real country-files.com release naturally contains no <c>Q</c>-series entry — a
    /// refresh with real data would otherwise silently regress that requirement (synthetic
    /// R&amp;R-study traffic would start resolving to <c>"Unknown"</c>). <see cref="SaveAsync"/>
    /// therefore guarantees the synthetic entry survives <em>any</em> caller's replacement list,
    /// rather than depending on every future caller to remember to preserve it.
    /// </para>
    /// </remarks>
    public async Task SaveAsync(
        IReadOnlyList<CallsignRegionEntry> entries,
        CancellationToken                  cancellationToken = default)
    {
        var toWrite = entries.Any(e => e.Synthetic)
            ? entries
            : [.. entries, .. CallsignRegionDefaults.Entries.Where(e => e.Synthetic)];

        await _saveLock.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            await WriteAsync(toWrite, isSeedData: false, cancellationToken);
            _entries     = toWrite;
            // engagement-target-validation: a successful operator-triggered refresh is real data,
            // regardless of what was loaded at startup.
            _isSeedData  = false;
            _logger?.LogInformation(
                "Saved {Count} region entr{Ies} to '{Path}'.",
                toWrite.Count, toWrite.Count == 1 ? "y" : "ies", _path);
        }
        finally
        {
            _saveLock.Release();
        }
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
                await WriteAsync(CallsignRegionDefaults.Entries, isSeedData: true, cancellationToken);
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

            _entries    = dto.Entries;
            // engagement-target-validation (design.md Decision 2; corrected per Finding E, dev-task
            // 2026-07-17-engagement-target-validation-qa-review-findings): provenance comes from
            // the file's own persisted marker, not from the mere fact that a file exists on disk —
            // the seed-write branch above writes this same file, so its mere existence on a
            // second-or-later launch does not by itself mean an operator ever refreshed. A
            // pre-existing file from before this marker existed deserialises IsSeedData as `false`
            // (missing-property JSON default) — a deliberate migration choice: an operator who has
            // been running the daemon long enough to have a pre-existing file is more likely to
            // have refreshed at least once than not, and there is no way to tell retroactively.
            _isSeedData = dto.IsSeedData;
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

    private async Task WriteAsync(
        IReadOnlyList<CallsignRegionEntry> entries, bool isSeedData, CancellationToken cancellationToken)
    {
        var dir = Path.GetDirectoryName(_path)
            ?? throw new InvalidOperationException($"Cannot determine directory for '{_path}'.");

        Directory.CreateDirectory(dir);

        var dto = new CallsignRegionsFile { Entries = [.. entries], IsSeedData = isSeedData };
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
