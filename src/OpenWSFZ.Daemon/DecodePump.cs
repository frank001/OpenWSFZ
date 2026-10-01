using System.Threading.Channels;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Everything <see cref="DecodePump"/> touches, as delegates and channel writers, so the pump can be driven by a
/// test or a replay harness without the daemon host (sub-feas-speed-redesign two-stage publish, design.md D9).
/// <c>Program.cs</c> wires each one to the real service it used to call inline.
/// </summary>
internal sealed record DecodePumpDependencies(
    Func<double?>                                                      CurrentDialFrequency,
    Func<double>                                                       FallbackDialFrequency,
    Func<double, string?>                                              DeriveBand,
    Func<bool>                                                         SubtractionEnabled,
    Func<float[], DateTime, string?, CancellationToken, Task<IReadOnlyList<DecodeResult>>> DecodeSingleBatch,
    Func<float[], DateTime, string?, Func<IReadOnlyList<DecodeResult>, Task>, CancellationToken, Task<IReadOnlyList<DecodeResult>>> DecodeTwoStage,
    Func<IReadOnlyList<DecodeResult>, IReadOnlyList<DecodeResult>>    ApplyNoiseSuppression,
    Func<IReadOnlyList<DecodeResult>, Task>                            PublishToPanel,
    Func<DateTime, double, IReadOnlyList<DecodeResult>, Task>          AppendAllTxt,
    Action<float[], DateTime, DateTime, int, double>                   EnqueueArchive,
    Func<DecodeResult, DecodeFilterState?>                             AdmitNewValues,
    Action<DecodeFilterState>                                          PublishFilterState,
    ChannelWriter<DecodeBatch>                                         AnswererChannel,
    ChannelWriter<DecodeBatch>                                         CallerChannel,
    ChannelWriter<DecodeBatch>                                         ExternalReportingChannel,
    ILogger                                                            Logger);

/// <summary>
/// The decode pump: reads completed PCM windows, decodes each, and publishes the result to every consumer.
///
/// <para>
/// Extracted from <c>Program.cs</c> for two-stage publish so it is testable; with the residual-pass flag OFF the
/// behaviour is the inline loop's, statement for statement (one decode, one publish, in the same order).
/// </para>
///
/// <para><b>Two-stage publish (flag ON, design.md D9).</b> The residual pass used to run inside the decode call, so
/// every decode, pass-0 included, reached the operator only after the whole pass (about 20.5 s after the cycle
/// started, against the 17.36 s deadline to answer a station heard in that cycle). Now pass-0 is published as
/// <b>batch 1</b> through <see cref="PublishFirstAsync"/> as soon as pass 0 returns, and the residual pass's new
/// decodes follow as <b>batch 2</b> through <see cref="PublishSecondAsync"/>, or not at all if the pass is abandoned,
/// fails or finds nothing new. The pump stays serial: it does not read the next window until batch 2 has been
/// published or abandoned.</para>
///
/// <para><b>Who receives batch 2 (P-4/P-5/P-6).</b> The decode panel, ALL.TXT, decode-filter admission and external
/// reporting. NOT the QSO answerer or caller (the answerer keeps <c>_lastIdleDecodeBatch</c> on every idle batch and
/// reads it in <c>TryEngageExternal</c>: a residual-only batch would replace the pass-0 snapshot and an external reply
/// to a pass-0 station would then be ignored; both services also treat every batch as a cycle). Not the cycle-audio
/// archive either: it enqueues the window once, at batch 1, with the pass-0 count.</para>
/// </summary>
internal sealed class DecodePump
{
    private readonly DecodePumpDependencies _d;

    public DecodePump(DecodePumpDependencies dependencies) => _d = dependencies;

    /// <summary>
    /// Runs until <paramref name="windows"/> completes or <paramref name="stoppingToken"/> is cancelled. Serial: the
    /// next window is not read until the current one is fully handled (both batches, or batch 1 alone).
    /// </summary>
    public async Task RunAsync(
        IAsyncEnumerable<(float[] Pcm, DateTime CycleStart, double? DialFrequency)> windows,
        CancellationToken stoppingToken)
    {
        await foreach (var (pcmWindow, cycleStart, windowDialFreq) in windows.WithCancellation(stoppingToken))
        {
            // cycle-audio-archive: sampled as close to the window's actual close as possible
            // (design.md Decision 6 — "the true wall-clock instant the window closed"), before
            // any decode latency below is incurred.
            var windowClosedUtc = DateTime.UtcNow;
            try
            {
                // Snapshot the live frequency immediately before decoding.
                // If a band change occurred during the 15-second capture window, the audio
                // spans two bands and cannot be reliably labeled with either frequency.
                // Discard the cycle: a mislabeled decode is worse than no decode (FR-032,
                // defect: dial-freq-snapshot).
                var currentDialFreq = _d.CurrentDialFrequency();
                if (windowDialFreq != currentDialFreq)
                {
                    _d.Logger.LogInformation(
                        "Cycle {CycleStart:HH:mm:ss}: discarded — dial frequency changed " +
                        "from {Before} to {After} MHz during capture window.",
                        cycleStart,
                        windowDialFreq?.ToString("F3") ?? "unknown",
                        currentDialFreq?.ToString("F3") ?? "unknown");
                    continue;
                }

                // cycleStart is the UTC instant at which CycleFramer began accumulating
                // this window — the authoritative cycle timestamp (R3 / FR-028).
                // dialFreq falls back to the configured value when CAT is absent.
                var dialFreq = windowDialFreq ?? _d.FallbackDialFrequency();

                // qso-confirmation-band-awareness: resolve the session's current active band
                // alongside dialFreq, using the same already-trustworthy (D-013) value.
                var currentBand = _d.DeriveBand(dialFreq);

                // The flag is read ONCE per window. OFF: the ordinary single decode and one publish, exactly as
                // before two-stage publish existed (P-9): this branch does not touch the two-batch machinery.
                if (!_d.SubtractionEnabled())
                {
                    var results = await _d.DecodeSingleBatch(pcmWindow, cycleStart, currentBand, stoppingToken);
                    await PublishFirstAsync(results, pcmWindow, cycleStart, windowClosedUtc, dialFreq);
                }
                else
                {
                    var second = await _d.DecodeTwoStage(
                        pcmWindow, cycleStart, currentBand,
                        batch1 => PublishFirstAsync(batch1, pcmWindow, cycleStart, windowClosedUtc, dialFreq),
                        stoppingToken);

                    // Nothing is published for batch 2 unless the pass completed with a new decode (P-2).
                    if (second.Count > 0)
                        await PublishSecondAsync(second, cycleStart, dialFreq);
                }
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break; // clean shutdown
            }
            catch (Exception ex)
            {
                _d.Logger.LogError(ex, "Decode error: {Message}", ex.Message);
            }
        }
    }

    /// <summary>
    /// Publishes a cycle's single batch (flag OFF) or batch 1 (flag ON) to EVERY consumer, in the order the inline
    /// pump always used.
    /// </summary>
    internal async Task PublishFirstAsync(
        IReadOnlyList<DecodeResult> results, float[] pcmWindow, DateTime cycleStart, DateTime windowClosedUtc,
        double dialFreq)
    {
        // decode-noise-suppression: a deliberate, operator-opt-in exception to the
        // region-lookup capability's "a lookup miss ... SHALL still reach ALL.TXT and the
        // UI" invariant — see DecodeNoiseSuppressionFilter's doc comment. region-lookup's
        // own resolution logic above is untouched; only the decode-panel broadcast and the
        // QSO-controller batches below are gated. ALL.TXT (next line) always receives the
        // unfiltered `results`.
        var visibleResults = _d.ApplyNoiseSuppression(results);

        _ = _d.PublishToPanel(visibleResults); // fire-and-forget: do not await WebSocket delivery
        await _d.AppendAllTxt(cycleStart, dialFreq, results); // unfiltered — ALL.TXT unaffected

        // cycle-audio-archive: non-blocking enqueue; the archive's own dedicated writer
        // task performs all file I/O (design.md Decision 2 — the pump must never await
        // disk I/O). decodeCount is unfiltered `results.Count`, matching ALL.TXT above —
        // Decoded/NoDecodes mode selection reflects what the decoder actually produced,
        // not what decode-noise-suppression hides from the UI. Runs ONCE per cycle, here (P-6).
        _d.EnqueueArchive(pcmWindow, cycleStart, windowClosedUtc, results.Count, dialFreq);

        AdmitAndBroadcastFilterState(visibleResults);

        // Fan-out to both QSO controller channels (non-blocking; DropOldest when full).
        // QsoControllerRouter activates only one service at a time via IsActive flags;
        // the inactive service's HandleIdleAsync is a no-op, so the extra batches are cheap.
        var batch = new DecodeBatch(new DateTimeOffset(cycleStart, TimeSpan.Zero), visibleResults);
        _d.AnswererChannel.TryWrite(batch);
        _d.CallerChannel.TryWrite(batch);
        _d.ExternalReportingChannel.TryWrite(batch);
    }

    /// <summary>
    /// Publishes batch 2 of a flag-ON cycle: the panel (appended, never replacing), ALL.TXT (appended, same stamp),
    /// decode-filter admission and external reporting. Deliberately NOT the answerer, the caller or the archive
    /// (P-5, P-6; see the class remarks).
    /// </summary>
    internal async Task PublishSecondAsync(IReadOnlyList<DecodeResult> results, DateTime cycleStart, double dialFreq)
    {
        var visibleResults = _d.ApplyNoiseSuppression(results);

        _ = _d.PublishToPanel(visibleResults);
        await _d.AppendAllTxt(cycleStart, dialFreq, results);

        AdmitAndBroadcastFilterState(visibleResults);

        _d.ExternalReportingChannel.TryWrite(new DecodeBatch(new DateTimeOffset(cycleStart, TimeSpan.Zero), visibleResults));
    }

    /// <summary>
    /// fix-decode-filter-new-value-admission, design.md Decision 4: admit any previously-unseen attribute value on a
    /// narrowed-but-non-empty axis BEFORE the QSO-controller fan-out, so this same decode cycle's engagement decision
    /// sees the already-corrected filter state. Runs unconditionally (no WebSocketHub.HasClients gate). Coalesced to
    /// at most one broadcast per batch, not once per admitted value.
    /// </summary>
    private void AdmitAndBroadcastFilterState(IReadOnlyList<DecodeResult> visibleResults)
    {
        DecodeFilterState? admittedState = null;
        foreach (var r in visibleResults)
        {
            var updated = _d.AdmitNewValues(r);
            if (updated is not null)
                admittedState = updated;
        }
        if (admittedState is not null)
            _d.PublishFilterState(admittedState);
    }
}
