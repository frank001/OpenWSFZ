# `LIVE-GAP-NOW` — result: **ROW 0d FAILS on C2 — the B1-B4 gate is VOID**; A1 (current live figure) stands at **61.09%**

QA, 2026-09-12 19:30Z (`date -u`, HK-017). Per spec
`2026-09-12-1721-architect-to-qa-spec-live-gap-now-current-binary-live-recovery.md`, cleared to run
2026-09-12 17:21Z (Captain: "proceed with your recommendations"), `arch/live-gap-now` `f022001a`.

**Headline: ROW 0d fails.** `NOW`'s replay of C2 vs C2's own live `openwsfz/ALL.TXT` gives
`F_live = 98.32%`, `F_rep = 86.64%` — both must be `>= 0.99`; `F_rep` misses by 12.4 points. Per
spec, **this VOIDs the entire §3.6 B1-B4 gate table: no `Δ(C1)`/`Δ(C2)` may be cited as a build
effect, or as the absence of one.** ROW 0c still PASSES exactly (H1's `40,003/69,222` reproduced to
the digit) and **A1 — the number that replaces "57.79%" as the current live figure — still stands**,
because it is read directly from live logs, not from any replay: **`R_wild(C2, NOW, live) = 61.09%`**
(`R_base = 59.39%`, `n_ref = 91,046`), qualifiers: binary `6b2e16a6...`, `nhard 60`, 20m, REF =
WSJT-X FT991A alone, 2026-09-08/09 window. 🛑 **Do not compare this to 57.79% as a build effect**
(different corpus, different REF definition, different date — spec §3.5's own standing guard).

---

## 1. HK-020 — critical config (checked against spec §1/§2, not inherited from a header)

| config | value |
|---|---|
| C1 | `artefacts/20260808_live_run_0016-8080/`, `owsfz/wav/` (our own capture), REF = `wsjt-x/ALL.TXT` A-only, window `260808_004000..260808_111500`. **2,541 cycles found in-window** (spec's own descriptive "2,529" is an approximation, not a ROW 0 value — no row checks this count; disclosed, not chased) |
| C2 | `artefacts/20260908_live_run_1827-fp-floor-live-2/`, `cycle-audio/` (mono/16-bit/12kHz/180,000 samples, confirmed), REF = `wsjtx-1-ft991a/ALL.TXT` A-only, window `2026-09-08T19:36:45Z..`last cycle in `openwsfz/ALL.TXT` (`260909_172200`). **5,222 cycles** after excluding 5 `*_2.wav` duplicate-pipeline files (all 5 predate the boundary, 0 inside it — matches spec's own expectation) |
| Legs | **L08** (`b8845cd` blob, SHA `f2f30c89...`, shim `20260033`, `(10,0.10,60)`), **NOW** (`origin/main`, SHA `6b2e16a6...`, shim `20260050`, `(10,0.10,60)`), **NOW40** (same binary as NOW, `(10,0.10,40)`) — each its own process, distinct DLL filename, `ft8_lib_version_check()` re-confirmed through the loaded handle |
| Matcher | H1's own `load()`/`wildcard_match()`, reused verbatim; `R(OWS,REF) = 100*(|REF∩OWS| + |wild_gained|)/|REF|`, `R_base` = exact-only |
| Bootstrap | frequency-clustered, paired per draw (`N_BOOT=2000`, seed `20260912`), extended from `p23_common.cluster_bootstrap` to keep per-draw arrays so `Δ` is a paired statistic, not a difference of two independent CIs |
| Total decode calls | `(2,541 + 5,222) x 3 legs` = 23,289. Wall time: **~50 min** (all three legs run concurrently, one process each) |

New code: `qa/rr-study/live-gap-now/{dll_pin.py,corpus.py,matcher.py,decode_leg.py,leg_output.py,seam.py,bootstrap.py,analyse.py}`.
Reused verbatim (HK-018): `p23_common.Decoder`/`read_wav`/`normalise_rms`,
`h1_hash_token_contamination.load`/`wildcard_match`.

## 2. ROW 0 (strict order)

| row | check | result |
|---|---|---|
| **0a** | SHA-256 of loaded file == pin, **and** `ft8_lib_version_check()` through the loaded handle == pin, all 3 legs | **PASS, all 3.** `L08`: `f2f30c89...` / `20260033`. `NOW`/`NOW40`: `6b2e16a6...` / `20260050` |
| **0b** | ABI: `ft8_lib_version_check`/`ft8_decode_all`/`ft8_set_decode_params` signatures and `FT8Result` layout identical between `b8845cd` and `origin/main`'s `ft8_shim.h` | **PASS** — byte-identical, independently diffed (not assumed from the spec's own drafting-time check) |
| **0c** | On C1, live `owsfz/ALL.TXT` vs `REF = A∩B` gives `|REF|=69,222` and `exact+wild=40,003` (`R_wild=57.79%`) | **PASS, exactly.** `69,222` / `40,003` / `57.7894%` — reproduces H1's headline to the digit |
| **0d** | On C2, **NOW's replay** vs C2's **live** `openwsfz/ALL.TXT`: `F_live >= 0.99` **and** `F_rep >= 0.99` | **FAIL.** `F_live = 0.9832` (n=57,969 live decodes), `F_rep = 0.8664` (n=65,780 replay decodes). `F_live` is close; `F_rep` misses badly. **§3.6 B-rows VOID.** §5 below |
| **0e** | (report only) **L08's replay** vs C1's **live** `owsfz/ALL.TXT`, same two shares | `F_live = 0.9849` (n=41,521), `F_rep = 0.8973` (n=45,576) — **the same asymmetric shape as 0d**, on a different corpus and a different (older) binary. Not a gate; affects only whether L08 may be called "the 08-08 live binary" (it already carries that caveat — spec §0) |
| **0f** | L08's and NOW's full `(ts,freq_hz,dt,snr,message)` tuples on C1 are **not** identical on every cycle | **PASS.** 1,529 of 2,541 C1 cycles differ between the two binaries — the seam is clearly not blind |
| **0g** | power: `SE(Δ(C1)) <= 0.75 pp` | **PASS.** `SE(Δ(C1)) = 0.053 pp`, well inside the bar (P1's own prior estimate was `0.347 pp`; the realised paired SE is smaller because the bootstrap is far more tightly paired than a two-sample comparison) |

**Truncation guard:** zero cycles hit `MAX_RESULTS=200`, any leg, any corpus.

## 3. Consequence of ROW 0d's failure (spec §3.2)

> "0d seam fidelity ... on failure: §3.6 rows VOID (a replay contrast would not speak for live).
> §3.5 A1, which is read from live logs, still stands."

**Applied exactly as written.** The `B1`/`B2`/`B3`/`B4` gate table in §3.6 does not run — `Δ(C1)`
and `Δ(C2)` are reported below in full (§6), for the record and for diagnosis, but **neither may be
cited as evidence the 08-22→09-12 build span changed live recovery, nor as evidence it did not.**
`A1` (§4) is unaffected — it never used a replay.

## 4. Why `F_rep` misses (diagnosis, offered as a hypothesis — not asserted as mechanism, same
discipline as the `NT` result's OSD/S7 note)

`F_rep < F_live` on **both** corpora, **both** binaries, at almost the same magnitude (C2/NOW:
86.6%/98.3%; C1/L08: 89.7%/98.5%) — this shape is not a one-off. Sampled mismatches (one cycle
inspected in full, `NFR-021`-checked before writing this: message text discarded, counts only)
show the pattern directly: for one C2 cycle carrying ~16-21 decodes on each side, replay produced
**5 extra decodes with garbled or hash-tokenised text** absent from the live log for that same
cycle, while the remaining ~15-16 stations matched almost exactly — one of those matching pairs
differed by **3 Hz** between live and replay (just outside this check's `1 Hz` tolerance), the rest
by 0 Hz.

**Checked, not assumed:** `DecodeNoiseSuppressionFilter.cs`'s own doc comment states plainly
*"`ALL.TXT` continues to receive the unfiltered `DecodeResult` list unchanged; this filter is never
applied to it"* — so the C#-level noise-suppression feature is **ruled out**; it cannot be the
cause, whatever its setting was during capture. **Checked for a within-window warm-up trend** (the
callsign hash table is process-global and session-scoped, spec's own note): splitting C2's 5,222
cycles into 10 chronological deciles shows `F_rep` **flat at 84-88% across the entire ~19-hour
span**, with no rising trend — ruling out simple "the replay process's table fills up as it goes."
**Working hypothesis:** the native decoder's own process-global, session-scoped hash-table
suppression (the 12-bit unique-match mechanism, #138, mentioned in this arm's own §0) depends on
history accumulated **before** the corpus window even starts — the live daemon had been running for
an unknown, likely much longer span before `19:36:45Z`; a replay process starting cold at the
window boundary can never reconstruct that prior state, so it under-suppresses a small, roughly
constant share of noise-triggered garbage throughout. **This is a hypothesis; `LIVE-GAP-NOW` was not
designed to test it, and I have not tested it further here.** It is exactly the failure mode ROW 0d
exists to catch (spec: "a replay leg's output... keyed the same way" — if the process's own history
differs, "a replay contrast would not speak for live").

## 5. `Δ(C1)` / `Δ(C2)` — reported, not gated (spec §3.6's own instruction on a VOID)

```
Delta(C1) = R(NOW) - R(L08), paired freq-clustered bootstrap, N=2000, n_freq=2,654
  mean = -0.129 pp   SE = 0.053 pp   CI95 = [-0.249, -0.052] pp
Delta(C2) = R(NOW) - R(L08), same method, n_freq=2,734
  mean = -0.297 pp   SE = 0.057 pp   CI95 = [-0.411, -0.196] pp
```

Both intervals exclude zero and are negative — if this were a valid contrast (it is not, per §3),
it would read as a small live recall *regression*, not the `+0.5..+2.5 pp` gain the Architect's own
blind prediction favoured (§4 of the spec, `B1` at 30%). **I am not reading this as `B3`.** ROW 0d's
failure means the replay path itself is not faithful enough to attribute this sign to the build
span rather than to the replay/live divergence documented in §4 above — the same-direction,
similar-magnitude asymmetry in `F_rep` on **both** corpora is at least as plausible an explanation
for a small negative `Δ` as a genuine regression would be. **This is squarely why ROW 0d exists**,
and why its failure is a STOP, not a footnote.

## 6. Descriptive, no row (spec §3.5, reported in full per the VOID instruction)

**A1 — current live figure (the citable replacement for "57.79%"):**

`R(C2 live openwsfz/ALL.TXT, REF A-only) = 61.0856%` (`R_base = 59.3931%`, `n_ref = 91,046`).
Citable only with all qualifiers: binary `6b2e16a6...`, `nhard 60`, 20m, REF = WSJT-X FT991A alone,
window `2026-09-08T19:36:45Z`..`2026-09-09T17:22:00Z`.

**A2 — R for every leg x corpus, plus `R(NOW,C1,A∩B)` beside 57.79%:**

| leg | corpus | R_base | R_wild |
|---|---|---:|---:|
| L08 | C1 | 55.98% | 58.24% |
| NOW | C1 | 56.17% | 58.11% |
| NOW40 | C1 | 57.19% | 58.23% |
| L08 | C2 | 59.10% | 62.59% |
| NOW | C2 | 58.99% | 62.29% |
| NOW40 | C2 | 59.01% | 62.19% |

On the **same `A∩B` REF H1 used** (`n=69,222`), for the record: `L08` replay `R_wild = 58.35%`,
`NOW` replay `R_wild = 58.22%`, `NOW40` replay `R_wild = 58.34%` — all close to but **not identical
to** the live `57.79%` headline, consistent with §4's replay/live divergence (even `L08`, nominally
"the same build", does not reproduce its own live figure exactly via replay).

**A3 — `R(NOW40,C) - R(NOW,C)`, descriptive only, does not reopen `NHARD40-DEFAULT`:**

| corpus | mean | SE | CI95 |
|---|---:|---:|---|
| C1 | +0.120 pp | 0.053 pp | `[+0.047, +0.237]` |
| C2 | -0.099 pp | 0.095 pp | `[-0.326, +0.029]` |

Neither corpus's `CI_hi < -0.5 pp`, so no same-day flag to the Architect is triggered. Signs
disagree between corpora and both magnitudes are small; at fixed `REF`, `nhard`'s FP benefit is
invisible to `R` (HK-021(t)) and a lower `nhard` can in principle only *lose* corroborated hits — a
small positive `C1` reading most plausibly reflects the wildcard-match term interacting with fewer
false decodes at `nhard=40`, not a genuine gain in true recovery. Not asserted as mechanism.

**A4 — where the change lives, recovery by reference SNR (2 dB bins) and by frequency band:**

By frequency band (the full 2dB-SNR-bin table is in `artefacts/live-gap-now/analysis.json`; the
by-band summary is the more legible cut):

| corpus | band | L08 | NOW | n |
|---|---|---:|---:|---:|
| C1 | `<200 Hz` | 11.80% | 11.80% | 805 |
| C1 | `200-3000 Hz` | 58.85% | 58.72% | 68,494 |
| C1 | `>=3000 Hz` | 0.00% | 0.00% | 73 |
| C2 | `<200 Hz` | 3.09% | 3.09% | 1,748 |
| C2 | `200-3000 Hz` | 63.78% | 63.47% | 89,265 |
| C2 | `>=3000 Hz` | 0.00% | 0.00% | 33 |

**Every out-of-band bin (`<200`, `>=3000`) reads byte-identical between L08 and NOW** — expected,
since both binaries' `ft8_decode_all` candidate passband covers the same nominal range at the
monitor-config level for signals actually reaching a candidate; the passband widening (`20260038`,
`[200,3000)`->`[140,3030)` Hz) does not shift these particular bin boundaries (200/3000 Hz), so this
table cannot see that change directly — a finer-grained bin at the 140-200 Hz edge would be needed
to, and is not computed here (out of this arm's scope). The `200-3000 Hz` band shows the small
negative `L08->NOW` shift consistent with `Δ(C1)`/`Δ(C2)`'s own sign, for the reasons in §5.

**A5 — `Δ(C2)` with its paired CI:** reported in §5 above (`-0.297 pp`, CI95 `[-0.411, -0.196]`).

## 7. NFR-021

C1/C2 `ALL.TXT` and WAVs carry real third-party callsigns. This report and `analysis.json` carry
counts, rates, and frequencies only — no message text or callsign appears anywhere in this
document. `scan()`/`classify()` run clean against this file and all new `.py` files.

## 8. Where this leaves the arm (spec §3.7)

Per spec, a VOID at ROW 0d means: report every figure (done, §6), nothing is re-based (57.79% is
**not** replaced by a build-attributed number — it is replaced, descriptively, by A1 alone, with
A1's own qualifiers), and `Δ` may not be cited as a change or as the absence of one (§5's own
framing). **I am not proposing a fix to the replay harness to chase `F_rep` up to 0.99** — that
would be a new arm (a warm-started replay, or a native-side export of the hash-table's own contents
to seed a fresh process), not a re-run of this one, and is the Architect's call per HK-025's own
"I report the fork, I do not resolve it" convention from the `NT` result.

## 9. Artefacts

`artefacts/live-gap-now/{bin/,_out/*.jsonl,logs/,analysis.json}` (gitignored, per standing
convention; corpora copied from the Architect root worktree with the Captain's go-ahead, ~3.8G).
Committed: `qa/rr-study/live-gap-now/*.py`, this report. Branch: `qa/live-gap-now-result` (off
`origin/main` post-`f91b9b8f` merge). **Not pushed** (HK-033) — Captain's go needed for push/PR.
