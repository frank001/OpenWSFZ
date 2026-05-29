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
/// The <see cref="IModeDecoder"/> contract is unchanged: callers pass a 15-second
/// 12 kHz mono float[] and receive a list of <see cref="DecodeResult"/> records.
/// Everything else — <see cref="CycleFramer"/>, <see cref="DecodeResult"/>, ALL.TXT
/// logging — is unaffected.
/// </para>
/// </summary>
public sealed class Ft8Decoder : IModeDecoder
{
    private const int ExpectedSampleCount = 180_000;   // 15 s × 12 000 Hz
    private const float SilenceRmsThreshold = 1e-6f;   // all-zero codeword guard

    private readonly IClock              _clock;
    private readonly ILogger<Ft8Decoder>? _logger;

    public Ft8Decoder(IClock clock, ILogger<Ft8Decoder>? logger = null)
    {
        _clock  = clock;
        _logger = logger;
    }

    /// <inheritdoc/>
    public Task<IReadOnlyList<DecodeResult>> DecodeAsync(float[] pcm, CancellationToken ct = default)
    {
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
            return Task.FromResult<IReadOnlyList<DecodeResult>>([]);
        }

        // ── Cycle-start timestamp ────────────────────────────────────────────
        // Capture before the (potentially slow) decode so the Time field in each
        // DecodeResult reflects the start of the 15-second window.
        var    cycleStart = AlignToCycleStart(_clock.UtcNow);
        string timeStr    = cycleStart.ToString("HH:mm:ss");

        _logger?.LogDebug(
            "Starting decode for cycle {Time}; pcm = {Samples} samples, RMS = {Rms:E3}.",
            timeStr, pcm.Length, rms);

        // ── Native decode ────────────────────────────────────────────────────
        var sw = System.Diagnostics.Stopwatch.StartNew();

        Ft8NativeResult[] native = Ft8LibInterop.DecodeAll(pcm);

        sw.Stop();

        // ── Map native results → DecodeResult ────────────────────────────────
        var results = new List<DecodeResult>(native.Length);
        var seen    = new HashSet<string>(StringComparer.Ordinal);

        foreach (ref readonly Ft8NativeResult nr in native.AsSpan())
        {
            // De-duplicate by message text (ft8_lib can produce the same message
            // from multiple candidates; the caller expects unique messages only).
            if (!seen.Add(nr.Message)) continue;

            results.Add(new DecodeResult(
                Time:    timeStr,
                Snr:     nr.Snr,
                Dt:      Math.Round(nr.Dt, 1),
                FreqHz:  nr.FreqHz,
                Message: nr.Message));
        }

        // ── Diagnostic log ───────────────────────────────────────────────────
        // Spec requirement: "Cycle {Time}: {Count} decode(s) found, elapsed={Elapsed} ms"
        _logger?.LogInformation(
            "Cycle {Time}: {Count} decode(s) found, elapsed={Elapsed} ms.",
            timeStr, results.Count, sw.ElapsedMilliseconds);

        return Task.FromResult<IReadOnlyList<DecodeResult>>(results);
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

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
}
