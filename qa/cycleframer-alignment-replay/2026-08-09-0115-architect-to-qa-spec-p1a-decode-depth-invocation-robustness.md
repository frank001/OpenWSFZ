# Architect → QA: spec P1a — is `A = 15.55 pp` real, or an artefact of the invocation I pinned?

**Author:** Architect, 2026-08-09 (01:15 UTC, from `date -u`, per HK-017). Repo `main` at `c4784c1`.
**Status:** offline replay of WAVs already on disk. No `src/` change, no capture, no rebuild, no
Developer session, nothing to reconfigure in WSJT-X.
NFR-021: counts and rates only — **no message text or callsign in output, report, or harness.**
**Supersedes:** `2026-08-08-2357-architect-to-qa-spec-p1-decode-depth-contrast.md` (P1, VOIDED at
ROW 0d). P1's §0, §0.1, §0.2, §1 and §2.2 carry over **unchanged** and are not restated here — read
that document first, then this one.

---

## 0. Why this exists

P1 ran correctly and voided on **my drafting defect, not QA's execution.** Two errors, and they
compound:

**Defect 1 — ROW 0d was a coin flip.** I required Angle 1's N4 duplicate property to reappear,
calling it "established." Its actual rate was **3 duplicates in ~129 800 decodes (≈0.0023%)**, so
this population expects λ ≈ 1.32 (d1) and 1.62 (d3), and **P(observe zero) ≈ 27% and 20%.** I built
a ROW 0 with a ~1-in-4 false-failure rate. QA computed this in four lines of Poisson arithmetic in
§2.1 of the result; HK-021's standing instruction — *draft the gate by writing the code that
evaluates it* — would have caught it before the run.

**Defect 2 — I pinned an invocation with no reason to produce what Defect 1 demanded.** Spec §2
fixed `jt9.exe -8 -d {1,3} <file>`: one process per file, **no `-p`**. Angle 1's N4 duplicates came
from a *batched* invocation with `-p 15`. QA's §2.2 hypothesis — that batched deep multi-pass search
is what re-detects a signal twice — is structurally plausible and independently motivated.

Together these made ROW 0d **uninformative in both directions.** It did not show the parser was
wrong. It showed nothing.

### 0.1 🔴 THIS RUN IS NOT BLIND — mandatory disclosure, must appear in the report

**Both the Architect and QA have seen `A = 15.553 pp`, CI [14.87, 16.30], from the voided run.**
Prediction-scoring on `A` is therefore worthless here and is **suspended** — do not score it, do not
present it as calibration evidence. This is the same disclosure discipline the board applies to the
band-vs-density arm.

What remains **genuinely blind, and is the actual question:**

> **Does `A` survive a change of invocation?**

P1a is a **validity re-test, not a fresh measurement.** If `A` moves materially when the invocation
is corrected, the number was an instrument artefact and the depth question is still open. If it
holds, `A` is robust and can be read through P1's original gate for the first time.

### 0.2 🛑 What has NOT changed

P1 §0.2's asymmetry governs this run identically and **must be restated whichever row fires**:
offline jt9 has no ~15 s real-time budget, so **a small `A` CLOSES the question; a large `A`
establishes only an upper bound**, never that depth costs us that much. P1 §1.1's prohibition also
stands in full: **no jt9 count may leave the document as a level.** `F_dec = 1.2455` stays uncitable.

---

## 1. The parser check that ROW 0d should have been

There is a high-power integrity check available that P1 never used, and it is already satisfied by
the voided run's own numbers:

```
|D1 ∩ D3| = n3_dedup − |D3\D1| = 69 646 − 12 852 = 56 794
|D1 \ D3| = n1_dedup − |D1∩D3| = 56 910 − 56 794 =    116     →  0.204% of D1
```

**d1's output is a 99.8% subset of d3's.** That is a structural relationship between two
independently parsed streams; a broken stdout parser cannot fake it, and the ~0.2% leakage is the
right order for a deeper search occasionally reordering candidates. Expected count is in the tens of
thousands, so **absence of nesting is genuinely diagnostic** — which is exactly the property ROW 0d
lacked.

⚠️ Confirm in the harness that `D3\D1` is computed on the **identical `(ts, message)` key** as the
dedup counts before relying on this. It appears to be (`to_keyset`), but assert it.

**New HK-021 sibling this establishes — record it as (j):** *an absence-based check is only
diagnostic when the expected count makes absence surprising.* Require **λ ≥ 5** (P(zero) < 1%) before
absence may condemn an instrument; below that you are gating on noise. Compute λ while drafting.

---

## 2. Method — four legs, not two

The invocation question is a confound. **HK-021 forbids estimating a confound in prose — compute
it.** So measure it: run both invocations, both depths, on the identical file set.

| leg | invocation |
|---|---|
| `d1_default` | `jt9.exe -8 -d 1 <file>` |
| `d3_default` | `jt9.exe -8 -d 3 <file>` |
| `d1_p15` | `jt9.exe -8 -d 1 -p 15 <file>` |
| `d3_p15` | `jt9.exe -8 -d 3 -p 15 <file>` |

`_decode_one` already builds the argv list — this is a one-line parameterisation.

**Why `-p 15` is a correctness fix, not a thumb on the scale.** QA verified the WAVs are exactly
15.0 s (12 000 Hz × 180 000 frames) while jt9 with no `-p` defaults to **`SECONDS = 60`**. That is a
real mismatch against the file's own duration. It applies identically to both depths, so it is
common-mode for the contrast either way; correcting it removes an unexplained variable.

**Do NOT batch.** One process per file, as in P1. Batching is the leading suspect for N4's
duplicates and it entangles per-file attribution. The `-p` flag is the single variable under test.

**Population, window, `REF`/`MISS`, and `ALL.TXT` parsing are unchanged from P1 §2.2** — reuse
`t1_frequency_quantisation.load`, `WINDOW_20M`, `LEG_20M` so the populations are provably identical.
The in-window file count is **2 529** (the directory holds 2 748; the clean window is the subset —
state both in the report so the two numbers stop looking like a discrepancy).

**Cost.** P1's full window ran in ~16 min at `--workers 8`. Four legs ≈ 32 min. Comfortably inside
budget, so **no timing probe and no subsample branch this time** — run the full window
unconditionally. Record wall-clock.

### 2.1 Metrics

Compute `A`, `B`, `C` exactly as P1 §2.3, once per invocation:

```
A_default , A_p15        <- P1's headline metric under each invocation
ΔA = A_p15 − A_default   <- THE GATED QUANTITY for this run
```

### 2.2 🔴 The bootstrap must be PAIRED

Both invocations run on the same files, so `A_default` and `A_p15` are positively correlated and
**an unpaired CI on `ΔA` is wrong.** Within each bootstrap draw: resample distinct REF frequencies
with replacement **once**, then recompute *both* `A_default` and `A_p15` on that same resampled
cluster set, and take their difference. ≥1 000 draws, seed **20260809** (same as P1, recorded in
advance here). Report `SE(ΔA)`.

🛑 A binomial interval must not appear anywhere. P1 measured a design effect of **2.52×** on this
population; T2a measured 3.5–4.2× on T1/T2's. Recompute, do not assume.

---

## 3. Pre-registered gate (HK-021) — two stages, strict order

```python
def p1a_row0(n_cycles, dedup, nest_frac, a_default, se_delta):
    # dedup: {"d1_default":(raw,ded), "d3_default":..., "d1_p15":..., "d3_p15":...}
    # nest_frac: {"default": |D1\D3|/|D1|, "p15": ...}
    if n_cycles < 800:
        return "ROW 0a"        # too few cycles replayed to read anything
    if dedup["d3_default"][1] == dedup["d1_default"][1] \
       or dedup["d3_p15"][1] == dedup["d1_p15"][1]:
        return "ROW 0b"        # the depth flag had no effect on some leg: wrong invocation
    if max(nest_frac.values()) > 0.01:
        return "ROW 0c"        # d1 is not a ~subset of d3: the jt9 stdout parser is wrong
                               # (REPLACES P1's ROW 0d -- see section 1)
    if abs(a_default - 15.553) > 0.10:
        return "ROW 0d"        # the default leg failed to reproduce the voided run: the
                               # harness is non-deterministic and nothing here is readable
    if se_delta > 0.75:
        return "ROW 0e"        # the 1.5 pp bar below is no longer 3 sigma -- UNDERPOWERED,
                               # an instrument failure, NOT a null (HK-021(i))
    return None


def p1a_gate_validity(delta_a):          # stage 1 -- runs first
    return "V-ROW 1" if abs(delta_a) <= 1.5 else "V-ROW 2"


def p1a_gate_substantive(a_p15):         # stage 2 -- ONLY if stage 1 is V-ROW 1
    if a_p15 >= 5.0:
        return "ROW 1"
    if a_p15 <= 1.5:
        return "ROW 2"
    return "ROW 3"
```

**Derivation of the 1.5 pp bar, so it is not a chosen constant:** P1 measured a clustered
`SE(A) = 0.347 pp`. An *unpaired* difference would carry `√2 × 0.347 = 0.49 pp`; the paired
difference is smaller still. Treat **0.5 pp as the noise floor**, making 1.5 pp a **3σ** bar.
ROW 0e enforces that this derivation actually held once `SE(ΔA)` is measured.

| row | consequence — as an assertion |
|---|---|
| **ROW 0a–0e** | **Instrument failure, not a null.** Report the failing check and its value. The depth caveat stays exactly as it is today. **Do not repair-and-rerun in-session.** ROW 0e specifically means underpowered, which is *not* evidence that `ΔA` is zero. |
| **V-ROW 2** (`\|ΔA\| > 1.5`) | 🔴 **`A` is invocation-sensitive and therefore not a measurement of depth.** Report both values and the paired CI. **`A` remains uncitable in every form**, and the standing depth caveat stays **exactly as worded today**. Escalate to the Captain: the depth question needs an instrument whose answer does not move under a flag that should be common-mode. Do **not** proceed to stage 2. |
| **V-ROW 1 → ROW 1** (`A_p15 ≥ 5.0`) | **Depth is a material *upper bound* on the gap — and that is ALL it is (P1 §0.2).** 🛑 Do not restate any recovery figure; do not subtract `A` from the deficit. Assert into the board that the depth asymmetry needs a **time-budgeted** instrument before it can be priced, and that the sync-refinement build case cannot be sized until then. Escalate to the Captain as a blocking uncertainty, with `A_p15`, `ΔA`, and both clustered CIs. |
| **V-ROW 1 → ROW 2** (`A_p15 ≤ 1.5`) | 🔴 **CLOSE the depth question.** **Replace** the standing "every recovery figure is against `NDepth = 3`" caveat with the measured bound in the 1942 report §8 and on the board — **edit it, do not annotate** (HK-024, same edit). The architectural reading hardens and the case for building sync refinement is correspondingly stronger. |
| **V-ROW 1 → ROW 3** (`1.5 < A_p15 < 5.0`) | Report `A_p15` and its CI. **Keep the depth caveat but quantify it** — "at most `A_p15` pp." No restatement of any headline. |

---

## 4. Architect's recorded predictions

🔴 **Predictions on `A` are SUSPENDED per §0.1 — I have seen 15.553 and cannot predict it blind.**
Only the genuinely blind quantities are scored:

| # | prediction | tested by |
|---|---|---|
| 1 | `\|ΔA\|` = **0–1.5 pp** — the period flag is common-mode and does not move the contrast | stage 1 |
| 2 | **V-ROW 1** (invocation-robust) | stage 1 |
| 3 | nesting fraction ≤ **0.5%** on *both* invocations | ROW 0c |
| 4 | `A_default` reproduces 15.553 **exactly** (jt9 is deterministic per file) | ROW 0d |
| 5 | `ratio_d3_live` under `-p 15` moves **toward** Angle 1's 1.112 and away from 1.0039 | context only, not gated |

⚠️ **Calibration, quoted because this gate turns on my prediction (HK-021):** my categorical ROW
calls run **2 of 4**; my ranges run **3 of 5**, and **both range misses were too pessimistic about
how cleanly an effect separates.** Read prediction 1 as asymmetric and weight prediction 2 lightly.
Prediction 5 is deliberately ungated — it is the one that would corroborate QA's §2.2 hypothesis
about *why* N4's duplicates never appeared, and I do not want a side-observation steering a gate.

---

## 5. Deliverables

1. Harness: extend `p1_decode_depth_contrast.py` in place (`--invocation {default,p15,both}`), or
   fork to `p1a_invocation_robustness.py` — QA's call. Reuse T1's `load()` so `REF`/`MISS` are
   provably the same populations. Assert the `D3\D1` key identity from §1.
2. Report `…-qa-to-architect-p1a-decode-depth-invocation-robustness-results.md`, filename and byline
   from real `date -u` and in agreement (HK-017), containing: **§0.1's non-blind disclosure,
   prominently**; wall-clock; raw/dedup counts for all four legs; nesting fractions; `A`, `B`, `C`
   per invocation; `ΔA` with its **paired clustered** CI and `SE(ΔA)`; the ordered gate trace
   (ROW 0a→0e, then stage 1, then stage 2); the blind predictions scored; **P1 §0.2's upper-bound
   caveat restated whichever row fires**; citation limits.
3. If **V-ROW 1 → ROW 2** fires, the §3 edits to the 1942 report §8 and `BOARD.md`, **same edit**
   (HK-024).
4. **No push, no merge, no `src/` change, no WSJT-X reconfiguration.** Committing is the Captain's
   call (HK-010/HK-014).

## 6. Citation limits set in advance

**May be cited:** `ΔA` and the validity verdict; `A_p15` **only if stage 1 returns V-ROW 1**, and
then **always as an upper bound with its clustered CI**; `B`, `C` as context; the gate row; the
nesting fractions as parser evidence.

🛑 **May not be cited:** any jt9 decode count as a level or reference (P1 §1.1); `A_default` = 15.55
as anything at all — it stays void, and reproducing it under ROW 0d is a *determinism check*, not a
rehabilitation; `A_p15` if stage 1 returns V-ROW 2; `A` as "the amount depth costs us" rather than
"at most"; `A` subtracted from the 42% deficit or the 57.8% recovery figure; any binomial interval;
any restatement of `G`, `D_int`, `U`, `M`, or the recovery headline.

---

# AMENDMENT 1 — 2026-08-09 10:56 UTC (Architect)

Made **before P1a was run**, on the basis of two mechanical pre-flights. **The spec's premise was
wrong and would have produced a FALSE PASS.** Recorded here rather than silently edited.

## A1.1 🛑 `-p 15` IS INERT FOR FILE DECODING — the specced contrast was vacuous

Measured directly, `jt9 -8 -d 3` over the same 5 in-window WAVs:

| invocation | decodes |
|---|---|
| (no `-p`) | **193** |
| `-p 15` | **193** |
| `-p 30` | **193** |
| `--bogusflag` | **0** |

The bogus flag returning 0 proves argv **is** reaching jt9 and being parsed. `-p` simply has no
effect when jt9 decodes files — it governs live T/R period, not file input.

🔴 **Consequence: `ΔA` would have been exactly 0 by construction, and stage 1 would have returned
V-ROW 1 "invocation-robust" — falsely rehabilitating `A` = 15.55.** A gate that cannot fail is worse
than no gate. This is the **third** gate-design defect in this thread and again it is mine; what
differs is that a mechanical pre-flight caught it *before* the run, which is HK-021(j) working as
intended.

## A1.2 🛑 QA's §2.2 batching hypothesis is REFUTED — neither invocation makes duplicates

40 in-window WAVs, depth 3, per-file vs Angle-1-style batched (`-p 15`, many files per process):

| invocation | raw | unique | **duplicate `(ts, message)` pairs** |
|---|---|---|---|
| per-file | 1 532 | 1 532 | **0** |
| batched | 1 707 | 1 707 | **0** |

**Neither produces duplicates.** So the absence of duplicates in P1 is **not** explained by the
invocation. **§2.1's base-rate argument now stands alone and unopposed**: at N4's ≈0.0023% rate a
2 529-file run expects λ ≈ 1.3–1.6, and observing zero is ordinary. P1's ROW 0d was simply a badly
calibrated gate — nothing more exotic.

## A1.3 ✅ What replaces the contrast: PER-FILE vs BATCHED

Batching is **not** inert — it yields **+11.4%** more decodes (1 707 vs 1 532). That is a real
invocation sensitivity and it is the one worth gating on. ⚠️ **Unplanned observation, flagged as
hypothesis-generating only and NOT a finding:** +11.4% sits suspiciously close to the **+11.2%**
overshoot the barred-instrument note attributes to `jt9 -d3` versus WSJT-X. If Angle 1's overshoot
was a *batching* artefact rather than a depth artefact, that reframes the bar itself — **out of
scope here, do not chase it in this arm, record it for a future pre-registration.**

**Revised legs:** `{d1, d3} × {per-file, batched}`, batch size **150** to match Angle 1's
`JT9_BATCH_SIZE` exactly (`qa/endurance/endurance_anova_jt9.py:127`). Batch size is a free
parameter and is therefore **pinned to the historical value, not chosen** (HK-021(d)).

**Everything else in §3's gate stands unchanged**, with `A_p15` reading as `A_batched`:
`ΔA = A_batched − A_perfile`, stage 1 at `|ΔA| ≤ 1.5 pp`, ROW 0c nesting, ROW 0d determinism
against 15.553, ROW 0e underpowered at `SE(ΔA) > 0.75`, paired clustered bootstrap.

## A1.4 Predictions — re-recorded, and the earlier set is void

Predictions 1, 2 and 5 in §4 referred to `-p 15` and are **void** (the flag does nothing). Replacing
them, recorded before the batched leg runs:

| # | prediction | tested by |
|---|---|---|
| 1' | `\|ΔA\|` = **1.0–5.0 pp** — batching moves decode volume ~11%, so it will move `A` materially | stage 1 |
| 2' | **V-ROW 2** (invocation-SENSITIVE) — i.e. I now expect `A` to fail its validity test | stage 1 |
| 3' | nesting ≤ 0.5% on both invocations | ROW 0c |
| 4' | `A_perfile` reproduces 15.553 exactly | ROW 0d |

⚠️ Calibration unchanged and still binding: categorical ROW calls **2 of 4**, ranges **3 of 5**, both
range misses too *pessimistic*. Prediction 2' reverses my original V-ROW 1 call — **the reversal is
evidence-driven (the +11.4% measurement), and it is recorded here before the run rather than
adjusted afterward.**
