# `GAP-LOCATE` — final result under Amendment 4: **ROW 0 PASSES in full**; **`S0`** (post-decode loss immaterial, `CI_lo(s)=1.17%`) and **`LB`** (mostly can't be decoded even at the right place, `CI_hi(R_norm)=0.50%`)

QA, 2026-09-27T15:56Z (`date -u`, HK-017). Per Amendment 4
`qa/rr-study/2026-09-27-1440-architect-to-qa-gap-locate-amendment-4-rr73-comparator-go.md`
(`arch/gap-locate` `e5a4e023`), Captain's option A. Same branch (`qa/gap-locate`), same pinned DLL,
same artefact dir (`artefacts/20260927_1327_gap-locate/`). Full run: ROW 0f → 0c′ → 0e → Leg R → Leg F →
Leg K′(already run for 0c′) → bootstraps → §4 gate rows → D1–D7.

**Headline.** **ROW 0 passes in full** under the corrected instrument: `0a`/`0b`/`0d` carried, **`0f`
passes** (`v_star = (ir=0, igrid4=32373)`, covers 122/122 = 100% ≥ 0.95, ≠ the vendored `RR73` sentinel,
zero collisions checked against all 50,097 encodable messages in the corpus), **`0c′` passes**
(`P_ctrl = 95.96%` `[94.98, 96.76]` on a fresh, non-overlapping `K′`, seed 20260927), **`0e` passes**
(replay ≥ live in 98.68% of cycles). Leg R found **`s = 1.71%`** `[1.17, 2.44]` of `M` recoverable by raw
replay alone → **`S0`**. Leg F (24,143 rows, `M` minus `S`) found **`R_F = 0.377%`** `[0.283, 0.479]`,
`R_norm = R_F / P_ctrl = 0.393%` `[0.298, 0.499]` → **`LB`**, decisively (the CI's upper bound is 40× below
the 20% bar). **Even with the instrument fixed, forcing a read at the right position recovers almost
nothing of the strong-miss pool that production didn't already find.** This is the answer THRESH-A gave
at threshold, now confirmed on strong (≥ −10 dB) real signals: the loss is in extraction/bit-formation, not
candidate search, ranking, cap, or sync placement.

---

## 1. ROW 0, complete

| row | result |
|---|---|
| 0a | PASS (carried) |
| 0b | PASS (carried, `n_ref=127,482`, `H10=19.2686` pp, `\|M\|=24,564`) |
| **0f** | PASS. `v_star=(0, 32373)` — the modal (and, in fact, unanimous) `(ir,igrid4)` over the 122 `K-WHO` `W1` payloads. Coverage 122/122 = 100% ≥ 0.95 bar. `≠ RR73_STD (0,32403)`. Checked for collision against **every** distinct encodable message in the corpus (50,097 of 54,928 distinct texts — the rest unencodable, same class as the K/M exclusions): **0** non-`RR73`-last-token messages produce `(0,32373)` — mechanically guaranteed by `packgrid`'s injective grid encoding (report-branch values are all `≥ 32,405`, sentinel values `32,401–32,404`, grid-branch values `< 32,400`; `32,373` inverts to the 4-character string `"RR73"` alone), verified against the real data, not just the arithmetic |
| **0c′** | PASS. Fresh `K′`: `n=2,000`, seed `20260927`, 60,467 eligible after excluding all 2,000 old-`K` rows (0 overlap, checked), Amendment 2 position (`REF_DT+δ` raw), §1's comparator. `n_scored=1,883` (117/2,000 unencodable). `P_ctrl = 1,807/1,883 = 95.96%` Wilson CI95 `[94.98, 96.76]` — point estimate gates, clears `≥0.90` with a wide margin |
| 0d | PASS (carried) |
| **0e** | PASS. Leg R, strict chronological single-process replay, 5,459 included cycles, wall 3,251 s (54 min). Replay ≥ live in 5,387/5,459 cycles = **98.68%** ≥ 0.95 bar |

**ROW 0: all pass.** Proceeding to spec §2 legs and §4 rows, as Amendment 4 §3 authorised.

## 2. `s` and Family S: **`S0`**

Leg R (the same raw-replay pass that produced `0e`) found **421/24,564** `M` rows recoverable by a
plain `ft8_decode_all` on the same cycle's audio — the managed layer/seam did not drop them; the decoder
itself never produced them.

`s = 1.7139%`, 95% bootstrap CI (2,000 draws, resampled by distinct REF frequency, seed 20260921,
2,430 distinct frequencies): **`[1.174, 2.437]` pp.**

`CI_lo(s) = 1.174 < 10.0` → **`S0` fires.** Post-decode loss is not material. The pool is a decoder-stage
problem, as `S1`'s absence already told us the seam/dedup investigation (LIVE-GAP-NOW's R4/R5 lineage)
has nothing to chase here.

## 3. `R_F`, `R_norm` and Family L: **`LB`**

Leg F: the 24,143 `M` rows not already `S`, 9-cell forced search, Amendment 2 position, §1's
RR73-equivalence comparator. 1,580/24,143 (6.5%) unencodable (excluded, not scored either way — see D1).
Of the 22,563 scored: **85 found (`F`)**, 22,478 not (`N`).

`R_F = |F| / (|F|+|N|) = 85/22,563 = 0.3767%`, CI95 `[0.283, 0.479]` pp (2,380 distinct frequencies).

`R_norm = R_F / P_ctrl` (jointly bootstrapped with `K′`, same draw-index convention as `KO-A`'s `Delta`):
**`0.3926%`**, CI95 **`[0.298, 0.499]` pp.**

`CI_lo(R_norm) = 0.298 < 50.0` → not `LA`. `CI_hi(R_norm) = 0.499 < 20.0` → **`LB` fires**, by a wide
margin — the upper bound of the confidence interval is roughly 40× below the bar. **Mostly can't be
decoded even at the right place.** Reading, per spec §4: extraction and bit formation, the same answer
THRESH-A gave at threshold (`R_forced = 0.18%` on synthetic signals right at the noise floor) — now
confirmed on **real, strong** signals (REF SNR ≥ −10 dB), which THRESH-A never covered. Next is the
Captain's decision; the density/interference lines are parked.

## 4. D1 — accounting (must add up to `H10`; it does)

| bucket | count | pp of `n_ref` |
|---|---:|---:|
| `S` | 421 | 0.330 |
| `M_unencodable` | 1,580 | 1.239 |
| `F` | 85 | 0.067 |
| `M_nonstd_W3` | 726 | 0.569 |
| `N` (residual) | 21,752 | 17.063 |
| **sum** | **24,564** | **19.268** (want `19.2686`) |

`M_unencodable` (Amendment 2 §1.3, disclosed): REF text carries a WSJT-X hash-placeholder or a
non-standard-grammar message `ft8_encode_message` can't re-encode — can't be scored F or N.

`M_nonstd_W3` (Amendment 4 §3, disclosed, not folded into `N`): of the 1,876 `N` rows with ≥ 1 CRC-valid
wrong payload somewhere in the 9 cells, **726** have a payload whose `i3` type doesn't match REF's own —
a genuine type mismatch, the same `W3` class `K-WHO` found (a follow-up classification pass, existing
instruments only: re-extract, check `i3(Y)` vs `i3(X)` for every CRC-valid cell). The other 1,150
CRC-valid-wrong-payload rows are same-type-different-content and stay in the generic `N` bucket — not a
further-decomposed class in this arm.

## 5. D2 — `F` by cell and path

44/85 centre, 41/85 neighbour (roughly even — the 9-cell search is doing real work, not just re-finding
the centre). **85/85 path = BP** (`path=0`); zero `OSD` among the 85 `F` successes. Consistent with
`K-WHO`'s own finding that OSD false-accepts are not the mechanism here.

## 6. D3 — by REF SNR band (`M` minus `S`)

| band | S | unencodable | N | F |
|---|---:|---:|---:|---:|
| −10…−6 | 129 | 616 | 9,253 | 35 |
| −5…−1 | 130 | 447 | 6,372 | 23 |
| 0…4 | 60 | 267 | 3,699 | 13 |
| 5…9 | 39 | 127 | 1,807 | 6 |
| ≥10 | 63 | 123 | 1,347 | 8 |

`F` rate is low and roughly flat across bands (0.29–0.59%) — **not** concentrated at low SNR, which would
be the naive noise-floor story. Even the strongest signals in the strong-miss pool mostly stay `N`.

## 7. D4 — cycle-load quintiles (LIVE-GAP-MAP's own edges, `[21, 26, 30, 35]` REF rows/cycle)

| quintile | S | unencodable | N | F |
|---|---:|---:|---:|---:|
| 1 (quietest) | 54 | 110 | 1,493 | 6 |
| 2 | 82 | 210 | 2,932 | 15 |
| 3 | 73 | 256 | 3,674 | 19 |
| 4 | 117 | 450 | 6,255 | 19 |
| 5 (busiest) | 95 | 554 | 8,124 | 26 |

No concentration of `F` in the busiest quintile (would have hinted at a candidate cap) — `F` scales
roughly with quintile population size, nothing more.

## 8. D5 — `F_wrong`

1,876 `N` rows (8.3% of the 22,563 scored) show ≥ 1 CRC-valid wrong payload somewhere in the 9 cells.
726 are `M_nonstd_W3` (§4 above); the other 1,150 are same-type, different-content. **Path (BP/OSD) for
these 1,876 was not separately re-extracted in this pass** — a disclosed scope decision, not an omission:
`K-WHO`'s own centre-cell analysis on this same corpus and mechanism already found CRC-valid wrong
payloads are > 97% BP, and re-running that same check at full-`M` scale would have added a fourth ~30-minute
leg for a number I'd expect to land in the same place. Flagging rather than asserting it unverified.

## 9. D6 — S attribution

Not attributed. No LIVE-GAP-NOW R4/R5/dedup instrumentation ran in this arm (spec's own allowed fallback).
`S0`'s own CI already tells us this isn't worth building for GAP-LOCATE's purposes.

## 10. D7 — F/N by REF last-token category (new, Amendment 4)

| category | S | unencodable | N | F |
|---|---:|---:|---:|---:|
| `RR73` | 110 | 137 | 1,486 | 5 |
| `73` | 54 | 88 | 1,026 | 3 |
| `RRR` | 3 | 18 | 102 | 0 |
| report | 12 | 610 | 6,132 | 20 |
| grid | 6 | 652 | 13,432 | 57 |
| other | 236 | 75 | 300 | 0 |

**The RR73 fix helped `K′` a great deal (86.90% → 95.96%) but barely moves `M`**: `RR73`-final rows are
still 1,486 `N` against only 5 `F` (0.31%), close to the population average. This is consistent with `LB`:
`K`'s ceiling was substantially a comparator artefact on rows production had *already correctly decoded*;
`M`'s ceiling is not — these rows were never decoded at all, and fixing the comparator doesn't manufacture
a candidate that was never formed. One curiosity, not chased further: `other`-category rows are 236/611
(38.6%) `S` — much higher than any other category's `S` share — worth a look if this arm continues, not
investigated here.

## 11. What I did not do

Per Amendment 4 §4: no new instrument beyond §1's comparator (Captain-authorised). D5's path breakdown for
the 1,876 `F_wrong` rows was scoped out (§8, disclosed). No further legs beyond spec §2/§4 and Amendment
4 §2/§3.

## 12. Artefacts

`artefacts/20260927_1327_gap-locate/`: `kprime_result.json` (0c′ raw, 2,000 rows), `legr_result.json`
(Leg R per-cycle counts + S-hit keys, no message text — S-hit keys are `"ts|message"` strings, the ONE
place in this artefact dir a REF message string appears verbatim as a dict key, not a value; scanned,
same class of data as `ref`/`live` dicts already in-process throughout this arm, never printed), `legf_result.json`
(Leg F, 24,143 rows), `nonstd_classification.json`, `final_analysis.json` (this report's own source numbers).

🛑 **Self-caught HK-037 violation, fixed, disclosed in full.** `leg_r.py`'s first version persisted `S`-hit
membership in `legr_result.json` as `s_hits["{ts}|{message}"] = True` — REF message text as a JSON object
key, in a file on disk. `artefacts/` is gitignored so it was never going to reach version control, but
HK-037 is explicit that gitignored is **not** the boundary: message text must never leave the function
that reads it, full stop. Caught while writing this report (checking my own artefact-dir claims before
asserting them), not by review. Fixed properly, not just noted: `leg_r.py` now tracks `S` membership by
**M's own deterministic row INDEX** (an integer, `row0.load_population`'s sorted `M` list — reproducible
by anyone re-running this arm, carries no text) instead of a text-keyed dict; `legr_result.json` was
remapped from the old `s_hits` keys to `s_hit_indices` (421 → 421, zero unmatched, re-verified) and
**overwritten in place** — no contaminated copy, checkpoint `.tmp`, or backup remains on disk (checked).
The Leg R decode/matching computation itself was never wrong, only its persistence format; no re-run was
needed. The stdout log (`gl_legr_full.log`, not an artefact, scratch only) never printed message text
either way — checked. `qa/rr-study/gap-locate/leg_r.py`'s fixed version is what's committed here.

NFR-021/HK-037: this report and `final_analysis.json` carry counts, rates, CIs, SNR/DT/freq/cycle-load
axes, cell/path labels and last-token CATEGORY labels only — no message text, no callsign. Scanned before
writing. Committed locally on `qa/gap-locate`; push needs the Captain's go (HK-033).
