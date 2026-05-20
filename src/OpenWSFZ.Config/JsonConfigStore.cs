using System.Text.Json;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Config;

/// <summary>
/// Loads configuration from a JSON file at construction time (creating the
/// file with defaults if absent) and writes it atomically via temp-file-then-rename.
/// </summary>
public sealed class JsonConfigStore : IConfigStore
{
    private readonly string _path;
    private volatile AppConfig _current;

    /// <param name="path">Resolved config file path (from <see cref="ConfigPathResolver"/>).</param>
    public JsonConfigStore(string path)
    {
        _path    = path;
        _current = Load(path);
    }

    /// <inheritdoc/>
    public AppConfig Current => _current;

    /// <inheritdoc/>
    public async Task SaveAsync(AppConfig config, CancellationToken ct = default)
    {
        var dir = Path.GetDirectoryName(_path)
            ?? throw new InvalidOperationException($"Cannot determine directory for '{_path}'.");

        Directory.CreateDirectory(dir);

        // Write to a temp file in the same directory, then rename atomically.
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
                    stream,
                    config,
                    ConfigJsonContext.Default.AppConfig,
                    ct);
            }

            File.Move(tmp, _path, overwrite: true);
            _current = config;
        }
        catch
        {
            // Clean up the temp file on failure; re-throw so the caller knows.
            try { File.Delete(tmp); } catch { /* best-effort */ }
            throw;
        }
    }

    // ── Helpers ──────────────────────────────────────────────────────────────

    private static AppConfig Load(string path)
    {
        if (!File.Exists(path))
        {
            CreateDefault(path);
            return new AppConfig();
        }

        try
        {
            var json = File.ReadAllText(path);
            return JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)
                ?? new AppConfig();
        }
        catch (Exception ex)
        {
            // Corrupt / unreadable config — return defaults and do not overwrite so the
            // operator can inspect and recover the file.  Log to stderr so the problem
            // is visible at startup without requiring a full logging stack.
            Console.Error.WriteLine(
                $"[OpenWSFZ] WARNING: config file '{path}' could not be read ({ex.GetType().Name}: {ex.Message}). " +
                "Using defaults — the file has NOT been overwritten.");
            return new AppConfig();
        }
    }

    private static void CreateDefault(string path)
    {
        var dir = Path.GetDirectoryName(path);
        if (!string.IsNullOrEmpty(dir))
            Directory.CreateDirectory(dir);

        var json = JsonSerializer.Serialize(
            new AppConfig(),
            ConfigJsonContext.Default.AppConfig);

        File.WriteAllText(path, json);
    }
}
