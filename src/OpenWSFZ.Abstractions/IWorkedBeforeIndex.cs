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
    /// Registers a single newly-logged callsign (and its resolved DXCC entity/continent,
    /// subject to the Unknown/synthetic exclusion — design.md Decision 4) into the live index,
    /// without requiring a reload of <c>ADIF.log</c>. Called only from a QSO write's success
    /// path — a failed ADIF write SHALL NOT register the callsign.
    /// </summary>
    void Register(string callsign);

    /// <summary>
    /// Resolves worked-before state for <paramref name="callsignToken"/> — the three
    /// independent booleans described by <see cref="WorkedBeforeInfo"/>.
    /// </summary>
    WorkedBeforeInfo Resolve(string callsignToken);
}
