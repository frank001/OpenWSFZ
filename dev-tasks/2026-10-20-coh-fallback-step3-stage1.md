# Developer task: COH-FALLBACK (A' step 3), STAGE 1 - native core and diagnostic export, no product wiring

To: Developer. From: QA. Captain's go: 2026-10-20 ("go on both, step-3 build and stage 2"), after the Q-GATE-2 ruling G2-OK (`d1c13992` on `arch/coherent-limb2`).

## Read first (the design is the Architect's; this file is the handoff)
- **Spec:** `qa/rr-study/2026-10-07-1330-architect-to-qa-spec-coh-fallback-step3-build.md`, requirements R1-R13, section 3 (Stage 1) and section 5.1 (A0, A2). It lives on the Architect's local branch `arch/coherent-limb2`; read it in this repository with `git show arch/coherent-limb2:qa/rr-study/2026-10-07-1330-architect-to-qa-spec-coh-fallback-step3-build.md`.
- **Ruling that licenses Stage 1:** `git show arch/coherent-limb2:qa/rr-study/2026-10-20-1710-architect-q-gate-2-ruling.md` (section 5). The gate obstacle is cleared; "necessary, not sufficient": candidate search, noise-only false outputs and CPU cost are NOT established, and Stage 1 exists to measure them.
- **The reference code you port (our own, clean-room by its headers; no WSJT-X source):** `qa/rr-study/coh-gain/fine_sync.py`, `qa/rr-study/n2-coherent-llr-extractor/coherent_extract.py`, `qa/rr-study/coh-gain/cg_gate_features.py` (F1b), at QA branch commit `44c70ea2` (verified to exist) and unchanged since. `T1` = 17.552446 dB is a constant in code with a comment citing `qa/rr-study/results/2026-10-06-coh-gain/gate_thresholds.json`.

## Scope of Stage 1 (spec section 3)
1. `ft8_coherent_fallback_at(pcm, freq_hz, time_offset_s, ...)`: returns the estimate (df, dt, edge), F1b, the 174 V3 LLRs, the BP outcome (CRC, path, payload) and the elapsed time. BP ONLY (`osd_depth` -1, 50 iterations, production normalisation), then CRC-14. No OSD.
2. A cycle-level diagnostic export that applies the fallback to every eligible candidate of one `ft8_decode_all` call (R2: the ordinary decode's own candidates from `ftx_find_candidates`, every pass, that were NOT decoded in any pass) and returns counts and timing. Record where you keep the candidate list (FILE:LINE).
3. R3 anchor convention: derive and record (FILE:LINE) how a candidate's lattice position maps to the estimator's anchor `(f0, t0)` so the +-0.12 s / +-2 Hz window is centred on the signal. A2(d) tests it.
4. **No product wiring in Stage 1:** no config key, no flag, no change to `DecodeTwoStageAsync`/`MapNative`, no change to any existing export or struct. Flag OFF identity does not arise yet (Stage 2). New exports only; `Ft8NativeResult` / `ft8_shim.h` existing structs unchanged (say if you had to touch one).
5. An equivalent but faster computation than the Python is allowed (one shared downconversion per cycle, a precomputed per-cycle reference-peak grid for F1b) IF A2 passes; A2 is what "exactly" means. Do not use any external library beyond what the vendored tree already carries (licence policy: permissive only).

## Branch, base and shim number (QA checked on 2026-10-20)
- **Base: `origin/main`** (currently shim 20260062). `decoding_improvement` is 195 commits behind `main` and 45 ahead (shim 20260063, DI sync 6, 2026-10-18); it has not been synced, so do NOT base on it unless the Captain says so. The Architect's ruling said "decoding_improvement or a branch off it"; QA is raising the base with him and will tell you if it changes before you start.
- **Shim number: 20260066.** 20260063 is `decoding_improvement`'s, 20260064/20260065 are the #225 branch (`feat/dxpedition-decode-225`, not merged). Update `libft8.version.txt`, `FT8_SHIM_VERSION`, the managed constant, and the manifest as your convention requires. Expect a merge conflict in those files with #225 when it lands; keep your numbers distinct.
- New branch name of your choice (suggest `feat/coh-fallback-stage1`). You do not push; QA pushes on the Captain's go (HK-033).

## Tests and builds
- A native self-test (as `dxped_selftest.c` was for #225) covering: the estimator on clean synthetic signals, F1b monotonic with signal strength, BP-only decode of a known C3 vector, the unsupported/edge paths; plus a managed P/Invoke smoke test if you export to C#. Synthetic callsigns only (NFR-021).
- Unfiltered `dotnet test OpenWSFZ.slnx` (state the exact command; a filtered-out suite is silent, HK-022), and the ASan+UBSan self-test run AFTER your last edit.
- Windows `libft8.dll` and Linux `libft8.so` rebuilt; give both SHA-256 values. macOS `.dylib` is not part of this.

## Hand-back (your report)
Branch and commit SHA(s); `git diff --stat origin/main..HEAD`; the shim number; both library SHA-256 values; the R2 candidate-list location (FILE:LINE); the R3 mapping and its derivation (FILE:LINE); the test results above; the names of any equivalent-but-faster shortcuts and what they replace.

## Acceptance (QA runs; mechanical; the Developer does NOT run these)
- **A2 port fidelity** (spec 5.1): native vs the Python reference on the frozen COH-GAIN fresh-sample rows (the G-fail rows of the persisted samples; `gate_features.csv`, 4,949 F1b rows, present at `artefacts/rr_2026-10-07_coh_gain_gate/`): (a) BP outcome agrees on >= 99.5 %; (b) (df, dt) equal to the Python grid argmax on >= 99 %; (c) F1b within +-0.25 dB on >= 99 % and the gate decision equal on >= 99.5 %; (d) anchor convention on the first 100 cycles of the acceptance corpus.
- **A0 cost gate** (spec 5.1): p95 per-cycle fallback wall time <= `S`, with `S` computed by QA from today's build BEFORE any Stage 1 timing is seen and committed as a dated note. Do not run or publish A0 timing yourself; if you profile, say it is profiling and keep the numbers out of the hand-back's conclusions until QA has committed `S`.
- Stage 2 (product wiring, R6-R13) does not start until A0 and A2 pass and the Architect rules; its acceptance bars are being refreshed by the Architect (HK-038: the old U-OK basis is from an older era).
