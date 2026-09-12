# `NHARD40-DEFAULT` `CC` — result: **`CC-S1` fires decisively** — zero genuine co-channel OSD rescues found, in any of the 5 families, and the 2026-06-20 R6 "genuine" population is directly shown to be false accepts

QA, 2026-09-12 10:25Z (`date -u`, HK-017). Per Amendment 1
`2026-09-12-1000-architect-to-qa-nhard40-default-amendment-1-cc-leg.md` §2, cleared to run
2026-09-12 ~10:00Z (PO: "Co-channel check first", `BAR_S=0.05` frozen for `CC` before any datum),
`arch/osd-nhard40-default` `f7faf15`.

**Headline: `CC-S1` fires** — pooled `CI_hi(L) = 0.18% < BAR_S = 5%`, and **every one of the 5
families independently clears the same bar** (`CI_hi` 0.6%–1.8%, all far below 5%) — the family
clause (§2.6) never comes close to firing. **`K = 0` and `C = 0`, pooled AND in every single
family.** Across all 4,300 station-cycles this battery produced, `nhard` 60→40→0 never changed a
single genuine payload's presence — not once, anywhere in S7's co-channel, near-collision,
time/freq-stagger, capture, or sweep geometries. Combined with the already-accepted `NT-S1`,
Amendment 1 §1 item 3 fires: **`NT-S1 ∧ CC-S1` ⇒ the dev-task (M2) is licensed.**

**The R6 question is answered directly, not inferred:** for parts 0–2 (`co_channel`), OSD-path
accepts at `nhard=60` numbered 75 (measured as `false@60 − false@0`, i.e. decodes present at 60 that
vanish entirely when OSD is shut off at `nhard=0`) — genuine ones **numbered zero**. **The
2026-06-20 R6 diagnostic's "genuine" population (90/92 OSD accepts in `nhard` (40,60]) was false
accepts, not genuine ones**, exactly the reading Amendment 1 §2.6 disclosed as possible if `C=0`.

---

## 1. HK-020 — critical config (checked against Amendment 1 §2, not inherited from a header)

| config | value |
|---|---|
| Scene | all 21 parts of `s7-compounding.json`, verbatim, 100 trials/part = 2,100 cycles; 5 families (`co_channel` 0–2, `near_collision` 3–7, `time_freq` 8–10, `capture` 11–14, `co_channel_sweep` 15–20) |
| Seed | `compute_seed('NHARD40-CC', part_index, trial_index)` |
| Renderer | `scene_render.render_scene` (12kHz), mirrors `run_scenario._render_compound`'s body exactly (encode each station clean, scale by relative `snr_db` via `channel.mix_to_shared_floor`, ONE shared seeded floor) — same mixing model, 12kHz vs `_render_compound`'s 48kHz only |
| Input contract | `normalise_rms(pcm, 0.20)`, same formula as `NT`/`part_d` |
| Legs | `nhard` 60/40/0, `k_min_score_pass2=10`, `osd_corr_threshold=0.10` fixed, identical PCM, one process/one thread |
| Unit / label | station-cycle; `present_L(s)` = payload match only (`true_codeword` compare, restricted to THIS station's own payload) — **no frequency condition**, deliberately (spec §2.3: a freq condition would relabel a genuine co-channel loss as junk, biasing toward `S1`) |
| CI | cycle-clustered bootstrap (2,000 resamples, seed `compute_seed('NHARD40-CC-BOOT',0,0) = 1148349359`); at `K=0`, replaced by `stats_common.clopper_pearson(0, N_cycles_with_G)`'s own upper bound — the SAME function `NT` used (HK-018), not a special case |
| `BAR_S` | `0.05`, PO-ratified + frozen ~10:00Z, before any `CC` datum, family clause included |
| Binary | `6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c`, shim `20260050` — enforced by `dll_pin.load_decoder(verify=True)` (ROW 0a) |

New code: `qa/rr-study/osd-fa-a/part_cc.py` (measurement), `part_cc_analysis.py` (gate/descriptive,
pure function of the persisted JSON), `part_cc_replay.py` (ROW 0c). Reused verbatim (HK-018):
`dll_pin.load_decoder`, `scene_render.render_scene`, `row0_bc.bind_decode_params`,
`harness.common.compute_seed`, `stats_common.clopper_pearson`, `part_d.cycle_clustered_bootstrap_ci`.

## 2. ROW 0

| row | check | result |
|---|---|---|
| **0a** | SHA-256 pin | enforced by `dll_pin.load_decoder(verify=True)` at every leg's decoder construction, both the main run and the independent ROW 0c replay — passed silently |
| **0b** | rendered signal list = `s7-compounding.json` for all 21 parts, field by field | Implemented as a pinned SHA-256 of the scenario file's own bytes (`aed34c69fbc55da91a28a9f2e7fcdfcf2b33db0fe3959f4eaacbb97d6e35761f`) plus a structural assert (21 parts, exact family part-index ranges, 2–3 stations/part) — byte-identical implies field-identical, and avoids retyping all 21 parts' fields by hand (a transcription-bug risk of its own). **PASS.** |
| **0c** | second-process determinism, seeded 300-cycle sample, all 3 legs, element-wise | **300 cycles sampled round-robin across all 21 parts (trial-major/part-minor, every family represented) → 900 (cycle,leg) comparisons, `0` mismatches.** Independent process, fresh `LdpcDecodeLLRs` instance, re-renders every cycle from its own seed. `part_cc_replay.py`, wall 91s |
| **0d** | power: `G ≥ 1,000` | **`G = 3,681`. PASS** (spec §2.8's own blind estimate: `G≈4,000`; realised is somewhat lower, still 3.68× the floor) |

No VOID. Main run wall time: **648s (~10.8 min)** across 21 parts (`part_cc.py`'s own per-part log
lines, checkpointed after each part).

## 3. The gate

```
POOLED (all 5 families, 2,100 cycles, 4,300 station-cycles, G=3,681)
  G = 3,681   K = 0   C = 0   gains = 0   net (K-gains) = 0
  N_cycles_with_G>=1 = 1,996 (of 2,100)
  L = 0.0000   CI [0.0000, 0.0018]  (CP95 upper bound, k=0, n=1,996)

FAMILY            G      K   C   CI_hi     N_cycles  N_with_G
co_channel        399    0   0   0.0183     300       200
near_collision    987    0   0   0.0074     500       500
time_freq         600    0   0   0.0122     300       300
capture           503    0   0   0.0092     400       400
co_channel_sweep 1,192    0   0   0.0062     600       596
```

**Gate: `CC-S1`** — pooled `CI_hi(L) = 0.18% < BAR_S = 5%`, **and no family comes anywhere close to
the family clause** (`CI_lo = 0` everywhere since `K=0` everywhere; the tightest family `CI_hi`,
`co_channel`'s 1.83%, is still more than 2.7× below the bar). This is not a borderline reading —
every one of the 6 numbers this gate depends on (pooled + 5 families) sits comfortably inside `S1`'s
own territory.

**Report-only (HK-021(k), evaluated, does not move the row): `gains` (station-cycles present@40 but
not@60) = 0, everywhere. `net = K − gains = 0`.** Removing decodes never changed what the decoder
subtracts in a way that surfaced a different station here.

## 4. What `C = 0` (pooled and per family) settles

Amendment 1 §2.6 disclosed this reading in advance: *"if `C = 0`, OSD rescues no genuine station
even in co-channel S7. Then S1 holds structurally, and the 2026-06-20 R6 'genuine' population was
false accepts."* **`C = 0` in every single family, with zero exceptions across 4,300 station-cycles.**
Combined with `NT`'s own `C_B = 0` (isolated AWGN), the finding now covers both conditions the
Architect's `NT` acceptance ruling named as untested: **no scene this instrument has measured —
isolated, near-threshold, or co-channel/compounding/capture — shows OSD ever recovering a genuine
payload that BP-only decoding would have missed.** Every genuine decode, in every family, resolves
identically at `nhard` 60, 40, and 0.

**This is the ceiling reading again, and it is the strongest possible version of `S1`, not the
weakest.** `NT`'s own `S1` was flagged (§4 of the NT result) as the weakest possible version, because
`NT`'s single-station AWGN scene had no reason to expect OSD engagement in the first place. `CC` is
different: this battery is the SAME S7 geometry `decode.c:41`'s comment cites as `nhard=60`'s own
calibration target, and it still shows `C=0` throughout. If OSD's marginal value exists anywhere in
this decoder's operating envelope, S7 compounding is the scenario built to exercise it, and it does
not fire here.

## 5. The R6 question, answered directly (spec §2.7)

```
parts 0-2 (co_channel), 300 cycles:
  OSD-path accepts at nhard=60 (false@60 - false@0) = 75
  of those, genuine (payload matches any station's truth, C)  =  0
  of those, false                                              = 75
```

**Every single OSD-path accept this measurement found in the co-channel family was false.** The
2026-06-20 R6 diagnostic's own methodology note assumed most of its 90/92 accepts were genuine
("rare spurious CRC coincidences … statistically minor") — the `NT` acceptance ruling had already
flagged that assumption as unverified (never payload-labelled, ~6 accepts/slot for 2–3 stations,
histogram indistinguishable from noise). **`CC` now tests it directly, on the same family of scenes,
and finds zero genuine OSD accepts where R6 implied dozens.** I am not asserting R6's own 90/92 were
literally these same decodes (different corpus, different date) — I am reporting that under a
fresh, payload-labelled measurement of the same scenario family, the "genuine OSD accept" event rate
is zero, which directly contradicts the assumption R6's own note made about its own population.

## 6. Descriptive (spec §2.7)

**Roles** (station-level presence, identical at all 3 legs — no row below has ANY 60/40/0
disagreement):

| role | p60=p40=p0 | n (station-cycles) | families |
|---|---:|---:|---|
| `strong` (capture, higher-SNR station) | 1.0000 | 400 | `capture` |
| `weak` (capture, lower-SNR station) | 0.2575 | 400 | `capture` |
| `equal` (all other families, equal-SNR stations) | 0.9080 | 3,500 | `co_channel`, `near_collision`, `time_freq`, `co_channel_sweep` |

The `capture` family's weak station recovers at 25.75% regardless of `nhard` — a real, large
sensitivity effect (capture ratio, not OSD) that `nhard` has zero influence over either way.
`co_channel`'s own `equal`-role rate is the lowest of the "equal" group at 57.0% (the family's own
tightest geometries: 0/−5dB pairs and a 3-station stack at Δ7–11 Hz) — still no 60/40/0 disagreement
anywhere within it.

**False decodes/cycle** (pooled across all 2,100 cycles, complementing `NT`'s own finding):
`60 = 0.2986`, `40 = 0.0143`, `0 = 0.0000` per cycle — a **21× reduction** 60→40, consistent
direction with `NT`'s `55×` and `E1`'s noise-only finding, at a scenario density (2–3 stations/slot)
that produces roughly double `NT`'s own false-decode rate at 60, as expected.

## 7. Consequence (Amendment 1 §1)

**`NT-S1 ∧ CC-S1` ⇒ item 3 fires: the dev-task (M2) is licensed**, carrying the PO's Q2 answer,
per Amendment 1's own restatement of base spec §1. I am not authoring the dev-task in this report —
per HK-033/HK-014 I hold for the Architect's acceptance ruling on this result first, same discipline
as `NT`.

## 8. NFR-021

Q-prefix synthetic messages only (`study-messages.json` `MSG-01/02/03`, text asserted against the
file at load time, not retyped blind); no live data touched. `part_cc.py`/`part_cc_analysis.py`/
`part_cc_replay.py` write/print counts, booleans, and message-shape assertions only.

Artefacts: `artefacts/2026-09-12-nhard40-default-cc/{cc.json,cc_analysis.json}` (gitignored, per
standing convention). Committed: `qa/rr-study/osd-fa-a/part_cc*.py`, this report, branch
`nhard40-default-nt-result` (unchanged branch — `CC` is the same arm's second leg, not a new
branch). **Not pushed** (HK-033 — this branch's own go is still outstanding, per the Architect's
own note in the CC clearance message).
