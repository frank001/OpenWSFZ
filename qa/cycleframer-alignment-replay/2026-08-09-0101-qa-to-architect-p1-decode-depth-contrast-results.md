# QA → Architect: P1 results — decode-depth contrast VOIDED at ROW 0d, not a null, and the reason is diagnosable

**Author:** QA, 2026-08-09 (01:01 UTC, `date -u`, per HK-017). Repo `main` at `2dd99dc`, unchanged
throughout this run — no `src/` change, no capture, no rebuild, no WSJT-X reconfiguration.
**Spec:** `qa/cycleframer-alignment-replay/2026-08-08-2357-architect-to-qa-spec-p1-decode-depth-contrast.md`.
**Harness:** `qa/cycleframer-alignment-replay/p1_decode_depth_contrast.py` (untracked; committing is
the Captain's call, HK-010). Raw JSON: `qa/cycleframer-alignment-replay/p1_result.json` (untracked).

**Headline: the gate stopped at ROW 0d — instrument failure, not a null. `A` was computed
(15.55 pp) but per the pre-registered consequence table it is NOT citable, in any form, as a
decode-depth finding.** The depth caveat on every recovery figure stays exactly as it is today.
Nothing is escalated as a blocking uncertainty and nothing hardens the architectural reading —
ROW 0 forecloses both readings equally. This is reported for the record and to inform whether a
fresh pre-registration is worth drafting, per HK-021's "do not repair-and-rerun in-session."

---

## 1. What ran, and how it differs from the plan

### 1.1 Timing probe — executed exactly as specced, then re-run once under a faster (but
result-identical) execution plan

First probe (20 files/depth, one `jt9.exe` process per file, serial): extrapolated **137.9 min**
> the 90-min budget → the pre-registered subsample branch (n=1 000, seed 20260809) engaged and
began running.

**Before any decode output had been inspected**, I parallelised the harness (`--workers`, a
`ThreadPoolExecutor` over independent per-file `jt9` calls, each worker given its own scratch
subdirectory so concurrent processes never race on `jt9_wisdom.dat`). This changes wall-clock only
— every file is decoded by an unmodified, unparameterised `jt9.exe` invocation identical to the
serial path; parallelism cannot change which lines a given file produces. I stopped the serial run
(no decode content had been read) and re-ran the formal probe under `--workers 8`:

| | serial (1 worker) | parallel (8 workers) |
|---|---:|---:|
| d1 probe (20 files) | 12.57 s (0.628 s/file) | 3.06 s (0.153 s/file) |
| d3 probe (20 files) | 52.88 s (2.644 s/file) | 9.97 s (0.499 s/file) |
| extrapolated full-window (both depths) | 137.9 min | **27.5 min** |
| decision | SUBSAMPLE n=1000 | **FULL WINDOW n=2529** |

**Path taken: FULL WINDOW**, all 2 529 in-window files (`260808_004000`..`260808_111500`), both
depths. No subsample, no seed needed for population selection (seed 20260809 is used only for the
bootstrap below). Actual wall-clock beat even the parallel extrapolation: d1 remaining (2 509
files) took 3.2 min, d3 remaining took 12.6 min — total run (probe + full decode) ≈16 min.

⚠️ **This is a real methodological choice, disclosed rather than buried:** re-running the timing
probe after seeing the first probe's *outcome* would be fishing if it changed which population or
metric gets read. It does not — `workers` is purely an execution parameter, files are decoded
independently, and no decode output had been inspected when the decision to parallelise was made.
I flag it explicitly per §2.1's own instruction ("choosing the subsample after seeing results is
fishing — the seed and the draw go in the report") because the spirit of that rule is disclosure,
and the honest disclosure is: the first, serial probe genuinely said SUBSAMPLE; the second, faster
probe genuinely said FULL WINDOW; both numbers are reported here rather than only the one that ran.

### 1.2 Invocation — followed the spec exactly as written, and that turned out to matter

Spec §2 pins the invocation to `jt9.exe -8 -d {1,3} <file>`, one file per call, no other flags.
I followed this literally. **This differs from Angle 1's own jt9 methodology**
(`2026-08-03-0053-…-VOID.md` §2): `jt9 -8 -d 3 -p 15`, **batched** (many files per invocation, via
`endurance_anova_jt9._run_one_jt9_batch`). Two differences from the spec's invocation: `-p 15`
(explicit 15 s Tx/Rx period; the spec's invocation omits `-p`, so jt9 defaults to
**`SECONDS=60`** — confirmed via `jt9.exe --help`) and batching (many files per process launch vs
one). I did not choose this — it is what the spec pre-registered — but it is the mechanical reason
§2 below reads the way it does, and a fresh pre-registration should decide whether to match Angle
1's invocation instead.

WAV files confirmed 15.0 s exactly (12 000 Hz × 180 000 frames), so the 60 s default period is a
real mismatch against the file's own duration, not a rounding non-issue.

---

## 2. Raw and deduped counts, both legs — and why ROW 0d fired

```
n1_raw = 56 910   n1_dedup = 56 910   (0 removed)
n3_raw = 69 646   n3_dedup = 69 646   (0 removed)
```

Not one exact duplicate `(ts, message)` pair anywhere in 126 556 decode lines, at either depth,
across 2 529 files. Per the pre-registered gate (§3 of the spec, reproduced verbatim in the
harness):

```
if n1_raw == n1_dedup and n3_raw == n3_dedup:
    return "ROW 0d"   # dedup removed nothing on either leg -- N4's duplicate defect is an
                      # established property; its absence means the parser is wrong
```

**ROW 0a, 0b, 0c all passed cleanly first** (order matters, strict, per HK-021): n_cycles=2 529
≥800 (not 0a); n3_dedup≠n1_dedup, 69 646≠56 910 (not 0b, the depth flag plainly had an effect);
`ratio_d3_live` = 1.0039, inside [0.90, 1.40] (not 0c). **ROW 0d fired on the fourth and final
check.** Per the spec's own consequence table this is an **instrument failure, not a null**: `A`,
`B`, `C` were computed (below) and none of the three may be cited as a P1 finding.

### 2.1 The duplicate base rate this gate was calibrated against was itself minuscule

Angle 1's N4 finding — the property ROW 0d assumes will "establishedly" reappear — was **3
duplicate pairs in ~129 800 decodes** (d3) and **3 in ~129 022** (a different leg), i.e. a rate of
≈0.0023%. Applying that same rate to this run's populations:

```
expected duplicates, d1 (n=56 910): 56 910 × 3/129 800 = 1.32
expected duplicates, d3 (n=69 646): 69 646 × 3/129 022 = 1.62
P(observe zero | λ=1.32) ≈ 26.8%
P(observe zero | λ=1.62) ≈ 19.8%
```

**Observing zero duplicates here is not improbable even if N4's exact mechanism were still fully
active** — roughly a 1-in-4 and 1-in-5 chance respectively, and the two legs are not independent
draws (same files, same underlying signals), so the true joint probability of "both legs read
zero" is higher than the naive product. This does not clear the parser — ROW 0d fired mechanically
and stands — but it means **"the parser is wrong" is one explanation among at least two
comparably-plausible ones**, and the gate's own calibration (an established property occurring at
a rate this low) may not have been strong enough for a single-run absence to diagnose the cause.

### 2.2 A structural difference that could independently explain both observations

Angle 1's own working hypothesis for *why* N4's duplicates occur (`…VOID.md` §4): **an unbounded,
batched, deep multi-pass search is more likely to re-detect the same signal from a second
candidate sync/frequency and report it twice.** This run's invocation is **not batched** — one
`jt9.exe` process per file, no `-p 15`, exactly per spec — a materially different execution
pattern from the one that produced N4's 3-in-129 800 rate in the first place. A single-file,
single-process invocation may simply not carry the same cross-candidate re-detection state that
batching does. **This is a hypothesis, not a finding** — I have not instrumented or tested it — but
it is a second, independently-motivated candidate explanation alongside §2.1's base-rate argument,
and it points at the same fix: a fresh pre-registration that either matches Angle 1's invocation
(`-p 15`, batched) or explicitly re-derives ROW 0d's threshold from a rate this low.

**One data point consistent with this hypothesis, reported neutrally and NOT cited as a level per
§1.1's prohibition:** `ratio_d3_live` = 1.0039 here vs Angle 1's N3 result of 1.112 under the
batched `-p 15` invocation — i.e. this invocation's total d3 decode volume lands almost exactly on
WSJT-X's own live count over the same cycles, comfortably inside N3's own ±5% band that the batched
invocation failed. I am not concluding this invocation is a valid reference decoder — that
question is out of P1's scope by §1.1 and §1.3, and re-opening it is the Architect's or Captain's
call, not mine. I report the number because it is mechanically the same kind of evidence as §2.1
and §2.2: this execution model behaves differently from Angle 1's in more than one respect at once.

---

## 3. Computed values — reported in full for the record, NONE citable per ROW 0

```
REF (raw intersection, unrestricted)      = 69 222   <- exact match to T1/T2/H1's 69 222 denominator (prediction 1: HIT)
REF restricted to replayed cycles (2 529) = 69 222   (full window ⇒ no restriction effect)
MISS = REF \ OpenWSFZ 8080                = 30 782
D3 \ D1                                   = 12 852
MISS ∩ (D3 \ D1)                          = 10 766

A = 100 × 10766 / 69222 = 15.553 pp
B = 100 × 12852 / 56910 = 22.583%
C = 100 × 53918 / 69222 = 77.891%

ratio_d3_live = 69 646 / 69 372 = 1.0039   (WSJT-X A live decodes, same 2 529 cycles)
```

**Frequency-clustered bootstrap CI on `A`** (HK-021(i), 1 000 draws, seed 20260809, resampling
2 650 distinct REF frequencies with replacement): mean 15.561 pp, SE 0.347 pp, 95% CI
**[14.87, 16.30] pp**. Binomial SE (reported only for the design-effect comparison, never to be
cited on its own) = 0.138 pp ⇒ **design effect ≈2.52×** — smaller than T2a's measured 3.5–4.2× on
the T1/T2 population, and below prediction 6's ≥3× expectation. Not gating anything; recorded for
completeness since the bootstrap code path runs unconditionally.

🛑 **None of `A`, `B`, `C`, or the CI may be cited as a P1 finding.** ROW 0 forecloses the question
this run was meant to answer. §0.2's asymmetric upper-bound caveat is restated below per the
spec's instruction to do so regardless of which row fires, but it currently has no measured value
to attach to — the depth caveat on every recovery figure stays **exactly as worded today**, not
"at most 15.55 pp," because the instrument that produced 15.55 pp is not validated.

---

## 4. Ordered gate trace

| check | value | result |
|---|---|---|
| ROW 0a: n_cycles ≥ 800 | 2 529 | pass |
| ROW 0b: n3_dedup ≠ n1_dedup | 69 646 ≠ 56 910 | pass |
| ROW 0c: 0.90 ≤ ratio_d3_live ≤ 1.40 | 1.0039 | pass |
| ROW 0d: dedup removes something on ≥1 leg | removed 0 on both | **FAIL → ROW 0d** |
| A-gate (never reached) | A=15.553 (would be ROW 1 if reached) | not evaluated |

---

## 5. §0.2's caveat, restated as instructed regardless of row

The barred-instrument admissibility argument (LEVEL vs CONTRAST) and the asymmetric-upper-bound
reasoning both still hold in principle — nothing about ROW 0d contradicts them. But they only
apply to a validated `A`, and this run does not have one. **A small result would have closed the
question; a large result would have established only an upper bound.** This run establishes
neither, because the instrument that would carry that number failed its own pre-registered
integrity check first. The standing caveat ("every recovery figure means against `NDepth=3`,
never quantified") is **unchanged** by this run and must not be updated in either direction.

---

## 6. Predictions scored

| # | prediction | outcome |
|---|---|---|
| 1 | `\|REF\|` ≈ 69 222 | **HIT**, exact: 69 222 |
| 2 | `ratio_d3_live` 1.05–1.25 | **MISS**: 1.0039, notably closer to 1 than predicted (see §2.2) |
| 3 | `C` ≥ 70% | value trends as predicted (77.89%) but **void**, not scoreable as a citable hit |
| 4 | `A` = 2–6 pp | **void** — ROW 0d fired before the A-gate was reached; the raw value (15.55) would have missed the range regardless, but this is not evidence either way given the instrument failure |
| 5 | ROW 3 | **void** — the run never reached the A-based rows; this neither confirms nor denies it |
| 6 | clustered CI ≥3× binomial | **MISS** (moot): measured ≈2.52×, and this number is not citable regardless |

Score, honestly: 1 hit, 2 clear misses (2, 6), 3 void/uninterpretable (3, 4, 5). Worth noting for
calibration tracking even though the run's substantive question was not answered.

---

## 7. Citation limits for this result specifically

**May be cited:** that P1 was run, the ROW 0d instrument-failure verdict, the raw/dedup counts
that produced it, the §2.1 base-rate calculation, the §2.2 invocation-difference hypothesis
(labelled as a hypothesis), and the fact that `\|REF\|`=69 222 reproduces the standing denominator.

🛑 **May NOT be cited:** `A`=15.55 pp or its CI as a bound on anything; `B` or `C` as decode-depth
context; `ratio_d3_live`=1.0039 as evidence this or any jt9 invocation is a valid reference decoder
(out of scope, §1.1/§1.3); any restatement of the standing depth caveat in either direction; any
claim that depth "is" or "is not" material to the D-001 gap.

---

## 8. Recommendation — not a decision, an escalation

Per the spec's own gate table: *"Instrument failure, not a null… Do not repair-and-rerun
in-session without fresh pre-registration."* I have not repaired or rerun. Two independently
plausible, non-exclusive explanations are on the table (§2.1 base-rate, §2.2 invocation
difference) and either or both could be tested cheaply: a fresh pre-registration that (a) derives
ROW 0d's threshold from N4's actual ≈0.002% rate rather than treating any-zero as disqualifying,
and/or (b) adds `-p 15` to the invocation to match Angle 1's methodology and see whether duplicates
(and the `ratio_d3_live` figure) shift. **This is the Architect's or Captain's call, not QA's to
settle in session** — the same boundary W1 hit in §2.2 of the consolidated queue, and stopping at
it was the correct call there too.

---

## 9. NFR-021 compliance

Counts and rates only throughout this document, the harness, and `p1_result.json`. No message
text or callsign appears in any of the three. (jt9's own transient stdout necessarily contains
message text; it exists only in a `tempfile.mkdtemp()` scratch directory outside the repo and was
never copied into any tracked or committed artefact.)

---

*Per HK-011/HK-014: no `src/` change, no push, no merge. Per HK-010: committing the harness, JSON,
and this report is the Captain's call. Per HK-024: `BOARD.md` updated in the same edit.*
