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
/// 20260007 — diag-d001-three-pass-sic (H2): K_MAX_PASSES 2→3 diagnostic. REVERTED (S7 50.54%, −4.30 pp).
/// 20260008 — diag-d001-pcm-sic (H3): CP-FSK/cosine PCM-domain SIC. REJECTED (S7 40.86%, −13.98 pp).
/// 20260009 — diag-d001-h3b-gfsk-sic (H3b): GFSK quadrature PCM SIC; analytic amplitude estimator. REJECTED (S7 37.63%, −17.21 pp).
/// 20260010 — diag-d001-h4-spectrogram-reinstate (H4): spectrogram suppression reinstated; H3b call site removed; GFSK helpers retained. ACCEPTED (S7 56.99%). Active baseline; restored after H5 rejection.
/// 20260011 — diag-d001-h5-suppression-tuning (H5): suppression ramp shifted [−5,+15]→[−15,+5]. REJECTED (S7 46.24%, −10.75 pp). Over-suppression confirmed. Reverted to 20260010.
/// 20260012 — fix-d004-local-noise-floor: per-signal local noise floor replaces global histogram-median in SNR formula. Resolves D-003 (SNR under-report) and D-004 (frequency-dependent bias).
/// 20260013 — fix-seh-av-containment: __try/__except wrapper in ft8_decode_all returns -2 on AV instead of crashing. D-006 root cause still unknown.
/// 20260014 — diag-d006-minidump: MiniDumpWriteDump moved to filter-expression function so ExceptionAddress is captured before stack unwind.
/// 20260015 — fix-d006-ptr-truncation: binary patch to message.obj — MOVSXD RBX,EAX at ftx_message_decode stpcpy call site replaced with MOV RBX,RAX. Fixes 32-bit pointer truncation crash for "R " prefix messages when thread stack is above 4 GB VA boundary. D-006 RESOLVED.
/// 20260016 — fix-d006-cleanup + fix-rq2-signal-db-oob: removed ft8_av_exception_filter and MiniDumpWriteDump infrastructure; __except reverts to EXCEPTION_EXECUTE_HANDLER. Also guards signal_db loop against out-of-bounds waterfall access for signals >= 2956 Hz.
/// </para>
///
/// <para>
/// The <see cref="IModeDecoder"/> contract is unchanged: callers pass a 15-second
/// 12 kHz mono float[] and receive a list of <see cref="DecodeResult"/> records.
/// Everything else — <see cref="CycleFramer"/>, <see cref="DecodeResult"/>, ALL.TXT
/// logging — is unaffected.
/// </para>
/// </summary>
public sealed class Ft8Decoder : IModeDecoder, IApConstraintSink
{
    private const int   ExpectedSampleCount         = 180_000;  // 15 s × 12 000 Hz
    private const float SilenceRmsThreshold         = 1e-6f;    // all-zero codeword guard
    private const float PcmNormalisationTargetRms   = 0.20f;    // D-002 SNR-bias fix: bring PCM to a fixed RMS level before native decode

    // Singleton default — stateless adapter; safe to share across instances.
    private static readonly IFt8NativeInterop DefaultInterop = new Ft8NativeInteropAdapter();

    private readonly IClock               _clock;
    private readonly ILogger<Ft8Decoder>? _logger;
    private readonly IFt8NativeInterop    _interop;

    // H6 AP decode (D-001): snapshot is taken inside Task.Run (same thread as DecodeAll).
    // volatile guarantees a fresh read without a lock; the reference itself is atomically
    // replaced by SetApConstraints, which is safe because writes and reads are both one
    // machine-word pointer operations on all supported platforms.
    private volatile Ft8ApConstraints? _apConstraints;

    /// <inheritdoc/>
    public void SetApConstraints(Ft8ApConstraints? constraints)
        => _apConstraints = constraints;

    /// <param name="clock">Wall-clock provider for aligning cycle timestamps.</param>
    /// <param name="logger">Optional structured logger; pass null to suppress all log output.</param>
    public Ft8Decoder(IClock clock, ILogger<Ft8Decoder>? logger = null)
        : this(clock, logger, DefaultInterop) { }

    /// <summary>
    /// Internal constructor for unit testing — allows a fake <see cref="IFt8NativeInterop"/>
    /// to be injected without loading the native DLL (accessible via
    /// <c>[assembly: InternalsVisibleTo("OpenWSFZ.Ft8.Tests")]</c>).
    /// </summary>
    internal Ft8Decoder(IClock clock, ILogger<Ft8Decoder>? logger, IFt8NativeInterop interop)
    {
        _clock   = clock;
        _logger  = logger;
        _interop = interop;
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
        int[]             candidateCounts;
        float             noiseFloorDb;
        (float[] LlrMeanAbs, float[] LlrPrenormVariance, int[] LlrFailCount) llrStats;

        // All five calls must be on the same thread — no await between them — because
        // ft8_get_last_pass_counts, ft8_get_last_candidate_counts,
        // ft8_get_last_noise_floor_db, and ft8_get_last_llr_stats all read TLS written
        // by ft8_decode_all.
        // IMPORTANT: do not make this lambda async or split these calls across separate
        // Task.Run invocations; doing so would break the TLS guarantee.
        //
        // NativeAccessViolationException (D-006 / SEH containment): if DecodeAll throws,
        // the lambda exits immediately — GetLastPassCounts, GetLastCandidateCounts,
        // GetLastNoiseFloorDb, and GetLastLlrStats are never reached, which is correct
        // because TLS state is unreliable after an AV (R-1 guard).
        // The exception propagates through Task.Run → await and is caught below.
        try
        {
            (native, passCounts, candidateCounts, noiseFloorDb, llrStats) = await Task.Run(() =>
            {
                // AP decode constraints (H6, D-001): must be set on the same thread as DecodeAll.
                // Snapshot to avoid tearing — _apConstraints is volatile but is a reference type.
                var ap = _apConstraints;
                if (ap is not null)
                    _interop.SetApBits(ap.MycallBits, ap.HiscallBits);
                else
                    _interop.SetApBits([], []);  // explicitly clear any TLS residue from a prior cycle

                var r = _interop.DecodeAll(normalisedPcm);
                var p = _interop.GetLastPassCounts(_interop.MaxDecodePasses);
                var c = _interop.GetLastCandidateCounts(_interop.MaxDecodePasses);
                var n = _interop.GetLastNoiseFloorDb();
                var l = _interop.GetLastLlrStats(_interop.MaxDecodePasses);
                return (r, p, c, n, l);
            }, ct);
        }
        catch (NativeAccessViolationException)
        {
            // Access violation caught by the native SEH wrapper (Windows only, D-006).
            // Log at WARNING so every occurrence is visible for root-cause investigation,
            // then return empty results — the cycle is skipped; the process continues.
            _logger?.LogWarning(
                "Cycle {Time}: native decode access violation (AV) caught by SEH wrapper — " +
                "cycle skipped. If this recurs, configure WER LocalDumps or attach ProcDump " +
                "before the next live run to capture a crash dump for D-006 root-cause analysis.",
                timeStr);
            return [];
        }

        sw.Stop();

        // ── Map native results → DecodeResult ────────────────────────────────
        var results = new List<DecodeResult>(native.Length);
        var seen    = new HashSet<string>(StringComparer.Ordinal);

        foreach (ref readonly Ft8NativeResult nr in native.AsSpan())
        {
            // D-005 fix: ft8_lib pads FT8Result.message to 36 bytes with trailing spaces
            // before the null terminator.  A Type 4 hash message such as "<HASH> CALLSIGN"
            // arrives as "<HASH> CALLSIGN \0" and marshals to "<HASH> CALLSIGN " (trailing
            // space).  Without trimming, IsPlausibleMessage sees two spaces, enters the
            // 3-token branch, extracts an empty last token, and incorrectly filters the
            // message.  TrimEnd() removes the padding before any downstream processing.
            string msg = nr.Message.TrimEnd();

            // De-duplicate by message text (ft8_lib can produce the same message
            // from multiple candidates; the caller expects unique messages only).
            if (!seen.Add(msg)) continue;

            // ── R4: Plausibility filter ──────────────────────────────────────
            // Reject Standard QSO messages whose 15-bit grid/report field has an
            // impossible value that slipped through CRC-14 by chance (≈ 1/16 384
            // per candidate; non-trivial over a 24-hour session on a busy band).
            if (!IsPlausibleMessage(msg))
            {
                _logger?.LogDebug(
                    "Cycle {Time}: filtered implausible message '{Message}' (false-positive guard).",
                    timeStr, msg);
                continue;
            }

            results.Add(new DecodeResult(
                Time:    timeStr,
                Snr:     nr.Snr,
                Dt:      Math.Round(nr.Dt, 1),
                FreqHz:  nr.FreqHz,
                Message: msg));
        }

        // ── Per-pass iterative subtraction log (AC-IS-4) ────────────────────
        // Loop over passCounts.Length so the log scales correctly with K_MAX_PASSES
        // without needing further code changes when the pass count changes.
        for (int p = 0; p < passCounts.Length; p++)
        {
            int candidates = p < candidateCounts.Length ? candidateCounts[p] : -1;
            _logger?.LogDebug(
                "Iterative subtraction: pass {Pass} of {Max}, {Candidates} candidates found, {K} decoded.",
                p + 1, passCounts.Length, candidates, passCounts[p]);
        }

        // ── D-001 LLR diagnostic log ─────────────────────────────────────────
        // Logged at Debug so it is only captured when file logging is enabled at
        // Debug level (Lesson 8: pre-configure Logging.FileEnabled = true and
        // Logging.FileLogLevel = "Debug" before any diagnostic run).
        // prenormVar (shim 20260020): pre-normalisation variance of raw log174.
        // R&R run on shim 20260020 REFUTED the near-zero LLR hypothesis —
        // co_channel fail cands show prenormVar 37–60 (not small). Revised
        // failure model: high-confidence wrong-sign LLRs under equal-SNR
        // co-channel. Probe retained for longitudinal monitoring.
        for (int p = 0; p < llrStats.LlrMeanAbs.Length; p++)
        {
            _logger?.LogDebug(
                "Iterative subtraction: pass {Pass} LDPC fail stats — " +
                "failCands={FailCount} meanAbsLLR={MeanAbs:F3} prenormVar={PrenormVar:F4}",
                p + 1, llrStats.LlrFailCount[p], llrStats.LlrMeanAbs[p], llrStats.LlrPrenormVariance[p]);
        }

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
    /// a blank/whitespace message, a raw hex dump (unrecognised message type), a message
    /// containing an oversized callsign token (D-009 OSD false-positive guard), or a
    /// Standard QSO message whose 15-bit grid/report field has an impossible bit value
    /// that slipped through CRC-14 by chance (≈ 1/16 384 per candidate; ~0.006% per cycle
    /// at 140 candidates).
    /// </summary>
    /// <remarks>
    /// <para>
    /// D9-R1 — blank/whitespace: empty or whitespace-only strings are rejected.  LDPC can
    /// converge to a valid codeword that maps to no printable message type; this guard
    /// prevents empty strings from reaching ALL.TXT and the UI.
    /// </para>
    /// <para>
    /// D9-R2 — hex dump: <c>ft8_lib</c> renders unrecognised message types as a raw
    /// uppercase hex string with no spaces.  Any single-token string ≥ 16 chars whose
    /// every character is an uppercase hex digit is rejected.
    /// </para>
    /// <para>
    /// D9-R3 — oversized callsign: a Type 1 callsign packs into 28 bits; the largest
    /// valid rendered form is a 6-char base call with a 3-char portable suffix
    /// (e.g. <c>VK9ABC/QRP</c>, 10 chars total).  Any callsign-position token whose base
    /// exceeds 6 chars, or whose total exceeds 10 chars, was not produced by valid
    /// callsign packing and is therefore a false-positive OSD candidate.
    /// </para>
    /// <para>
    /// D9-R4 (existing) — Maidenhead grid / report validation on 3-token Standard QSO
    /// messages: grid letters must be in [A–R]; dB reports must match known-valid forms.
    /// All other message forms are accepted unconditionally.
    /// </para>
    /// </remarks>
    internal static bool IsPlausibleMessage(string? text)
    {
        if (text is null) return false;

        // ── D9-R1: Blank / whitespace ────────────────────────────────────────────
        // LDPC can converge to a codeword that produces no printable message type;
        // the resulting empty / whitespace-only string is always a false positive.
        if (string.IsNullOrWhiteSpace(text)) return false;

        // ── D9-R2: Hex dump (unrecognised message type) ──────────────────────────
        // ft8_lib renders unrecognised message types as a raw uppercase hex string
        // with no spaces.  Threshold of 16 chars gives generous headroom above the
        // longest valid unspaced callsign token (10 chars including /suffix).
        if (text.Length >= 16 && !text.Contains(' ') && IsAllUpperHex(text)) return false;

        // ── R5 Rule A: Single-token ───────────────────────────────────────────────
        // No valid FT8 decode is ever a single token.  This gate is ordered after D9-R2
        // so long hex-dump strings hit that rule first (behaviour unchanged); shorter
        // single-token garbage (e.g. a callsign-sized OSD hit with no spaces) is caught
        // here.
        if (!text.Contains(' ')) return false;

        // ── D9-R3: Oversized callsign token ──────────────────────────────────────
        // Applied to 2-token CQ/DE/QRZ messages (callsign is token 1) and 3-token
        // Standard QSO messages (tokens 0 and 1 are callsigns).
        // IndexOf avoids a second pass over the string after the spaces count below.
        {
            int firstSpace  = text.IndexOf(' ');
            int secondSpace = firstSpace  >= 0 ? text.IndexOf(' ', firstSpace  + 1) : -1;
            int thirdSpace  = secondSpace >= 0 ? text.IndexOf(' ', secondSpace + 1) : -1;

            if (firstSpace > 0 && secondSpace < 0)
            {
                // 2-token message: "TOKEN0 TOKEN1"
                // Check both tokens — the CQ/DE/QRZ restriction on token0 was too narrow;
                // patterns like "<...> M5E5B91HFHL" and "9ULLPTCDZH <...>" slipped through.
                // IsCallsignOversized already exempts hash references (<...) and short keywords.
                string token0 = text[..firstSpace];
                string token1 = text[(firstSpace + 1)..];
                if (IsCallsignOversized(token0) || IsCallsignOversized(token1))
                    return false;

                // R5 Rule C — CQ <hash>: "CQ <...>" is not a valid 2-token FT8 form.
                // In FT8, CQ messages always carry a real callsign (and optionally a grid);
                // a 2-token "CQ <hash>" is an OSD CRC-14 coincidence (D-009 Category C FP).
                if (token0.Equals("CQ", StringComparison.Ordinal) &&
                    token1.Length > 0 && token1[0] == '<')
                    return false;
            }
            else if (firstSpace > 0 && secondSpace > firstSpace
                     && thirdSpace < 0)
            {
                // Exactly 3-token message: "TOKEN0 TOKEN1 TOKEN2"
                string token0 = text[..firstSpace];
                string token1 = text[(firstSpace + 1)..secondSpace];
                if (IsCallsignOversized(token0) || IsCallsignOversized(token1))
                    return false;
            }
            else if (firstSpace > 0 && secondSpace > firstSpace && thirdSpace > secondSpace
                     && text.IndexOf(' ', thirdSpace + 1) < 0)
            {
                // Exactly 4-token message: "TOKEN0 TOKEN1 TOKEN2 TOKEN3"
                // The only valid 4-token FT8 forms are "CQ <modifier> <callsign> <grid>"
                // (e.g. "CQ DX Q1ABC FN42", "CQ NA Q9XYZ EN37").
                // Patterns like "CALLSIGN CALLSIGN R GRID" are OSD CRC-14 false alarms
                // (D-009 R2 verification, Category A) — they are not Type 1 FT8 messages.
                string token0 = text[..firstSpace];
                if (!token0.Equals("CQ", StringComparison.Ordinal))
                    return false;
            }
            // 5+ token messages: not validated here.
        }

        // Quick count: only Standard QSO has exactly 3 space-separated tokens.
        int spaces = 0;
        foreach (char c in text) if (c == ' ') spaces++;

        // R5 Rule B — 5+ tokens: no valid FT8 message type has 5 or more tokens.
        // Valid forms top out at 4 tokens (CQ <modifier> <callsign> <grid>), already gated
        // above.  An OSD hit with ≥ 4 spaces is a CRC-14 false positive.
        if (spaces >= 4) return false;

        if (spaces != 2) return true; // Not 3-token — accept unconditionally.

        int    lastSpace = text.LastIndexOf(' ');
        string last      = text[(lastSpace + 1)..];

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

    /// <summary>
    /// Returns <c>true</c> when every character in <paramref name="s"/> is an uppercase
    /// hexadecimal digit (0–9, A–F).  Used by the D9-R2 hex-dump guard.
    /// </summary>
    private static bool IsAllUpperHex(string s)
    {
        foreach (char c in s)
            if (!((c >= '0' && c <= '9') || (c >= 'A' && c <= 'F')))
                return false;
        return true;
    }

    /// <summary>
    /// Returns <c>true</c> when <paramref name="token"/> is a callsign-position token
    /// that exceeds the limits of valid Type 1 callsign packing (D9-R3 guard).
    /// </summary>
    /// <remarks>
    /// Exempt cases (always returns <c>false</c>):
    /// <list type="bullet">
    ///   <item>Hash-reference tokens beginning with <c>&lt;</c> (e.g. <c>&lt;...&gt;</c>).</item>
    ///   <item>Short pseudo-callsigns with ≤ 3 characters (CQ, DE, QRZ).</item>
    /// </list>
    /// A valid Type 1 base callsign has at most 6 characters; with a portable suffix
    /// (<c>/P</c>, <c>/M</c>, <c>/R</c>, <c>/MM</c>, <c>/QRP</c>) the rendered token
    /// reaches at most 10 characters.  Anything beyond these limits was not produced
    /// by valid callsign packing.
    /// </remarks>
    private static bool IsCallsignOversized(string token)
    {
        if (token.StartsWith('<')) return false;   // hash reference — never oversized
        if (token.Length <= 3)    return false;    // CQ / DE / QRZ / very short call — exempt

        // Split on '/' to isolate the base callsign from any portable suffix.
        int    slashPos  = token.IndexOf('/');
        string baseCall  = slashPos >= 0 ? token[..slashPos] : token;

        // Base callsign from standard Type 1 packing: maximum 6 characters.
        // Rendered token with /suffix: maximum 10 characters.
        return baseCall.Length > 6 || token.Length > 10;
    }
}
