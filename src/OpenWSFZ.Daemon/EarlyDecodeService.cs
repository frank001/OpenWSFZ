using System.Diagnostics;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Web;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Everything <see cref="EarlyDecodeService"/> touches, as delegates, so it can be driven by a test or a replay harness
/// without the daemon host (the same pattern as <see cref="DecodePumpDependencies"/>).
/// </summary>
internal sealed record EarlyDecodeServiceDependencies(
    Func<double?>                                                                          CurrentDialFrequency,
    Func<double>                                                                           FallbackDialFrequency,
    Func<double, string?>                                                                  DeriveBand,
    Func<float[], DateTime, string?, CancellationToken, Task<IReadOnlyList<DecodeResult>>> DecodeEarly,
    Func<IReadOnlyList<DecodeResult>, IReadOnlyList<DecodeResult>>                         ApplyNoiseSuppression,
    Func<IReadOnlyList<EarlyRow>, Task>                                                    PublishEarlyToPanel,
    ILogger                                                                                Logger);

/// <summary>
/// decode-early-batch-panel (phase 4a, design.md D2, D6, D7): reads the framer's EARLY windows (and only those: it is not
/// a second consumer of the ordinary window channel), decodes each through the pass-0-only early entry and shows the rows
/// on the decode panel, marked, and nowhere else.
///
/// <para>
/// <b>Never in the way.</b> It takes the shared decode gate with <c>Wait(0)</c>: if any decode is running it SKIPS (counted,
/// never queued). <b>Dial-frequency rule.</b> A window whose dial-frequency snapshot differs from the live frequency is
/// skipped, exactly as the pump discards such a cycle. <b>Same visibility filter</b> as batch 1
/// (<see cref="DecodePumpDependencies.ApplyNoiseSuppression"/>). <b>Panel only:</b> no ALL.TXT, UDP, QSO channel, archive or
/// filter-admission call exists in this class.
/// </para>
/// </summary>
internal sealed class EarlyDecodeService
{
    private readonly EarlyDecodeCoordinator         _coordinator;
    private readonly EarlyDecodeServiceDependencies _d;

    public EarlyDecodeService(EarlyDecodeCoordinator coordinator, EarlyDecodeServiceDependencies dependencies)
    {
        _coordinator = coordinator;
        _d           = dependencies;
    }

    /// <summary>Runs until <paramref name="windows"/> completes or <paramref name="stoppingToken"/> is cancelled.</summary>
    public async Task RunAsync(
        IAsyncEnumerable<(float[] Pcm, DateTime CycleStart, double? DialFrequency)> windows,
        CancellationToken stoppingToken)
    {
        await foreach (var (pcm, cycleStart, windowDialFreq) in windows.WithCancellation(stoppingToken))
        {
            try
            {
                await HandleAsync(pcm, cycleStart, windowDialFreq, stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception ex)
            {
                // Never let an early-decode fault stop the loop, and never touch the ordinary pipeline.
                _d.Logger.LogError(ex, "Early decode error: {Message}", ex.Message);
            }
        }
    }

    /// <summary>One early window: the dial rule, the gate, the decode, the filter, the panel. Exposed for tests.</summary>
    internal async Task HandleAsync(float[] pcm, DateTime cycleStart, double? windowDialFreq, CancellationToken ct)
    {
        // R10: the same rule as the pump's. The panel must not show early rows labelled with a band the final decode then discards.
        if (windowDialFreq != _d.CurrentDialFrequency())
        {
            _coordinator.RecordSkip(cycleStart, "dialFrequencyChanged");
            return;
        }

        // R2: never in the way. Busy means skip, never queue.
        if (!_coordinator.Gate.Wait(0))
        {
            _coordinator.RecordSkip(cycleStart, "decoderBusy");
            return;
        }

        // The gate is held until the cycle's early batch has been RECORDED, not just until the decode returns: the final
        // decode of this same cycle may be waiting on the gate, and the moment it gets it, it reads the recorded batch
        // (for the R7 line's finalWaitMs and to resolve the early rows in its own frame). Releasing before recording would
        // let it run first and find nothing.
        try
        {
            IReadOnlyList<DecodeResult> results;
            var sw = Stopwatch.StartNew();
            try
            {
                var dialFreq    = windowDialFreq ?? _d.FallbackDialFrequency();
                var currentBand = _d.DeriveBand(dialFreq);
                results = await _d.DecodeEarly(pcm, cycleStart, currentBand, ct);
            }
            catch (OperationCanceledException) when (ct.IsCancellationRequested)
            {
                throw;
            }
            catch (Exception ex)
            {
                _d.Logger.LogWarning(ex, "Early decode of cycle {CycleStart:HH:mm:ss} failed: {Message}", cycleStart, ex.Message);
                _coordinator.RecordSkip(cycleStart, "error");
                return;
            }
            sw.Stop();

            // R11: the same visibility filter as batch 1. R3: AdmitNewValues is NOT run on early rows.
            var visible = _d.ApplyNoiseSuppression(results);
            var rows    = new List<EarlyRow>(visible.Count);
            foreach (var r in visible)
                rows.Add(new EarlyRow(_coordinator.NextEarlyId(), r));

            // Recorded BEFORE the panel frame leaves and before the gate is released, so the cycle's final batch can never miss it.
            _coordinator.RecordEarly(cycleStart, rows, sw.Elapsed.TotalMilliseconds);
            if (rows.Count > 0)
                _ = _d.PublishEarlyToPanel(rows);   // fire-and-forget, as the pump does for batch 1
        }
        finally
        {
            _coordinator.Gate.Release();
        }
    }
}
