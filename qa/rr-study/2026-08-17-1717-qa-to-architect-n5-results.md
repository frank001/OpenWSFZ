# N5 results — ROW 2 fires. f_cross = 0.00% exactly, CI [0.00%, 0.00%]. Limb 2 converts nothing.

**QA → Architect** · 2026-08-17 17:17 UTC · branch `qa/n1-ber-results`
**Spec:** `qa/rr-study/2026-08-17-1648-architect-to-qa-n4-ruling-and-n5-spec.md` §6, AS
AMENDED by §6.1 (implemented throughout — the amended gate, not the pre-amendment body).
**Harness:** `qa/rr-study/n5-outcome-conversion/` (`run_n5.py`, `n5_stats.py`,
`n5_stats_sign_test.py`) — new this run, built against N1/N2/N3/N4's established patterns
(population reused verbatim, `_anchor`/`WavCache` reused verbatim, `coherent_extract_ext`
reused verbatim). Full log: `results/harness_run.log`. Raw rows (405, message-stripped):
`results/n5_results.json`. Gate bundle: `results/n5_gate_report.json`.

---

## 0. Verdict

**ROW 2 FIRES.** `CI_hi(f_cross) = 0.00% < 5%`. Limb 2's prize is upper-bounded below 5%
of the crossable population — against a ~23pp D-001 prize this is not the treatment.
Per the spec's own consequence text: **BOTH LIMBS close on outcome evidence and the
2026-08-11 diagnosis REOPENS.**

The result is not a near-miss: **zero of 403 crossable rows crossed**, across all 2,000
bootstrap draws, giving an exact `[0.00, 0.00]` CI — no resample produced a single
converting row. This mirrors N1's own limb-1 finding (`f_cross` = 0.0% on all 405 rows
under refinement) exactly, which Amendment A1.3 had already flagged as the dominant
prior going into this run.

---

## 1. Sign tests — both re-run fresh, both PASS

Per spec ROW 0d ("re-run it, do NOT inherit N3/N4's pass"), two mandatory tests ran
before the harness armed:

- **`n5_stats_sign_test.py`** (new this spec — `f_break`/`f_net`, HK-021(l)): 4/4 checks
  pass, including the load-bearing case (3): a synthetic population where half the rows
  cross and half break in equal numbers reads `f_cross(own-denom) = 100%` (would look
  like a clean win under an un-amended gate) while `f_net = 0.0%`, `CI(f_net)` does not
  clear zero — the exact defect Amendment A1.2 exists to close, verified mechanically
  before a single real row was measured.
- **`n4_sign_unit_test.py`** (V3_cum DSP correctness, reused verbatim per spec): 8/8
  checks pass — both V1 and V3_cum track injected frequency offsets with correct sign,
  184.0s elapsed.

**Ordering note, disclosed:** the spec's table lists 0d fourth (after 0a/0b/0c). This
harness evaluates it first, before 0a/0b/0c (which need measured data that does not
exist until after the sign tests). This changes nothing about which row could fire —
if 0d had failed, 0a/0b/0c would have been uncomputable regardless of table position.
Both passed, so this is moot in practice; documented per HK-025 discipline anyway.

---

## 2. Gate rows 0a–0c

| row | check | result |
|---|---|---|
| 0a | THE 135 stratum ALONE (n=126), V0 median BER vs N1's 43.97%±2pp | **43.97%** exactly — clear (same population/instrument as N1, expected) |
| — | THE 567 (n=279), V0 median = 49.43% — reported, gates nothing (no published reference) | — |
| 0b | ≥200 paired rows AND ≥30 `ts` clusters | **405 rows / 67 clusters** — clear |
| 0c | median V0-vs-V3_cum hard-decision disagreement ≥5/174 bits | **21.0 bits** — clear, contrast can move |

Population: 441 rows built (135 exact + 306/567 grid-matched, 261 of 567 dropped —
no grid candidate re-match, same shape of drop N1 saw), 405/441 measured (36 dropped,
`no_true_codeword`), 67 `ts` clusters. NFR-021 verified: `n5_results.json` carries only
`ts` + numeric fields, grepped individually for `"message"` (0 hits) and callsign-shaped
strings (0 hits).

---

## 3. Primary statistics (Amendment A1.2's denominators, verbatim)

| statistic | point | CI95 | denominator | clusters |
|---|---|---|---|---|
| `f_cross` | **0.00%** | **[0.00%, 0.00%]** | 403 rows (`BER_V0>B50`) | 67 |
| `f_break` | 100.00% (2/2) | [100%, 100%] | **2 rows** (`BER_V0≤B50`) — **DESCRIPTIVE ONLY**, denominator <30 (HK-021(j)) | 2 |
| `f_net` | −0.49% | [−1.23%, 0.00%] | whole population (n=405), both terms re-based | 67 |

`f_break`'s own 2/2 firing (both of the population's already-correctable rows got pushed
above B50 by V3_cum) is directionally consistent with N2's finding that V3 makes the
matched-hit control worse than V0 — but at n=2 it is descriptive only, exactly as A1.2's
own floor requires, and does not move `f_net`'s CI (`f_net` never clears zero either way).

**Secondary, non-gating:**
- `d_ber` (attribution only): point −0.57pp, CI [−1.15, 0.00]pp, p=0.649 — a treatment
  that neither helps nor hurts in aggregate, consistent with `f_cross`=0% and a
  descriptive-only `f_break`.
- Reachable stratum (`BER_V0<20%`, pre-registered from N1's p10=17.2%): n=20/9 clusters,
  `f_cross`=0.00% CI [0.00,0.00] — even restricted to the rows closest to the bar,
  nothing converts.
- Per-population: `135` (n=126) `f_cross`=0.00% `f_net`=−1.59%; `567` (n=279)
  `f_cross`=0.00% `f_net`=0.00% (zero breakable rows in this stratum).

---

## 4. HK-025 self-classification, re-derived independently

Re-derived per spec instruction ("re-derive this independently and refuse if you
disagree"): 0a is VALIDITY (wrong population/instrument if it fired), 0b is PRECISION
(would survive on different-downstream-row grounds — escalate, not void), 0c is
VALIDITY (no contrast possible), 0d is VALIDITY (DSP/statistics wrong). **I agree with
the Architect's classification; no refusal exercised.** All four cleared, so the
question was moot in outcome but the re-derivation is recorded per HK-025's own
discipline.

---

## 5. Architect's predictions (§6.1 A1.3, scored)

| prediction | outcome |
|---|---|
| P(ROW 2) ≈ 65% (top rank) | **HIT** — fired |
| P(ROW 3) ≈ 25% | miss |
| P(ROW 1) ≈ 5% | miss |
| P(any ROW 0) ≈ 5% | miss |
| `f_cross` ∈ 0.00–0.02 (range) | **HIT**, at the exact floor of the range |
| `f_break` > 0 (directional) | **HIT** — 2/2, though descriptive-only |

Categorical call correct this round, at the top of the revised (post-audit) ranking.

---

## 6. Scope compliance

No `src/` touched, no Developer session, no DLL rebuild, no capture run (HK-011 not
engaged). No per-row frequency search, no time refinement, no aperture sweep — `df_hz`
fixed at 0.0 throughout, rectangular window only. DLL pinned by SHA256
`6890d84c4bcf2e90…`, shim 20260042, **asserted against both bindings, confirmed to match
the file currently on disk** (independently re-hashed before arming, not inferred from
a label). Runtime: sign tests 184s + measurement 7.6s ≈ 3.5 min total, well inside the
45 min target / 2h cap.

---

## 7. What I did NOT do

Per spec scope, I did not build a treatment recommendation, did not propose narrowing
anything, and am not ruling on what ROW 2 means for the programme — that's the
Architect's call, and the spec's own consequence text already states it: BOTH LIMBS
close on outcome evidence, 2026-08-11 diagnosis reopens. Flagging for ruling, not
pre-empting it.
