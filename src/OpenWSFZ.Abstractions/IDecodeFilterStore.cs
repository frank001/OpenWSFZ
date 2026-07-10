namespace OpenWSFZ.Abstractions;

/// <summary>
/// Holds the current daemon-owned <see cref="DecodeFilterState"/>
/// (<c>decode-panel-filtering</c> capability, design.md Decision 3). Explicitly NOT an
/// <see cref="IConfigStore"/>-style persistent store — no <c>SaveAsync</c>-to-disk, no JSON
/// file involvement. State is ephemeral and shared across all connected clients: it resets to
/// <see cref="DecodeFilterState.Unfiltered"/> on every daemon restart, and is not scoped per
/// browser tab or per connection.
/// </summary>
public interface IDecodeFilterStore
{
    /// <summary>The current filter state. Defaults to <see cref="DecodeFilterState.Unfiltered"/>.</summary>
    DecodeFilterState Current { get; }

    /// <summary>
    /// Replaces the current filter state (whole-object replace — matches
    /// <c>POST /api/v1/config</c>'s existing whole-object-replace convention).
    /// </summary>
    void Set(DecodeFilterState state);
}
