using FluentAssertions;
using OpenWSFZ.Abstractions;
using Xunit;

namespace OpenWSFZ.Daemon.Tests;

/// <summary>
/// Unit tests for <see cref="BackgroundLoggingOverride.Resolve"/> (daemon-background-mode,
/// task 7.3) — covers the "background-worker startup with logging.fileEnabled: false in the
/// persisted config still produces a log file, and the persisted config.json itself remains
/// unchanged" requirement at the level this logic is actually implemented: a pure function
/// from the persisted <see cref="LoggingConfig"/> to the effective in-memory one
/// <c>Program.cs</c> passes to <c>LoggingPipeline.Apply</c>. Because <see cref="LoggingConfig"/>
/// is an immutable record, proving the persisted value is never mutated reduces to proving the
/// input reference/value is untouched and a distinct value is returned — which these tests
/// assert directly, rather than needing a real config.json round-trip.
/// </summary>
[Trait("Category", "Unit")]
public sealed class BackgroundLoggingOverrideTests
{
    [Fact(DisplayName =
        "FR-059: daemon-background-mode 7.3: background worker + persisted FileEnabled=false forces it on in the effective config")]
    public void Resolve_BackgroundWorkerWithFileDisabled_ForcesFileEnabledOn()
    {
        var persisted = new LoggingConfig { FileEnabled = false };

        var result = BackgroundLoggingOverride.Resolve(persisted, isBackgroundWorker: true);

        result.EffectiveConfig.FileEnabled.Should().BeTrue(
            "a background worker must guarantee file logging regardless of the persisted value");
        result.ForcedFileLoggingOn.Should().BeTrue();
    }

    [Fact(DisplayName =
        "daemon-background-mode 7.3: the persisted config instance is never mutated by the override")]
    public void Resolve_BackgroundWorkerWithFileDisabled_PersistedConfigUnchanged()
    {
        var persisted = new LoggingConfig { FileEnabled = false, Directory = "/tmp/logs" };

        var result = BackgroundLoggingOverride.Resolve(persisted, isBackgroundWorker: true);

        persisted.FileEnabled.Should().BeFalse(
            "the original persisted record must remain exactly as loaded from config.json — " +
            "only the returned EffectiveConfig reflects the in-memory override");
        result.EffectiveConfig.Should().NotBeSameAs(persisted,
            "the override must return a distinct value, never the same instance mutated in place");
        result.EffectiveConfig.Directory.Should().Be("/tmp/logs",
            "every other field must be carried over unchanged — only FileEnabled is overridden");
    }

    [Fact(DisplayName =
        "daemon-background-mode 7.3: background worker + persisted FileEnabled=true is a no-op (no forcing needed)")]
    public void Resolve_BackgroundWorkerWithFileAlreadyEnabled_NoOverrideNeeded()
    {
        var persisted = new LoggingConfig { FileEnabled = true };

        var result = BackgroundLoggingOverride.Resolve(persisted, isBackgroundWorker: true);

        result.EffectiveConfig.Should().Be(persisted);
        result.ForcedFileLoggingOn.Should().BeFalse(
            "nothing was actually forced — file logging was already enabled, so no Warning " +
            "notice should be logged");
    }

    [Fact(DisplayName =
        "daemon-background-mode 7.3: non-background-worker startup never overrides FileEnabled, even when false")]
    public void Resolve_NotBackgroundWorker_NeverOverrides()
    {
        var persisted = new LoggingConfig { FileEnabled = false };

        var result = BackgroundLoggingOverride.Resolve(persisted, isBackgroundWorker: false);

        result.EffectiveConfig.Should().Be(persisted);
        result.ForcedFileLoggingOn.Should().BeFalse();
    }
}
