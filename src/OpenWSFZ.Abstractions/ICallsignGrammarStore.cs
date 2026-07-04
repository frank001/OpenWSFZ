namespace OpenWSFZ.Abstractions;

/// <summary>
/// In-process store for the callsign shape-grammar configuration
/// (<c>callsign-grammar.json</c>), replacing the length-only D9-R3
/// oversized-callsign guard. Loaded at startup; mirrors the
/// <see cref="IFrequencyStore"/> pattern (data-directory override path
/// resolution, default-file-created-on-first-run, malformed-file fallback to
/// compiled-in defaults with a logged warning).
/// </summary>
public interface ICallsignGrammarStore
{
    /// <summary>
    /// The current in-memory grammar configuration. Populated after startup
    /// initialisation; falls back to <see cref="CallsignGrammarConfig.BuiltInDefault"/>
    /// if the backing file is absent or malformed.
    /// </summary>
    CallsignGrammarConfig Current { get; }
}
