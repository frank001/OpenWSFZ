using System.Text.Json;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Config;

/// <summary>
/// Loads configuration from a JSON file at construction time (creating the
/// file with defaults if absent) and writes it atomically via temp-file-then-rename.
/// </summary>
public sealed class JsonConfigStore : IConfigStore
{
    private readonly string                   _path;
    private readonly ILogger<JsonConfigStore>? _logger;
    private volatile AppConfig                _current;

    // Serializes SaveAsync so concurrent callers (e.g. WebApp.cs's explicit /tx/abort save
    // racing SafeAbortToIdleAsync's own save, or CatPollingService's independent polling
    // save) queue instead of both calling File.Move onto the same destination path at once.
    // Windows transiently denies a second File.Move targeting a path that another
    // File.Move/replace onto that same path is mid-flight on, throwing
    // UnauthorizedAccessException — see dev-tasks/2026-07-10-config-store-concurrent-save-race.md.
    private readonly SemaphoreSlim _saveLock = new(1, 1);

    /// <param name="path">Resolved config file path (from <see cref="ConfigPathResolver"/>).</param>
    /// <param name="logger">Optional logger.  When <c>null</c> the store operates silently.</param>
    public JsonConfigStore(string path, ILogger<JsonConfigStore>? logger = null)
    {
        _path    = path;
        _logger  = logger;
        _current = Load(path);
        // Note: Load() runs before the logger exists when called at bootstrap before
        // the log level is known.  Bootstrap warnings fall back to Console.Error.
    }

    /// <inheritdoc/>
    public AppConfig Current => _current;

    /// <inheritdoc/>
    public event Action<AppConfig>? OnSaved;

    /// <inheritdoc/>
    public async Task SaveAsync(AppConfig config, CancellationToken ct = default)
    {
        var dir = Path.GetDirectoryName(_path)
            ?? throw new InvalidOperationException($"Cannot determine directory for '{_path}'.");

        Directory.CreateDirectory(dir);

        // Serialize the write-then-rename critical section across concurrent callers.
        // See _saveLock's declaration for why this is necessary.
        await _saveLock.WaitAsync(ct);
        try
        {
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
                _logger?.LogInformation("Configuration saved to '{Path}'.", _path);
                OnSaved?.Invoke(config);
            }
            catch
            {
                // Clean up the temp file on failure; re-throw so the caller knows.
                try { File.Delete(tmp); } catch { /* best-effort */ }
                throw;
            }
        }
        finally
        {
            _saveLock.Release();
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
            var json   = File.ReadAllText(path);
            var config = JsonSerializer.Deserialize(json, ConfigJsonContext.Default.AppConfig)
                ?? new AppConfig();

            // Migrate legacy audioDeviceName → audioDeviceId (p7 field rename).
            if (config.AudioDeviceId is null)
            {
                using var doc = JsonDocument.Parse(json);
                if (doc.RootElement.TryGetProperty("audioDeviceName", out var legacy) &&
                    legacy.ValueKind == JsonValueKind.String)
                {
                    config = config with { AudioDeviceId = legacy.GetString() };
                }
            }

            // Guard against STJ source-generation overriding the property initialiser
            // with null when the "logging" key is absent from older config files.
            if (config.Logging is null)
                config = config with { Logging = new LoggingConfig() };

            // Same guard for the newer "decodeLog" key (absent in config files created
            // before p9; STJ source-gen sets the property to null instead of new()).
            if (config.DecodeLog is null)
                config = config with { DecodeLog = new DecodeLogConfig() };

            // "remoteAccess" key is absent in config files written before the lan-remote-access
            // phase.  STJ source-gen may set the non-nullable init property to null rather than
            // using the property initialiser (= new()) when the key is missing from JSON — same
            // behaviour as "logging" and "decodeLog" above.  Apply the same null guard.
            if (config.RemoteAccess is null)
                config = config with { RemoteAccess = new RemoteAccessConfig() };

            // "decodeNoiseSuppression" key is absent in config files written before the
            // decode-noise-suppression phase. Same STJ source-gen null-vs-initialiser guard as
            // "logging"/"decodeLog"/"remoteAccess" above.
            if (config.DecodeNoiseSuppression is null)
                config = config with { DecodeNoiseSuppression = new DecodeNoiseSuppressionConfig() };

            // "externalReporting" key is absent in config files written before the
            // gridtracker-udp-reporting change. Same STJ source-gen null-vs-initialiser guard as
            // "logging"/"decodeLog"/"remoteAccess"/"decodeNoiseSuppression" above.
            if (config.ExternalReporting is null)
                config = config with { ExternalReporting = new ExternalReportingConfig() };

            // "cat" key is intentionally nullable: absent in config files written before p16.
            // Null is the correct default (CAT disabled); no guard needed — consumers use
            // (config.Cat ?? new CatConfig()) to get a non-null value.

            // "tx" key is intentionally nullable: absent in config files written before
            // ft8-qso-answerer-v1.  Null is the correct default (TX subsystem uses defaults);
            // consumers use (config.Tx ?? new TxConfig()).  When the key is present we clamp
            // out-of-range values and warn the operator.
            if (config.Tx is { } tx)
            {
                bool clamped = false;
                if (tx.RetryCount < 0)
                {
                    Console.Error.WriteLine(
                        $"[OpenWSFZ] WARNING: tx.retryCount = {tx.RetryCount} is invalid (minimum 0); clamped to 0.");
                    tx      = tx with { RetryCount = 0 };
                    clamped = true;
                }
                if (tx.RetryCount > 200)
                {
                    Console.Error.WriteLine(
                        $"[OpenWSFZ] WARNING: tx.retryCount = {tx.RetryCount} exceeds maximum (200); clamped to 200.");
                    tx      = tx with { RetryCount = 200 };
                    clamped = true;
                }
                if (tx.WatchdogMinutes < 1)
                {
                    Console.Error.WriteLine(
                        $"[OpenWSFZ] WARNING: tx.watchdogMinutes = {tx.WatchdogMinutes} is below minimum (1); clamped to 1.");
                    tx      = tx with { WatchdogMinutes = 1 };
                    clamped = true;
                }
                if (tx.WatchdogMinutes > 60)
                {
                    Console.Error.WriteLine(
                        $"[OpenWSFZ] WARNING: tx.watchdogMinutes = {tx.WatchdogMinutes} exceeds maximum (60); clamped to 60.");
                    tx      = tx with { WatchdogMinutes = 60 };
                    clamped = true;
                }
                if (clamped)
                    config = config with { Tx = tx };
            }

            return config;
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

        // Include cat, tx, remoteAccess, and decoder sections with explicit defaults so the
        // operator can see all available settings without having to look up the documentation
        // (FR-031, FR-046, lan-remote-access, decoder-settings-page).
        var json = JsonSerializer.Serialize(
            new AppConfig() with
            {
                Cat               = new CatConfig(),
                Tx                = new TxConfig(),
                RemoteAccess      = new RemoteAccessConfig(),
                Decoder           = new DecoderConfig(),
                ExternalReporting = new ExternalReportingConfig(),
            },
            ConfigJsonContext.Default.AppConfig);

        File.WriteAllText(path, json);
    }
}
