# `DENSITY-REMEDY` Stage 0 — result: **`floor+footprint`**, ROW 0 silent — both levers clear the 0.5 pp bar by a wide margin, **but the census says where a lever COULD act, not that the loss is caused there, and the footprint's bucket does not concentrate where its mechanism predicts**

QA, 2026-09-19 12:47Z (`date -u`, HK-017). Per spec `2026-09-19-1228-architect-to-qa-spec-density-remedy-suppression.md`
§3 + §10 (`arch/density` `2f6ba3e2`). Harness `qa/rr-study/density-remedy/stage0_census.py`, **pre-registered before any
share existed** as `77e129ee`, with the ROW 0c sample fixed in the same commit. **No build, no Developer contact.**
Stage 1 (the build) is **not started**.

**Headline.** Of the **5,085** missed EXPOSED victims, the dominant neighbour was **not decoded** for 26.3 % (N0: no lever
can act), had **factor ≥ 0.90** for 12.2 % (RA, floor), **0.50–0.90** for 19.8 % (RM, both) and **≤ 0.50** for **41.7 %** (RB,
footprint). Applying the pre-registered rule (C = 4.30 pp, `REACH_BAR` = 0.5 pp): **floor 1.378 pp, footprint 2.644 pp, both in.**
The bar needs only an 11.6 % share; the floor bucket set holds 32.1 % and the footprint set 61.5 %. A ±1 dB error in our SNR
does not change either verdict (§6).

🔴 **Three things to read before citing it.**
1. **RB is not concentrated where a footprint mechanism predicts.** RB's share is **38.8 %** at Δf 0–6 Hz, **43.1 %** at 7–12
   and **43.6 %** at 13–18. The bench's collateral was a *dose* driven by overlap bits (84 / 27 / 12 per trial at Δ 6.25 / 12 /
   18.75); a ±1-bin footprint should bite hardest at small Δf. It does not. RB is better read as "**strong neighbour**" (reported
   ≥ +5 dB) than as "**collateral**". Its footprint reach is therefore an **upper bound with doubt**, not a forecast.
2. **RB victims are the hardest to recover: 1.35 %** (29 of 2,147), against **11.8 %** for RM, 6.6 % for N0 and 3.1 % for RA
   (post-hoc, §6). Strong-neighbour victims are lost at a rate no bucket approaches.
3. **The reach is a proportional attribution of the 4.30 pp, not a ceiling** (§4 note).

---

## 1. HK-020 / HK-022 — critical config

| item | value |
|---|---|
| Corpus | **C2** `artefacts/20260908_live_run_1827-fp-floor-live-2/`, `corpus.c2_cycles()` window: **5,222** cycles; REF **91,046** rows; TEST (live `ALL.TXT`) **57,969** rows |
| C2 qualifiers | 🔴 travel with **every** number: live binary `6b2e16a6` (shim `20260050`), **nhard 60**, **pre-`PASSBAND-140`**. Not the current binary, not nhard 40 |
| Classes | `density_live.classify()`, verbatim; the REF-only class table reproduces `DENSITY-LIVE` §2.1 exactly (its own hard gate) |
| Replay (ROW 0c only) | Stage 1 DLL SHA-256 `50e94e7d73e33050ac37145ac675ad467415324b9cbc5183dc47f3e361829bb7`, shim `20260053`; `ft8_set_decode_params(10, 0.10, 60)` **SET, read-back impossible** (no getter); PCM via `p23_common.read_wav` → `normalise_rms(0.20)`, the audited production-mirroring path |
| Test filter | **none** (Python harness; nothing can be filtered out silently) |
| ⚠️ Smoke | plumbing was smoke-tested with `--smoke` (40 victims, 3 cycles **outside** the real sample; printed no number, wrote nothing) |
| Numbering | the Captain's *"Go for stage 1"* is read as this spec's **Stage 0** (Architect, §10). QA reads it the conservative way (census only). **Confirmation asked of the Captain.** The census is required under either reading |

## 2. ROW 0 — silent

| row | check | result |
|---|---|---|
| **0a** | `R_wild` = 61.0856, n_EXPOSED = 5,363, EXPOSED hits = 278; class table | ✅ **exact**: 61.08560…, 5,363, 278 |
| **0b** | AMBIGUOUS share of missed victims ≤ 0.05 | ✅ **0 / 5,085** — but see below |
| **0c** | on the fixed 50-cycle sample, integer SNR of replay = live `ALL.TXT`, ≥ 0.90, ≥ 200 pairs | ✅ **0.9203** (716 / 778 pairs, of 788 live decodes) |

- **0b cannot fire on this corpus** (HK-021(k), spec weakness, harmless here). Across **all 1,541** wildcard-recovered refs in C2,
  **none** has ≥ 2 candidates, so the spec's predicate is unreachable. It is not instrument blindness: the matcher's own broader
  definition (one candidate shared by ≥ 2 refs) finds **8** corpus-wide, and **0** among the decoded dominant neighbours. The row
  passes by a wide margin under either definition.
- **0c passed with 2.1 SE to spare, not comfortably.** The 62 disagreements are **not** rounding noise (§6 C): 10 at −1,
  14 at +1, and **38 at +2 … +4 dB**: **52 of the 62 are in the same direction (replay reads higher than live)**. A minority,
  systematic, plausibly the live-vs-replay binary difference the spec anticipated. It is why bucket boundaries carry uncertainty.

## 3. The census (missed EXPOSED victims, n = 5,085; AMBIGUOUS excluded, none)

| bucket | predicate (our integer `ALL.TXT` SNR) | lever | n | share |
|---|---|---|---:|---:|
| **N0** | dominant neighbour not decoded by us | neither | 1,337 | **26.3 %** |
| **RA** | factor ≥ 0.90 (SNR ≤ −3) | floor | 621 | **12.2 %** |
| **RM** | 0.50 < f < 0.90 (SNR −2 … 4) | both | 1,009 | **19.8 %** |
| **RB** | f ≤ 0.50 (SNR ≥ +5) | footprint | 2,118 | **41.7 %** |

```
reach_floor     = (s_RA + s_RM) × 4.30 = 1.378 pp   ≥ 0.5  → floor IN
reach_footprint = (s_RB + s_RM) × 4.30 = 2.644 pp   ≥ 0.5  → footprint IN      verdict: floor+footprint
```

## 4. Reading note (QA, not a gate)

§3.4 calls the reach "a ceiling". `s_X × C` is a **proportional attribution** of the 4.30 pp, not a ceiling: recovering every
missed victim in a bucket would gain `n_X / n_REF` pp, which is larger, because 4.30 pp counts only the excess over the matched-PL
baseline. Both are reported; **only `s_X × C` gates, exactly as ratified.** The full-recovery figures: N0 1.468, RA 0.682,
**RM 1.108, RB 2.326** pp, so a floor lever reaches at most 1.79 pp and a footprint lever at most 3.43 pp *even if it recovered
every victim in its buckets*. The predicate fires either way (it depends on the shares), so it is not decorative.

## 5. Reporting items (§3.5)

| item | result |
|---|---|
| **1. by Δf band** | 0–6 Hz (n 1,899): N0 28.0 / RA 12.5 / RM 20.6 / **RB 38.8** · 7–12 (n 1,476): 25.1 / 12.7 / 19.1 / **43.1** · 13–18 (n 1,710): 25.4 / 11.5 / 19.6 / **43.6** |
| **2. SNR-input check** | median (ours − REF) is **−3 dB for both** decoded dominant neighbours (n 3,774) and decoded CLEAR rows (n 24,149); standardised difference **+0.34 dB**. **Crowding does NOT depress our SNR reading**, so regime A is not an SNR-estimation artefact here. Our scale sits ~3 dB under WSJT-X everywhere, equally |
| **3. pass attribution** | on the 0c sample, **56 / 56** decoded dominant neighbours are decoded in **pass 0** by the replay: they suppress before the victim's pass-1 search, so RA/RM/RB do **not** overstate the reach. **n = 56 from 50 cycles**, small |
| **4. HIT victims (278)** | N0 33.8 / RA 7.2 / **RM 48.6** / RB 10.4 %. Hits concentrate in RM |
| **5. full recovery** | see §4 |

## 6. Post-hoc robustness — 🛑 NOT pre-registered, gates nothing (`stage0_extras.py`)

| | result |
|---|---|
| **A. recovery rate by neighbour bucket** | **RM 11.80 %** (135/1,144) · N0 6.57 % (94/1,431) · RA 3.12 % (20/641) · **RB 1.35 %** (29/2,147). Overall 5.18 % |
| **B. our SNR shifted −1 / 0 / +1 dB** | floor reach **1.533 / 1.378 / 1.246** pp · footprint **2.536 / 2.644 / 2.732** pp · **both in at every shift** |
| **C. replay − live SNR, 778 pairs** | −1: 10 · **0: 716** · +1: 14 · +2: 21 · +3: 12 · +4: 5. 10 live decodes unmatched; 136 replay decodes absent from live (live's plausibility/dedup filters and the binary difference) |
| **D. broader ambiguity** | 0 among dominant neighbours (§2) |

## 7. What this could NOT see

1. **Necessary condition, not cause.** A bucket says a lever *could* act on that neighbour. It does not say the neighbour's
   suppression is why the victim was lost. The headline's item 1 (the flat Δf profile) is the evidence that RB in particular may be a strong-neighbour regime.
2. **C2 only:** one band, one binary (`20260050`), pre-`PASSBAND-140`, nhard 60. The live station now runs a different
   binary and nhard 40.
3. **Bucket assignment uses our rounded ALL.TXT SNR.** ±1 dB moves a bucket's share by up to 3.6 points (§6 B) and the 0c disagreement
   structure (§6 C) says the true ramp input may sit 2–4 dB **higher** for ~5 % of paired decodes (38 / 778).
4. **No CI was computed.** The margin is 3× the bar on both levers, so none was needed for the verdict. Rows within a cycle are
   not independent, so the binomial SE (~0.7 pp on 41.7 %) is a lower bound.
5. **The two bench regimes came from one synthetic scene and one message pair.** Nothing here says the bench's collateral
   *dose* mechanism operates live.
6. **0c's sample is 50 cycles**, and the pass-attribution figure rests on 56 neighbours.

## 8. For the Architect

- **Spec weakness:** ROW 0b's AMBIGUOUS predicate is unreachable on C2 (0 of 1,541). Harmless here; worth tightening to the
  matcher's broader definition in any later arm.
- **Wording:** "ceiling" in §3.4 should read "proportional attribution" (§4).
- **Stage 1 shim version:** by QA's own check, **`20260054` is free.** The highest version defined anywhere is `20260053`;
  `20260054` appears in exactly one commit, your spec, and is never defined; `20260052` remains reserved by the queued rc4
  renumber task.
- **Stage 1 is HELD** until the Captain's go after Stage 0 (§10.1, HK-030). QA has **not** drafted the OpenSpec change or the
  dev-task yet, and hands nothing to the Developer.

## 9. Status

- ✅ **Stage 0 complete.** Verdict **`floor+footprint`**, ROW 0 silent. Neither lever is removed from Stages 1–3.
- 🛑 **Nothing pushed, nothing merged.** Branch `qa/density-remedy`, based on `qa/density-p1` (it imports the Stage 1
  harness, which is not on `main`).
- ➡️ **Next, all the Captain's:** the go for Stage 1 (the build, widened per §10.2). Stages 2 and 3 are not authorised.
- Artefacts: `artefacts/density-remedy-stage0/` (gitignored; per-victim rows hold timestamps, buckets and SNR, no message text).
  Committed: harness, 0c sample, `results/stage0_result.json`, `results/stage0_extras.json` (counts and rates only).

---

*Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>*
