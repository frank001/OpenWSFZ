# `DENSITY-MECH` Amendment A1 — result: **A1-PASS1, unanimous** — production recovers F only via pass 1; single-pass extraction fails even at production's own reported position

QA, 2026-09-18 14:52Z (`date -u`, HK-017). Per spec
`2026-09-18-1356-architect-to-qa-spec-density-mechanism-oracle-position.md` §10.5, `arch/density`
`1a7f9547`. Diagnostic only — 🛑 **A1 carries no M1/M2 verdict** (spec's own instruction). Follows the
VOID ruling on the original `DENSITY-MECH` run (`qa/rr-study/2026-09-18-1433-qa-to-architect-density-
mech-result.md`, corrected in a separate commit).

**Headline: unanimous `A1-PASS1` in all three qualifying cells.** With pass 1 disabled
(`k_min_score_pass2 = 1,000,000`, `osd_corr_threshold`/`osd_nhard_max` otherwise left at the shim's own
defaults — `nhard=60`, not the live app's `40`; see §1), production decodes `F` **0/100 times** in every
cell — including the three where full two-pass production decodes it 94–100/100 on the same audio. The
oracle at **production's own reported position** (not the
textbook true position) also reads **0/100** in all three. Production's reported position turns out to be
within 0–1 Hz of the textbook true position anyway (see §4) — so this isn't a position story at all.
**Pass 1 (soft SNR-scaled tile suppression + a wider candidate net) is what recovers `F` where it is
recovered; pass 0 alone cannot, at any position tested.**

---

## 1. HK-020 — critical config

| config | value |
|---|---|
| Harness | Same binary/pin (`91997e38...`, shim `20260051`), same scene machinery, same seeds as `density_mech.py` — reused verbatim via `import density_mech as DM` (`DM.cell_signals`, `DM.F_TIME_OFFSET_S`, `DM.MAX_ITERS`/`DM.OSD_DEPTH`) |
| Cells | 6, each pinned to its **original** `part_index` so the rendered audio is bit-identical to the VOIDed run: `primary Δ=6.25/12.00/18.75 X=+1`, `strong Δ=12.00/18.75`, `primary Δ=12.00 X=+3` (excluded reference) |
| N | 100 trials/cell (single run — A1 is diagnostic, spec does not ask for a ROW 0b-style determinism double-run) |
| Params used ("prod") | `k_min_score_pass2=10, osd_corr_threshold=0.10, osd_nhard_max=60` — **read from the build**, `ft8_shim.c:478-480`'s compiled-in `s_k_min_score_pass2`/`s_osd_corr_threshold`/`s_osd_nhard_max` initial values. 🛑 **These are the RAW SHIM's defaults, not the live app's** — the shipped app sets `OsdNhardMax=40` through the managed layer (`DecoderConfig.cs:94`, `NHARD40-DEFAULT`, since 2026-09-12), confirmed on disk this session. This harness never called `ft8_set_decode_params` before A1, so every `prod` figure here and in the original run used the shim's `nhard=60`, not the live app's `40` — confirmed identical to the original run below (§3), not assumed. **`A1-PASS1` is invariant to this**: `osd_nhard_max` is a maximum-Hamming-distance rejection gate (stricter at a lower value), so `nhard=40` can only reject candidates `nhard=60` already rejects — `prod_p0=0/100` at `60` implies `0/100` at `40` too. **The same caveat applies to every direct-DLL harness that never calls `ft8_set_decode_params`**: `F-NBR-A`, `NBR-RERUN`, and this arm's own `prod` rates all ran at the shim's `nhard=60`, not the live app's `40` |
| Pass-1-disabled params | `k_min_score_pass2=1,000,000`, `osd_corr_threshold`/`osd_nhard_max` unchanged at production's values |
| Wall time | 412.5 s (6.9 min) |

New code: `qa/rr-study/density-mech/density_mech_a1.py`. Binds `ft8_get_last_candidate_counts` (not
previously bound by `ExtractLLRs`/`LdpcDecodeLLRs`); reuses `ft8_set_decode_params` (already bound by
`ExtractLLRs.__init__`).

## 2. `orc_P`'s position convention

`freq_hz` = production's own reported `freq_hz` (tone-0 convention, already confirmed via the original
run's ROW 0c). `time_offset_s` = production's own reported `dt` **used directly, with no `SYMBOL_PERIOD_S`
added on top** — `dll_common.py`'s own `B-orig-A` finding already established that `ft8_decode_all`'s
reported `dt` for a known-true-`dt`=0 station reads `~0.15999999...`, i.e. **already equals**
`dt_true + SYMBOL_PERIOD_S`. Adding the correction a second time on an already-corrected, decoder-reported
value would double it. Confirmed empirically below: measured `dt_offset_s` (production's reported `dt`
minus `F_TIME_OFFSET_S`) is `-3.6×10⁻⁹` in every cell — floating-point noise, i.e. **exactly zero**.

## 3. `prod` reproduces the VOIDed run exactly

| cell | `prod` (A1, fresh) | `prod` (original run) |
|---|---:|---:|
| primary Δ=6.25, X=+1 | 35/100 | 35/100 |
| primary Δ=12.00, X=+1 | 15/100 | 15/100 |
| primary Δ=18.75, X=+1 | 94/100 | 94/100 |
| strong Δ=12.00 | 100/100 | 100/100 |
| strong Δ=18.75 | 100/100 | 100/100 |
| primary Δ=12.00, X=+3 (ref) | 0/100 | 0/100 |

**Exact match, every cell** — confirms this harness's implicit defaults were identical all along: the
shim's defaults (`nhard 60`; the live app runs `40`), and `A1-PASS1` is invariant to it (§1). `prod`'s own
determinism (already proven in the original run's ROW 0b) extends
across scripts using the same seeds/binary.

## 4. `prod_p0`, `orc_P`, and the position offset

| cell | `prod` | `prod_p0` | pass-1 candidates seen (nonzero trials) | `orc_P` (of 100) | `orc_P` (of `prod` hits) | freq offset (Hz) | dt offset (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| primary Δ=6.25, X=+1 | 35/100 | **0/100** | 0/100 | **0/100** | 0.000 | −0.25 (constant) | ≈0 |
| primary Δ=12.00, X=+1 | 15/100 | **0/100** | 0/100 | **0/100** | 0.000 | +1.00 (constant) | ≈0 |
| primary Δ=18.75, X=+1 | 94/100 | **0/100** | 0/100 | **0/100** | 0.000 | +0.25 (constant) | ≈0 |
| strong Δ=12.00 | 100/100 | **0/100** | 0/100 | **0/100** | 0.000 | +1.00 (constant) | ≈0 |
| strong Δ=18.75 | 100/100 | **0/100** | 0/100 | **0/100** | 0.000 | +0.25 (constant) | ≈0 |
| primary Δ=12.00, X=+3 (ref) | 0/100 | 0/100 | 0/100 | n/a (0 `prod` hits) | — | — | — |

**Pass 1 confirmed disabled on every p0 trial, every cell** (`ft8_get_last_candidate_counts`'s pass-1
count was 0 on all 600 p0 decode calls, mechanically checked, not assumed).

**The position offset is tiny and fixed, not a "displaced candidate."** Every cell's frequency offset is
**constant across every hit trial in that cell** (min = mean = max exactly) — sub-lattice-quantum
(`K_FREQ_OSR=2` ⇒ 3.125 Hz quantum; the largest offset seen is 1.0 Hz, under a third of one quantum). The
time offset is zero to floating-point precision in every cell. **Production's own candidate genuinely
sits at (within rounding) `F`'s textbook true position** — this rules out `§10.2`'s second candidate
explanation ("production extracts at a displaced position") as the driver of these five cells. The
oracle at the true position and the oracle at production's own reported position are, for practical
purposes, **the same test**, and both read 0/100.

## 5. Readings (spec §10.5, cells with `prod` ≥ 0.80 only)

| cell | `prod_p0` | `orc_P` | read |
|---|---:|---:|:---:|
| primary Δ=18.75, X=+1 | 0.00 | 0.00 | **A1-PASS1** |
| strong Δ=12.00 | 0.00 | 0.00 | **A1-PASS1** |
| strong Δ=18.75 | 0.00 | 0.00 | **A1-PASS1** |

**Unanimous `A1-PASS1`.** Per spec §10.5: *"`A1-PASS1` would mean the oracle needs pass-1's suppressed
waterfall, which no export provides. That is a `native/` change (HK-011) and a Captain decision."*
`A1-POS`'s premise (production succeeds via a displaced pass-0 candidate) does not hold — §4's offset
data rules it out directly.

🛑 **A1 carries no M1/M2 verdict, and this report draws none.** What it establishes: in the cells where
`DENSITY-MECH`'s original oracle failed while production succeeded, production's success runs through
**pass 1 specifically** — its soft SNR-scaled tile suppression and/or its wider candidate net after
suppression — not through some pass-0 candidate at a different position that the original oracle simply
missed.

## 6. The excluded reference cell

`primary Δ=12.00, X=+3`: `prod=0/100`, `prod_p0=0/100`, pass-1 candidates 0 on every p0 trial. A
genuinely-excluded cell stays excluded with pass 1 disabled too — production's aggregate 2-pass exclusion
here isn't secretly being rescued by pass 1 some fraction of the time and then lost again; it's excluded
throughout, consistent with the original run's finding at this cell.

## 7. What this can't see

This diagnostic still can't distinguish suppression from the wider net **within** pass 1 — both changes
land in the same pass-1 code path, and A1 doesn't separate them (not asked to). It also can't say whether
pass 1's recovery mechanism would generalise beyond this scene's specific geometry (`E` at −5/+8 dB, one
interferer, synthetic AWGN) — same scope limit as the original arm (spec §5). It says nothing about `M1`
vs `M2` for the cells that stay excluded even in full two-pass production (the other 4 primary cells from
the original run, not re-tested here since `A1`'s cell set is fixed by spec §10.5 to the `prod`-succeeding
cells plus one reference).

## 8. NFR-021

Same discipline as the original arm: bit/rate/frequency/time space only, message text never printed.
`scan()`/`classify()` run clean against `density_mech_a1.py`, `results/density_mech_a1_result.json`,
`results/run_a1.log`, and this report.

## 9. Where this leaves the arm (spec §10.5's own routing)

**`A1-PASS1` unanimous → the oracle needs pass-1's suppressed waterfall to test further, and no export
currently provides it.** That is a `native/` change (HK-011) — I am not proposing one; per spec, this is
the Architect's and the Captain's decision on whether it's worth pursuing. `DENSITY-LIVE`'s ≈4.30 pp
remains unaffected either way — this whole thread is about *where* the loss happens in synthetic
single-pass extraction, not *whether* it happens live.

## 10. Artefacts

Committed by path (HK-014/HK-033 — **not pushed**, Captain's go needed): `qa/rr-study/density-mech/`
(`density_mech_a1.py`, `results/density_mech_a1_result.json`, `results/run_a1.log`), this report. Branch:
`qa/e4-bench`. No `src/`/`native/` change, no station time, no new capture.
