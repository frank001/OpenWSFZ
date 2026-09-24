using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Web;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Orchestrates capture-device re-resolution across every automatic capture-start path
/// (capture-device-reresolution #187, design.md Decisions 1, 3, 4) — the one place startup
/// auto-start, the <c>CaptureFailed</c> retry, and the watchdog restart all converge: re-resolve
/// the configured device against a fresh enumeration, act per design D1's outcome table, and —
/// for a <c>NotFound</c>/<c>Ambiguous</c> outcome, where nothing was started and so no
/// <c>CaptureFailed</c> event will ever fire to bring this loop back — self-schedule its own next
/// attempt.
///
/// <para>
/// Extracted out of <c>Program.cs</c>'s top-level statements specifically so this — the
/// highest-risk logic in this change, the exact two landmines the dev-task's handoff calls out by
/// name (no double restart per adoption; no deadlock under <c>restartSemaphore</c>) — is directly
/// unit-testable with fake collaborators, rather than reachable only through the daemon's real
/// top-level wiring.
/// </para>
///
/// <para>
/// Deliberately never called for <c>POST /api/v1/config</c>'s device-change or
/// <c>DecodingEnabled</c>-transition branches: an ID/setting the operator has just set is never
/// re-resolved (design's explicit non-goal).
/// </para>
///
/// <para>
/// <strong>No deadlock, by construction.</strong> This class never itself holds a lock while
/// calling <c>startCaptureAsync</c> or <see cref="IConfigStore.SaveAsync"/> — resolution always
/// happens <em>before</em> the caller's own restart-serialising semaphore is (re-)entered, never
/// from inside it. <c>startCaptureAsync</c> is free to acquire whatever serialisation the caller
/// needs (in production, <c>Program.cs</c>'s <c>RestartPipelineAsync</c>, which acquires
/// <c>restartSemaphore</c>) without this class ever holding it first.
/// </para>
///
/// <para>
/// <strong>No double restart, by construction.</strong> On <c>Adopt</c>, this class only calls
/// <see cref="IConfigStore.SaveAsync"/> — it never also calls <c>startCaptureAsync</c> for that
/// same adoption. In production, <c>IConfigStore.SaveAsync</c> firing <c>OnSaved</c>'s existing
/// device-change branch (unconditional whenever <c>newDevice != runningDevice</c>, exactly what an
/// adoption produces) is the one and only start that results.
/// </para>
/// </summary>
public sealed class CaptureAutoStartCoordinator
{
    private readonly IConfigStore                             _configStore;
    private readonly IAudioDeviceProvider                     _deviceProvider;
    private readonly CaptureRecoveryState                     _recoveryState;
    private readonly Func<bool>                                _isCapturing;
    private readonly Func<string, CancellationToken, Task>    _startCaptureAsync;
    private readonly ILogger                                  _logger;
    private readonly Func<TimeSpan, CancellationToken, Task>  _delayAsync;

    /// <param name="configStore">Read for the configured device; written on <c>Adopt</c>.</param>
    /// <param name="deviceProvider">Enumerated once per automatic attempt (design D1).</param>
    /// <param name="recoveryState">Failure/attempt counters this coordinator updates.</param>
    /// <param name="isCapturing">
    /// Returns whether a capture session is currently running — the pre-existing L-14 (DIAG)
    /// restart-guard check, mirrored here: an attempt that arrives after another path already
    /// recovered is a no-op.
    /// </param>
    /// <param name="startCaptureAsync">
    /// Starts (or restarts) capture on the given device ID. In production,
    /// <c>(id, ct) =&gt; RestartPipelineAsync(id, stopCaptureManager: true)</c> — the existing,
    /// unmodified, <c>restartSemaphore</c>-serialised entry point. Never called for an
    /// <c>Adopt</c> outcome (see the no-double-restart note above).
    /// </param>
    /// <param name="logger">Logger for the three new Warning lines (design D6).</param>
    /// <param name="delayAsync">
    /// Test seam: replaces the real backoff wait. Defaults to
    /// <c>(delay, ct) =&gt; Task.Delay(delay, ct)</c>. The exact schedule itself is
    /// <see cref="CaptureBackoffSchedule.DelayFor"/>'s own concern (pure, separately
    /// table-tested, gate G10 has nothing to flag there) — this seam exists only so a test can
    /// exercise the full self-rescheduling retry loop (a <c>NotFound</c>/<c>Ambiguous</c> outcome
    /// recursing until it resolves) without actually waiting out real 5-60 s delays.
    /// </param>
    public CaptureAutoStartCoordinator(
        IConfigStore                             configStore,
        IAudioDeviceProvider                     deviceProvider,
        CaptureRecoveryState                     recoveryState,
        Func<bool>                                isCapturing,
        Func<string, CancellationToken, Task>    startCaptureAsync,
        ILogger                                  logger,
        Func<TimeSpan, CancellationToken, Task>? delayAsync = null)
    {
        _configStore       = configStore;
        _deviceProvider    = deviceProvider;
        _recoveryState     = recoveryState;
        _isCapturing       = isCapturing;
        _startCaptureAsync = startCaptureAsync;
        _logger            = logger;
        _delayAsync        = delayAsync ?? ((delay, ct) => Task.Delay(delay, ct));
    }

    /// <summary>
    /// Runs one automatic capture-start attempt, or — for a <c>NotFound</c>/<c>Ambiguous</c>
    /// outcome — self-schedules the next one after the computed backoff delay (design D4).
    /// </summary>
    /// <param name="applyBackoffDelay">
    /// <see langword="false"/> only for the very first startup attempt and for a caller that has
    /// already applied its own delay — design D4: "the first startup attempt SHALL NOT be
    /// delayed." <see langword="true"/> for every other automatic attempt (a <c>CaptureFailed</c>
    /// retry, a watchdog restart, or this method's own self-scheduled retry).
    /// </param>
    public async Task RunAsync(bool applyBackoffDelay, CancellationToken ct = default)
    {
        if (applyBackoffDelay)
        {
            var delay = CaptureBackoffSchedule.DelayFor(_recoveryState.ConsecutiveCaptureFailures);
            await _delayAsync(delay, ct).ConfigureAwait(false);
        }

        // Guards mirrored from the pre-existing L-14 (DIAG) restart-guard pattern: the operator
        // may have disabled decoding, or another path may already have recovered, while this
        // attempt was waiting out its backoff delay.
        if (!_configStore.Current.DecodingEnabled) return;
        if (_isCapturing()) return;

        var configuredId   = _configStore.Current.AudioDeviceId;
        var configuredName = _configStore.Current.AudioDeviceFriendlyName;
        if (configuredId is null && configuredName is null) return; // nothing configured at all

        IReadOnlyList<AudioDeviceInfo> devices;
        try
        {
            devices = await _deviceProvider.GetDevicesAsync(ct).ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            // Enumeration itself failing is not a resolver outcome (Resolve expects an
            // already-enumerated list) — treat it the same as an empty enumeration:
            // CannotResolve, attempt the configured ID unchanged (today's behaviour when nothing
            // better is known).
            _logger.LogWarning(ex,
                "Automatic capture-device enumeration failed — attempting the configured device unchanged.");
            devices = [];
        }

        var resolution = CaptureDeviceResolver.Resolve(configuredId, configuredName, devices);

        switch (resolution.Kind)
        {
            case CaptureDeviceResolutionKind.UseConfigured:
            case CaptureDeviceResolutionKind.CannotResolve:
                if (configuredId is null) return;
                await _startCaptureAsync(configuredId, ct).ConfigureAwait(false);
                break;

            case CaptureDeviceResolutionKind.Adopt:
                _logger.LogWarning(
                    "Capture device re-resolved: '{OldId}' -> '{NewId}' (friendly name '{Name}' unchanged).",
                    configuredId, resolution.NewId, configuredName);
                // HK-035 full-replace: build from a fresh read, immediately before the save.
                await _configStore.SaveAsync(
                    _configStore.Current with { AudioDeviceId = resolution.NewId }, ct).ConfigureAwait(false);
                break;

            case CaptureDeviceResolutionKind.NotFound:
            case CaptureDeviceResolutionKind.Ambiguous:
                var message = resolution.Kind == CaptureDeviceResolutionKind.NotFound
                    ? $"No available capture device named '{configuredName}' was found (0 matches)."
                    : $"Capture device name '{configuredName}' is ambiguous: {resolution.MatchCount} available matches.";
                _recoveryState.RecordFailedAttempt(message, deviceUnavailable: true);
                _logger.LogWarning("Capture device unavailable — {Message}", message);
                _ = Task.Run(() => RunAsync(applyBackoffDelay: true, ct), CancellationToken.None);
                break;
        }
    }
}
