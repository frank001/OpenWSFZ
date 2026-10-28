using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Interop;
using OpenWSFZ.Ft8.Subfeas;

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
public sealed class Ft8Decoder : IModeDecoder, IApConstraintSink, IDisposable
{
    private const int   ExpectedSampleCount         = 180_000;  // 15 s × 12 000 Hz
    private const float SilenceRmsThreshold         = 1e-6f;    // all-zero codeword guard
    private const float PcmNormalisationTargetRms   = 0.20f;    // D-002 SNR-bias fix: bring PCM to a fixed RMS level before native decode

    /// <summary>
    /// sub-feas-speed-redesign A4: the configured <c>decoder.subtractionMaxThreads</c> (0 = auto). The effective
    /// number of concurrent residual-pass fits, and the native workspace pool's bound, is resolved from it once
    /// per decode cycle by <see cref="SubtractionThreads.Resolve"/> and takes effect on the next cycle. Replaces
    /// the fixed <c>Math.Min(Environment.ProcessorCount, 4)</c> cap of the base change.
    /// </summary>
    private volatile int _subtractionMaxThreads;

    /// <summary>The last out-of-range configured value already warned about (never warned about twice).</summary>
    private int _warnedSubtractionMaxThreads;

    /// <summary>
    /// sub-feas-speed-redesign A4: sets the configured fit thread count (<c>0</c> = auto, otherwise clamped to
    /// <c>[1, ProcessorCount]</c>). Called when the config is applied (startup and every config save). Logs
    /// <b>one</b> warning when a non-zero value had to be clamped, never per decode cycle and not again for the
    /// same value on later, unrelated config saves. Takes effect on the next decode cycle.
    /// </summary>
    public void SetSubtractionMaxThreads(int configured)
    {
        _subtractionMaxThreads = configured;

        int effective = SubtractionThreads.Resolve(configured, Environment.ProcessorCount, out bool clamped);
        if (!clamped)
        {
            _warnedSubtractionMaxThreads = 0;
            return;
        }
        if (Interlocked.Exchange(ref _warnedSubtractionMaxThreads, configured) == configured)
            return;
        _logger?.LogWarning(
            "Decoder: subtractionMaxThreads {Original} out of range [1, {Max}] - clamped to {Clamped}.",
            configured, Math.Max(1, Environment.ProcessorCount), effective);
    }

    /// <summary>
    /// The effective residual-pass fit parallelism for the current configuration on this machine:
    /// <c>0</c> means auto, <c>max(1, ProcessorCount - 2)</c>. Read once per decode cycle.
    /// </summary>
    internal int EffectiveSubtractionThreads
        => SubtractionThreads.Resolve(_subtractionMaxThreads, Environment.ProcessorCount, out _);

    /// <summary>
    /// Frees the native residual-pass workspace pool (sub-feas-speed-redesign A3). The daemon calls this at
    /// shutdown, after the decode pump has stopped. Idempotent, and it does not load the native library.
    /// </summary>
    public void Dispose() => _interop.SubfeasPoolShutdown();

    /// <summary>
    /// Hard per-cycle wall-clock budget (13 s, tasks.md runtime gate) for pass-0 plus the
    /// residual pass. The residual pass gets whatever remains after pass-0 and abandons itself
    /// (pass-0-only) if it runs out. A hard bound since sub-feas-speed-redesign A5: the native fits are
    /// cancelled at <c>budget - SubtractionPass.SubtractionResidualDecodeReserve</c>.
    /// </summary>
    internal static readonly TimeSpan SubtractionCycleBudget = TimeSpan.FromSeconds(13);

    // Singleton default — stateless adapter; safe to share across instances.
    private static readonly IFt8NativeInterop DefaultInterop = new Ft8NativeInteropAdapter();

    /// <summary>
    /// The native FT8 decoder shim's actual loaded ABI version
    /// (f-004-operator-visibility-improvements, design.md Decision 1).
    /// Reading this property triggers the native library's lazy load + ABI self-test
    /// as a side effect if it has not already run — callers that want the ABI check to
    /// happen at daemon startup (rather than on the first decode cycle) should read this
    /// property once, early, before the web host starts accepting requests. The value is
    /// stable for the remainder of the process lifetime once read.
    /// </summary>
    /// <exception cref="InvalidOperationException">
    /// Thrown if the native DLL cannot be loaded or the ABI version check fails — same as
    /// any other native call through <see cref="Ft8LibInterop"/>.
    /// </exception>
    public static int LoadedShimVersion => Ft8LibInterop.LoadedShimVersion;

    private readonly IClock                 _clock;
    // COH-FB-AUDIO N-1: the time source of the cycle's elapsed/budget arithmetic (BudgetClock). System in production; a test injects a fake.
    private readonly TimeProvider          _timeProvider;
    private readonly ILogger<Ft8Decoder>?   _logger;
    private readonly IFt8NativeInterop      _interop;
    private readonly ICallsignGrammarStore? _grammarStore;
    private readonly ICallsignRegionStore?  _regionStore;
    private readonly IWorkedBeforeIndex?    _workedBeforeIndex;

    // H6 AP decode (D-001): snapshot is taken inside Task.Run (same thread as DecodeAll).
    // volatile guarantees a fresh read without a lock; the reference itself is atomically
    // replaced by SetApConstraints, which is safe because writes and reads are both one
    // machine-word pointer operations on all supported platforms.
    private volatile Ft8ApConstraints? _apConstraints;

    /// <inheritdoc/>
    public void SetApConstraints(Ft8ApConstraints? constraints)
        => _apConstraints = constraints;

    /// <summary>
    /// Forwards the OSD gate parameters to the native shim so they take effect on the
    /// next decode cycle.  Thread-safe: the native setter writes to module-level globals
    /// that are only read at the start of each <c>ft8_decode_all</c> call.
    ///
    /// <para>
    /// Called from the daemon's <c>IConfigStore.OnSaved</c> handler and once at startup
    /// so that the operator's saved values override the compile-time defaults without a
    /// daemon restart.  When the caller passes <c>null</c> for <paramref name="kMinScorePass2"/>
    /// (i.e. the <c>decoder</c> config key is absent), use <c>new DecoderConfig()</c> to
    /// obtain the calibrated defaults before calling this method.
    /// </para>
    /// </summary>
    public void SetDecodeParams(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax)
        => _interop.SetDecodeParams(kMinScorePass2, osdCorrThreshold, osdNhardMax);

    /// <summary>osd-sign-fix (#215, shim 20260060): sets the process-global OSD sign switch (1 = corrected, 0 = previous behaviour). For the replay harness; the daemon never calls it.</summary>
    public void SetOsdSignFix(int enabled) => _interop.SetOsdSignFix(enabled);

    /// <summary>osd-sign-fix (#215, shim 20260060): reads the OSD sign switch.</summary>
    public int GetOsdSignFix() => _interop.GetOsdSignFix();

    /// <summary>
    /// sub-feas-native-subtraction (design.md Decision 6): gates the additive residual-decode
    /// pass (<see cref="SubtractionPass"/>). Default <c>false</c> at construction — with the
    /// flag off, <see cref="DecodeAsync(float[],DateTime,string?,CancellationToken)"/>'s output
    /// is byte-identical to pre-change behaviour. Takes effect on the next decode cycle, no
    /// rebuild required (spec's own "Feature can be enabled without a rebuild" scenario).
    /// Thread-safe: <c>volatile</c> bool, read once at the top of each decode cycle.
    /// </summary>
    public void SetSubtractionEnabled(bool enabled)
        => _subtractionEnabled = enabled;

    private volatile bool _subtractionEnabled;

    // ── third-pass-deep (#240, step 1) ───────────────────────────────────────

    private volatile int _decodingDepth;   // (int)DecodingDepth; Normal (0) at construction

    /// <summary>
    /// third-pass-deep: sets <c>decoder.decodingDepth</c>. <see cref="DecodingDepth.Normal"/> (the default at
    /// construction) is the decoder as it was before the third pass existed; <see cref="DecodingDepth.Deep"/> adds the
    /// third pass to <see cref="DecodeStagedAsync"/> cycles. Read once per decode cycle; takes effect on the next cycle.
    /// </summary>
    public void SetDecodingDepth(DecodingDepth depth)
        => _decodingDepth = (int)depth;

    /// <summary>The decoding depth the decoder is using now (what <c>GET /api/v1/status</c> reports).</summary>
    public DecodingDepth DecodingDepth => (DecodingDepth)_decodingDepth;

    // ── COH-FALLBACK (A' step 3) Stage 2 ──────────────────────────────────────

    private volatile bool _coherentFallbackEnabled;   // false at construction

    /// <summary>
    /// COH-FALLBACK Stage 2 (R10): sets <c>decoder.coherentFallbackEnabled</c>. <c>false</c> (the default of a bare decoder at construction; the daemon applies <c>decoder.coherentFallbackEnabled</c>, default <c>true</c>, at start-up) is the decoder
    /// as it was before the fallback existed: no extra native call, the same outputs in the same order. <c>true</c> runs the coherent-
    /// extraction fallback on the candidates the ordinary decode did not decode. Step 4: it STARTS only after the cycle's last ordinary batch
    /// has been handed off (never during pass 0's follow-on work, the residual pass or the third pass), runs on up to
    /// <see cref="EffectiveSubtractionThreads"/> worker threads, and publishes as a batch of its own after every ordinary batch: batch 4 on
    /// <see cref="DecodingDepth.Deep"/>, batch 3 on Normal, only if non-empty. It has an effect only while <see cref="SubtractionEnabled"/> is on
    /// and only on <see cref="DecodeStagedAsync"/> (the entry with a callback for every batch): <see cref="DecodeTwoStageAsync"/> has no callback
    /// for a batch of its own, so the flag has no effect there; the early decode never runs it (R9). Read once per decode cycle; takes effect on
    /// the next cycle. For the replay harness as well as the daemon.
    /// </summary>
    public void SetCoherentFallbackEnabled(bool enabled)
        => _coherentFallbackEnabled = enabled;

    /// <summary>COH-FALLBACK Stage 2: whether the coherent-extraction fallback is on now (the read-back of <see cref="SetCoherentFallbackEnabled"/>).</summary>
    public bool CoherentFallbackEnabled => _coherentFallbackEnabled;

    private volatile bool _coherentFallbackMultiSet;   // false at construction; the daemon sets the configured value (default true) before the first cycle

    /// <summary>
    /// COH-MULTISET: sets <c>decoder.coherentFallbackMultiSet</c>. The decoder object itself starts <c>false</c> at construction; the configured default
    /// (<c>DecoderConfig.CoherentFallbackMultiSet</c>, true when the key is absent) reaches it through this setter, which the daemon calls before
    /// the first cycle and on every config change. <c>false</c> leaves the fallback exactly as it was: the same native calls, outputs and order. <c>true</c> makes the fallback try C1, J2, J3, N1 on a candidate where V3 gives no CRC-valid
    /// output. It acts only while <see cref="CoherentFallbackEnabled"/> is on. Read once per decode cycle; takes effect on the next cycle.
    /// </summary>
    public void SetCoherentFallbackMultiSet(bool enabled)
        => _coherentFallbackMultiSet = enabled;

    /// <summary>COH-MULTISET: whether the multi-set walk is requested now (the read-back of <see cref="SetCoherentFallbackMultiSet"/>).</summary>
    public bool CoherentFallbackMultiSet => _coherentFallbackMultiSet;

    private volatile CoherentFallbackAudio _coherentFallbackAudio = CoherentFallbackAudio.Original;   // the object starts Original; the daemon sets the configured value (default Both) before the first cycle

    /// <summary>
    /// COH-FB-AUDIO: sets <c>decoder.coherentFallbackAudio</c>. The decoder object itself starts at <see cref="CoherentFallbackAudio.Original"/> (the
    /// fallback as it was); the configured default (<c>DecoderConfig.CoherentFallbackAudio</c>, <c>Both</c> when the key is absent) reaches it through
    /// this setter, which the daemon calls before the first cycle and on every config change. Read once per decode cycle; takes effect on the next cycle.
    /// It acts only while <see cref="CoherentFallbackEnabled"/> is on.
    /// </summary>
    public void SetCoherentFallbackAudio(CoherentFallbackAudio audio)
        => _coherentFallbackAudio = audio;

    /// <summary>COH-FB-AUDIO: the audio mode the fallback uses now (the read-back of <see cref="SetCoherentFallbackAudio"/>).</summary>
    public CoherentFallbackAudio CoherentFallbackAudio => _coherentFallbackAudio;

    /// <summary>
    /// COH-FALLBACK Stage 2, R7': time held back from the shared 13 s cycle budget for the work after the native fallback returns (the text
    /// unpack, the mapping and the publish of the last batch). The native run stops starting candidates at <c>budget - elapsed - this</c>.
    /// </summary>
    internal static readonly TimeSpan CoherentFallbackPublishReserve = TimeSpan.FromMilliseconds(250);

    private long _thirdPassRuns, _thirdPassSkippedNoNew, _thirdPassSkippedAbandoned,
                 _thirdPassAbandoned, _thirdPassFailed, _thirdPassDecodes;

    /// <summary>
    /// third-pass-deep (B6): the third pass's process-lifetime counters and the depth in use, separate from the residual
    /// pass's. All counters stay 0 while the depth is <see cref="DecodingDepth.Normal"/>.
    /// </summary>
    public ThirdPassStatus GetThirdPassStatus() => new(
        DecodingDepth.ToString(),
        Interlocked.Read(ref _thirdPassRuns),
        Interlocked.Read(ref _thirdPassSkippedNoNew),
        Interlocked.Read(ref _thirdPassSkippedAbandoned),
        Interlocked.Read(ref _thirdPassAbandoned),
        Interlocked.Read(ref _thirdPassFailed),
        Interlocked.Read(ref _thirdPassDecodes));

    /// <summary>
    /// Return the process-lifetime count of Type 4 callsign announcements the native decoder
    /// discarded because its session-scoped callsign hash table was already at its 4096-slot
    /// capacity (f-005-hash-table-saturation-diagnostic; capacity raised from 256 to 4096 at
    /// shim 20260038, g2-hash-table-sizing-and-candidate-passband).
    /// <para>
    /// A non-zero value means the hash table saturated during this session and one or more
    /// nonstandard-callsign announcements could not be stored — the exact condition F-001's
    /// design flagged as a risk on a busy or long session.  The daemon reads this once at
    /// graceful shutdown to log a session-end summary line, and serves it live on
    /// <c>GET /api/v1/status</c> for mid-session diagnosis.  Reading has no side effects; the
    /// counter resets to 0 only on daemon restart.
    /// </para>
    /// </summary>
    public int GetHashTableRejectCount()
        => _interop.GetHashTableRejectCount();

    /// <summary>SUP-B (shim 20260047). See <see cref="IFt8NativeInterop.GetH12DisplayingCount"/>.</summary>
    public int GetH12DisplayingCount() => _interop.GetH12DisplayingCount();

    /// <summary>SUP-B (shim 20260047). See <see cref="IFt8NativeInterop.GetH12AmbiguousCount"/>.</summary>
    public int GetH12AmbiguousCount() => _interop.GetH12AmbiguousCount();

    /// <summary>SUP-B (shim 20260047). See <see cref="IFt8NativeInterop.GetH12DivergentCount"/>.</summary>
    public int GetH12DivergentCount() => _interop.GetH12DivergentCount();

    /// <summary>f001-h12-unique-match-suppression (shim 20260049). See <see cref="IFt8NativeInterop.GetH12SuppressedCount"/>.</summary>
    public int GetH12SuppressedCount() => _interop.GetH12SuppressedCount();

    /// <param name="clock">Wall-clock provider for aligning cycle timestamps.</param>
    /// <param name="logger">Optional structured logger; pass null to suppress all log output.</param>
    /// <param name="grammarStore">
    /// Optional callsign shape-grammar store (<c>f-002-callsign-structure-region-lookup</c>).
    /// When <c>null</c>, <see cref="IsPlausibleMessage"/> falls back to
    /// <see cref="CallsignGrammarConfig.BuiltInDefault"/> — existing callers that do not
    /// wire this up keep today's behaviour.
    /// </param>
    /// <param name="regionStore">
    /// Optional advisory callsign region-lookup store. When <c>null</c>, every
    /// <see cref="DecodeResult.Region"/> resolves to <c>null</c> ("Unknown") — purely a GUI
    /// bycatch, never affects decode acceptance.
    /// </param>
    /// <param name="workedBeforeIndex">
    /// Optional advisory worked-before index (<c>qso-confirmation</c> capability). When
    /// <c>null</c>, every <see cref="DecodeResult.WorkedBefore"/> resolves to <c>null</c>
    /// (every checkbox unchecked) — purely a GUI bycatch, never affects decode acceptance.
    /// </param>
    public Ft8Decoder(
        IClock                  clock,
        ILogger<Ft8Decoder>?    logger            = null,
        ICallsignGrammarStore?  grammarStore      = null,
        ICallsignRegionStore?   regionStore       = null,
        IWorkedBeforeIndex?     workedBeforeIndex = null)
        : this(clock, logger, DefaultInterop, grammarStore, regionStore, workedBeforeIndex) { }

    /// <summary>
    /// Internal constructor for unit testing — allows a fake <see cref="IFt8NativeInterop"/>
    /// to be injected without loading the native DLL (accessible via
    /// <c>[assembly: InternalsVisibleTo("OpenWSFZ.Ft8.Tests")]</c>).
    /// </summary>
    internal Ft8Decoder(
        IClock                  clock,
        ILogger<Ft8Decoder>?    logger,
        IFt8NativeInterop       interop,
        ICallsignGrammarStore?  grammarStore      = null,
        ICallsignRegionStore?   regionStore       = null,
        IWorkedBeforeIndex?     workedBeforeIndex = null,
        TimeProvider?           timeProvider      = null)
    {
        _timeProvider      = timeProvider ?? TimeProvider.System;
        _clock             = clock;
        _logger            = logger;
        _interop           = interop;
        _grammarStore      = grammarStore;
        _regionStore       = regionStore;
        _workedBeforeIndex = workedBeforeIndex;
    }

    // ── IModeDecoder — backward-compatible overload ───────────────────────────
    // Infers the cycle-start timestamp from the injected clock, aligned to the
    // nearest 15-second UTC boundary.  Susceptible to a wall-clock race if the
    // calling thread is delayed past a cycle boundary; prefer the cycleStart
    // overload (supplied by CycleFramer) in production code.
    /// <inheritdoc/>
    public Task<IReadOnlyList<DecodeResult>> DecodeAsync(float[] pcm, CancellationToken ct = default)
        => DecodeAsync(pcm, AlignToCycleStart(_clock.UtcNow), currentBand: null, ct);

    // ── IModeDecoder — canonical overload (cycleStart from CycleFramer) ───────
    // Forwards to the richer currentBand-aware overload below with currentBand: null, so this
    // still satisfies IModeDecoder's exact 3-parameter signature unchanged (design.md Decision 4
    // — the new parameter is additive, not a breaking change to the interface).
    /// <inheritdoc/>
    public Task<IReadOnlyList<DecodeResult>> DecodeAsync(
        float[] pcm, DateTime cycleStart, CancellationToken ct = default)
        => DecodeAsync(pcm, cycleStart, currentBand: null, ct);

    /// <summary>
    /// Decodes one 15-second capture window, additionally threading the session's current
    /// active band into worked-before resolution (<c>qso-confirmation-band-awareness</c>
    /// design.md Decision 4). Not part of <see cref="IModeDecoder"/> — called directly on the
    /// concrete <see cref="Ft8Decoder"/> type by <c>Program.cs</c>'s decode pump, which is the
    /// one place "current band" is resolved.
    /// </summary>
    /// <param name="pcm">15 s × 12 000 Hz mono PCM samples.</param>
    /// <param name="cycleStart">UTC instant the capture window began accumulating (FR-028/R3).</param>
    /// <param name="currentBand">
    /// The session's current active band (resolved by the caller via the live-CAT-aware
    /// three-tier frequency rule, converted to a band name), or <c>null</c> when it cannot be
    /// resolved. Threaded into <see cref="IWorkedBeforeIndex.Resolve"/> so every worked-before
    /// dimension that would otherwise resolve <see cref="WorkedBeforeState.ThisBand"/> instead
    /// degrades to <see cref="WorkedBeforeState.DifferentBand"/> (if worked at all) when the
    /// current band is unresolvable.
    /// </param>
    /// <param name="ct">Cancellation token.</param>
    public Task<IReadOnlyList<DecodeResult>> DecodeAsync(
        float[]           pcm,
        DateTime          cycleStart,
        string?           currentBand,
        CancellationToken ct = default)
        => DecodeCoreAsync(pcm, cycleStart, currentBand, onFirstBatch: null, early: false, ct);

    /// <summary>
    /// decode-early-batch-panel (#122 step 4, phase 4a, design.md D3/D4): the <b>early</b> decode of a zero-filled
    /// partial window. It is <b>pass 0 only</b>: it never reads <c>_subtractionEnabled</c> and never runs
    /// <see cref="SubtractionPass"/> (so it costs about what the full single-pass decode costs, not the residual
    /// pass on top), and it writes no instance state. The native call is bracketed, inside the same
    /// <see cref="Task.Run(Func{TResult})"/> lambda as <c>DecodeAll</c>, by a save and (in a <c>finally</c>) a restore
    /// of the process-global decode state (<c>ft8_hash_state_*</c>), so a decode that adds callsigns or moves the
    /// counters leaves nothing behind that could change the FINAL decode of the same window (R4). The caller must
    /// hold the decode gate: no other decode may run between the save and the restore.
    /// The per-cycle Information log lines of an ordinary decode are NOT written (they would duplicate the
    /// <c>Cycle</c> lines that log parsers read); the early service writes its own line.
    /// </summary>
    /// <param name="pcm">15 s x 12 000 Hz mono PCM, the first part real, the tail zero.</param>
    /// <param name="cycleStart">UTC instant the window began accumulating.</param>
    /// <param name="currentBand">The session current band, or <c>null</c>.</param>
    /// <param name="ct">Cancellation token.</param>
    public Task<IReadOnlyList<DecodeResult>> DecodeEarlyAsync(
        float[]           pcm,
        DateTime          cycleStart,
        string?           currentBand,
        CancellationToken ct = default)
        => DecodeCoreAsync(pcm, cycleStart, currentBand, onFirstBatch: null, early: true, ct);

    /// <summary>
    /// Whether the residual-decode pass (<c>decoder.subtractionEnabled</c>) is currently on. The daemon pump reads
    /// it once per window to choose between <see cref="DecodeAsync(float[],DateTime,string?,CancellationToken)"/>
    /// (one batch, exactly as before) and <see cref="DecodeTwoStageAsync"/>.
    /// </summary>
    public bool SubtractionEnabled => _subtractionEnabled;

    /// <summary>
    /// sub-feas-speed-redesign two-stage publish (design.md D9). Decodes one window and hands the caller the cycle's
    /// decodes in <b>two batches</b> when the residual pass is on:
    /// <list type="number">
    ///   <item><b>Batch 1</b> = pass-0, delivered through <paramref name="publishFirstBatch"/> as soon as pass 0 has
    ///   returned and been mapped, <i>before</i> the residual pass starts;</item>
    ///   <item><b>Batch 2</b> = the residual pass's genuinely new decodes, mapped exactly like batch 1 (the text
    ///   de-duplication set is per cycle and spans both batches) and <b>returned</b>. It is empty when the pass is
    ///   abandoned, fails, or finds nothing new: an empty return means "publish nothing".</item>
    /// </list>
    /// <para>
    /// With the flag OFF (or nothing decoded, or a skipped silent cycle) this is the ordinary single-batch decode:
    /// <paramref name="publishFirstBatch"/> is called exactly once with what
    /// <see cref="DecodeAsync(float[],DateTime,string?,CancellationToken)"/> would have returned, and the return value
    /// is empty. <paramref name="publishFirstBatch"/> is called <b>exactly once, always</b> (an empty batch 1 is a
    /// real cycle: the answerer, caller and ALL.TXT count it).
    /// </para>
    /// <para>
    /// Callable from a test or replay harness with no daemon pump (a lambda that records the batch is enough).
    /// <see cref="IModeDecoder.DecodeAsync"/> is unchanged; this is an additional entry on the concrete type.
    /// </para>
    /// </summary>
    /// <param name="pcm">15 s x 12 000 Hz mono PCM samples.</param>
    /// <param name="cycleStart">UTC instant the capture window began accumulating.</param>
    /// <param name="currentBand">The session's current band, or <c>null</c>.</param>
    /// <param name="publishFirstBatch">Publishes batch 1. Awaited before the residual pass begins.</param>
    /// <param name="ct">Cancellation token.</param>
    /// <returns>Batch 2 (may be empty).</returns>
    public async Task<IReadOnlyList<DecodeResult>> DecodeTwoStageAsync(
        float[]                                   pcm,
        DateTime                                  cycleStart,
        string?                                   currentBand,
        Func<IReadOnlyList<DecodeResult>, Task>   publishFirstBatch,
        CancellationToken                         ct = default)
    {
        ArgumentNullException.ThrowIfNull(publishFirstBatch);

        bool published = false;
        async Task MarkAndPublish(IReadOnlyList<DecodeResult> batch1)
        {
            published = true;
            await publishFirstBatch(batch1).ConfigureAwait(false);
        }

        var second = await DecodeCoreAsync(pcm, cycleStart, currentBand, MarkAndPublish, early: false, ct).ConfigureAwait(false);

        if (!published)
        {
            // Single-batch outcome (flag OFF, silent cycle, native AV, ...): what the core returned IS the cycle.
            await publishFirstBatch(second).ConfigureAwait(false);
            return [];
        }
        return second;
    }

    /// <summary>
    /// third-pass-deep (#240, step 1): the staged decode with <b>every batch delivered through a callback</b>, so the
    /// residual pass's batch 2 can leave BEFORE the optional third pass starts. Batches:
    /// <list type="number">
    ///   <item><b>1</b> = pass 0, delivered exactly once, always (an empty batch 1 is a real cycle), as in <see cref="DecodeTwoStageAsync"/>;</item>
    ///   <item><b>2</b> = the residual pass's new decodes, delivered only when non-empty, mapped exactly like batch 1;</item>
    ///   <item><b>3</b> = the third pass's new decodes (decoding depth <see cref="DecodingDepth.Deep"/> only), delivered
    ///   only when non-empty, mapped exactly like batch 2 with the same per-cycle text de-duplication set;</item>
    ///   <item><b>4</b> (step 4) = the coherent fallback's own batch with <c>decoder.coherentFallbackEnabled</c> ON: batch 4 on Deep, batch 3 on
    ///   Normal (where there is no third pass), delivered only when non-empty and after every ordinary batch.</item>
    /// </list>
    /// With the depth <see cref="DecodingDepth.Normal"/> this delivers exactly what <see cref="DecodeTwoStageAsync"/>
    /// would (batch 1, then batch 2), and the third pass code is not reached. The third pass is all-or-nothing: if it
    /// is abandoned on the cycle budget or fails, nothing is delivered for batch 3 and batches 1 and 2 stand.
    /// </summary>
    /// <param name="pcm">15 s x 12 000 Hz mono PCM samples.</param>
    /// <param name="cycleStart">UTC instant the capture window began accumulating.</param>
    /// <param name="currentBand">The session's current band, or <c>null</c>.</param>
    /// <param name="publishBatch">Called with the batch number (1, 2, 3 or 4) and the batch. Awaited before the next stage begins.</param>
    /// <param name="ct">Cancellation token.</param>
    public async Task DecodeStagedAsync(
        float[]                                              pcm,
        DateTime                                             cycleStart,
        string?                                              currentBand,
        Func<int, IReadOnlyList<DecodeResult>, Task>         publishBatch,
        CancellationToken                                    ct = default)
    {
        ArgumentNullException.ThrowIfNull(publishBatch);

        bool published = false;
        async Task MarkAndPublish(IReadOnlyList<DecodeResult> batch1)
        {
            published = true;
            await publishBatch(1, batch1).ConfigureAwait(false);
        }

        var rest = await DecodeCoreAsync(
            pcm, cycleStart, currentBand, MarkAndPublish, early: false, ct,
            onSecondBatch: batch2 => publishBatch(2, batch2),
            onThirdBatch:  batch3 => publishBatch(3, batch3),
            onFallbackBatch: (number, batchF) => publishBatch(number, batchF)).ConfigureAwait(false);

        if (!published)
        {
            // Single-batch outcome (flag OFF, silent cycle, native AV, ...): what the core returned IS the cycle.
            await publishBatch(1, rest).ConfigureAwait(false);
            return;
        }
        // Two-stage with no staged callbacks consumed (Normal): the return value is batch 2.
        if (rest.Count > 0) await publishBatch(2, rest).ConfigureAwait(false);
    }

    /// <summary>
    /// The decode itself. <paramref name="onFirstBatch"/> <c>null</c> = the single-batch behaviour of
    /// <see cref="DecodeAsync(float[],DateTime,string?,CancellationToken)"/> (with the flag ON the residual pass runs
    /// inside this call and its decodes are appended to the one returned list). Non-null AND the flag ON = two-stage
    /// (see <see cref="DecodeTwoStageAsync"/>): batch 1 goes to the callback, the return value is batch 2.
    /// </summary>
    private async Task<IReadOnlyList<DecodeResult>> DecodeCoreAsync(
        float[]                                    pcm,
        DateTime                                   cycleStart,
        string?                                    currentBand,
        Func<IReadOnlyList<DecodeResult>, Task>?   onFirstBatch,
        bool                                       early,
        CancellationToken                          ct,
        Func<IReadOnlyList<DecodeResult>, Task>?   onSecondBatch = null,
        Func<IReadOnlyList<DecodeResult>, Task>?   onThirdBatch  = null,
        Func<int, IReadOnlyList<DecodeResult>, Task>? onFallbackBatch = null)
    {
        // The flag is read ONCE per cycle. Two-stage only when the caller asked for it AND the flag is on: with the
        // flag off this method is, statement for statement, the pre-change single-batch path (P-9).
        // The EARLY entry (decode-early-batch-panel D3) never reads the flag: it is pass 0 only, whatever the flag says.
        bool subtractionOn = !early && _subtractionEnabled;
        bool twoStage      = onFirstBatch is not null && subtractionOn;
        // COH-FALLBACK Stage 2 (R10): read ONCE per cycle, like the two flags above. Only a staged cycle can carry it (its output goes in
        // a batch of its own, after the last ordinary one), the early decode never does (R9), and OFF means no native call that was not there
        // before (R13).
        // Step 4 (R6-triple-prime): the fallback's own batch needs the staged callbacks (second, third and the fallback's own): DecodeTwoStageAsync
        // supplies none, so on that entry the flag has no effect.
        bool cohOn         = twoStage && _coherentFallbackEnabled
                             && onSecondBatch is not null && onThirdBatch is not null && onFallbackBatch is not null;
        // COH-MULTISET: read ONCE per cycle too, and only meaningful while the fallback itself runs.
        bool multiSetOn    = cohOn && _coherentFallbackMultiSet;
        // COH-FB-AUDIO: read ONCE per cycle too.
        var  audioMode     = _coherentFallbackAudio;

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
            if (early)
                _logger?.LogDebug("Early decode skipped — RMS {Rms:E3} is below silence guard.", rms);
            else
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
        var sw = BudgetClock.StartNew(_timeProvider);

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
        byte[]?           cohSnapshot = null;

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
            (native, passCounts, candidateCounts, noiseFloorDb, llrStats, cohSnapshot) = await Task.Run(() =>
            {
                // decode-early-batch-panel R4 (design.md D4): the EARLY decode saves the process-global decode state
                // before the native call and restores it in a finally, in THIS lambda (the native TLS is per-thread, and
                // the bracket must cover exactly the native call). The ordinary decode does neither: its path is unchanged.
                // The save is outside the try: if it throws there is no valid image, so nothing is restored.
                byte[]? stateImage = null;
                if (early)
                {
                    stateImage = RentStateImage();
                    _interop.HashStateSave(stateImage);
                }
                try
                {
                    // AP decode constraints (H6, D-001): must be set on the same thread as DecodeAll.
                    // Snapshot to avoid tearing — _apConstraints is volatile but is a reference type.
                    // The early lambda sets them exactly as the final decode does (they are thread-local and
                    // ft8_decode_all does not reset them; the early decode may run on a different pool thread).
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
                    // COH-FALLBACK Stage 2: the fallback's candidate list and decoded payloads are thread-local to THIS thread and are
                    // reset by the next ft8_decode_all call on it, so they are copied out here, right after the call, for the fallback to
                    // read on another thread. Flag OFF: not called.
                    var cs = cohOn ? _interop.CohFallbackSnapshot() : null;
                    return (r, p, c, n, l, cs);
                }
                finally
                {
                    if (stateImage is not null)
                    {
                        _interop.HashStateRestore(stateImage);
                        ReturnStateImage(stateImage);
                    }
                }
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

        // ── sub-feas-native-subtraction: additive residual-decode pass ──────
        // Flag OFF (default): native is untouched -- byte-identical to pre-change behaviour
        // (spec's own "Flag OFF leaves decode output unchanged" scenario). Flag ON: fits and
        // subtracts every re-encodable pass-0 signal, decodes the residual, and appends only
        // the genuinely new (payload-deduped) decodes to native BEFORE the existing per-
        // message mapping loop below runs -- so pass-0 and residual-pass results go through
        // the identical plausibility-filter/text-dedup/region/worked-before pipeline, no
        // duplicated logic (design.md's own intent for this two-call shape). Included inside
        // the same `sw` timing window as pass-0 so the existing per-cycle "elapsed" log line
        // (below) already captures total cost with the flag on -- exactly the number tasks.md
        // 8.1's runtime gate needs, with no separate instrumentation required.
        // SubtractionPass contains EVERY non-cancellation failure internally (returns empty +
        // logs a warning) per design.md Decision 4, so pass-0's results are never lost here.
        // It also receives the AP constraints (native AP state is thread-local) and a wall-clock
        // budget = whatever remains of the cycle budget after pass-0.
        if (!twoStage && subtractionOn && native.Length > 0)
        {
            var newFromResidual = await SubtractionPass.RunAsync(
                _interop, normalisedPcm, native, EffectiveSubtractionThreads, _logger,
                _apConstraints, SubtractionCycleBudget - sw.Elapsed, ct);
            if (newFromResidual.Length > 0)
            {
                var combined = new Ft8NativeResult[native.Length + newFromResidual.Length];
                native.CopyTo(combined, 0);
                newFromResidual.CopyTo(combined, native.Length);
                native = combined;
            }
        }

        // Two-stage: the stopwatch keeps running, because the residual pass's wall-clock budget is measured from the
        // start of this decode; the per-cycle "elapsed" line below then reports the time to BATCH 1 (design.md D9).
        if (!twoStage) sw.Stop();

        // ── Map native results → DecodeResult ────────────────────────────────
        // The text de-duplication set is per CYCLE: in two-stage mode batch 2 is mapped with the SAME set, so a
        // residual decode whose text already appeared in batch 1 is not published twice.
        var seen    = new HashSet<string>(StringComparer.Ordinal);

        List<DecodeResult> MapNative(Ft8NativeResult[] source, int path = PathOrdinary)
        {
        var mapped = new List<DecodeResult>(source.Length);

        foreach (ref readonly Ft8NativeResult nr in source.AsSpan())
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
            if (!IsPlausibleMessage(msg, _grammarStore))
            {
                _logger?.LogDebug(
                    "Cycle {Time}: filtered implausible message '{Message}' (false-positive guard).",
                    timeStr, msg);
                continue;
            }

            // ── Region bycatch (advisory only, region-lookup capability) ─────
            // Best-effort: any failure here degrades to Region = null ("Unknown") and
            // never withholds or alters the decode itself.
            RegionInfo? region = null;
            if (_regionStore is not null)
            {
                try
                {
                    var primaryToken = ExtractPrimaryCallsignToken(msg);
                    if (primaryToken is not null)
                        region = _regionStore.TryGetRegion(primaryToken);
                }
                catch (Exception ex)
                {
                    _logger?.LogWarning(ex,
                        "Cycle {Time}: region resolution failed for message '{Message}' — " +
                        "defaulting to Unknown.", timeStr, msg);
                    region = null;
                }
            }

            // ── Worked-before bycatch (advisory only, qso-confirmation capability) ───
            // Best-effort: any failure here degrades to WorkedBefore = null (every
            // checkbox unchecked) and never withholds or alters the decode itself.
            WorkedBeforeInfo? workedBefore = null;
            if (_workedBeforeIndex is not null)
            {
                try
                {
                    var primaryToken = ExtractPrimaryCallsignToken(msg);
                    if (primaryToken is not null)
                        workedBefore = _workedBeforeIndex.Resolve(primaryToken, currentBand);
                }
                catch (Exception ex)
                {
                    _logger?.LogWarning(ex,
                        "Cycle {Time}: worked-before resolution failed for message '{Message}' — " +
                        "defaulting to not-worked-before.", timeStr, msg);
                    workedBefore = null;
                }
            }

            mapped.Add(new DecodeResult(
                Time:         timeStr,
                Snr:          nr.Snr,
                Dt:           Math.Round(nr.Dt, 1),
                FreqHz:       nr.FreqHz,
                Message:      msg,
                Region:       region,
                WorkedBefore: workedBefore,
                Band:         currentBand)
            {
                Path = path   // R11 provenance tag (COH-FALLBACK Stage 2); not serialised, not in any output format
            });
        }

        return mapped;
        }

        var results = MapNative(native);

        // ── Per-pass iterative subtraction log (AC-IS-4) ────────────────────
        // Loop over passCounts.Length so the log scales correctly with K_MAX_PASSES
        // without needing further code changes when the pass count changes.
        // M3 (sub-feas-speed-redesign): guarded, so with Debug logging off no loop runs and no message is formatted.
        bool debugLogging = _logger?.IsEnabled(LogLevel.Debug) == true;
        if (debugLogging)
        {
            for (int p = 0; p < passCounts.Length; p++)
            {
                int candidates = p < candidateCounts.Length ? candidateCounts[p] : -1;
                _logger!.LogDebug(
                    "Iterative subtraction: pass {Pass} of {Max}, {Candidates} candidates found, {K} decoded.",
                    p + 1, passCounts.Length, candidates, passCounts[p]);
            }
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
        if (debugLogging)
        {
            for (int p = 0; p < llrStats.LlrMeanAbs.Length; p++)
            {
                _logger!.LogDebug(
                    "Iterative subtraction: pass {Pass} LDPC fail stats — " +
                    "failCands={FailCount} meanAbsLLR={MeanAbs:F3} prenormVar={PrenormVar:F4}",
                    p + 1, llrStats.LlrFailCount[p], llrStats.LlrMeanAbs[p], llrStats.LlrPrenormVariance[p]);
            }
        }

        // The early decode returns here, BEFORE the per-cycle Information lines below: they would duplicate the
        // "Cycle {Time}: ... decode(s) found" line that log parsers read, and the cumulative counters they print are
        // the final decode to report. The early service writes its own one line (design.md D8).
        if (early) return results;

        // ── Diagnostic log ───────────────────────────────────────────────────
        // Spec requirement: "Cycle {Time}: {Count} decode(s) found, elapsed={Elapsed} ms"
        _logger?.LogInformation(
            "Cycle {Time}: {Count} decode(s) found, elapsed={Elapsed} ms.",
            timeStr, results.Count, sw.ElapsedMilliseconds);

        // ── tasks.md 8.4 (fix-cycle-boundary-clock-drift): systematic hashTableRejectCount
        // logging at a regular (once-per-cycle) cadence ──────────────────────────────────
        // Prior to this, hashTableRejectCount (see GetHashTableRejectCount's doc comment) was
        // only observable via ad hoc GET /api/v1/status polling — a live endurance run
        // (dev-tasks/2026-07-24-cycleframer-correction-not-converging-live-evidence.md, Evidence
        // 5) sampled it informally that way to check whether it grows alongside the session's
        // non-converging cycle-boundary drift, but the resulting reading couldn't be reconciled
        // against the raw daemon log after the fact — unlike decode elapsed time immediately
        // above, which the same investigation confirmed IS already logged every cycle and could
        // be reconciled that way. Logging it here, at the same per-cycle cadence and Information
        // level as the elapsed-time line above, closes that gap for future live runs without
        // needing ad hoc endpoint polling during the session. This is process-lifetime
        // cumulative (GetHashTableRejectCount's own contract), not a per-cycle delta — logging it
        // every cycle still lets a raw-log analysis compute cycle-over-cycle deltas or a
        // whole-session trend, same as the elapsed-time reconciliation already does.
        _logger?.LogInformation(
            "Cycle {Time}: hashTableRejectCount={HashTableRejectCount} (process-lifetime cumulative).",
            timeStr, _interop.GetHashTableRejectCount());

        // ── SUP-B (shim 20260047) + f001-h12-unique-match-suppression (shim 20260049):
        // 12-bit-path unique-match sizing AND the suppression it now sizes ─────────
        // Per-cycle CUMULATIVE (not a delta), matching hashTableRejectCount's own
        // convention immediately above and spec Sec.3.3's rationale: this gives S
        // as a function of elapsed session time, which is the product question
        // being answered, and lets a raw daemon log reconstruct the S-over-time
        // curve spec Sec.6.2 needs without ad hoc endpoint polling. h12Suppressed is
        // arithmetically identical to h12Ambiguous by design (see the native getter's
        // own doc comment) -- it is a live wiring-invariant check, not new information.
        _logger?.LogInformation(
            "Cycle {Time}: h12Displaying={H12Displaying} h12Ambiguous={H12Ambiguous} " +
            "h12Divergent={H12Divergent} h12Suppressed={H12Suppressed} (process-lifetime cumulative).",
            timeStr, _interop.GetH12DisplayingCount(), _interop.GetH12AmbiguousCount(),
            _interop.GetH12DivergentCount(), _interop.GetH12SuppressedCount());

        // ── D-003 noise-floor diagnostic ─────────────────────────────────────
        // Log the histogram-median noise floor returned by ft8_get_last_noise_floor_db.
        // If D-003 (intermittent ~15 dB SNR under-report) is caused by a noise-floor
        // estimator anomaly, affected cycles will show this value ~15 dB above its
        // neighbours.  Logged at Information so it appears without adjusting log levels.
        _logger?.LogInformation(
            "Cycle {Time}: noise_floor={NoiseFloor:F1} dB (waterfall histogram median).",
            timeStr, noiseFloorDb);

        // coh-fb-residual: what the fallback may read instead of the original audio (set inside the staged path below).
        bool deepForFallback = false;
        SubtractionPass.ResidualPassReport? reportForFallback = null;
        SubtractionPass.ThirdPassResult? thirdResult = null;

        if (twoStage)
        {
            // Batch 1 leaves NOW, through the caller's publish path, before any residual work starts. Nothing else
            // sits between "pass 0 returned and was mapped" and this hand-off (the logs above are cheap and
            // Debug-guarded), because acceptance row S2 times exactly that gap.
            await onFirstBatch!(results).ConfigureAwait(false);

            // third-pass-deep: the depth is read ONCE per cycle, and only a staged caller (one that supplied both
            // callbacks) can receive batch 3. Otherwise this is, statement for statement, the two-stage path as it was.
            bool deep = onSecondBatch is not null && onThirdBatch is not null && DecodingDepth == DecodingDepth.Deep;
            deepForFallback = deep;

            // COH-FALLBACK step 4 (R6''', R7'''): the fallback does NOT run during pass 0's follow-on work. With the flag ON it starts only
            // after the cycle's LAST ordinary batch has been handed off (batch 3 on Deep, after the third pass whether or not batch 3 had
            // decodes; batch 2 on Normal; batch 1 when pass 0 decoded nothing and there is no residual pass), runs on up to
            // EffectiveSubtractionThreads worker threads (R15) with nothing else left to run, and publishes as a batch of its own after
            // every ordinary batch: batch 4 on Deep, batch 3 on Normal, only if non-empty. OFF: fallbackBatchNumber is unused and every
            // branch below is the code as it was.
            bool fallbackReady = cohOn && cohSnapshot is not null;
            int  fallbackBatchNumber = deep ? FallbackBatchDeep : FallbackBatchNormal;

            if (native.Length == 0)
            {
                // Nothing decoded in pass 0: there is no residual pass or third pass, so batch 1 was the last ordinary batch.
                if (fallbackReady) await RunCoherentFallbackBatchAsync(fallbackBatchNumber).ConfigureAwait(false);
                return [];
            }

            var report = deep ? new SubtractionPass.ResidualPassReport() : null;
            reportForFallback = report;

            // The residual pass, after batch 1 is out. Its wall-clock budget is what remains of the cycle budget,
            // measured from the start of this decode (the callback's own time counts: it is part of the cycle).
            var newFromResidual = await SubtractionPass.RunAsync(
                _interop, normalisedPcm, native, EffectiveSubtractionThreads, _logger,
                _apConstraints, SubtractionCycleBudget - sw.Elapsed, ct, report);

            // Batch 2: nothing when the pass was abandoned, failed, or found nothing new.
            var second = newFromResidual.Length == 0 ? [] : MapNative(newFromResidual, PathResidual);
            if (!deep)
            {
                // Normal: batch 2 is returned (unchanged) unless the fallback is on, in which case batch 2 leaves through its callback and
                // the fallback follows as batch 3.
                if (!fallbackReady) return second;
                if (second.Count > 0) await onSecondBatch!(second).ConfigureAwait(false);
                await RunCoherentFallbackBatchAsync(fallbackBatchNumber).ConfigureAwait(false);
                return [];
            }

            // ── Deep: batch 2 leaves NOW (before the third pass starts), then the third pass ───────────────────
            if (second.Count > 0) await onSecondBatch!(second).ConfigureAwait(false);

            // Batch 3: the third pass's new decodes (mapped exactly like batch 2, same per-cycle text de-duplication set).
            // Delivered only if non-empty.
            var batch3 = await ThirdPassBatchAsync().ConfigureAwait(false);
            if (batch3.Count > 0)
            {
                Interlocked.Add(ref _thirdPassDecodes, batch3.Count);
                await onThirdBatch!(batch3).ConfigureAwait(false);
            }

            // The last ordinary batch is out (or there was none): only now does the fallback start.
            if (fallbackReady) await RunCoherentFallbackBatchAsync(fallbackBatchNumber).ConfigureAwait(false);
            return [];

            async Task<List<DecodeResult>> ThirdPassBatchAsync()
            {
                // Skip rules (spec section 1 step 1): run only when the residual pass returned >= 1 new decode and was not
                // abandoned. Anything else would only repeat the residual pass on an unchanged buffer.
                if (report!.DeadlineAbandoned || report.ContainedException)
                {
                    Interlocked.Increment(ref _thirdPassSkippedAbandoned);
                    SubtractionPass.LogThirdPass(_logger, 0, 0, SubtractionPass.ThirdPassOutcome.SkippedAbandoned, 0);
                    return [];
                }
                if (newFromResidual.Length == 0 || report.Residual is null)
                {
                    Interlocked.Increment(ref _thirdPassSkippedNoNew);
                    SubtractionPass.LogThirdPass(_logger, 0, 0, SubtractionPass.ThirdPassOutcome.SkippedNoNew, 0);
                    return [];
                }

                // Same budget, same cancellation/reserve mechanism: what remains of the 13 s measured from the start of this decode.
                var third = await SubtractionPass.RunThirdPassAsync(
                    _interop, report.Residual, newFromResidual, native, EffectiveSubtractionThreads, _logger,
                    _apConstraints, SubtractionCycleBudget - sw.Elapsed, ct);
                thirdResult = third;

                switch (third.Outcome)
                {
                    case SubtractionPass.ThirdPassOutcome.SkippedNoNew:
                        Interlocked.Increment(ref _thirdPassSkippedNoNew);   // nothing re-encodable: never started a fit
                        return [];
                    case SubtractionPass.ThirdPassOutcome.Abandoned:
                        Interlocked.Increment(ref _thirdPassRuns);
                        Interlocked.Increment(ref _thirdPassAbandoned);
                        return [];
                    case SubtractionPass.ThirdPassOutcome.Failed:
                        Interlocked.Increment(ref _thirdPassRuns);
                        Interlocked.Increment(ref _thirdPassFailed);
                        return [];
                }

                Interlocked.Increment(ref _thirdPassRuns);
                if (third.NewResults.Length == 0) return [];

                return MapNative(third.NewResults, PathResidual);
            }
        }

        return results;

        // ── COH-FALLBACK step 4 ──────────────────────────────────────────────────────────────────────────────────────
        // The fallback's batch: run the native cycle on worker threads (R15), choose what to publish (R6''), turn each payload into text
        // through the ordinary message decode (the fallback's only hash-table access, R9: every other native decode of this cycle has
        // finished, since the fallback starts after the last ordinary batch, and the pump holds the decode gate), map them like any other
        // decode (R6': the same per-cycle text de-duplication, plausibility filter and region/worked-before bycatch), hand the batch to
        // the caller as batch <paramref name="batchNumber"/> if it is non-empty, and write the R12' log line (one per cycle).
        async Task RunCoherentFallbackBatchAsync(int batchNumber)
        {
            var fbStart = sw.Elapsed;
            // COH-FB-AUDIO: which audio the fallback reads. Original => normalisedPcm itself (the same reference as before).
            // The chosen arrays are read-only to the fallback's worker threads; nothing mutates or pools them (the third pass ran to completion
            // before this point, and the residual pass's array is the pass's own, never returned to a pool).
            var choice = CohFallbackAudioSelector.Select(audioMode, normalisedPcm, deepForFallback, reportForFallback, thirdResult);
            // The shared 13 s budget (R7'''): what is left of it when the fallback starts, less the reserve for the work after the native run.
            double budgetMs = Math.Max(0.0, (SubtractionCycleBudget - fbStart - CoherentFallbackPublishReserve).TotalMilliseconds);
            int workers = EffectiveSubtractionThreads;
            CohFallbackAudioSelector.Merged? merged = null;
            CohFallbackRunResult? outcome;
            if (audioMode != CoherentFallbackAudio.Both)
            {
                outcome = await Task.Run(
                    () => RunCoherentFallback(choice.Pcm, cohSnapshot!, budgetMs, workers, multiSetOn, timeStr, ct), CancellationToken.None).ConfigureAwait(false);
            }
            else
            {
                // Both: SEQUENTIAL, residual first (the run that matters if the budget is short), then the original audio on what is left of the ONE shared
                // budget. Sequential because each run already uses `workers` threads (parallel would double the thread count for no wall-time that the
                // 13 s budget needs) and because a deadline between the runs is then a plain, countable event. If nothing is left for the second run it is not
                // started and its eligible candidates are counted abandoned. With no usable residual buffer the original audio is run ONCE, never twice.
                CohFallbackRunResult? first = await Task.Run(
                    () => RunCoherentFallback(choice.Pcm, cohSnapshot!, budgetMs, workers, multiSetOn, timeStr, ct), CancellationToken.None).ConfigureAwait(false);
                CohFallbackRunResult? second = null;
                if (choice.IsResidual && first is not null)
                {
                    double leftMs = budgetMs - (sw.Elapsed - fbStart).TotalMilliseconds;
                    second = leftMs > 0.0
                        ? await Task.Run(() => RunCoherentFallback(normalisedPcm, cohSnapshot!, leftMs, workers, multiSetOn, timeStr, ct), CancellationToken.None).ConfigureAwait(false)
                        : new CohFallbackRunResult(CohFallbackAudioSelector.NotRun(first.Stats), []) { Workers = first.Workers };
                }

                var residualRun = choice.IsResidual ? first : null;
                var originalRun = choice.IsResidual ? second : first;
                merged = CohFallbackAudioSelector.Merge(originalRun?.Rows, residualRun?.Rows);
                outcome = (originalRun, residualRun) switch
                {
                    (null, null) => null,
                    (not null, null) => originalRun,
                    (null, not null) => residualRun,
                    _ => new CohFallbackRunResult(
                             CohFallbackAudioSelector.CombineStats(originalRun!.Stats, residualRun!.Stats),
                             residualRun.Rows.Concat(originalRun.Rows).ToList())
                         { Workers = Math.Max(originalRun.Workers, residualRun.Workers) },
                };
            }
            double fbWallMs = (sw.Elapsed - fbStart).TotalMilliseconds;
            if (outcome is null) return;   // failed: already logged, nothing published

            var picked = CoherentFallbackSelector.Select(merged?.Rows ?? outcome.Rows);
            var natives = new List<Ft8NativeResult>(picked.Count);
            var edgeByText = new Dictionary<string, bool>(StringComparer.Ordinal);
            foreach (var row in picked)
            {
                string? text;
                try { text = _interop.CohFallbackUnpack(row.Payload); }
                catch (NativeAccessViolationException)
                {
                    _logger?.LogWarning("Cycle {Time}: coherent fallback text unpack caught a native access violation — that decode skipped.", timeStr);
                    continue;
                }
                if (string.IsNullOrWhiteSpace(text)) continue;
                natives.Add(new Ft8NativeResult { FreqHz = (int)Math.Round(row.OutFreqHz), Dt = row.OutDtS, Snr = row.SnrDb, Message = text });
                edgeByText[text.TrimEnd()] = row.Edge;
            }

            var batch = MapNative(natives.ToArray(), PathFallback);
            int publishedEdge = batch.Count(d => edgeByText.TryGetValue(d.Message, out bool edge) && edge);

            // Hand-off: the publish time is read immediately before the caller's callback is called, from the decode's own start (the
            // same clock as batch 1's hand-off). -1 with batch4Published=0 when there is no fallback batch: never average the -1.
            double publishMs = -1.0;
            bool batchPublished = batch.Count > 0;
            var st = outcome.Stats;
            try
            {
                if (batchPublished)
                {
                    publishMs = sw.Elapsed.TotalMilliseconds;
                    await onFallbackBatch!(batchNumber, batch).ConfigureAwait(false);
                }
            }
            finally
            {
                // The R12' line is written even when the caller's publish throws (batch4Published=1: the hand-off was attempted).
                _logger?.LogInformation(
                    "Coherent fallback: eligible={Eligible}, attempted={Attempted}, crcOk={CrcOk}, f1bComputed={F1bComputed}, gated={Gated}, " +
                    "published={Published}, abandoned={Abandoned}, elapsedMs={ElapsedMs:F0}, publishedEdge={PublishedEdge}, path={Path}, " +
                    "workers={Workers}, fbStartMs={FbStartMs:F0}, fbWallMs={FbWallMs:F0}, batch={Batch}, batch4Published={BatchPublished}, batch4PublishMs={BatchPublishMs:F0}, " +
                    "sets={Sets}, walkEntered={WalkEntered}, crcC1={CrcC1}, crcJ2={CrcJ2}, crcJ3={CrcJ3}, crcN1={CrcN1}, audio={Audio}{BothCounts}.",
                    st.Eligible, st.Attempted, st.CrcOk, st.F1bComputed, st.Gated, batch.Count, st.Abandoned, st.TotalMs, publishedEdge, PathFallback,
                    outcome.Workers, fbStart.TotalMilliseconds, fbWallMs, batchNumber, batchPublished ? 1 : 0, publishMs,
                    multiSetOn ? "on" : "off", st.WalkEntered, outcome.CrcValidBySet(1), outcome.CrcValidBySet(2), outcome.CrcValidBySet(3), outcome.CrcValidBySet(4),
                    CohFallbackAudioSelector.Label(audioMode, choice.Level),
                    merged is null ? "" : $", fromOriginal={merged.FromOriginal}, fromResidual={merged.FromResidual}, inBoth={merged.InBoth}");
            }
        }
    }

    /// <summary>COH-FALLBACK step 4: the number of the fallback's own batch on <see cref="DecodingDepth.Deep"/> (after batches 1, 2 and 3).</summary>
    internal const int FallbackBatchDeep = 4;

    /// <summary>COH-FALLBACK step 4: the number of the fallback's own batch on <see cref="DecodingDepth.Normal"/> (after batches 1 and 2).</summary>
    internal const int FallbackBatchNormal = 3;

    /// <summary>R11 provenance tag of a decode the ordinary pass 0 / pass 1 produced.</summary>
    internal const int PathOrdinary = 0;

    /// <summary>R11 provenance tag of a decode the residual pass or the third pass produced.</summary>
    internal const int PathResidual = 1;

    /// <summary>R11 provenance tag of a decode the coherent-extraction fallback produced.</summary>
    internal const int PathFallback = 2;

    /// <summary>
    /// COH-FALLBACK Stage 2: the native fallback run on a thread of its own. Contains every failure: a fault is logged and the cycle
    /// simply has no fallback decodes (batches 1, 2 and 3 as they would have been), never lost.
    /// </summary>
    private CohFallbackRunResult? RunCoherentFallback(float[] pcm, byte[] snapshot, double budgetMs, int workers, bool multiSet, string timeStr, CancellationToken ct)
    {
        try
        {
            return _interop.CohFallbackRun(pcm, snapshot, budgetMs, workers, multiSet, ct);
        }
        catch (Exception ex)
        {
            _logger?.LogWarning(ex, "Cycle {Time}: coherent fallback failed — no fallback decodes this cycle.", timeStr);
            return null;
        }
    }

    // ── Early-decode state image (decode-early-batch-panel D4) ────────────────

    /// <summary>
    /// The reusable heap buffer for the native state image (about 150 KB: large-object heap, so reused, never a stack).
    /// Rented with <see cref="Interlocked.Exchange{T}(ref T, T)"/>, so two overlapping early decodes (which the daemon
    /// decode gate forbids) could not share one buffer.
    /// </summary>
    private byte[]? _stateImage;

    private byte[] RentStateImage()
    {
        int size = _interop.HashStateSize();
        var buf  = Interlocked.Exchange(ref _stateImage, null);
        return buf is not null && buf.Length == size ? buf : new byte[size];
    }

    private void ReturnStateImage(byte[] buf) => Volatile.Write(ref _stateImage, buf);

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
    /// D9-R3 — callsign shape grammar (<c>f-002-callsign-structure-region-lookup</c>):
    /// replaces the earlier length-only oversized-callsign guard with an ITU Radio
    /// Regulations Article 19 §19.68–19.69-derived structural check — see
    /// <see cref="IsCallsignShapeInvalid"/> for the full rule. Any callsign-position
    /// token whose shape or total length is invalid was not produced by valid callsign
    /// packing (Type 1) nor by a valid Type 4 literal-text field, and is therefore a
    /// false-positive OSD candidate.
    /// </para>
    /// <para>
    /// D9-R4 (existing) — Maidenhead grid / report validation on 3-token Standard QSO
    /// messages: grid letters must be in [A–R]; dB reports must match known-valid forms.
    /// All other message forms are accepted unconditionally.
    /// </para>
    /// <para>
    /// #226/#227/#228 (acceptance-only): a <c>PREFIX/CALL</c> token is shape-valid when its right
    /// half is the base callsign; <c>CQ &lt;modifier&gt; &lt;call&gt;</c> (1–4 letters or 3 digits,
    /// no grid) is plausible; <c>CALL CALL R GRID</c> is plausible.
    /// </para>
    /// </remarks>
    /// <param name="text">The candidate decode text.</param>
    /// <param name="grammarStore">
    /// Optional callsign shape-grammar store; falls back to
    /// <see cref="CallsignGrammarConfig.BuiltInDefault"/> when <c>null</c> (existing
    /// call sites that predate <c>f-002-callsign-structure-region-lookup</c> keep
    /// today's behaviour unchanged).
    /// </param>
    internal static bool IsPlausibleMessage(string? text, ICallsignGrammarStore? grammarStore = null)
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
                // IsCallsignShapeInvalid already exempts hash references (<...) and short keywords.
                string token0 = text[..firstSpace];
                string token1 = text[(firstSpace + 1)..];
                if (IsCallsignShapeInvalid(token0, grammarStore) || IsCallsignShapeInvalid(token1, grammarStore))
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

                // #227 — "CQ <modifier> <call>" (no grid) is a valid FT8 form.  Token 1 is a CQ
                // modifier (e.g. DX, POTA, 123), exempt from the callsign-shape check in this case
                // only.  The accept happens here, BEFORE the last-field rule below, which would
                // reject a callsign in the last position.
                if (token0.Equals("CQ", StringComparison.Ordinal) &&
                    IsCqModifier(token1) &&
                    IsParsedCallsign(text[(secondSpace + 1)..], grammarStore))
                    return true;

                if (IsCallsignShapeInvalid(token0, grammarStore) || IsCallsignShapeInvalid(token1, grammarStore))
                    return false;
            }
            else if (firstSpace > 0 && secondSpace > firstSpace && thirdSpace > secondSpace
                     && text.IndexOf(' ', thirdSpace + 1) < 0)
            {
                // Exactly 4-token message: "TOKEN0 TOKEN1 TOKEN2 TOKEN3"
                // Valid 4-token FT8 forms are "CQ <modifier> <callsign> <grid>"
                // (e.g. "CQ DX Q1ABC FN42", "CQ NA Q9XYZ EN37") and, since #228,
                // "CALL CALL R GRID" (e.g. "Q1ABC Q2XYZ R FN42").  ft8_lib renders the latter
                // form (message.c:952-953); the earlier rule that rejected it rested on D-009
                // false-alarm evidence (Category A) that predates the OSD sign fix (#215).
                // Every other non-CQ 4-token message stays rejected.
                string token0 = text[..firstSpace];
                if (!token0.Equals("CQ", StringComparison.Ordinal))
                {
                    string token1 = text[(firstSpace + 1)..secondSpace];
                    string token2 = text[(secondSpace + 1)..thirdSpace];
                    string token3 = text[(thirdSpace + 1)..];
                    if (!(token2.Equals("R", StringComparison.Ordinal) &&
                          IsAcknowledgedGrid(token3) &&
                          IsHashOrParsedCallsign(token0, grammarStore) &&
                          IsHashOrParsedCallsign(token1, grammarStore)))
                        return false;
                }
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

    /// <summary>Maximum letters in a CQ modifier (<c>CQ DX</c>, <c>CQ POTA</c>).</summary>
    private const int CqModifierLetterMax = 4;

    /// <summary>Digits in a numeric CQ modifier (<c>CQ 123</c>).</summary>
    private const int CqModifierDigitCount = 3;

    /// <summary>
    /// <c>true</c> when <paramref name="token"/> is a CQ modifier: 1 to
    /// <see cref="CqModifierLetterMax"/> letters A–Z, or exactly
    /// <see cref="CqModifierDigitCount"/> digits (#227).
    /// </summary>
    public static bool IsCqModifier(string token)
    {
        if (token.Length == CqModifierDigitCount)
        {
            bool allDigits = true;
            foreach (char c in token) if (!char.IsAsciiDigit(c)) { allDigits = false; break; }
            if (allDigits) return true;
        }

        if (token.Length is < 1 or > CqModifierLetterMax) return false;
        foreach (char c in token)
            if (c < 'A' || c > 'Z') return false;
        return true;
    }

    /// <summary>
    /// <c>true</c> when <paramref name="token"/> matches <c>[A-R]{2}[0-9]{2}</c> — a
    /// Maidenhead 4-character grid (#228).
    /// </summary>
    public static bool IsAcknowledgedGrid(string token) =>
        token.Length == 4 &&
        token[0] >= 'A' && token[0] <= 'R' &&
        token[1] >= 'A' && token[1] <= 'R' &&
        char.IsAsciiDigit(token[2]) &&
        char.IsAsciiDigit(token[3]);

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
    /// that fails the ITU Radio Regulations Article 19 §19.68–19.69-derived shape
    /// grammar (D9-R3 guard, <c>f-002-callsign-structure-region-lookup</c>) — replacing
    /// the earlier length-only oversized-callsign check.
    /// </summary>
    /// <remarks>
    /// Exempt cases (always returns <c>false</c>):
    /// <list type="bullet">
    ///   <item>Hash-reference tokens beginning with <c>&lt;</c> (e.g. <c>&lt;...&gt;</c>).</item>
    ///   <item>Short pseudo-callsigns with ≤ 3 characters (CQ, DE, QRZ).</item>
    /// </list>
    /// <para>
    /// The shape grammar (design.md Decision 1) accepts a <em>superset</em> of the
    /// standard prefix–numeral–suffix form so that genuine Type 4 nonstandard/special-
    /// event callsign literals (D-011, <c>f-001-hashed-callsign-resolution</c>) are not
    /// rejected again via a different mechanism: a base callsign (before any portable
    /// suffix) is shape-valid when its <em>trailing</em> contiguous digit-run (the run
    /// immediately preceding the letters-only suffix) is 1 to
    /// <see cref="CallsignGrammarConfig.DigitRunMax"/> digits long, the suffix after
    /// that run is 1 to <see cref="CallsignGrammarConfig.SuffixLengthMax"/> letters, and
    /// the remaining leading prefix (1–4 alphanumeric characters containing at least one
    /// letter) accounts for everything before the digit-run. A token whose total or base
    /// length exceeds <see cref="CallsignGrammarConfig.TotalLengthMax"/> (default 11,
    /// unchanged from D-011 — the Type 4 <c>ihashcall</c>/<c>pack58</c> charset width) is
    /// rejected outright, before the shape check runs.
    /// </para>
    /// <para>
    /// This is what rejects <c>3AG9672ATCH</c>-class noise (digit-run <c>9672</c> — 4
    /// consecutive digits, exceeding the default cap of 3) while continuing to admit
    /// genuine nonstandard literals like <c>Q0D011ABCDE</c> (trailing digit-run
    /// <c>011</c> — 3 digits, within cap; prefix <c>Q0D</c>; suffix <c>ABCDE</c>).
    /// </para>
    /// <para>
    /// #226: a token with exactly one <c>/</c> is also shape-valid as <c>PREFIX/CALL</c> — the
    /// right half parses as a callsign shape and the left half is a prefix shape (1–4
    /// alphanumerics, at least one letter). The reserved-prefix exclusion applies to the base
    /// and, in that case, to the left half. Anything the left-base rule accepts stays accepted.
    /// </para>
    /// <para>
    /// A parsed prefix matching a reserved/never-allocated entry in
    /// <see cref="CallsignGrammarConfig.ReservedPrefixExclusions"/> with no synthetic
    /// carve-out is also rejected (Decision 2) — this is an exclusion signal, not a
    /// positive allow-list: a prefix absent from the table is never rejected on that
    /// basis alone.
    /// </para>
    /// </remarks>
    /// <param name="token">The callsign-position token to check.</param>
    /// <param name="grammarStore">
    /// Optional callsign shape-grammar store; falls back to
    /// <see cref="CallsignGrammarConfig.BuiltInDefault"/> when <c>null</c>.
    /// </param>
    internal static bool IsCallsignShapeInvalid(string token, ICallsignGrammarStore? grammarStore = null)
    {
        // Today's rule first: anything it accepts stays accepted (acceptance-only, #226).
        if (!IsCallsignShapeInvalidLeftBase(token, grammarStore)) return false;

        // #226 — a token with exactly one '/' may also be PREFIX/CALL: the RIGHT half is the
        // base callsign and the left half a prefix shape.  Two or more '/' keep today's result.
        int slashPos = token.IndexOf('/');
        if (slashPos < 0 || token.IndexOf('/', slashPos + 1) >= 0) return true;

        var config = grammarStore?.Current ?? CallsignGrammarConfig.BuiltInDefault;
        string left  = token[..slashPos];
        string right = token[(slashPos + 1)..];

        if (token.Length > config.TotalLengthMax || right.Length > config.TotalLengthMax) return true;
        if (!IsPrefixShape(left)) return true;
        if (!TryParseCallsignShape(right, config, out string rightPrefix)) return true;

        // The reserved-prefix exclusion applies to the base (right half) and, under this
        // branch, also to the left half — both as written and with trailing digits dropped
        // (the prefix a callsign built on it would carry).
        if (IsExcluded(config, rightPrefix) ||
            IsExcluded(config, left) ||
            IsExcluded(config, left.TrimEnd('0', '1', '2', '3', '4', '5', '6', '7', '8', '9')))
            return true;

        return false;
    }

    /// <summary>
    /// <c>true</c> when <paramref name="token"/> is a hash reference (<c>&lt;…&gt;</c>) or a
    /// token that genuinely PARSES as a callsign (see <see cref="IsParsedCallsign"/>).
    /// </summary>
    private static bool IsHashOrParsedCallsign(string token, ICallsignGrammarStore? grammarStore) =>
        token.StartsWith('<') || IsParsedCallsign(token, grammarStore);

    /// <summary>
    /// <c>true</c> when <paramref name="token"/> is shape-valid AND its base callsign actually
    /// parses with <see cref="TryParseCallsignShape"/> — stricter than "not invalid", which
    /// also exempts hash references, tokens of 3 characters or fewer, and <c>RR73</c>
    /// (#227/#228, spec amendment 2). The base is the part before the first '/', or — for a
    /// single-slash token — the right half (#226).
    /// </summary>
    public static bool IsParsedCallsign(string token, ICallsignGrammarStore? grammarStore = null)
    {
        if (token.StartsWith('<') || IsCallsignShapeInvalid(token, grammarStore)) return false;

        var config = grammarStore?.Current ?? CallsignGrammarConfig.BuiltInDefault;
        int slashPos = token.IndexOf('/');
        if (slashPos < 0) return TryParseCallsignShape(token, config, out _);

        if (TryParseCallsignShape(token[..slashPos], config, out _)) return true;
        return token.IndexOf('/', slashPos + 1) < 0 &&
               TryParseCallsignShape(token[(slashPos + 1)..], config, out _);
    }

    private static bool IsExcluded(CallsignGrammarConfig config, string prefix)
    {
        if (prefix.Length == 0) return false;
        var exclusion = FindExclusion(config, prefix);
        return exclusion is not null && !exclusion.SyntheticCarveOut;
    }

    /// <summary>
    /// <c>true</c> when <paramref name="s"/> is a prefix shape: 1 to 4 alphanumeric
    /// characters containing at least one letter (the grammar
    /// <see cref="TryParseCallsignShape"/> applies to a callsign's leading prefix).
    /// </summary>
    private static bool IsPrefixShape(string s)
    {
        const int PrefixLengthMax = 4;
        if (s.Length == 0 || s.Length > PrefixLengthMax) return false;
        bool hasLetter = false;
        foreach (char c in s)
        {
            if (char.IsAsciiLetter(c)) hasLetter = true;
            else if (!char.IsAsciiDigit(c)) return false;
        }
        return hasLetter;
    }

    /// <summary>
    /// The pre-#226 shape check: the base callsign is the part before any '/'.
    /// </summary>
    private static bool IsCallsignShapeInvalidLeftBase(string token, ICallsignGrammarStore? grammarStore)
    {
        if (token.StartsWith('<')) return false;   // hash reference — always shape-valid
        if (token.Length <= 3)    return false;    // CQ / DE / QRZ / very short call — exempt

        // Terminal shorthand tokens are not callsign-position tokens even though the
        // 2-token "check both tokens" path (Gap A) calls this on every token
        // indiscriminately — a Type 4 shorthand message like "<...> RR73" has RR73 in
        // the token-1 position, which must not be evaluated against the shape grammar.
        // "RRR" and "73" are already exempt via the ≤3-char check above; "RR73" is the
        // only 4+ char terminal keyword.
        if (token.Equals("RR73", StringComparison.Ordinal)) return false;

        var config = grammarStore?.Current ?? CallsignGrammarConfig.BuiltInDefault;

        // Split on '/' to isolate the base callsign from any portable suffix
        // (/P, /M, /MM, /QRP, /A, or a compound second callsign) — evaluated
        // separately from the shape grammar, as today.
        int    slashPos = token.IndexOf('/');
        string baseCall = slashPos >= 0 ? token[..slashPos] : token;

        // Total-length ceiling: base callsign from standard Type 1 packing, OR a
        // literal Type 4 nonstandard callsign's full text (D-011) — checked before
        // the shape grammar so a merely-too-long token is rejected outright.
        if (baseCall.Length > config.TotalLengthMax || token.Length > config.TotalLengthMax)
            return true;

        if (!TryParseCallsignShape(baseCall, config, out string prefix))
            return true;

        // Decision 2: reserved/never-allocated prefix exclusion list, with an explicit
        // synthetic-use carve-out (NFR-021) — an additional signal, not a positive
        // allow-list. A prefix absent from the table is never rejected on this basis.
        var exclusion = FindExclusion(config, prefix);
        if (exclusion is not null && !exclusion.SyntheticCarveOut)
            return true;

        return false;
    }

    private static CallsignPrefixExclusion? FindExclusion(CallsignGrammarConfig config, string prefix)
    {
        foreach (var exclusion in config.ReservedPrefixExclusions)
            if (string.Equals(exclusion.Prefix, prefix, StringComparison.OrdinalIgnoreCase))
                return exclusion;
        return null;
    }

    /// <summary>
    /// Attempts to parse <paramref name="baseCall"/> into the three shape-grammar
    /// components (design.md Decision 1): a leading prefix (1–4 alphanumeric characters
    /// containing at least one letter), a trailing contiguous digit-run of 1 to
    /// <see cref="CallsignGrammarConfig.DigitRunMax"/> digits, and a letters-only suffix
    /// of 1 to <see cref="CallsignGrammarConfig.SuffixLengthMax"/> characters.
    /// </summary>
    /// <remarks>
    /// The digit-run is identified as the maximal contiguous run of digits ending at the
    /// <em>last</em> digit anywhere in <paramref name="baseCall"/> — not an arbitrary
    /// split — so digits earlier in the string (which belong to the prefix) cannot be
    /// used to dodge the digit-run cap. This is what distinguishes a genuine literal like
    /// <c>Q0D011ABCDE</c> (trailing run <c>011</c>, 3 digits) from garbage like
    /// <c>3AG9672ATCH</c> (trailing run <c>9672</c>, 4 digits — over cap).
    /// </remarks>
    private static bool TryParseCallsignShape(string baseCall, CallsignGrammarConfig config, out string prefix)
    {
        const int PrefixLengthMax = 4;
        prefix = "";

        int lastDigitIndex = -1;
        for (int i = baseCall.Length - 1; i >= 0; i--)
        {
            if (char.IsAsciiDigit(baseCall[i])) { lastDigitIndex = i; break; }
        }
        if (lastDigitIndex < 0) return false; // no mandatory call-area digit at all

        // Suffix: everything after the last digit — must be letters only.
        string suffix = baseCall[(lastDigitIndex + 1)..];
        if (suffix.Length == 0 || suffix.Length > config.SuffixLengthMax) return false;
        foreach (char c in suffix)
            if (!char.IsAsciiLetter(c)) return false;

        // Digit-run: the maximal contiguous run of digits ending at lastDigitIndex.
        int digitRunStart = lastDigitIndex;
        while (digitRunStart > 0 && char.IsAsciiDigit(baseCall[digitRunStart - 1]))
            digitRunStart--;
        int digitRunLength = lastDigitIndex - digitRunStart + 1;
        if (digitRunLength > config.DigitRunMax) return false;

        // Prefix: everything before the digit-run — 1–4 alphanumeric chars, ≥1 letter.
        string candidatePrefix = baseCall[..digitRunStart];
        if (candidatePrefix.Length == 0 || candidatePrefix.Length > PrefixLengthMax) return false;

        bool prefixHasLetter = false;
        foreach (char c in candidatePrefix)
        {
            if (char.IsAsciiLetter(c)) prefixHasLetter = true;
            else if (!char.IsAsciiDigit(c)) return false;
        }
        if (!prefixHasLetter) return false;

        prefix = candidatePrefix;
        return true;
    }

    // ── Region lookup (advisory bycatch, region-lookup capability) ────────────

    /// <summary>
    /// Extracts the callsign-position token in the "caller-identification" position from
    /// a plausible decode text — the station whose callsign identifies the transmission
    /// that produced this message — for the advisory region lookup (design.md Decision 4).
    /// Best-effort only: a <c>null</c> result simply leaves <see cref="DecodeResult.Region"/>
    /// unresolved ("Unknown"); it never affects decode acceptance.
    /// </summary>
    /// <remarks>
    /// <list type="bullet">
    ///   <item>
    ///     <c>CQ [modifier] &lt;call&gt; [grid]</c>: the CQ caller's own callsign — token 1
    ///     for the 2/3-token forms, token 2 for the 4-token <c>CQ &lt;modifier&gt; &lt;call&gt; &lt;grid&gt;</c> form
    ///     (mirrors <c>web/js/main.js</c>'s <c>extractCqCallsign</c>).
    ///   </item>
    ///   <item>
    ///     Standard QSO <c>&lt;to&gt; &lt;from&gt; &lt;ext&gt;</c> form: token 1 (the "from"/sender
    ///     field — the station identifying itself in this transmission), falling back to
    ///     token 0 when token 1 is a hash reference or a terminal keyword.
    ///   </item>
    /// </list>
    /// </remarks>
    internal static string? ExtractPrimaryCallsignToken(string text)
    {
        var tokens = text.Split(' ');
        if (tokens.Length == 0) return null;

        if (tokens[0].Equals("CQ", StringComparison.Ordinal))
        {
            string? candidate = tokens.Length switch
            {
                2 or 3         => tokens[1],
                >= 4           => tokens[2],
                _              => null,
            };
            return candidate is not null && IsCandidateCallsignToken(candidate)
                ? CallsignTokenHelpers.StripPortableSuffix(candidate)
                : null;
        }

        if (tokens.Length >= 2 && IsCandidateCallsignToken(tokens[1]))
            return CallsignTokenHelpers.StripPortableSuffix(tokens[1]);

        if (tokens.Length >= 1 && IsCandidateCallsignToken(tokens[0]))
            return CallsignTokenHelpers.StripPortableSuffix(tokens[0]);

        return null;
    }

    private static bool IsCandidateCallsignToken(string token)
        => token.Length > 0 && token[0] != '<' && token is not ("RRR" or "73" or "RR73");
}
