using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Resolves the in-memory-only <see cref="LoggingConfig"/> override for a background worker
/// (daemon-background-mode, design.md Decision 4): file logging is forced on when the process
/// is a background worker and the persisted configuration has <c>FileEnabled = false</c> —
/// a background instance must never be allowed to run invisibly with no console and no file
/// sink. <see cref="LoggingConfig"/> is an immutable record, so the returned
/// <see cref="Result.EffectiveConfig"/> is always a distinct in-memory value; the
/// <paramref name="persistedConfig"/> passed in (and therefore, transitively, whatever
/// <c>config.json</c> was loaded from) is never touched.
/// </summary>
internal static class BackgroundLoggingOverride
{
    /// <param name="EffectiveConfig">
    /// The <see cref="LoggingConfig"/> to actually pass to <c>LoggingPipeline.Apply</c>.
    /// </param>
    /// <param name="ForcedFileLoggingOn">
    /// <see langword="true"/> when <see cref="EffectiveConfig"/> differs from
    /// <paramref name="persistedConfig"/>) — i.e. the override actually took effect and a
    /// one-time Warning-level notice should be logged naming the resolved log file path.
    /// </param>
    internal readonly record struct Result(LoggingConfig EffectiveConfig, bool ForcedFileLoggingOn);

    public static Result Resolve(LoggingConfig persistedConfig, bool isBackgroundWorker)
    {
        if (isBackgroundWorker && !persistedConfig.FileEnabled)
            return new Result(persistedConfig with { FileEnabled = true }, ForcedFileLoggingOn: true);

        return new Result(persistedConfig, ForcedFileLoggingOn: false);
    }
}
