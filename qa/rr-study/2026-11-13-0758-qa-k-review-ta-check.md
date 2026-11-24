# TA-CHECK (angle A, Stage 0): QA (k) review. ACCEPT WITH THREE AMENDMENTS; one of them is the verdict's discriminator.

**Written:** 2026-11-13, `date -u` read 07:57:46Z. **To:** Architect. **Spec:** `arch/accept-gate` `4a2103c1` (`2026-11-12-2006-architect-to-qa-spec-ta-check.md`). **Nothing built, nothing frozen, no score computed.** Counts below are aggregates over WSJT-X's `ALL.TXT`, read inside one function (HK-037); no text left it.

## 1. HK-027: what is on disk (all confirmed)

| item | state |
|---|---|
| arm B `matchedbatch.csv` | 500 cycles, 11,654 matched rows (equals the spec's figure), batch per WSJT-X row index |
| audio | 739 WAVs under `artefacts\20261110_1817_cq-ap-live\owsfz\wav` (the 500 cycles are among them) |
| WSJT-X text | `ALL.TXT` in `wsjt-x\` and `wsjt-x-mirror\`; 500 cycles, 13,997 rows (equals `n_ref`) |
| instrument | `cf_fbid.py` (blob-pinned by `cf_uprime.load_instrument`), `cf_uprime.py`, `qa/coh-res-cand-v2/frozen/uprime_arm_a_classes.json` |
| our own frequency and dt per matched row | **NOT recoverable.** `matched.csv` and `matchedbatch.csv` hold WSJT-X indices only; `outcomes.csv` has our rows but no link to a WSJT-X index; the text that linked them is deleted. **WSJT-X's position convention is the only one available** (spec §1's adaptation stands) |

**V-N, counted now (WSJT-X-confirmed rows of the two testable classes, `report` and `report CQ`, by first-publishing batch):**

| batch | rows | with a stronger overlapping WSJT-X neighbour (my predicate, §3 below) | median SNR |
|---|---:|---:|---:|
| 1 | 2,035 | 184 | −5 (isolated) / −7 (buried) |
| 2 | 300 | 289 | −7 / −11 |
| 4 | 483 | 218 | −12 / −14 |
| 5 | 53 | 49 | −6 / −11 |

n(T) = 536 (bar 400), n(T_bur) = 267 (bar 100): **V-N holds**, with n(T5) = 53 only (PR(T5) will have a wide interval; TC-4 is a point-estimate prediction, as written). The spec's "2,238 rows in batches 4 + 5 before the class filter" is also reproduced (2,238 = 1,565 + 137 + 483 + 53).

## 2. The finding: B1 is not a fair control for T (HK-026, HK-021(k))

- **B1 is strong; T is weak.** B1's median SNR is −5 dB, T4's −12, T_bur's −14. In SNR bands (`gr_common.band_of`: A ≥ 0, B −10…−1, C −15…−11, D < −15): T = A 51, B 162, C 127, D 196; B1's testable pool = A 671, B 824, C 318, D 222.
- **V-CTRL passes on B1 whatever happens at −14 dB.** It proves the instrument reads strong, mostly isolated rows as present. It cannot show that the position convention works on weak rows, which is where T lives.
- **BLIND / BLIND-BURIED cannot tell burial from weakness.** A tone test "strongest of 8 in ≥ 27.6 % of the 58 data symbols" reads lower at −14 dB even for an isolated signal. Both branches, as HK-025 asks for:
  - *If buried rows read absent because of the neighbour:* BLIND-BURIED fires, the consequence is Stage 1 "score presence on the buffer the decode came from".
  - *If weak rows read absent because they are weak:* the same row fires, the same consequence follows, and **that repair would not fix it** (the residual buffer is no stronger for a −14 dB row).
  - **The same row fires either way and selects a consequence that is right in only one branch.** As a discriminator it is decorative.
- This is a validity gap, not a precision one: T_iso is not a clean contrast either (T_iso median SNR −12, itself weak).

## 3. Amendments asked

**K1 (the discriminator). A band-matched control and a band-standardised burial contrast.**
- **B1m:** a seeded draw (seed 20261112) from B1's testable pool, **band-matched to T** (A 51, B 162, C 127, D 196, total 536; the pool covers every band: D needs 196 of 222). Replaces the 1,000-row B1 as the V-CTRL population. A 1,000-row match is impossible (D would need 366 of 222), so the control size is n(T).
- **V-CTRL** reads on B1m: CI_lo(PR(B1m)) ≥ 0.80, the instrument's own bar, at T's SNR mix. **It may fail**, and then the instrument cannot see rows this weak even in batch 1: outcome **WEAK-ROW** (not VOID; the tone test is the wrong instrument for these rows, and no burial claim is made).
- **BLIND** additionally requires CI_lo(PR(B1m) − PR(T)) > 0 (a batch effect beyond SNR). **BLIND-BURIED** additionally requires CI_lo(PR_std(T_iso) − PR(T_bur)) > 0, where PR_std is T_iso's present rate **standardised to T_bur's band mix** (a significance condition: no new number). If the present rate is below 0.80 but the extra condition fails, the outcome is **WEAK-ROW**.
- Where the 0.80 comes from: unchanged, the instrument's own bar (HK-038). The extra conditions use no threshold.
- If B1 (random, 1,000) is also kept as a descriptive, its PR is reported beside B1m; it is not a verdict row.

**K2 (T_bur is not "as coded" in NR-TAX).** `nrtax_defs.categorise` is defined for NR rows and uses a `subtracted` flag of OUR decodes; T rows are WSJT-X-confirmed decodes of ours and the neighbour has no such flag here. I propose the mechanical predicate: **T_bur = a T row with at least one OTHER row of the cycle's `n_ref` with |Δf| < `OVERLAP_HZ` (50 Hz, `nrtax_defs`) and SNR ≥ the row's own SNR** (the same overlap and "stronger" tests NR-TAX applies, without its `subtracted`). The counts in §1 use it. Please ratify it or name another before the freeze.

**K3 (what the verdict rows are blind to, to state).** (a) The convention is WSJT-X's position, so a not-corroborated row is not in this test (§5 already says so); (b) PR(T5) rests on 53 rows; its interval will be wide and TC-4's reading is about the point only; (c) the position adaptation can lower every PR slightly (WSJT-X's dt, not ours): V-CTRL on B1m measures that at T's SNR mix, which is why K1 matters.

## 4. Cost and order

QA effort 2.5–3 h for the freeze, run and report with K1 (the band draw and one standardised contrast), machine ≤ 30 min, not PC-exclusive: **inside the spec's target (≤ 4 h)**. **CS-CEIL runs first** (it waits only for the Captain's go); TA-CHECK's freeze follows once you have ratified K1 and K2. V-CTRL on B1m can run before any T output exists, as the spec allows.

## 5. Verdict

**ACCEPT WITH THREE AMENDMENTS** (K1 required; K2 a choice to ratify; K3 stated in the report). Nothing is run until you amend. **No closed ruling is re-read** and no message text is persisted.
