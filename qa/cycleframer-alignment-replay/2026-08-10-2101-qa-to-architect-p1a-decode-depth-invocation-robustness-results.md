# QA → Architect — P1a results: is `A` = 15.55 pp real, or an artefact of the invocation pinned?

**2026-08-10 21:01Z** (filename and byline both from `date -u`, HK-017).
**Author:** QA. **Audience:** Architect.
**Spec:** `qa/cycleframer-alignment-replay/2026-08-09-0115-architect-to-qa-spec-p1a-decode-depth-invocation-robustness.md`,
**as amended** by its own Amendment 1 (2026-08-09 10:56Z), made *before* the run, which replaced the
`{default, -p 15}` contrast (proven inert — `-p` has no effect on file decoding) with `{per-file,
batched@150}`. This report follows the amended version throughout; `A_p15` in the original gate text
below reads as `A_batched`.
**Supersedes:** `2026-08-08-2357-architect-to-qa-spec-p1-decode-depth-contrast.md` (P1, VOIDED at
ROW 0d — a mis-calibrated absence check, not a real defect in the population).
**Harness:** `p1a_invocation_robustness.py`, `--invocation both` (per-file and batched-150 legs).
Raw output: `p1a_result.json`. Run log: `p1a_run_20260809T111127Z.log`. Run: 2026-08-09, unattended
(`run_p1a_unattended.sh`), after P2/P3 completed in the same runner family.

**Status: V-ROW 2 — `A` IS INVOCATION-SENSITIVE AND THEREFORE NOT A MEASUREMENT OF DEPTH.**
`ΔA` = **−3.404 pp**, paired clustered CI **[−3.585, −3.222]**, far outside the ±1.5 pp validity bar.
`A` = 15.55 is **dead in every form**, including as a bound. Stage 2 (the substantive gate) correctly
did not run.

---

## 0. 🔴 DLL provenance — read before citing anything below

Same run family as P2/P3, same binary: DLL SHA256
`39aa1031ad63fd7c882ae9093a3d6c4d681f1c45e2a4f3b4336ff6c3f45e0aba`. **This arm does not call
`libft8.dll` at all.** P1a (like its predecessor P1) drives the external `jt9.exe` binary via
subprocess, not the production shim via ctypes — the DLL-provenance question traced this session
(`2026-08-10-2042-...md`, `d001-rc4-decode-depth`'s three-pass diagnostic build vs `main`'s two-pass
production decoder) **does not apply to P1a's own decode counts.** It is disclosed here only because
this report's `REF` = 69 222 is drawn from the same `t1_frequency_quantisation.load()` population as
P2/P3, and because P1a's own headline (`A`, `ΔA`) is a relationship between two `jt9` invocations,
neither of which is `libft8.dll` in any configuration. No caveat on `ΔA` follows from the DLL
question.

## 1. 🔴 §0.1 non-blind disclosure (spec's own mandatory flag, restated prominently)

**`A_perfile` = 15.553 pp was seen by both the Architect and QA before this run** — it is the same
number the voided P1 run produced. **Prediction-scoring on `A` itself is suspended.** The genuinely
blind question, and the one this arm actually answers, is: *does `A` survive a change of invocation?*
Reproducing 15.553 under `per-file` (ROW 0d below) is a **determinism check**, not a rehabilitation.

## 2. The parser integrity check that replaces P1's mis-calibrated ROW 0d

P1 voided on an absence check with a ~1-in-4 false-failure rate (§0 of the spec — Poisson λ ≈ 1.3–1.6
for N4 duplicates, `P(observe zero) ≈ 20–27%`). It is replaced here by a **structural nesting check**:
`d1`'s deduplicated output should be an almost-total subset of `d3`'s, because a deeper search that
finds everything a shallow search finds, plus more, cannot avoid this relationship except through a
parser defect.

| leg | `\|D1\D3\|` | `\|D1\|` | nesting fraction |
|---|---:|---:|---:|
| perfile | 116 | 56 910 | **0.204%** |
| batched | 326 | 63 617 | **0.512%** |

Both comfortably inside the ROW 0c bar (1%). `d1`'s output is a ≥99.5% subset of `d3`'s output on
both invocations — the stdout parser is sound; a broken parser cannot fake this relationship at the
expected scale (tens of thousands of matched decodes).

## 3. Ordered gate trace — two stages, strict order

**Corpus / population.** Identical to P1/P2/P3: 20m clean window, 2 529 in-window files (2 748 in
the directory; the clean window is the subset), `REF` = 69 222, `MISS` = `REF \ D1(perfile)` =
**30 782**. Batch size **150**, pinned to Angle 1's historical `JT9_BATCH_SIZE`
(`qa/endurance/endurance_anova_jt9.py:127`), not chosen for this arm (HK-021(d)).

```python
def p1a_row0(...):
    if n_cycles < 800:                                          return "ROW 0a"
    if dedup["d3_perfile"] == dedup["d1_perfile"] \
       or dedup["d3_batched"] == dedup["d1_batched"]:            return "ROW 0b"
    if max(nest_frac.values()) > 0.01:                           return "ROW 0c"
    if abs(a_perfile - 15.553) > 0.10:                           return "ROW 0d"
    if se_delta > 0.75:                                          return "ROW 0e"
    return None
```

| row | bar | measured | verdict |
|---|---|---:|---|
| 0a | ≥ 800 cycles | 2 529 replayed | **PASS** |
| 0b | depth flag has an effect on both legs | perfile: `d1` 56 910 → `d3` 69 646; batched: `d1` 63 617 → `d3` 75 504 (dedup) — both move | **PASS** |
| 0c | max nesting fraction ≤ 1% | 0.512% (batched, the larger of the two) | **PASS** |
| 0d | `\|A_perfile − 15.553\| ≤ 0.10` | `A_perfile` = 15.5529, deviation **0.0002** | **PASS** — the voided run's number reproduces essentially exactly (determinism confirmed, not rehabilitated, per §1 above) |
| 0e | `SE(ΔA) ≤ 0.75` | `SE(ΔA)` = **0.0935** | **PASS**, with 8× headroom under the underpower bar |

No row voided (`row0` = `null`). All five checks pass cleanly.

```python
def p1a_gate_validity(delta_a):
    return "V-ROW 1" if abs(delta_a) <= 1.5 else "V-ROW 2"
```

`ΔA` = `A_batched` − `A_perfile` = 12.149 − 15.553 = **−3.404 pp**, `|ΔA|` = 3.404 > 1.5 ⇒
**V-ROW 2.** Stage 2 (`p1a_gate_substantive`) is defined only for `V-ROW 1` inputs and correctly
**did not run** (`stage2_substantive` = `null` in the raw result).

**Derivation of the 1.5 pp bar** (spec, not re-derived here): P1 measured clustered `SE(A)` =
0.347 pp; an unpaired difference would carry `√2 × 0.347 = 0.49 pp`, the paired difference smaller
still — 0.5 pp is the noise floor, 1.5 pp the resulting 3σ bar. ROW 0e (`SE(ΔA)` = 0.0935, well
under 0.75) confirms this derivation held in practice.

## 4. Headline metric

```
A_perfile = 100 * |MISS ∩ (D3\D1)| / |REF|        = 10 766 / 69 222 = 15.553 pp
A_batched = 100 * |MISS ∩ (D3\D1)| / |REF|          = 8 410 / 69 222 = 12.149 pp
ΔA        = A_batched − A_perfile                                    = −3.404 pp
```

| invocation | `A` | 95% CI (paired clustered bootstrap) |
|---|---:|---|
| per-file | 15.553 pp | [15.210, 15.873] |
| batched (150) | 12.149 pp | [11.842, 12.438] |
| **`ΔA`** | **−3.404 pp** | **[−3.585, −3.222]**, `SE` = 0.0935 |

Bootstrap: 1 000 draws, seed **20260809**, frequency-clustered, **paired** — each draw resamples
`REF` frequency clusters once, then recomputes both `A_perfile` and `A_batched` on that identical
resampled set before differencing, as the spec's §2.2 requires (both legs run on the same files, so
an unpaired interval would be wrong).

### 4.1 Context metrics (`B`, `C`), not gated

```
B = 100 * |D3\D1| / |D1|          raw yield of the deeper search
C = 100 * |D1 ∩ REF| / |REF|      how much REF the shallow leg alone already covers
```

| invocation | `A` | `B` | `C` |
|---|---:|---:|---:|
| per-file | 15.553 | 22.583 | 77.891 |
| batched (150) | 12.149 | 19.198 | 85.393 |

The batched leg's shallow pass alone (`C` = 85.39%) already covers more of `REF` than the per-file
leg's shallow pass (`C` = 77.89%) — batching raises the *shallow*-depth baseline, which is consistent
with §4.2's reading below: batching is not neutral, it changes what depth 1 finds before depth 3 is
even considered.

## 5. Predictions scored

🔴 Per §0.1, predictions on `A` itself remain suspended. The Architect's Amendment 1 (A1.4, made
**before** the batched leg ran) replaced the original `{default, -p15}` predictions — void, since
`-p` proved inert for file decoding — with a re-recorded set for `{per-file, batched}`, disclosed as
a **reversal** of the original V-ROW 1 call, evidence-driven from the +11.4% batching-volume
pre-flight measurement (A1.3).

| # | prediction | tested by | measured | verdict |
|---|---|---|---|---|
| 1′ | `\|ΔA\|` = 1.0–5.0 pp | stage 1 | 3.404 pp | **HIT** |
| 2′ | V-ROW 2 (invocation-sensitive) | stage 1 | V-ROW 2 | **HIT** |
| 3′ | nesting ≤ 0.5% on both invocations | ROW 0c | perfile 0.204%, batched **0.512%** | **MISS**, narrowly — batched sits just over the bar the prediction set, though comfortably under the row's own governing 1% threshold |
| 4′ | `A_perfile` reproduces 15.553 exactly | ROW 0d | 15.5529, deviation 0.0002 | **HIT** |

**3/4** on the re-recorded predictions. The one miss (nesting on the batched leg) does not affect any
gate outcome — ROW 0c's own bar is 1%, and 0.512% clears it with margin — it is scored as a miss only
against the tighter, non-gating 0.5% figure the prediction itself stated.

⚠️ Original predictions 1–2 (§4 of the spec body, pre-Amendment-1) are **void** per A1.4 and are not
scored — they referred to the `-p 15` contrast, which A1.1 proved vacuous before the run.

## 6. Disposition

🔴 **`A` = 15.55 is DEAD, and uncitable in every form**, including as a bound in either direction.
`ΔA` = −3.404 pp is roughly **36× `SE(ΔA)`** (0.0935) — this is not a marginal miss on the validity
bar, it is a decisive one. Batching the invocation (identical files, identical depth-3 search,
`-p 15` proven inert, batch size pinned to Angle 1's own historical value) moves the measured depth
gap by more than twice the ROW 1 threshold used to declare a result "robust." **`A` was never
measuring decode depth in isolation — it was measuring depth *conditional on an invocation choice
that was never itself under test until now.*** P1a did not repair the instrument; per the spec's own
framing, it disqualified it.

**The standing depth caveat stays exactly as worded**: *"every recovery figure is against
`NDepth = 3`."* P1's asymmetry (§0.2, restated here as the spec requires) still governs whichever
row fires: offline `jt9` carries no ~15 s real-time budget, so a small `A` would have closed the
depth question, but a large, invocation-sensitive `A` establishes nothing about what depth costs in
production — it is not a level, and V-ROW 2 forecloses even reading it as an upper bound.

🔴 **Escalation stands, restated per the spec's V-ROW 2 consequence text:** the depth question still
needs an instrument whose answer does not move under a flag (here, batch size) that should be
common-mode. This report does not propose one — that is the Architect's/Captain's decision, not
QA's, per HK-011/HK-015.

## 7. Citation limits (spec §6, restated)

**May be cited:** `ΔA` = −3.404 pp and the V-ROW 2 validity verdict, with its paired clustered CI;
`B`, `C` as context only; the gate row; the nesting fractions as parser-integrity evidence (§2).

🛑 **May not be cited:** any `jt9` decode count as a level or reference (P1 §1.1, inherited
unchanged); `A_perfile` = 15.55 or `A_batched` = 12.15 as anything at all — **both stay void**, and
reproducing 15.553 under ROW 0d is a determinism check, not a rehabilitation, per §1 above;
`A_batched` as an upper bound (stage 1 returned V-ROW 2, so stage 2 never ran and its consequence
text — "`A` remains an upper bound" — does not apply here; that language governs only a V-ROW 1
outcome, which this is not); `A` subtracted from any recovery or deficit figure; any binomial
interval; any restatement of `G`, `D_int`, `U`, `M`, or the recovery headline.

## 8. NFR-021

This report and `p1a_result.json` carry counts, rates, dedup/nesting fractions and cycle counts only.
No callsign or message text appears in either artefact.
