# `NHARD40-DEFAULT` `NT` — acceptance ruling: **S1 ACCEPTED**, structurally. The ceiling is zero: isolated weak stations never use OSD, so the question moves to co-channel conditions, which no leg has tested

**Architect, 2026-09-12 09:56Z** (`date -u`, HK-017). Branch `arch/osd-nhard40-default`.
Docs-only; `git diff --stat origin/main -- src/ native/` empty.

Accepts QA's work on branch `nhard40-default-nt-result`, `1383c05`, against the pre-registration
`2026-09-12-0912-architect-to-qa-spec-nhard40-default-preregistration.md` §3:

- `qa/rr-study/2026-09-12-0945-qa-to-architect-nhard40-default-nt-result.md`

---

## 1. Recomputed

From `artefacts/2026-09-12-nhard40-default-nt/nt.json`, with my own counting:

| check | QA | recomputed |
|---|---|---|
| Cycles | 5,250 (21 rungs × 250), no extension, no top-up | same |
| ROW 0b bracket | `p60(−26.0) = 0.000`, `p60(−16.0) = 1.000` | same |
| Band `B` (`p60 < 0.95`, from the 60-leg only) | 15 rungs, −26.0 … −19.0 | same (`p60(−19.0) = 0.936`, `p60(−18.5) = 0.992`) |
| `G_B` / `K_B` / `C_B` | 710 / 0 / 0 | **710 / 0 / 0** |
| `L_B`, CP95 | [0%, 0.52%] | **[0.000%, 0.518%]** |
| `p60 = p40 = p0` | at every rung | **identical at all 21 rungs** |
| Genuine decodes gained at 40 | — | 0 |
| False decodes per cycle, 60 / 40 / 0 | 0.1385 / 0.0025 / 0 | same: **the three settings were really applied** |

**S1:** `CP95_hi(L_B) = 0.52% < BAR_S = 5%`. **ACCEPTED.** ROW 0a–0d clear, as QA reports. QA's
direct path probe (710 of 710 genuine band-`B` decodes resolve by BP) agrees with the ceiling leg
by a second, independent route.

## 2. QA's fork: is S1 with `L0_B = L_B = 0` sufficient for G2 as specified? **Yes.**

§3.6 pre-registered exactly this reading: if the ceiling is below `BAR_S`, *"no `nhard` setting at
all could cost more than `BAR_S` on this scene … a structural result, and a legitimate one, because
0b guarantees the scene contains the threshold."* 0b held with wide margins, and `G_B = 710` real
near-threshold genuine decodes exist. **This is not E2's defect:** E2 had no threshold, and NT
measured one.

- 🛑 **Adding a requirement to G2 now, such as "NT must show some OSD engagement", would re-read a
  gate after its data is known.** This programme bars that. G2 stands as passed.
- **QA was right not to refuse** (the row is real) **and right not to write the dev-task on its own
  initiative.** Both calls were correct, and the fork was the right thing to surface.

## 3. What S1 settles, and what it moves elsewhere (HK-026)

**It settles, structurally:** for an isolated station on AWGN, **`nhard` is irrelevant to
sensitivity.** Even `nhard = 0`, which disables OSD acceptance entirely, loses none of 710
near-threshold decodes. The decode curve does not move by a single decode (50% point −20.19 dB
nominal at all three settings). In this condition, 60 → 40 removes 98% of false decodes
(0.1385 → 0.0025 per cycle) for **zero** genuine cost.

**It moves the open question elsewhere, and does not answer it.** If OSD never rescues an isolated
weak station, then any genuine cost of 40 can only arise where **BP fails on a real signal and OSD
rescues it**: co-channel overlap, strong-neighbour interference, fading, drift, timing spread. The
pre-registration §6 disclosed that NT cannot see these. **No leg of either arm has tested them.**

**Evidence already on file, and what it can and cannot carry (HK-018):**

- **`qa/rr-study/results/diag-nhard-2026-06-20/`, the R6 diagnostic behind "60 calibrated against S7
  genuine histograms" (`decode.c:41`).** Its "genuine" population is 92 OSD accepts from S7
  co-channel slots, and **90 of the 92 have `nhard` in (40, 60]**: exactly the band 40 removes.
  🛑 **That population was never payload-labelled.** Its own methodology note *assumes* most are
  genuine ("rare spurious CRC coincidences … statistically minor"). Against that:
  - 92 accepts in 15 slots is about 6 per slot, for a scene with 2–3 stations;
  - its `nhard` histogram is **indistinguishable from pure noise** (mean 51.4 vs 51.8, same shape,
    same range).

  **It is not evidence of harm, and it is not evidence of safety.** It is the one place a harm
  mechanism could live, and it has never been measured with truth labels.
- **Live, Part D3:** 10 OSD-path decodes that WSJT-X confirms, in 11,615 (0.09%). So genuine OSD
  rescues do exist on air.
- **Live, E3:** 2 corroborated removals in 1,491 (≈ 0.09 per hour). That bounds live genuine loss
  from below only.

## 4. Consequence

**Pre-registration §2 item 3 fires:** `NT-S1` ⇒ *the Architect asks QA to author the dev-task per
§1, carrying the PO's Q2 answer (M2).* **The licence stands.** Merge, as always, needs the Captain's
sign-off (HK-010).

**My recommendation to the Captain** is a new measurement, not a re-read of NT, and his decision to
make. Before the dev-task, run a **payload-labelled co-channel check (`CC`)**:

- S7-type co-channel slots with oracle truth, decoded at `nhard` 60 / 40 / 0 with NT's machinery
  (reuses `part_nt.py`);
- it answers directly whether the 2026-06 "genuine" population was genuine;
- it costs about an hour of compute.

If CC shows no genuine co-channel OSD rescues in (40, 60], the default change goes ahead with no
known untested mechanism. If it shows some, the PO sees the price before the default changes for
every install.

## 5. Predictions (pre-registration §4)

| row | predicted | result |
|---|---|---|
| S1 | 0.35 | **fired** |
| S3 | 0.40 | — |
| S2 | 0.25 | — |

**My stated reasoning was wrong:** I expected genuine near-threshold hard-error counts to push
genuine OSD accepts into (40, 60]. For isolated stations, there are **no** genuine OSD accepts at
all. The row landed on my second choice.

## 6. Housekeeping

- QA's result branch is **stacked** on `osd-fa-a-row0-part-d-result` (it reuses `dll_pin` /
  `part_a` / `part_b`). HK-008 applies at push/PR time: retarget before merging or deleting the base.
- **Not pushed.** QA's push/PR go covered the `OSD-FA-A` branches; this branch needs its own go
  (HK-033).
