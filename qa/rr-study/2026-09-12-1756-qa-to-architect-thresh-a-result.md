# `THRESH-A` — result: **`T2` fires** — the isolated-threshold loss is in bit formation, not candidate acquisition

QA, 2026-09-12 17:56Z (`date -u`, HK-017). Per spec
`2026-09-12-1724-architect-to-qa-spec-thresh-a-isolated-threshold-locus.md`, cleared to run
2026-09-12 17:24Z (Captain: "proceed with your recommendations"), `arch/thresh-a` `32e44313`.

**Headline: `T2` fires.** `CP95_hi(R_forced) = 1.02% < 0.20` (the T2 bar). Of the 546 cycles where
production misses the true cell in `R*` (`-21.0`..`-19.0` dB), a forced read at the exact true cell —
right frequency and time bin, snapped onto production's own lattice, no sub-lattice gain — recovers
**1 of them** on the BP path. **The isolated-threshold loss is overwhelmingly in bit formation
(L-BITS), not in finding/accepting the candidate (L-CAND).** `Δ50 = x50(P) − x50(F_BP) = 0.000 dB`:
handing production a perfect candidate stage at the true cell buys essentially nothing at this
threshold. Per spec §3.6, this licenses no candidate-stage follow-up arm; the only remedy on the
shelf for bit formation is the coherent extractor, which C-GAP-D has already ruled is not a D-001
treatment — that ruling stands untouched here.

---

## 1. HK-020 — critical config (checked against spec §3, not inherited from a header)

| config | value |
|---|---|
| Scene | NT's scene, verbatim: ONE Q-prefixed station/cycle, rotating `MSG-01`/`02`/`04`/`05` by `trial mod 4` (`700`/`1300`/`1900`/`2500` Hz), `dt_s=0.0` |
| Ladder | `-26.0..-16.0` dB nominal, `0.5` dB steps, 21 rungs × 250 trials, **all 21 get the P leg** (ROW 0b reproduction) |
| `R*` (primary, fixed pre-datum from NT's committed table, HK-021(y)) | `-21.0, -20.5, -20.0, -19.5, -19.0` dB — **only these 5 rungs also get the F leg**, every trial regardless of P's own outcome |
| Seed | `compute_seed('NHARD40-NT', rung_index, trial_index)` — the SAME seed namespace NT used, so this is a re-render of NT's own scene, not a new one |
| Legs | **P** (production): `decode_all(pcm)` at `(10, 0.10, 60)`. **F** (forced): `row0._forced_success(dec, pcm, f_inj, msg_text, true_dt_s=0.0)`, reused verbatim from `f-nbr-a` (applies the confirmed +0.16s waterfall-origin correction internally). Identical PCM, one process, one thread |
| Genuine (P) | `part_a.is_true` (payload) **and** `\|freq_hz − injected\| ≤ 4.0 Hz` (`part_b.FREQ_TOL_HZ`) — NT's own predicate |
| `M` / `H` | `M` = `R*` cycles with `¬genuine_P` (546). `H` = `R*` cycles with `genuine_P` (704) |
| Binary | `6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c`, shim `20260050` — `osd-fa-a/dll_pin.load_decoder(verify=True)`, ROW 0a |

New code: `qa/rr-study/thresh-a/run.py` (measurement, both legs), `row0c_lattice.py` (ROW 0c, static),
`analyse.py` (gate/descriptive, pure function of the persisted JSON). Reused verbatim (HK-018):
`osd-fa-a/part_nt.MESSAGES`/`build_truth`/`rung_index`/`rung_db`, `f-nbr-a/row0._forced_success`,
`f-nbr-a/scene_render.render_scene`, `osd-fa-a/part_a.is_true`, `osd-fa-a/part_b.FREQ_TOL_HZ`,
`harness.common.compute_seed`, `osd-fa-a/dll_pin.load_decoder`.

## 2. ROW 0

| row | check | result |
|---|---|---|
| **0a** | SHA-256 + shim pin | enforced by `dll_pin.load_decoder(verify=True)` — passed silently, shim `20260050` |
| **0b** | P-leg genuine counts, all 21 rungs, == NT's committed table | **EXACT MATCH, all 21 rungs**: `[0,0,0,0,0,0,0,1,0,5,30,78,155,207,234,248,250,250,250,250,250]`. Same scene, same binary, confirmed by re-derivation, not assumed |
| **0c** | the four `(f_inj, dt=0.16s)` forced-read positions land exactly on `ft8_extract_llrs_at`'s own lattice | **PASS, independently re-derived from `ft8_shim.c`'s own constants** (not just the spec's algebra): `symbol_period=0.16s` (from the shim's `f_min=200.0f`/`6.25 Hz/bin` comment), `min_bin=32` (exact integer, `200/6.25`), `freq_osr=time_osr=2`. All four `raw_freq_bin×2` and `raw_time_bin×2` are exact integers (160, 352, 544, 736; 2, 2, 2, 2) — checked to `1e-6`, see `row0c_lattice.py` |
| **0d** | positive control: `CP95_lo(R_ctrl) ≥ 0.90` | **`R_ctrl = 704/704 = 100.00%`, CP95 `[99.48%, 100.00%]`. PASS**, and by a wide margin — the forced read at the true cell reproduces every single one of production's own `R*` hits |
| **0e** | zero harness faults on leg F, `R*` | **0 faults, all 1,250 `R*` trials. PASS** |
| **0f** | power: `\|M\| ≥ 300` | **`\|M\| = 546`. PASS**, no top-up needed |

No VOID, no STOP, no top-up. Wall time: **559s (~9.3 min)** — well under the spec's 1–1.5h estimate
(single-position forced reads are cheap; the dominant cost is scene rendering, shared with the P leg).

## 3. The gate

```
|M| (R* misses, production)         = 546
|H| (R* hits, production)           = 704
k_BP  (forced BP-only successes, M) = 1
R_forced (BP-only) = 1/546 = 0.18%   CP95 [0.00%, 1.02%]   (Clopper-Pearson exact)
k_any (forced, incl. OSD path, M)   = 1   (reported, not gated — see §5; the 16 cycles where
                                            OSD was engaged all failed CRC/payload, so k_any == k_BP)
```

**Gate: `T2`** — `CP95_hi(R_forced) = 1.02% < 0.20` (the T2 bar). Independently re-verified
(`scipy.stats.beta.ppf`, exact).

This is a far more extreme result than the bar required: T2 only needed `CP95_hi < 20%`; the
observed point estimate itself is `0.18%`. **Essentially none of production's isolated-threshold
misses are recoverable by handing production the correct cell.**

## 4. Why this is not F-NBR-A's result wearing a different scene

F-NBR-A's forced read at station F (0/100, near-neighbour-contaminated cell) could not distinguish
"bit formation is hard" from "the neighbour's energy corrupts the LLRs at F's own cell" — that arm's
own scope note said so. `THRESH-A`'s scene has **no neighbour, no crowding, no channel effect**
(spec §0/§4) — the true cell here is clean by construction, and R0d's positive control (`704/704`)
confirms the forced-read pipeline itself is not the bottleneck: when the true cell already contains
a signal strong enough for production to decode it, the SAME pipeline recovers it 100% of the time.
The 546 misses in `M` are therefore not a pipeline artefact; they are cycles where the true cell's
own single-symbol, non-coherent, magnitude-only LLRs genuinely do not carry enough information for
BP to converge, even read at the exact right position.

## 5. `M`'s path distribution, cross-tabulated with success (report only, spec §3.7)

```
path=-1 (no decode reached CRC at all)          = 529 / 546  (96.9%)   success=False (all 529)
path= 1 (OSD engaged; CRC-valid, WRONG payload) =  16 / 546  ( 2.9%)   success=False (all 16)
path= 0 (BP succeeded)                          =   1 / 546  ( 0.2%)   success=True
```
[Line 2 corrected post-hoc, HK-022, 2026-09-14 — originally read "OSD engaged, CRC/payload still
failed". Per the Architect's re-derivation from this run's own per-cycle JSON: `crc_ok=1` on all
16 of these cycles. CRC did not fail — OSD produced a structurally valid, CRC-passing codeword
whose payload does not match the true transmitted message. See `BOARD.md`.]

**`k_any == k_BP == 1`.** ~~The 16 cycles where OSD was engaged (i.e. BP alone did not converge, so
the harness's `ldpc_decode_llrs` fell through to OSD at depth 2) **all failed** CRC or payload
match — OSD is invoked but recovers nothing extra at this population.~~ **CORRECTED (post-hoc,
HK-022, 2026-09-14): the 16 cycles where OSD was engaged (BP alone did not converge, so
`ldpc_decode_llrs` fell through to OSD at depth 2) all produced a CRC-valid, gate-passing decode
whose payload is wrong — not a CRC failure. At the true cell, OSD's own record here is 0 right /
16 wrong (2.93%): it is not idle and it does not "recover nothing extra," it is invoked and
confidently wrong every time. This does not change the gate** (`T2` is scored on `R_forced`,
which counts only correct-payload successes, so the gate reading is unaffected by this
reclassification) **but it is a materially different characterisation than the original text gave.**
So the "any path" reading is not more
generous than BP-only here: they are identical (`k_any == k_BP` — zero CRC-valid *correct-payload*
decodes either way). Even under that reading, **96.9%** of `M`'s 546
cycles produce no decode that reaches a CRC check at all, and ~~the LDPC error count for the 545
failing cycles runs `mean 7.35`, `median 7`, up to `20` hard-decision errors against a `174`-bit
codeword — nowhere near BP's convergence basin.~~ **CORRECTED (post-hoc, HK-022, 2026-09-14):
`ldpc_errors` is the count of unsatisfied parity checks (`ldpc.c:130`ff) against this code's 83
parity checks, not a hard-decision bit-error count against the 174-bit codeword, and it is only
meaningful for the `path=-1` population — the 16 `path=1` cycles reached OSD via a different code
path and were wrongly pooled into the original figure. Over the 529 `path=-1` cycles alone:
`mean 7.57`, `median 7` unsatisfied parity checks (of 83) — still nowhere near BP's convergence
basin, but the original `mean 7.35` both mislabelled the unit and pooled in a population it should
not have.**

`ldpc_errors` for the one BP success in `M`: `0` (a clean decode; this cycle was almost certainly a
true miss only because production's own candidate/acceptance logic passed it over, not because its
bits were marginal — the one case where L-CAND's contribution is visible, at `1/546`).

## 6. `Δ50` and the descriptive ladder (spec §3.7)

| dB | n | p_P | p_F_BP | p_F_any |
|---:|---:|---:|---:|---:|
| -26.0..-23.0 (7 rungs) | 250 each | 0.000 | n/a | n/a |
| -22.5 | 250 | 0.004 | n/a | n/a |
| -22.0 | 250 | 0.000 | n/a | n/a |
| -21.5 | 250 | 0.020 | n/a | n/a |
| **-21.0** | 250 | **0.120** | 0.124 | 0.124 |
| **-20.5** | 250 | **0.312** | 0.312 | 0.312 |
| **-20.0** | 250 | **0.620** | 0.620 | 0.620 |
| **-19.5** | 250 | **0.828** | 0.828 | 0.828 |
| **-19.0** | 250 | **0.936** | 0.936 | 0.936 |
| -18.5 | 250 | 0.992 | n/a | n/a |
| -18.0..-16.0 (6 rungs) | 250 each | 1.000 | n/a | n/a |

`p_F_BP` tracks `p_P` almost exactly within `R*` (the 1 BP recovery in `M` moves the `-21.0` dB cell
from `0.120` to `0.124`, everywhere else it is identical) — the direct, per-rung confirmation of the
aggregate gate result.

**`x50(P) = x50(F_BP) = -20.195` dB (nominal renderer units, linear interpolation). `Δ50 = 0.000
dB`.** A perfect candidate stage, at the true cell, buys **no** threshold sensitivity here. 🛑
Nominal renderer units — never compared numerically with S1b's on-air dB (spec §1).

**Positive-control complement (ROW 0d's own complement, spec §3.7):** cycles where `F` fails
although `P` succeeded, split by `R*` rung — **zero, every rung.** `R_ctrl = 100%` is not an
artefact of a lenient count; it holds rung by rung.

**False decodes/cycle, P leg, all 21 rungs: `727/5250 = 0.1385/cycle`** — reproduces NT's own
reference figure at `nhard=60` exactly, confirming this is the same production decode path NT
measured, not a harness drift.

## 7. Consequence (spec §3.6)

**`T2`** ⇒ per spec, no candidate-stage work may be described as a threshold treatment for this
population. The remedy on the shelf for bit formation is the coherent extractor — **not shippable**
(`ROW 0g-2`), and C-GAP-D's ruling that the coherent-LLR limb is not a D-001 treatment stands
**untouched**; this arm makes no D-001 claim (spec §4, §0). Whether to reopen Route B2 on
**sensitivity grounds only**, with its own acceptance test, is the Architect's/Captain's call, not
licensed by this result. I am not proposing that reopening; I am reporting `T2` and its size.

## 8. NFR-021

Q-prefix synthetic messages only (`part_nt.MESSAGES`: `MSG-01/02/04/05`). `run.py`/`analyse.py`
write/print counts, rates, and LDPC error integers only — no message text is logged to disk or
printed; the labeller consumes it in memory per-cycle.

## 9. Artefacts

`artefacts/thresh-a/_out/{thresh_a.json,analysis.json}` (gitignored, per standing convention),
`artefacts/thresh-a/logs/run.log`. Committed: `qa/rr-study/thresh-a/{run.py,row0c_lattice.py,
analyse.py}`, this report. Branch: `qa/thresh-a-result` (off `origin/main` post-`f91b9b8f` merge).
**Not pushed** (HK-033) — Captain's go needed for push/PR, same as every other QA-originated branch.
