# D-001 C.2 Phase 2c — LLR shrinkage trial + hard-decision BER measurement findings

**Author:** Developer session (HK-011), 2026-07-26. **For:** QA/Architect (per HK-000/HK-015 —
Dev reports up to QA, not directly to the Architect/Captain).
**Source:** `dev-tasks/2026-07-26-d001-c2-phase2c-shrinkage-trial-and-ber.md`.
**Build under test:** branch `d001-c4-min-score-sweep` (continuing this thread's established
convention of stacking each D-001 phase onto the same feature branch rather than a fresh one per
session — see `git log`), shim version 20260034 → **20260035**.

---

## 1. Summary verdict

**Part A (shrinkage trial): closes on evidence, at the worst row of the dev-task's own decision
table.** Δ matched decodes across the weight sweep {0.0, 0.25, 0.5, 0.75, 1.0} on the discovery
corpus never exceeds +1, and at weight 1.0 goes **negative (−3)** — the "negative at any weight"
row of §4's decision rule, which the dev-task's own source note calls decisive on its own. **THE
135 population (score ≥10, the shrinkage trial's actual target) gained zero recoveries at every
single weight tested.** The trial also lost real, previously-working decodes: 1/2/5 matched-hit
regressions at weight 0.5/0.75/1.0 respectively. Item 3 (LDPC survival/LLR quality) is now closed
on measurement, not argument, exactly as the 19:30 ruling revision hoped this session would
resolve it.

**Part B (BER measurement): both missed populations sit at or near the Architect's ≈50% "front-end,
not magnitude" band.** THE 135: median BER 44.0% (n=126 measured). THE 567: median BER 49.4%
(n=279 measured, see §7's truncation caveat). Neither reads as "low, with correct signs" — the band
that would reopen Phase 2b. This independently *explains* Part A's negative result: shrinkage only
rescales LLR magnitude, and magnitude was never the problem — the sign itself is wrong on roughly
half the bits, indistinguishable from noise at the front end.

**Both halves of this session converge on the same conclusion by two independent methods.** That
convergence is itself evidence: a magnitude-focused fix (shrinkage) failing to help, and a
bit-level correctness measurement (BER) independently showing near-noise-level sign accuracy, are
not the same measurement re-asked — they are different questions that happen to agree.

## 2. What was built

### Part A — LLR shrinkage toggle (native)

1. **`ft8_set_llr_shrinkage(double weight)`** — thread-local, default `0.0`, exported from
   `ft8_shim.c`/`.h` (shim 20260034 → **20260035**). Plumbed into
   `native/ft8_lib_build/patched/ft8/decode.c`'s `ftx_normalize_logl`.
2. **Design**: blends each candidate's own pre-normalisation `log174` variance with a
   thread-local, per-`ft8_decode_all`-call running reference — the Welford-style running mean of
   every non-degenerate candidate's raw variance normalised so far on this thread this call
   (`tls_llr_shrink_ref_mean`/`tls_llr_shrink_ref_n`, reset at the top of every `ft8_decode_all`).
   `effective_variance = (1 − weight) × own_variance + weight × reference`. This is a Developer
   design choice made within this session (the Architect's source notes named "a per-cycle/
   per-pass median across candidates" as one option among a few, explicitly leaving the exact
   mechanism to the implementing session) — chosen specifically because it needs **no prelim pass
   over all candidates** (the per-pass loop restructure C.2 Phase 1 flagged as its own real cost)
   and is purely sequential state threaded through consecutive `ftx_normalize_logl` calls.
3. **Weight 0.0 is an exact no-op by construction**: `effective_variance = variance` is assigned
   inside an `if (tls_llr_shrinkage_weight != 0.0)` guard — the reference is never read, let alone
   arithmetically combined, when the weight is 0.0, which also protects against `0.0 * a
   non-finite reference` producing NaN.
4. **Verified empirically, not just by inspection** (§4.1): weight 0.0 reproduces the discovery
   corpus's `ALL.TXT` **byte-for-byte** against the pre-Phase-2c artefact
   (`c2_phase1/k10_c0.10_n60/ALL.TXT`, 1284 decodes, `hashTableRejectCount=656` both) — the trial's
   own no-op proof, same discipline as C.2 Phase 1's byte-identical DLL diff.
5. **Known limitation, stated plainly**: when `ft8_set_candidate_diag_capture` diagnostic capture
   is *also* enabled, `ftx_compute_candidate_llr_stats`'s own diagnostic-only `ftx_normalize_logl`
   call additionally updates the running reference (candidates get counted toward the reference
   twice: once for the real decode attempt, once for the diagnostic probe). This has **zero effect
   on the weight-0.0 no-op guarantee** (the reference is never read at weight 0.0 regardless), and
   this session never ran diag capture and the shrinkage sweep in the same pass, but it is a real
   confound for anyone re-running both together in future and is recorded here so they don't have
   to re-derive it.

### Part B — hard-decision BER measurement

1. **Gray/sync round-trip verified**, per the dev-task's own item 1: confirmed end-to-end with
   **no new native code** — `ft8_encode_message` (already exported) plus the vendored upstream
   `kFT8_Gray_map` and Costas/sync symbol layout (parsed at runtime from
   `C:\Temp\ft8_lib_headers\ft8\constants.c`, not hand-transcribed) recover the true 174-bit
   codeword from 79 tones. Verified via **two independent checks** on 6 Q-prefix synthetic test
   messages: CRC-14 match (ftx_compute_crc/ftx_extract_crc, ported from
   `C:\Temp\ft8_lib_headers\ft8\crc.c`) **and** all 83 LDPC parity-check rows (`kFTX_LDPC_Nm`,
   also parsed at runtime, not transcribed) satisfied — **6/6 messages passed both checks**. No
   fallback native codeword export was needed.
   Script: `qa/cycleframer-alignment-replay/c2_phase2c_gray_sync_roundtrip_verify.py`.
2. **174-value raw LLR export**: `ft8_set_candidate_diag_llr_capture(int enable)` +
   `ft8_get_last_candidate_llr(...)`, layered on top of C.2 Phase 1's existing
   `ft8_set_candidate_diag_capture` (has no effect unless that capture is *also* enabled — kept as
   a separate toggle so a caller wanting only the cheap scalar stats never pays for the ~140×174
   floats of extra copying per cycle). Exports `ftx_get_candidate_raw_llr`'s raw (pre-normalisation)
   log174, which never needs a degenerate-candidate NaN guard (unlike
   `ftx_compute_candidate_llr_stats`) — a hard-decision sign comparison is defined for every
   candidate.
3. **Harness**: `--candidate-diag-llr` flag appends one `llr174` column (semicolon-joined, not
   174 separate CSV columns) to `--candidate-diag-csv`'s existing output.
4. **Sign-convention finding, recorded so nobody re-derives it**: the raw `log174` array's
   POSITIVE sign means **bit = 1** (matching `ft8_extract_symbol`'s own code comment,
   `log likelihood log(p(1)/p(0))`, taken literally) — **not** `decode.c`'s own internal
   `hd = (llr > 0.0f) ? 0 : 1` formula used for its `nhard`/OSD-gate feature. That formula is an
   internally-consistent proxy for Hamming-closeness gating inside `decode.c`'s own bit
   bookkeeping; it is **not** a true-bit predictor in the sense this measurement needs. Found by
   the self-check in §3 below: the matched-hit control's BER was ~90-95% (i.e. almost total
   *disagreement*) under `decode.c`'s own `hd` formula, and ~3-8% (correctly near-zero) under the
   complementary convention (`hd = 1 if llr > 0.0 else 0`) — a symptom of a sign-convention
   mismatch, not of a bug in the independently CRC/LDPC-syndrome-verified codeword recovery. This
   is now documented directly in `c2_phase2c_ber_measurement.py`'s `hard_decision_ber` docstring.

## 3. Method

**Corpus**: the same fixed 68-cycle discovery corpus used throughout C.1–C.4 and Phase 2a
(`artefacts/20260725_live_run_1806/owsfz/wav68/`, filename-matched against WSJT-X's own capture),
decoded via `qa/rr-study/d001-param-sweep-2026-07-22` at `--points k10_c0.10_n60 --dial-mhz 7.074`.
Per the dev-task's own §2 item 7, this is the discovery corpus only — a positive result here is an
upper bound requiring held-out confirmation, not (per §1) a result this session authorises acting
on directly.

**Part A** ran at the *shipped* `K_MIN_SCORE=10`/`K_MAX_CANDIDATES=140` config — the only config
under consideration for shipping — sweeping `--llr-shrinkage-weight` across
{0.0, 0.25, 0.5, 0.75, 1.0}, five separate harness invocations.

**Part B** required the raw LLR export enabled on **two** separate candidate sets, since THE 135
and THE 567 populations exist in different candidate sets (a fact established by Phase 1/Phase 2a,
not new to this session):
- THE 135 (score ≥10): captured at the shipped K10/cap140 config, weight 0.0.
- THE 567 (score 5–9): required a **temporary** native rebuild at `K_MIN_SCORE=4`/
  `K_MAX_CANDIDATES=2000` (the same config C.4/Phase 2a used to find these candidates in the first
  place — a compile-time `#define` swap, not a runtime toggle) to give these candidates any LLRs
  to export at all. **Reverted immediately after the capture run** — confirmed by re-running the
  weight-0.0 no-op check a second time post-revert: `ALL.TXT` byte-identical to the pre-Phase-2c
  artefact again (§4.1). `git diff` on `ft8_shim.c` shows `K_MIN_SCORE`/`K_MAX_CANDIDATES` at
  their shipped 10/140 values; only the additive Phase 2c changes remain.

**Population identities** (135 / 567 / matched-hit control) are reproduced from the same frozen
artefacts C.2 Phase 1 and Phase 2a already committed, using the same freq/dt matching tolerance
(±10 Hz, ±0.5 s) and hash-token normalisation established in that thread — **not re-argued or
re-derived from scratch**. Self-check: this session's re-derivation of THE 135 (n=135), the 648
candidate-generation-gap population (n=648), and THE 567 (n=567) all reproduce the exact frozen
counts from the source findings docs. Scripts:
`qa/cycleframer-alignment-replay/c2_phase2c_shrinkage_sweep_analysis.py` (Part A) and
`c2_phase2c_ber_measurement.py` (Part B).

**Self-check before trusting any BER number** (Part B): the matched-hit control population
(messages we definitely decoded, CRC-checked) must show near-zero BER. First attempt failed
(§2 item 4) — not because of a pipeline bug, but a sign-convention question, resolved and
documented. **Second attempt: median BER 2.9%, mean 8.0% (n=171) — PASS.**

## 4. Results

### 4.1 Part A — shrinkage weight sweep (K10/cap140, discovery corpus)

| weight | total | matched | Δ matched | THE 135 hit | THE 567 hit | matched-hit regressed |
|---:|---:|---:|---:|---:|---:|---:|
| 0.00 | 1284 | 1235 | +0 (baseline) | 0/135 | 0/567 | 0/1235 |
| 0.25 | 1285 | 1236 | **+1** | 0/135 | 0/567 | 0/1235 |
| 0.50 | 1285 | 1236 | **+1** | 0/135 | 1/567 | 1/1235 |
| 0.75 | 1284 | 1235 | **+0** | 0/135 | 1/567 | 2/1235 |
| 1.00 | 1281 | 1232 | **−3** | 0/135 | 1/567 | 5/1235 |

Unique-to-us share held flat at 3.8% across every weight (49 unique-to-us messages at every
weight) — the toggle is not manufacturing false decodes at any tested weight, for what that is
worth given the headline result below.

**Elapsed time vs. the 15 s budget**: 570–742 ms/decode across the sweep (highest observed:
weight 0.25, 742 ms) — comfortably inside budget at every weight tested, as expected for a toggle
that adds one branch and a few flops per candidate, not new BP/OSD iterations.

**hashTableRejectCount** (a session-lifetime resolution-table counter, unrelated to this trial's
own mechanism but a convenient corroborating signal): 656 at weight 0.0/0.25, 655 at 0.5/0.75, 650
at weight 1.0 — the decode set is genuinely shifting under the toggle, not just relabelling the
same decodes; consistent with (not proof of) the same underlying LDPC/OSD-convergence changes the
matched-decode table shows directly.

### 4.2 Part B — hard-decision BER

| population | n (population) | n (measured) | median BER | mean BER | min | max |
|---|---:|---:|---:|---:|---:|---:|
| matched-hit control (self-check) | 200 (capped) | 171 | **2.9%** | 8.0% | 0.0% | 52.9% |
| THE 135 (score ≥10, K10/cap140) | 135 | 126 | **44.0%** | 39.0% | 6.9% | 61.5% |
| THE 567 (score 5–9, K=4/cap2000) | 567 | 279 (§7 caveat) | **49.4%** | 49.0% | 16.1% | 62.1% |

Gray/sync round-trip: **6/6 test messages passed both the CRC-14 and full 83-row LDPC syndrome
check** — see §2 item 1.

## 5. Verdict against the fixed decision rules

**Part A, against the dev-task §4 table** (fixed before the numbers were visible, per that table's
own convention):

> **negative at any weight → Closes immediately; confirms rather than merely raises the 18:30
> note's wrong-sign concern.**

Weight 1.0's Δ = −3 triggers this row. Every other weight sits in the **"< 10"** row ("C.4's
shape... Item 3 closes on evidence") regardless. **Both readings agree: item 3 (LDPC survival/LLR
quality) is closed on measurement.** THE 135 population — the specific 135 candidates the entire
Phase 1→2a→2c chain has been about — gained **zero** recoveries at every weight tested; whatever
tiny movement (+1) appears elsewhere in the corpus at low weights is not this mechanism working.

**Part B, against §3.5's illustrative bands** (explicitly not calibrated, per that section and
per the source note's own honesty about it):

> **≈50% → sync/demodulation front-end; kills all LLR-scaling avenues including the shrinkage
> trial's own, permanently.**

THE 135's 44.0% and THE 567's 49.4% median BER both sit at or very near this band, not at
"~15–25%" (decode effort) or "low, with correct signs" (which would reopen Phase 2b). Read
together with Part A's own negative/null result, this is a **coherent, doubly-confirmed** picture:
our LLRs for these specific missed messages are wrong on roughly half their bits — magnitude
rescaling (shrinkage) cannot fix a wrong sign, which is exactly why it didn't.

**Neither result should be read past what it actually shows** (per the dev-task's own §4 closing
line): this is one 21-minute corpus, one device, one band, same single-sample caveat as every
prior note in this thread. The BER bands are illustrative, not derived from this codebase's actual
LDPC/OSD correction power (§3.5's own caveat, carried forward unchanged here).

## 6. What this does not authorise

Per dev-task §5, unchanged by this session's results:

- **No ship decision.** Item 3's closure is a closure of the *avenue*, not a decline-to-investigate
  — it is now closed **on evidence**, which the 19:30 ruling revision said was worth one session to
  establish either way.
- **No D-009 recalibration, no R&R S1–S8 rerun, no held-out weight sweep, no unflagged change to
  `ftx_normalize_logl`.** None of these were touched. The shrinkage toggle defaults to 0.0 and
  nothing in this branch changes that default.
- **`K_MIN_SCORE` stays at 10, `K_MAX_CANDIDATES` stays at 140.** The temporary K=4/cap2000 swap
  for THE 567's capture was reverted before this findings doc was written; confirmed by §4.1's
  post-revert byte-identical re-check.
- **Item 4 (structural decoder difference) is not closed by this session** — if anything, Part B's
  BER result is the FIRST measured evidence bearing directly on it, pointing toward the
  sync/demodulation front-end rather than decode effort or LLR magnitude. §6.3's product framing
  (how much of WSJT-X's decoder to reimplement) remains parked for the Captain, per the 18:30
  ruling's own instruction — this session narrows the question, it does not answer it.

## 7. Housekeeping notes and honest caveats

- **THE 567's BER measurement is on a truncated subsample (n=279/567), not the full population.**
  The K=4/cap2000 capture hit the managed `Ft8LibInterop.MaxPass0Candidates` ceiling (600) in
  **every one of the 68 cycles** (confirmed: min/median/max candidates per cycle all exactly 600) —
  the same silent-truncation bug class C.4's own dev-task found once already for this exact
  constant (raised 140→600 for that reason). Raising it again (600→2000, to match this session's
  own K=4/cap2000 capture ceiling) and re-running would take ~6 more minutes of wall time per the
  §4.1 elapsed-time note below; not done in this session because the measured subsample (n=279,
  median 49.4%) already agrees closely with THE 135's independently-measured 44.0%, and it is
  unlikely additional data would move the qualitative verdict away from the "≈50%, front-end" band
  — but the exact 49.4% figure should be read as measured-subsample, not exhaustive-population.
  Whoever revisits this (or a similar K=4/cap2000 capture) next should raise `MaxPass0Candidates`
  first and confirm no cycle sits at the ceiling before trusting an exact percentage.
- **K=4/cap2000 decode cost**: 5338 ms/decode (68/68 wavs, 6.1 min wall) — ~7-9× slower than the
  shipped K10/cap140 config's ~600-740 ms/decode, still comfortably inside the 15 s budget, but a
  real cost data point for anyone considering K=4/cap2000 (or similar) as a shippable config in a
  different context. Not itself in scope for a ship decision here — recorded because C.1/C.4 both
  recorded elapsed time and this session follows the same convention.
- **The sign-convention finding in §2 item 4 is the single most important thing to carry forward**
  if anyone else touches raw (pre-normalisation) LLR values from this export: `decode.c`'s own
  `hd` formula is NOT a true-bit predictor outside its own internal nhard/OSD-gate bookkeeping.
  Documented directly in code (`c2_phase2c_ber_measurement.py`'s `hard_decision_ber` docstring),
  not just here.
- **The shrinkage blend design (running per-call mean, not a true per-pass median requiring a
  prelim candidate pass) was this session's own choice**, made explicitly to stay inside "one
  session's worth" of plumbing per the dev-task's own sizing note. It is a reasonable
  implementation of "shrinkage toward a robust reference," not the only possible one — if item 3
  is ever reopened (it should not be, per §5's decisive result, absent new evidence), a different
  reference design is not automatically ruled out by this session's negative result, though the
  BER finding in Part B argues the mechanism class itself (LLR-magnitude rescaling) is the wrong
  target regardless of the exact reference used.
- **One 21-minute session, one device, one band.** Unchanged from every prior note in this thread.

## 8. Definition of done (dev-task §6)

- [x] `ft8_set_llr_shrinkage(double weight)` implemented, thread-local, default 0.0.
- [x] Weight-0.0 no-op self-check passes (byte-identical `ALL.TXT`, 1284 decodes,
      `hashTableRejectCount=656`, against the pre-Phase-2c artefact) before any other row was
      trusted — checked twice (before and after the temporary K=4/cap2000 revert).
- [x] Weight sweep (0.0/0.25/0.5/0.75/1.0) run on the discovery corpus; matched/total/unique-share
      table reported per weight, per population (135/567/matched-hit control) — §4.1.
- [x] Elapsed time reported against the 15 s budget for at least the highest-cost weight — §4.1
      (570-742 ms/decode across the sweep).
- [x] Gray/sync round-trip verified against known messages before use; result stated explicitly
      (PASS, 6/6, both CRC-14 and full LDPC syndrome) — §2 item 1, no fallback export needed.
- [x] 174-value LLR export added to `candidate_diag.csv` capture, opt-in/default-off, layered on
      C.2 Phase 1's existing toggle — §2 item 2.
- [x] Hard-decision BER reported for 135/567/matched-hit control, separately — §4.2 (567's caveat
      in §7).
- [x] A written verdict against §4's decision rule for Part A (closes — negative at weight 1.0,
      <10 at every other weight), and against §3.5's bands for Part B (≈50%, front-end) — §5.
- [x] Δ matched reached the "negative at any weight" row (weight 1.0), so **the Architect is
      notified per HK-015 before any further session is scoped** — see the QA notification this
      findings doc feeds.
- [ ] `python3 tools/pre_merge_check.py` green (HK-006) — run after this findings doc; see commit
      message / QA follow-up for the result.
- [x] NFR-021: no callsigns or raw message text in anything committed. All test messages used in
      the round-trip verification and BER measurement are Q-prefix synthetic (ITU-unallocated).
      Message text is used internally by both Part B scripts (to re-encode) but never printed or
      written to any committed file — only aggregate BER statistics are. Per-cycle
      `candidate_diag.csv`/`ALL.TXT` outputs (containing real off-air callsigns from the discovery
      corpus, same as every prior C.2/C.3/C.4 session) live under the git-ignored `artefacts/`
      tree, never committed.
- [ ] `git status` clean of any rebuilt `libft8.dll` beyond what this diagnostic branch needs, with
      Captain sign-off before merge (HK-010/HK-011) — the temporary K=4/cap2000 build was reverted
      before this doc was written (§4.1, §6); the committed `libft8.dll` reflects the shipped
      10/140 config plus the two new opt-in diagnostics only. Awaiting Captain sign-off per
      HK-011/HK-010, not yet pushed or merged (HK-014's convention applied to this Developer
      session too, per this thread's established practice).

## 9. Cross-references

- `dev-tasks/2026-07-26-d001-c2-phase2c-shrinkage-trial-and-ber.md` — the task spec this executes.
- `qa/cycleframer-alignment-replay/2026-07-26-1930-architect-c2-phase2a-ruling-revision.md` §5, §6,
  §8 — the shrinkage trial's design, decision rule, and honest caveats this session inherits.
- `qa/cycleframer-alignment-replay/2026-07-26-1830-architect-c2-phase2a-ruling.md` §6, §7 — the
  BER measurement's design, feasibility notes (Gray/sync round-trip unverified until this
  session), and reading bands.
- `qa/cycleframer-alignment-replay/c2_llr_normalization_analysis.py`,
  `c2_phase2_ceiling_rederivation.py` — THE 135 / THE 567 population identities reproduced here
  (not re-derived from first principles).
- `qa/cycleframer-alignment-replay/c2_phase2c_shrinkage_sweep_analysis.py`,
  `c2_phase2c_gray_sync_roundtrip_verify.py`, `c2_phase2c_ber_measurement.py` — this session's own
  analysis scripts.
- `native/ft8_lib_build/patched/ft8/decode.c` — `ftx_normalize_logl` (shrinkage blend),
  `ftx_get_candidate_raw_llr` (new, Part B's raw LLR export).
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c`/`.h` — shim 20260035: `ft8_set_llr_shrinkage`,
  `ft8_set_candidate_diag_llr_capture`, `ft8_get_last_candidate_llr`.
- `src/OpenWSFZ.Ft8/Interop/*.cs`, `src/OpenWSFZ.Ft8/Ft8Decoder.cs`,
  `src/OpenWSFZ.Ft8/Ft8CandidateDiagnostic.cs` — managed wiring for both new toggles.
- `qa/rr-study/d001-param-sweep-2026-07-22/Program.cs` — `--llr-shrinkage-weight`,
  `--candidate-diag-llr` harness flags (deviation from "harness unmodified", same class as C.1's
  `--debug-log` and C.2 Phase 1's `--candidate-diag-csv`).
- `dev-tasks/2026-07-26-d001-c2-phase2-llr-shrinkage.md` §3, §4 — Phase 2b's ship spec; untouched
  by this session, and per §5's decisive result should not be picked up absent new evidence.

---

*Per HK-014's convention as applied to Developer sessions in this thread, nothing is pushed or
merged. Per HK-000/HK-015, this findings doc goes to QA, and — because Δ matched reached the
"negative at any weight" row of §4's decision rule — QA routes this to the Architect before any
further session is scoped, per the dev-task's own Definition of Done.*
