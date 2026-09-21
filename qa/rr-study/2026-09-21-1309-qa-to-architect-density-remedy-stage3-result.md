# `DENSITY-REMEDY` Stage 3 — result: **both finalists REJECTED, ROW F** — the additions are far dirtier than what V0 already emits; 🔴 **and neither would have cleared `GAIN_BAR` anyway** (`(−5,+15,0.0)` ΔR **−0.257 pp**, `(−5,+15,0.5)` ΔR **+0.193 pp**, bar 0.5 pp)

QA, 2026-09-21 (`date -u`, HK-017). Per spec `2026-09-19-1228-architect-to-qa-spec-density-remedy-suppression.md` §6 as ruled by
§17 and §18 (`arch/density` `6bf2bd03`). Harness `qa/rr-study/density-remedy/stage3_replay.py`, **pre-registered `86040caa` before any leg
decoded**. **Ratified by the Captain, committed `343d095d` BEFORE `F1`/`F2` decoded** (`results/stage3_ratified.json`: strict-corroboration
`U_base` rule, value **0.0553**, `GAIN_BAR` **0.5 pp**, recorded together).
🛑 **No default changes in this arm.** Nothing here is ship-eligible; ROW S did not fire for either finalist.

**Headline.** On the 5,222-cycle C2 replay, **neither footprint finalist is worth shipping**:

| | `F1` = (−5,+15,**0.0**) | `F2` = (−5,+15,**0.5**) |
|---|---:|---:|
| **verdict** | **ROW F — REJECT** | **ROW F — REJECT** |
| added decodes (`u_add + k_add`) | 880 (579 + 301) | 798 (473 + 325) |
| uncorroborated share of additions | **0.658**, CP95 [0.626, 0.689] | **0.593**, CP95 [0.558, 0.627] |
| bar (`U_base`, ratified) | 0.0553 | 0.0553 |
| **ΔR** (`R_wild`, V0 → variant) | **−0.257 pp** (−234 REF rows) | **+0.193 pp** (+176 REF rows) |
| bar (`GAIN_BAR`) | 0.5 pp (455 rows) | 0.5 pp (455 rows) |
| corroborated decodes added / removed | 301 / **580** | 325 / 236 |

🔴 **Four things to read before citing it.**
1. **ROW F is not a small-`n` artefact and not near the bar.** The *lower* Clopper-Pearson bound (0.626 and 0.558) is already **11.3× and 10.1×** the bar (0.0553). The row fires on the interval's lower edge, so the estimate and the interval agree.
2. **The rejection is over-determined (HK-021(k)).** ROW N would have fired for **both** finalists as well (ΔR < 0.5 pp). Neither the `U_base` rule nor its value, nor the row order, changes the outcome. Wildcard-only matches are only **0.86 % / 1.06 %** of `u_add`, so the strict-versus-lenient corroboration choice is **immaterial here**.
3. 🛑 **"Uncorroborated" is not "false".** It means WSJT-X #1 (the REF) has no row at the same cycle, ±3 Hz, exact text. The additions are decodes V0 did not make; REF absence bounds genuine gain from below and `u_add` bounds FP from above. **Never write "the additions are false positives".** This is a raw-C-ABI replay **without** `IsPlausibleMessage` or text dedup, so junk the app would filter counts against **both** legs; `U_base` is measured on the same footing, so the comparison is like-for-like, the absolute rate is not the live one.
4. **`F1` is a net loss, `F2` a small net gain, and no interval was pre-registered on ΔR.** Both are point estimates. Do not present `F2`'s +0.193 pp as a result; it is below the bar and the harness gives no CI.

---

## 1. HK-020 / HK-022 — critical config

| item | value |
|---|---|
| Binary | `decoding_improvement` `fa8a56ae`, `libft8.dll` SHA-256 `38a21f840b00af146348c166786cb54e178cd2201c5ed4dba3016a4c589a1cba`, shim `20260054`. **One DLL for every leg**, SHA and version checked in every leg process (`meta.sha` identical in `V0`/`VN`/`F1`/`F2`) |
| Params | `ft8_set_decode_params(10, 0.10, 40)` set once before the first decode; `table_ok = True` in every leg. Suppression triple read back with `ft8_get_supp_params`: `F1` (−5,15,0.0), `F2` (−5,15,0.5), `VN` (−5,15,1.0), `V0` default; **`supp_ok = True` in all four** |
| Test filter | **none**: Python/ctypes harness, nothing can be filtered out silently |
| Commands | `stage3_replay.py leg --leg F1` and `--leg F2` (parallel, detached, `launch_legs2.sh`); then `stage3_replay.py measure`; then `stage3_replay.py nullcheck` |
| Corpus | C2, `corpus.c2_cycles()`. **Every leg executed 5,222 cycles, same cycle list (sha256 prefix `b7acfd10b2a6`), `n_av = 0`, `n_truncated_at_max = 0`.** The leg's own executed count is the denominator (§18(e)) |
| Open item | catalogue 5,222 vs `DENSITY-LIVE` S1 4,113 (21 %) **still unreconciled**; neither chosen |
| Ratification | `343d095d`, before any finalist decode; `measure` asserts `u_base_value` equals the V0-derived value to 1e-12 |

## 2. ROW 0 (all evaluated before any finalist leg, from the baseline legs; unchanged)

| row | result |
|---|---|
| **0a-pipeline** (gates) | ✅ **0.9887** vs 0.90 (not near-bar) |
| **0a-delta** (reported) | 0.9671 |
| **0b** | ✅ `S1` ≡ `S2` byte-identical |
| **0c** | ✅ placebo `D` = 0.028, CI95 [0.014, 0.043], inside ±0.05 |
| **0d** | ✅ headers agree; one cycle list; finalist read-backs as registered |
| **0e** | ✅ null leg `VN` identical on outcome **and** text on all 5,222 cycles; re-run today by `nullcheck` over 59,758 pairs: **0 added, 0 removed, ΔR = 0.0 exactly** |
| **`row0_fires`** (as `measure` read it) | **false** |

The null check matters: it exercises the same pairing and corroboration code as `measure`, and it returns exactly zero, so the non-zero churn below is the variant's, not the plumbing's.

## 3. What each finalist did (counts; churn is reported, never gated)

| | `F1` (0.0) | `F2` (0.5) |
|---|---:|---:|
| added: corroborated / wildcard-only / uncorroborated | 301 / 5 / 574 | 325 / 5 / 468 |
| removed: corroborated / wildcard-only / uncorroborated | 580 / 20 / 552 | 236 / 8 / 524 |
| net decodes (added − removed) | −272 | +30 |
| tie-break events (used text) | 394 (393) | 397 (396) |
| `ΔC` (reported) | +0.116 pp of `C_V0` = 4.413 | +0.090 pp of `C_V0` = 4.413 |

- `F1` removes **580** corroborated decodes and adds **301**: a net loss of about 279 corroborated decodes, which is the sign of its ΔR.
- Both variants swap a similar number of uncorroborated rows in and out (`F1` 574 in / 552 out; `F2` 468 in / 524 out). Only the direction of the net change differs.
- `ΔC` is the harness's density-cost measure (§ pre-registration, **reported, not a gate**). The footprint lever moves it by **0.09–0.12 pp against a `C_V0` of 4.413**. `C_V0` is this harness's figure (current DLL, `nhard` 40), **not Stage 0's ≈4.30 pp** (`6b2e16a6`, `nhard` 60, pre-`PASSBAND-140`); do not equate them without those qualifiers.

## 4. The two mandatory stratifications — **REPORTED, NO VERDICT READ FROM THEM** (§18(g))

Gained = REF rows the variant recovers and V0 does not; lost = the reverse. Net over all strata: `F1` **−234**, `F2` **+176** (= ΔR × 910.46 exactly).

**By the blocker's reported SNR in the V0 leg**

| stratum | `F1` gained / lost / net | `F2` gained / lost / net |
|---|---:|---:|
| blocker ≥ +5 | 95 / 7 / **+88** | 52 / 1 / **+51** |
| blocker < +5 | 40 / 39 / +1 | 55 / 16 / +39 |
| blocker not decoded by V0 | 0 / 1 / −1 | (none) |
| **no neighbour** | 169 / 491 / **−322** | 228 / 142 / **+86** |
| total | 304 / 538 / −234 | 335 / 159 / +176 |

**By Δf band**

| band | `F1` net | `F2` net |
|---|---:|---:|
| 0–6 Hz | +26 (33 / 7) | +17 (21 / 4) |
| 7–12 Hz | +19 (29 / 10) | +20 (22 / 2) |
| 13–18 Hz | +43 (73 / 30) | +53 (64 / 11) |
| no neighbour | −322 (169 / 491) | +86 (228 / 142) |

Observations only, no mechanism claimed and **no row is read from any of it**:
- In the **blocker ≥ +5** stratum both finalists gain far more than they lose, the direction the bench switch predicts. That stratum is a **minority of the gained rows** (95 of 304 for `F1`, 52 of 335 for `F2`).
- The **largest gained stratum for both is "no neighbour"** (169 and 228 rows), and it is also **where `F1` loses 491 rows**. That one stratum decides `F1`'s sign.
- **Δf-banded nets are positive in every band with a neighbour, and rise with Δf** (13–18 Hz largest), not flat.
- These arbitrate the Stage 0 / Stage 2 tension only in the Architect's reading; QA reads no verdict from them. 🔴 They inherit Stage 0's caveat that a neighbour WSJT-X did not decode is invisible.

## 5. What this could NOT see (HK-022 / HK-026)

1. **One corpus** (C2, 20 m, two days) and **a replay, not the live path**: raw C-ABI without `IsPlausibleMessage` or text dedup.
2. **The C2 live leg ran an older binary at `nhard` 60**; the replay is `nhard` 40 on the current DLL (`0a-pipeline` 0.9887 says the pipeline reproduces it at 60).
3. **REF is one decoder, WSJT-X #1**: corroboration bounds genuine gain from below and `u_add` bounds FP from above.
4. **Neighbours WSJT-X did not decode are invisible** to the stratifications.
5. **No interval on ΔR** was pre-registered, so `F2`'s +0.193 pp and `F1`'s −0.257 pp are unqualified point estimates.
6. **The bench numbers (`G` = 0.492) are pooled bench figures and are never compared with these.** Different quantities.
7. **Windows DLL only.** Defaults were never changed; each leg set its triple at runtime.

## 6. Status and what is needed

- ✅ **Stage 3 is computed as pre-registered and ratified.** Both finalists: **REJECT (ROW F)**, and ROW N as well. **No ship-eligible variant.** Stage 2 left **no third-ranked variant**, so **there is no substitute without a re-run** (§17).
- Predictions §18.8 are the Architect's to score. **The inputs:** **S1** (`F1` ΔR < 1.0 pp): yes, −0.257. **S2** (`F1` clears 0.5 pp): **no**. **S3** (neither finalist increases `u_add` above `U_base`'s share): **does not hold, both do**: 0.658 and 0.593 against 0.0553. **S4** (`0a-pipeline` ≥ 0.90 first time): yes, 0.9887. **S5** (live gain concentrates in blockers ≥ +5): the ≥ +5 stratum is **31 % (`F1`) and 16 % (`F2`)** of gained rows, and "no neighbour" is the largest; scoring is the Architect's.
- 🛑 **Pending decisions are not QA's:** what Stage 3 does to the density arm, and whether the Stage 0 flat-Δf finding and the Stage 2 bench switch are now reconciled. QA read no verdict from the stratifications.
- 🛑 **Push and route of `qa/density-remedy` (20 commits, local-only) needs the Captain's go (HK-033).**
- Artefacts: `artefacts/density-remedy-stage3/` (gitignored, real callsigns; `F1`/`F2` `.jsonl` + `.meta.json`, `logs/`, `launch_legs2.sh`, `measure_stdout.txt`). Committed: `results/stage3_ratified.json` (`343d095d`) and `results/stage3_verdict.json` (counts only; NFR-021 scanned, 0 callsign-shaped tokens in the JSON, and the prose above carries counts and category labels only).

---

*Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>*
