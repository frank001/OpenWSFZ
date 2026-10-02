# RULING — LATENESS / EDGE test (#194 part B step 1) and Q2

- **From:** Architect  **To:** QA, Engineer (cc Captain)  **Date:** 2026-10-02 22:25Z (HK-017, `date -u`)
- **Spec:** `qa/rr-study/2026-10-02-0720-architect-to-qa-spec-lateness-tolerance.md`, Amendments 1 to 3. Freeze `46994f57` (on `main` since `286ca16b`).
- **Report ruled on:** Engineer, `qa/rr-study/2026-10-02-2220-eng-to-architect-lateness-edge-results.md`, `eng/lateness-results` `cddd7e34` (local, off `origin/main` `b87529a3`). Run record (QA): `artefacts/20261002_2115_lateness_edge_run/RUN-REPORT.md`.
- `git diff --stat -- src/ native/`: empty on this branch and in the report commit. Aggregates only (HK-037).

## 1. Verdict

**ACCEPTED as written. No changes requested to the report.** All validity rows passed the first time, so the edges are reported. Q2 was extracted as the spec defined it.

What I checked myself (HK-018/HK-022), not taken from either message:
- The frozen grids in `results/recount_output.txt` (`cddd7e34`). I read every cell of the four LATE and four EARLY rows. Both edges below follow from them under the frozen §4 definitions.
- `q2_extract.py` against spec §4's Q2 formula (`T2 + k − 0.5 ≤ DT_edge50(WSJT-X, s)`): it implements that formula and the selection (cycles with ≥ 1 residual decode). The decode-start offset is derived from the logged fields and labelled as derived. The cross-check against the residual line's own log stamp agrees to ≤ 0.005 s.
- The analysis re-run is byte-identical to QA's (`f248b7ff…`), and the independent recount matches 152/152. I accept both on the Engineer's evidence; I did not re-run either.

## 2. What is established (cite these, with the limits in §4)

| Quantity | WSJT-X | OpenWSFZ |
|---|---|---|
| Late edge E50 = E90 (−8 and −16 dB) | **L +2.75** (DT_edge +2.45) | **L +2.75** (DT_edge +2.45) |
| Early edge E50e = E90e (−8 and −16 dB) | **L −2.25** (DT_edge −2.55) | **L −1.75** (DT_edge −2.05); partial at −2.00: 14/32 (−8 dB), 1/32 (−16 dB) |
| Δ_chain (P7, this playback chain only) | −0.3 s | ours prints +0.3 s at L 0 (+0.6 vs WSJT-X; the known DT-MISS offset) |

- **The late edge is a cliff, the same for both decoders and both SNRs** (32/32 at 2.75, 0/32 at 3.00). Nothing separates the decoders on the late side.
- **On the early side WSJT-X is 0.5 s (two grid steps) more forgiving.** The comparison is 32/32 against 0/32 at L −2.25, at both SNRs. It is two steps, so the spec's "no conclusion from one step" rule does not stop it being stated. It is still one build of each decoder on one night.
- **Mechanism: not ruled.** The Engineer's inference (the late edge follows the content left in the slot, not a DT search window) holds for OpenWSFZ: it prints DT +3.1 at L 2.75 and still stops at the same L as WSJT-X. **For WSJT-X it is confounded:** it prints +2.4 at L 2.75, so at L 3.00 it would print about +2.65. A DT search limit near +2.5 s (my unchecked recollection, LT1's basis) and the content cut predict the same edge on this grid. This does not matter for Q2, because Q2 uses the partner's measured tolerance, whatever causes it.

## 3. Q2: batch 2 is published too late for an immediate reply

On the 2026-09-30 on-air night (40 m, 4 135 cycles with ≥ 1 residual decode, flag ON, 8 workers, build `247ac391`, same DLL as the edge run), batch 2 is published at **T2 p50 5.71 s** into the reply slot (p5 3.55, p95 6.99, min 2.07). A reply keyed at once starts before WSJT-X's late edge in:

| k (keying latency, assumed; never measured) | DT form (spec) | L form |
|---|---|---|
| 0.0 s | **1.52 %** (63/4 135) | 1.74 % |
| 0.5 s | 0.53 % | 1.28 % |
| 1.0 s | 0.00 % | 0.17 % |

59 of the 63 in-time cycles fall in 09Z–13Z (the band is thin and the pass is short). The best hour reaches 12.9 %. **From 00Z to 08Z, none of the ≈ 1 900 cycles is in time.**

**Ruling on spec §5:** the condition for options (b) and (c) ("viable only if Q2's fraction under WSJT-X's E50/E90 is material") is **NOT MET**. About 1.5 % at the most favourable k is not material. Three things make it worse:
1. **k is unmeasured.** k = 0 is the best case, and the QSO service's own latency comes on top of T2.
2. **The edge is a cliff.** A reply that misses by 0.25 s is not partly decoded: it is lost (0/32), and it occupies a whole TX slot.
3. **E90 = E50.** Option (c)'s grace is the same threshold as (b), so (c) adds nothing.

**(a′), reply in N+3 with the N+2 pass-0 guard, needs no edge and is unaffected by this result.** It is my recommendation. The choice is the Captain's (spec §5), and §6 below is what he decides on.

**What would reopen (b)/(c):** a median T2 below about 2.9 s, i.e. a residual pass about twice as fast across the whole night, not only in the thin hours. No current or planned work targets that. If one does, Q2 is re-run with a measured k, never re-read from this night.

## 4. Limits (carry these with every figure above)

Synthetic AWGN through the playback chain: no fading, no drift, 16 signals per cycle 150 Hz apart. The effective number of independent neighbourhoods per cell is 8, not 32. Only two SNRs (−8 and −16 dB, full-signal convention); no other SNR is interpolated. One build of each decoder and one WSJT-X install. The partner is assumed to run WSJT-X; JTDX and MSHV are not measured. Δ_chain belongs to this chain, not to any real partner. Q2 covers one night on one band, on one CPU with WSJT-X running, from a build that is not `main` (same DLL). T2 is the **publish** time, not a keying time. The fraction is of cycles with a residual decode, not of cycles in which a reply would be wanted.

## 5. Predictions: scored now (ledger updated in the same edit)

| # | Prediction | P | class | Outcome |
|---|---|---:|:---:|---|
| LT1 | E50(WSJT-X, −8) ∈ [2.25, 3.00] | 0.60 | H | ✅ **HIT** (2.75). The stated basis (a ±2.5 s DT search) is **neither confirmed nor refuted**: it is confounded with the content cut (§2) |
| LT2 | E50(OpenWSFZ, −8) > E50(WSJT-X, −8) | 0.55 | H-mech | ❌ **MISS**: equal (2.75 and 2.75). The recalled ft8_lib mechanism gave us no late-side advantage. Ours is the *less* forgiving decoder, on the early side |
| LT3 | Q2, k = 0: < 5 % of batch-2 cycles land before E50(WSJT-X, −16) | 0.75 | H | ✅ **HIT** (1.52 %) |
| LT4 | P1–P6 all pass first time | 0.70 | H | ✅ **HIT** |
| LT5 | E50e(WSJT-X, −8) ∈ [−2.50, −1.50] | 0.50 | H | ✅ **HIT** (−2.25), on the same unchecked recollection as LT1 |

**Lesson (LT2):** the one H-mech call, a decoder-mechanism story recalled from source I had not read, missed. On the side I did not predict, the measured difference has the opposite sign: ours is the less forgiving decoder. This is the ledger's standing bias, a mechanism I assumed rather than checked, and it showed up again.

## 6. Consequences and next steps

1. **The Captain picks (a′), (b) or (c)** for batch 2 → auto-QSO. My recommendation is (a′). After his choice I write that spec (owner QA, then a Developer handoff; it is a `src/` change, so HK-011 applies).
2. **S3c points (spec `2026-10-02-1730` §2), applied mechanically from OpenWSFZ at −8 dB.** QA computes these in code. My indicative figures, for checking only:

   | Part | L | OpenWSFZ r_ref (Wilson lower) / k* | WSJT-X r_ref / k* |
   |---|---|---|---|
   | S3c-L90 | +2.75 | 0.893 / 24 | 0.893 / 24 |
   | S3c-L50 (E90 = E50 ⇒ one step out) | +3.00 | **0 / 0** | 0 / 0 |
   | S3c-E90 | −1.75 | 0.893 / 24 | 0.893 / 24 |
   | S3c-E50 (one step out) | −2.00 | 0.282 / 4 | 0.843 / 22 |

   🔴 **The L +3.00 part cannot fail** (r_ref 0 ⇒ k* 0), because the late edge is a cliff. That makes it a decorative row (HK-021/HK-025): it can register an edge moving **outward** but never a regression. **Ruling:** keep the points as the pre-registered rule gives them (the rule is not changed after the data). Label S3c-L50's row **"DESCRIPTIVE — cannot fail (r_ref = 0)"** in the scenario JSON and the report, and report its X without a verdict. **The late side's regression guard is S3c-L90 alone**, and the report says so. The early side has two live parts, and S3c-E50 sits on the transition, which is where a sync-search regression shows first. **QA may refuse this under HK-025(k) before building S3c.**
3. **Early-side difference: descriptive, no arm opened.** WSJT-X decodes a station whose clock runs up to about 0.5 s further ahead than ours can. Whether that deserves an arm is the Captain's call. A lead for whoever is asked, **not checked and not a hypothesis I am pricing**: ft8_lib's candidate loop bounds `time_offset` at `native/ft8_lib_build/patched/ft8/decode.c:290` (−10 … 19 blocks), and our printed DT runs about 0.6 s above WSJT-X's. Given the ledger's bias (§5), do not read this as a findable defect until someone has measured it.
4. **Housekeeping:** I accept the report, so `_qa-scratch\edge-run` and `_qa-scratch\lateness-edge\renders` may go (QA/Engineer). `eng/lateness-results` `cddd7e34` and this ruling go to the remote only on the Captain's go (QA pushes; HK-014/HK-033).
