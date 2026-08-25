# QA → Architect — GAP-CENSUS-A results: A1 fires (passband funded), Part B UNRESOLVED (the two mandatory nulls disagree on B2), Part C descriptive

**Author:** QA, 2026-08-25 15:31Z (`date -u`, HK-017). Repo `main` at `d62ca29`.
**Spec:** `qa/rr-study/2026-08-23-2113-architect-to-qa-spec-gap-census-a.md`.
**Status:** COMPLETE. ROW 0 evaluated in strict order — 0a/0b/0c/0f all **PASS**, 0d
(determinism, two full runs) **PASS**, byte-identical. Part A (gated) fires **A1** — the
passband is a funded item, arming the G2(b) ladder is recommended. Part B (gated) fires
**B3, UNRESOLVED** — not for lack of precision (ROW 0e's own bar clears easily) but because
the spec's own mandatory second null disagrees with the first, beyond the spec's own bar,
on bucket B2 specifically. Part C (descriptive) reported in full. Captain authorised via
"read the board and perform the tests"; the spec is pre-registered as a no-`src/`,
no-rebuild, no-capture, offline-only census (HK-011 does not bite), so I did not stop to
ask before running it.

**Harness:** `qa/rr-study/gap-census-a/` (`common.py`, `partition.py`, `wav_spectrum.py`,
`row0.py`, `part_a.py`, `part_b.py`, `part_c.py`, `run_all.py`), committed alongside this
report. Results: `qa/rr-study/gap-census-a/results/2026-08-25-d62ca29/`
(`result.json`, `run.log`, `determinism_run1.json`, `determinism_run2.json`).

---

## 0. NFR-021 disclosure

Both legs' `ALL.TXT` under `artefacts/20260803_live_run_1713/` carry real off-air
callsigns. `common.parse_all_txt` reads `message`, immediately derives `message_norm`
(whitespace-only normalisation) and `has_hash` (does the text contain an unresolved
`<...>` marker), and **discards the original string** — no function past that point ever
receives raw message text. `message_norm` itself (needed as half of the match key) never
leaves `common.Population`'s internal sets/dicts: no report, log line, or JSON file below
contains it. I grepped `result.json`, `run.log`, and both determinism JSONs for
callsign-shaped tokens before writing this report (`grep -RnE
"[A-Z0-9]{1,3}[0-9][A-Z]{1,4}\b"`, filtered for the report's own vocabulary) — none found.
`git check-ignore -v` on the results directory confirms it is **not** ignored (it lives
under `qa/`, not `artefacts/`) and will be tracked as intended.

---

## 1. ROW 0 — all pass

| row | check | result | verdict |
|---|---|---|---|
| 0a | population stated; committed-baseline reproduction/reconciliation | see §1.1 below | **PASS** |
| 0b | partition exhaustive & mutually exclusive, `A+B1+B2+C == theirs_only`; bucket C independently recomputed via a separate code path (HK-022 mitigation) | `1154+754+1133+15653 = 18694 = 18694`; independent bucket-C recomputation agrees **exactly** (same 15,653-key set, not just the same count) | **PASS** |
| 0c | our leg produces zero decodes below `f_min=200.0 Hz` | `n=0` | **PASS** |
| 0d | determinism: two full runs, JSON mechanically diffed | byte-identical (`determinism_run1.json` == `determinism_run2.json`) | **PASS** |
| 0e | null adequacy: null estimator's own 95% half-width ≤ 0.25 pp | worst case (across both nulls, both buckets) = **0.012 pp** | **PASS** (routing consequence moot — see §3.2) |
| 0f | sub-`f_min` decodes are real signal, confirmed against the raw WAV spectrum, not either decoder (HK-026) | median `[140,200)` power **41.7 dB** above the noise-floor band `[5000,5900)`, 60 sampled `owsfz/wav` files, bar 3.0 dB | **PASS** |

### 1.1 ROW 0a — population and the 42.2%/43.05% reconciliation

**Population:** raw distinct `(ts, whitespace-normalised message)` keys, both legs' full
`ALL.TXT` over the entire corpus, **no** epoch filter, **no** hash/band exclusions —
matching the Architect's own §0.2 basis and the f-nbr-a harness's key convention.
`ours=64,417` rows, `theirs=43,423` rows, **zero duplicate keys on either leg** (checked,
not assumed — `len(key_set) == n_rows` exactly both sides), `both=24,729`,
`theirs_only=18,694` ⇒ **D-001 = 43.0509%**.

**Reconciliation, as the spec's own §2 requires:** no committed, citable baseline exists
to reproduce. I went looking (HK-018) rather than assume: the **42.2%** figure
(2026-08-05 Arm R.D spec) was computed on this *same* corpus but over a *different,
filtered* basis — the "decisive epoch" subset (56,202/37,158 rows), not the full raw
`ALL.TXT` (64,417/43,423 rows) — and that spec's own §1 explicitly disclaims it as
"Architect feasibility scouting... must not be cited as a verdict"; its planned §4
QA-independent re-derivation was never completed (the investigation moved to the RC1–RC4
root-cause programme instead). The **43.05%** figure in *this* arm's own §0.2 is likewise
disclosed as exploratory/uncitable (§0.1). Neither is a "committed baseline" in ROW 0a's
sense. This row's population is stated fresh and derived independently; it agrees with
the Architect's own §0.2 number (43.05% both) because both use the same raw-key basis —
the difference from 42.2% is a basis difference, not a disagreement.

---

## 2. Part A (GATED) — the aperture census

| statistic | value |
|---|---|
| bucket A (below `f_min`) | **1,154** decodes, **1,102 distinct cycles** |
| `S_A` (share of theirs-only) | **6.17%** |
| pp of D-001 | **2.66** |
| bar | `S_A ≥ 0.04` |

**ROW A1 fires** (`S_A = 0.0617 ≥ 0.04` and ROW 0f confirms): **the passband is a funded
item.** The G2(b) ladder — specced, five Architect reviews, never armed — is recommended
for arming ahead of the next DSP arm. This is a recommendation only; nothing here
authorises the ladder to ship (§8 of the spec, HK-011/014/010).

`S_A` is a **ceiling**, not a delivery estimate: it assumes every one of the 1,154
sub-`f_min` reference decodes would be recoverable through a passband region that is
dozens of dB above the electrical noise floor (ROW 0f) but was never measured against
*decodability* — that is exactly what arming G2(b) measures. Per the spec's own
instruction, the upper passband edge is out of scope and not re-litigated here (both legs
already produce zero at/above 3000 Hz on this corpus, on the permanently-uncitable list).

---

## 3. Part B (GATED) — the text-recovery census, null-corrected

### 3.1 Observed and the mandatory nulls

| | raw count | cluster count (cycles) | pp of D-001 (raw) |
|---|---:|---:|---:|
| B1 (co-located, our text carries `<...>`) | 754 | 646 | 1.74 |
| B2 (co-located, text differs otherwise) | 1,133 | 935 | 2.61 |

Unresolved-hash rate this corpus: **ours 6.74%, reference 6.61%** — near parity, *unlike*
the 5.5%-vs-1.7% split that motivated G2(a) on the 2026-08-08 leg. Reported as the spec
requires, not omitted because it complicates the B1 story.

**A raw co-location count is not a result** (the spec's own §0.3 lesson) — both mandatory
nulls, 200 seeded trials each:

| null | construction | B1 mean (sd) | B2 mean (sd) |
|---|---|---:|---:|
| 1 | circular frequency shift, **independent draw per cycle**, wrapped `[200,3000)`, preserving each cycle's own decode count | 60.1 (7.7) | 774.0 (29.0) |
| 2 | cycle-label permutation (derangement — every theirs-only decode matched against a genuinely *different* cycle's ours-decodes) | 67.3 (8.1) | 1,209.2 (38.4) |

### 3.2 ROW 0e passes on precision — but the two nulls disagree on B2

Worst-case 95% half-width of either null's own mean, either bucket, converted to pp of
D-001: **0.012 pp**, comfortably under the 0.25 pp bar. **Precision is not the problem.**

The spec's own §5.2 also requires: *"If the two nulls disagree by more than the ROW 0e
bar, say so and read B as unresolved."* Applying that bar to the two nulls' own means:

| bucket | null 1 mean | null 2 mean | disagreement (pp) | bar | verdict |
|---|---:|---:|---:|---:|---|
| B1 | 60.1 | 67.3 | 0.017 | 0.25 | agree |
| **B2** | **774.0** | **1,209.2** | **1.002** | 0.25 | **DISAGREE — 4× the bar** |

**This is the mechanical trigger for ROW B3.** I did not smooth it away, average the two
nulls, or pick the more convenient one — the spec names this exact failure mode and its
exact consequence, and it fired.

**A candidate explanation, disclosed as a hypothesis, not scored, not gating anything:**
the circular-shift null always compares a cycle's theirs-only decodes against *that same
cycle's own* ours-decode count; the permutation null compares them against an unrelated
cycle's count. If a cycle's own ours-decode density and its theirs-only yield are
correlated across the corpus — exactly the mechanism Measurement D/X1/X2 already
established (we do worse specifically when the band is dense) — the two nulls are not
measuring the same thing, and B2 (the larger, noisier bucket) is where that shows up. This
is a hypothesis about *why*, offered because leaving the disagreement unexplained invites
someone to explain it later with the retired spectral-locality metric; it is **not** a
frequency-separation stratification (§6's prohibition) and it changes no gate outcome.

### 3.3 Excess against null 1 (reported, not actioned — Part B did not clear its gate)

| bucket | excess (count) | 95% CI | pp | pp CI |
|---|---:|---|---:|---|
| B1 | 693.9 | [668.1, 719.8] | 1.60 | [1.54, 1.66] |
| B2 | 359.0 | [294.8, 423.3] | 0.83 | [0.68, 0.97] |

Both individually exclude zero against null 1 alone, and B1 dominates B2 — which is
exactly the shape the spec's B1 row (§5.3) would fire on. **It does not fire**, because
ROW B3's precondition (null agreement) is evaluated first and fails. **ROW B3: text
recovery is not established. Report the counts and the null; propose nothing** — no
G2(a) re-measure recommendation is issued from this arm's Part B. (The re-measure remains
independently on the board as arm #2 in the running order regardless of this result — see
§6.)

One disclosed convention, not spelled out in the spec: where a theirs-only decode's
matching window contains more than one ours-decode, I classify it **B1 if any** matching
decode carries a hash marker (else B2) — a hash-carrying match is the more specific,
more decision-relevant condition. This tie-break affects a small minority of the 1,887
co-located keys (multiple ours-decodes within an 8 Hz window at ~14 decodes/2,800 Hz is
uncommon) and does not change which ROW fires.

---

## 4. Part C (descriptive, not gated) — the residual

| statistic | value |
|---|---:|
| bucket C (genuine DSP miss) | **15,653** decodes, **3,944 distinct cycles** |
| pp of D-001 | **36.05** |

**SNR stratum composition** (pinned L1 edges `[-15,-10,-5,2]`, never re-derived):

| stratum (dB) | n | share |
|---|---:|---:|
| (−∞, −15] | 8,331 | 53.2% |
| (−15, −10] | 3,906 | 25.0% |
| (−10, −5] | 2,029 | 13.0% |
| (−5, 2] | 959 | 6.1% |
| (2, +∞) | 428 | 2.7% |

Over half of bucket C sits below −15 dB — consistent with a genuine sensitivity/SNR-floor
story, not a marginal-signal artefact. **Band stratification: not applicable** — this
corpus is single-band (20m, 14.074 MHz) on both legs; nothing to stratify by band on here
(disclosed rather than silently omitted).

**Diagnostics (informational, no consequence, per §6):**
- Max OpenWSFZ decodes in any one cycle: **30**, against `K_MAX_DECODED` caps of 340/540 —
  a third independent confirmation that the candidate-budget family has never bound.
- Miss rate `[200,250)` = 260/1,186 = **21.9%**, against a `[700,3000)` baseline of
  11,004/25,624 = **42.9%** — the inward edge is *better* than average on this corpus too
  (consistent with the Architect's own §0.2 finding on the earlier 19.9%-vs-38.3% figures;
  the small difference from those numbers is the population-basis difference already
  reconciled in §1.1, not a new finding).

🛑 **No stratification of bucket C by frequency separation to a neighbouring decode was
performed, in any form** (spec §6 prohibition; the retired spectral-locality metric).

---

## 5. The addition — spec §7's deliverable

**Additive table** (mechanically enforced by ROW 0b — raw counts, exhaustive and mutually
exclusive by construction):

| bucket | raw count | cluster count | null (mean, primary=circular-shift) | excess | pp of D-001 (raw) | pp of D-001 (excess) |
|---|---:|---:|---:|---:|---:|---:|
| A | 1,154 | 1,102 | n/a (census, no null needed) | 1,154 | 2.66 | 2.66 |
| B1 | 754 | 646 | 60.1 | 693.9 | 1.74 | 1.60 (UNRESOLVED — §3) |
| B2 | 1,133 | 935 | 774.0 | 359.0 | 2.61 | 0.83 (UNRESOLVED — §3) |
| C | 15,653 | 3,944 | n/a (descriptive) | — | 36.05 | — |
| **sum** | **18,694** | — | — | — | **43.05** | — |

Raw-count pp sums to **43.0509%**, matching `D-001` computed directly (43.0509%) to
6 significant figures — the addition identity holds exactly, as ROW 0b already asserted
mechanically.

**NOT ADDITIVE** (carried from the spec's own §0.4/§7 list — cited, not independently
re-verified in this arm):

| item | value | why it is not in the table above |
|---|---|---|
| `G(3)` | ≈6.995 pp | a ceiling **inside** bucket C, not an increment beside it |
| `T1` | ≥3.16 pp floor | inside C, closed treatment (OSR) |
| `X2` | +17.22 pp | a **contrast** (crowding), not a share |
| `X1` | +5.70 pp | a **contrast** (band), not a share |
| `X3` | 1.85 pp | ROW 4 outcome, **not citable** |
| `P3` | 4.27 pp | doubly compromised (pre-hash-fix, unmerged RC4 DLL) |

---

## 6. What this arm does not settle, and what is still queued

- **Does not arm G2(b).** A1 recommends; arming is the Captain's decision (spec §8).
- **Does not recommend a G2(a) re-measure from Part B** (B3 fired, not B1) — but arm #2 in
  the running order (`G2A-REMEASURE-A`) stands independently of this result; nothing here
  argues against running it.
- **Did not replicate on the three weekend corpora** (spec §2's "secondary, reported
  alongside" instruction). The harness generalises to another corpus by changing four path
  constants in `common.py`; I did not spend the time to run it against all three this
  session and am flagging that as undone rather than silently skipping it (HK-004) — a
  follow-up call for the Captain/Architect, not something I judged unnecessary.
- Per the spec's own running order: `G2A-REMEASURE-A` (2) is next and strictly depends on
  this arm's bucket definitions/null construction, which it reuses verbatim — both of
  which are now exercised and passing ROW 0. G2(b) `140 Hz` rung (3) and `OSD-FA-A` (4)
  remain independently runnable per the withdrawal memo.

Per HK-011/014/010: no `src/` change, no rebuild, no push, no merge, no
`pre_merge_check.py`. Committed locally only.
