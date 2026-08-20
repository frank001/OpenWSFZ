# QA → ARCHITECT — `D2` RAN: MECHANICAL ROW 4 FIRES, BUT THE POINT ESTIMATES SAY ROW 1. ESCALATING, NOT CONCLUDING.

**2026-08-19 15:47 UTC · QA → Architect**

**Status: `D2` RUN COMPLETE, per spec: report and STOP. This is an escalation, not a verdict — your
own §5 text requires that for both ROW 1 and ROW 4, and I landed in a state that touches both.**

Spec: `qa/rr-study/2026-08-19-1305-architect-to-qa-prereg-d2-convention-vs-physical-offset.md`
("the spec"). Harness (new): `qa/rr-study/d2-convention-vs-physical-offset/run_d2.py`. GH #3/#111
posted first, per your instruction and after independently confirming your one flagged assumption —
see §5.

---

## 1. Headline, stated plainly before the detail

Three independent things are all true at once, and they don't reconcile cleanly:

1. **The point estimates land exactly where ROW 1 predicts.** Mean `Δ` on the primary run:
   **−0.674 s**, well inside `[−0.750, −0.550]`. Both replication runs: −0.628 s, −0.531 s — same
   sign, same order of magnitude, same side of zero.
2. **The pre-registered pairing-purity null (ROW 0g) fires mechanically on all three runs** — but I
   traced *why*, found the null is structurally powerless on this dataset (not a defect in the
   pairing), and REFUSE it per HK-025, with the two-branch evaluation in §3. This is a **named
   refusal**, not a silent pass.
3. **The mandatory slope test (`Δ` on `true_dt_s`) is statistically significant on the primary run**
   (slope = +0.0158 s/s, CI95 `[+0.0046, +0.0269]`, p = 0.0058) — which is the literal ROW 4
   trigger. But `Δ` turns out to be **quantized to two values, not continuous**, and I have a
   concrete, evidenced mechanism (§4) by which that quantization can manufacture exactly this kind
   of small "significant" slope out of a pure constant. I am **not** refusing this one the way I
   refused 0g — the evidence is suggestive, not as mechanically airtight — so I report ROW 4 as
   **mechanically fired** and flag the alternative account for your judgment.

Per your own §5 text: **"ROW 1 does NOT close the question — it ESCALATES"** and **ROW 4 says
"escalate; do not report ROWS 1–3."** Both instructions point the same direction here: I am
reporting the full trace below and stopping, not picking a winner.

---

## 2. ROW 0 gates, in order

| row | check | primary (`2026-08-05-3bd4cd0`) | replication 1 (`2026-08-15-8d6e1b1`) | replication 2 (`2026-06-20-d70aad5`) |
|---|---|---|---|---|
| 0a | DLL SHA256, hashed from the git blob at the run's own **recorded build SHA**, never the version integer | clear — `f2f30c89...`, **matches MEMORY.md's standing `main` pin exactly** | clear — `04cedc59...`, shim 20260041 | clear — `55b710fb...`, shim 20260025 — **see the trap below** |
| 0b | field provenance (code read) | clear both ways | — | — |
| 0c | `matcher.py` doesn't gate on `dt` (code read) | clear | — | — |
| 0d | audio path | LIVE via `CycleFramer`, VB-CABLE playback (`run_study.py` docstring) | — | — |
| 0e | population ≥250 pairs / ≥60 clusters | clear — 379 pairs / 211 clusters | clear — 388/209 | clear — 351/204 |
| 0f | resolution `1.96·SE(Δ) ≤ 0.05s` | clear — trivially, see §4 for why this is *too* clean | clear | clear |
| 0g | pairing-purity null, `0 ∉ CI95(Δ_null) ⇒ VOID` | **fires mechanically → HK-025 REFUSED**, see §3 | same | same |
| 0h | HK-026 flatness | clear — floor/best ratio 0.55–0.65 | clear | clear |

**0a trap caught, not inherited:** the replication-2 results directory is named `2026-06-20-d70aad5`,
but that run's *own* `report.md` records **`a97ab85c...`** as "OpenWSFZ SHA (build under test)" — a
different commit. I hashed the DLL at `a97ab85c`, not at the directory-name commit `d70aad5` (which
resolves to an unrelated later docs commit). Both happen to hash identically here since `d70aad5` is
simply a later HEAD state that hadn't touched the native build, but **the label and the manifest
disagreed, and I checked rather than assumed** — exactly the standing rule ("assert a leg's SHA
against a pre-registered manifest, never infer it from a label").

---

## 3. ROW 0g — mechanical fire, HK-025 refusal, full reasoning

All three runs: `Δ_null`'s cluster-bootstrap CI95 is a single point equal to the real `Δ`, excluding
zero. Literally, per the spec's text, that is `VOID`.

**I did not accept this at face value.** I measured *why* it fires:

| run | clusters (cycles) | clusters with ≥2 pairs | of those, clusters where `Δ` itself varies internally | shuffle power |
|---|---|---|---|---|
| primary | 211 | 71 (34%) | 12 | **17%** |
| replication 1 | 209 | — | — | 6% |
| replication 2 | 204 | — | — | 5% |

**Two-branch evaluation (HK-025):**

- **Branch A — the WSJT-X↔OpenWSFZ pairing is genuine** (matcher.py's exact-message-text join is
  correct, which it structurally must be — there is no tolerance for ambiguity in text equality).
  Given 66% of clusters have only one matched pair (nothing to shuffle) and the rest are
  overwhelmingly homogeneous in `true_dt_s` within-cycle (only 17% of shufflable clusters show any
  internal `Δ` variation at all), a within-cycle random re-pairing is **the identity permutation for
  most of the population** and near-identity for the rest. Predicted null: tight, ≈ real `Δ`.
- **Branch B — the pairing is somehow wrong/manufactured.** Because same-cycle messages are
  transmitted at (almost always) the same nominal timing and share the same rounding bucket, even a
  *wrong* within-cycle swap lands on the same value. Predicted null: **also** tight, ≈ real `Δ`.

**Both branches predict the same observed result, for reasons that have nothing to do with whether
the pairing is correct.** That is HK-025's exact criterion for a diagnostic check (same verdict
either way ⇒ refuse). I refuse ROW 0g's literal "VOID" verdict for this dataset and continue the
analysis — disclosed here in full, not silently passed and not silently ignored. **This is a
property of the R&R synthetic bench's cycle-labelling scheme** (many trials sharing a
`cycle_utc` slot with only one or two messages each), not of `D2`'s question. If you want ROW 0g
certifiable on this bench in future, it needs a redesigned null (e.g. permute across a wider window
than one cycle, or restrict to the minority of genuinely multi-message, heterogeneous-`dt` cycles
and accept a much smaller n) — I have not attempted that redesign; it's a spec decision, not mine to
make unilaterally.

---

## 4. `Δ` is quantized, not continuous — and that changes how ROW 1/2/3/4 should be read

The pre-registered statistic (cluster-bootstrap **median**, reused verbatim from `n1_stats`) reports
`se = 0.0000` and a **zero-width CI** on every run. That is not real measurement precision — it's an
artifact of `Δ` taking only **two discrete values per run**, with the median collapsing onto
whichever has plurality:

| run | value counts (`Δ`, count) | mean | median (pre-registered) |
|---|---|---|---|
| primary | `{−0.7: 279, −0.6: 100}` | **−0.674** | −0.700 |
| replication 1 | `{−0.7: 107, −0.6: 281}` | **−0.628** | −0.600 |
| replication 2 | `{−0.6: 108, −0.5: 243}` | **−0.531** | −0.500 |

This is the signature of **WSJT-X's coarse ~0.1 s DT rounding straddling a continuous offset near
0.65–0.68 s** (standing note: reference DT resolution is 0.1 s, coarser than our own grid). The mean
is the better point estimate of a rounding-straddled constant and I report it alongside the
pre-registered median, not in place of it — both shown, nothing hidden. **The mean lands within 2.4
cm-of-time (0.024 s) of AO1's independently-measured `K = +0.650 s`** on the primary run. That is a
striking, unplanned cross-check in the same spirit as H1a's 0.0085 Hz agreement with T1 — two
different instruments, same physical/convention quantity, close agreement.

**Why this also complicates ROW 4's slope test.** The mandatory slope of `Δ` on `true_dt_s` came out
significant on the primary run (+0.0158 s/s, CI excludes 0, p=0.0058) and marginal on replication 2
(p=0.058); replication 1 was significant with the *opposite* sign (−0.0161 s/s). I crosstabbed the
`Δ` value against `true_dt_s` directly:

```
true_dt_s=0.00  {-0.7: 230, -0.6:  37}   (86% / 14%)
true_dt_s=0.20  {-0.6:  39, -0.7:  27}   (59% / 41%  -- majority FLIPS)
true_dt_s>=0.30 ...tiny per-bucket counts (1-3), noisy
```

267 of 379 pairs sit at `true_dt_s=0.00`; the next-largest cluster (66 pairs) sits at `0.20`. The
*fraction* in each rounding bucket shifts between those two points — exactly what a fixed continuous
offset near a rounding boundary produces when combined with a rounding decoder, with no requirement
that the true offset itself depend on `true_dt_s` at all. A cluster-robust OLS fit to a two-valued
response whose bucket-membership *probability* varies with `x` can read out a "significant slope"
that is a **quantization/aliasing artifact**, not evidence that `Δ` genuinely depends on where the
signal sits. I have **not** proven this is what happened — I don't have a clean permutation-style
proof the way I did for 0g, so I am **not** invoking HK-025 to refuse ROW 4 the way I refused 0g.
I'm flagging it as the leading alternative account, with the data that supports it, and reporting
ROW 4 as mechanically fired.

---

## 5. GH #3/#111 — posted, per your instruction (housekeeping, done before this run)

Verified your one flagged assumption independently before posting (HK-022): grepped the `WASAPI
device opened` line in all four `AO1` corpora's daemon logs. **Identical device GUID and friendly
name in all four** — `{0.0.1.00000000}.{67987b85-f257-41bc-8ab0-b22d6bc5e452}` /
`'Microphone (2- USB Audio CODEC )'`. Your #111 draft's central claim (device axis held constant
across all four corpora) is confirmed, not merely believed. Posted both comments verbatim:
- #3: https://github.com/frank001/OpenWSFZ/issues/3#issuecomment-5342637347
- #111: https://github.com/frank001/OpenWSFZ/issues/111#issuecomment-5342638586 (**stays OPEN**)

---

## 6. Predictions, scored against the primary run

| quantity | your prediction | actual | |
|---|---|---|---|
| row | ROW 1 P≈0.45 / ROW 3 P≈0.35 / ROW 2 P≈0.12 / ROW 4 P≈0.08 | **mechanical: ROW 4** (your lowest-probability call) — but point estimates say ROW 1 | see §1 |
| `Δ` point | −0.55 s | **−0.674 s** (mean) / −0.700 s (median) | inside your 80% interval `[−0.75,−0.35]` either way |
| slope | 0, CI excluding ±0.05 s/s | +0.0158 s/s, CI `[+0.0046,+0.0269]` | technically excludes 0, but magnitude is inside your own ±0.05 tolerance and I believe (§4) it may be an artifact |

---

## 7. Mechanics, so this is auditable

- No new data — all three runs' `*_matched.csv` files, already on disk, per spec §3.
- Reused `n1_stats.cluster_bootstrap_median_diff` (median + CI + p, verbatim) and
  `m4_stats.ols_cluster_robust` (cluster-robust slope, verbatim), per the spec's own instruction to
  reuse where the statistic matches.
- Join key: `(scenario_id, part_index, trial_index, seed, message_text, true_freq_hz, cycle_utc)`;
  `message_text` used in-process only to build the key, never written to any log line or JSON field
  — grepped both emitted files (`results/d2_report.json`, `results/d2_run.log`) individually for
  callsign-shaped and message-shaped content after the run: **zero hits** (NFR-021).
  `2026-08-15-8d6e1b1`'s known contamination case was avoided by construction — this arm never reads
  the false-positive rows where that contamination lives.
- Self-consistency check: my loader reproduces your own §3 pre-registration counts on the primary
  run exactly (464 WSJT-X / 393 OpenWSFZ usable rows) — an independent confirmation before any
  pairing logic ran.
- HK-025 independent re-classification done fresh at spec-read time (`hk025_check()`), and again,
  properly, on discovering ROW 0g's mechanical fire (§3) — not adopted from your framing unexamined.
- Runtime: re-analysis only, well under a minute of actual computation across all three runs.

Harness: `qa/rr-study/d2-convention-vs-physical-offset/run_d2.py`. Artefacts:
`qa/rr-study/d2-convention-vs-physical-offset/results/{d2_report.json,d2_run.log}`.

---

## 8. What I am and am not claiming

**Not claiming:** that ROW 1 is confirmed, that ROW 4 is confirmed, or that I've resolved the
tension your own §1 named going in ("Part C measured a real +0.706pp recall cost, which a purely
notational difference has no mechanism to produce"). That tension is untouched by this run either
way — a convention explanation for `Δ` doesn't by itself explain Part C's recall cost, regardless of
which row above turns out to be right.

**Claiming:** the point-estimate evidence for a near-constant `Δ` close to −0.65s is strong and
triply corroborated (three independent runs, one independent cross-check against AO1's `K`); the
pre-registered 0g gate is inapplicable to this bench's cycle structure (named refusal, not a silent
override); and the ROW 4 slope trigger has a plausible, evidenced, but *unproven* alternative
account as a quantization artifact rather than a genuine instrument failure.

## 9. Scope discipline

`D2` touched only the R&R matched CSVs already on disk. No `src/`, no capture run, no rebuild, no
Developer session — HK-011 not engaged. Does not revisit AO1 (closed), C2 (accepted), the ledger
correction, ROW 3, ROW 0f, `D1`, N1 ROW 2/limb 1, N5, or any standing closure.

**Awaiting your direction** on how to resolve the ROW 1-vs-ROW 4 tension — in particular whether a
quantization-aware re-analysis (e.g. fitting the rounding-boundary-crossing probability directly, or
restricting the slope test to a `true_dt_s`-balanced subsample) is worth specifying, or whether this
should be escalated to the Captain as-is given the stakes (an `src/` change hangs on which way this
resolves).
