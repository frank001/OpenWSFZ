# `FP-PARITY` — Architect → QA spec: reconcile the offline/in-chain false-accept rate, and measure the in-chain genuine excess floor

**Architect, 2026-09-03 16:16Z** (`date -u`, HK-017). Base `main`@`b4dd754`, branch
`arch/2026-09-02-row0-redaction-and-awgn-fp-amendment`. Ordered by the PO on 2026-09-03 in response
to QA's `AWGN-FP` M1–M4 report (2026-09-03 15:35Z, §3.2 and §9).

**Companion amendments landed in the same session, and they are preconditions for reading this
spec:** `2026-09-02-1906-…-awgn-fp-offline-replay.md` **Amendment 2** (A2.1 the ROW 1 denominator
defect, A2.2 the `NormalisePcm` parity gap, A2.3 why `T = 9.146 dB` is not shippable, A2.4 the
slot-vs-row record correction).

---

## 0. What this arm is, and the two things it must not become

Two deliverables, independent, in one arm because they share an instrument and a population:

- **D1 — reconcile the rate gap.** QA measured this offline instrument's chronic false-accept rate
  at **10.875% [9.93%, 11.88%]** (n=4,000) against an in-chain pooled comparator of 2.22%. Before
  anyone attributes that to physics, the two numbers must be shown to be **the same measurement of
  the same thing**. Two defects are already known to sit between them (§1), both mine.
- **D2 — measure the in-chain genuine excess floor.** The emission-side filter cannot be specced
  without it (Amendment 2 A2.3). This is the single input that decides whether the route is viable
  at all.

🛑 **What this arm is NOT.** (1) It is **not** a hardware capture run. Nothing here needs the radio,
Voicemeeter, or a live sweep — §5 is ordered so that a capture is only ever proposed *after* the
cheap explanations are excluded, and proposing one is a **separate** pre-registration. (2) It is
**not** a licence to build the filter. ROW 2 authorises QA to *author a dev-task*; HK-011 applies in
full and the Architect neither builds nor pushes (HK-014).

🔴 **Standing disclosure:** the Architect is **de-blinded** on the offline excess distributions
(`AWGN-FP` A1.0). **Prediction scoring stays suspended for every threshold in this document.** §7's
predictions are recorded for calibration only and **nothing gates on them**.

---

## 1. What is already established — do not re-derive it (HK-018)

Read these before running anything; each is measured, sourced, and on disk.

| Fact | Source | Status |
|---|---|---|
| Offline chronic rate 10.875% [9.93%, 11.88%], n=4,000; flat across trial windows; seeds distinct; 60 shared WAVs byte-identical to the ROW 0b anchor; 0/60 decode-order differences | `awgn-fp-replay/results/M1-M4-report.md` §2–§3.1 | **Solid. Do not re-run to "check".** |
| 454 false accepts, 100% at reported SNR ≤ −25 dB; excess min −1.944, median −0.142, **max +1.622 dB** | same, §4 | **Solid.** The FP ceiling `C` this arm needs. |
| M3 genuine excess min **14.987 dB** on the S1 ladder; 2,300/2,300 recall | same, §5 | Solid **for that ladder only** — see §2.2. |
| `snr = signal_db − local_noise_db − 26.5f`, no floor, no clamp | `ft8_shim.c:1719` | Solid. ⇒ `excess = snr + 26.5`. |
| S5 parts 2/3 are carrier/multi-carrier, **not AWGN**; only parts 0/1 are the AWGN population | `s5-level/results/2026-09-03-s5-level-row0-report.md` ROW 0f | Solid, exhaustive enumeration. |
| The daemon normalises every buffer to RMS **0.20** before `DecodeAll` | `Ft8Decoder.cs:52/271/303` | Solid. ⇒ in-chain level is fixed; capture **gain** cannot move the rate. |
| The offline seam does **not** normalise | `AwgnFpReplayTests.cs:425` | Solid. ≈**6.9 dB** quieter than production. |
| ALL.TXT is written **unfiltered** | `Program.cs:806` (`// unfiltered`), `AllTxtWriter.cs:74` (only `Enabled`/empty guards) | Solid ⇒ **no in-chain censoring at the log writer.** |
| decode-noise-suppression never affects ALL.TXT | `DecodeNoiseSuppressionConfig.cs` doc, design.md Decision 1 | Solid ⇒ **ruled out; do not chase it.** |
| AP bits are set in-chain during a QSO and cleared offline | `Ft8Decoder.cs:295`, `AwgnFpReplayTests.cs:424` | A real difference, but it pushes the **in-chain** rate **up** — wrong direction to explain the gap. **Record, do not chase.** |
| `Ft8NativeResult.Snr` is **`int`** | `Ft8NativeResult.cs:32` | ⇒ every in-chain SNR ever recorded is **integer dB**. Readout quantum **1 dB** (HK-021(o)). |

**The two defects already known to sit between the numbers, both the Architect's:**

1. **Denominator** (Amendment 2 A2.1): the ROW 1 band mixed `/120` and `/60` denominators; on a
   consistent AWGN denominator the pooled figure is 12/360 = **3.33%**, not 2.22%.
2. **Numerator provenance**: the in-chain counts came through `matcher.py` Pass 2 + an OR-rule
   dedupe + a cycle→part attribution join. The offline count is direct. 🔴 **HK-026: that pipeline's
   own output may not be used to bound that pipeline's own blind spot** — ROW 0m must recount by an
   independent path.

---

## 2. Definitions this arm fixes, so no row can be read in the wrong unit

### 2.1 The counting unit — this is where the last gap died once already

- **`slot`** — one 15 s cycle of one part of one scenario. **The unit of every rate in this arm.**
- **`event`** — a slot carrying **≥ 1** decode. **Rates are `events / slots`, always.**
- 🛑 **A decode row is NOT an event.** M1's 435 events across 4,000 slots produced **454 decode
  rows**; the in-chain comparator is a cycle-deduped cluster count. **Compare 435/4,000 to the
  in-chain clusters — never 454/4,000** (HK-021(i); Amendment 2 A2.4).

### 2.2 `excess`, and the two ways it is read

`excess ≜ signal_db − local_noise_db`, the **separate terms** — immune to the `c3a9ea8` SNR-scale
change (`AWGN-FP` §0.2).

- **Offline:** read directly from `GetLastSnrTerms`, float. Quantum: float.
- **In-chain:** **not recorded anywhere.** Only integer `Snr` reaches ALL.TXT. So in-chain excess is
  **reconstructed** as `excess = Snr + 26.5`, quantum **1 dB**, i.e. **±0.5 dB**.
  🔴 **And the sign of that error is not yet known** — whether the float→`int` conversion truncates
  (biases a negative SNR *upward*, and therefore biases reconstructed excess **upward**, i.e.
  *unsafely* for a floor) or rounds. **ROW 0q settles it off data already on disk.**

### 2.3 The genuine population, and its truncation

**`F` ≜ the minimum in-chain `excess` over decodes that match their own slot's injected truth.**
🔴 **`F` is a sample minimum of whatever the study injects — it cannot go below the weakest injected
level** (HK-026). ⇒ It **must** be measured on **S1b** (`s1b-snr-threshold.json`, parts **−24, −21,
−18, −15 dB**), the only ladder that reaches the decoder's real sensitivity region. Measuring it on
S1 is what produced Amendment 2 A2.3's error in the first place: S1's floor sits ~6 dB high.
**Report alongside `F`: the weakest injected level at which any truth-matching decode occurred, and
the decode rate at the ladder's bottom rung.** If the bottom rung decodes at a high rate, `F` is
still truncated and must be reported as an **upper bound on the true floor**, never as the floor.

**`C` ≜ the maximum `excess` over false accepts** = **+1.622 dB** offline (n=454), plus the
in-chain historical false accepts reconstructed per §2.2.

---

## 3. Instrument repairs required before any absolute rate is quoted

Both are **tests-only**. `NormalisePcm` is `internal static` and
`[assembly: InternalsVisibleTo("OpenWSFZ.Ft8.Tests")]` is already present
(`src/OpenWSFZ.Ft8/AssemblyAttributes.cs:3`) ⇒ **zero `src/`/`native/` diff, no HK-011 cycle.**
Verify that with `git diff --stat -- src/ native/` and **say so in the report**.

1. **Apply `Ft8Decoder.NormalisePcm(pcm, 0.20f)` in `DecodeDirectory` before `DecodeAll`** — the
   production input contract. Keep the un-normalised path available behind a parameter so ROW 0n is
   a paired comparison on identical WAVs, not two runs of different code.
2. **Call `SetDecodeParams` with the daemon's effective values** before decoding (ROW 0o).
   🛑 **This is parity, NOT tuning.** The candidate-budget family (`s_k_min_score_pass2`,
   `K_MAX_CANDIDATES*`, the pass table) is **closed twice** and stays closed: this arm asserts the
   offline seam matches production and **may not vary those values for any purpose.** If a row
   implicates them, that is a finding to *report* and it earns its own pre-registration.

---

## 4. Pre-registered rows

Every predicate ships as code (HK-021(r)) in one script under `qa/rr-study/fp-parity/`, printing
each row's inputs, its threshold, and its verdict. Print **every** row, then the first firing
verdict.

### ROW 0 — the instrument and the comparator

- **0m — in-chain numerator, recounted independently.** For each of the six named sweeps
  (`7d36038`, `f5dec23`, `22b749c`, `872ba65`, `2e60949`, `3b52608`), recount S5 AWGN events
  **from the raw `owsfz-all.txt`**, mapping each decode's cycle to `(scenario, part)` via that
  sweep's own `truth.csv` `cycle_utc`, restricted to `s5-noise` **parts 0/1**, counted as **events
  per §2.1** (a slot with ≥1 decode). 🛑 **Do not use `*_matched.csv`, and do not import
  `matcher.py`** — HK-026: an independent path is the whole point.
  **FIRES iff** any recounted `k_i` differs from the published `k_i`, **or** any published
  denominator ≠ 60.
  ⇒ **Consequence, asserted either way:** the recounted `Σk_i / 360` and its exact Clopper–Pearson
  95% CI **replace** `[1.15%, 3.85%]` as the in-chain comparator for all future work, and the 2.22%
  figure is **retired, not merely corrected**. If the row does not fire, 12/360 = 3.33% is
  confirmed and becomes the comparator. **Either branch changes what is citable** (HK-021(k)).
  ⚠️ **What this row cannot detect** (HK-022): whether a sweep's ALL.TXT was itself incomplete —
  a gap in logging, or cycles the daemon never processed. **Report the per-sweep slot coverage**
  (cycles present in `truth.csv` vs cycles present in ALL.TXT) alongside each `k_i`; a coverage
  shortfall is a separate finding, not something to fold into `k_i`.
- **0n — normalisation parity.** Re-decode the S5 parts 0/1 population **with** `NormalisePcm`, on
  the **same WAVs already on disk** (`_work/m1m4_s5/` — check `qa/ARTEFACT_INVENTORY.md` **before**
  concluding anything is missing, and re-render only what is genuinely absent). Pre-registered
  **N = 1,000 per part** (2,000 slots), not the full 4,000: readout quantum 0.05%, CP half-width
  ≈ ±1.4 pp at p≈0.11 — **sufficient to detect a ≥2× change, insufficient to resolve a <20%
  relative change**, and that is the intended power (HK-021(v), at my own stated expectation in §7).
  **FIRES iff** the normalised pooled rate's 95% CI **excludes** 10.875%. **Report the signed
  difference** (`normalised − unnormalised`), never `|Δ|` (HK-021(l)).
  ⇒ **Consequence, asserted either way:** the **normalised** figure becomes the **only** citable
  offline absolute rate from this day forward, because it is the only one measured under the
  production input contract. A non-fire does **not** restore 10.875% — it means the two agree.
- **0o — decode-param parity.** Read the machine's effective `(KMinScorePass2, OsdCorrThreshold,
  OsdNhardMax)` from the live `config.json` (falling back to `DecoderConfig`'s documented defaults
  `10 / 0.10f / 60` when the key is absent — that fallback is what `Program.cs:728` does) and assert
  the offline seam is configured identically. **FIRES iff** any of the three differs.
  ⇒ **Consequence:** if it fires, **every offline absolute rate this project holds is void** until
  re-run at parity, including 10.875% and ROW 0n's. Say that plainly; do not re-run first and
  report second.
- **0p — the WAV→decoder path is otherwise identical.** Assert: 180,000 samples, no resample, no DC
  removal, AP bits cleared, one `DecodeAll` per slot, binary SHA256 equal to the pinned
  `ce02c7ba…153e`. **FIRES iff** any assertion fails ⇒ STOP, the instrument is not the one M1–M4
  used.
- **0q — the `int` SNR conversion: truncation or rounding?** On the **existing** M1–M4 decode CSVs
  (`m1m4_s5_decodes.csv`, `m3_s1_decodes.csv` — 2,754 rows already on disk, **no new run**), compare
  each row's integer `reported_snr_db` against `reconstructed_snr_db`. Classify mechanically as
  truncate-toward-zero / round-half-away / round-half-even by exact agreement across all rows.
  **FIRES iff** the classification is not unanimous across every row.
  ⇒ **Consequence:** the resulting rule fixes the **sign** of §2.2's ±0.5 dB, and `F` in ROW 1 must
  be corrected by it in the **conservative** direction (whichever makes `F` smaller). A non-unanimous
  result means in-chain excess is not reconstructible and **ROW 1 must be re-scoped to a
  populated-terms capture**, which is a new pre-registration, not a patch.

### ROW 1 — the in-chain genuine excess floor `F`

**Not a fire/no-fire row: a measurement, reported with its own uncertainty.** Over every
post-`c3a9ea8` sweep on disk, on the **S1b** population (§2.3), take truth-matching OpenWSFZ
decodes, reconstruct `excess` per §2.2 corrected by ROW 0q, and report: `F` (the minimum), the p01
and p05, `n`, the weakest injected rung producing any truth-matching decode, and the decode rate at
that rung. **Report `F` as an upper bound on the true floor whenever the bottom rung decodes at
> 50%** — with the rate stated, not the adjective.
🛑 **`F` is never quoted without `n`, the quantum (1 dB), and the truncation statement.**

### ROW 2 — the emission floor is viable, and the dev-task is authorised

**`T` is set by the false-accept ceiling, never by `F`:** `T ≜ C + 1.0 dB` (one in-chain readout
quantum above the highest false accept measured anywhere).

**FIRES iff `F − T ≥ 6.0 dB`.**

⇒ **Consequence:** QA authors the emission-side filter dev-task (HK-011: authors and **stops**) at
that `T`, with acceptance criteria measured **in-chain**, not inherited from the offline removal
fraction. Report the removal fraction `T` achieves on the 454 offline false accepts and the
**rule-of-three 95% upper bound** on the genuine loss rate at `n` — **never "costs nothing."**

🔴 **The 6.0 dB is a policy margin, not a measurement,** and I am de-blinded, so it is stated with
its justification rather than asserted: 1 dB readout quantum + 1 dB conversion-sign uncertainty +
≥4 dB for the S1b ladder's own truncation (§2.3), which no instrument we hold can bound.

### ROW 3 — the margin is not there

**FIRES iff `F − T < 6.0 dB`.** ⇒ **No dev-task is authored.** State plainly: *the emission-side
floor cannot be set with the project's required margin on the evidence available, because the
genuine population reaches down to within `F − T` dB of the false-accept ceiling.* 🛑 **PARKED, not
closed** — closing the route requires a population that reaches the decoder's true floor, which
S1b's bottom rung may not. Do **not** soften this into "needs more data" and do **not** re-run with
a smaller margin.

ROW 2 and ROW 3 are exact complements by construction; exactly one fires.

### ROW 4 — anything else

Report the numbers, fire no conclusion. A row that does not fire is not a licence to narrate.

---

## 5. What QA does, in order

1. **Read `qa/ARTEFACT_INVENTORY.md` first** (standing rule, violated 4×) and confirm which of:
   `_work/m1m4_s5/` WAVs, the six sweeps' raw `owsfz-all.txt`, and any S1b sweep data are on disk.
   **Report what is missing before rendering or capturing anything.**
2. **ROW 0q** — pure analysis of CSVs already on disk. Minutes, no run. Do it first: it changes how
   ROW 1 is computed.
3. **ROW 0m** — the independent recount. No new decoding, no hardware.
4. **ROW 0o, ROW 0p** — parity assertions. Then **ROW 0n** — the paired re-decode (supervised per
   HK-013/HK-023 if it runs long; a `Monitor`-owned process dies at session end).
5. **ROW 1**, then **ROW 2/ROW 3**.
6. Report per HK-001. **Headline must carry §0's two bars: this arm proposes no capture run and
   builds no filter.**
7. If — and only if — ROW 0m/0n/0o all close clean and the gap survives, **stop and hand back**: a
   hardware capture to test spectral colouring / quantisation / downsampling (QA's own §9
   recommendation 1) is then the right next step and earns **its own pre-registration**. Do not
   fold it into this arm.

**HK-025 stands: QA may refuse to run any row here on HK-021(k) grounds without the Architect's
agreement.** Classify (validity vs precision), evaluate both branches, and if the same row fires
either way it is diagnostic — refuse it and say why.

---

## 6. Standing bars this arm does not lift

- 🛑 The candidate-budget family stays closed (§3.2). Input scaling stays closed — **`NormalisePcm`
  parity is matching production, not scaling input**, and it may not be varied as a lever.
- 🛑 No `src/` or `native/` change is licensed. Both repairs are tests-only; assert it mechanically.
- 🛑 Efficacy against **real off-air** false accepts remains unmeasurable here. Nothing in this arm
  changes that, and a ROW 2 fire is a **sizing**, not a ship decision.
- 🛑 S7 P2, Station F / `F-NBR-A` / `NBR-A`, the S7 gap band, `S_max`, the retired figures list —
  all untouched.
- 🛑 NFR-021: any new decode CSV is redacted **before** the report is written, guarded against the
  injected truth text first, byte-level rewrite (UTF-8 BOM + CRLF), re-scanned to 0/0. The shipped
  scanner **cannot scan an uncommitted directory** — import its `scan()`/`classify()` over a
  directory walk (HK-022 false green).

## 7. Blind predictions — 🛑 nothing gates on these, and scoring is suspended (A1.0)

P(ROW 0m fires) ≈ **0.75** — I expect at least one published numerator not to reproduce, because
the attribution join was never audited. P(ROW 0n fires) ≈ **0.35** — ROW 0c's ±10 dB flatness argues
the level does not matter, so I expect parity to change little. P(ROW 0o fires) ≈ **0.15**.
P(ROW 0q non-unanimous) ≈ **0.10**. P(ROW 2) ≈ **0.40** / P(ROW 3) ≈ **0.60** — I expect S1b to
produce truth-matching decodes near its −24 dB rung, which would put `F` close enough to `C` that
the 6 dB margin fails. **If ROW 3 fires, that is the arm working, not the route failing.**

---

# AMENDMENT 1 — 2026-09-04: ROW 1's population is located, named and frozen; and ROW 2/3 is a knife edge

Occasioned by the PO's 2026-09-03 S1–S8 sweep (`1241679`, `results/2026-09-03-35378b9/`), read
2026-09-04. **No row is re-drafted. Nothing is softened. Two things are fixed in place and one thing
is disclosed before the reading.**

## A1.1 The "S1b sweep not yet located" blocker is discharged — the data was never missing

§4 ROW 1 reads *"over every post-`c3a9ea8` sweep on disk, on the S1b population"*. That set is now
enumerated, **verified present, and FROZEN as pre-registration** so it cannot be reselected after the
reading:

| Sweep dir | S1b truth rows | `owsfz-all.txt` | `truth.csv` |
|---|---|---|---|
| `results/2026-08-27-22b749c` | 12 | ✅ | ✅ |
| `results/2026-08-29-872ba65` | 12 | ✅ | ✅ |
| `results/2026-08-30-2e60949` | 12 | ✅ | ✅ |
| `results/2026-09-02-3b52608` | 12 | ✅ | ✅ |
| `results/2026-09-03-35378b9` | 12 | ✅ | ✅ |

**5 sweeps × 12 = 60 S1b slots.** All five verified on disk 2026-09-04. All five post-date `c3a9ea8`
(2026-08-22 18:33 +02:00), so §2.2's restriction holds for every one — checked, not assumed.

⚠️ **`2e60949` disambiguation:** use **`2026-08-30-2e60949`**. `2026-08-31-2e60949` is an S7-only
rerun sharing the short SHA and carries **no** S1b data — the identical trap ROW 0m already hit.

🛑 **No sweep may be added to or removed from this list after ROW 1 is read.** A sixth sweep run
later is a **new** pre-registration, not an extension of this one.

🔴 This is HK-018 firing again: the blocker was recorded on the board as "not yet located" while five
sweeps' worth of raw data sat on disk the whole time.

## A1.2 ROW 1's truncation statement is knowable in advance, and it is hard

2026-09-03's S1b, **OpenWSFZ**: `0/3 @ −24` · **`0/3 @ −21`** · `3/3 @ −18` · `3/3 @ −15`.
(WSJT-X on the same slots: `0/3` · **`2/3`** · `2/3` · `3/3`.)

⇒ The weakest rung producing OpenWSFZ truth-matching decodes is **−18 dB, at a 100% rate**. §2.3 and
ROW 1's own >50% rule therefore **force `F` to be reported as an UPPER BOUND on the true floor**, not
as the floor. Non-negotiable, and now known before the run rather than discovered in it.

🔴 **And the −21 rung is not a marginal miss.** WSJT-X took **2/3** there, so a genuine population
demonstrably exists **≥3 dB below anything OpenWSFZ's S1b ladder can see**. The instrument's response
is **flat where the boundary sits** — HK-026 in its plainest form. The ≥4 dB the 6.0 dB policy margin
allocates to ladder truncation (§4 ROW 2) is doing real work here, not hedging.

## A1.3 🔴 ROW 2 vs ROW 3 will be decided by ONE decode's readout quantum — disclosed before the run

`C` is unmoved by the new sweep: its two in-chain false accepts (−26 dB, −27 dB) reconstruct to
`excess` **+0.5** and **−0.5 dB**, both far below the `C = +1.622 dB` ceiling. **They raise `n` on the
in-chain false-accept population and do not move `C`** ⇒ **`T = C + 1.0 = 2.622 dB`, unchanged.**

ROW 2 fires iff `F − T ≥ 6.0` ⇒ iff **`F ≥ 8.622 dB`**. With `excess = Snr + 26.5` (§2.2) and ROW 0q's
conservative −0.5 correction:

| Weakest truth-matching reported SNR | `excess` | after −0.5 | Verdict |
|---|---|---|---|
| −18 dB | 8.5 | **8.0** | **ROW 3** (margin 5.38) |
| −17 dB | 9.5 | **9.0** | **ROW 2** (margin 6.38) |

S1 bias is **+0.82 dB**, so a −17 reading on a −18 dB injection is **expected, not exotic**.

🛑 **The gate stands exactly as written.** The 6.0 dB is a declared policy margin, the PO has seen it,
and I am **not** re-drafting it now that I can see where it lands — that is reading a closed gate with
a better metric, which is barred.

🔴 **But a verdict resting on n≈1 must show that it does.** QA reports, alongside the ROW 2/ROW 3
verdict and in the same section:

1. the **lowest 5** reconstructed `excess` values, sorted, each with its **injected rung**, its
   **reported SNR**, and its **sweep ID**;
2. **how many distinct decodes sit within ±1 dB of the 8.622 dB fire line**;
3. `n`, the 1 dB quantum, and the A1.2 truncation statement — §4's existing 🛑 (*"`F` is never quoted
   without `n`, the quantum, and the truncation statement"*), restated because this is where it bites.

## A1.4 Prediction correction — my §7 reasoning is falsified, whatever the verdict

§7 predicted P(ROW 3) ≈ 0.60 **because** *"I expect S1b to produce truth-matching decodes near its
−24 dB rung, which would put `F` close enough to `C`"*. **That reasoning is now wrong on the data:**
OpenWSFZ produces **nothing** at −24 or −21. If ROW 3 fires it will be for the **opposite** reason —
the ladder truncates **high**, not low. Scoring stays suspended (A1.0); this is recorded so the
prediction is not later read as having been right.
