namespace OpenWSFZ.Abstractions;

/// <summary>
/// In-process store for the operator's working-frequency list (FR-042).
/// Loaded at startup from <c>frequencies.json</c>; persisted atomically on
/// <see cref="SaveAsync"/>. Mirrors the <see cref="IConfigStore"/> pattern.
/// </summary>
public interface IFrequencyStore
{
    /// <summary>
    /// The current in-memory frequency list.
    /// Populated after startup initialisation and updated atomically by
    /// <see cref="SaveAsync"/>.
    /// </summary>
    IReadOnlyList<FrequencyEntry> Entries { get; }

    /// <summary>
    /// Replaces the in-memory list and persists the new list to
    /// <c>frequencies.json</c> atomically (write-to-temp-then-rename).
    /// <see cref="Entries"/> is updated only after a successful file write.
    /// </summary>
    Task SaveAsync(IReadOnlyList<FrequencyEntry> entries, CancellationToken cancellationToken = default);
}
