using System.Text.Json;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Concrete <see cref="IFrequencyStore"/> that reads and writes
/// <c>frequencies.json</c> using an atomic write-to-temp-then-rename pattern
/// (FR-042). Mirrors the pattern used by <c>JsonConfigStore</c>.
/// </summary>
public sealed class FrequencyStore : IFrequencyStore
{
    private readonly string                        _path;
    private readonly ILogger<FrequencyStore>?      _logger;
    private readonly SemaphoreSlim                 _saveLock = new(1, 1);
    private volatile IReadOnlyList<FrequencyEntry> _entries;

    /// <param name="path">Resolved path to <c>frequencies.json</c>.</param>
    /// <param name="logger">Optional logger for diagnostics.</param>
    public FrequencyStore(string path, ILogger<FrequencyStore>? logger = null)
    {
        _path    = path;
        _logger  = logger;
        _entries = FrequencyDefaults.Entries; // safe default before LoadAsync
    }

    // ── IFrequencyStore ───────────────────────────────────────────────────────

    /// <inheritdoc/>
    public IReadOnlyList<FrequencyEntry> Entries => _entries;

    /// <inheritdoc/>
    public async Task SaveAsync(
        IReadOnlyList<FrequencyEntry> entries,
        CancellationToken             cancellationToken = default)
    {
        var dir = Path.GetDirectoryName(_path)
            ?? throw new InvalidOperationException(
                $"Cannot determine directory for '{_path}'.");

        Directory.CreateDirectory(dir);

        // FR-042: entries are always persisted in ascending FrequencyMHz order so
        // that the dropdown and the Settings table present a consistent, sorted list
        // regardless of the order in which rows were added by the operator.
        var sorted = entries.OrderBy(e => e.FrequencyMHz).ToList();
        var dto = new FrequenciesFile { Entries = sorted };

        // Write to a temp file in the same directory, then rename atomically.
        // The semaphore serialises concurrent callers so that two simultaneous
        // saves do not race on the final File.Move to the shared destination path.
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
                    dto,
                    FrequencyJsonContext.Default.FrequenciesFile,
                    cancellationToken);
            }

            File.Move(tmp, _path, overwrite: true);
            _entries = sorted;
            _logger?.LogInformation("Frequencies saved to '{Path}'.", _path);
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
    /// Loads <c>frequencies.json</c> from the configured path.
    /// <list type="bullet">
    ///   <item>Absent file → writes the default list and uses it.</item>
    ///   <item>Malformed file → logs Error, uses compiled-in defaults in memory
    ///         (<em>does not</em> overwrite the file).</item>
    ///   <item>Valid file → loads and uses it.</item>
    /// </list>
    /// </summary>
    public async Task LoadAsync(CancellationToken cancellationToken = default)
    {
        if (!File.Exists(_path))
        {
            _logger?.LogInformation(
                "frequencies.json not found at '{Path}' — writing default list.", _path);
            await SaveAsync(FrequencyDefaults.Entries, cancellationToken);
            return;
        }

        try
        {
            var json = await File.ReadAllTextAsync(_path, cancellationToken);
            var dto  = JsonSerializer.Deserialize(
                json,
                FrequencyJsonContext.Default.FrequenciesFile);

            if (dto is null)
            {
                _logger?.LogError(
                    "frequencies.json at '{Path}' deserialised as null — using compiled-in defaults " +
                    "(file NOT overwritten).", _path);
                _entries = FrequencyDefaults.Entries;
                return;
            }

            // Sort in memory so even a pre-existing file written without this
            // invariant is presented in ascending FrequencyMHz order.
            _entries = dto.Entries.OrderBy(e => e.FrequencyMHz).ToList();
            _logger?.LogInformation(
                "Loaded {Count} frequenc{Ies} from '{Path}'.",
                _entries.Count,
                _entries.Count == 1 ? "y" : "ies",
                _path);
        }
        catch (JsonException ex)
        {
            _logger?.LogError(ex,
                "frequencies.json at '{Path}' is malformed — using compiled-in defaults " +
                "(file NOT overwritten).", _path);
            _entries = FrequencyDefaults.Entries;
        }
    }
}
