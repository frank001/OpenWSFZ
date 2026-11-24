# TA-MASK pilot: the mask repairs the buried rows (PR_M 0.93 vs 0.77 unmasked, 30 rows) but neighbour-copy ghosts read present at 0.10, above both the 0.05 bar and the 0.02 challenge line. QA challenges A-GHOST's form before any freeze.

**Written:** 2026-11-13, `date -u` read 10:10:33Z (before this file). **To:** Architect. **Spec:** `arch/accept-gate` `104f197f` + Amendment 1 `0777c9b9`. **Code:** `qa/ta-mask/tm_lib.py`, `tm_run.py`, `tm_selftest.py` (22 of 22 mutations killed), committed with this record. **Nothing is frozen. No acceptance-row S_M exists** (the `null` and `own` stages have not run; `own` refuses without a committed `tm.json`). Pilot rows: 30 T_bur + 30 B1m, seed 20261113, excluded from every acceptance rate hereafter (list in `_qa-scratch\ta-mask\frozen\tm_pilot_rows.json`). Numbers only; message text never left the scorer.

## 1. Pilot numbers (60 rows; every figure is a pilot count, none is an acceptance rate)

| item | T_bur (30) | B1m (30) |
|---|---|---|
| n_s (scorable data symbols), min / 25 / 50 / 75 / max | 27 / 35 / 42.5 / 49 / 56 | 38 / 54 / 58 / 58 / 58 |
| unscorable (n_s < 20) | **0** | 0 |
| masked bins per symbol (mean) | 2.46 of 8 | 0.40 of 8 |
| rows with an unencodable neighbour (left unmasked) | 2 | 1 |
| null: sequences scored / unscorable excluded | 594 / 6 | 600 / 0 |
| **null p99** | **0.445** | **0.283** |
| null mean | 0.220 | 0.164 |
| **PR_M at the pilot T_M** | **28 / 30 = 0.933** | 30 / 30 = 1.000 |
| unmasked U′ (T 0.276), same rows | 23 / 30 = 0.767 | 30 / 30 = 1.000 |

- **T_M (A1.1), pilot values:** pooled p99 0.407, T_bur-only p99 **0.445**, B1m-only 0.283: T_M = **0.445**. The masked null is much higher for buried rows (fewer bins and symbols), as the (k) review said; the unmasked 0.276 would have let nulls through at that level.
- **SA-2 reading so far:** A-KEEP is not threatened (B1m 30 of 30 at T_M 0.445). **A-SEE looks reachable** (28 of 30 even at the higher T_M).

## 2. The ghosts (T_bur, 30 rows, the strongest overlapping neighbour's tone sequence at the row's own position and mask)

| ghost | present | note |
|---|---:|---|
| **masked ghost (A-GHOST's quantity)** | **3 / 30 = 0.10** | at T_M 0.445; every ghost scorable (n_s 22–53 in the top rows) |
| unmasked ghost (descriptive) | 3 / 30 = 0.10 | at 0.276, the unmasked instrument on the same rows |
| second ghost (neighbour's sequence at the neighbour's OWN position, with the row's mask; descriptive) | **0 / 30 present, 30 / 30 unscorable** | as predicted: the own bins coincide with the masked bins |

The three present masked ghosts all sit under a neighbour **at least 20 dB stronger** (ΔSNR 21, 22, 20; |Δf| 5, 5, 17 Hz); the other 27 read 0.08–0.36. For the two at |Δf| = 5 Hz the unmasked ghost read 1.000 and the masked 0.65 and 0.63. I read the mechanism as **leakage of a neighbour that is 20 dB or more stronger beyond the 6.25 Hz mask**, helped by the position search's DF grid (±3.125 Hz), which can slide the bins out of mask reach. On the full frozen T_bur, **17 of 267 rows** have ΔSNR ≥ 20 dB (5 of them within 10 Hz): even if only those rows read present, the ghost point rate is at most 17 / 267 = 0.064, and the pilot says they do.

## 3. The challenge (A1.3: the pilot's masked ghost rate is above 0.02)

**A-GHOST as written, CI_hi(PR_M(ghost)) ≤ 0.05, will fail on this data whatever the mask does, because the same ghosts read present with no mask at all (3 / 30 both ways).** HK-025, both branches:
- *If masking worked perfectly:* leakage beyond its radius from ≥ 20 dB neighbours still reads present, so A-GHOST fails.
- *If masking did nothing:* A-GHOST fails the same way.
- The row fires either way. It therefore cannot tell the repair from no repair; it measures a property of strong close neighbours, which the current U′ already has.
- Where the 0.05 comes from (spec §3): "no data on file"; the pilot is the first data and shows the quantity is at 0.10 before and after.

**Options (the ruling is yours):**
1. **Keep the bar.** The outcome is then CREDULOUS (rule 2), M is not used, and angle A goes to NOT-REPAIRED's route (a capture replay for route R, or record U′ as blind under burial). The acceptance run would be a formality.
2. **A-GHOST as a non-inferiority row (my recommendation):** PR_M(ghost) must not exceed the unmasked instrument's ghost rate on the same rows (CI_hi(PR_M(ghost) − PR_U′(ghost)) ≤ 0, paired by row, cycle bootstrap), **with the absolute rates and a ΔSNR ≥ 20 dB stratum reported beside it**. The row then asks what the repair is responsible for: does masking add credulity to the instrument? The pre-existing ghost rate of U′ is recorded as a limit of the instrument (it applies to the late-pass U rows that exist already) and is not hidden. Where its bar comes from (HK-038): the unmasked instrument's own behaviour on the same rows, measured, not a chosen number.
3. **A leakage guard in the instrument:** rows with a neighbour ≥ 20 dB stronger within the mask's reach are `unscorable` by rule (counted as not present). This removes the 17 rows by construction (PR_M(T_bur) is then capped near 0.94, A-SEE still reachable) and A-GHOST would pass by construction, so it would be decorative; the 20 dB comes from three pilot rows (HK-038: thin). Not recommended unless you want the claim "we do not score rows under a neighbour ≥ 20 dB stronger".

**Also a pilot finding for the freeze:** T_M is 0.445, 1.6 times 0.276; PR_M at that threshold is the quantity A-SEE reads.

## 4. State and next

- Nothing frozen; nothing acceptance-side computed. After your ruling on §3 I commit the null stage's `tm.json` (T_M from the 1,012 acceptance nulls) before any own S_M, as Amendment 1 requires.
- Cost so far about 1 h; the pilot ran in 9 s. Still inside the 4 h line.
