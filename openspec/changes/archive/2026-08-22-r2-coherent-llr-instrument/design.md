## Context

Full derivation: `qa/rr-study/2026-08-19-1850-architect-to-qa-spec-b2-phase1-coherent-
llr-kill-gate.md` ("the Phase 1 spec"). Summary of what changed the shape of this work
during drafting (Phase 1 spec §0): the `C:\Temp` build blocker that made Route B2 look
un-sizeable is gone (R0 vendored the tree); half of Route B2 (`sync_refiner.c`, limb 1)
was already built and has no production call site; and that built half is the half
that has since failed three times (`M4`, `N1`, P-LIVE Stage 2 — see proposal.md Why).
**Route B2's remaining value rests entirely on limb 2** (coherent multi-symbol LLR
formation), which has never been measured. Phase 1 tests limb 2 alone, formed at the
*existing* grid position so that limb 1's death cannot contaminate the result.

This change is itself phased (proposal.md's own distinction): **Phase 0 (2026-08-20,
QA, no native code) built and validated the measurement harness against the then-current
build; Phase 1 (native, 2026-08-20/21 Developer session) built `ft8_coherent_llr_at()`
— shipped, `main` `a420016`, shim `20260043`.** Phase 1's own kill gate (§ below,
`tasks.md` §4.3) then blocked on a validity pre-check, **ROW 0g**, which FIRED on the
merged binary (`qa/rr-study/2026-08-21-1100-qa-to-architect-row0g-fires-phase1-gate-
void.md`): the coherent path collapsed to nearly pure chance (median 79/174 bit errors)
on real audio despite passing a clean-signal synthetic check. Two native defects were
subsequently diagnosed and are fixed together as **Phase B**: **B1**, a raw-PCM
correlation-origin unit-conversion error (`qa/rr-study/2026-08-21-1412-…-origin-
convention-finding-and-spec-b-orig-a.md`, confirmed against known ground truth by
B-orig-A, ROW 1); and **B2**, a cross-window LLR-fusion comparison that is indefensible
on arithmetic grounds alone (raw `fabsf` magnitude compared across differently-scaled
1/2/3-symbol windows — `qa/rr-study/2026-08-21-1525-…-phase-b-origin-and-fusion-fix-
and-row0g-rerun.md` §1.2). Phase B also adds **B4** (Amendment 1,
`qa/rr-study/2026-08-21-1644-…-phase-b-amendment-1-ldpc-decode-llrs-export-and-cascade-
pin.md`), a diagnostic-only export that decodes a caller-supplied LLR vector through
production's own `ftx_normalize_logl` → `bp_decode` → OSD → CRC-14 sequence — inert,
reachable only from tests/harnesses, needed so a future analysis arm (C2, specced
later, not this change) can report CRC-verified decode counts instead of modelled BER-
threshold crossings — and **C1**, a documentation-only pin of the cascade shape (D-B2-1
below) with no code change and no Developer session. The three native items (B1, B2,
B4) share one Developer session and one `FT8_SHIM_VERSION` bump (`20260043` →
`20260044`); C1 is QA's own edit, applied directly in this document, no run required.

The change is one OpenSpec change across all of Phase 0/1/B because it specifies one
capability end-to-end, matching R1's own precedent (build-with-acceptance-criteria);
they are not one *session* of work.

Phase B shipped (`main`-bound branch `feat/r2-coherent-llr-phase-b`, commit `7ed8b0c`)
and arm **B-dt-A** then ran against it: `M0` (mean reported-minus-true SNR on matched
decodes at `true_dt == 0`) moved from `-14.333`/`-13.9 dB` (pre-B1) to `-14.104 dB`
(post-B1) — **+0.229 dB, sub-quantum, i.e. B1 did not move it.** ROW 2 fired
(`qa/rr-study/2026-08-22-1218-…-b-dt-a-results.md`). This is the condition **Amendment
2** (`qa/rr-study/2026-08-21-2311-…-phase-b-amendment-2-snr-terms-getter.md`), as
corrected in full by **Amendment 3**
(`qa/rr-study/2026-08-21-2334-…-phase-b-amendment-3-snr-terms-correction.md`), was
written to require before proceeding: a new diagnostic-only export,
`ft8_get_last_snr_terms`, that exposes the two terms (`signal_db`, `local_noise_db`)
of the per-signal SNR formula that has been unobservable since the `fix-d004-local-
noise-floor` estimator (`FT8_SHIM_VERSION 20260012`) replaced the global noise floor
those terms are computed against. **Amendment 3 retracted Amendment 2's own central
claim** — the error is not a single- vs multi-signal ("crowding") split, it is a
`true_dt == 0` vs `true_dt > 0` split, identifiable from data already on disk (HK-018
fired on the Architect for asserting it "cannot be identified from outside the shim"
when it already had been, by one stratification). `tasks.md` §14-19 specify this
Amendment; §14.1 additionally bundles in the same rebuild a one-line widening of
`ftx_ldpc_decode_llrs`'s degenerate-variance guard (B4's own `decode.c:940`) flagged
in the 2026-08-21 22:09Z QA code review, since both share the one Developer session.

## Goals / Non-Goals

**Goals (Phase 0, this session):**
- Re-derive the exact population Phase 1's gate will run on
  (`plive_population.build_p_live_population(PRIMARY_CORPUS)`, the P-LIVE Stage 2
  population — reference decoded, we did not), reporting CLUSTER counts, not row
  counts, and confirming no population helper truncates via a `limit=` argument
  (HK-021(i)).
- Build the `ber_grid` half of the harness Phase 1 will extend with a second
  (`ber_coh`) extraction call, using only the *existing* `ft8_extract_llrs_at` export.
- Pass a mandatory two-sided sign unit test (ROW 0c) proving the bit-error-counting
  convention this harness reuses is correct in both directions.
- Reproduce Stage 2's own already-published median `ber_grid` (31.03%) within 1.0pp on
  a fresh re-derivation (ROW 0d), certifying the harness before Phase 1 is proposed.

**Goals (Phase 1, shipped 2026-08-21 — specified here, built in that Developer
session):**
- Build `ft8_coherent_llr_at()`: coherent per-candidate LLR formation *at the existing
  grid position*, reusing `sync_refiner.c`'s already-reviewed downconversion.
- Run the pre-registered gate (§ below) on the P-LIVE Stage 2 population and report
  one of ROW 1/2/3/4. **Blocked on ROW 0g, which FIRED against the as-shipped Phase 1
  binary — see Phase B below.**

**Goals (Phase B, native — specified here, not yet built):**
- **B1** — correct `ft8_coherent_llr_at`'s raw-PCM correlation origin: it converts a
  waterfall block index to seconds and uses that directly, but the analysis window
  centre sits `1/time_osr − freq_osr/2 − 0.5` symbols earlier (the look-back buffer +
  multi-symbol window span). Derive the correction from `mon.wf.time_osr`,
  `mon.wf.freq_osr` and `mon.symbol_period` at runtime — never hardcode the resulting
  `-1.0` (at `K_TIME_OSR = K_FREQ_OSR = 2`) as a literal.
- **B2** — normalise each fusion window's per-bit LLRs to a common, window-size-
  independent scale (e.g. divide by that window's own `stddev(mag[])`, guarding
  `scale > 0`) before the cross-`n_syms` `fabsf` magnitude comparison, so the
  comparison selects the most *reliable* candidate rather than the *longest* window.
- **B4** — add `ft8_ldpc_decode_llrs`, a diagnostic-only export in `decode.c` that
  decodes a caller-supplied 174-LLR vector through production's own
  `ftx_normalize_logl` → `bp_decode` → OSD (conditional) → CRC-14 sequence, mirroring
  `decode.c:641-713` exactly. Inert (no production call site); exists so a future
  analysis arm can report CRC-verified message counts on rows already measured, not a
  new population or gate itself.
- Re-run ROW 0g (§ below, unchanged pre-registration) after B1+B2 land, gated by an
  intermediate acceptance step (re-run B-orig-A for B1 alone; the B2 unit test) that
  restores per-fix attribution despite both landing in one Developer session.
- **C1** — pin, in this document (Decision D-B2-1), whether the coherent path replaces
  or falls back behind the grid path in any eventual production wiring. Docs only, no
  Developer session, no run.

**Goals (Amendment 2, corrected by Amendment 3 — specified here, not yet built,
conditional on B-dt-A ROW 2, which has fired):**
- Add `ft8_get_last_snr_terms`, a diagnostic-only, per-decode, index-aligned parallel-
  array export (Decision D11) exposing `signal_db` and `local_noise_db` — the two
  terms of `snr = signal_db - local_noise_db - 26.5f`, computed today at
  `ft8_shim.c:1473-1474` but never separately observable. Read-only; no production
  call site.
- Bundle the `ftx_ldpc_decode_llrs` degenerate-variance guard widening (Decision D12)
  into the same rebuild.
- Run the corrected AC-N5 measurement (`tasks.md` §17.4): S3 (DT sweep) + S8,
  stratified by `true_dt`, reporting which of the two terms carries the
  `true_dt == 0` collapse. No threshold, no pass/fail — the mechanism has not been
  observed yet; a gate on it now would be HK-021 theatre (Amendment 2 §0).

**Non-Goals (any phase):**
- Not wiring `ft8_coherent_llr_at` into `ftx_decode_candidate()` or any production
  decode call — that is Phase 2's scope entirely, gated on Phase 1's ROW 1/ROW 2 (now
  additionally gated on Phase B's ROW 0g re-run passing).
- Not calling `ft8_refine_candidate` from anywhere in this change, diagnostically or
  otherwise (Decision D1). Limb 1 is dead three times over; no phase, including B, may
  import that dependency even for a "coarse position." B1/B2 do not introduce a
  position estimate — B1 is a unit conversion of an *existing* candidate position, B2
  only changes how already-formed LLRs at that position are compared (§1.3 of the
  2026-08-21 15:25Z spec) — so this Non-Goal and Decision D1 are unaffected by Phase B.
- Not re-deriving the `+0.65s` anchor-offset correction — it is REUSED verbatim from
  Stage 2's own Part A (`r2_population.STAGE2_ANCHOR_OFFSET_S`), not re-swept here.
- Not re-measuring `B50` = 11.3% (the July-corpus correction threshold) — reused as-is
  from N1/N5's own citation, flagged as a real but accepted risk (Phase 1 spec §6.2).
- Not the S3b synthetic sweep — HELD, released only on this change's Phase 1 ROW 1/2
  outcome, and not this change's own concern (2026-08-20-1613 ordering doc §3).
- Not building B3 (`out_diag`, the fusion-selection-share diagnostic) — HELD by the
  Captain; Phase B does not build it and does not pre-empt it. B2 is justified on
  arithmetic alone, not on a measurement that only B3 could provide.
- Not running C2 (the CRC-verified re-analysis of Stage 1RE using B4) or drafting C3 —
  both are specced later, after Phase B's binary is merged and its SHA256 pinned; C2
  must never run against an unmerged branch build (the board's own P2/P3/P1a confound).
- Not declaring N5's `4.37%` figure a bound on limb 2 again, anywhere — retired
  permanently by the Captain's 2026-08-21 16:34Z ruling (an ordinary zero, `lambda`
  ≈ 1.97, not evidence of anything about limb 2's ceiling).
- **Amendment 2/3 does NOT reopen H5** (closed gate, standing prohibition), does NOT
  change the SNR formula, and does NOT change suppression or `K_SOFT_SUPP_SNR_*` —
  `DEFECT-snr-reported-gain-error.md` §4 (the correction shape) remains an open
  decision this Amendment does not make. Does NOT license C2 or C3. Does NOT bear on
  ROW 0g/task 4.3/Route B2/B3 — none of those are re-evaluated by this Amendment.

## Decisions

**D1 — Phase 1 forms coherent LLRs at the EXISTING grid position; no dependence on
`ft8_refine_candidate()`'s position estimate.**
Alternative considered: refine first, then form coherent LLRs at the refined position
(the naive "improve limb 1, then add limb 2" order). Rejected — limb 1 is dead three
times over (`M4` ROW 2, `N1` ROW 2, P-LIVE Stage 2 ROW 3/HARM); stacking limb 2 on a
dead limb 1 would make a limb-2 null result ambiguous between "coherent LLRs don't
help" and "the position they were formed at was already wrong," exactly the
interpretability hazard R1 was built to remove for the refiner itself. Forming coherent
LLRs at the grid position makes the two limbs' fates independent by construction.

**D2 — Phase 0's harness reuses `plive_population.build_p_live_population` and
`extract_llrs_ctypes.ExtractLLRs`/`hard_decision_ber` verbatim; it does not
reimplement population construction or bit-error counting.**
HK-018: both are already built, already validated across Stage 1/1R/2, and a second,
divergent implementation of either would risk two different definitions of "the
population" or "an error" existing in the same codebase for the same capability.
`r2_ber_grid.py` is a genuinely new module (it drops the refiner call Stage 2's own
`measure_stage2_row` made — D1 above — so it cannot be a call-for-call reuse of that
function), but every primitive it calls is reused, not rewritten.

**D3 — ROW 0c (sign unit test)'s SIGNAL sub-check uses real P-HIT rows at Stage 2's own
corrected anchor, not a synthetic signal at its own encoder-specified position.**
The first construction of this check used `qa/rr-study/synth/encoder.encode_message`
at a clean high SNR, extracted at the exact `(freq_hz, dt_s)` passed to the encoder,
expecting `n_err ≈ 0`. **It failed**: mean `n_err ≈ 70/174`, far from clean. A
fine-grained noiseless `dt` sweep isolated the cause: the synth encoder's `dt_s`
parameter and `ft8_extract_llrs_at`'s own `time_offset_s` convention are offset from
each other by roughly +0.1–0.2s — a real, repeatable gap, but a *different* one from
the already-known `+0.65s` live-capture-chain offset (`AO1`/`D1`/Stage 2), with no
prior measurement anywhere in this project. Chasing that gap to a precise constant is
its own investigation (a synth-harness question, not a Phase 0 or Phase 1 question) and
is explicitly out of scope here — flagged to the Architect in the QA report, not solved
in this change. The construction actually shipped sidesteps the question entirely:
real P-HIT rows (a cycle both decoders decoded, so ground truth is real, off-air audio)
at the anchor+offset convention Stage 2's own sign test already validated. See
`r2_sign_test.py`'s module docstring for the full account, kept in the code per
HK-022 rather than only in this document.

**D4 — ROW 0c's SIGNAL sub-check gates on the MEDIAN of `n_err`, not the mean.**
A first pass gated on the mean and FAILED (22.78, bar 15) on the same 18-trial sample
whose median was 12.5 (PASS). The distribution is right-skewed by construction: most
P-HIT rows extract near-clean at the corrected anchor, a minority sit near chance
(rows where the WSJT-X-reported anchor itself carries more slop than the single global
`+0.65s` correction absorbs — the same phenomenon Stage 2's own Part A found and
reported as a *median*, never a mean, throughout this project's history for this exact
population). Both statistics are computed and reported in the harness output (HK-022 —
report what was measured, don't silently pick whichever passes); only the median gates.

**D5 — Mechanical definitions for Phase 1's gate, fixed now (HK-021(o), reused
verbatim from the Phase 1 spec §3 rather than re-derived):**
- A codeword is 174 bits ⇒ the BER quantum is `1/174 = 0.575pp`. The correction
  threshold `B50 = 11.3%` does not land on a quantum, so **correctable ⇔ `n_err ≤ 19`**
  (10.92%, the conservative side of 11.3%) — an integer bit-count comparison, never a
  float comparison against `0.113`. `r2_ber_grid.py` reports `n_err_grid` as an int for
  exactly this reason.
- `f_net`'s quantum on the 3,916-cluster P-LIVE population is `1/3,916 = 0.0255%`.
- Resolvable distance (HK-021(m), stated while drafting, unchanged from the Phase 1
  spec): at `f_net ≈ 10%`, cluster-level SE ≈ 0.48%, CI half-width ≈ 0.94% — the 5%
  and 15% gate bars sit ~10 half-widths apart. If the delivered cluster count at Phase
  1 time is below 1,500, STOP and escalate rather than running (the bars stop
  separating well before that floor, but 1,500 is the pre-registered trigger).
- HK-021(l): `f_net` is signed (nets the reverse crossings); never gate on `n_in` alone.

**D6 — ROW ordering for Phase 1's gate is unchanged from the Phase 1 spec §3, restated
here for one-document completeness (not re-derived):** ROW 1 (`CI_lo(f_net) > 15%`) →
ROW 2 (`CI_lo(f_net) > 5%`, not ROW 1) → ROW 3 (`CI_hi(f_net) < 5%`) → ROW 4 (residue).
Exclusivity: ROW 1 ⊂ ROW 2's condition, evaluated first; ROW 2 requires `CI_lo > 5%`,
ROW 3 requires `CI_hi < 5%`, and `CI_lo ≤ CI_hi` ⇒ they cannot both hold; ROW 4 is the
complement.

**D7 — Phase 0 ships no native code and touches no `src/` file.** `ft8_coherent_llr_at`
does not exist in the current binary (confirmed: `ft8_shim.h` grepped, no such symbol;
DLL SHA256 re-verified at `6890d84c...`, shim `20260042`, matching the pin already in
production use — no rebuild happened). HK-011 is not engaged by this change's Phase 0
scope; it is engaged the moment Phase 1's native tasks begin, and that requires a
Captain-opened Developer session this change does not authorise.

**D-B2-1 — the coherent path is a FALLBACK LEG, never a replacement.** (Amendment 1,
C1 — QA's own edit, docs only, no run, no Developer session.) Production decodes with
the grid LLRs first. Only where the decode fails its CRC-14 does the coherent
extraction run, on that candidate, and emit only if *its* CRC-14 passes. Consequences,
and they are the reason this is pinned before any integration work: (a) rows the grid
path already decodes **cannot be lost** — the second leg never runs on them, so
`f_break` is not a recall cost under this shape; (b) the trigger is a **real CRC-14,
not a modelled BER threshold** — no oracle, nothing estimated at run time; (c) false
emissions stay bounded by the same CRC-14 the existing path relies on; (d) the
remaining cost is **compute** — measured 2026-08-21: coherent **8.32 ms**/call vs grid
**4.22 ms**/call, second leg on the miss population only. ⚠️ A cascade protects rows
the grid **actually** decodes; `f_break`'s breakable subset is defined by the B50
model, and B50 is not the decoder. C2 (specced later, not this change) settles that
gap. This does **not** amend Decision D1 above — the 2026-08-21 12:01Z spec §5 ruling on
D1 itself remains the Captain's and remains owed, and is not pre-empted or needed here.

**D8 — B1's origin correction is derived from `mon.wf.time_osr`/`mon.wf.freq_osr`/
`mon.symbol_period` at runtime, never hardcoded as a literal.** `1/time_osr −
freq_osr/2 − 0.5` evaluates to `-1.0` symbol at production's own
`K_TIME_OSR = K_FREQ_OSR = 2`, matching the empirically-calibrated
`TIME_ORIGIN_CORRECTION_SAMPLES_2K = -SPS_2K` constant the Python prototype
(`qa/rr-study/n2-coherent-llr-extractor/coherent_extract.py:227`) has carried since the
N2 session — the prototype was correct all along; the C port dropped it during the
port to `coherent_llr.c`. A hardcoded literal would silently go wrong if
`K_TIME_OSR`/`K_FREQ_OSR` ever changed; the derived form documents itself and stays
correct. The correction is applied to `origin_sample_f` (`coherent_llr.c:437`) before
`monitor_free(&mon)` frees the three source values, and must carry a comment naming
*why* it exists (the look-back window + the `b + (s+1)/T − F/2` window-centre
derivation), pointing at the 2026-08-21 14:12Z finding document — a bare unexplained
constant is how this defect survived the port in the first place.

**D9 — B2 standardises each fusion window by its OWN magnitude spread, not by
restricting `n_syms`.** Alternative considered and rejected: forcing `n_syms = 1`
everywhere, which would remove the multi-symbol coherence that is the entire premise
of Route B2's limb 2 and would silently convert the gate into a test of something not
being proposed. Instead, before the cross-`n_syms` comparison at `coherent_llr.c:480`
(`if (n_syms == 1 || fabsf(candidate) > fabsf(out_log174[gb]))`), each window's per-bit
LLRs are divided by that window's own `stddev(mag[0..n_tones))`, guarded `scale > 0`
(leaving a degenerate window's LLRs unscaled, or excluded, rather than dividing by
zero). Absolute scale does not matter for the final output — `coh_normalize_logl()`
renormalises the whole 174-vector at the end regardless — only the *relative* scale
between windows during the comparison is load-bearing. A mandatory unit test (design
Requirement, `specs/ft8-coherent-llr/spec.md`) constructs two windows with equal
discriminative information but different absolute scale and asserts their normalised
LLRs agree while their pre-normalisation values do not, so this arithmetic is verified
directly and does not depend on B3 (which is HELD).

**D10 — B4 lives in `decode.c`, gets no `Ft8LibInterop`/`IFt8NativeInterop` C# binding,
and duplicates no production arithmetic.** Forced, not a preference:
`ftx_normalize_logl` (`decode.c:391`) and `osd_decode` (`decode.c:507`) are both
`static` in `decode.c`, so the probe must live there — exactly where
`ftx_extract_likelihood_at` (`decode.c:838`) already lives, with a thin wrapper in
`ft8_shim.c` (the established two-file pattern for both existing diagnostic exports).
Nothing is un-static'd, `osd_decode` is not moved, and no CRC or normalisation
arithmetic is copied into the shim — a copy that drifts from production would silently
answer a different question than the one asked. No C# binding is added, following
`n1-extract-llrs-at-position`'s own considered precedent (that change's D5): the
consumer is QA's Python `ctypes` harness (future C2) and the Developer session's own
native/Python smoke tests, exactly as `ft8_extract_llrs_at` already established — a
managed P/Invoke surface would be unused production-adjacent code for a diagnostic-only
probe with no C# caller.

**D11 — `ft8_get_last_snr_terms` is a parallel array, per-decode (not per-cycle), and
exports BOTH terms — three design decisions, each an identifiability requirement, not
a preference (Amendment 2 §2.2, unchanged by Amendment 3 §7).**
(a) A parallel array, not a new `FT8Result` field — a struct field is an ABI break
with managed-marshalling consequences at every existing call site; the parallel-array
getter is the pattern `ft8_get_last_candidate_counts`/`ft8_get_last_llr_stats` already
establish. (b) Per-decode, not a per-cycle aggregate — the open anomaly (the S8
650 Hz/1650 Hz split) is a BETWEEN-DECODE, WITHIN-CYCLE difference; an aggregate is
mathematically incapable of resolving it, and the B-dt-A finding (the collapse is keyed
to `true_dt`, a per-decode property carried in `FT8Result.dt`) strengthens this rather
than weakening it. (c) Both terms, not just the noise floor — `signal_db` is nominally
recoverable as `snr + local_noise_db + 26.5`, but `FT8Result.snr` is int-rounded
(`ft8_shim.c:1479`), so that recovery is only good to ±0.5 dB and is not an
INDEPENDENT check: it assumes the very formula under test (this is what makes AC-N2 a
real identifiability check rather than a tautology). Contract for the two NULL cases,
corrected by Amendment 3 §4(c): either pointer may be NULL to request only the other
array; if both are NULL, the function writes nothing and returns the count it would
have written.

**D12 — the `ftx_ldpc_decode_llrs` degenerate-variance guard widening rides the same
rebuild as D11, because it is a one-line fix discovered auditing B4's own code in the
2026-08-21 22:09Z QA review, and Amendment 2 §7 explicitly folds it in ("one rebuild,
not two") rather than opening a second Developer session for it.** `variance == 0.0f`
(exact equality) is narrower than its sibling `coh_window_scale`'s own guard
(`!(variance > 0.0f)`, added by B2 in the SAME diff) — a near-constant-but-not-bit-
exact input could produce a small float-cancellation NEGATIVE variance, slip past the
exact-equality guard, and reach `sqrtf(24.0f/variance)`, producing NaN and
contradicting B4-d's own "no crash, no NaN" charter. Widening it to match its sibling
closes that gap. This is purely a hardening of an already-inert diagnostic export
(`ft8_ldpc_decode_llrs` has no production call site) — it does not change any value
B4 returns on any input that previously passed the guard.

## Risks / Trade-offs

- **[Risk, named in the Phase 1 spec, restated] The shared-machinery risk.** Limb 2
  reuses `sync_refiner.c`'s existing downconversion. Decision D1 stops a bad *position
  estimate* from propagating (coherent LLRs are formed at the grid position, not a
  refined one), but if the downconversion itself is defective on real signals rather
  than merely on its search, limb 2 inherits that. Mitigation: Phase 1's own ROW 0c
  (ft8_coherent_llr_at's sign test, not this change's Phase 0 sign test) is the guard,
  and per the Phase 1 spec it must be two-sided for exactly this reason.
- **[Risk, discovered this session] The synth encoder/extractor position-convention
  gap (D3).** Unresolved and out of scope. If a future change needs a *synthetic*
  known-good signal at a precisely-known extraction position (Phase 1's own harness
  extension might want this for a cleaner AC-style sign test on the coherent limb),
  this gap will need to be chased down first. Flagged, not blocking Phase 0's own ROW
  0c (which sidesteps it via D3's real-data construction).
- **[Trade-off] `B50 = 11.3%` is a July-corpus figure (n = 126 measured), reused
  without re-measurement.** Carried forward from the Phase 1 spec (§6.2) rather than
  re-litigated here; it is doing real work in `n_err ≤ 19`. A re-measurement is a
  defensible ask and would cost a re-run, not a rebuild, if the Captain wants it first.
- **[Trade-off] The 8.9% no-candidate misses are outside Phase 1's addressable
  population by construction** (RC1's decomposition — 3.1% out-of-band, 8.9%
  no-candidate, 87.9% candidate-present-and-failed). The ~37pp ceiling this implies for
  Route B2's maximum possible recall gain is a Phase 1 spec quantity (§2), not
  recomputed in this change; do not let it be dropped when a Phase 1 result is quoted.
- **[Risk, Phase B] That C1 causes B-pos-A's residual `d_global = -6.0` bits (grid vs.
  coherent at own-best position, real rows) is UNPROVEN — B2 is justified on
  arithmetic alone.** The measurement that would prove it (a fusion selection-share
  diagnostic) is B3, which stays HELD. If ROW 0g still fires after Phase B lands, that
  is evidence about the residual, not a refutation of B2's own justification — do not
  report a Phase B outcome as though C1 were a diagnosed cause either way.
- **[Risk, Phase B] Fixing B1+B2 makes the ROW 0g gate runnable again; it does not by
  itself make Route B2 viable.** Standing scale arithmetic cuts against it: misses sit
  at BER median 44.0% against BP+OSD's ~11.3% correction threshold, so converting a
  miss needs recovering ~57 of 174 bits, while the measured gap between grid and
  coherent at the *correct* position (B-pos-A) is 6 bits. The Architect's own recorded
  prediction for ROW 0g-2 passing after Phase B is ~35%.
- **[Trade-off, Phase B] B4's CRC-verified count may come back zero.** If it does,
  limb 2's entire prior "conversion" reading (Stage 1RE's `f_net`) was the B50
  threshold's geometry, not a real decode gain, and Route B2's value collapses to
  whatever Phase B's origin fix alone recovers. That outcome must be reportable without
  it being treated as a failure of QA or of B4's construction (Amendment 1 §G).
- **[Risk, Amendment 2/3] AC-N5 is REPORTED, not gated, because the DT mechanism has
  not been observed yet — a threshold now would be HK-021 theatre.** A third mechanism
  proposal may be needed after AC-N5 runs (the Architect's own recorded confidence:
  40%, unaffected by the retraction). Two prior mechanism proposals on this same
  dataset (neighbour distance, single-vs-multi-signal crowding) were both refuted by
  data already gathered — Amendment 3 §6 flags its own remaining predictions for a
  calibration discount as a result. **Boundary shape between DT 0.0 and 0.2/0.3, and
  negative DT, are entirely unmeasured** (`s3b-dt-boundary.json`, built-not-run) —
  AC-N5's own S3/S8 measurement must not be used to interpolate across that gap
  (HK-026); if the mechanism lands there, the report must say so and name a wider-
  aperture instrument rather than extrapolate.

## Migration Plan

No runtime migration in Phase 0 — nothing production-facing exists yet. Phase 1,
built 2026-08-21, is diagnostic-only (same discipline as R1's `ft8_refine_candidate`
and the existing `ft8_extract_llrs_at`): `FT8_SHIM_VERSION`/`ExpectedShimVersion`
advanced to `20260043`, all three platform binaries rebuilt, no production call site
was added. Phase B (B1, B2, B4) is the same discipline again: one more
`FT8_SHIM_VERSION` bump (`20260043` → `20260044`), all three platforms rebuilt, zero
production call sites added or changed — B1/B2 correct `ft8_coherent_llr_at`'s own
existing (diagnostic-only) behaviour in place, and B4 is a wholly new diagnostic
export. Rollback of Phase B is a plain `git revert` of the fix + B4-export commit;
Phase 0's harness and Phase 1's export both remain structurally valid regardless (B1/B2
change *values* `ft8_coherent_llr_at` returns, not its signature or its Phase 0/1
dependents' call shape). Phase 2 (production wiring) does not start until Phase 1's
gate (post-Phase-B) reports ROW 1 or ROW 2 and the Captain has made the explicit
re-decision the Phase 1 spec names for a ROW 2 outcome (§3: "the project's stated
purpose is not met by this outcome and he should hear that in those words"). C2 (the
B4-based re-analysis) and Phase 2 are independent forks off Phase B landing — C2 does
not require a ROW 1/2 gate outcome, only a merged, SHA256-pinned binary.

Amendment 2/3 (D11/D12) is the same discipline again, a third time: one more
`FT8_SHIM_VERSION` bump (`20260044` → `20260045`), all three platforms rebuilt, zero
production call sites added or changed. `ft8_get_last_snr_terms` is wholly new and
diagnostic-only; the guard widening (D12) only tightens an already-inert export's own
input validation and changes no value on any input that previously passed. Rollback is
a plain `git revert`; nothing downstream of Phase B (§11's still-unrun acceptance
ordering, task 4.3's still-void kill gate) depends on this Amendment landing, and this
Amendment does not depend on §11 having run either — they are independent forks off
the same Phase B binary, same as C2/Phase 2 above.

## Open Questions

1. **Exact placement of `ft8_coherent_llr_at`'s C source** — RESOLVED, Phase 1:
   `native/ft8_lib_vendor/refine/coherent_llr.c`, a new sibling file (not appended to
   `sync_refiner.c` itself).
2. **Whether `r2_ber_grid.py` gains the `ber_coh`/second-extraction-call limb as an
   edit to this same module, or a new sibling module**, once `f_net`/`C_ber` (`tasks.md`
   §4.3) is finally run — a QA-tooling placement choice with no bearing on the gate
   itself, still open, deferred until after Phase B's ROW 0g re-run passes (still
   blocked, not decided by Phase B).
3. **Whether the synth encoder/extractor position-convention gap (D3/Risks) is ever
   chased down**, and if so whether it belongs to this change, a `synth/` defect report,
   or a standalone QA note — not decided here; flagged in the QA report for the
   Architect. Still open; Phase B's B-orig-A acceptance check (real P-HIT rows, not
   synthetic) sidesteps it the same way ROW 0c did.
4. **[New, Phase B] Whether `ft8_ldpc_decode_llrs`'s OSD-vs-BP split (`out_path` per
   row) changes how C2 is eventually specced** — Amendment 1 specs OSD IN because
   production runs it, flags that if OSD dominates the result the arm may need a
   with/without split, and requires `out_path` be reported per row precisely so that
   split remains possible without re-running anything. Not decided here; C2's own
   pre-registration (specced later, not this change) makes the call.
5. **[New, Amendment 2/3] What fixes the `true_dt == 0` SNR collapse, once AC-N5
   localises it to a term** — not decided here. This Amendment builds and runs the
   instrument only; a correction (to `DEFECT-snr-reported-gain-error.md` §4's still-
   open shape decision, or elsewhere) earns its own pre-registration, per the same
   discipline Amendment 2 §0 states for itself ("this is an instrument, not an arm").
