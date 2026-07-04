using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Test double for <see cref="ICallsignGrammarStore"/> returning a fixed, caller-supplied
/// <see cref="CallsignGrammarConfig"/> — no file I/O.
/// </summary>
internal sealed class FixedCallsignGrammarStore(CallsignGrammarConfig config) : ICallsignGrammarStore
{
    /// <summary>A store returning <see cref="CallsignGrammarConfig.BuiltInDefault"/> — the
    /// production defaults, used by D009/D011 regression-fence tests (task 2.5) so their
    /// call sites are explicit about which grammar is under test.</summary>
    public static readonly FixedCallsignGrammarStore Default = new(CallsignGrammarConfig.BuiltInDefault);

    public CallsignGrammarConfig Current { get; } = config;
}
