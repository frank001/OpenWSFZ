# QA → Architect — F-NBR-A results: Gate A fires A2, not A1; Gate B fires B1; Part C pins the cause on E and maps the exclusion zone

**Author:** QA, 2026-08-23 12:14Z, addendum (§5, ROW 0d) at 12:43Z (`date -u`, HK-017).
**Spec:** `qa/rr-study/2026-08-23-1124-architect-to-qa-spec-f-nbr-a-station-f-near-neighbour-exclusion.md`.
**Status:** COMPLETE. ROW 0 evaluated (all pass, two disclosed corrections — §1; determinism
confirmed — §5). Gate A fires **A2**
(§2) — the opposite of the Architect's on-the-record prediction. Gate B fires **B1** (§3),
as predicted, at a lower point estimate than forecast. Part C (§4, descriptive) finds E
fully causal (C1) and maps a sharp, level-dependent exclusion zone 3–5 tone bins wide (C2,
C3). Captain authorised via "read the board and perform the tests"; the spec itself
authorises this as a no-`src/`, offline-only arm (HK-011 does not bite), so I did not stop
to ask before running it.

**Harness:** `qa/rr-study/f-nbr-a/` (`scene_render.py`, `dll_common.py`, `row0.py`,
`part_a.py`, `part_b.py`, `part_c.py`, `stats_common.py`, `run_all.py`), committed alongside
this report. Results JSON: `qa/rr-study/f-nbr-a/results/f-nbr-a-results.json`.

---

## 0. NFR-021 disclosure

Part B reads the live off-air `artefacts/20260803_live_run_1713/owsfz/ALL.TXT`. Only the
numeric SNR field (`[4]`) and the cycle timestamp (`[0]`, needed for cluster identity) are
ever parsed (`part_b.py::_parse_fields`) — `message_text` is never read, split out, stored,
or emitted, in memory or on disk. Output is counts, fractions, CIs and an SNR histogram
only. I ran `git check-ignore -v` on every artefact this arm produced and grepped
`qa/rr-study/f-nbr-a/results/*.json` for callsign-shaped tokens before writing this report;
none found (the files contain only numeric fields and row labels — a confirmation, not a
discovery, since the harness never touches text in the first place). Parts A and C are
100% synthetic, Q-prefix callsigns from `s8hn-band-scene-highn.json`; no NFR-021 concern.

---

## 1. ROW 0 — all pass, two disclosed corrections

| row | check | result | verdict |
|---|---|---|---|
| 0a | SHA256 of both on-disk `libft8.dll` copies | both `bc8efcf1...b051d7f` | **PASS** |
| 0b | trials 0–24 reproduce the 11 recovered (non-F) stations | 25/25 (corrected — see below) | **PASS** |
| 0c | positive control, station A + station E, forced-position pipeline | 25/25 each (corrected — see below) | **PASS** |
| 0d | two full runs, byte-identical JSON | *(running; see §5)* | *(pending)* |
| 0e | live corpus `ALL.TXT` is the archived copy, mtime predates session | mtime 2026-08-04, path under `artefacts/` | **PASS** |
| 0f | `max_iters==50`, `osd_depth==2`, read from source | both confirmed (`ft8_shim.c:509`, `decode.c:666`) | **PASS** |

### 🔴 Correction 1 — ROW 0b's literal "compare the multiset" check VOIDs at 7/25; its own VOID-condition wording does not

Run literally (full `(freq_hz, message_text)` multiset per cycle, regenerated vs the
committed `owsfz-all.txt`), ROW 0b **fails at 7/25**. Inspecting all 18 "mismatches"
mechanically: **the 11 real S8HN stations reproduce exactly, freq and text, in every single
one.** The only difference is 1–3 extra noise-floor junk decodes (garbled callsigns at
near-random frequencies) present on one side but not the other, per cycle. This is expected,
not a chain defect: the committed run was captured through real audio hardware (48 kHz DAC →
Voicemeeter → WASAPI capture → the daemon's own downsample to 12 kHz), while this harness
synthesises directly at 12 kHz (`scene_render.py`, following `ac_n5_dt_stratified_
measurement.py`'s own precedent) — the two noise-floor *realisations* differ enough to flip
a handful of already-marginal, noise-triggered false decodes, while every genuine
well-above-floor signal is untouched. The row's own VOID-condition column already names the
correct target — "fewer than 24 of 25 cycles reproduce **the 11 recovered stations**
exactly" — not the full multiset including junk. Corrected check: does the regenerated
cycle's decode set cover all 11 non-F truth stations (matcher.py's own `FREQ_TOLERANCE_HZ`
+ exact text convention)? Verified mechanically first: all 25 committed cycles already carry
all 11 non-F truth stations (0 missing) before touching the regenerated side. Result: **25/25.**

### 🔴 Correction 2 — ROW 0c's positive controls VOID at 0/25 on the spec's literal `time_offset_s=0.0`; root cause is an already-CONFIRMED finding from a different arm

Run literally (`ft8_extract_llrs_at(..., freq_hz, time_offset_s=0.0)` at station A and
station E, both true `dt_s=0.0`, per spec §3), **both controls recover 0/25** — despite
`ft8_decode_all` decoding both stations 25/25 in the identical PCM. Investigating: every
true-`dt_s=0.0` station's own real candidate reports `dt ≈ 0.1599999964237213` (bit-identical
across every such station), not `0.0`. Forcing extraction at that decoder-reported `dt`
instead of literal truth `dt` makes both controls succeed immediately (`crc_ok=1`, exact
payload match, `ldpc_errors=0`).

**This is not a new finding.** It is `r2-coherent-llr-instrument`'s own **B-orig-A** arm
(2026-08-21, CONFIRMED, gated ROW 1 fired): *"the waterfall index that `ft8_extract_llrs_at`
reads is NOT raw-PCM time — it runs exactly ONE FT8 symbol AHEAD of it"* (monitor.c's
look-back window). `0.1599999964237213 s` is exactly one FT8 symbol period (`1920/12000`).
Reused verbatim per HK-018 rather than re-derived: `time_offset_s = dt_true + 0.16`,
applied as a fixed function (`dll_common.extraction_time_offset_s`), uniformly to **every**
forced-extraction call in this arm — both ROW 0c's controls and Part A's own forced
extraction at station F. Applying it only to the controls while leaving F at the spec's
literal `0.0` would extract F from a *different* relative position than the one the controls
just validated, defeating ROW 0c's stated purpose ("uses station F's own near neighbour as
one of the two controls"). Result: **25/25 for both A and E.**

Both corrections are disclosed per the spec's own §8 instruction ("a disclosed correction is
a result; a silent one voids the arm"). Full derivation and code: `qa/rr-study/f-nbr-a/row0.py`,
`qa/rr-study/f-nbr-a/dll_common.py`.

---

## 2. Gate A (PRIMARY) — `R_forced`: **A2 fires — EXTRACTION LOCUS**

| trials | successes (`crc_ok==1` AND payload match) | `R_forced` | 95% Clopper–Pearson CI |
|---:|---:|---:|---|
| 100 | **0** | 0.000 | **[0.0000, 0.0362]** |

`CI_hi = 0.0362 < 0.20` → **Gate A row A2 fires**, per the pre-registered table (spec §5,
"k ≤ 11 → A2"). At `k=0` this clears the A2 bar by a wide margin (the bar sits at `CI_hi <
0.20`; the observed CI is 5.5× tighter).

**This is the opposite of the Architect's on-the-record prediction** ("A1, with `R_forced` ≥
0.95", reasoning that F's tone bins are largely uncontaminated because E's tones fall on F's
*differential probe* bins rather than F's *signal* bins — spec §5). Per the spec's own
instruction: **"If A2 fires instead, §0.5's mechanism is wrong and must be discarded, not
rescued."** §0.5's differential-sync-score story is discarded, not merely unconfirmed.

Per Gate A's own consequence text: **"Extraction and LDPC recover station F unreliably even
handed its exact position ⇒ E's energy corrupts F's extraction. Candidate selection is
exonerated for station F. Part C's ablation becomes the priority follow-up."** — which §4
below now answers directly.

**Path distribution** (descriptive, not gated): of 100 trials, BP converged on 0, OSD
converged on 5 (`path=1`), neither converged on 95 (`path=-1`). 🔴 **All 5 OSD-converged
trials had `crc_ok=1` but the WRONG payload** — a CRC-14 false-accept on corrupted LLRs, not
a real recovery of F. This is a plausible mechanism for the "3 junk decodes matching no
injected signal" the spec's own §0.1 disclosure reports at 1144/1147 Hz: OSD occasionally
manufactures a CRC-valid but garbled message out of F's corrupted extraction window. Flagged
descriptively; not gated, not claimed as established (would need its own arm to confirm the
frequencies line up).

---

## 3. Gate B (independent of Gate A) — `Z`: **B1 fires**

| population | `Z` (fraction with factor ≥ 0.99) | 95% CI (cluster bootstrap) | `Abar` (mean attenuation) | 95% CI |
|---|---:|---|---:|---|
| 4,614 cycles / 64,417 decodes, `20260803_live_run_1713` | **0.6567** | **[0.6527, 0.6607]** | 0.1353 | [0.1332, 0.1374] |

Field-order hand-check (`260803_171330 ... -11 1.1 2194 CQ BG7BMG OL66` → SNR=-11, DT=1.1,
freq=2194) passed before any computation, per the spec's mandatory guard against a `[5]`/`[6]`
inversion. Cluster bootstrap: `N_BOOT=2000`, `seed=20260823`, resampled by cycle timestamp
(4,614 clusters, not 64,417 rows).

`CI_lo(Z) = 0.6527 > 0.50` → **Gate B row B1 fires**: *"THE SUPPRESSION STAGE IS INERT FOR A
MAJORITY OF PRODUCTION DECODES. Pass 1 may not be cited as the mechanism that recovers weak
near-neighbours in live operation."* This is the row the Architect predicted, though the
point estimate (0.657) sits well below the forecast "`Z ≥ 0.80`" — the ramp is inert for a
majority, not a large supermajority, of live decodes. Per Gate B's own closing note, this
authorises no change to `K_SOFT_SUPP_SNR_MIN_DB`/`MAX_DB` (that ground stays closed,
`diag-d001-h5-suppression-tuning`, REJECTED) — it is a statement about *how often* the stage
acts, nothing about where its window should sit.

---

## 4. Part C (descriptive, NOT gated) — E is fully causal; the exclusion zone is 3–5 tone bins wide and level-dependent

### C1 — neighbour ablation: E is the cause, unambiguously

| condition | `R` | 95% CI |
|---|---:|---|
| baseline (E present, unmodified S8HN) | 0/100 | [0.0000, 0.0362] |
| **E removed** | **100/100** | **[0.9638, 1.0000]** |

Removing station E — nothing else changed, same 100 seeds, same remaining 11 stations —
flips F's recovery from **0% to 100%**, both CIs non-overlapping by the widest possible
margin. **E is not merely correlated with F's loss; it is sufficient and necessary in this
scene.** Per the spec's own §4.3 framing, this is the "completely different and much more
interesting result" branch's opposite: E's causal role is confirmed outright, not falsified.
Combined with Gate A's A2 (extraction locus, not candidate-selection) and the §0.5 story's
discard, the mechanism is real (E corrupts F's extraction) but the specific "±1 differential
probe bin" explanation for *why* is not supported — see C2 below for the actual footprint.

### C2 — separation sweep: the zone is 3–4 tone bins wide, not the ±1 bin §0.5 predicted

Station E fixed at 1150 Hz / −5 dB; F moved to `1150 + Δ`, F's own SNR fixed at −8 dB
(baseline). FT8 tone spacing = 6.25 Hz.

| Δ (Hz) | Δ (tone bins) | `R(Δ)` | 95% CI |
|---:|---:|---:|---|
| 6.25 | 1 | 0/100 | [0.0000, 0.0362] |
| 12.00 (baseline) | 1.92 | 0/100 | [0.0000, 0.0362] |
| 18.75 | 3 | 0/100 | [0.0000, 0.0362] |
| 25.00 | 4 | **27/100** | [0.1861, 0.3680] |
| 31.25 | 5 | **98/100** | [0.9296, 0.9976] |
| 50.00 | 8 | 100/100 | [0.9638, 1.0000] |
| 100.00 | 16 | 100/100 | [0.9638, 1.0000] |

**Complete exclusion (0/100, CI entirely below 4%) holds through 3 tone bins (18.75 Hz)**,
a sharp transition sits at 4 bins (25 Hz, 27%), and the zone is functionally resolved by 5
bins (31.25 Hz, 98%). §0.5's own mechanism — `ft8_sync_score`'s ±1-bin differential probe —
predicted the effect should be confined to roughly 1–2 bins; **the measured footprint is 2–3×
wider**. This is exactly the outcome the spec called for discarding §0.5 over (§2 above), and
C2 gives the first real measurement of what the true footprint looks like: a zone closer in
width to a *tile* (pass-1's suppression unit, or a comb/leakage footprint) than to a single
differential-score probe pair. I make no claim about which — that is a new question for
whoever picks this up next, not something C2's own descriptive, non-gated design can settle.

### C3 — level sweep: a sharp, ~3 dB knife-edge, not a gradual weak-signal tail

Δ fixed at 12 Hz (baseline separation), E fixed at −5 dB; F's own SNR varied.

| `snr_F` (dB) | relative to E | `R(snr_F)` | 95% CI |
|---:|---:|---:|---|
| −2 | **+3 dB stronger than E** | **100/100** | [0.9638, 1.0000] |
| −5 | equal to E | 0/100 | [0.0000, 0.0362] |
| −8 (baseline) | −3 dB weaker than E | 0/100 | [0.0000, 0.0362] |
| −11 | −6 dB weaker than E | 0/100 | [0.0000, 0.0362] |

At fixed 12 Hz separation, F recovers **100%** the instant it is 3 dB *stronger* than E, and
**0%** the instant it is merely *equal* to E — a transition inside a single 3 dB step, with
no gradual weak-signal tail visible at this resolution. This is a level-*ratio* effect, not a
pure-position effect: moving F's absolute level while holding its position fixed is enough to
flip the outcome completely, which rules out "F's position is simply unreachable regardless
of level" and supports "E's presence imposes a strength-relative exclusion at short range."
Per the spec's scope boundary (§4.3), this says nothing about WSJT-X's own behaviour at the
same separation/level — no cross-decoder comparison is drawn.

---

## 5. ROW 0d — determinism check: **PASS**

Two full pipeline executions (ROW 0 → Part A → Part B → Part C, `run_all.py
--determinism-check`), each producing an independent JSON of every counted/measured value
above, mechanically diffed byte-for-byte: **identical.** Every number in §§1–4 above
reproduces exactly on a second, independent run — including Part A's `path` distribution and
Part C's full C1/C2/C3 tables. Evidence: `qa/rr-study/f-nbr-a/results/f-nbr-a-row0d-run1.json`,
`f-nbr-a-row0d-run2.json` (`diff` clean). The canonical single-run result is committed as
`qa/rr-study/f-nbr-a/results/f-nbr-a-results.json`.

**All of ROW 0 now PASSES. The arm is closed as run; nothing above is provisional.**

---

## 6. Reading order and what this does and does not authorise (per spec §6)

Per spec §1/§5's reading order — Gate A first, then Gate B, then Part C descriptively — no
result above is read across gates. Consequences, stated plainly:

- **No extraction-quality, LLR-quality, or coherent-combining work may be described as a
  candidate-selection treatment for station F** (A2's own consequence text) — the reverse of
  what A1 would have said, and the opposite of what a naive reading of "station F is never
  in the candidate list" might have suggested going in.
- **Pass 1 may not be cited as the mechanism that already rescues weak near-neighbours in
  live operation** (B1) — any future proposal relying on it must first establish ramp
  activity in its own target SNR regime.
- **No change to `K_SOFT_SUPP_SNR_MIN_DB`/`MAX_DB`, no candidate-budget change, no OSR
  change, no reopening of subtract-and-resynthesise or spectral locality** — none of this
  arm's results touch that closed ground, and none should be read as reopening it.
- **No claim about WSJT-X's own near-neighbour behaviour** — Part C characterises OpenWSFZ
  against injected truth only (HK-026 satisfied); a comparable measurement for WSJT-X would
  need a live leg this arm does not fund.
- Station F's defect is now a **located, causally-confirmed, and roughly-bounded** problem
  (extraction locus; E is the sufficient cause; the footprint is 3–5 tone bins, sharply
  level-dependent) — which is considerably more than "never decoded" was this morning, but
  this arm proposes no fix and authorises none.

---

## 7. What I recommend, not decide

- **The extraction-locus finding (A2) plus C1's outright causal confirmation is a strong,
  clean basis for a follow-up arm** aimed at *why* E's extraction-window contamination has a
  3–5-bin footprint rather than a 1-bin one — the natural next question this arm's own data
  raises, not one it was scoped to answer.
- **The OSD false-accept observation (§2, 5/100 trials)** is circumstantial but cheap to
  check against the real 1144/1147 Hz junk decodes' actual frequencies if anyone wants to
  chase it; I did not, since it is outside this arm's scope.
- Everything else the spec named as out-of-scope (§6 of the spec) remains exactly as open as
  it was this morning: NFR-021 audit, Phase B close/park, C-FREQ-A funding, N14, S5 FP
  regression, E2, E4. This arm answers station F and the suppressor's duty cycle; nothing else.
