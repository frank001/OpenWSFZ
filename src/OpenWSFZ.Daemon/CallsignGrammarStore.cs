using System.Text.Json;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Concrete <see cref="ICallsignGrammarStore"/> that reads <c>callsign-grammar.json</c>,
/// following the <see cref="FrequencyStore"/> pattern: default-file-created-on-first-run,
/// malformed-file fallback to <see cref="CallsignGrammarConfig.BuiltInDefault"/> with a
/// logged Warning. There is no operator-facing editor for this file (unlike
/// <c>frequencies.json</c>), so no <c>SaveAsync</c> is exposed — only <see cref="LoadAsync"/>.
/// </summary>
public sealed class CallsignGrammarStore : ICallsignGrammarStore
{
    private readonly string                          _path;
    private readonly ILogger<CallsignGrammarStore>?  _logger;
    private volatile CallsignGrammarConfig           _current;

    /// <param name="path">Resolved path to <c>callsign-grammar.json</c>.</param>
    /// <param name="logger">Optional logger for diagnostics.</param>
    public CallsignGrammarStore(string path, ILogger<CallsignGrammarStore>? logger = null)
    {
        _path    = path;
        _logger  = logger;
        _current = CallsignGrammarConfig.BuiltInDefault; // safe default before LoadAsync
    }

    /// <inheritdoc/>
    public CallsignGrammarConfig Current => _current;

    // ── Startup ───────────────────────────────────────────────────────────────

    /// <summary>
    /// Loads <c>callsign-grammar.json</c> from the configured path.
    /// <list type="bullet">
    ///   <item>Absent file → writes the built-in default grammar and uses it.</item>
    ///   <item>Malformed file → logs Warning, uses <see cref="CallsignGrammarConfig.BuiltInDefault"/>
    ///         in memory (does not overwrite the file).</item>
    ///   <item>Valid file → loads and uses it.</item>
    /// </list>
    /// </summary>
    public async Task LoadAsync(CancellationToken cancellationToken = default)
    {
        if (!File.Exists(_path))
        {
            _logger?.LogInformation(
                "callsign-grammar.json not found at '{Path}' — writing built-in defaults.", _path);
            try
            {
                await WriteAsync(CallsignGrammarConfig.BuiltInDefault, cancellationToken);
            }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
            {
                _logger?.LogWarning(ex,
                    "Cannot write default callsign-grammar.json to '{Path}' — " +
                    "using built-in defaults in memory.", _path);
            }
            _current = CallsignGrammarConfig.BuiltInDefault;
            return;
        }

        try
        {
            var json = await File.ReadAllTextAsync(_path, cancellationToken);
            var dto  = JsonSerializer.Deserialize(json, CallsignJsonContext.Default.CallsignGrammarConfig);

            if (dto is null)
            {
                _logger?.LogWarning(
                    "callsign-grammar.json at '{Path}' deserialised as null — using built-in " +
                    "defaults (file NOT overwritten).", _path);
                _current = CallsignGrammarConfig.BuiltInDefault;
                return;
            }

            _current = dto;
            _logger?.LogInformation("Loaded callsign grammar configuration from '{Path}'.", _path);
        }
        catch (JsonException ex)
        {
            _logger?.LogWarning(ex,
                "callsign-grammar.json at '{Path}' is malformed — using built-in defaults " +
                "(file NOT overwritten).", _path);
            _current = CallsignGrammarConfig.BuiltInDefault;
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private async Task WriteAsync(CallsignGrammarConfig config, CancellationToken cancellationToken)
    {
        var dir = Path.GetDirectoryName(_path)
            ?? throw new InvalidOperationException($"Cannot determine directory for '{_path}'.");

        Directory.CreateDirectory(dir);

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
                    stream, config, CallsignJsonContext.Default.CallsignGrammarConfig, cancellationToken);
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
