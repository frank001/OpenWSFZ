# D-001 C.2 — LLR-normalisation findings

**Author:** Developer session (HK-011), 2026-07-26. **For:** QA/Architect (per HK-000/HK-015 —
Dev reports up to QA, not directly to the Architect/Captain).
**Source:** `dev-tasks/2026-07-26-d001-c2-llr-normalization.md`.
**Build under test:** branch `d001-c2-llr-normalization`, off `main` @ `7a44b2c`.

---

## 1. Summary verdict

**Phase 1 CONFIRMS the correlation.** Candidates matched to WSJT-X messages we failed to decode
("matched-missed") show systematically weaker pre-normalisation `log174` variance and weaker
post-normalisation mean|LLR| than candidates that did decode ("matched-hit") on the *same cycles*
— and the gap **survives controlling for sync score** (score-banded breakdown, section 4). Both
differences are large and statistically overwhelming (Mann-Whitney U, p = 6e-35 and p = 6.9e-8
raw; p = 9e-34 and p = 5.4e-7 restricted to the two populations' overlapping score range).

Per the dev-task's own §5 decision rule, this warrants **Phase 2 (a fix attempt)** — but see
section 6 for why this session **scopes Phase 2 rather than shipping it**: my own Phase 1 data
rules out the naive reading of the fix ("clamp/floor the variance") and points at a more invasive
change (shrinkage toward a robust reference) that touches the decoder's hot path for every decode
call, not just an opt-in diagnostic, and interacts with D-009's calibrated OSD gate — a materially
bigger, riskier change that deserves its own dedicated implementation-and-validation pass.

## 2. Phase 1 — what was built

1. **Native**: `ft8_shim.c`/`.h`, shim version 20260033 → 20260034. Two new exported entry points,
   opt-in and disabled by default:
   - `ft8_set_candidate_diag_capture(int enable)` — thread-local toggle.
   - `ft8_get_last_candidate_diag(...)` — returns, for every **pass-0** candidate examined during
     the most recent `ft8_decode_all` call on the calling thread: `freq_hz`, `dt`, `score`,
     `decoded` (raw LDPC/OSD+CRC survival — independent of later cross-pass dedup or text-unpack),
     `prenorm_var`, `postnorm_mean_abs_llr` (may be NaN for degenerate/zero-variance candidates).
   - Implementation re-derives `prenorm_var`/`postnorm_mean_abs_llr` via the existing
     `ftx_compute_candidate_llr_stats()` for **every** pass-0 candidate (decoded or not), inside
     the existing per-candidate loop in `ft8_decode_all` — independent of, and without touching,
     the existing failing-candidate-only aggregate accumulator (`tls_llr_mean_abs_sum` etc.), so
     that feature's behaviour cannot regress.
   - **Verified behavioural no-op when disabled** (the shipped default): rebuilt the DLL, ran the
     68-cycle matched corpus (see section 3) through the harness with capture off, and diffed
     against a pristine `main`-branch build byte-for-byte — **0-line diff**, identical
     `hashTableRejectCount` (656 both). Re-ran with capture *on* — also 0-line diff against the
     capture-off run. The diagnostic genuinely costs nothing when unused and does not perturb
     decode output when used.
2. **Managed**: `IFt8NativeInterop`/`Ft8NativeInteropAdapter`/`Ft8LibInterop` — thin pass-through
   additions, same pattern as `GetLastLlrStats`. `Ft8Decoder` — **not** a direct pass-through:
   the native capture flag is thread-local and `DecodeAsync` offloads the actual native call to a
   `Task.Run` ThreadPool thread, so `SetCandidateDiagCapture`/`GetLastCandidateDiagnostics` cannot
   safely be simple wrappers around the native calls (a first attempt at exactly that produced
   silently-empty diagnostics — zero rows — because the harness's calling thread is never the
   thread that runs `ft8_decode_all`). Fixed by making `SetCandidateDiagCapture` set a pure C#
   `volatile bool` field; `DecodeAsync`'s existing `Task.Run` lambda (which already has a
   documented TLS-affinity contract for `GetLastPassCounts`/`GetLastCandidateCounts`/
   `GetLastNoiseFloorDb`/`GetLastLlrStats`) re-asserts the native flag and reads the diagnostics
   itself, snapshotting the result into an ordinary managed field that's safe to read from any
   thread once the `DecodeAsync` task completes.
3. **Harness**: `qa/rr-study/d001-param-sweep-2026-07-22/Program.cs` — new opt-in
   `--candidate-diag-csv <name>` flag; when set, writes one CSV per grid point alongside its
   `ALL.TXT` (`cycle_ts,wav_stem,freq_hz,dt,score,decoded,prenorm_var,postnorm_mean_abs_llr`).
   Deviation from "harness unmodified" recorded per project convention, same class of deviation
   C.1 recorded for its `--debug-log` flag.
4. **Analysis**: new `qa/cycleframer-alignment-replay/c2_llr_normalization_analysis.py`.

## 3. Method

Re-decoded the same fixed 68-cycle corpus used throughout D-001 (filename-matched intersection of
`artefacts/20260725_live_run_1806/owsfz/wav/` and `.../wsjt-x/wav/`, 68 files) via
`qa/rr-study/d001-param-sweep-2026-07-22` at `--points k10_c0.10_n60 --dial-mhz 7.074
--candidate-diag-csv candidate_diag.csv`. Total decodes: **1284** (not the consolidation doc's
1288, nor C.1's reproduced 1288 — see the note in section 7; this is an environmental drift in
the corpus/tooling between sessions, not a regression from this branch, confirmed by the
byte-identical main-vs-branch diff in section 2).

**Matched-missed set** (dev-task §4 step 3): for each of the 68 cycles, every WSJT-X `ALL.TXT`
message was checked against our own `ALL.TXT` for that cycle by message text (hash-bracket
tokens normalised via the same `normalize_hash_tokens` used in `score_recall.py`, for the same
session-scoped-hash-table-order reason documented there). Messages present in both are a shared
hit and excluded. WSJT-X-only messages were matched to the **nearest of our own failed
(`decoded=0`) pass-0 candidates** in the same cycle by frequency, within tolerance:

- **Frequency tolerance: ±10 Hz.** FT8 tone spacing is 6.25 Hz (`TONE_SPACING_HZ` in
  `ft8_shim.c`; `freq_osr=2` gives 3.125 Hz sub-bin resolution) — one full tone spacing plus slop
  for two independent frequency estimators (WSJT-X's and ours) disagreeing on the same signal.
- **Time tolerance: ±0.5 s**, generous, used only to break rare same-frequency ties.

Of 2028 WSJT-X messages in these 68 cycles: 1235 were shared hits, 793 were WSJT-X-only. Of those
793: **135 (17.0%) matched one of our failed candidates** (the matched-missed population this
experiment is about); 658 had no candidate of ours — decoded or not — anywhere within tolerance.
A supplementary check (not part of the CSV/script, run ad hoc) found only 10 of those 658 were
near a *decoded* candidate of ours (a dedup/text-unpack-stage loss, not a candidate-generation
gap); the remaining 648 are a genuine candidate-generation gap — `ftx_find_candidates` never
proposing a sync candidate near that frequency/time at all. That is a **different** mechanism from
C.1's candidate-*cap* question (which asked whether truncation of an already-found candidate list
costs decodes) and is out of scope for C.2 (LLR normalisation only applies to candidates that
exist). Flagged here for whoever scopes the next avenue in the consolidation doc's §6.3 tree — not
investigated further in this branch.

**Control population**: all `decoded=1` pass-0 candidates on the same 51 cycles that contributed
at least one matched-missed candidate (n=2502).

## 4. Results

Full output: `artefacts/20260725_live_run_1806/c2_phase1/k10_c0.10_n60/` (`ALL.TXT`,
`candidate_diag.csv`; git-ignored per NFR-021 — real off-air callsigns).

| population | n | median score | median prenorm_var | median postnorm_mean\|LLR\| |
|---|---:|---:|---:|---:|
| matched-missed | 135 | 15.0 | 85.69 | 4.054 |
| matched-hit | 2502 | 21.0 | 155.24 | 4.247 |

Mann-Whitney U (two-sided, raw populations): `prenorm_var` U=62628, **p=6.2e-35**;
`postnorm_mean_abs_llr` U=122405, **p=6.9e-8**. Matched-missed median is lower on both metrics.

**Score-banded breakdown** (the actual score-controlled test — dev-task §4 step 4 requires
controlling for score, not just reporting the raw gap):

| score band | n missed | med prenorm_var (missed) | med postnorm (missed) | n hit | med prenorm_var (hit) | med postnorm (hit) |
|---|---:|---:|---:|---:|---:|---:|
| [10,20) | 112 | 83.26 | 4.030 | 949 | 114.48 | 4.083 |
| [20,30) | 22 | 105.06 | 4.242 | 1319 | 167.90 | 4.308 |
| [30,40) | 1 | 252.60 | 4.561 | 234 | 242.07 | 4.602 |

**Missed candidates have lower median prenorm_var and postnorm_mean\|LLR\| within every populated
score band**, not just in aggregate — the effect is not merely a proxy for missed candidates
having lower sync scores. Score-overlap-restricted comparison (score in [10,32], the missed
population's full range) reproduces the same result: prenorm_var p=9.1e-34, postnorm p=5.4e-7,
same direction.

**Effect is a broad distributional shift, not a degenerate-candidate tail.** The matched-hit
population's *minimum* prenorm_var (22.02) is actually *below* the matched-missed population's
minimum (29.08) — there is no clean low-variance cutoff separating "will never decode" from "will
decode." This matters directly for section 6's Phase 2 scoping.

## 5. Interpretation

**Hypothesis confirmed at the message level, not just the aggregate-decile level the consolidation
doc originally observed.** The specific messages WSJT-X decoded and we didn't are, on this
corpus, measurably weaker in normalised-LLR terms than candidates on the same cycles that
survived LDPC/OSD — even after controlling for sync score. This rules out the alternative reading
(§3 of the dev-task): matched-missed candidates are not simply "ordinary low-score/low-SNR
candidates that were never going to decode by any normalisation scheme" in a way that's
*independent* of normalisation — if that were the whole story, the score-banded breakdown would
show no residual gap once score is held fixed, and it does not.

This does **not** by itself prove that changing the normalisation scheme would recover these 135
(or the 728-decode decoder-attributable gap C.1's consolidation routed here) — it proves the
*discriminator* the hypothesis needs to exist, does exist. Whether an alternative scheme can
actually flip a meaningful fraction of these specific candidates from fail to pass is an
empirical question Phase 2 would have to answer by re-decoding, exactly as C.1 did for the
candidate cap.

## 6. Phase 2 — scoped, not shipped this session

The dev-task's own §4 gate is satisfied (Phase 1 confirmed) and its Definition of Done lists
Phase 2 as expected "if warranted." This section explains why Phase 2 is scoped here rather than
implemented and shipped in the same branch.

**What Phase 1's data already rules out:** a naive **clamp/floor** of the pre-normalisation
variance (dev-task §3 reading (a), "estimator noise," in its simplest form) would not help. A
floor only changes behaviour for candidates whose raw variance sits *below* the floor; both
populations' distributions substantially overlap across the whole range shown in section 4 (the
gap is a ~1.8x shift in central tendency, not a distinct low tail), and the matched-hit
population's own minimum (22.02) is below the matched-missed population's minimum (29.08) — so a
floor near the values that would plausibly separate "degenerate" candidates would floor almost
none of either population, or would floor genuinely-decodable low-variance candidates along with
the missed ones. This is a useful negative result: it saves whoever picks up Phase 2 next from
re-deriving it.

**What looks more promising, and why it isn't attempted here:** a **shrinkage** estimator — blend
each candidate's own 174-sample variance estimate with a robust reference (a per-cycle/per-pass
median across candidates, or dev-task §4's suggested session/cycle-level noise-floor estimate) —
would systematically pull low-variance (mostly matched-missed-like) candidates' effective variance
*up*, which under `norm_factor = sqrt(24/variance)` would scale their LLRs *less* aggressively
than today. Whether that improves LDPC/OSD convergence for these specific candidates, or simply
under-drives already-marginal signals into non-convergence a different way, is exactly the kind of
question that can only be answered empirically by re-decoding — reasoning about `bp_decode`'s
convergence behaviour from first principles is not reliable enough to skip that step (dev-task
§2's own note: confirm which BP variant is linked and whether it's documented-sensitive to LLR
magnitude, which this session did not additionally chase down).

Implementing shrinkage properly is a bigger and riskier change than everything else in this
branch:
- `ftx_normalize_logl` is **not** an opt-in diagnostic — it runs on every `bp_decode`/OSD attempt,
  in production, for every candidate, in both passes. A change here is not behind a flag; it
  changes the daemon's real decode output the moment it ships.
- A per-cycle-median variant requires restructuring the pass-0 loop (a lightweight prelim pass
  over all candidates' raw variances before any candidate is decoded) — a real control-flow
  change to a loop that already carries AP-decode, dedup, and suppression-accumulator logic
  (`ft8_shim.c`'s pass loop, ~150 lines), not a one-line edit.
- It interacts with **D-009's calibrated OSD gate** (`OSD_CORR_THRESHOLD`, `OSD_NHARD_MAX`) —
  both were calibrated against the *current* LLR distribution; changing the distribution's shape
  invalidates that calibration until it's re-verified, which is out of scope for a single
  dev-task branch.
- Validating it properly means more than this one 68-cycle corpus: at minimum a rerun of the
  existing R&R S1–S8 synthetic gate suite (`rr-study-baseline.md`) to confirm no regression on
  the corpora that calibration was actually done against, in addition to a before/after decode
  count on this corpus (C.1's own validation shape).

None of that is beyond this project's reach — it is exactly the shape of work C.1 already
recommended deferring for its own much smaller `K_MAX_CANDIDATES` proposal ("a separate,
deliberate follow-up with its own Captain sign-off"). Given C.2's fix touches a hot-path function
with no flag, the same deferral applies with more force here, not less.

**Recommendation for the follow-up dev-task**: implement shrinkage toward a per-pass median raw
variance (reusing `ftx_compute_candidate_llr_stats`, which is already cheap — no BP iterations),
sweep the shrinkage weight on a held-out corpus (not this same 68-cycle set, to avoid tuning to
the data used to discover the effect), re-run this branch's `candidate_diag.csv` capture to
confirm the matched-missed/matched-hit gap actually narrows before touching decode counts, then
re-run the full R&R gate suite before any shipped-constant decision.

## 7. Housekeeping notes

- **1284 vs. 1288 decodes on this corpus.** The consolidation doc and C.1 both report 1288 total
  decodes on this 68-cycle corpus; this session's runs (both a pristine `main` build and this
  branch, byte-identical to each other) reproduce **1284**. This was investigated far enough to
  rule out a regression from this branch's changes (section 2's byte-identical diff against
  pristine `main`) but not further — likely environmental drift (e.g. `owsfz/wav/` gained a file
  since C.1's run: this session found 85 files there vs. C.1's reported 84, though the 68-file
  matched intersection itself is identical either way). Does not affect this experiment's
  conclusions, which are about relative LLR statistics between two populations drawn from the
  *same* run, not about matching the historical absolute decode count.
- The `owsfz/wav68/` scratch directory (68-file copy used as `--wav-dir`) and the
  `c2_phase1/` output directory are both under the git-ignored `artefacts/` tree; not committed.

## 8. Definition of done (dev-task section 6)

- [x] Per-candidate diagnostic export added (native + harness), producing frequency/dt/score/
      decoded/prenorm-var/post-norm-mean\|LLR\| for every pass-0 candidate on the 68-cycle corpus.
- [x] Matched-missed set computed per cycle against WSJT-X's `ALL.TXT`, with the frequency-match
      tolerance used recorded explicitly (±10 Hz, ±0.5 s — section 3).
- [x] Matched-missed vs. matched-hit LLR comparison reported, controlling for sync score
      (score-banded breakdown, section 4).
- [x] A written verdict: **hypothesis supported** (section 1, section 5) — not left ambiguous.
- [x] Phase 2 warranted; scoped rather than run this session, with the specific reasoning recorded
      (section 6) instead of a before/after decode-count table.
- [x] Any deviation from spec recorded: harness `--candidate-diag-csv` flag (section 2.3), the
      `Ft8Decoder` TLS-thread-affinity fix needed beyond what the spec anticipated (section 2.2).
- [x] `python3 tools/pre_merge_check.py` green (HK-006) — see commit message / QA follow-up.
- [x] `git status` clean of any rebuilt `libft8.dll` beyond this branch's own diagnostic-capture
      rebuild — no normalisation change was made, so no further native rebuild is pending.

## 9. Cross-references

- `dev-tasks/2026-07-26-d001-c2-llr-normalization.md` — the task spec this executes.
- `qa/cycleframer-alignment-replay/2026-07-26-0015-d001-consolidation-and-clean-slate.md` §3, §6.2
  — the finding and framing this executes.
- `qa/cycleframer-alignment-replay/2026-07-26-c1-candidate-cap-sweep-findings.md` — C.1, the
  sibling experiment; establishes the candidate cap is not the constraint and that this experiment
  accounts for the remaining 98.4% (728/740) of the decoder-attributable gap.
- `native/ft8_lib_build/patched/ft8/decode.c:380-399` (`ftx_normalize_logl`), `:748-803`
  (`ftx_compute_candidate_llr_stats`) — unchanged this branch; the code Phase 2 would touch.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c`/`.h` — this branch's diagnostic capture (shim 20260034).
- `qa/cycleframer-alignment-replay/c2_llr_normalization_analysis.py` — this findings doc's
  analysis script.
- `qa/cycleframer-alignment-replay/score_recall.py` — message-matching/hash-normalisation logic
  adapted here for frequency-based matching of failed candidates.
- Consolidation doc §6.3 — the fallback avenue (structural WSJT-X comparison) if a future Phase 2
  attempt is also inconclusive.
