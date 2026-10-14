# SPEC — `OSD-FIX` (issue #215): correct the sign the OSD fallback reads, re-derive its gate, and show on the product that the fixed OSD is no worse than today's; PRIORITY 1 in the Developer's next build

- **To:** QA (owner: the OpenSpec change, `tasks.md`, the Developer handoff; HK-015 / HK-000). cc Captain. **From:** Architect. **Date:** 2026-10-07 15:45Z (`date -u`, HK-017).
- **Branch:** `arch/osd-fix` (local, off `origin/main` `81f74ede`). Docs only: `git diff --stat -- src/ native/` is empty. **The build is `native/`**: a separate Developer session (HK-011), a new shim number (next free; QA confirms on `origin/main`).
- **Authorised:** the Captain, Architect's window, 2026-10-07 ~15:3xZ: *"unpark #215. not switching it off but actually fixing it. this is hurting the first pass decode. make it part of the build with prio 1"*. This **reverses** the 2026-10-07 07:3xZ park of OSD-off. **This spec authorises the build and the replay. Merge (HK-010) stays the Captain's.**
- **Status:** PRE-REGISTERED for the acceptance rows (§5). QA may amend mechanics before any decode by a dated note. No row, bar or grid changes after any FIX-arm decode has run.

## 0. Evidence this rests on

| figure | value | source |
|---|---|---|
| the defect | extractor and BP: positive LLR = bit 1; `osd_decode`: positive = bit 0; the call sites pass the same `log174` un-negated. Three call sites at `origin/main` `81f74ede`: `decode.c:666`, `:978` (the `ft8_ldpc_decode_llrs` test export), `:1089` | issue #215; `grep osd_decode(` today |
| direct test | forced OSD on 50 real rows: **0/50** true payloads as shipped, **16/50** with the sign negated (all 16 were signals BP already decoded; 0 of 13 BP failures rescued) | QA, 2026-10-06, `ft8_ldpc_decode_llrs` |
| removing the inverted OSD | NET **+0.074 pp [+0.020, +0.146]** (K 7, G 0), replicated +0.079; not-confirmed per cycle **0.469 → 0.395** | OSD-OFF ruling `003d4f30` (build `be3cc5ac`, shim 20260058, `nhard` 40, 1-in-10 of `20261004_1634`) |
| a sign-CORRECTED OSD at WSJT-X's positions | GO arm **+0.051 pp** pooled (33 true vs 1,846 CRC-valid payloads that differ from WSJT-X's at that position; the pilot read +0.011 pp, 1 vs 271); C3O +0.26 pp | COH-GAIN reports; 🛑 the 1,846 are **unclassified** (WRONG-ID classified only the C3 fallback's wrongs, where 32 % were real neighbours) |
| what is **not** established | what a corrected OSD adds in the **product** (batch 1 and batch 2); its false-output rate on noise; which `nhard` is right for it. `nhard` 40 and corr 0.10 were set on the inverted output and do not carry over | #215 body |

**Read this honestly (the Architect's expectation, stated before any data):** the sign is a correctness defect and is worth fixing for that. The offline evidence says a corrected OSD is **not a large decode-rate lever** (+0.05 pp) and that the inverted one costs only about **0.07 pp**. The Captain's mechanism, that false first-pass decodes are subtracted from the audio and cost residual decodes, is plausible and **untested**; §5 measures it (mandatory descriptive rows) instead of assuming it.

## 1. What changes, in one paragraph

Every OSD call receives LLRs in OSD's own convention (positive = bit 0), by **one** helper the three call sites share (so a site cannot be missed), and the `nhard` / corr gate, which already uses OSD's convention, therefore measures the distance to the **true** hard decisions. The gate's `nhard` default is then re-derived on the corrected output (§5.2), because 40 was calibrated on chance-CRC output. A harness-only switch lets the replay run the old behaviour in the same build. Nothing else changes: not BP, not the extractor, not subtraction, not the early decode.

## 2. Requirements

| # | Requirement |
|---|---|
| **R1 one convention, one helper** | A single static function (e.g. `osd_call(const float *llr_bp, int depth, uint8_t *plain, …)`) negates the BP-convention `log174` into OSD's convention and calls `osd_decode`. All three sites call it. The Developer greps for `osd_decode(` and records every hit with FILE:LINE; a fourth caller in a later change must fail a unit test (R5), not review. |
| **R2 the gate follows** | The post-OSD corr/norm and `nhard` blocks keep reading the array they pass to `osd_decode` (OSD's convention), so they now measure agreement with the **true** hard decisions. The Developer shows this at each site with FILE:LINE and fixes the three header comments that say or imply the old convention (`decode.c` top-of-file R4/R5 block and the `osd_decode` header). `native/ft8_lib_vendor/ft8/ldpc.c:9` is upstream's comment, not touched. |
| **R3 harness-only switch** | An exported process-global setter `ft8_set_osd_sign_fix(int)` (default **1** = corrected), read per call, **not** wired to config, UI or API (like the `nhard` setter in spirit). Setting 0 reproduces the old behaviour **bit-for-bit** (A-OFF). A getter is exported so the harness can read it back. |
| **R4 `nhard` default** | Left at 40 in this build. §5.2 picks the value; the Developer changes the code default (and QA the station-config migration, if the value is not 40; HK-035: check how `decoder.nhard` is stored and whether a stored value overrides the new default, as the flag-ON migration of v0.54 did) in a **second, small commit** after the Architect's ruling. |
| **R5 tests** | (a) **Sign unit test, native:** an LLR vector for a known codeword with enough erasures/flipped signs that BP (50 iterations) fails and depth-2 OSD succeeds on the corrected path; assert payload equal with the switch at 1 and **no decode** at 0. (b) **No-bare-callers test:** a source scan in the test suite (or a link-level test) fails if `osd_decode(` appears outside the helper. (c) The all-ones word is not accepted as a codeword. (d) Existing OSD/gate tests re-baselined **only where they encoded the inverted behaviour**, each re-baseline listed in the PR with the reason. |
| **R6 diagnostics** | The existing `C:\Temp\nhard_diag.log` writes (`decode.c` near `:725`, `:1132`) are unchanged in this change. If the per-accept `nhard` and corr are not already returned to the harness, the Developer returns them (per accepted OSD decode: `nhard`, corr/norm, depth, batch), aggregates only, no text (HK-037). |
| **R7 flag-OFF-like identity** | With the switch at 0: same native calls, same outputs, same order as `origin/main` `81f74ede` (characterisation tests; A-OFF). |

## 3. Build ordering (what the Captain asked for)

OSD-FIX is the **first** item in the Developer's native queue and is stacked **under** the step-3 build (HK-008): step-3 Stage 1 starts on the OSD-FIX branch tip, not on `81f74ede`. Consequences for `2026-10-07-1330-architect-to-qa-spec-coh-fallback-step3-build.md` (a dated note from QA suffices; no row changes):

- **A1 baseline:** "identical to the pre-change build" means the **OSD-FIX tip** (with the fix at its default), not `81f74ede`.
- **A0's `S`:** computed from the OSD-FIX tip on the step-3 corpus.
- **U-OK basis check (§5.3 there):** the `[0.30, 0.65]` flag on the OFF arm's not-confirmed per cycle stays and is the safeguard: a corrected OSD moves that number, and the Architect rules on the reading first if it leaves the interval.
- `T1` (17.552 dB) is unaffected: the fallback is BP only.

## 4. Who decides what

| step | needs |
|---|---|
| native fix → replay | A-SIGN, A-OFF, unit tests green (QA verifies; Developer reports FILE:LINE) |
| `nhard` choice | the mechanical rule in §5.2, ruled by the Architect |
| merge to `main` | verdict row F-GO or F-NEUTRAL (§5.3), unit and characterisation tests green, **the Captain's sign-off** (HK-010). F-FAIL ⇒ the Architect rules and the Captain decides |

## 5. Acceptance (mechanical; each stop scoped to the outputs it guards, HK-021 (ab))

### 5.1 Native, before any replay

| row | predicate | guards |
|---|---|---|
| **A-SIGN** | R5(a) passes **and** on the 50 frozen pilot rows (QA locates them; if they are gone, the first 50 rows of the COH-GAIN frozen list at G-fail) forced OSD with the switch at 1 recovers **≥ 16/50** true payloads and with the switch at 0 recovers **0/50** (QA's own reading, reproduced) | the fix is real |
| **A-OFF** | R7: with the switch at 0, ALL.TXT lines, per-cycle multisets and native outputs equal `81f74ede`'s on QA's characterisation set **and** on the first 100 cycles of the TRAIN set vs the N40 arm on file (**0** cycles differ; on FAIL the N40 arm is re-run in full, as in NHARD-REP's V7) | the OFF arm of the replay is today's behaviour |

### 5.2 `nhard` for the corrected OSD (calibration on TRAIN, committed before TEST)

- **TRAIN:** `20261004_1634`, systematic 1-in-10 cycles at residues **{0, 5}** (the NHARD-REP samples; their N40/N0 arms are on file; 622 cycles). Frozen ordered `selection.json` with SHA before any decode.
- **Arms:** `REF` (switch 0, `nhard` 40: today) and `FIX(n)` for `n` ∈ **{24, 30, 40, 50, 60}** (switch 1, corr 0.10 unchanged), harness mode `two1`, subtraction ON as shipped, one build, DLL SHA pinned at the start and end of every arm, threads 8, Test B match rule, in-process (HK-037).
- **Rule (code, committed before any `FIX` decode):** `n*` = among the grid values with point estimate **ΔU_TRAIN(n) ≤ 0** (not-confirmed per cycle, FIX − REF), the one with the largest point estimate of NET_TRAIN(n) (FIX − REF, pp of WSJT-X's decodes); ties → the lower `n`. **If no grid value has ΔU ≤ 0 ⇒ verdict `FIX-NO-GATE`: no TEST run; the Architect designs a different gate (corr threshold, depth) for the Captain.**
- **Where the grid comes from (HK-038):** 40 is today's default; 60 was the earlier default and the NHARD-REP comparison point; 24, 30, 50 bracket them in steps the gate has already been run at (D-009 R5 range), **not** a measured optimum, because no corrected-OSD run exists. If `n*` lands on the grid's edge (24 or 60) QA says so and the Architect decides whether to extend the grid **before** TEST.

### 5.3 The decision replay (TEST; `n*` only)

- **Corpus:** QA lists **every** `artefacts/` folder with full cycle audio plus a WSJT-X `ALL.TXT` (feedback rule 2026-10-03) and picks **a 40 m night other than `20261004_1634`**. If none exists, TEST is `20261004_1634` at the residues `{1, 2, 4, 6, 8, 9}` (disjoint from TRAIN's {0, 5}; those cycles' decodes have not been used to choose anything here) and the report says so in its limits. ≥ 300 cycles, systematic, frozen `selection.json` + SHA before any decode.
- **Fixed:** as §5.2. Arms **REF** and **FIX(n\*)**, each in a fresh process, read back.
- **Estimands:** NET = 100 × Σ(`M_fix,i` − `M_ref,i`) / Σ`W_i`; ΔU = mean over cycles of (not-confirmed FIX − REF). 95 % block bootstrap, blocks of 40 consecutive cycles, ratio estimator for NET, B 10,000, seed 20261007.

**Validity (any FAIL ⇒ no verdict):**

| row | predicate |
|---|---|
| V1 | DLL pin equal at the start and end of every arm |
| V2 | `ft8_get_osd_sign_fix` (and `nhard`) read back as intended in every run; `selection.json` SHA identical in every run |
| V3 | 0 access violations, 0 contained exceptions, 0 non-zero exits |
| V4 | A-SIGN and A-OFF PASS |
| V5 | **noise leg:** the 200 noise WAVs of NHARD-REP's V2 (`artefacts/rr_2026-10-06_nhard_rep/`; QA locates and pins) through `FIX(n*)`: **false decodes = 0** ⇒ PASS; **≥ 1 ⇒ FLAG to the Architect, not an automatic FAIL** (the bar is the population's own reading under REF, which was 0/200 at `nhard` 40 and 60; a count above it is rulable, not a threshold I can justify in advance) |
| V6 | cycles with residual work abandoned ≤ 5 % in each arm (sub-feas replay design) |

**Verdict rows (exclusive, first match wins; on TEST):**

| row | predicate |
|---|---|
| **F-FAIL** | `CI_lo(ΔU)` > 0 (the fixed OSD adds not-confirmed decodes, i.e. false outputs) |
| **F-GO** | `CI_lo(NET)` > 0 **and** `CI_hi(ΔU)` ≤ 0 |
| **F-NEUTRAL** | otherwise (correct, not a measurable lever, not harmful) |

**Where the numbers come from (HK-038):** 0 is the decision value "no worse than what ships today": REF **is** today's behaviour (build `81f74ede` + switch 0), measured on the same cycles, not an older population. The bootstrap design is carried from the sub-feas / step-3 replays on this harness family. Nothing here uses the NHARD-REP or OSD-OFF numbers as a bar; they are reported beside the result.

**HK-025(k), both ways:** a fix whose switch is ignored gives NET = ΔU = 0 exactly and CI [0, 0] ⇒ F-NEUTRAL, which A-SIGN and V2 expose; so F-GO is the row that can fail. A fix that outputs junk gives ΔU > 0 ⇒ F-FAIL. QA adds a test that a doctored FIX arm identical to REF is reported as a blind instrument, not as F-GO.

**Descriptive, mandatory** (they test the Captain's mechanism and size the cost):
- NET and ΔU **by batch** (1 vs 2) and by SNR band A–D.
- **First-pass false decodes:** batch-1 not-confirmed per cycle, and residual-pass (batch 2) confirmed decodes per cycle, REF vs FIX. If the Captain's mechanism is real, the batch-1 not-confirmed falls and the batch-2 confirmed rises together; report both, no bar.
- OSD accepts per cycle (REF and FIX), their confirmed share, and the **`nhard` histogram (bins of 5) of confirmed vs not-confirmed OSD accepts** under FIX: this is the evidence any later gate is set on.
- Batch-1 and total decode wall time per cycle (median, p95), REF vs FIX.
- The FP-watch flag per band (sub-feas rule: `CI_lo` of FIX not-confirmed rate > `CI_hi` of REF's ⇒ FLAG).

## 6. Limits, stated in the report

One band, one night's audio, replay not live. Test B's not-confirmed count is an upper bound on false decodes (hashed `<...>` texts cannot match). `n*` is chosen on TRAIN and judged on TEST, which, if no second night exists, share a night. The 1,846 GO "wrongs" are unclassified, so the offline reading of a corrected OSD's false rate is open until TEST.

## 7. Predictions (blind; scored at the ruling)

| # | prediction | P | class |
|---|---|---:|:---:|
| OF1 | A-SIGN passes on the first native build | 0.85 | H |
| OF2 | some grid value has ΔU_TRAIN ≤ 0 (no `FIX-NO-GATE`) | 0.70 | H |
| OF3 | `n*` = 40 or lower | 0.55 | H |
| OF4 | TEST: F-NEUTRAL | 0.45 | H |
| OF5 | TEST: F-GO | 0.35 | H |
| OF6 | TEST: F-FAIL | 0.20 | H |
| OF7 | V5 noise leg: 0 false decodes | 0.75 | H |

⚠️ Calibration note: my HYPOTHESISED calls lean toward the tidy mechanism (CW3). OF5 is held below OF4 because every corrected-OSD figure on file is within 0.05 pp of zero.
