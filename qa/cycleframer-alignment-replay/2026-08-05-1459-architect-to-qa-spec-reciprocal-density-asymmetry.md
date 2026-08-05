# Arm R.D — spec: reciprocal density asymmetry, reference-free
# Whose density penalty is it — ours, or the band's?

**Author:** Architect, 2026-08-05 (14:59 UTC, `date -u`, per HK-017). Repo `main` at `dd237bc`.
**Requested by:** the Captain, 2026-08-05 — *"make progress on D-001."*
**For:** QA. Executable as specced — **no `src/` change, no capture run, no Developer session.**
**Answers:** `project-state-2026-07-31-d001-competition-confirmed.md` §5.4, which named this
*"the single most decision-relevant unknown for the menu"* and assumed it needed a capture that
had not been run.

---

## 0. Headline, stated before the detail

1. **The capture §5.4 asked for already exists.** `20260803_live_run_1713` is 20m, contiguous,
   drift-clean, post-`be5960a`, and carries both decoders on **one verified audio path**. It was
   captured two days after §5.4 was written and has been used for Tasks 1/3/5 without anyone
   reading it as the D-001 replication corpus. **No capture run is authorised or needed.**
2. **The Captain's "~40% shortfall" reproduces exactly on it** — we miss **42.2%** of WSJT-X's
   decodes. It is real and it is not a drift artefact.
3. **And simultaneously WSJT-X misses 61.8% of ours.** The two decoders agree on **29.9%** of the
   union of what they find, on identical audio. That asymmetry is what this arm measures.

Item 3 is new. It does not soften item 2 — both are true at once, and any menu decision taken on
item 2 alone is being taken on half the picture.

## 1. What is already established (measured 2026-08-05, not recalled)

All figures below are **Architect feasibility scouting**. They are *not* this arm's outcome and
**must not be cited as a verdict** — they are unstratified, un-SNR-matched, and taken outside any
pre-registered rule. QA re-derives everything under §4.

**Corpus `artefacts/20260803_live_run_1713/`**, from `qa/ARTEFACT_INVENTORY.md` (`--check` clean,
2026-08-05) and from the files themselves:

| property | value | source |
|---|---|---|
| Band | **14.074 MHz — 20m**, both legs | frequency column, both `ALL.TXT` |
| Span | 260803_171330 → 260804_135645 | inventory |
| Decisive epoch | **one contiguous 18.96 h epoch** | Task 5 self-check 1 |
| Drift | **ROW 5 PASS, +0.0 ppm** | `2026-08-04-1405-…-PASS.md` |
| Legs | `owsfz` 4,614 cyc / `wsjt-x` 4,531 cyc, **not hardlinked** | inventory |
| WAVs | 4,971 / 4,963; **4,956 shared filenames**, 12 kHz mono 16-bit 15.00 s both | disk |
| Capture device | `Microphone (2- USB Audio CODEC)` — the 48.0 ppm FT-991A chain | `contents.md` |

**Same audio path — verified, not assumed.** 8 random shared-filename WAV pairs, FFT
cross-correlation with ±250 ms lag search:

```
median |r| = 0.9870   (range 0.9768 – 0.9947)
best-lag   |lag| <= 34.1 ms on every pair
RMS ratio   0.902 – 1.036
```

Same signal content, sub-cycle window offsets, near-unity gain. **The one antenna / two radios
confound recorded in memory does not apply to this run.** §4.3 V3 re-runs this at n≥20 as a gate.

**Duplicate emission — zero on both legs.** `distinct(ts,msg) == rows` exactly, both decoders,
56,202 and 37,158. Neither leg has the property that invalidated `jt9 -d 3`. Raw counts are honest.

**Reciprocal overlap, decisive epoch, distinct `(ts, message)`:**

| quantity | value |
|---|---:|
| OpenWSFZ decodes | 56,202 |
| WSJT-X decodes | 37,158 |
| Both | 21,487 |
| OpenWSFZ only | 34,715 |
| WSJT-X only | 15,671 |
| **of WSJT-X's, we missed** | **42.2%** |
| **of ours, WSJT-X missed** | **61.8%** |

**Density range available:** WSJT-X per-cycle decode quartiles give a sparse-vs-dense contrast of
**6.54×** on this corpus. Measurement D needed 2.2× and the VOID bar is 2.0×; there is ample
headroom, so §4.3 V2 keeps D's bar at **2.0 and does not relax it.**

## 2. The question, and why it decides the menu

**Question:** does the density penalty measured by Measurement D belong to *our decoder*, or to
*dense 20m as an environment*?

- **Ours** ⇒ there is something to buy. Menu rows 4/5 (front-end/sync work; adopt WSJT-X core)
  have a defined target and their cost can be weighed against a known gain.
- **The band's** ⇒ a decoder of WSJT-X's maturity pays the same penalty on the same audio, NFR-018's
  80% parity target may be unreachable by anyone in this regime, and the honest move is menu
  **row 1** — accept and re-baseline.

That is the fork the B.3 menu has been sitting on since 2026-07-27. This arm resolves it.

## 3. Design — and the non-circularity problem it has to solve

Measurement D's load-bearing rule was: **density comes from the reference decoder, never from us**
— *"using our own count is circular (cycles we did badly on would be labelled sparse by
construction)."* That rule was correct and it is why D is citable.

There is no valid reference any more. Offline `jt9 -d 3` is barred by standing rule (+93.8%
overshoot vs OpenWSFZ, duplicate `(ts,message)` emission), and it was jt9-as-reference that VOIDed
Angle 1 after full execution. So the arm must be **symmetric** rather than referenced.

**Primary density index: `both(c)` — messages decoded by BOTH decoders in cycle `c`.**

Symmetric by construction: neither decoder's *exclusive* misses move its own stratum label
preferentially. Its weakness is stated plainly — if both decoders degrade in genuinely dense
cycles, `both` under-reports density exactly there, compressing the strata toward each other. That
biases **toward the null**, which is the safe direction for an arm whose positive result would
authorise expensive work.

**Sensitivity index: `union(c) = |A ∪ B|`** — inflated by each decoder's exclusive finds, also
symmetric, and biased the opposite way. V7 requires the two indices to agree on the row outcome.

**The statistic.** Let A = OpenWSFZ, B = WSJT-X. Per density stratum `S`:

```
miss_A(S) = |B_only ∩ S| / |B ∩ S|      fraction of B's decodes that A missed
miss_B(S) = |A_only ∩ S| / |A ∩ S|      fraction of A's decodes that B missed

Δ_A = miss_A(H) − miss_A(L)             percentage points
Δ_B = miss_B(H) − miss_B(L)

D   = Δ_A − Δ_B                         ← the decisive statistic
```

`D` is a difference-in-differences. **Anything that makes dense cycles harder for both decoders
cancels in `D`** — propagation, occupancy, QRM, AGC. What survives is decoder-*specific* density
sensitivity, which is precisely the menu's question.

**SNR handling — why each half uses a different scale, and why that is correct.** `miss_A` is
computed over B's decode population, for which **B** reports SNR; `miss_B` over A's population, for
which **A** reports SNR. Each metric is binned in 2 dB bins on **its own population's finder's
scale**, following Measurement D §3. Our S7 gain error (slope 0.6865) therefore never mixes scales:
`Δ_A` is a difference across strata computed wholly in B's scale, `Δ_B` wholly in A's. The scale
cancels *within* each Δ before the two are subtracted. Do not "correct" one scale onto the other.

**Matching** is reused unchanged from `measurement_d_within_band_density.py` — single-pass greedy
consumption resolved ONCE over the full corpus, stratum filters selecting only which rows tally
into which stratum's bins. Middle-quartile cycles participate in the matching pass and are tallied
into neither stratum.

## 4. The reading rule — mechanical, pre-registered, evaluated in strict order

### 4.1 Population and strata (fixed here, in git, before any outcome exists)

- **Included:** cycles in the decisive epoch (`ts >= 260803_185914`, per Task 5's epoch boundary).
- **Stratum L:** bottom quartile of included cycles by `both(c)`.
- **Stratum H:** top quartile by `both(c)`.
- **Excluded:** middle two quartiles, deliberately.

### 4.2 Statistic

`Δ_A`, `Δ_B`, `D` per §3, aggregated over **common-support 2 dB SNR bins only** (n ≥ 20 in both
strata), Wilson 95% intervals reported per bin.

### 4.3 VOID gates — evaluated FIRST, in order. Any one firing ⇒ VOID, and no row outcome of any kind is reported.

| # | condition | ⇒ |
|---|---|---|
| V1 | `n_L < 300` **or** `n_H < 300` cycles | **VOID** |
| V2 | `median(both \| H) < 2.0 × median(both \| L)` | **VOID** |
| V3 | over **≥ 20** random shared-filename WAV pairs: `median \|r\| < 0.95` **or** any pair's best-lag `\|lag\| > 250 ms` | **VOID** — audio paths not common; hardware confound live |
| V4 | the corpus's drift-screen row is not a PASS (**cited, not re-run**) | **VOID** |
| V5 | duplicate `(ts,msg)` rate `> 1.0%` on either leg in either stratum | **VOID** |
| V6 | fewer than **8** common-support SNR bins for either `Δ_A` or `Δ_B` | **VOID** |
| V7 | re-running §4.4 with density index `union(c)` yields a **different row** | **VOID** — report both |
| V8 | permutation null fails (§4.5) | **VOID** |

### 4.4 Reading rule — mutually exclusive, exhaustive, strict order, first match wins

| # | condition | reading | consequence |
|---|---|---|---|
| **1** | `Δ_A < 5.0` | No material density penalty on us **on this corpus** | **Escalate. Do not interpret.** This contradicts D's ~19.8 pts and does **not** disprove it — different corpus, different instrument. Architect reconciles |
| **2** | `Δ_A >= 5.0` **and** `D >= 5.0` | Penalty is **ours**, not the band's | Menu rows 4/5 have a defined target ⇒ return to the Captain **priced**. **Do not start any of it** |
| **3** | `Δ_A >= 5.0` **and** `D <= −5.0` | WSJT-X degrades **more** than us with density | **Escalate.** Premise inverted; the menu's framing needs rewriting before any decision |
| **4** | `Δ_A >= 5.0` **and** `−5.0 < D < 5.0` | Both decoders degrade **together** | Density penalty is a property of dense 20m, not of us. Points at menu **row 1** (accept / re-baseline NFR-018) ⇒ return to the Captain |

**The 5.0 pt threshold, justified rather than picked.** Measurement D's density penalty was
~19.8 pts, so a real D-sized effect clears this bar by ~4×. At the expected stratum sizes (≈1,000
cycles, ≥10,000 messages per stratum) the Wilson half-width on a miss rate near 0.4 is well under
1 pt, so 5.0 sits far outside binomial noise. It is set to be clearable by a real effect and not by
sampling error, and it is fixed here before any outcome exists.

### 4.5 Mandatory permutation null

Shuffle the stratum label (L/H) across included cycles, **20 times**, recomputing `D` each time.
**Observed `|D|` must exceed the maximum `|D_shuffled|` across all 20.** If it does not ⇒ **V8 fires
⇒ VOID**; report the null failure, not the result.

### 4.6 Reporting

`n_L`, `n_H`, both density medians and their ratio, `miss_A(L)`, `miss_A(H)`, `miss_B(L)`,
`miss_B(H)`, `Δ_A`, `Δ_B`, `D`, per-bin tables with Wilson intervals, the 20 shuffled `D` values,
the V7 sensitivity outcome, and the V3 correlation table.
**NFR-021: aggregates only — no callsigns, no message text, in output or in any committed file.**

## 5. What this arm does and does not decide

- **Decides:** whether the density penalty is decoder-specific or environmental. That is the B.3
  menu's open fork and nothing else on the board resolves it.
- **⚠️ Does NOT establish decoder quality, and this is the sharpest limit.** An exclusive decode is
  not a *correct* decode. **No oracle exists here.** The 34,715 messages WSJT-X missed may be
  genuine sensitivity or may be false positives — and **the post-fix FP surge is open and
  unclosed**. If our exclusive set is substantially false, row 2 would fire and would be
  **misleading**: we would look density-robust because we emit junk indiscriminately. Row 2 must
  therefore be read as *conditional on the FP surge being closed*, and it returns to the Captain
  priced, not actioned.
- **Does not touch mechanism 1** (the ~34% baseline deficit). That number was measured against
  offline `jt9 -d 3`, now barred; it needs its own recalibration, which is mine and is not in this
  document.
- **Does not close the FP surge.** It measures asymmetry, not correctness.
- **WSJT-X remains a co-appraiser, not an oracle** — 86.9–93.0% within-appraiser repeatability
  (`qa/rr-study/results/corpus-2026-07-10/report.md`). The difference-in-differences cancels its
  *level*, but **not** a density-dependent change in its own repeatability. V8's null guards this
  partially; it does not eliminate it. Stated as a limitation, not a solved problem.
- **Authorises no run of anything else**, no `src/` change (HK-011), no push or merge (HK-014/010).

## 6. Honest caveats

- **The `both(c)` density index attenuates.** §3 states the direction (toward the null). A row-1
  outcome is therefore weaker evidence of "no penalty" than a row-2 outcome is of "penalty is ours".
  V7's `union(c)` sensitivity run is what stands between this and an artefact of index choice.
- **§1's 42.2% / 61.8% are scouting figures.** They are whole-corpus, unstratified and
  un-SNR-matched. They motivate the arm; they are not its result and must not be quoted as one.
- **The strata are defined on the same corpus the arm runs on.** Mild post-hoc exposure, mitigated
  by quartile boundaries being data-defined rather than hand-picked and by the outcome variable
  never having been observed — but it is not zero.
- **29.9% agreement between two mature FT8 decoders on identical audio is extraordinary** and I do
  not have an explanation for it. It may indicate something wrong with one leg's configuration
  (decode depth, passband, threshold) rather than genuine decoder divergence. This arm measures the
  asymmetry's *density dependence* and remains valid either way, but **the raw disagreement itself
  deserves its own investigation** and I am flagging it rather than absorbing it.

## 7. Cross-references

- `project-state-2026-07-31-d001-competition-confirmed.md` §5.4 — the request this answers.
- `qa/cycleframer-alignment-replay/measurement_d_within_band_density.py` — matching pass, SNR
  binning, and the non-circularity rule §3 had to work around.
- `2026-07-31-1355-…-row4-decomposition-rev2-competition-scoped.md` — the design this sits beside.
- `2026-08-04-1733-…-task5-isolated-replay-ROW4-STRONG.md` §1 — the epoch boundary §4.1 uses.
- `qa/endurance/2026-08-03-drift-screen/2026-08-04-1405-…-PASS.md` — V4's cited row.
- `qa/rr-study/2026-08-04-1500-…-false-positive-surge-…md` — the open FP surge §5 is conditional on.
- `qa/ARTEFACT_INVENTORY.md` — §1's corpus, `--check` clean before writing.

---

*Per HK-015 this is Architect → QA: a design for QA to scope and author as `dev-tasks/`, not tasks
issued by me. Per HK-014/HK-010 committed locally, no push, no merge, and I do not ask for one. Per
HK-011 nothing here touches `src/`. Per HK-021 §4 is drafted as the code that would evaluate it —
hard thresholds, consequences as assertions, rows mutually exclusive and exhaustive in strict
order, and the 5.0 pt bar justified before any outcome exists. Per HK-018 §1 was measured from disk
and from a freshly `--check`ed inventory today, not asserted from memory — including the
same-audio-path check, which was the assumption most likely to silently defeat the arm. Per HK-017
filename and byline carry `date -u` UTC.*
