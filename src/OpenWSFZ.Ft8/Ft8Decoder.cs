using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Interop;

namespace OpenWSFZ.Ft8;

/// <summary>
/// FT8 decoder implementing <see cref="IModeDecoder"/> via a P/Invoke binding to
/// <c>libft8.dll</c> (kgoba/ft8_lib v2.0, MIT licence).
///
/// <para>
/// The homegrown Bluestein/Costas/LDPC pipeline (p5–p11) achieved 0% recovery on
/// 42 real off-air WAVs.  This implementation delegates to the proven ft8_lib native
/// library, which implements the full WSJT-X decode pipeline including candidate
/// detection (up to 140 candidates) and soft-decision LDPC with 25 iterations.
/// </para>
///
/// <para>
/// Native shim version history (tracked via <c>FT8_SHIM_VERSION</c> / <c>ExpectedShimVersion</c>):
/// 20240001 — single-pass decode.
/// 20260001 — p15 iterative subtraction (spectrogram-domain, 2 passes).
/// 20260002 — R6 weak-signal post-correction removed (R&amp;R-001 linearity fix);
///            revert-pcm-sic: PCM-domain SIC reverted, two-pass spectrogram suppression restored.
/// 20260003 — fix-D001: PCM-domain SIC; K_MAX_PASSES = 3; carrier estimation + CP-FSK synthesis.
///            (Version skipped — was the reverted PCM-SIC; never shipped.)
/// 20260004 — fix-d001-revised: Option B soft SNR-scaled tile attenuation.
/// 20260005 — diag(D-003): ft8_get_last_noise_floor_db() TLS getter added.
/// 20260006 — fix(D-002): SNR bandwidth constant -26.0 → -26.5 dB (bias calibration).
/// </para>
///
/// <para>
/// The <see cref="IModeDecoder"/> contract is unchanged: callers pass a 15-second
/// 12 kHz mono float[] and receive a list of <see cref="DecodeResult"/> records.
/// Everything else — <see cref="CycleFramer"/>, <see cref="DecodeResult"/>, ALL.TXT
/// logging — is unaffected.
/// </para>
/// </summary>
public sealed class Ft8Decoder : IModeDecoder
{
    private const int   ExpectedSampleCount         = 180_000;  // 15 s × 12 000 Hz
    private const float SilenceRmsThreshold         = 1e-6f;    // all-zero codeword guard
    private const float PcmNormalisationTargetRms   = 0.20f;    // D-002 SNR-bias fix: bring PCM to a fixed RMS level before native decode

    private readonly IClock              _clock;
    private readonly ILogger<Ft8Decoder>? _logger;

    public Ft8Decoder(IClock clock, ILogger<Ft8Decoder>? logger = null)
    {
        _clock  = clock;
        _logger = logger;
    }

    // ── IModeDecoder — backward-compatible overload ───────────────────────────
    // Infers the cycle-start timestamp from the injected clock, aligned to the
    // nearest 15-second UTC boundary.  Susceptible to a wall-clock race if the
    // calling thread is delayed past a cycle boundary; prefer the cycleStart
    // overload (supplied by CycleFramer) in production code.
    /// <inheritdoc/>
    public Task<IReadOnlyList<DecodeResult>> DecodeAsync(float[] pcm, CancellationToken ct = default)
        => DecodeAsync(pcm, AlignToCycleStart(_clock.UtcNow), ct);

    // ── IModeDecoder — canonical overload (cycleStart from CycleFramer) ───────
    /// <inheritdoc/>
    public async Task<IReadOnlyList<DecodeResult>> DecodeAsync(
        float[]           pcm,
        DateTime          cycleStart,
        CancellationToken ct = default)
    {
        // ── R2: Pre-condition guard ──────────────────────────────────────────
        // Declared async so that this throw surfaces as a faulted Task rather than
        // propagating synchronously to callers expecting Task-based exception semantics.
        if (pcm.Length != ExpectedSampleCount)
            throw new ArgumentException(
                $"PCM buffer must be exactly {ExpectedSampleCount} samples (15 s × 12 000 Hz). Got {pcm.Length}.",
                nameof(pcm));

        ct.ThrowIfCancellationRequested();

        // ── Silence guard ────────────────────────────────────────────────────
        // Skip cycles where the signal is below the noise floor.  This also
        // prevents the all-zero codeword from being accepted as a valid message.
        float rms = ComputeRms(pcm);
        if (rms < SilenceRmsThreshold)
        {
            _logger?.LogInformation(
                "Cycle skipped — RMS {Rms:E3} is below silence guard (threshold {Threshold:E3}).",
                rms, SilenceRmsThreshold);
            return [];
        }

        // ── R3: Use caller-supplied cycle-start timestamp ────────────────────
        // cycleStart comes from CycleFramer, which records it when the window
        // begins accumulating — not when the decoder is eventually invoked.
        // This avoids the wall-clock race where scheduler delay causes
        // AlignToCycleStart to snap to the start of the *next* cycle.
        string timeStr = cycleStart.ToString("HH:mm:ss");

        _logger?.LogDebug(
            "Starting decode for cycle {Time}; pcm = {Samples} samples, RMS = {Rms:E3}.",
            timeStr, pcm.Length, rms);

        // ── Native decode ────────────────────────────────────────────────────
        // Offload to a thread-pool thread so that the blocking P/Invoke call does
        // not pin the async continuation's synchronisation context.
        var sw = System.Diagnostics.Stopwatch.StartNew();

        // ── D-002 PCM normalisation ──────────────────────────────────────────
        // Normalise a copy of the PCM buffer to a fixed target RMS before passing
        // to the native decoder.  This is a defensive pre-conditioning step for
        // pathologically low-amplitude inputs; it does not affect SNR accuracy on
        // typical captures.  Investigation (R&R runs 6ce38a3 and 4ab061a) confirmed
        // that the normalisation is invariant to the libft8 SNR formula: both
        // signal_db and noise_floor_db are waterfall-derived, so uniform amplitude
        // scaling cancels identically in both terms.  The D-002 bias fix was the
        // shim bandwidth constant (−26.0 → −26.5 dB, commit 3771986).
        // Operates on a copy — the caller's buffer is never mutated.
        float[] normalisedPcm = NormalisePcm(pcm, PcmNormalisationTargetRms);

        Ft8NativeResult[] native;
        int[]             passCounts;
        float             noiseFloorDb;

        // All three calls must be on the same thread — no await between them — because
        // ft8_get_last_pass_counts and ft8_get_last_noise_floor_db both read TLS written
        // by ft8_decode_all.  IMPORTANT: do not make this lambda async or split these
        // calls across separate Task.Run invocations; doing so would break the TLS guarantee.
        (native, passCounts, noiseFloorDb) = await Task.Run(() =>
        {
            var r = Ft8LibInterop.DecodeAll(normalisedPcm);
            var p = Ft8LibInterop.GetLastPassCounts(Ft8LibInterop.MaxDecodePasses);
            var n = Ft8LibInterop.GetLastNoiseFloorDb();
            return (r, p, n);
        }, ct);

        sw.Stop();

        // ── Map native results → DecodeResult ────────────────────────────────
        var results = new List<DecodeResult>(native.Length);
        var seen    = new HashSet<string>(StringComparer.Ordinal);

        foreach (ref readonly Ft8NativeResult nr in native.AsSpan())
        {
            // De-duplicate by message text (ft8_lib can produce the same message
            // from multiple candidates; the caller expects unique messages only).
            if (!seen.Add(nr.Message)) continue;

            // ── R4: Plausibility filter ──────────────────────────────────────
            // Reject Standard QSO messages whose 15-bit grid/report field has an
            // impossible value that slipped through CRC-14 by chance (≈ 1/16 384
            // per candidate; non-trivial over a 24-hour session on a busy band).
            if (!IsPlausibleMessage(nr.Message))
            {
                _logger?.LogDebug(
                    "Cycle {Time}: filtered implausible message '{Message}' (false-positive guard).",
                    timeStr, nr.Message);
                continue;
            }

            results.Add(new DecodeResult(
                Time:    timeStr,
                Snr:     nr.Snr,
                Dt:      Math.Round(nr.Dt, 1),
                FreqHz:  nr.FreqHz,
                Message: nr.Message));
        }

        // ── Per-pass iterative subtraction log (AC-IS-4) ────────────────────
        // Two explicit lines — one per pass (K_MAX_PASSES = 2).
        _logger?.LogDebug(
            "Iterative subtraction: pass {Pass} of {Max}, {K} new decodes.",
            1, passCounts.Length, passCounts.Length > 0 ? passCounts[0] : 0);
        _logger?.LogDebug(
            "Iterative subtraction: pass {Pass} of {Max}, {K} new decodes.",
            2, passCounts.Length, passCounts.Length > 1 ? passCounts[1] : 0);

        // ── Diagnostic log ───────────────────────────────────────────────────
        // Spec requirement: "Cycle {Time}: {Count} decode(s) found, elapsed={Elapsed} ms"
        _logger?.LogInformation(
            "Cycle {Time}: {Count} decode(s) found, elapsed={Elapsed} ms.",
            timeStr, results.Count, sw.ElapsedMilliseconds);

        // ── D-003 noise-floor diagnostic ─────────────────────────────────────
        // Log the histogram-median noise floor returned by ft8_get_last_noise_floor_db.
        // If D-003 (intermittent ~15 dB SNR under-report) is caused by a noise-floor
        // estimator anomaly, affected cycles will show this value ~15 dB above its
        // neighbours.  Logged at Information so it appears without adjusting log levels.
        _logger?.LogInformation(
            "Cycle {Time}: noise_floor={NoiseFloor:F1} dB (waterfall histogram median).",
            timeStr, noiseFloorDb);

        return results;
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    /// <summary>
    /// Returns a new float[] whose RMS equals <paramref name="targetRms"/>.
    /// If the input RMS is below <see cref="SilenceRmsThreshold"/> (effectively silent),
    /// the original array is returned unchanged to avoid divide-by-zero.
    /// The caller's <paramref name="pcm"/> array is never mutated.
    /// </summary>
    internal static float[] NormalisePcm(float[] pcm, float targetRms)
    {
        float srcRms = ComputeRms(pcm);
        if (srcRms < SilenceRmsThreshold)
            return pcm;          // silent buffer — return as-is; guard against ÷0

        float scale = targetRms / srcRms;
        var   result = new float[pcm.Length];
        for (int i = 0; i < pcm.Length; i++)
            result[i] = pcm[i] * scale;
        return result;
    }

    private static float ComputeRms(float[] pcm)
    {
        if (pcm.Length == 0) return 0f;
        double sum = 0.0;
        foreach (float s in pcm) sum += s * s;
        return (float)Math.Sqrt(sum / pcm.Length);
    }

    private static DateTime AlignToCycleStart(DateTime utc)
    {
        // FT8 cycles start at even 15-second boundaries (00, 15, 30, 45 seconds).
        int totalSeconds = utc.Second + utc.Minute * 60;
        int aligned      = (totalSeconds / 15) * 15;
        int deltaSeconds = totalSeconds - aligned;
        return utc.AddSeconds(-deltaSeconds).AddMilliseconds(-utc.Millisecond);
    }

    /// <summary>
    /// Returns <c>false</c> when <paramref name="text"/> looks like a false LDPC convergence —
    /// a Standard QSO message whose 15-bit grid/report field has an impossible bit value
    /// that slipped through CRC-14 by chance (≈ 1/16 384 per candidate; ~0.006% per cycle
    /// at 140 candidates).
    /// </summary>
    /// <remarks>
    /// Only applied to exactly 3-token messages (the Standard QSO pattern).  All other
    /// message forms — CQ messages, contest serials, free text, Type 4 hash notation —
    /// are accepted unconditionally to avoid false negatives on valid traffic.
    ///
    /// The filter catches the most common false-positive category: Maidenhead grid fields
    /// whose leading letter pair encodes values outside [0, 17] (letters beyond 'R').
    /// dB report fields and terminal tokens are validated against their known-valid forms.
    /// </remarks>
    internal static bool IsPlausibleMessage(string? text)
    {
        if (text is null) return false;

        // Quick count: only Standard QSO has exactly 3 space-separated tokens.
        int spaces = 0;
        foreach (char c in text) if (c == ' ') spaces++;
        if (spaces != 2) return true; // Not 3-token — accept unconditionally.

        int    lastSpace = text.LastIndexOf(' ');
        string last      = text[(lastSpace + 1)..];

        // CQ messages (first token "CQ") are always valid.
        if (text.StartsWith("CQ ", StringComparison.Ordinal)) return true;

        // Terminal tokens (Standard QSO closing phase).
        if (last is "RRR" or "73" or "RR73") return true;

        // Type 4 hash notation — callsign not in per-call table.
        if (last.Contains('<')) return true;

        // dB report: [+-][0-9][0-9]
        // Received report: R[+-][0-9][0-9]
        if (IsDbReport(last)) return true;

        // 4-char candidate grid: [letter][letter][digit][digit]
        // Maidenhead letter indices must be in [0, 17] → letters in [A-R].
        // Values outside this range indicate impossible bit encodings.
        if (last.Length == 4 &&
            char.IsAsciiDigit(last[2]) &&
            char.IsAsciiDigit(last[3]))
        {
            if (char.IsAsciiLetter(last[0]) && char.IsAsciiLetter(last[1]))
                // Reject if either leading letter is beyond 'R' (Maidenhead index > 17).
                return char.ToUpperInvariant(last[0]) <= 'R' &&
                       char.ToUpperInvariant(last[1]) <= 'R';

            // Non-letter prefix (unusual contest serial or numeric form) — accept.
            return true;
        }

        // All-digit tokens: contest serial numbers (00000–97799) and other numeric fields.
        bool allDigits = last.Length > 0;
        foreach (char c in last) if (!char.IsAsciiDigit(c)) { allDigits = false; break; }
        if (allDigits) return true;

        // 3-token message with an unrecognisable last field — likely a false positive.
        return false;
    }

    private static bool IsDbReport(string token)
    {
        ReadOnlySpan<char> t = token.AsSpan();
        if (t.Length == 4 && t[0] == 'R') t = t[1..];
        return t.Length == 3
               && (t[0] == '+' || t[0] == '-')
               && char.IsAsciiDigit(t[1])
               && char.IsAsciiDigit(t[2]);
    }
}
