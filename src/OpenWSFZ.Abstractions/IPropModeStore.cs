namespace OpenWSFZ.Abstractions;

/// <summary>
/// Abstraction for the protocol-aware propagation mode list store (qso-log-dialog).
/// Mirrors the <see cref="IFrequencyStore"/> pattern.
/// </summary>
public interface IPropModeStore
{
    /// <summary>The current list of propagation mode entries.</summary>
    IReadOnlyList<PropModeEntry> Entries { get; }

    /// <summary>
    /// Replaces the stored list atomically and persists it to <c>prop-modes.json</c>.
    /// </summary>
    Task SaveAsync(IEnumerable<PropModeEntry> entries, CancellationToken cancellationToken = default);
}
