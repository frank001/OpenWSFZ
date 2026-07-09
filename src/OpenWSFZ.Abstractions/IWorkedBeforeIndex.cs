namespace OpenWSFZ.Abstractions;

/// <summary>
/// In-process, in-memory index of every distinct callsign (and its resolved DXCC entity /
/// continent) ever logged to <c>ADIF.log</c> — the <c>qso-confirmation</c> capability's
/// "worked before" advisory lookup, mirroring <see cref="ICallsignRegionStore"/>'s
/// load-once-then-serve-from-memory pattern.
///
/// <para>
/// Built once at daemon startup via <see cref="LoadAsync"/>; kept live for the running session
/// by <see cref="Register"/>, called from <c>AdifLogWriter</c>'s successful-write path so a QSO
/// logged mid-session is reflected on the very next decode of that station without a restart.
/// </para>
///
/// <para>
/// A missing or unreadable <c>ADIF.log</c>, or any resolution failure, degrades to an empty
/// index / <see cref="WorkedBeforeInfo.None"/> — never a startup failure and never withholds a
/// decode.
/// </para>
/// </summary>
public interface IWorkedBeforeIndex
{
    /// <summary>
    /// Loads (or reloads) the index from the resolved <c>ADIF.log</c> path. A missing file
    /// resolves to an empty index, not an error.
    /// </summary>
    Task LoadAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Registers a single newly-logged callsign (and its resolved DXCC entity/continent/CQ-zone/
    /// ITU-zone, subject to the Unknown/synthetic exclusion — design.md Decision 4) into the live
    /// index, along with the band it was worked on, without requiring a reload of
    /// <c>ADIF.log</c>. Called only from a QSO write's success path — a failed ADIF write SHALL
    /// NOT register the callsign.
    /// </summary>
    /// <param name="callsign">The just-logged partner callsign.</param>
    /// <param name="band">
    /// The band the QSO was worked on (already computed by <c>AdifLogWriter</c> for the record's
    /// own <c>BAND</c> tag), or <c>null</c> when the band could not be derived — the callsign
    /// still contributes to the "worked at all" fact but not to any specific band
    /// (<c>qso-confirmation-band-awareness</c> design.md Decision 5).
    /// </param>
    void Register(string callsign, string? band);

    /// <summary>
    /// Resolves worked-before state for <paramref name="callsignToken"/> — the five independent
    /// tri-state dimensions described by <see cref="WorkedBeforeInfo"/>.
    /// </summary>
    /// <param name="callsignToken">The decoded callsign-position token to resolve.</param>
    /// <param name="currentBand">
    /// The session's current active band (resolved via the live-CAT-aware three-tier frequency
    /// rule, converted to a band name), or <c>null</c> when it cannot be resolved — every
    /// dimension that would otherwise resolve <see cref="WorkedBeforeState.ThisBand"/> instead
    /// resolves <see cref="WorkedBeforeState.DifferentBand"/> (if worked at all).
    /// </param>
    WorkedBeforeInfo Resolve(string callsignToken, string? currentBand);
}
