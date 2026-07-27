# D-001 R.5 — hybrid ladder findings: no single rung explains the gap, and the two decoders
# diverge more with each rung added

**Author:** QA, 2026-07-27 (18:48 UTC, `date -u`, per HK-017). **Executes:**
`2026-07-27-r5-hybrid-ladder-task-spec.md`, operationalising
`2026-07-27-1822-architect-r5-hybrid-ladder-design.md`.

---

## 0. Verdict

**Both self-checks pass. The ladder does not collapse at a single rung — it declines at every
rung, and the gap between our decoder and jt9 (zero at rung 0) widens at every rung too, reaching
20.5 points by rung 4.** The design's reading rule was written for a step function (flat, then one
collapse, then flat again); the measured shape is a slope. Read literally, the rule's first row
("collapse first appears at rung 1") technically fires and would nominally point at population
geometry alone — but reporting that in isolation would misrepresent the data, since three further
collapses follow it, one of them (rung 3 -> rung 4) larger than rung 1's. **The most informative
single observation is not which rung collapses first, but that our decoder loses ground to jt9 at
every rung from rung 1 onward, with two step-changes in that relative gap** — one at rung 2 -> rung
3 (jt9 *improves* against real noise while we do not) and one at rung 3 -> rung 4 (the real cycle
itself, which no synthetic rung, including the one with real noise, reproduces).

## 1. Self-checks

```
[PASS] rung 0 Wilson lower CI >= 90%: ours ci_lo=97.7% jt9 ci_lo=97.7%
       (160/160 both decoders, 20 buffers x 8 isolated signals at -14 dB reference SNR)
[INFO] rung 4, 20-cycle sample vs full-68-cycle published:
       ours 61.6% [57.6%,65.4%] (published ~61%, B.1/R.4b)  -- consistent
       jt9  82.5% [79.2%,85.3%] (jt9's own full-corpus overall hit-rate is 83.5%,
            A2=1693/2028, B.1 Sec.3 -- NOT the 55.4% miss-coverage figure, a different
            quantity; see Sec.2 note) -- consistent
```

Both pass. Rung 0 reproduces the 100% clean-signal result R.4 established (147/147, once the
slot-7 defect was excluded) at a smaller, freshly-generated sample — the harness plants correctly
inside the corrected `200-2950` Hz band. Rung 4's 20-cycle sample lands inside or adjacent to the
full-68-cycle published figures for both decoders, confirming the reused artefacts (WSJT-X
`ALL.TXT`, our offline `ALL.TXT`, B.1's recorded jt9-depth-1 stdout) are being read correctly for
this cycle subset.

**A third check, added beyond the task spec's own Sec.4** (run because the raw rung-4 population
was larger than rungs 1-3's, and a population mismatch could have manufactured part of the
apparent rung 3->4 collapse): rung 4 recomputed restricted to *exactly* the same 526 messages
planted in rungs 1-3 (`rung4_matched`, `n_not_in_wsjtx=0` sanity check passed). The matched and
unmatched rung-4 numbers agree closely (ours 61.6% both ways; jt9 82.1% matched vs 82.5%
unmatched) — **the rung 3->4 collapse is not a population-size artefact.**

## 2. The ladder, in full

| rung | n | ours P(decode) | ours ci | jt9 P(decode) | jt9 ci | gap (ours-jt9) |
|---|---:|---:|---|---:|---|---:|
| 0 (isolated synth, -14 dB ref) | 160 | 100.0% | [97.7%,100%] | 100.0% | [97.7%,100%] | 0.0 pt |
| 1 (+real density/layout) | 526 | 84.6% | [81.3%,87.4%] | 90.3% | [87.5%,92.5%] | -5.7 pt |
| 2 (+real SNR distribution) | 526 | 80.2% | [76.6%,83.4%] | 87.5% | [84.3%,90.0%] | -7.3 pt |
| 3 (+real noise background) | 526 | 79.7% | [76.0%,82.9%] | 93.5% | [91.1%,95.3%] | -13.8 pt |
| 4 (real, unmodified; matched pop.) | 526 | 61.6% | [57.4%,65.7%] | 82.1% | [78.6%,85.2%] | -20.5 pt |

**Per-step deltas:**

| step | Delta ours | Delta jt9 | Delta(ours) - Delta(jt9) ("excess" loss, ours-specific) |
|---|---:|---:|---:|
| rung0 -> rung1 | -15.4 pt | -9.7 pt | -5.7 pt |
| rung1 -> rung2 | -4.4 pt | -2.9 pt | -1.5 pt |
| rung2 -> rung3 | -0.6 pt | **+6.1 pt** | -6.7 pt |
| rung3 -> rung4 | -18.1 pt | -11.4 pt | -6.7 pt |

Two things jump out beyond the top-line shape:

1. **jt9 improves at rung 3** (real noise background, real-SNR amplitudes held fixed from rung 2)
   while we are flat-to-slightly-down. This is not a shared difficulty — it is a divergence. Adding
   the real noise environment measurably *helps* jt9 relative to synthetic AWGN at the same nominal
   SNR, and does nothing for us. This is the single cleanest piece of evidence in this arm that
   something about noise handling specifically (not sensitivity, not density) differs between the
   two decoders, independent of the rung3->4 jump.
2. **The largest single step for both decoders is the last one** (rung3->4, real content) — larger
   than rung 1's population-geometry step for both. Per the design's own reading rule, this is the
   "Rung 4 only" row: *"nothing about the content explains it; the difference is in the
   capture/processing chain ahead of the decoder... the most surprising outcome."* It fires, and it
   fires alongside rung 1's row rather than instead of it.

## 3. Reading against the design's table (Sec.3 of the design)

None of the four rows applies cleanly in isolation, for the same reason R.4b's three rows did not
fire cleanly: **the table was written for a single collapse point, and the data shows a decline at
every rung.** Read against each row honestly:

| row | fires? |
|---|---|
| Rung 1 only (population geometry) | **Partially** — real collapse here (-15.4/-9.7 pt), but three more collapses follow, one bigger. Not the whole story. |
| Rung 2 (dynamic range, the Architect's stated bet) | **Weakly** — a real but small further step (-4.4/-2.9 pt), the smallest of the four transitions for both decoders. The stated bet does not dominate. |
| Rung 3 (noise environment) | **No, and reversed for jt9** — we do not collapse here; jt9 *improves*. The "hardest to act on" row does not describe what happened, but the divergence it produced (§2 point 1) is real and load-bearing. |
| Rung 4 only (capture/processing chain) | **Yes, strongly** — the single largest step for both decoders, confirmed robust to the population-matching check (§1). |

**My own reading, offered for ruling rather than as a settled conclusion:** the honest shape is
that population geometry (rung 1) and something specific to real, unmodified audio that no
synthetic manipulation reproduces (rung 3->4) each explain a comparable, large share of the total
collapse (ours: -15.4 pt and -18.1 pt of a total -38.4 pt; jt9: -9.7 pt and -11.4 pt of a total
-17.9 pt), with the real-SNR-distribution step (rung 2) contributing modestly and the real-noise
step (rung 3) contributing near-zero to us but *negatively* (i.e. helping) to jt9. **The design's
own bet (rung 2, dynamic range) is the one row that clearly does not dominate** — it is the
smallest transition on the ladder for both decoders.

## 4. What this changes about "the other 93%"

R.4/R.4b already showed pure sensitivity (a clean 2.62 dB edge) explains only a small, bounded
slice of the gap. R.5 adds a second finding of the same shape: **no single content property —
density, SNR distribution, or noise texture — explains the bulk of it either.** The largest
identified piece (rung 3->4, -18.1 pt for us) is specifically the piece the design's own table
labels "not attributable to content at all" — something in the capture/processing chain, or some
combination of real-audio properties this ladder's four synthetic rungs collectively still do not
reproduce even when noise, density and SNR are all matched to reality individually.

**The rung2->3 divergence (§2 point 1) is, on this evidence, the most actionable single lead in
this arm.** It isolates a difference between the two decoders' handling of real (non-white,
non-stationary) background noise specifically, holding signal content and amplitude fixed — the
one place in the ladder where the two decoders' curves move in *opposite* directions from the same
manipulation. C.3's proximity/SIC proxy and R.4's independent ΔSNR both already pointed away from
raw sensitivity; this is a third, independent instrument pointing at noise-adaptive
handling/candidate scoring rather than co-channel proximity specifically, since rung 3's background
is real ambient noise with the *known* signals notched out, not a co-channel collision.

## 5. Layout/timing filter exclusions (task spec Sec.4 point 3)

Aggregate: of 599 real messages across the 20 cycles, 3 dropped to the band filter (`freq` outside
`[200, 2950]` Hz), 70 dropped to the timing filter (`dt` outside the buffer's plantable window after
per-cycle shift), leaving 526 planted. Two cycles were thinned heavily by the timing filter alone
(`260725_181815`: 26 of 31 dropped, only 5 planted; `260725_182015`: 30 of 36 dropped, only 6
planted) — both cycles evidently had a wide real `dt` spread that the 15 s buffer's 2.37 s
plantable window could not accommodate simultaneously for most of their population. These two
cycles contribute thin, geometry-unrepresentative samples to rungs 1-3; the pooled n=526 absorbs
this without a single cycle dominating, but it is not nothing — full per-cycle counts in
`artefacts/d001_r5_hybrid_ladder/layout_stats.json`.

## 6. Honest caveats

- **Rung 3's amplitude/noise-power rescaling is a QA construction** (task spec §2.4/§2.6), not
  specified by the design — amplitudes at rung 3 are pinned to that buffer's own real notched-noise
  RMS rather than the fixed synthetic reference, to isolate noise *character* from noise *power*.
  This means rung 2 and rung 3 are matched in nominal SNR, not in absolute signal amplitude, so the
  rung2->3 divergence (§2 point 1) should be read as "matched-SNR noise-character effect," not
  "identical-signal noise-character effect."
- **The dt shift-and-drop (§5) changes relative timing for the two heavily-thinned cycles**, and
  more mildly for others — unavoidable given the 15 s buffer format this whole study uses, but it
  means rungs 1-3's "real layout" is not always the *full* real layout.
- **CPFSK vs GFSK** — the standing caveat since B.2, carried through rungs 0-3 exactly as in every
  prior synthetic arm; rung 4 (real, unmodified audio) is exempt, same as R.4b.
- **WSJT-X's reported SNR is its own estimator**, inherited by rungs 2 and 3's amplitude
  construction, same caveat as R.4/R.4b.
- **The notch is imperfect by construction** (design §6, task spec §2.6): messages WSJT-X did not
  decode (weak/missed real signals) are not notched and remain as unaccounted structure in rung 3's
  "noise" background; messages above 2950 Hz are correctly notched (real signal energy) but were
  never planting candidates.
- **One decoder generation, one operator, one season, one corpus (40 m)** — the standing caveat
  every arm in this thread carries; R.5 uses corpus 1 only, per the design's own scope (§3 sizing).
- **The rung0 self-check's numeric target is a QA translation** (task spec §2.3), not R.4's own
  147/147 reproduced verbatim — a different, smaller, freshly-seeded sample at the same reference
  condition, passing a Wilson-CI-based criterion rather than an exact-count match.

## 7. Cross-references

- `2026-07-27-r5-hybrid-ladder-task-spec.md` — method, all operational choices (band/timing
  filters, rung-0 self-check translation, rung-3 rescaling, rung-4 reuse).
- `2026-07-27-1822-architect-r5-hybrid-ladder-design.md` — the design this executes; §3's reading
  table, applied in §3 above.
- `2026-07-27-1522-architect-r4-ruling-and-r4b.md` §2 — the search-band stop rule this arm's rung 0
  is built to satisfy from the start (200-2950 Hz, not 300-3300 Hz).
- `2026-07-27-r4-sensitivity-gap-findings.md`, `2026-07-27-r4b-realworld-sensitivity-findings.md` —
  the ~61% real-corpus endpoint and the 2.62 dB sensitivity edge this arm's rung 0/4 anchor to and
  extend.
- `2026-07-26-c3-candidate-generation-gap-findings.md` — the proximity/SIC proxy; §4 above adds a
  third, independent instrument (rung2->3 divergence) to the same "not raw sensitivity" direction.
- `artefacts/d001_r5_hybrid_ladder/` — `measurements.json`, `manifest.json`, `layout_stats.json`,
  `curves.json` (git-ignored, NFR-021; synthetic messages are Q-prefix by construction; real
  message text is used internally for the matched-population check §1 and never printed).
- `r5_hybrid_ladder.py` — the harness.
