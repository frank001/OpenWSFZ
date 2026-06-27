using System.Text.Json;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Manages a JSON-backed list of propagation mode entries (qso-log-dialog).
///
/// <para>
/// The backing file is <c>prop-modes.json</c>, located in the same directory as
/// <c>appconfig.json</c> (resolved via <c>LaunchOptions.ConfigPath</c>).
/// If the file does not exist on startup, or contains an empty array, the default
/// FT8 seed (10 entries) is written and used.
/// </para>
///
/// <para>
/// Mirrors the architecture of <see cref="FrequencyStore"/>: atomic temp-then-rename
/// writes, a semaphore to serialise concurrent saves, and an optional logger.
/// </para>
/// </summary>
public sealed class PropModeStore : IPropModeStore
{
    private readonly string                           _path;
    private readonly ILogger<PropModeStore>?          _logger;
    private readonly SemaphoreSlim                    _saveLock = new(1, 1);
    private volatile IReadOnlyList<PropModeEntry>     _entries;

    /// <summary>Default FT8 propagation mode seed (10 entries).</summary>
    public static readonly IReadOnlyList<PropModeEntry> DefaultEntries =
    [
        new PropModeEntry("FT8", "",         "Not specified"),
        new PropModeEntry("FT8", "TR",       "Tropospheric Ducting"),
        new PropModeEntry("FT8", "ES",       "Sporadic E"),
        new PropModeEntry("FT8", "F2",       "F2 Reflection"),
        new PropModeEntry("FT8", "EME",      "Earth-Moon-Earth"),
        new PropModeEntry("FT8", "MS",       "Meteor Scatter"),
        new PropModeEntry("FT8", "TEP",      "Trans-Equatorial"),
        new PropModeEntry("FT8", "SAT",      "Satellite"),
        new PropModeEntry("FT8", "LOS",      "Line of Sight"),
        new PropModeEntry("FT8", "INTERNET", "Internet-assisted"),
    ];

    /// <param name="path">Resolved path to <c>prop-modes.json</c>.</param>
    /// <param name="logger">Optional logger for diagnostics.</param>
    public PropModeStore(string path, ILogger<PropModeStore>? logger = null)
    {
        _path    = path;
        _logger  = logger;
        _entries = DefaultEntries; // safe default before LoadAsync
    }

    // ── Public API ────────────────────────────────────────────────────────────

    /// <summary>The current list of propagation mode entries.</summary>
    public IReadOnlyList<PropModeEntry> Entries => _entries;

    /// <summary>
    /// Replaces the stored list atomically and persists it to <c>prop-modes.json</c>.
    /// </summary>
    public async Task SaveAsync(
        IEnumerable<PropModeEntry> entries,
        CancellationToken          cancellationToken = default)
    {
        var list = entries.ToList();

        var dir = Path.GetDirectoryName(_path)
            ?? throw new InvalidOperationException(
                $"Cannot determine directory for '{_path}'.");

        Directory.CreateDirectory(dir);

        var tmp = Path.Combine(dir, Path.GetRandomFileName());
        await _saveLock.WaitAsync(cancellationToken).ConfigureAwait(false);
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
                    stream,
                    list,
                    PropModeJsonContext.Default.ListPropModeEntry,
                    cancellationToken);
            }

            File.Move(tmp, _path, overwrite: true);
            _entries = list;
            _logger?.LogInformation("Prop modes saved to '{Path}' ({Count} entries).", _path, list.Count);
        }
        catch
        {
            try { File.Delete(tmp); } catch { /* best-effort */ }
            throw;
        }
        finally
        {
            _saveLock.Release();
        }
    }

    // ── Startup ───────────────────────────────────────────────────────────────

    /// <summary>
    /// Loads <c>prop-modes.json</c> from the configured path.
    /// <list type="bullet">
    ///   <item>Absent file → writes the default FT8 seed and uses it.</item>
    ///   <item>Empty array → writes the default FT8 seed (reseeds).</item>
    ///   <item>Malformed file → logs Error, uses compiled-in defaults in memory (does not overwrite).</item>
    ///   <item>Valid file → loads and uses it.</item>
    /// </list>
    /// </summary>
    public async Task LoadAsync(CancellationToken cancellationToken = default)
    {
        if (!File.Exists(_path))
        {
            _logger?.LogInformation(
                "prop-modes.json not found at '{Path}' — writing default FT8 seed.", _path);
            try
            {
                await SaveAsync(DefaultEntries, cancellationToken);
            }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
            {
                // In test environments (WebApplicationFactory) the target path may be
                // inaccessible.  Use the compiled-in defaults in memory; this is safe
                // because the DI container will replace IPropModeStore anyway.
                _logger?.LogWarning(ex,
                    "Cannot write default prop-modes.json to '{Path}' — " +
                    "using compiled-in defaults in memory.", _path);
                _entries = DefaultEntries;
            }
            return;
        }

        try
        {
            var json    = await File.ReadAllTextAsync(_path, cancellationToken);
            var entries = JsonSerializer.Deserialize(
                json,
                PropModeJsonContext.Default.ListPropModeEntry);

            if (entries is null || entries.Count == 0)
            {
                _logger?.LogInformation(
                    "prop-modes.json at '{Path}' is empty — reseeding with default FT8 entries.", _path);
                try
                {
                    await SaveAsync(DefaultEntries, cancellationToken);
                }
                catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
                {
                    _logger?.LogWarning(ex,
                        "Cannot reseed prop-modes.json at '{Path}' — " +
                        "using compiled-in defaults in memory.", _path);
                    _entries = DefaultEntries;
                }
                return;
            }

            _entries = entries;
            _logger?.LogInformation(
                "Loaded {Count} prop mode entr{Ies} from '{Path}'.",
                _entries.Count,
                _entries.Count == 1 ? "y" : "ies",
                _path);
        }
        catch (JsonException ex)
        {
            _logger?.LogError(ex,
                "prop-modes.json at '{Path}' is malformed — using compiled-in defaults " +
                "(file NOT overwritten).", _path);
            _entries = DefaultEntries;
        }
    }
}
