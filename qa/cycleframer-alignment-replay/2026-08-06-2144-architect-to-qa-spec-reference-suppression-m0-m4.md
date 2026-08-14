# Architect → QA: spec — reference-suppression investigation, M0–M4

**Author:** Architect, 2026-08-06 (21:44 UTC, `date -u`, per HK-017). Repo `main` at `98db57b`.
**For:** QA.
**Authorisation:** **NOT AUTHORISED TO RUN.** This is a spec for the Captain to authorise, in
whole or in part. M0 is the one step I would ask for immediately regardless (see §2 —
it is preservation, not measurement).
**Reads together with:** `2026-08-06-2123-qa-to-architect-live-cross-decode-anova-and-overlap-flip.md`
(the trigger), `2026-08-06-2115-qa-live-cross-decode-full-anova-results.md`,
`2026-08-06-2022-qa-live-cross-decode-replay-results.md`,
`2026-08-06-1933-qa-decode-config-comparison-wsjtx-vs-openwsfz.md`,
`2026-08-06-1920-qa-wav-content-comparison-1713.md`.

---

## 0. Why this exists

Five independent replays established that WSJT-X, decoding its own archived WAVs from
`20260803_live_run_1713`, yields **748–759 decodes** on a 20-cycle window against the
**328** recorded in that corpus's live `wsjt-x/ALL.TXT` for the same cycles. OpenWSFZ
reproduces its own original count on the same window (461 vs 466).

The consequence is not about that window. It is that **the corpus's live WSJT-X `ALL.TXT`
— the reference every "shortfall vs WSJT-X" figure in this project is computed against —
may be a degraded instrument**, in the same way `jt9 -d 3` was found to be a degraded
instrument on 2026-08-03, but erring in the opposite direction.

M1–M4 exist to decide three things, in this order of decision-value:

1. **What kind of defect is it?** Degraded decoding, or an incomplete log? (M1 — these have
   entirely different consequences and M1 is free.)
2. **Does the "OpenWSFZ finds what WSJT-X cannot" population survive?** (M2 — also free.)
3. **Does it generalise beyond one window?** (M3 — the one that decides whether corpus-wide
   figures are salvageable.)
4. **Can the hypothesised mechanism actually produce it?** (M4 — gated, see §7.)

### 0.1 A correction QA should apply to the 2123 note

The §3 **table** in `2026-08-06-2123-…-overlap-flip.md` is correct and internally consistent
(279 + 187 = 466; 141 + 187 = 328; 187/466 = 40.1%). The **prose** beneath it, lines 68–70,
swaps the two decoders:

> "WSJT-X missed 141 of OpenWSFZ's 466 decodes (43%); OpenWSFZ missed 279 of WSJT-X's own 328 (60%)"

Neither half survives arithmetic: 141/466 = 30.3%, not 43%; and 279 of 328 would be 85.1%,
not 60%, and would force matched = 49 against the table's 187. The correct statement is:

> **WSJT-X missed 279 of OpenWSFZ's 466 (59.9%). OpenWSFZ missed 141 of WSJT-X's 328 (43.0%).**

**This is an Architect-side catch on a QA note, and it cuts in QA's favour** — the corrected
reading makes the finding *stronger*, not weaker. Originally OpenWSFZ appeared to
out-decode WSJT-X 466 to 328 with 279 decodes exclusively ours; tonight it is 461 to 752
with ~14 exclusively ours. The comparison does not shift, it **inverts**. Please correct the
prose in place with a dated correction block, in the same style as §6 of the 1933 note.

---

## 1. Shared implementation notes — read before writing any of M1–M4

### 1.1 What is already built and must be reused, not rewritten

From `qa/endurance/anova_common.py`:

| symbol | gives you |
|---|---|
| `parse_all_txt(path) -> list[dict]` | rows with `ts`, `snr`, `dt`, `freq_hz`, `message` |
| `normalize_hash_tokens(message)` | the project-standard message normalisation |
| `parse_cycle_ts(token)` | cycle token → `datetime` |

From `run_cross_decode_replay.py` in the replay directory: `WINDOW` (the 20 filenames),
`SLOT_SECONDS`, `WSJTX_ALL_TXT`, `filter_by_window()`, `match_pairs()`.

**Match key is `(cycle, normalize_hash_tokens(message))` throughout, identical to every other
script in this directory.** Do not introduce a second convention.

### 1.2 The cross-session timestamp mapping — the one place this can silently go wrong

Tonight's decodes carry **tonight's** UTC timestamps (`260806_2009…`). The archived corpus
decodes carry **the corpus's** (`260804_0858…`). Every M1/M2 comparison needs tonight's
decodes mapped back to the corpus cycle whose audio was playing.

Derive the mapping **arithmetically from `pass_windows.json`**, never from the observed
decodes:

```python
# B0 = the first 15 s boundary at or after pass start. play_pass() records its start
# 0.5 s BEFORE the boundary it waits for (prewarm=0.5), so snapping UP recovers it.
start   = datetime.datetime.fromisoformat(pass_start_iso)   # from pass_windows.json
b0_epoch = math.ceil(start.timestamp() / SLOT_SECONDS) * SLOT_SECONDS
# slot i played WINDOW[i]:
slot_of = {b0_epoch + i * SLOT_SECONDS: WINDOW[i][:-4] for i in range(len(WINDOW))}
```

Worked check against `_work/run1/pass_windows.json`: pass 1 start `20:09:29.500283` snaps up
to `20:09:30`; 20 slots then run `20:09:30 … 20:14:15`, last cycle ending `20:14:30`, against
a recorded pass end of `20:14:31.13`. Consistent.

**Do not** derive the mapping by sorting the distinct observed timestamps and zipping them
positionally against `WINDOW`. That works only while every cycle yields ≥1 decode, and fails
*silently by shifting every subsequent cycle* the first time one does not.

### 1.3 Mandatory assertions — all four, in every M1/M2 script

These are not optional sanity checks; a failure of any one means the extraction is wrong and
**no ROW in §3–§6 may be evaluated**:

```python
assert set(mapped_cycles) <= set(w[:-4] for w in WINDOW)      # nothing outside the window
assert len(set(mapped_cycles)) == 20                          # all 20 cycles represented
assert all((t - b0_epoch) % SLOT_SECONDS == 0 for t in ts)    # exact grid, no drift
assert len(rows) == len({(c, m) for c, m in keys})            # zero duplicate (cycle,msg)
```

The fourth exists specifically because duplicate `(ts, message)` emission is what invalidated
`jt9 -d 3` and VOIDed Angle 1. QA verified it for tonight's counts already; re-assert it
mechanically here rather than inheriting the finding.

### 1.4 Which pass is primary

**Pass 1 (WSJT-X-source WAVs) is primary for every measurement below.** It is the truest
reconstruction of WSJT-X's own original conditions — its own capture chain's audio, replayed
to itself. Pass 2 results are to be reported as a secondary column but **do not drive any
ROW**. Rationale: the 3-way ANOVA put Source at 0.03% of variance with a flat Decoder × Source
interaction, so pass 2 adds confirmation, not independent evidence.

### 1.5 Privacy

`ALL.TXT` on both sides contains **real callsigns**. `artefacts/` (`.gitignore:105`) and
`qa/cycleframer-alignment-replay/_work/` (that directory's own `.gitignore:3`) are both
ignored and untracked — verified 2026-08-06. Message text may be read to build match keys and
**must never be printed to console, written to a committed file, or included in any note**.
Committed outputs are aggregate counts and statistics only, per NFR-021.

---

## 2. M0 — preserve the evidence (prerequisite, not a measurement)

**Cost: minutes. No playback. I would ask for this before anything else, including before any
decision on M1–M4.**

Tonight's five runs exist on the WSJT-X side in exactly one place:
`C:\Users\Frank\AppData\Local\WSJT-X - FT991A\ALL.TXT` — 496,800 bytes,
last written 2026-08-06 21:14:01 UTC. The committed `summary_run*.json` files are
**aggregate-only** (verified: counts and mean/median deltas, no per-decode rows), and
`_work/run1..run5/` hold only `our_ALL.TXT`. **Every per-decode WSJT-X record from all five
runs is in a live, unversioned file outside the repo.**

M3 and M4 append to that same file. Appending is not itself destructive — the harness slices
by UTC window — but the file being cleared, rotated, or the profile being reset would make
the five-run experiment unreproducible without re-running it.

1. Create `artefacts/20260806_cross_decode_replay_2009/` per HK-016 (dated, with a
   `README.md` recording provenance: source paths, the five run windows, `98db57b`, and
   that the WSJT-X file is an all-time accumulating log, not a session log).
2. Copy in: `WSJT-X - FT991A\ALL.TXT`, all five `_work/run*/our_ALL.TXT`, all five
   `_work/run*/pass_windows.json`, all five `_work/run*/daemon_stdout.log`, and the
   committed `summary_run*.json` + `full_anova_summary.json`.
3. Record the source file's size and `LastWriteTimeUtc` in the `README.md` so a later
   divergence is detectable.
4. Regenerate the inventory: `python qa/artefact_inventory.py`, then
   `python qa/artefact_inventory.py --check` to confirm it is not stale.

**HK-016 gap worth noting for the record:** HK-016 covers gathering *our own* logs, WAVs and
`ALL.TXT`. It does not currently cover WSJT-X's AppData `ALL.TXT`, which is why a five-run
experiment ended up with its reference leg living only outside the repo. Whether HK-016 should
be widened is the Captain's call, not something to change unilaterally — flagging it, not
proposing it.

---

## 3. M1 — SNR signature of the suppressed decodes

**Offline. No playback. Reads only files already on disk.**

### 3.1 Question

Are the decodes WSJT-X found tonight but *not* in the original archive systematically
**weaker** than the ones it found both times?

- **Deadline/contention truncation** predicts yes: Deep mode's later iterative-subtraction
  passes are what recover marginal signals, so a truncated cycle drops the weakest first.
- **Incomplete log** (transcription loss, not decode loss) predicts no: losses would be
  broadly indifferent to SNR.

These predictions are opposite and the data to separate them already exists.

### 3.2 Procedure

1. Extract tonight's pass-1 WSJT-X decodes for each of the 5 runs from the M0-preserved
   `ALL.TXT` using each run's `pass_windows.json` window. Map to corpus cycles per §1.2.
   Apply all four assertions in §1.3.
2. Extract archived original WSJT-X decodes for the same 20 corpus cycles from
   `artefacts/20260803_live_run_1713/wsjt-x/ALL.TXT`.
3. Partition tonight's decode keys, pooling the 5 runs by **presence in any run**:
   - `SHARED` = key also present in the archived original.
   - `NEW` = key not present in the archived original.
4. For SNR, use each key's **median SNR across the runs in which it appeared** (avoids
   weighting a key by how many runs happened to catch it).
5. Compute `delta = median(SNR of NEW) − median(SNR of SHARED)` and a **Mann-Whitney U**
   two-sided test (nonparametric — WSJT-X reports integer dB and the distributions are not
   assumed normal).

### 3.3 Pre-registered gate — evaluate in strict order, first matching row wins

```python
def m1_row(delta_db: float, p: float) -> str:
    if delta_db <= -2.0 and p < 0.001:            return "ROW 1"
    if abs(delta_db) < 1.0 and p >= 0.001:        return "ROW 2"
    if delta_db >= 2.0 and p < 0.001:             return "ROW 3"
    return "ROW 4"
```

| row | condition | consequence |
|---|---|---|
| **ROW 1** | `delta ≤ −2.0` dB **AND** `p < 0.001` | **TRUNCATION SUPPORTED.** ⇒ M4 is authorised to proceed (subject to Captain sign-off). |
| **ROW 2** | `abs(delta) < 1.0` dB **AND** `p ≥ 0.001` | **TRUNCATION NOT SUPPORTED**; log-incompleteness becomes the lead hypothesis. ⇒ **M4 MUST NOT RUN.** ⇒ Escalate to Architect — this is a different defect class with different consequences. |
| **ROW 3** | `delta ≥ +2.0` dB **AND** `p < 0.001` | **ANOMALY** — tonight-only decodes are *stronger*, which fits neither hypothesis. ⇒ **HALT M1–M4.** ⇒ Escalate immediately. |
| **ROW 4** | anything else | **INCONCLUSIVE.** ⇒ **M4 MUST NOT RUN.** ⇒ Report `delta`, `p`, both medians, both n, and escalate. |

Rows are mutually exclusive by construction: ROW 1 and ROW 3 cannot co-hold (`delta` cannot be
both ≤ −2.0 and ≥ +2.0); ROW 2 requires `p ≥ 0.001` where ROW 1 and ROW 3 require `p < 0.001`.
ROW 4 is the exhaustive remainder.

**Both an effect-size threshold and a significance threshold are required, deliberately.** The
2115 note made exactly this point about its own 0.1 Hz frequency result being "significant" at
p<0.0001 purely on sample size. With n≈565 vs n≈187 the same trap is live here, and a gate on
p alone would walk into it.

### 3.4 Threshold rationale (challenge these before running, not after)

`2.0 dB` and `1.0 dB` are judgement calls, not derived quantities. Reasoning: WSJT-X reports
SNR in integer dB over roughly a −24…+10 dB range, so a shift smaller than 1 dB is inside
reporting granularity and not interpretable as a population difference; a truncation effect
that preferentially drops marginal decodes should move the median by considerably more than
one reporting step. `p < 0.001` rather than 0.05 because the sample is large and the claim is
load-bearing. **If QA thinks any of these three is wrong, say so before execution** — changing
a threshold after seeing the result is what HK-021 exists to prevent.

---

## 4. M2 — direct set test on the "OpenWSFZ-exclusive" population

**Offline. No playback. Same script and same data pull as M1.**

### 4.1 Question

§3 of the 2123 note infers from aggregate rates that tonight's WSJT-X "absorbed almost
everything that used to be OpenWSFZ's unique territory". Measure it directly instead of
inferring it: of the **279** decodes that were OpenWSFZ-exclusive in the original archive, how
many does tonight's WSJT-X find?

### 4.2 Procedure

1. From the archived corpus, for the 20 window cycles, compute
   `ORIG_OWSFZ_EXCL` = keys in `owsfz/ALL.TXT` not in `wsjt-x/ALL.TXT`, and
   `ORIG_WSJTX_EXCL` = keys in `wsjt-x/ALL.TXT` not in `owsfz/ALL.TXT`.
   **Assert** `len(ORIG_OWSFZ_EXCL) == 279` and `len(ORIG_WSJTX_EXCL) == 141`. If either
   fails, the 2123 note's table cannot be reproduced from the archive and **M2 is VOID
   pending Architect review** — do not proceed to §4.4.
2. `R_owsfz = |ORIG_OWSFZ_EXCL ∩ TONIGHT_WSJTX| / |ORIG_OWSFZ_EXCL|`, where `TONIGHT_WSJTX`
   is the union across the 5 runs (pass 1).
3. Report alongside, as a secondary figure that drives no row: the same ratio computed with
   `TONIGHT_WSJTX` = intersection across all 5 runs (`R_owsfz_all5`). If
   `R_owsfz − R_owsfz_all5 > 0.15`, note it — a large gap means the recovered decodes are
   themselves marginal and only intermittently found.

### 4.3 Validity gate — evaluate BEFORE §4.4

```python
R_wsjtx_self = len(ORIG_WSJTX_EXCL & TONIGHT_WSJTX) / len(ORIG_WSJTX_EXCL)
if R_wsjtx_self < 0.80:
    verdict = "VOID"
```

**If `R_wsjtx_self < 0.80` ⇒ M2 is VOID.** If tonight's replay cannot reproduce 80% of
WSJT-X's *own* original exclusive decodes, then replay conditions differ enough from the
original session that set-level absorption claims are unsafe, and §4.4 must not be evaluated.
Report `R_wsjtx_self` and escalate.

`0.80` is a judgement threshold: decoding is stochastic at the margin so exact reproduction is
not expected, but a replay that loses more than a fifth of the reference leg's own decodes is
not reconstructing the original conditions well enough to reason about set membership.

### 4.4 Pre-registered gate — strict order, first matching row wins

```python
def m2_row(r: float) -> str:
    if r >= 0.90:  return "ROW 1"
    if r >= 0.50:  return "ROW 2"
    return "ROW 3"
```

| row | condition | consequence |
|---|---|---|
| **ROW 1** | `R_owsfz ≥ 0.90` | **CONFIRMED** — "OpenWSFZ finds decodes WSJT-X cannot" is **false on this window**; that population is a reference-suppression artifact. ⇒ Arm R.D's reciprocity premise is undermined on this window; **R.D remains unauthorised** pending M3. |
| **ROW 2** | `0.50 ≤ R_owsfz < 0.90` | **PARTIAL** — majority artifact, with a residual genuinely-exclusive population of `(1 − R_owsfz) × 279` decodes. ⇒ Report the residual count. **No verdict on its cause.** |
| **ROW 3** | `R_owsfz < 0.50` | **NOT SUPPORTED** — §3's aggregate-rate reading is masking set churn. ⇒ §3's "absorption" reading **must be withdrawn** and the Architect notified before any further inference rests on it. |

Mutually exclusive and exhaustive: a partition of `[0, 1]` at `0.90` and `0.50`.

---

## 5. M3 — does it generalise? Low-density window replay

**3 runs × 1 pass × 5 min = 15 min playback, ~17 min machine time.**

### 5.1 Single-pass authorisation

**Run pass 1 only (WSJT-X-source WAVs). Do not run pass 2.** The 3-way ANOVA measured Source
at **0.03%** of total variance with `Decoder × Source` flat at `p = 0.688`, and the WAV-content
note independently found the two chains' in-band audio essentially identical. For a
suppression-ratio measurement the second pass buys nothing at double the cost. This halves
every run from 10m30s to ~5 min.

### 5.2 Window selection — mechanical, no judgement

Read `qa/ARTEFACT_INVENTORY.md` first (🔴 standing rule) and confirm the corpus row for
`20260803_live_run_1713` before selecting anything. Then, over the corpus's archived
`wsjt-x/ALL.TXT` and `owsfz/ALL.TXT`:

1. Compute per-cycle original **combined** (owsfz + wsjtx) decode counts across the corpus.
2. Enumerate all contiguous 20-cycle windows for which all 20 WAVs exist on the WSJT-X side.
3. **Exclude** any window whose archived original WSJT-X total over the 20 cycles is `< 60`
   (mean < 3/cycle) — the suppression ratio's denominator is too small to be stable below that.
4. Select the surviving window with the **lowest** mean combined count. Tie-break: earliest UTC.
5. Compute `contrast = mean_combined(busy window) / mean_combined(selected window)`.
   **If `contrast < 3.0` ⇒ do not run M3.** Report and escalate: the corpus does not offer
   enough density leverage for this test and a different design is needed.

### 5.3 Validity gate — evaluate BEFORE §5.4

```python
counts = [run1_wsjtx, run2_wsjtx, run3_wsjtx]
if (max(counts) - min(counts)) > 0.10 * (sum(counts) / 3):
    verdict = "INSTRUMENT NOISE HIGH"
```

**If the 3 runs' WSJT-X counts span more than 10% of their mean ⇒ `S_low` is not citable as a
point estimate.** Report the three counts and escalate; §5.4 is not evaluated. (Tonight's
busy-window span was 7 on a mean of ~755 = 0.9%; at low density absolute counts are smaller so
relative spread will be larger, and 10% is a deliberately generous bound on that.)

### 5.4 Pre-registered gate — strict order, first matching row wins

`S_low = mean(3 runs' pass-1 WSJT-X count) / archived original WSJT-X count`, same 20 cycles.
Established comparator: `S_busy = 2.30` (5 runs, 754/328).

```python
def m3_row(s_low: float) -> str:
    if s_low < 1.00:  return "ROW 4"
    if s_low < 1.25:  return "ROW 3"
    if s_low < 2.00:  return "ROW 2"
    return "ROW 1"
```

| row | condition | consequence |
|---|---|---|
| **ROW 1** | `S_low ≥ 2.00` | **SUPPRESSION GENERALISES**, not density-dependent. ⇒ The corpus's live WSJT-X `ALL.TXT` is **unsafe as a reference corpus-wide**. Every figure computed against it requires re-derivation. ⇒ Arm R.D **stays unauthorised**. |
| **ROW 2** | `1.25 ≤ S_low < 2.00` | **SUPPRESSION PRESENT BUT DENSITY-DEPENDENT** — consistent with a load/deadline mechanism. ⇒ The reference is unsafe *as a function of density*, which means the **density penalty specifically is confounded** and must be re-derived before it is cited again. |
| **ROW 3** | `1.00 ≤ S_low < 1.25` | **WINDOW/DENSITY-SPECIFIC** — the busy-window result does not generalise. ⇒ Corpus-wide scouting figures survive at low density but not at high; the busy end must be treated separately. |
| **ROW 4** | `S_low < 1.00` | **ANOMALY** — replay yields *fewer* decodes than the original at low density. ⇒ **HALT.** The replay instrument itself is suspect and must not be used further until explained. Escalate. |

Mutually exclusive and exhaustive: a partition of the reals at `1.00`, `1.25`, `2.00`.

### 5.5 Known design limit — state it in the write-up

Within a single corpus, **low density and time-of-day are aliased**: a quiet window is quiet
because propagation differs, so "less density" and "different band conditions" cannot be fully
separated. M3 cleanly tests **whether the ~2.3× suppression is window-specific**; it **cannot**
attribute the cause to density alone. Do not let the ROW 2 wording imply otherwise in any
downstream citation.

---

## 6. M4 — load sweep (GATED)

**🛑 M4 RUNS ONLY IF M1 FIRES ROW 1. Under M1 ROW 2, ROW 3, or ROW 4, M4 MUST NOT RUN.**

Rationale for the gate: M4 tests whether CPU contention can truncate decoding. If M1 shows the
missing decodes are not SNR-biased, the defect is not decode truncation and M4 would be 17
minutes spent testing a hypothesis M1 already rejected.

**3 loaded runs × 1 pass × 5 min = 15 min playback.** The no-load control is free — tonight's
5 runs already provide `W(0) = 754` on this window.

### 6.1 Procedure

Same busy window (`260804_085845 … 260804_090330`), same single-pass configuration as §5.1.
Load applied for the full duration of the pass, defined mechanically as `N` busy-spin threads
at **normal** priority, with `C` = logical processor count from
`(Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors`:

| level | threads | note |
|---|---|---|
| `L0` | 0 | control — **do not re-run**, use tonight's `W(0) = 754` |
| `L1` | `ceil(C / 2)` | |
| `L2` | `C` | |
| `L3` | `2 * C` | oversubscribed |

Record actual achieved CPU utilisation per run, not just the thread count — a spin loop that
gets descheduled is not the load you specified.

### 6.2 Pre-registered gate — strict order, first matching row wins

```python
def m4_row(w1: float, w2: float, w3: float) -> str:
    monotone = (w1 >= w2 >= w3)
    if w3 <= 400 and monotone:  return "ROW 1"
    if w3 <= 400:               return "ROW 2"
    if w3 <= 600:               return "ROW 3"
    return "ROW 4"
```

| row | condition | consequence |
|---|---|---|
| **ROW 1** | `W(L3) ≤ 400` **AND** `W(L1) ≥ W(L2) ≥ W(L3)` | **MECHANISM DEMONSTRATED** — CPU contention is *sufficient* to reproduce the original suppression, with a clean dose-response. |
| **ROW 2** | `W(L3) ≤ 400`, not monotone | **SUPPRESSION REPRODUCED, DOSE-RESPONSE UNCLEAN** — sufficient, but the mechanism is not cleanly characterised. Report all three counts. |
| **ROW 3** | `400 < W(L3) ≤ 600` | **PARTIAL** — load suppresses yield but cannot reach the original 328. ⇒ Contention alone is **not sufficient**; a second factor is required. Escalate. |
| **ROW 4** | `W(L3) > 600` | **NOT SUPPORTED** — 2× oversubscription does not materially suppress WSJT-X yield. ⇒ The original suppression has another cause entirely. Escalate. |

Mutually exclusive and exhaustive: `W(L3)` partitions at `400` and `600`, with ROW 1/ROW 2
split by monotonicity inside `W(L3) ≤ 400`.

Thresholds: `400` sits within ~22% of the original 328 and would count as reproducing it;
`600` is ~80% of the 754 no-load figure and would mean load barely moved the needle. Both are
judgement calls — challenge them before execution.

### 6.3 What M4 can and cannot establish

**M4 can only ever demonstrate *sufficiency*, never that this is what actually happened on
2026-08-03/04.** The original session's load is unrecorded. A ROW 1 result means "a load of
this magnitude can produce this suppression", which is worth having, but it is not root cause
and must never be written up as though it were.

---

## 7. Execution order and gates

```
M0  preserve  ──────────────────────────────────────►  (do first, regardless)
                     │
                     ▼
M1 + M2  one offline script, no playback, ~45 min QA time
                     │
        ┌────────────┴────────────┐
        │                         │
   M1 = ROW 1              M1 = ROW 2/3/4
        │                         │
        ▼                         ▼
   M4 authorised          🛑 M4 MUST NOT RUN
   (15 min playback)         escalate to Architect
        │
        └────────────┬────────────┘
                     ▼
M3  independent of M1's outcome — run regardless
    (worth running whatever the mechanism turns out to be,
     because generalisation is the question that decides
     whether corpus-wide figures survive)
```

M3 does **not** depend on M1. M4 does. M1 and M2 share one script and one data pull.

---

## 8. Cost

| step | playback | machine | QA time |
|---|---:|---:|---|
| M0 | none | minutes | ~20 min |
| M1 + M2 | **none** | none | ~45 min (one script, shared pull) |
| M3 | 15 min | ~17 min | ~1 h incl. window selection |
| M4 *(gated)* | 15 min | ~17 min | ~1 h 10 incl. load spec |

**Total playback if all four run: ~30 min.** Realistic path — M0, then M1+M2, then M3, with M4
only if M1 fires ROW 1 — is **~17 min of audio** to reach the decision-relevant answers.

Budget one false start on M3: tonight's first run cost 22m52s against a 10m30s steady state,
and the 2022 note records an aborted first attempt (WSJT-X Monitor enabled late into pass 1).

Machine constraints: no other audio work during playback; M4 deliberately saturates the CPU so
nothing else should run alongside it. M1 and M2 are offline and can be done on a different day
from the replays.

---

## 9. What this spec does and does not decide

- **Does not touch `src/`.** Everything here is `qa/` tooling plus `artefacts/` gathering.
  No Developer session required (HK-011 not engaged).
- **Is not a capture run.** M3 and M4 replay audio already archived in
  `20260803_live_run_1713`. No new capture is proposed, and per the standing rule none should be.
- **Does not touch Arm R.D, Measurement D, or any existing pre-registered gate.** It does bear
  on whether R.D should be authorised — see §4.4 ROW 1 and §5.4 ROW 1 — but **R.D's own spec is
  unmodified and remains unauthorised.**
- **Does not re-derive any D-001 figure.** I have deliberately not quoted Mechanism 1 or the
  density-penalty numbers anywhere in this spec; the standing citation limit requires opening
  `project-state-2026-07-31-d001-competition-confirmed.md` first, which I have not yet done.
  Any re-derivation is a separate piece of work.
- **Chooses no replacement reference instrument.** The replay harness is the strongest
  candidate this project has had — 5 replicates, span of 7 counts, no duplicates, live WSJT-X
  rather than offline `jt9` — but adopting it is an Architect recommendation for the Captain
  to decide, and I will not put it forward until M3 reports. Two open weaknesses to carry into
  that decision: pass order was never counterbalanced (aliased with Source, though the flat
  interaction makes it a minor worry), and playback peak-normalises to 0.9 (`PLAYBACK_PEAK`),
  which is a real level difference from the original capture whose effect on yield is untested.

---

*Per HK-015 this is Architect → QA; `tasks.md` and any `dev-tasks/*.md` remain QA's to author.
Per HK-014 this is committed locally, not pushed, no merge implied or requested. Per HK-011
nothing here touches `src/`. Per HK-021 every gate above is stated as a hard threshold with its
consequence as an assertion, rows mutually exclusive in strict order, each drafted as the code
that evaluates it — and the three judgement-based thresholds (§3.4, §4.3, §6.2) are flagged as
such for challenge **before** execution, not after. Per NFR-021 no message text or callsign
appears in this document.*
