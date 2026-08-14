# Architect → QA: spec — D-001 root cause, RC1–RC4

**Author:** Architect, 2026-08-06 (23:36 UTC, `date -u`, per HK-017). Repo `main` at `420bebf`.
**For:** QA. §0 is for the Captain — it changes the priority order I gave three hours ago.
**Authorisation:** **NOT AUTHORISED TO RUN.** RC1–RC4 all require `src/` changes and therefore a
Developer session plus the Captain's sign-off (HK-011). §5 proposes bundling them into one.
**Reads together with:** `2026-08-06-2323-architect-where-the-decode-gap-actually-lives.md`
(the stratification these target), `2026-08-06-2249-…-m3-void-preflight-desync.md`.

---

## 0. What changed since the 2323 note — read this before the specs

I closed two of my own open questions from that note using data already on disk, and the answers
**reorder the priorities I gave you.**

### 0.1 The diagnostic instrumentation is not missing — it is already wired and already logging

`ft8_get_last_candidate_counts`, `ft8_get_last_pass_counts` and `ft8_get_last_llr_stats` are
exported from the shim, P/Invoked (`Ft8LibInterop.cs:324/336/347`), called on the same thread as
every decode (`Ft8Decoder.cs:280-294`), and **written to the debug log per cycle**
(`Ft8Decoder.cs:397-421`):

```
Iterative subtraction: pass 1 of 2, 140 candidates found, 22 decoded.
Iterative subtraction: pass 2 of 2, 200 candidates found,  1 decoded.
Iterative subtraction: pass 1 LDPC fail stats -- failCands=... meanAbsLLR=... prenormVar=...
```

Those lines are in `_work/run{1..5}/logs/*.log` **from the five runs we already have.** The
08-04 board's record of S.2a as "blocked on instrumentation" should be revisited — for candidate
counts, pass counts and LLR statistics it is not.

### 0.2 Both candidate caps are saturated on essentially every cycle

Parsed from those logs, pass 1 of the busy window, 5 runs, 100 cycle-observations:

| | saturated | rate |
|---|---:|---:|
| pass 1 at `K_MAX_CANDIDATES = 140` | 95 / 100 | **0.950** |
| pass 2 at `K_MAX_CANDIDATES_PASS2 = 200` | 90 / 100 | **0.900** |

`ftx_find_candidates()` returned **exactly** the maximum it was permitted to return on 95% of
cycles. The waterfall contained more candidates than we ever looked at.

### 0.3 The candidate budget is allocated backwards

| | candidates | decodes | **yield** | share of our output |
|---|---:|---:|---:|---:|
| pass 1 | 13,300 | 2,184 | **16.42%** | 93.5% |
| pass 2 | 18,972 | 151 | **0.80%** | **6.5%** |

Pass 2 is given **more** candidate budget than pass 1 (200 vs 140) and converts it at **1/20th**
the rate. Some of that gap is expected — pass 2 works a residual and mops up harder signals —
but the allocation is the wrong way round against measured yield, and pass 1 is the one hitting
its ceiling.

**This is the first mechanism found that could plausibly account for a 40% deficit, and it sits
exactly in the parameter family D-009's grid excluded by construction
(`K_MAX_CANDIDATES_PASS2`, out of scope per that spec's §1).**

### 0.4 Two corrections to my own 2323 note

**(a) The depth re-test was my top recommendation. It should not be.** I called
`K_MAX_PASSES = 3` "the single highest-value experiment available." Pass 2 already converts at
0.80%; a third pass works an even more depleted residual and would convert at less. The June
revert (−4.30 pp, `shim:48-56`) now looks **better founded than I credited it**, not worse. It is
demoted to RC4 and I recommend not running it until RC1 and RC2 report.

**(b) The passband finding is smaller than I framed it.** I reported "50 decodes, 3.3% of all
misses." Measured properly: the 47 sub-200 Hz decodes are **all at 193 Hz** and the 3 above are
**all at 3006 Hz** — that is one station just below our floor and one just above our ceiling on
this window, not a broad population. Still a certain defect worth fixing, but on another window
the gain could be zero. §4 of the 2323 note overstates it and should be read with this.

### 0.5 A gate I nearly wrote, and why it would have failed

My plan was to correlate candidate saturation against miss rate. **That test cannot fire:**
saturation occurs on 95% of cycles, so the predictor has almost no variance. The five
non-saturated cycles are the near-empty ones at the window edges (their miss rate, 0.462, is
higher, on n=5 — noise, not signal).

Recording it because it is the same family as tonight's other gate failures: **check the
distribution your statistic can actually take before you write the threshold.** A ceiling is not
a correlation, and it needed a different measurement, not a better threshold.

---

## 1. Shared design rules for every gate below

Applying tonight's lessons explicitly, so they are visible rather than assumed:

1. **Boundary values fall to the inconclusive row.** Every threshold below uses strict `<` / `>`
   so a statistic landing exactly on a boundary is reported as PARTIAL, never as an assertive
   verdict. This is the direct fix for M1's ROW 1 sitting on exactly `−2.0` dB.
2. **Thresholds are checked against the lattice the statistic can occupy** before they are set.
3. **No gate is placed on a variable known to have no variance** (§0.5).
4. Rows are mutually exclusive, exhaustive, evaluated in strict order, first match wins.
5. Every threshold below is a judgement call with its rationale stated. **Challenge them before
   execution, not after.**

Match key remains `(cycle, normalize_hash_tokens(message))` throughout. Reference for every
comparison is **fresh WSJT-X on the same replayed audio** — never the archived corpus `ALL.TXT`,
whose validity is still open.

---

## 2. RC1 — per-decode attribution (the root-cause measurement)

**The decisive experiment. Everything else is a treatment; this is the diagnosis.**

§0.2 shows the candidate list is truncated. It does **not** show that the decodes we miss were in
the truncated tail — candidates are ranked by sync score, so the tail is the weakest, which is
*consistent* with our miss profile but is not evidence. RC1 settles it.

### 2.1 The `src/` change required (diagnostic only)

A new TLS getter, in the same family as `ft8_get_last_candidate_counts`, exposing the per-pass
candidate **list** rather than its count: for each candidate, `(time_offset, freq_offset, score)`
as `ftx_find_candidates()` returned it, before any LDPC attempt.

**No decode logic, pass configuration, candidate search or struct layout changes.** Export,
P/Invoke, adapter and interface follow the existing pattern exactly. This is the same shape of
change as shim 20260018.

### 2.2 Procedure

Replay the busy window, 3 runs, pass 1 only. For every WSJT-X decode we did not produce,
classify:

| class | test |
|---|---|
| `OUT_OF_BAND` | WSJT-X `freq_hz` outside `[200, 3000]` |
| `NO_CANDIDATE` | no candidate within tolerance of the decode's (DT, freq) |
| `CANDIDATE_NOT_DECODED` | a candidate was present; decode failed |

**Tolerance.** Frequency: ±6.25 Hz (one FT8 tone spacing). Time: our reported DT runs **+0.65 s**
against WSJT-X's on this pipeline (2115 note §4), so centre the DT window on that measured offset
and allow ±0.5 s — **do not centre on zero.** QA must state the symbol-units→seconds conversion
used for `time_offset` in the write-up; I have not verified the candidate struct's units and will
not guess them.

Report the three-way split overall, and stratified by SNR band and density band using the same
bands as the 2323 note, so it joins directly to that stratification.

### 2.3 Pre-registered gate

`f_nocand = NO_CANDIDATE / (total misses − OUT_OF_BAND)`

```python
def rc1_row(f):
    if f > 0.60:  return "ROW 1"
    if f < 0.30:  return "ROW 2"
    return "ROW 3"
```

| row | condition | consequence |
|---|---|---|
| **ROW 1** | `f_nocand > 0.60` | **ROOT CAUSE IS CANDIDATE GENERATION.** The signals are never offered to the decoder. ⇒ RC2 is the priority lever; depth and OSD work is deprioritised. |
| **ROW 2** | `f_nocand < 0.30` | **ROOT CAUSE IS DECODE, NOT SEARCH.** Candidates are found and not converted. ⇒ RC2 will not help; the lever is LDPC/OSD/depth and §0.3's yield asymmetry needs a different explanation. |
| **ROW 3** | `0.30 ≤ f_nocand ≤ 0.60` | **MIXED — no single root cause.** ⇒ Report both fractions stratified by SNR and density; the stratification decides where to spend, not the pooled number. |

Thresholds: `0.60` and `0.30` are judgement calls. Reasoning — a majority attribution is the bar
for calling something *the* root cause and redirecting effort onto it; below a third it is not the
dominant term. Boundaries fall to ROW 3 by construction.

---

## 3. RC2 — candidate budget (the leading treatment hypothesis)

**Do not run before RC1 reports.** If RC1 fires ROW 2, RC2's mechanism is already excluded.

### 3.1 Make the caps runtime-settable first

`K_MAX_CANDIDATES` and `K_MAX_CANDIDATES_PASS2` are compile-time `#define`s
(`ft8_shim.c:467, 504`), so a sweep over them is one rebuild per point. The D-009 parameters were
already converted to runtime variables via `ft8_set_decode_params()` /
`s_k_min_score_pass2`; **extend that setter to cover both caps.** One build, N configurations, and
every future sweep over this family becomes cheap.

⚠️ **Implementation constraint, already documented in the shim** (`ft8_shim.c:514-525`): the local
`candidates[]` array is sized `K_MAX_CANDIDATES_ANY_PASS`, and `K_MAX_DECODED` is
`K_MAX_CANDIDATES + K_MAX_CANDIDATES_PASS2`. Raising either cap past 200 requires the array
allocation and both macros to move with it. The comment records this as a latent overflow that was
found once already — **it must be handled deliberately, not discovered.** Sizing must be driven
from the runtime maxima, not from the old constants.

### 3.2 Configurations

3 runs each, pass 1 only, busy window. Baseline `C0` is free — the 5 runs already on disk.

| | pass 1 | pass 2 | tests |
|---|---:|---:|---|
| `C0` | 140 | 200 | baseline, **already measured**: 461 decodes/run |
| `C1` | 280 | 200 | does pass 1 keep converting past its ceiling? |
| `C2` | 340 | 60 | reallocation at ~constant total budget |
| `C3` | 560 | 200 | does it keep scaling? **Conditional** — run only if `C1` fires ROW 1. |

15 min playback each; 30 min for `C1`+`C2`, plus 15 if `C3` triggers.

### 3.3 Pre-registered gate — evaluated per configuration

`g = mean decodes/run(C) − 461`. FP arms are the existing S5/S7 synthetic arms, unchanged.

```python
def rc2_row(g, s5_fp, s7_fp, s7_base):
    if g > 40.0 and s5_fp == 0 and s7_fp <= s7_base:  return "ROW 1"
    if g > 40.0:                                      return "ROW 2"
    if g < 10.0:                                      return "ROW 3"
    return "ROW 4"
```

| row | condition | consequence |
|---|---|---|
| **ROW 1** | `g > 40.0` **AND** `S5 FP == 0` **AND** `S7 FP <= baseline` | **THE CAP WAS BINDING AND THE BUDGET IS A LIVE LEVER.** ⇒ Candidate caps enter the next parameter sweep as first-class terms. Adoption is still the Captain's call. |
| **ROW 2** | `g > 40.0`, FP regressed | **GAIN AT AN FP COST.** ⇒ Report both; no adoption. The trade is a Captain decision, not a QA one. |
| **ROW 3** | `g < 10.0` | **NOT THE CONSTRAINT.** Candidates beyond 140 do not convert. ⇒ Close this line; the deficit is downstream of candidate generation. |
| **ROW 4** | `10.0 ≤ g ≤ 40.0` | **PARTIAL.** ⇒ Report `g` per configuration with its run spread. No verdict. |

Thresholds: run-to-run spread on the baseline was **8 counts** (461 across 5 runs), so `40` is
~5× the instrument's own noise and ~14% of the 291-decode gap to WSJT-X — a real effect, not a
flutter. `10` is just above noise. Boundaries fall to ROW 4.

---

## 4. RC3 — search band, and RC4 — depth

### 4.1 RC3 — widen the search band

**🛑 Must not run before RC2 reports.** Widening the band adds candidates to a list that is
already saturated 95% of the time (§0.2). Under a binding cap, widening can *displace* stronger
candidates and **reduce** total decodes. Sequencing this correctly matters.

Change `monitor_config_t cfg` (`ft8_shim.c:1183`): `f_min` 200 → **150**, `f_max` 3000 → **3100**.
Measured extremes on this window are 193 Hz and 3006 Hz, so those limits clear both with margin
and stay well inside the transceiver's own ~2800 Hz rolloff behaviour.

| row | condition | consequence |
|---|---|---|
| **ROW 1** | decodes increase **AND** `S5 FP == 0` **AND** `S7 FP <= baseline` | **ADOPT** (Captain's call). |
| **ROW 2** | decodes increase, FP regressed | **REJECT as configured.** Report; a narrower widening may still be viable. |
| **ROW 3** | no increase | **REJECT.** Mechanism is not as modelled — most likely the cap interaction above. |

Expect a small gain. Per §0.4(b) this is one station at each edge on this window.

### 4.2 RC4 — decode depth, `K_MAX_PASSES` 2 → 3

**Specced for completeness. I recommend not running it.** §0.4(a): pass 2 converts at 0.80%, so
pass 3 works a further-depleted residual and should convert at less. The June revert is
consistent with that. If RC1 fires ROW 2 — root cause is decode, not search — this becomes worth
revisiting; otherwise it is not where the 40% lives.

If run: 3 runs, pass 1 only, busy window. `d` = change in miss rate for signals below −12 dB,
in percentage points, negative = improvement.

```python
def rc4_row(d, worst_band_regression):
    if d < -5.0 and worst_band_regression <= 2.0:  return "ROW 1"
    if abs(d) < 2.0:                               return "ROW 2"
    if d > 5.0:                                    return "ROW 3"
    return "ROW 4"
```

| row | condition | consequence |
|---|---|---|
| **ROW 1** | `d < −5.0` pp **AND** no SNR band worsens by more than `2.0` pp | **DEPTH HELPS WEAK SIGNALS**; the June co-channel verdict does not generalise to weak-signal recall. |
| **ROW 2** | `abs(d) < 2.0` pp | **NO EFFECT.** The June verdict holds on real audio too. Close it. |
| **ROW 3** | `d > +5.0` pp | **DEPTH HURTS**, consistent with June. Close it. |
| **ROW 4** | anything else | **MIXED.** Report the full miss-rate-by-SNR table for both configurations. |

Baseline for `d` is the 2323 note's table: miss rate `0.564` at −15…−12, `0.685` at −20…−15,
`0.792` below −20.

---

## 5. Sequencing, dependencies and cost

```
                      RC1  per-decode attribution        (3 runs, 15 min)
                            |
              ROW 1 ────────┴──────── ROW 2
        (search is the cause)      (decode is the cause)
              |                            |
              v                            v
         RC2  budget                  RC4  depth becomes
         (30-45 min)                  worth revisiting
              |
              v
         RC3  passband  <-- MUST follow RC2; cap interaction
         (15 min)
```

| step | `src/` change | playback | notes |
|---|---|---:|---|
| RC1 | diagnostic getter, no logic change | 15 min | the diagnosis |
| RC2 | caps → runtime-settable + array sizing | 30–45 min | needs §3.1 done carefully |
| RC3 | two constants | 15 min | after RC2 only |
| RC4 | one constant | 15 min | recommended: don't |

**One Developer session should carry RC1's getter and RC2's runtime-settable caps together** —
they are independent edits in the same file, both mechanical, and bundling them means one
authorisation, one build, one review. RC3 and RC4 are single-constant changes that can ride along
behind a runtime flag or wait for a second session.

Total playback if everything runs: ~75 min. The realistic path — RC1, then RC2, then RC3 — is
**~60 min**, and RC1's 15 minutes is the part that decides whether the other 45 are worth spending.

---

## 6. What this programme does and does not do

- **It targets the root cause of D-001 directly.** RC1 partitions the 1,526 missed decodes into
  "never offered to the decoder" and "offered and failed." Those two have disjoint fixes, and no
  measurement in this project has separated them.
- **It does not depend on the archived corpus `ALL.TXT`.** Every comparison is fresh WSJT-X on
  identically replayed audio. M3's outcome does not gate any of it.
- **It does not touch Arm R.D, Measurement D, D-009's parameter decision, or any existing
  pre-registered gate.**
- **It does not re-derive any D-001 figure**, and I have still not opened
  `project-state-2026-07-31-d001-competition-confirmed.md`. §0.3's yield asymmetry and the 2323
  note's density result both bear on the density penalty recorded there; reconciling them is
  separate work and should not be done by assuming either side.
- **Nothing here is authorised.** RC1–RC4 all require `src/` changes, a Developer session, and
  the Captain's sign-off (HK-011). QA proposes and stops.

---

*Per HK-015 this is Architect → QA; `tasks.md` and `dev-tasks/*.md` remain QA's to author. Per
HK-014 committed locally, not pushed, no merge implied or requested. Per HK-011 every step here
requires a separate Developer session and Captain authorisation before any `src/` edit. Per
HK-021 every gate is a hard threshold with its consequence as an assertion, rows mutually
exclusive in strict order, drafted as the code that evaluates it; boundary values fall to the
inconclusive row by construction (§1), and §0.5 records a gate I discarded because its predictor
had no variance. Per NFR-021 no message text or callsign appears here.*
