namespace OpenWSFZ.Abstractions;

/// <summary>
/// Owns the configuration file lifecycle: load on startup, write on Save.
/// Reads are synchronous (called once before the host starts);
/// writes are async (triggered from HTTP endpoints).
/// Implemented by <c>OpenWSFZ.Config.JsonConfigStore</c>.
/// </summary>
public interface IConfigStore
{
    /// <summary>The current in-memory configuration.</summary>
    AppConfig Current { get; }

    /// <summary>
    /// Raised on the calling thread immediately after a successful <see cref="SaveAsync"/>.
    /// The argument is the newly-saved configuration.
    /// </summary>
    event Action<AppConfig>? OnSaved;

    /// <summary>
    /// Persists <paramref name="config"/> to disk atomically and updates
    /// <see cref="Current"/> to reflect the new values.
    /// </summary>
    Task SaveAsync(AppConfig config, CancellationToken ct = default);
}
