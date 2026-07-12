using Microsoft.Extensions.Logging;

namespace OpenWSFZ.Daemon;

/// <summary>Identifies which <c>IPttController</c> implementation to register (FR-056).</summary>
internal enum PttControllerKind
{
    AudioVox,
    CatCommand,
    SerialRtsDtr,
}

/// <summary>
/// Pure mapping from <c>AppConfig.Ptt.Method</c> to a <see cref="PttControllerKind"/>
/// (FR-056, design.md Decision 6), extracted from <c>Program.cs</c>'s DI wiring so the
/// selection logic — including the unrecognised-value fallback and its Warning log — is
/// directly unit-testable (task 12.9) without spinning up the whole daemon host.
/// </summary>
internal static class PttControllerSelector
{
    /// <summary>
    /// Resolves <paramref name="method"/> to a <see cref="PttControllerKind"/>.
    /// Recognised values: <c>"AudioVox"</c>, <c>"CatCommand"</c>, <c>"SerialRtsDtr"</c>.
    /// Any other value logs a Warning naming the invalid value (matching the existing
    /// <c>CatConfig.RigModel</c> unknown-value handling, FR-034) and falls back to
    /// <see cref="PttControllerKind.AudioVox"/>.
    /// </summary>
    public static PttControllerKind Resolve(string method, ILogger logger)
    {
        switch (method)
        {
            case "CatCommand":
                return PttControllerKind.CatCommand;
            case "SerialRtsDtr":
                return PttControllerKind.SerialRtsDtr;
            case "AudioVox":
                return PttControllerKind.AudioVox;
            default:
                logger.LogWarning(
                    "ptt.method '{Method}' is not recognised (expected AudioVox, CatCommand, " +
                    "or SerialRtsDtr) — falling back to AudioVox.", method);
                return PttControllerKind.AudioVox;
        }
    }
}
