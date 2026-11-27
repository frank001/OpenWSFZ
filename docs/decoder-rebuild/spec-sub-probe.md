# SUB-PROBE: why lean misses a weak signal beside one it already decoded

**To:** QA, who turns §2 into one Developer task (HK-015) and runs §3–§4
**From:** Architect, 2026-11-26
**Approved:** Product Owner, 2026-11-26: option **A, "measure first"**, and **"fold into probe run"**: the probe's replay also gives the new post-DR-3 baseline on all three slices. No separate confirmation run of DR-3's +3.19 pp.
**Why:** CS-MAP (`qa/rr-study/results/2026-11-26-lc-base/cs-map-result.md`) showed that lean usually decodes the strong neighbour of a weak signal it misses, but that removing the neighbour barely helps. Misses rise to 43–51 % when the neighbour is more than 10 dB stronger. Then the DR-3 duplicate fix lifted lean on S40 from 81.52 % to 84.70 %, +213 of it in rounds 1–3 (`dr3-s40-replay.md`), so the picture has moved. The probe says, for each such miss, which of three things failed:

1. **Subtraction:** too much of the neighbour is left in the residual.
2. **Search:** the weak signal never becomes a candidate (or is filtered out).
3. **Decode:** it becomes a candidate but belief propagation, CRC or a gate rejects it.

**Process:** the minimal-test rule: one Developer task, unit tests, QA's review (HK-039), one replay (§3, on three slices as the Product Owner chose). No bars. The result picks the first decoder change.

---

## 1. Where it is built

- **Stacked on DR-3** (`feat/dr3-lean-default`, `4fa2c637`, or `main` once #295 has merged), HK-008. The Developer can start at once.
- It rides in the sprint PR (one PR per sprint, Product Owner 2026-11-26).

## 2. The probe (Developer)

**Test-only and off by default.** A new flag `FTZ_FLAG_PROBE` in `ftz_params_t.flags`, set only by the replay harness (`Ft8.FitProbe`, `--lean-probe 1`). The daemon never sets it. **With the flag off, nothing changes:** no extra work, no extra memory. **With the flag on, the published decodes are byte-identical to flag off** (unit test, as the determinism test).

With the flag on, the native code fills a probe buffer per cycle, which the harness writes to `probe.tsv` beside its other per-cycle files. **Numbers only, no message text** (HK-037): positions, scores and outcome codes.

| Record | Written for | Fields |
|---|---|---|
| `SUB` | every signal subtracted, every round | round, freq Hz, time s, the fit's amplitude, **suppression dB** = 10·log10(power in the signal's footprint before ÷ after the subtraction), measured on the waterfall over its 8 tone columns × 79 symbols |
| `CAND` | round 0 and every round 1–3 | for **every** candidate from `ftx_find_candidates`: round, freq Hz, time s, sync score, `kept` (passed the round's patch filter and floor, or round 0), and the outcome code below |
| `LOW` | rounds 1–3 only | one extra `ftx_find_candidates` call on the residual with floor 0 and cap 400, **not decoded**: freq, time, score. It shows candidates the normal floor (`kMinScorePass2`) or cap cut off. |

**Outcome code per kept candidate:** `A_OK` tier A decoded; `A_BP` tier A failed in BP (+ the final number of unsatisfied parity checks); `A_CRC` failed CRC; `B_NE` not eligible for tier B; `B_OK` / `B_BP` / `B_CRC` the same for tier B; `CQ_OK` / `CQ_FAIL`; `DUP` decoded but dropped as a duplicate; `GATE` decoded but dropped by an accept gate (name the gate as a code). Not kept: `NOT_KEPT_PATCH`, `NOT_KEPT_CAP`.

**Unit tests:** (a) flag off vs flag on gives byte-identical published output on the committed `synth-qso-*.wav` files; (b) on a synthetic two-signal WAV (a strong and a weak signal 10 Hz apart, built with the existing modulator test helpers), the probe has one `SUB` row for the strong signal with suppression > 0 dB and a `CAND` row near the weak one; (c) the probe buffer is bounds-checked (ASan job covers it).

## 3. The replay (QA)

- Build: DR-3 + probe, harness with `-p:HasLean=true`, `libft8.dll` SHA pinned and stated.
- Lean, 16 threads, `--lean-probe 1`, flags as LC-BASE's L arm.
- **S40** (170 cycles), **H40** and **H20** (240 each). About 20 minutes in total.
- **Free check:** S40's published decodes must equal QA's DR-3 S40 replay (`dr3-s40-replay.md`: matched 5,737, ours 6,009). If they differ, the probe changed behaviour: stop and tell the Architect.

## 4. What is reported (aggregates only, beside LC-BASE)

1. **The new baseline**, LC-BASE Table 1 format: lean post-DR-3 on S40, H40 and H20 against LC-BASE's classic arm (unchanged). This answers whether DR-3's +3 pp holds beyond S40.
2. **CS-MAP's key tables re-run on the new lean** (QA's script, unchanged): the neighbour-decoded share, by `dSNR` and by `|dF|`.
3. **The classification.** Take every crowded WSJT-X decode **T** that lean missed and whose nearest neighbour **N** lean decoded (CS-MAP's definitions). "Near T" means within ±3.2 Hz and ±0.16 s (one search-grid step each way, at frequency and time oversampling 2). Every such T goes into **exactly one** class, first match wins:

| Class | Rule | Points at |
|---|---|---|
| **K1 decoded, dropped** | a kept `CAND` near T with `DUP` or `GATE` | accept rules |
| **K2 tried, failed** | a kept `CAND` near T in any round (codes `A_BP`, `A_CRC`, `B_*`, `CQ_FAIL`) | decoding (bit metrics, BP) |
| **K3 found, not kept** | a `CAND` near T with `NOT_KEPT_*`, or a `LOW` row near T | search (patch filter, floor, cap) |
| **K4 not found** | none of the above | subtraction or the search itself |

   For each class: the count and share, by `dSNR` band (CS-MAP's bands), and **the median and quartiles of N's suppression dB** (its `SUB` row; "not subtracted" counted separately). For K2: the distribution of unsatisfied parity checks.
4. **N's suppression overall:** distribution over all `SUB` rows, by N's SNR band. A subtraction that leaves the neighbour 10 dB down still buries a signal 15 dB weaker than it.

## 5. What happens next

The Architect reads §4.3 and proposes the first decoder change to the Product Owner. The largest class picks the lever: K4 with low suppression → the fit; K3 → the search rules; K2 → the bit metrics; K1 → the gates.

## 6. The Architect's expectations (priced, written before the run; scored in the ledger)

| # | Prediction | P |
|---|---|---:|
| SP-1 | Lean post-DR-3 is at or above classic's rate on H40 **and** H20 (LC-BASE C: 85.29 / 81.25 %) | 0.60 |
| SP-2 | K4 (not found) is the largest class on H40 and H20 | 0.45 |
| SP-3 | K2 (tried, failed) is larger than K3 (found, not kept) on H40 and H20 | 0.55 |
| SP-4 | Median suppression of a subtracted N is below 20 dB | 0.50 |
