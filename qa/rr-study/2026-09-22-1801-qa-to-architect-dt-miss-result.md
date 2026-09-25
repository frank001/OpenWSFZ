# `DT-MISS` — result: **ROW T2 fires — no measurable late-start penalty; timing is ruled out as a cause of the strong-miss pool**

QA, 2026-09-22T18:00:53Z (`date -u`, HK-017). Per spec
`qa/rr-study/2026-09-22-1754-architect-to-qa-spec-dt-miss-rate.md` (`arch/live-gap-map`, commit
`1d927f00`), Captain-authorised (*"have QA run the DT miss-rate check"*), no capture, no rebuild, no
`src/`/`native/` change.

**Headline.** All three ROW 0 checks pass. `CORE` (REF DT `[0.0,1.0)`) misses at **27.57%**; `LATE`
(REF DT `≥1.5`) misses at **23.99%** — **lower**, not higher. `Δ = −3.57` pp, CI95 `[−7.92, +1.98]`
straddles zero, so `CI_lo(Δ) ≤ 0` — **T2 fires**: neither T1 nor T1b, because the sign the geometry
hypothesis predicted (late costs more) does not hold even before materiality is asked. `n_late = 1,092`
(well above the `T0` power floor of 300). The predicted window-edge cliff at `+1.71` s (§1 of the spec)
does not appear in the 0.1 s curve (§4 below, chart). `D-c` shows the OWS−REF DT offset is flat across
every band (`0.638`–`0.664` s), so this is not a display artefact masking a real timing loss.

---

## 1. ROW 0 (strict order, per spec §5)

| row | check | result |
|---|---|---|
| **0a** | Amendment-3-cut harness reproduces `n_ref` 127,482 / `H10` 19.2686 before any split | **PASS, exact.** `{"n_ref": 127482, "H10_4dp": 19.2686}` |
| **0b** | median REF DT over C3 (all REF rows, parseable) in `[0.0, 0.6]` s | **PASS.** `0.2` s, `n_parsed` 127,482, `n_unparsed` 0 |
| **0c** | band `n`'s (7 bands + "unparsable") sum to `n(pop)` exactly, on both the `H10` population and all REF rows | **PASS, both.** `H10` pop: `87,031` = `87,031`. All REF: `127,482` = `127,482`. Zero unparsable DT lines on either the REF or OWS `ALL.TXT` in this corpus |

Column-`[5]` assertion (§2 of the spec, "swapping 5/6 inverts results"): confirmed by construction —
`load_all_dt` parses `f[5]` as DT and separately validates `f[4]`/`f[6]` parse as SNR/`freq_hz` int,
exactly mirroring the harness's own `matcher.load()`. Key-set alignment between the DT loader's REF
keys and the harness's own `ref` dict: **exact match**, `key_alignment_ref_dt_vs_ref = true`.

## 2. ROW T (strict order, first match wins, per spec §3)

| row | predicate | this corpus |
|---|---|---|
| T0 | `n(LATE) < 300` | Not fired: `n(LATE) = 1,092` |
| **T1** | `CI_lo(Δ) > 0` and `Excess ≥ 0.5` | **Not fired** |
| **T1b** | `CI_lo(Δ) > 0` and `Excess < 0.5` | **Not fired** |
| **T2** | otherwise | **FIRES** |

`Δ_pp = miss(LATE) − miss(CORE) = 23.9927 − 27.5661 = −3.5734` pp. 95% frequency-clustered bootstrap
(N=2000, seed 20260921, resampled over the `CORE ∪ LATE` frequency universe, 2,693 distinct
frequencies, paired per draw): `CI95 [−7.919, +1.977]`. Since `CI_lo = −7.919 ≤ 0`, `T1`/`T1b`'s first
condition fails regardless of `Excess` — **T2 by construction**, not a close call on materiality. For
completeness, the point-estimate `Excess_pp = Δ_pp × n(LATE)/n(pop) = −3.5734 × 1092/87031 = −0.0448`
pp — negative and two orders of magnitude below the `GAIN_BAR` of 0.5 pp even had the sign gone the
other way.

**Reading:** stations starting late in our capture window do not decode worse than stations starting in
the core window — if anything the point estimate runs the other way, but the CI is consistent with no
effect at all. **Timing is ruled out as a cause of the strong-miss pool on this corpus.** No window-fix
spec is licensed by this result (§3.7 of the arm's parent spec: the fix track in the Architect's §1
geometry reasoning does not apply).

## 3. Descriptives (§4 of the spec, report every one, gates nothing)

**D-a, `H10` population** (REF SNR ≥ −10, `n = 87,031`, `24,564` total misses):

| REF DT band | n | misses | miss % | share of all misses |
|---|---:|---:|---:|---:|
| `< −0.5` | 2,021 | 820 | 40.57% | 3.34% |
| `[−0.5, 0.0)` | 5,377 | 2,018 | 37.53% | 8.22% |
| `[0.0, 0.5)` | 67,217 | 18,595 | 27.66% | 75.70% |
| `[0.5, 1.0)` | 8,608 | 2,307 | 26.80% | 9.39% |
| `[1.0, 1.5)` | 2,716 | 562 | 20.69% | 2.29% |
| `[1.5, 2.0)` | 707 | 182 | 25.74% | 0.74% |
| `≥ 2.0` | 385 | 80 | 20.78% | 0.33% |
| unparsable | 0 | 0 | — | — |

**D-a, all REF rows** (`n = 127,482`, `51,117` total misses) — same shape, uniformly higher miss % (the
`H10` population excludes the easiest, strongest signals):

| REF DT band | n | misses | miss % |
|---|---:|---:|---:|
| `< −0.5` | 2,584 | 1,236 | 47.83% |
| `[−0.5, 0.0)` | 6,986 | 3,183 | 45.56% |
| `[0.0, 0.5)` | 99,184 | 39,566 | 39.89% |
| `[0.5, 1.0)` | 13,482 | 5,453 | 40.45% |
| `[1.0, 1.5)` | 3,693 | 1,147 | 31.06% |
| `[1.5, 2.0)` | 1,071 | 394 | 36.79% |
| `≥ 2.0` | 482 | 138 | 28.63% |

**Reading both tables together:** the *earliest*-arriving band (`< −0.5` s, stations whose signal starts
before our nominal slot) has the **highest** miss rate of any band on both populations — the opposite
edge from the one the window-geometry hypothesis was about. The bulk of both the population and the
misses sit in `[0.0, 0.5)` (76–78% of all misses) simply because that is where REF DT clusters (median
0.2 s) — this band's miss rate (27.66% `H10` / 39.89% all-REF) is close to the corpus-wide average and
should not be over-read as either better or worse than typical.

**D-b, 0.1 s miss-rate curve, REF DT `[−1.0, +2.5]`, `H10` population:** chart at
`qa/dt-miss/2026-09-22-84cac119-amendment3/dtmiss_curve.png` (full 35-bin table in
`dtmiss_result.json`). **No cliff at the predicted `+1.71` s window edge.** The curve is noisy above
`+1.5` s (bins there hold roughly 100–200 rows each, against the H10 population's 87,031 total, so
single-bin swings of ±10–15 pp are sampling noise, not signal) and shows no sustained step change
anywhere near `+1.71` s specifically — a local peak sits at `+1.85`–`1.9` s (~35%) immediately followed
by a trough at `+1.95`–`2.0` s (~15%), which is exactly the kind of adjacent-bin noise expected from
counts in the tens per bin, not a geometry-driven edge.

**D-c, OWS−REF DT offset for matched pairs, per band** (exact-matched pairs plus unambiguous
single-candidate wildcard pairs; ambiguous multi-candidate gains excluded — no single OWS DT to
attribute):

| REF DT band | n pairs | mean offset (s) | SD (s) |
|---|---:|---:|---:|
| `< −0.5` | 1,201 | 0.6449 | 0.0511 |
| `[−0.5, 0.0)` | 3,359 | 0.6632 | 0.0485 |
| `[0.0, 0.5)` | 48,618 | 0.6540 | 0.0500 |
| `[0.5, 1.0)` | 6,301 | 0.6379 | 0.0497 |
| `[1.0, 1.5)` | 2,154 | 0.6438 | 0.0498 |
| `[1.5, 2.0)` | 525 | 0.6636 | 0.0482 |
| `≥ 2.0` | 305 | 0.6430 | 0.0496 |

Flat within noise across the entire DT range (`0.638`–`0.664` s, SD ≈ `0.05` s throughout) — this
matches the Architect's own §1 note that ~0.5 s of the offset is a slot-start-vs-nominal-TX-start
definition difference, and confirms it does not vary with how late a station starts. No indication that
our DT *reporting* degrades or shifts at the late end even where miss rate is being read.

**D-d, C2 replication (shape only, not a row — C2 is `nhard` 60, 13 days apart, level not comparable):**
run via `dtmiss.py --selftest-c2`. Same qualitative shape as C3's `H10`-population D-a: earliest bands
(`< −0.5`, `[−0.5, 0.0)`) at 33.0%/27.9% miss, the bulk band `[0.0, 0.5)` at 27.9%, and the late bands
(`[1.5, 2.0)` 26.1%, `≥2.0` 22.0%) **not** elevated above the core bands — same sign of "no late
penalty" as C3, on a differently-built, differently-timed corpus. Offered as corroborating shape, never
as a second data point for the level.

## 4. Architect predictions (§6 of the spec) — inputs handed over, scoring is yours

| # | prediction | input |
|---|---|---|
| T-1 | T1 fires | **Does not fire.** T2 fired |
| T-2 | T1b fires | **Does not fire.** T2 fired |
| T-3 | T2 fires | **Fires** |
| T-4 | T0 fires | **Does not fire** (`n_late` 1,092 ≥ 300) |
| T-5 | D-b shows the steepest rise between `+1.5` and `+2.0` s | Reported, not scored by me: the curve rises from `+1.5` s (~28%) to a local peak at `+1.85`–`1.9` s (~35%) then falls to a trough at `+1.95`–`2.0` s (~15%) before rising again past `+2.0` s — whether this constitutes "the steepest rise in that window" against the rest of the −1.0…+2.5 s range is a reading call, not a mechanical one I'll make; full 35-bin table in `dtmiss_result.json` for you to check it against the other bins directly |

## 5. NFR-021

Report, `dtmiss.py`, `dtmiss_result.json` and the chart carry counts, rates, DT/SNR/frequency values
only — no message text or callsign anywhere. `scan()`/`classify()` (imported directly, file uncommitted
at scan time) run clean against this file, `qa/rr-study/live-gap-map/dtmiss.py`, and both files in
`qa/dt-miss/2026-09-22-84cac119-amendment3/`. The chart PNG was manually reviewed (axis-labelled miss-
rate curve only, no text overlay beyond axis/legend labels).

## 6. HK-025

No row here is a diagnostic dressed as a gate: `T0`/`T1`/`T1b`/`T2` are mutually exclusive, evaluated in
a fixed order, on a hard, pre-registered bar (`GAIN_BAR` 0.5 pp, already the project's standing
materiality bar, not invented for this arm), and the significance leg (`CI_lo(Δ) > 0`) is checked before
the materiality leg in both T1 and T1b — a corpus where `Δ`'s sign had gone the other way would have
fired a different row, not this one. No refusal needed.

## 7. Artefacts

Corpus: `artefacts/20260921_1624_live_run-live-gap-map/` (gitignored, unchanged from `LIVE-GAP-MAP`,
Amendment 3 cut applied by the same `AMD3_EXCLUDE` code path, `results/dtmiss_result.json` +
`results/dtmiss_curve.png` are the script's own record). Script: `qa/rr-study/live-gap-map/dtmiss.py`
(new, committed this session), imports `lgm_harness` for `load_c3`/`core` so the cut and the matcher are
exactly the ones `LIVE-GAP-MAP`'s M1 verdict used. Committed to this report:
`qa/dt-miss/2026-09-22-84cac119-amendment3/` (`dtmiss_result.json` + `dtmiss_curve.png`, copies of the
corpus's own gitignored output, promoted here for the record) and this file. Branch: `qa/live-gap-map`.
**Not pushed** (HK-033) — Captain's go needed for push/PR; nothing merged.
