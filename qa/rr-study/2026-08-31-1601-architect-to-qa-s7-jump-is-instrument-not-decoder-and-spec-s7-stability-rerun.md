# S7's 2026-08-31 "jump" is the INSTRUMENT, not the decoder — finding, and pre-registered spec for an S7 stability re-run

**From:** Architect
**For:** QA (execution), and the Captain (bench time, and the gap-figure consequence in §A.5)
**Date:** 2026-08-31 16:01 UTC
**Concerns:** `results/2026-08-30-2e60949/report.md` Rev 2 (S7), `results/2026-08-31-2e60949/`,
Section 6's S7 column, and the `19.07pp` S7 gap figure carried on the board.

**Trigger:** the PO asked whether the S7 improvement could be attributed to the Amendment 2
developer diff, observing that it introduced hash-table counters and was not aimed at decode
performance. It could not. The investigation below is what that question turned up.

---

# PART A — THE FINDING

## A.1 The code is ruled out, twice over

The Amendment 2 diff (`47447e3`) added h12/hash-table instrumentation counters. It cannot have
changed decode behaviour, and we do not have to argue this from the commit message:

- **ROW 0b of the SUP-B Amendment 2 pilot: 29,696 / 29,696 decodes byte-identical**, BASE
  (`bc8efcf1…` / shim `20260046`) vs INST (`e22524e8…` / shim `20260048`), over 1,856 cycles.
  Not "no regression detected" — bitwise identity of the decode set.
- The 17:43Z QA code review traced the logic by hand: `g_h12_code_out_of_range` increments
  **before** the defensive mask, `cb_lookup_hash`'s return path is unchanged, and
  `hash_table_lookup`'s body is untouched apart from one assignment. The instrumentation counts;
  it does not decide.

⚠️ **HK-022 caveat, stated and then discharged:** ROW 0b was pointed at the `S-17M` live corpus,
not at S7's synthetic co-channel stacks, so byte-identity there does not *mechanically* transfer
to S7. It transfers by construction instead — the changed code is counter arithmetic on a path
that returns the same value it always did. The per-part evidence in §A.2 independently confirms
it: the parts that measure real structural limits did not move at all.

**Conclusion: the binary that produced 82.79% decodes identically to the one that produced
73.95%.** Whatever moved, it was not the decoder. The PO's read is correct.

## A.2 What actually moved: five parts, and the arithmetic closes exactly

Per-part diff of OpenWSFZ, `872ba65` → the 2026-08-31 capped re-run:

| Part | Condition | `872ba65` → re-run | Δ (messages) |
|---|---|---|---|
| P0 | co-channel, 2-stack equal 0 dB, Δ7 Hz | 6/10 → **10/10** | +4 |
| P1 | co-channel, 2-stack equal −5 dB, Δ13 Hz | 9/10 → **10/10** | +1 |
| P15 | sweep, 2-stack equal 0 dB, Δ5 Hz | 0/10 → **8/10** | +8 |
| P16 | sweep, 2-stack equal 0 dB, Δ7 Hz | 5/10 → **10/10** | +5 |
| P17 | sweep, 2-stack equal 0 dB, Δ10 Hz | 9/10 → **10/10** | +1 |
| | | | **+19** |

19 / 215 = **+8.84pp**, matching the reported +8.8pp exactly. WSJT-X's own delta decomposes the
same way (P2 +3, P3 +2, P15 +6 = +11 = +5.12pp, matching +5.1pp).

**Every other part is unchanged, and that is the load-bearing half of this finding.** The parts
that measure genuine structural limits did not move by a single message:

| Part | Measures | All six recent sweeps |
|---|---|---|
| P2 | 3-stack co-channel | `0/15` — **every sweep, including this one** |
| P4 | near-collision Δ6 Hz | `5/10` |
| P12 / P13 / P14 | weak-signal capture (−6 / −10 / −10 dB) | `5/10` |

A genuine decoder improvement would be expected to move at least one of these. None moved.

## A.3 The smoking gun: an unchanged reference decoder swinging 0/10 → 10/10

WSJT-X 2.7.0's binary has not changed across any of these sweeps. Its own P15 score:

| Sweep | `8d6e1b1` | `7d36038` | `f5dec23` | `22b749c` | `872ba65` | capped re-run |
|---|---|---|---|---|---|---|
| **WSJT-X** P15 | 0/10 | 6/10 | 8/10 | 10/10 | 2/10 | 8/10 |
| **OpenWSFZ** P15 | 3/10 | 4/10 | 8/10 | 4/10 | 0/10 | 8/10 |

🔴 **A fixed binary cannot vary 0/10 → 10/10 on an identical seeded synthetic stimulus.** The
variance is therefore upstream of both decoders — in playback delivery, not in decoding. P0, P1
and P16 behave the same way. **These are harness-sensitive parts and always have been**; they are
the carriers of the S7 column's historical noise.

## A.4 Why this run reads high, and why the asymmetry is not evidence of anything

The capped re-run sits **at or above the historical maximum on all five volatile parts
simultaneously**. Across five noisy parts that is not a lucky seed draw; it is a cleaner
measurement.

The asymmetry (WSJT-X +5.1pp, OpenWSFZ +8.8pp) needs no decoder explanation: WSJT-X sits at ~98%
and has almost no headroom in which a cleaner chain could show up. OpenWSFZ has headroom, so it
does. **Ceiling effect, not differential improvement.**

## A.5 🔴 Consequences — including one that touches a live board figure

1. **`82.79%` must not be cited as progress.** The report calls it "in-family"; I withdraw that
   characterisation on the evidence above. It is the best OpenWSFZ S7 reading ever recorded, by
   **+3.3pp over the previous best** (`79.5%`, `f5dec23`). It is out-of-family *high*, for
   instrument reasons.
2. 🔴 **The board carries S7's adversarial gap as `19.07pp`. This run implies `15.35pp`.
   NEITHER IS CLEAN** — the first was measured on a partly-degraded chain, the second on a
   newly-capped harness that has run exactly once. **Do not update that figure in either
   direction, and do not quote 15.35pp.** Part B exists to settle this.
3. **Section 6's S7 column is not one comparable series.** Every reading before 2026-08-31 was
   taken under unbounded batching. It needs the same class of footnote the table already carries
   for the S1/S3 redesigns and the S5 `N` change.
4. This is the **third** recorded occasion on which an S7 move looked like progress and was not
   — the board already records WSJT-X's own 78.5% → 97.7% shift as a scenario revision. 🛑 **S7
   has a track record of flattering us for reasons that are not the decoder. Treat any S7
   movement as instrument-suspect until shown otherwise.**

Nothing here reopens P2's `0/15`. That reproduces identically across all six sweeps and both
harness regimes, and remains a genuine structural finding under D-001.

---

# PART B — SPEC: S7 STABILITY RE-RUN (pre-registered)

## B.0 Question, and scope of the claim

**Question:** under the capped harness, is S7 a stable enough instrument to yield a citable gap
figure — and if so, what may be quoted?

**Population the claim ranges over (HK-021(x)):** S7 readings taken on the capped harness at the
pinned binary. **Nothing in this spec licenses any statement about S8, S1–S5, or about decoder
capability.** The binary is pinned and proven decode-identical; this measures the instrument.

## B.1 Pre-work, before any playback (offline, no bench time)

**W1 — Comparator base rates (HK-021(u)).** From the five most recent uncapped sweeps
(`8d6e1b1`, `7d36038`, `f5dec23`, `22b749c`, `872ba65`), compute and record the uncapped range
of S7 "all" recovery, in **messages**, for each appraiser. Architect's derivation, to be
confirmed or corrected by QA: **OpenWSFZ ≈ 24 messages** (68.4%–79.5%), **WSJT-X ≈ 11 messages**
(93.0%–98.1%). These are the comparators ROW 1 and ROW 3 are read against, fixed before any run.

⚠️ **W1 precondition:** verify the S7 truth total is **215 messages in all five** of those
sweeps. If any differs, the scenario was revised and that sweep is excluded from the comparator
(the board already records one such S7 revision). State which were used.

**W2 — Per-batch WSJT-X floor, for ROW 0d.** The cap groups S7's 105 trials into six batches by
part: `P0–P3`, `P4–P7`, `P8–P11`, `P12–P15`, `P16–P19`, `P20`. For each of the five sweeps in
W1, compute WSJT-X's matched recovery within each of those six part-groups. Record the **minimum
cell** across all (sweep × group). ROW 0d's threshold is **that minimum, minus one message**,
fixed now and not revisited after the runs.

**W3 — 🟢 RECOVER THE DESTROYED R1 READING. Do this first.** Rev 2 overwrote
`results/2026-08-30-2e60949/S7_matched.csv` with the re-run's output, destroying the collapsed
reading. **It is reconstructible — I verified the inputs survive:**

| Artefact | State |
|---|---|
| `2026-08-30-2e60949/truth.csv` | mtime 2026-08-30 22:59 — **original**, holds all 215 S7 truth rows |
| `2026-08-30-2e60949/owsfz-all.txt` | mtime 2026-08-30 22:51 — original, spans `260830_190530` → `260830_205130`, i.e. **covers the collapse window** |
| `2026-08-30-2e60949/wsjt-all.txt` | mtime 2026-08-30 22:47 — original |
| `S7_matched.csv`, `S7_recovery.png` | 🔴 overwritten 2026-08-31 17:27 — the only losses, and both are derived |

Re-run the matcher over those three originals, write **`S7_matched.R1-collapsed.csv`** (do not
reuse the bare name), and enter R1 into the register in §C with real numbers rather than prose.
The record of a defect is evidence and should not survive only as narrative.

## B.2 Runs

**N = 3** independent S7-only runs (`--scenarios S7`).

🔴 **Independence requirement (HK-021(i) — observation is not independence).** No two runs may
share a daemon session, and the three must span **at least two distinct calendar days**, with a
full daemon + WSJT-X restart between them. Rationale: the 2026-08-30 chain was described in the
report itself as possibly "still settling" after that evening's hardware failure. Three runs
back-to-back in one session would sample one chain state three times and would not answer the
question.

## B.3 ROW 0 — validity rows, strict order, mutually exclusive

Evaluated per run. **Any ROW 0 firing VOIDs that run entirely — no partial reading, no
substitution.**

| Row | Predicate (mechanical) | Consequence if it fires |
|---|---|---|
| **0a** BUILD PIN | `SHA256(src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll)` == `e22524e8fb4964496e34a2c3f08d6e10d8f6f48eaadb0626fe6a8799fa84e33e` (shim `20260048`), asserted against `2026-08-30-1507-qa-sup-b-row0-manifest.md`, **re-hashed per run, never inferred from a label**; and `wsjt-version.txt` records WSJT-X 2.7.0 | VOID that run, re-arm |
| **0b** HARNESS PIN | `_MAX_BATCH_TRIALS == 20` present in `harness/run_scenario.py`; run log shows **exactly 6 flushes**, max batch ≤ 20, total trials == 105 | VOID that run |
| **0c** CHAIN AT START | A warm-up decode present in **both** `ALL.TXT` files within 300 s preceding the first S7 cycle | VOID that run |
| **0d** CHAIN HELD | For each of the six batches, WSJT-X matched recovery ≥ W2's threshold | VOID that run, **flag as chain degradation** |
| **0e** TRUTH IDENTITY | Each run's 215-row S7 truth block is identical (sorted) to `2026-08-30-2e60949/truth.csv`'s S7 block | VOID **and escalate** — seeding is not reproducible, a separate defect |

**HK-022 — what these rows cannot detect, stated deliberately:**

- **0c cannot detect mid-run degradation** — precisely the failure mode under investigation. It
  is necessary and *not* sufficient. That is why 0d exists; do not treat 0c passing as a healthy
  chain.
- ⚠️ **0d uses WSJT-X, which is one of the two appraisers** — an instrument partly inside the
  system under study (HK-026). It is therefore a **VOID row only, never a reading**, and its
  threshold comes from WSJT-X's own historical floor rather than from this run's data.
  **Corroborate with two independent sensors, recorded as diagnostics and explicitly not gated
  (no base rate exists for either yet):** the daemon's noise-floor series across the run, and the
  count of decodes at SNR ≤ −24 dB matching no truth row. Report both per batch.
- **0a cannot detect an audio-routing or Voicemeeter change.** Record the configured device
  explicitly per run — note the standing trap that `--device` still defaults to `"CABLE Input"`
  while routing moved to `"Voicemeeter AUX Input"`.

## B.4 Reading rows — evaluated only if ROW 0 passes on all three runs

**Readout quantum (HK-021(o)): 215 messages ⇒ 1 message = 0.465pp. Every threshold below is in
messages, not percentage points.** No bootstrap SE.

### ROW 1 — instrument stability (primary)

Metric: **range (max − min) of OpenWSFZ S7 "all" recovery across the three capped runs, in
messages.** Comparator: W1's uncapped OpenWSFZ range (Architect's derivation ≈ 24 messages).

| Row | Condition | Verdict |
|---|---|---|
| **1a** | range **≤ 8 messages** (≈3.7pp) | **INSTRUMENT STABILISED.** S7 becomes citable; the capped readings supersede the pre-cap series, which is retired as non-comparable |
| **1b** | range **9–16 messages** | **PARTIAL.** S7 citable **only as an interval, never a point**; any gap figure quoted as a range with the run count attached |
| **1c** | range **≥ 17 messages** | **NOT STABILISED.** 🔴 S7 may not be cited for gap estimation at all; the gap must come from S8 or a purpose-built arm |

Rows are mutually exclusive and evaluated in strict order.

**Threshold derivation, stated as the judgement it is:** 8 ≈ one-third of the uncapped spread;
17 ≈ 70% of it, i.e. essentially no improvement. **My own expectation (HK-021(v)) is ROW 1a** —
I expect the cap to remove most chain-degradation variance. If QA judges that expectation
under-powered at n=3, say so before running, not after.

⚠️ **Stated limitation:** a 3-run range systematically **under**estimates true spread. **ROW 1a
at n=3 is suggestive, not settled** — it licenses citing S7 *with the run count recorded
alongside*, and does not license treating the instrument as characterised.

### ROW 2 — structural null control (trap check)

Predicate, across all three runs: OpenWSFZ **P2 == 0/15 in every run**, **and** P4, P12, P13,
P14 each within **±1 message** of `5/10`.

- **Satisfied** ⇒ confirms only the volatile set moved; supports ROW 1's reading.
- 🔴 **Violated** ⇒ something other than the harness changed. **STOP. Do not report a stability
  verdict. Escalate to Architect.**

### ROW 3 — reference-decoder noise calibration

Metric: range of **WSJT-X** S7 "all" across the three runs, in messages. WSJT-X's binary is
fixed, so any spread in its number is pure instrument noise.

- **WSJT-X capped range ≥ 11 messages** (its own uncapped range from W1) ⇒ chain noise is **not**
  reduced ⇒ **downgrade ROW 1's verdict one level** (1a→1b, 1b→1c).

⚠️ Asymmetry caveat: WSJT-X sits near its ceiling, so it can essentially only move downward. It
is a valid one-sided noise sensor, not a symmetric one. Do not read a small WSJT-X range as
positive evidence on its own.

### ROW 4 — volatile-set identification (diagnostic, explicitly not gated)

Report per-part **min/max across the three runs, all 21 parts**. Names which parts carry
instrument noise under the cap, and feeds any future S7 redesign. **No threshold. This is a
diagnostic and may not be read as a verdict** — reporting it is the deliverable.

## B.5 What a PASS does and does not license

| Licensed | **Not** licensed |
|---|---|
| Updating the S7 gap figure — **only if ROW 1a AND ROW 2 clear AND ROW 3 does not downgrade** | Any statement about decoder improvement. The binary is pinned and byte-identity-proven |
| Retiring the pre-cap S7 series as non-comparable | Any read-across to S8, S1–S5, or D-001 route selection |
| Recording the volatile-part set for future S7 design | Reopening P2's `0/15`, which is unchanged across both harness regimes |

## B.6 Cost, gating, and QA's standing right to refuse

- **Bench time:** 3 × S7-only ≈ 26 min playback each, plus warm-up and settle — call it ~2 h
  wall clock across ≥2 days. Pre-work W1/W2/W3 is offline, minutes.
- **Scope:** `qa/` harness and reporting only. No `src/` change ⇒ **HK-011 does not apply**; no
  Developer session needed.
- **Independence from SUP-B:** this neither blocks nor unblocks the SUP-B merge decision or its
  step 7. Same binary, unrelated thread. It does need bench time, so the **Captain schedules it**.
- 🛑 **HK-025 applies in full: QA may refuse to run any row on HK-021(k) grounds without
  Architect agreement.** Classify each row (validity vs precision), evaluate both branches, and
  if a row lands the same verdict either way, name it, call it a DIAGNOSTIC, and stop. I would
  rather hear that before the bench time is spent.

---

# PART C — REPORTING RULE: THE S7 SECTION EXTENDS, IT NEVER OVERWRITES

**PO instruction, 2026-08-31.** My reading, stated so it cannot be mistaken: this concerns the
**`## S7` scenario section of the R&R report** (and its artefacts), not the creation of a new
numbered "Section 7". If the PO meant otherwise, correct me before QA executes.

**Rationale:** Rev 2 replaced `S7_matched.csv` and rewrote the S7 numbers in place. That
destroyed the collapsed reading, and it is why the instrument story in Part A took a per-part
archaeology across six reports to see. A scenario whose readings are instrument-sensitive must
**accumulate** them.

## C.1 Required shape — a reading register

```markdown
## S7 — Compounding / co-channel overlap

### S7 reading register

| # | Date | SHA / shim | Harness | Batches | WSJT-X all | OpenWSFZ all | Status |
|---|---|---|---|---|---|---|---|
| R1 | 2026-08-30 | 2e60949 / 20260048 | uncapped | 1 × 105 | (from W3) | (from W3) | 🔴 VOID — mid-run chain collapse |
| R2 | 2026-08-31 | 2e60949 / 20260048 | capped 20 | 6 | 98.14% | 82.79% | valid, n=1, instrument-suspect |
| R3 | … | … | capped 20 | 6 | … | … | … |
```

## C.2 Rules, binding on every future S7 report

1. **A new reading ADDS a row. Never edit, never delete an existing row's numbers.**
2. **A void or superseded reading stays in the register**, with its status and one-line reason.
3. **Per-family and per-part tables are kept per reading** — a subsection per reading, or a run
   column added to the existing tables. The per-part detail is what made Part A provable; it
   must not be collapsed to a single "current" table.
4. 🔴 **`S7_matched.csv` is never overwritten.** New readings land as `S7_matched.<run-id>.csv`.
   This is the specific mechanic that failed in Rev 2.
5. **Section 6's S7 column carries a harness-state annotation per row.** Pre-cap and post-cap
   readings are **not one series** and must not be trended as one.

## C.3 Applies retroactively

Rule 1 and §B.1 W3 together mean the 2026-08-30 report gains an R1 row with recovered numbers.
The existing Rev 2 prose in Section 5 Finding 1 stays as it is — it is a good account of the
incident; it simply is not a substitute for the reading.

---

## Sources

- `results/2026-08-30-2e60949/report.md` (Rev 2), `results/2026-08-31-2e60949/report.md`
- `results/{2026-08-15-8d6e1b1, 2026-08-21-7d36038, 2026-08-22-f5dec23, 2026-08-27-22b749c,
  2026-08-29-872ba65}/report.md` — S7 per-part tables
- `qa/rr-study/2026-08-30-1507-qa-sup-b-row0-manifest.md` — the `INST` SHA pin
- `qa/rr-study/2026-08-30-1821-qa-to-architect-f001-sup-b-amendment-2-row0-result.md` — ROW 0b
- `qa/rr-study/harness/run_scenario.py` — `_MAX_BATCH_TRIALS`
