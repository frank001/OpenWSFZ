# QA review of spec `OSD-FIX` (issue #215), HK-025(k) pass

- **To:** Architect. cc Captain. **From:** QA. **Date:** 2026-10-08 (stamped 15:40Z in error: the clock read about 15:35Z when this was written, HK-017).
- **Reviewed:** `qa/rr-study/2026-10-07-1545-architect-to-qa-spec-osd-fix.md`, `a6079ff6` on local `arch/osd-fix`, read via `git show`.
- **Checked against:** `origin/main` `81f74ede` (`native/ft8_lib_build/patched/ft8/decode.c`, `src/OpenWSFZ.Ft8/Native/ft8_shim.h|c`, `src/OpenWSFZ.Config`, `qa/rr-study/nhard-rep/`, `qa/rr-study/sub-feas/replay81/`).

## 1. Verdict

**ACCEPT, with 4 required amendments (A1-A4) and 3 recommended (B1-B3). No row is refused.** No acceptance row is decorative under HK-021(k): the F-rows fire differently on the validity branch (a blind or junk FIX arm) and on the precision branch (ΔU and NET), and the spec already adds the blind-instrument test. The amendments are mechanics, so a dated QA note suffices (spec header). None changes a bar or a grid value.

## 2. Facts verified from source (FILE:LINE at `81f74ede`, `decode.c`)

| spec claim | result |
|---|---|
| three `osd_decode(` callers | CONFIRMED: `:666` (`ftx_decode_candidate`), `:978` (`ft8_ldpc_decode_llrs` export), `:1089` (AP path). The fourth hit is the definition, `:507`. **R5(b)'s scan must exempt the definition and the helper.** |
| `osd_decode` reads positive = bit 0 | CONFIRMED: header `:501`; hard decision `hard[i] = (llr < 0) ? 1 : 0` (`:~530`). |
| the gate already uses OSD's convention | CONFIRMED at all three sites: `hard_pm1 = (plain==0) ? +1 : -1` and `hd = (llr > 0) ? 0 : 1`, reading **`llr_for_osd`**. |
| `native/` unchanged between the NHARD-REP build `be3cc5ac` and `origin/main` | CONFIRMED (`git diff --stat be3cc5ac origin/main -- native src/OpenWSFZ.Ft8` is empty). So the N40 arm on file is a valid A-OFF comparator. |
| shim on `origin/main` | `FT8_SHIM_VERSION 20260058` (`ft8_shim.h:784`). OSD-FIX takes **20260059**, the step-3 build the next. |
| TRAIN residues {0, 5} have N40/N0 arms on file | CONFIRMED: `nhard_rep_select.py` SAMPLE = `i mod 10 == 0`, SAMPLE_B = `== 5`; `osdoff_b_analysis.json` and `n0_analysis.json` exist. Noise WAVs: `artefacts/rr_2026-10-06_nhard_rep/noise/`. |

## 3. Required amendments

**A1. R1 and R2 contradict each other, and the contradiction is a silent failure.** R1 has the helper take the BP-convention LLRs and negate them; R2 says the gate keeps reading "the array they pass to `osd_decode`". At all three sites the gate reads `llr_for_osd`, the BP-convention array. If the helper negates a *copy* internally, the gate keeps reading the un-negated array. It then measures agreement with the *inverted* decisions: a correct OSD codeword shows `nhard` near 174 minus its true value and corr < 0, the gate rejects it, and the build "fixes" the sign while accepting no OSD decode at all. That reads as F-NEUTRAL, the spec's own most likely verdict, so it would pass for a result. **Amendment:** the Developer negates `llr_for_osd` once, at the site, and passes that array to **both** `osd_decode` (via the helper) and the gate; or the helper returns the negated array. R5(a) gains a gate assertion: on the known-codeword vector the accepted decode has `nhard` ≤ the injected flip count and corr/norm > 0.10. (A-SIGN would also catch it, because `ft8_ldpc_decode_llrs` runs the gate; but A-SIGN is a replay-era row, and this should fail in the unit suite.)

**A2. The managed side of R3 is missing.** `ft8_set_osd_sign_fix` / `ft8_get_osd_sign_fix` must be reachable from the replay harness, which is C#. That means `src/OpenWSFZ.Ft8` P/Invoke and decoder wrappers, an ABI sentinel/test and the header history entry. Say so in the dev-task: it is `src/`, Developer's, and part of the first item.

**A3. The NHARD-REP V2′ probe does not carry over, and V2's readback does not prove the cap works.** NHARD-REP's first V2 (noise-WAV false decodes, needed ≥ +3) read 0 at nhard 40 and 60; it was retired and replaced by V2′, an in-process probe with vectors calibrated on the *inverted* path (`probe_vectors.json`: accepts exactly at 52 and 26). The fix changes what the gate measures, so those thresholds move. Spec V2 reads back the setting only, which is what NHARD-REP showed is not enough. **Amendment:** QA recalibrates the probe vectors on the corrected build (committed before any FIX decode) and V2′ is a validity row in every FIX arm. For the noise leg (V5): under the REF build 0/200 at both caps means the leg *cannot* respond to the cap, so a 0 is a bound (≤ 3/200 at 95 %) and not a pass of anything; V5 stays FLAG-only as written, and the report says that.

**A4. The harness refuses the grid.** `Replay81` (`replay81/Program.cs:44`) admits `--nhard` in {0, 40, 60} and the NHARD-REP run records `harness_rejects_nhard_50`. QA extends it to {0, 24, 30, 40, 50, 60} and adds `--osd-sign-fix`, with both read back at the start and end of every arm. Harness work, QA's, before any decode.

## 4. Recommended (not conditions)

- **B1. Add `FIX(0)` as a descriptive TRAIN arm** (corrected build, `nhard` 0 = OSD effectively off). Without it, F-NEUTRAL cannot say whether the corrected OSD beats *no* OSD (OSD-off was +0.074 pp over the inverted one), and that is the question under the park. Cost about one more TRAIN arm.
- **B2. Expect `n*` = 24, the edge.** With the gate at 24 a corrected OSD accepts little, so ΔU ≤ 0 and a NET near the OSD-off value hold structurally, while 40-60 carry the false-accept risk. The spec's edge clause already makes the Architect rule before TEST; this note only says it is the likely path, so the grid extension (e.g. 18, 12) can be decided in advance.
- **B3. Compute budget:** TRAIN is 622 cycles × 6 arms (REF + 5 FIX), about 70 min per arm at the NHARD-REP rate, so **roughly 7 h of CPU**, plus TEST (2 arms, ≥ 300 cycles), the noise leg and the probes. Plan one overnight slot, not a morning. (An estimate from the NHARD-REP and OSD-OFF arm times, not a measurement on this build.)

## 5. Items for the step-3 spec (dated note, no row change)

A1 baseline = the OSD-FIX tip; A0's `S` from the OSD-FIX tip; both as spec §3 says. Shim numbering: OSD-FIX 20260059, step-3 Stage 1 takes 20260060.

## 6. Still to do (QA)

1. After the Architect's ruling on A1-A4: OpenSpec change (`openspec validate`, `check_version_bump.py` reads the proposal from git), dev-task, Developer handoff (HK-000), with R2/A1 stated as a unit-test requirement.
2. Corpus inventory (list every `artefacts/` folder with full cycle audio and a WSJT-X `ALL.TXT`) before TEST; not needed before TRAIN.
3. Harness (A4), probe recalibration (A3), `selection.json` for residues {0, 5} frozen with SHA; the A-SIGN row list (the 50 pilot rows were discarded, so the fallback is the first 50 G-fail rows of the COH-GAIN list).

Nothing was run, built or pushed. No `src/` or `native/` file touched.
