# `NHARD40-DEFAULT` `NT` — result: **`NT-S1`** fires, but `L0_B` reads the same as `L_B`

QA, 2026-09-12 09:45Z (`date -u`, HK-017). Per spec
`2026-09-12-0912-architect-to-qa-spec-nhard40-default-preregistration.md` §3, cleared to run
2026-09-12 09:15Z (PO: `BAR_S=0.05` frozen, Q2=M2), `arch/osd-nhard40-default` `c86ec2d`.

**Headline: `NT-S1` fires** — `CP95_hi(L_B) = 0.52% < BAR_S = 5%`. But **`L0_B` (the ceiling) reads
identically zero, `0/710`, same CI.** Every genuine near-threshold decode this scene produced is
byte-for-byte identical across all three `nhard` settings (60/40/0) — `p60(r) == p40(r) == p0(r)`
on **every one of the 21 rungs, with no exception.** That is exactly the reading the spec's own
§3.6 "ceiling" paragraph names: *"no `nhard` setting at all could cost more than `BAR_S` on this
scene, because the OSD path contributes too few genuine near-threshold decodes."* Directly
confirmed by a path probe (§5 below): **100% of genuine band-`B` decodes are BP-path, 0% OSD.**
`NT` therefore shows *isolated near-threshold single-station recovery in AWGN is unaffected by
60→40 because it never engages the mechanism the change touches* — it does **not** show that an
OSD-dependent near-threshold decode survives the change, because this scene never produces one.
🔴 **Whether that reading is sufficient for `G2` (spec §2) is the Architect's call, not mine — I
report the fork, I do not resolve it.**

---

## 1. HK-020 — critical config (checked against spec §3, not inherited from a header)

| config | value |
|---|---|
| Scene | ONE Q-prefixed station/cycle, rotating `MSG-01`/`02`/`04`/`05` by `trial mod 4` (`700`/`1300`/`1900`/`2500` Hz), `dt_s=0.0` |
| Ladder | `-26.0..-16.0` dB nominal, `0.5` dB steps, 21 rungs × 250 trials = 5,250 cycles |
| Seed | `compute_seed('NHARD40-NT', rung_index, trial_index)`, `trial_index` restarting at 0 per rung — the same within-rung counter drives BOTH the seed and the `trial mod 4` message rotation, disclosed as one convention, not two independent choices |
| Input contract | `normalise_rms(render_scene(seed), 0.20)` — applied to the raw `render_scene` float64 array (scale-invariant, same formula as `part_d.read_wav_normalised`/E1's contract; Parts A/B/E2 are unaffected, they decode the renderer's level directly) |
| Legs | `nhard` 60/40/0, `k_min_score_pass2=10`, `osd_corr_threshold=0.10` fixed, identical PCM, one process/one thread, switching between complete `decode_all()` calls (E1/E2's own ruled-safe scheme) |
| Genuine | `part_a.is_true` (payload, not text) **and** `\|freq_hz − injected\| ≤ 4.0 Hz` (`part_b.FREQ_TOL_HZ`) |
| Binary | `6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c`, shim `20260050` — enforced by `dll_pin.load_decoder(verify=True)` (ROW 0a), not a separate check |
| `BAR_S` | `0.05`, PO-ratified + frozen 09:15Z, before any `NT` datum |

New code: `qa/rr-study/osd-fa-a/part_nt.py` (measurement), `part_nt_analysis.py` (gate/descriptive,
pure function of the persisted JSON), `part_nt_replay.py` (ROW 0c). Reused verbatim (HK-018):
`dll_pin.load_decoder`, `scene_render.render_scene`, `row0_bc.bind_decode_params`, `part_a.is_true`,
`part_b.FREQ_TOL_HZ`, `harness.common.compute_seed`, `f-nbr-a/stats_common.clopper_pearson`.

## 2. ROW 0

| row | check | result |
|---|---|---|
| **0a** | SHA-256 pin | enforced by `dll_pin.load_decoder(verify=True)` at every leg's decoder construction — passed silently (no exception), both the main run and the independent ROW 0c replay |
| **0b** | bracket: `p60(-26.0) ≤ 0.05` and `p60(-16.0) ≥ 0.95` | **`p60(-26.0)=0.0000`, `p60(-16.0)=1.0000`. PASS, no extension needed** (both bounds cleared with large margin — 0/250 and 250/250 respectively) |
| **0c** | second-process determinism, seeded ~500-cycle sample, all 3 legs, element-wise | **500 cycles sampled round-robin across all 21 rungs (trial-major/rung-minor, so every rung is represented, not just the quiet end) → 1,500 (cycle,leg) comparisons, `0` mismatches.** Independent process, fresh `LdpcDecodeLLRs` instance, re-renders every cycle from its own seed rather than reading the main run's PCM. `qa/rr-study/osd-fa-a/part_nt_replay.py`, wall 106s |
| **0d** | power: `G_B ≥ 300` | **`G_B = 710`. PASS, no top-up needed** (spec's own worked estimate in §3.8 assumed `G_B≈500`; the realised transition is somewhat wider/righter than that blind estimate, giving more band-`B` mass, not less) |

No VOID, no extension, no top-up. Phase 1 wall time: **1,056s (~17.6 min)** (summed directly from
the per-rung log lines — the JSON's own self-reported `wall_s_total` field had a save()-accumulation
bug, harmless to every decode result, caught and fixed in `part_nt.py`; the persisted value was
corrected in place, disclosed here rather than silently overwritten).

## 3. Band B and the gate

**Band B** (`p60 < 0.95`, from the 60-leg only, before any comparison): 15 of 21 rungs,
`-26.0` through `-19.0` dB. The remaining 6 rungs (`-18.5..-16.0`) are excluded — `p60 ≥ 0.95` there
already, no near-threshold mass to lose.

```
G_B (genuine@60, band B)                = 710
K_B (of those, absent@40 -- killed)      = 0
C_B (of those, absent@0 -- ceiling)      = 0
L_B  = K_B/G_B = 0.0000   CP95 [0.0000, 0.0052]  (Clopper-Pearson, k=0, n=710)
L0_B = C_B/G_B = 0.0000   CP95 [0.0000, 0.0052]  (IDENTICAL to L_B's own CI)
```

Independently re-verified (`scipy.stats.beta.ppf(0.975, 1, 710) = 0.0051821...`, matching exactly).

**Gate: `S1`** — `CP95_hi(L_B) = 0.52% < BAR_S = 5%`.

**Report-only (HK-021(k), evaluated, does not move the row): "killed at 40 but present at 0" = 0.**
Trivially zero here since `K_B` itself is zero — nothing was killed at 40 for anything to be
recovered by the `nhard=0` leg.

## 4. 🔴 Why `S1` here needs the same caution as `E2-B1` — and what's different

`L0_B` (the ceiling — the most **any** `nhard` setting, including total OSD shutdown, could remove)
equals `L_B` exactly: **`0/710` both ways.** Per spec §3.6, this is the disclosed, anticipated
reading: *when the ceiling itself is indistinguishable from zero, the scene's OSD path contributes
too few genuine near-threshold decodes to be measured at all* — not that OSD-dependent near-threshold
decodes are safe, but that this scene never produced one to test.

**This is NOT the same defect as `E2`'s.** `E2`'s `S8HN` scene had **no near-threshold genuine
signal whatsoever** (`per_cycle_true` fixed at 11/12 in all 1,000 cycles) — the comparison was
undefined before any measurement. `NT`'s scene **does** have a real, measured near-threshold
transition (`p60` climbs `0.000 → 1.000` cleanly across `-22.0` to `-18.0` dB, §6 below) — `G_B=710`
genuine decodes exist in the band. The transition is real; what's absent is OSD's participation in
it, and that absence is now directly confirmed, not merely inferred from a leg-agreement:

## 5. Direct path probe (not aggregate-only)

To rule out "the 0/40/60 legs merely happen to agree" as a bookkeeping question, every genuine
band-`B` decode at 60 (all 710) was independently probed at its own reported `(freq, dt)` via
`extract_at` + `ldpc_decode_llrs` (the same probe `row0_bc.decode_and_count_osd` itself uses) and
its `path` field read directly (0=BP, 1=OSD, -1=extraction failure):

```
n_genuine (band B, 60-leg, probed) = 710   (matches G_B exactly)
path=0 (BP)    = 710
path=1 (OSD)   = 0
path=-1 (fail) = 0
```

**Every genuine near-threshold decode in this scene resolves via BP, none via OSD.** `nhard` gates
only the OSD path (base ROW 0b, `decode.c` fact 3) — a mechanism this scene's near-threshold
recovery never touches. A plausible physical reading, offered as commentary and not asserted as
mechanism (the spec's own §4 already flags the relevant calibration fact): `decode.c:41` calibrated
`nhard=60` against **S7, a co-channel/compounding scenario** — never against an isolated
single-station ladder. OSD's marginal value may concentrate in bit-error patterns that come from
collision/co-channel interference, not from an isolated station simply running out of SNR; if so,
no single-station near-threshold ladder, at any `nhard` value, would ever exercise it. **This is a
hypothesis, not a finding** — `NT` was not designed to test it, and I have not tested it here.

## 6. Descriptive (spec §3.7)

| dB | p60 | p40 | p0 | n |
|---:|---:|---:|---:|---:|
| -26.0 | 0.000 | 0.000 | 0.000 | 250 |
| -25.5 | 0.000 | 0.000 | 0.000 | 250 |
| -25.0 | 0.000 | 0.000 | 0.000 | 250 |
| -24.5 | 0.000 | 0.000 | 0.000 | 250 |
| -24.0 | 0.000 | 0.000 | 0.000 | 250 |
| -23.5 | 0.000 | 0.000 | 0.000 | 250 |
| -23.0 | 0.000 | 0.000 | 0.000 | 250 |
| -22.5 | 0.004 | 0.004 | 0.004 | 250 |
| -22.0 | 0.000 | 0.000 | 0.000 | 250 |
| -21.5 | 0.020 | 0.020 | 0.020 | 250 |
| -21.0 | 0.120 | 0.120 | 0.120 | 250 |
| -20.5 | 0.312 | 0.312 | 0.312 | 250 |
| -20.0 | 0.620 | 0.620 | 0.620 | 250 |
| -19.5 | 0.828 | 0.828 | 0.828 | 250 |
| -19.0 | 0.936 | 0.936 | 0.936 | 250 |
| -18.5 | 0.992 | 0.992 | 0.992 | 250 |
| -18.0 | 1.000 | 1.000 | 1.000 | 250 |
| -17.5..-16.0 | 1.000 | 1.000 | 1.000 | 250 each |

**50% point (linear interpolation): `-20.19` dB, identical at 60 and 40 (`shift = 0.0` dB).** The
`p60`/`p40`/`p0` columns are not merely "close" — they are **exact, row for row**, across all 5,250
cycles.

**False decodes/cycle** (noise-plus-weak-signal picture, complementing E1, HK-021(t) cost on the
complement): `60 = 0.1385`, `40 = 0.0025`, `0 = 0.0000` per cycle. This is the internal-consistency
check that the setting changes are real and taking effect — if the three legs were silently decoding
under the same setting, the false-decode rate would be identical too, and it is not (a `55×`
reduction 60→40, matching E1's own noise finding directionally).

## 7. NFR-021

Q-prefix synthetic messages only (`study-messages.json` `MSG-01/02/04/05`); no live data touched.
`part_nt.py`/`part_nt_analysis.py`/`part_nt_replay.py` write/print counts and booleans only — no
message text is logged (the labeller consumes it in memory and discards it per-cycle).

## 8. Where this leaves the arm (spec §2)

Per spec's strict-order gate table, `NT-S1` ⇒ *"the Architect asks QA to author the dev-task per
§1, carrying the PO's Q2 answer."* **I am not doing that yet.** §4 above is the reason: `L0_B`
reading identically to `L_B` means this specific `S1` is the weakest possible version of that
verdict — a scene that structurally cannot fail it, not one that was stress-tested and held. Per
HK-025, I am not refusing the row (it is not decorative — a real, measured near-threshold
transition exists, and the row does respond to what data there is); I am surfacing that the
scene's OSD-engagement is zero so the Architect can rule on whether that is sufficient for `G2` as
written, or whether `NT` needs a construction that guarantees some OSD-path engagement near
threshold before `S1` can be read as licensing the dev-task.

Artefacts: `artefacts/2026-09-12-nhard40-default-nt/{nt.json,nt_analysis.json,nt_run.log}`
(gitignored, per standing convention). Committed: `qa/rr-study/osd-fa-a/part_nt*.py`, this report,
branch `nhard40-default-nt-result` (based on `osd-fa-a-row0-part-d-result`, since `part_nt.py`
reuses that branch's own `dll_pin.py`/`part_a.py`/`part_b.py`/`row0_bc.py`, not yet merged to
`main`). **Not pushed** (HK-033).
