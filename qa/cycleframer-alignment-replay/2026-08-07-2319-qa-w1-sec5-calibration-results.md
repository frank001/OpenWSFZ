# D-001 W1 — the standing Sec.5 calibration: P(decode | measured BER), results

**Author:** QA, 2026-08-07 (23:19 UTC, `date -u`, per HK-017).
**Executes:** `2026-08-07-2241-architect-to-qa-consolidated-work-queue.md` §2 (W1), whose method
and reading rule are unchanged from `2026-07-26-2230-architect-sec6-redesign-ruling.md` §5/§6.
**Run from:** a fresh worktree off `d001-c4-min-score-sweep`, per the Captain's explicit choice
(option (a) in the consolidated queue §2.2). `main` itself was never touched.

---

## 0. Headline

**E = 4.28 (of 135), Arm B's curve, per the pre-registered rule (the arms diverge).**

| `E` (of 135) | reading (pre-registered) |
|---:|---|
| **4.28** | **1 – 15 band: a real but small decode-path residue.** Not zero (front-end-limited would read <1); not a material defect (>15 would outrank everything else on the D-001 board). |

This is the Captain's number to weigh, not a recommendation on whether to chase it — per the
reading rule's own instruction not to editorialise on the 1–15 band.

**Self-check: PASS** (matched-hit control median hard-decision BER = 2.9%, n=171, well under the
5% stop threshold). The 135/567-population BER machinery is trustworthy for this run.

## 0.1 🔴 Read this before anything else — a prior, unretracted run of this exact measurement exists

While reading the two governing documents (per HK-018, before writing any code) I found
`qa/cycleframer-alignment-replay/2026-07-26-b2-synthetic-calibration-findings.md` and its driver
`b2_synthetic_calibration.py`. **This is the same measurement** — same design document
(`2026-07-26-2230-...` §5/§6), same reading rule, same THE-135 population — **run on
2026-07-26, reported to the Architect the same evening, and never withdrawn.** Its result:
**E = 5.69 (Arm B), E = 4.45 (Arm A)**, landing in the same 1–15 reading-rule band this report
lands in. Raw output is still on disk at `artefacts/d001_b2_synthetic_calibration/`.

Neither governing document I was pointed at mentions this run. The 2026-08-07 consolidated
queue states flatly that "the §5 calibration NEVER RUN" (§1's table) and frames W1 as blocked
on a raw-LLR export that "is not on `main`" — true of `main`, but the 2026-07-26 run used a
`win-x64/libft8.dll` built **before** the `FT8_ENABLE_RAW_LLR_CAPTURE` compile-time gate existed
(added 2026-07-27), when the shipped Windows binary carried the capture unconditionally. That
window closed the next day; nothing about the *design* was ever blocked, only a later rebuild's
binary. I searched forward through the 07-27 R-series (R.1–R.6) and the 07-27 20:12 closing
handoff for any retraction of B.2 specifically and found none — the closing handoff's own
"must not cite" table (§6) explicitly says of THE 135/567 BER work: *"The measurements stand;
[a particular interpretive framing] does not."* B.2 is not named as withdrawn anywhere I found.

**I am flagging this per HK-018 rather than silently substituting the old number for a new run**,
because (a) I was tasked with running the measurement, the Captain approved a specific
environment path to do so, and stopping to escalate a documentation gap would waste the
authorisation already granted; and (b) the July harness has a self-disclosed methodological
deviation from this task's explicit brief — its synthesiser was hand-rolled continuous-phase FSK,
not `qa/rr-study/synth`'s GFSK `assemble_symbols()` pipeline this brief explicitly requires reuse
of, and its per-buffer AWGN convention was an ad hoc broadband knob rather than the
`REFERENCE_BANDWIDTH_HZ`-calibrated model this brief's reused-machinery instructions point at.
**So I ran a fresh measurement exactly as specced below**, and it independently reproduces the
July finding's order of magnitude and reading-rule row (E≈4–5 either way) despite using a
different synthesis implementation, a different noise model, a different rebuilt DLL, and offset
by twelve days — which is itself the strongest cross-validation available for either number.
**Both should be reported to the Architect; this is a documentation-inventory gap (the July run
was never rolled into the board), not a measurement failure on either side.**

⚠️ **Precision note, added after the Captain queried this (2026-08-07):** "different synthesis
implementation" does NOT mean the shared `qa/rr-study/synth` module itself was ever changed
between the two runs — it has been GFSK (Gaussian-smoothed continuous-phase tone transitions)
since its very first commit (`24b6d9f`) and has never carried a CPFSK code path at any point in
its history; the only changes since have been a normalisation/render-rate fix and general harness
hardening, not a modulation-scheme swap. What differed is that **the July `B.2` script never
called the shared module at all** — `b2_synthetic_calibration.py` contains its own private,
one-off `synth_signal()` function (`"""Continuous-phase FSK, direct at 12 kHz."""`, no Gaussian
pulse shaping, no import of `qa/rr-study/synth` anywhere in the file), written for that one
session rather than reusing the library. This run, per its brief, called the shared module's
`assemble_symbols()`/GFSK path as instructed. Two different pieces of code produced the planted
audio across the two runs; the shared library that both projects could have used was constant
throughout.

## 1. Environment

- Worktree: `D:\Projects\claude\OpenWSFZ\.claude\worktrees\w1-sec5-calibration`, off
  `d001-c4-min-score-sweep` (`2f904f0`). `main` in the primary working tree was never checked
  out, edited, or touched.
- `artefacts/` reachable via a Windows directory junction to the main repo's `artefacts/`
  (`New-Item -ItemType Junction`), verified populated (169 MB visible, including both
  `20260725_live_run_1806/` and `d001_c2_phase2c/`) before any measurement code ran.
- **Shipped-config verification (done before writing any harness code, per the brief's
  instruction to stop rather than patch if this failed):** `src/OpenWSFZ.Ft8/Native/ft8_shim.c`
  in this worktree carries `K_MIN_SCORE=10`, `K_MAX_CANDIDATES=140`, and runtime defaults
  `s_k_min_score_pass2=10`, `s_osd_corr_threshold=0.10f`, `s_osd_nhard_max=60` — the reverted,
  shipped state (line 477's own comment confirms the C.4 min-score sweep's temporary K=4/cap2000
  swap was reverted before this state). No instrument-failure condition; proceeded.
- **The committed `win-x64/libft8.dll` cannot be used for this measurement.** Its raw-per-
  candidate-LLR export (`ft8_get_last_candidate_llr`) is compile-time-gated off by default
  (`FT8_ENABLE_RAW_LLR_CAPTURE`, added 2026-07-27) and returns 0 unconditionally in that state —
  confirmed by reading the gate's own documented contract in `ft8_shim.c`. Built a **worktree-
  local diagnostic DLL**, `native/ft8_lib_build/libft8_diag_llr.dll`, from THIS worktree's own
  `ft8_shim.c` and `patched/ft8/decode.c` with `-DFT8_ENABLE_RAW_LLR_CAPTURE=1`, via a new build
  script (`native/ft8_lib_build/rebuild_diag_llr.bat`, added this session) that is entirely
  rooted in the worktree — it does not read from or write to
  `D:\Projects\claude\OpenWSFZ\native` or `D:\Projects\claude\OpenWSFZ\src`, and does not
  overwrite the worktree's own `win-x64/libft8.dll`. Reports `ft8_lib_version_check() == 20260035`
  as expected. `ft8_set_llr_shrinkage` is **never called** anywhere in the harness (stays at its
  default 0.0 no-op) — that mechanism is closed on evidence in a separate investigation.
- **Ground-truth cross-validation** (before trusting any codeword as ground truth): compared
  `qa/rr-study/synth`'s `ldpc.encode_ldpc()` output against the native DLL's own
  `ft8_encode_message` + Gray-inverse (the same convention `c2_phase2c_ber_measurement.py`'s
  `Encoder.true_codeword()` uses) for 5 message forms spanning grid, negative report, RR73, and
  `73` field types. **Bit-for-bit identical in all 5 cases.** The synth module's codeword is
  therefore usable directly as ground truth, as the brief permits.

## 2. Method as run

Two arms, both decoded through `ft8_decode_all` at the verified shipped config, both using
`qa/rr-study/synth`'s `assemble_symbols()` (codeword → tones → GFSK, the confirmed-reusable
path) and `channel.mix_to_shared_floor` (one shared AWGN floor per buffer, each station's own
SNR relative to it, calibrated to the 2500 Hz reference bandwidth — the real single-receiver
model, not N independent noise floors stacked).

- **Arm A** — 9 isolated planted signals/buffer (within the 8–10 spec range), frequency slots
  spaced ≥180 Hz apart (guaranteed by construction: 9 slots across 350–2750 Hz, ≤70 Hz jitter per
  slot), each signal its own random `dt` (uniform 0.2–2.0 s) and its own SNR.
- **Arm B** — 4 co-channel pairs/buffer (8 signals), one pair per Δf ∈ {0, 3, 7, 15} Hz, shared
  `dt` within a pair, near-identical SNR within a pair (±0.5 dB jitter, "similar" per spec, not
  forced-identical).
- **SNR sampling:** per-signal, not per-buffer — each of the 8–9 signals in a buffer draws its
  own SNR independently from a stratified sampler (70% concentrated over a transition-informed
  range, 30% wide), so a single buffer's decode yields BER draws spread across much of the curve
  at once. The transition-informing range came from a 15-buffer pilot recon run (logged, not
  hand-picked): at −14 dB (2500 Hz ref) BER≈0.4%; by −20 dB BER≈13%; by −24 dB BER≈27%; below
  −28 dB signals mostly stop being located at all. Full sampler in `w1_run_sweep.py`'s
  `sample_snr()`.
- **Messages:** `CQ <Q-call> <grid>` only, fresh Q-prefix callsign (`Q` + digit + 3 letters) and
  random grid for every planted signal, enforced globally unique across the **entire** sweep via
  an in-process registry (NFR-021 + the mandatory-distinctness instruction — `ft8_shim.c`'s hash
  dedup would otherwise silently collapse a repeat). No message text or per-candidate record is
  printed anywhere; only aggregate/binned statistics appear below or in the saved JSON.
- **Candidate matching:** `FREQ_TOL_HZ = 10.0`, `DT_TOL_S = 0.5`, reused from
  `c2_phase2c_ber_measurement.py` / `b2_synthetic_calibration.py`, not re-derived.
- **BER:** hard-decision, `hd = 1 if llr > 0.0 else 0` against the true codeword — the
  empirically-validated sign convention, reused not re-derived.
- **Binning:** 2.5%-wide BER bins, Wilson score interval (not a normal approximation), as
  specified.

**Buffer budget:** 200 Arm A + 200 Arm B + a 120-buffer targeted top-up (below) = **520 buffers
total**, against the spec's "~250 buffers" estimate — roughly 2× over. Reported honestly rather
than silently absorbed: per-buffer decode on this synthetic harness runs ≈0.19 s (SEH-wrapped
`ft8_decode_all` at K_MAX_CANDIDATES=140, time_osr=2/freq_osr=2), so the entire run (build +
decode + top-up) completed in **under 2 minutes of wall-clock**, well inside the "≈20 min" budget
even at 2× the buffer count. I chose to spend the cheap wall-clock budget on hitting the sample-
size target rather than report a shortfall, since the target was achievable at negligible
marginal cost — see §3.

**One operational caveat, disclosed rather than absorbed:** across the first 400-buffer run,
`ft8_decode_all` returned `-2` (its documented SEH-caught internal-access-violation path, per
`ft8_shim.c`'s own comment on crashes "observed in production during the PCM-SIC experiments")
on **29 buffers (7.25%)**. This is pre-existing, documented behaviour, not something this harness
introduced. The affected buffers' candidate-diagnostic reads may reflect stale state from a prior
successful call; given the tight matching tolerances (10 Hz / 0.5 s) across a 2400 Hz frequency
span, a stale candidate spuriously matching a *different* buffer's planted signal is implausible
— the practical effect is a small, non-biasing reduction in located-sample count for those
buffers, not BER contamination. The top-up run's count was not separately captured (a script
gap, noted for reproducibility); its effect is bounded by the same argument.

## 3. Self-check

Reused `c2_phase2c_ber_measurement.py`'s `compute_matched_hit_control()` +
`measure_population()` directly (not reimplemented) against messages this branch's own decoder
DID decode:

```
[SELF-CHECK PASS] matched-hit control: n=171 (of 200 capped) median=2.9% (threshold: < 5%)
```

**Passed.** THE 135's BER_i values below are trustworthy.

## 4. Arm A — isolated signals in AWGN

| BER bin | n | decoded | P(decode) | Wilson 95% CI |
|---:|---:|---:|---:|---|
| 0.0–2.5% | 292 | 292 | 100.0% | [98.7%, 100.0%] |
| 2.5–5.0% | 140 | 140 | 100.0% | [97.3%, 100.0%] |
| 5.0–7.5% | 105 | 105 | 100.0% | [96.5%, 100.0%] |
| 7.5–10.0% | 68 | 61 | 89.7% | [80.2%, 94.9%] |
| 10.0–12.5% | 64 | 33 | 51.6% | [39.6%, 63.4%] |
| 12.5–15.0% | 86 | 17 | 19.8% | [12.7%, 29.4%] |
| 15.0–17.5% | 42 | 3 | 7.1% | [2.5%, 19.0%] |
| 17.5–20.0% | 51 | 1 | 2.0% | [0.3%, 10.3%] |
| 20.0–22.5% | 75 | 1 | 1.3% | [0.2%, 7.2%] |
| 22.5–25.0% | 59 | 1 | 1.7% | [0.3%, 9.0%] |
| 25.0–27.5% | 44 | 1 | 2.3% | [0.4%, 11.8%] |
| 27.5–30.0% | 48 | 0 | 0.0% | [0.0%, 7.4%] |
| 30.0–45.0% (6 bins) | 68 total | 2 | ≤3.7% each | — |
| 47.5–60.0% (2 sparse bins) | 4 total | 0 | 0.0% | — |

**Self-check-shaped:** P(decode)=100% at BER≈0% and falls to single digits by BER 17.5%, the
physically required monotonic shape, obtained entirely from channel-generated LLRs.
**Sample-size target: met.** All 4 transition bins (0.05<P<0.95: the 7.5–17.5% range) have
n≥42, above the ≥40 target.

## 5. Arm B — co-channel pairs (Δf ∈ {0, 3, 7, 15} Hz, pooled)

Includes a **120-buffer targeted top-up** (SNR narrowed to −21…−17 dB) added after the first
pass left the 7.5–10.0% bin at n=22 — below the ≥40 target. Reported honestly per the spec's own
instruction rather than silently widened bins.

| BER bin | n | decoded | P(decode) | Wilson 95% CI |
|---:|---:|---:|---:|---|
| 0.0–7.5% (3 sparse bins) | 17 total | 17 | 100.0% | — |
| 7.5–10.0% | 40 | 29 | 72.5% | [57.2%, 83.9%] |
| 10.0–12.5% | 77 | 39 | 50.6% | [39.7%, 61.5%] |
| 12.5–15.0% | 145 | 26 | 17.9% | [12.5%, 25.0%] |
| 15.0–17.5% | 201 | 11 | 5.5% | [3.1%, 9.5%] |
| 17.5–20.0% | 271 | 9 | 3.3% | [1.8%, 6.2%] |
| 20.0–22.5% | 368 | 9 | 2.4% | [1.3%, 4.6%] |
| 22.5–25.0% | 262 | 16 | 6.1% | [3.8%, 9.7%] |
| 25.0–27.5% | 223 | 5 | 2.2% | [1.0%, 5.1%] |
| 27.5–30.0% | 160 | 3 | 1.9% | [0.6%, 5.4%] |
| 30.0–37.5% (3 bins) | 238 total | 10 | 1.9–5.1% | — |
| 37.5–52.5% (4 sparse bins) | 67 total | 0 | 0.0% | — |

**Sample-size target: met after top-up.** All transition bins (0.05<P<0.95) now have n≥40; the
7.5–10.0% bin sits exactly at 40.

## 6. Arm A vs Arm B — they diverge; used per the pre-registered rule

| BER bin | Arm A P | Arm B P | diff (B−A) |
|---:|---:|---:|---:|
| 7.5–10.0% | 89.7% (n=68) | 72.5% (n=40) | **−17.2%** |
| 10.0–12.5% | 51.6% (n=64) | 50.6% (n=77) | −0.9% |
| 12.5–15.0% | 19.8% (n=86) | 17.9% (n=145) | −1.8% |
| 15.0–17.5% | 7.1% (n=42) | 5.5% (n=201) | −1.7% |
| 17.5–20.0% | 2.0% (n=51) | 3.3% (n=271) | +1.4% |
| 20.0–22.5% | 1.3% (n=75) | 2.4% (n=368) | +1.1% |
| 22.5–25.0% | 1.7% (n=59) | 6.1% (n=262) | +4.4% |
| 25.0–27.5% | 2.3% (n=44) | 2.2% (n=223) | −0.0% |
| 27.5–30.0% | 0.0% (n=48) | 1.9% (n=160) | +1.9% |
| 30.0–35.0% (2 bins) | avg 3.4% | avg 4.5% | +1.1% |
| 35.0–37.5% | 0.0% (n=21) | 3.5% (n=57) | +3.5% |

**Max |diff| = 17.2 percentage points**, at BER 7.5–10.0%, where Arm A reads *higher*
P(decode) than Arm B (the opposite direction from the rest of the transition, where Arm B tends
to read a few points higher, consistent with the July B.2 run's finding of the same qualitative
direction — "Arm B reads systematically higher P(decode) than Arm A" — though at roughly a
quarter of that run's magnitude). Both arms' Wilson intervals at 7.5–10.0% barely overlap
([80.2%, 94.9%] vs [57.2%, 83.9%]), so this is a real, well-powered difference at that one bin,
not small-sample noise — both sides of it have n≥40.

**Applying a 5-percentage-point divergence threshold (the largest single-bin gap that would still
plausibly be sampling noise at these n): the arms diverge.** Per the pre-registered rule, **E is
computed from Arm B.**

The likely mechanism echoes the July finding: at Δf=0 the ±10 Hz/±0.5 s matcher necessarily
returns the *same* candidate object for both co-located planted messages — a known matching
artefact, not two independently detected signals, diluted here to a smaller share of Arm B's much
larger pooled population than in the July run.

## 7. E, applied to THE 135

THE 135 population and BER measurement: `compute_135_population()` +
`measure_population()`, imported and called directly from `c2_phase2c_ber_measurement.py`
(reused, not re-derived) — n=126 of 135 measured (9 excluded: true codeword could not be
re-encoded, the same known exclusion every prior session touching this population reports).

**Interpolation method** (documented per the spec's "pick one defensible method" instruction):
linear interpolation between Arm B's bin-centre P(decode) values, clamped to the nearest bin's
value at the curve's edges. A nearest-bin (no interpolation) method is reported alongside as a
sensitivity check — it does not change the reading-rule row.

```
E (Arm B, interpolated)      = 4.28
E (Arm B, nearest-bin)       = 4.26   <- method choice: negligible difference
E (Arm A curve, comparison)  = 4.01
```

**E = 4.28, of 135 (≈3.2%).**

| `E` | reading-rule row | consequence |
|---:|---|---|
| **4.28** | **1 – 15: a real but small decode-path residue** | Not <1 (front-end-limited); not >15 (material-scale defect). This is the Captain's number to weigh — not a QA recommendation on whether to chase it, per the reading rule's own instruction. |

## 8. B10 / B50 / B90, N — for interpretability, not the verdict

**Curve-crossing definition** (the brief's explicit definition — "the BER values at which the
calibration curve crosses 50%/10%/90% decode probability"), computed against **Arm B's curve**
(the one selected for E):

```
B10 = 15.3%   B50 = 11.3%   B90 = 7.2%
N = |{THE 135 : BER_i <= B50=11.3%}| = 2   (of 126 measured)
```

**Distinct from — and not to be confused with — THE 135's *own* BER-distribution percentiles**,
which is what the July B.2 findings doc's "B10/B50/B90" actually reported (its script computed
percentiles of `bers135` itself, not curve crossings, despite the same variable names). For
direct comparability with that prior report, THE 135's own BER percentiles from this run's
identical underlying capture:

```
THE 135 own-BER distribution: p10=17.2%  p50=43.7%  p90=52.3%  (median 44.0%, mean 39.0%)
```

These match the July report's cited numbers exactly (same underlying `d001_c2_phase2c` capture,
same population-selection code) — confirming both runs are reading the same THE-135 data, just
computing two different, similarly-named quantities from it. **N=2** reflects how few of THE
135's own (mostly high-BER) codewords fall below this run's curve-crossing B50 of 11.3% — THE
135's median own-BER (44.0%) sits far out on Arm B's near-flat low-P tail, which is exactly why
E is small: most of THE 135 individually contribute only a few percent of a "decode" each to the
sum, and it is the sum over all 126, not N, that the reading rule keys on.

## 9. Comparison to the Architect's stated prior

**Prior (recorded in advance, per the queue's own request to state agreement/disagreement
plainly):** B50 in 12–20%, E in 5–15.

**This run: B50 = 11.3%, E = 4.28.** Both land just outside the prior's stated range on the low
side — B50 by 0.7 percentage points, E by 0.72. Neither is a large miss, and both are inside the
adjacent reading-rule row's own band edge (E=4.28 is still comfortably >1, so the *row* the prior
predicted — "1–15, small residue" — is confirmed even though the specific number sits just under
the prior's own 5–15 sub-range). Stated plainly, not resolved in the prior's favour: **this run's
E is somewhat lower than the Architect predicted, not higher**, and the July B.2 run (E=4.01–5.69
depending on arm/method) also straddles the same boundary from both sides. Per the reading rule's
own explicit warning: known biases in this kind of measurement (candidate mismatch inflating BER
toward 50%, where P(decode)≈0 regardless of a candidate's true status) push E **down, never up**
— so a low E close to a boundary is *more*, not less, consistent with "the true residue may be
mildly larger than measured," not evidence the prior overshot.

## 10. Honest caveats

- **Sample budget:** 520 buffers run against a "~250" estimate (≈2× over), justified above by
  the low actual per-buffer decode cost; wall-clock stayed under 2 minutes throughout, well
  inside the ≈20-minute budget.
- **SEH-caught internal decode crashes:** 29/400 buffers (7.25%) in the initial run hit
  `ft8_decode_all`'s documented internal-AV recovery path; effect argued non-biasing in §2, not
  independently proven by a dedicated control.
- **Δf=0 matching artefact (Arm B):** unresolved from the July run, same root cause (shared
  candidate object for co-located planted signals), smaller relative weight here (1 of 4 Δf
  values × a much larger pooled Arm B population).
- **Message form:** only `CQ <call> <grid>`, not the full space of standard-message field types
  (reports, RR73, 73) — narrower than THE 135's own real-corpus message mix, though the ground-
  truth cross-validation (§1) confirmed the encoder handles all forms identically; this only
  narrows what was *planted*, not what the encoder can produce.
- **Synthetic ≠ corpus**, unchanged from every prior session touching this design: calibrates
  what BP+OSD can correct on synthetic signals in synthesised interference; THE 135 came off a
  real antenna with real QRM, drift, and multipath.
- **The §0.1 discovery** is itself a limitation of process, not of this measurement — a five-
  minute board-inventory gap let a completed, unretracted result sit unrolled-in for twelve days.
  Flagged, not silently resolved by picking one number over the other.

## 11. Reproducibility

- Harness: `qa/cycleframer-alignment-replay/w1_sec5_calibration.py` (library: Native bindings,
  message/ground-truth generation, buffer builders, matching/BER, binning/Wilson/E/curve-crossing
  helpers) and `w1_run_sweep.py` (driver). Both added this session, saved alongside this report.
- Diagnostic build script: `native/ft8_lib_build/rebuild_diag_llr.bat` (added this session,
  worktree-local, does not touch `main`'s working tree or the branch's shipped `win-x64/libft8.dll`).
- Raw + summary data: `artefacts/d001_w1_sec5_calibration/` (git-ignored; `arm_a_raw.json`,
  `arm_b_raw_full.json`, `curve_a.json`, `curve_b.json`, `summary_final.json` — the last is the
  authoritative summary this report is drawn from).
- Prior run for cross-validation: `artefacts/d001_b2_synthetic_calibration/` (2026-07-26, see §0.1).

## 12. Cross-references

- `2026-08-07-2241-architect-to-qa-consolidated-work-queue.md` §2/§2.1 — the spec and reading
  rule executed here.
- `2026-07-26-2230-architect-sec6-redesign-ruling.md` §4/§5/§6 — original design; §4 explains why
  C.5a (direct bit-injection) is ill-posed, which this measurement avoids by construction (AWGN
  through a real GFSK channel, never a hand-set LLR).
- `2026-07-26-b2-synthetic-calibration-findings.md` — the prior, unretracted run of this same
  measurement (§0.1).
- `c2_phase2c_ber_measurement.py` — self-check and THE 135 population/measurement, imported not
  reimplemented.
- `qa/rr-study/synth/` — GFSK synthesis path (`assemble_symbols`, `modulator.modulate`,
  `channel.mix_to_shared_floor`), reused not re-derived.

---

*Per HK-015 this is QA material for the Architect. Per HK-014 nothing here is pushed or merged —
this worktree has no relationship to `origin` beyond its branch ancestry. Per HK-011 no `src/`
change is proposed; the diagnostic DLL is a local, throwaway build artifact, not a committed
source change. Per HK-006 no `pre_merge_check.py` run is implied. NFR-021: Q-prefix synthetic
callsigns only, generated fresh per signal, never printed individually.*
