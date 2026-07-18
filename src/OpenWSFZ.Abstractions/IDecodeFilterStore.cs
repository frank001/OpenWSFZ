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

    /// <summary>
    /// Called once per newly-arrived <see cref="DecodeResult"/> (<c>fix-decode-filter-new-value-admission</c>,
    /// design.md Decision 1). For each of the decode's resolved attribute values (DXCC entity,
    /// Continent, CQ Zone, ITU Zone) not yet observed this session: if the corresponding axis is
    /// currently narrowed (non-<see langword="null"/> AND non-empty allow-list), admits the value
    /// into that axis's allow-list so it passes by default, exactly as if the axis were untouched.
    /// Always records the value as "seen" regardless of admission, for future popup candidate
    /// population. An axis that is <see langword="null"/> (unrestricted) or explicitly empty
    /// (<c>[]</c> — every value deselected) is never admitted into.
    /// </summary>
    /// <returns>
    /// The updated <see cref="DecodeFilterState"/> if any axis actually changed, or
    /// <see langword="null"/> if nothing needed admitting (no state change, no broadcast
    /// required).
    /// </returns>
    DecodeFilterState? AdmitNewValues(DecodeResult decode);
}
