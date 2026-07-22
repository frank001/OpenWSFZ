# Work Order — D-001 Runtime-Parameter Recall/False-Positive Pareto Sweep

**Date:** 2026-07-22
**Author:** QA
**For:** Developer (via Captain, per HK-000 handoff procedure)
**Branch:** `chore/d001-runtime-param-sweep` (tooling-only; no `src/` product or native-code
change is authorised under this work order — see Guardrails below)
**Source spec:** `dev-tasks/2026-07-22-d001-runtime-param-recall-fp-sweep-spec.md` — read that
document in full before starting. This work order operationalises its §3 Method into concrete,
file-level steps; it does not restate the rationale.

---

## 1. Context

D-001 (weak-signal/co-channel decode recall gap vs WSJT-X, issue #3) and D-009 (false-positive
gate calibration) sit on the same three runtime-configurable decode knobs
(`ft8_set_decode_params`, shim 20260030). The Captain is holding an H7 (MMSE joint demodulation,
3–6 months' cost) go/no-go decision open until three bounded groundwork passes are done. This is
the third — and the only one that can *directly* recover some recall rather than only describe
the gap. It costs no rebuild: sweep the three runtime knobs against the D-001 recall corpus and
the D-009 false-positive scenarios, and see whether any operating point dominates the shipped
baseline `(k_min_score_pass2=10, osd_corr_threshold=0.10, osd_nhard_max=60)`.

This is **analysis tooling**, not a product change: nothing under `src/` is expected to change.
The deliverable is a throwaway C#/Python harness under `qa/` plus a results report.

---

## 2. Actions

### 2.1 — Harness project scaffold

1. Create `qa/rr-study/d001-param-sweep-2026-07-22/` as a new C# console project
   (`.csproj`, target `net10.0`, matching the existing
   `qa/rr-study/diag-fp-engagement-survival-2026-07-18/FpEngagementSurvival.csproj` as a
   structural template for `ProjectReference`s and build settings).
2. `ProjectReference` **`OpenWSFZ.Ft8`** and **`OpenWSFZ.Abstractions`** only. Do **not** add
   `InternalsVisibleTo` for this new project and do **not** reach into `IFt8NativeInterop`
   (`internal`) — drive the decoder exclusively through the public
   `OpenWSFZ.Ft8.Ft8Decoder` class (`IModeDecoder.DecodeAsync`, and the public
   `Ft8Decoder.SetDecodeParams(int, float, int)` wrapper at `Ft8Decoder.cs:102`). This mirrors
   how the daemon itself drives the decoder and keeps the harness honestly exercising the
   production code path, not a bypass of it.
3. Note for sequencing calls: per `Ft8Decoder.cs:90-96`, `SetDecodeParams` writes to
   module-level native globals read only at the *start* of each `ft8_decode_all` call — it is
   **not** thread-affine the way `GetLastPassCounts`/`GetLastCandidateCounts`/AP-constraint
   snapshotting are (those genuinely require same-thread-as-`DecodeAll`, see
   `IFt8NativeInterop.cs:30-52`). It is safe to call `SetDecodeParams` once per grid point, then
   iterate `DecodeAsync` sequentially across all WAVs for that point. Do **not** parallelise
   decode calls across grid points in the same process run — that would race the shared native
   globals `SetDecodeParams` writes to.
4. Bring in a WAV reader for the raw 12 kHz mono PCM: link (via MSBuild `<Compile Include>`,
   not copy-paste) `tests/OpenWSFZ.Ft8.Tests/WavReader.cs` into the harness project. It already
   validates 12 kHz/mono/16-bit PCM and returns the normalised `float[]` `DecodeAsync` expects
   — do not reimplement it.

### 2.2 — Recall-arm inputs (07-07 off-air corpus)

5. Read all `artefacts/20260706_live_run_2308/save/*.wav` (4,075 files) via `WavReader`. Confirm
   each is exactly 180,000 samples (15 s × 12,000 Hz) per file; log and skip (do not throw on)
   any file that isn't, and report the skip count in the final report — a silent skip would
   quietly undercount recall.
6. The reference file for scoring is `artefacts/20260706_live_run_2308/WSJT-X ALL.TXT`
   (unchanged — never write to this file).
7. **Held-out split (§4.4a of the spec):** sort the 4,075 WAVs by their embedded timestamp and
   split into a first-half **tune** set and second-half **validate** set. Run the full 45-point
   grid (§2.4 below) on **tune** only to pick a candidate point; then separately score that one
   candidate point (plus the baseline) against **validate** to report whether the recall gain
   holds out-of-sample. Report both numbers — do not report only the tune-set result as if it
   were confirmatory.

### 2.3 — False-positive-arm inputs (S5 + S7 synthetic) — requires a small harness-generator change

8. The existing S5/S7 scenario generator (`qa/rr-study/harness/run_scenario.py`) synthesises PCM
   in-process and plays it live through a PortAudio device into VB-CABLE (see `_play_samples` /
   `_render_noise` / `_render_compound`); `--dry-run` only skips the *playback* step, it does not
   persist the rendered samples anywhere. Add a new **`--dump-wav-dir <path>`** CLI option (in
   addition to `--dry-run`, not replacing it) that, when set, writes each rendered slot's PCM
   (before playback) to a 12 kHz mono 16-bit PCM WAV file under that directory instead of/as well
   as playing it, named so it can be paired back to the corresponding `truth.csv` row (e.g. by
   `part_index`/`trial_index`/`seed`, whatever `_run_pairs`/`_append_truth` already key on — reuse
   those fields verbatim rather than inventing a new naming scheme). This is the only change to
   an existing script this work order authorises; it is additive and gated behind a new flag, so
   the existing playback path (used by the live corpus-replay workflow) must be provably
   unaffected — run the script once with and once without the flag on the same scenario and
   `diff` the resulting `truth.csv` to confirm identical output.
9. Run `harness/run_scenario.py qa/rr-study/scenarios/s5-noise.json --dry-run --dump-wav-dir
   <somewhere>` and the equivalent for `s7-compounding.json`, once each, to produce the WAV
   corpora + `truth.csv` for the FP arm. These are generated once and reused across all 45 grid
   points (the PCM itself does not depend on the decode-side parameters being swept).
10. `matcher.py` expects a run directory containing `truth.csv`, `wsjt-all.txt`, and
    `owsfz-all.txt` (`qa/rr-study/harness/matcher.py:2-4,49-70`). For S5/S7 you only need the
    `owsfz-all.txt` side — there is no live WSJT-X run to pair against for this synthetic FP arm,
    so pass `--wsjt <an empty-but-well-formed ALL.TXT>` or check whether `matcher.py` already
    tolerates a zero-row WSJT file for FP-only scoring (it computes `false_positive` from
    `truth.csv` vs `owsfz-all.txt` alone per scenario semantics) — confirm this from
    `harness/common.py`/`matcher.py` before assuming; do not guess.

### 2.4 — The sweep driver

11. Implement the 5×3×3 = 45-point grid exactly as specified in §3.1 of the spec:
    - `k_min_score_pass2 ∈ {5, 7, 10, 15, 20}`
    - `osd_corr_threshold ∈ {0.10, 0.15, 0.25}`
    - `osd_nhard_max ∈ {40, 60, 80}`
    - The baseline `(10, 0.10, 60)` **must** be one of the 45 points, never a separate special
      case — it needs to go through the identical code path as every other point so the "delta
      vs baseline" comparison is apples-to-apples.
12. For each of the 45 points, in order:
    a. `decoder.SetDecodeParams(k, corr, nhard)`.
    b. Recall arm: `DecodeAsync` every WAV in the **tune** half of the 07-07 corpus (§2.2); write
       results in WSJT-X `ALL.TXT` format to a per-point file. Reuse the exact line format from
       `src/OpenWSFZ.Daemon/AllTxtWriter.cs:99` —
       `{timestamp}     {dialMhz:F3} Rx FT8 {snr,6} {dt,4:F1} {freq,4} {message}` — byte-for-byte,
       since `classify_cochannel.py`'s `parse()` depends on exact column alignment. (You do not
       need `AllTxtWriter`/`IConfigStore` itself — that class is daemon-wired to live config; just
       match its format string.)
    b'. Also run the **validate** half for the baseline point and for whichever point in step 13
        below turns out to be the sole candidate — not for all 45 (that would defeat the point of
        holding data out).
    c. FP arm: `DecodeAsync` every WAV in the S5 corpus, then every WAV in the S7 corpus (§2.3);
       write each to its own `owsfz-all.txt` under a per-point run directory alongside the
       `truth.csv` generated in step 9 (copy or symlink `truth.csv`/`wsjt-all.txt` into each
       per-point run dir — do not regenerate the synthetic corpus per point, only the decode
       output changes).
13. Recall scoring: `classify_cochannel.py`'s `classify_session()`
    (`qa/rr-study/results/2026-07-07-b4bdf88-d001-cochannel-attribution/classify_cochannel.py:89`)
    currently hardcodes `session_dir = ARTEFACTS / dirname` and reads
    `"OpenWSFZ ALL.TXT"`/`"WSJT-X ALL.TXT"` from that fixed path — it must **never** be pointed at
    the real `artefacts/20260706_live_run_2308/` directory for this sweep (that directory holds
    the one real captured baseline and must not be overwritten by synthetic per-point output).
    Import and reuse its scoring functions (`parse`, `sig_key`, `freq_bin`, `is_hashed`, the
    Tight/Partial/Isolated `classify()` closure, and the band restriction) against your own
    per-point directory layout — either by adding an explicit directory parameter to
    `classify_session` (preferred: a minimal, additive signature change, default value preserves
    existing call sites) or by writing a thin driver in the sweep project that imports the module
    and calls its functions directly with your own paths. Do not reimplement the classification
    logic from scratch — it is the one true agreement algorithm Option B established and this
    sweep must stay comparable to it.
14. FP scoring: run `matcher.py --run-dir <per-point-S5-dir> --scenario S5` and
    `--run-dir <per-point-S7-dir> --scenario S7` for every point, unmodified.
15. Emit one CSV row per grid point with: `(k, corr, nhard)`, overall recall %, per-class
    (Tight/Partial/Isolated) recall %, recall Δpp vs baseline, S5 FP rate, S5 FP Δ vs baseline,
    S7 FP rate, S7 recovery %, S7 FP Δ vs baseline. This is the primary data artefact for the
    report.

### 2.5 — Pareto verdict and report

16. Identify the Pareto frontier per §3.5 of the spec: a point only counts as a candidate "win"
    if **both** S5 FP rate and S7 FP rate are `≤` the baseline's (§3.4's two-sided rule — a
    recall gain with either FP arm regressed is reported as a trade-off, never as a win, and never
    averaged into a single blended score).
17. Draft `qa/rr-study/results/2026-07-22-<sha>-d001-param-sweep/report.md` containing: the full
    45-row grid table, the Pareto-frontier identification, the per-class recall breakdown for the
    best point(s), the tune/validate split result for the chosen candidate (step 12.b'), and one
    of the three headline verdicts from spec §3.5 (dominating point / strict trade / baseline
    dominates) with the corresponding recommendation (ship-after-live-A/B / no-change /
    scope-Phase-2). **Leave report.md Sections 1 and 5 as `TODO — QA` stubs** — per HK-001, QA
    authors those sections, not the developer. Everything else (the data sections) is yours.
18. Commit the harness project, the `run_scenario.py` `--dump-wav-dir` addition, the 45-point CSV,
    and `report.md`. Do **not** commit the S5/S7 `truth.csv`, the generated WAV corpora, or any
    per-point `owsfz-all.txt`/`OpenWSFZ ALL.TXT` files — these stay local/git-ignored exactly as
    the rest of the R&R study handles them (confirm with `git status`/`git check-ignore -v`
    before pushing, don't assume the existing `.gitignore` patterns already cover your new
    per-point directory names — extend `.gitignore` if they don't).

---

## 3. Guardrails — what this work order does NOT authorise

- **No `src/` changes.** Nothing in `src/OpenWSFZ.Ft8`, `src/OpenWSFZ.Daemon`, or any other
  product project should appear in the diff. If you find yourself needing one, stop and flag it
  to QA/Captain rather than making it — that would be D-001/D-009 product work, out of scope for
  this tooling pass.
- **No native/shim rebuild.** All three knobs are exercised at runtime through the existing
  `ft8_set_decode_params` entry point. `K_MIN_SCORE`, `K_MAX_CANDIDATES`, LDPC iteration count,
  and OSD `ndeep` are compile-time constants and explicitly out of reach here (spec §4.6/§5).
- **No live capture.** Both arms run against already-retained data (07-07 off-air WAVs;
  synthetic S5/S7 scenario renders). Do not open a live capture session for this pass.
- **`run_scenario.py`'s existing live-playback path must be provably unaffected** by the
  `--dump-wav-dir` addition (step 8's diff check is not optional).
- **Not a shippable production default on its own.** Even a clean Pareto-dominating point is a
  *candidate* — the report should say so explicitly and recommend the confirmatory live A/B
  (spec §4.4b), not present the sweep result as ready to ship.

---

## 4. Acceptance criteria (what QA will check on review)

1. `git diff` touches only `qa/` and `dev-tasks/` (plus, if unavoidable, a `.gitignore` addition)
   — nothing under `src/`.
2. The harness builds against `OpenWSFZ.Ft8`/`OpenWSFZ.Abstractions` public API only — no
   `InternalsVisibleTo` added for the new project, no direct use of `IFt8NativeInterop`.
3. All 45 grid points present, baseline `(10, 0.10, 60)` included as an ordinary point, not a
   special-cased outlier.
4. Every recall number in the report has its paired S5/S7 FP numbers from the *same* point
   sitting next to it — no recall-only table anywhere (spec §4.1, the D-009-origin rigour rule).
5. Per-class (Tight/Partial/Isolated) recall breakdown present for at least the baseline and the
   best candidate point(s), reusing `classify_cochannel.py`'s classification logic verbatim (spot
   check: pick one grid point, hand-verify a few Tight/Isolated calls against its output).
6. Tune/validate split actually implemented and both numbers reported for the chosen candidate —
   not just the tune-set number presented as final (spec §4.4a).
7. `run_scenario.py`'s pre-existing playback behaviour is unchanged — the diff-check from step 8
   is in the PR description or report, not just asserted.
8. Nothing under `qa/rr-study/d001-param-sweep-2026-07-22/` commits raw truth/decode data files
   (`truth.csv`, `owsfz-all.txt`, `OpenWSFZ ALL.TXT`, generated WAVs) — verified via `git status`
   / `git check-ignore -v`, not assumed (NFR-021).
9. `report.md` Sections 1 and 5 are left as QA stubs, not authored by the developer (HK-001).
10. `python3 tools/pre_merge_check.py` green before this is called ready for merge (HK-006) —
    this still applies even though the change is `qa/`-scoped, since it is a real PR to `main`.
11. The final §3.5 verdict is one of the three headline outcomes the spec defines, stated
    unambiguously, with a recommendation attached — not left as an open question.

---

## 5. References

| Reference | Why |
|---|---|
| `dev-tasks/2026-07-22-d001-runtime-param-recall-fp-sweep-spec.md` | The full spec this work order operationalises — read first |
| `qa/rr-study/results/2026-07-07-b4bdf88-d001-cochannel-attribution/report.md` + `classify_cochannel.py` | Option B verdict/ceiling this sweep is measured against; the recall-scoring logic to reuse, not reimplement |
| `src/OpenWSFZ.Ft8/Ft8Decoder.cs` (`SetDecodeParams`, `DecodeAsync`) | The public API surface the harness must drive through |
| `src/OpenWSFZ.Ft8/Interop/IFt8NativeInterop.cs` | Why `SetDecodeParams` is thread-safe per-point but the pass/candidate-count getters are not — do not conflate the two |
| `src/OpenWSFZ.Abstractions/DecoderConfig.cs` | Confirms the shipped defaults `(10, 0.10, 60)` and documented valid ranges |
| `src/OpenWSFZ.Daemon/AllTxtWriter.cs` | The exact ALL.TXT line format the harness's output must match byte-for-byte |
| `tests/OpenWSFZ.Ft8.Tests/WavReader.cs` | WAV→float[] reader to link into the harness, not reimplement |
| `qa/rr-study/diag-fp-engagement-survival-2026-07-18/` (`.csproj` + `Program.cs`) | Structural template for a throwaway in-process C# QA harness project |
| `qa/rr-study/harness/run_scenario.py` | S5/S7 scenario generator; needs the additive `--dump-wav-dir` flag (step 8) |
| `qa/rr-study/harness/matcher.py` + `qa/rr-study/harness/common.py` | FP-arm scorer; confirm its WSJT-side tolerance for the synthetic-only FP arm before assuming |
| `qa/rr-study/STUDY-SPEC.md` §6.2, S5/S7 entries | Scenario definitions and rationale |
| HK-000, HK-001, HK-006 (`MEMORY.md`) | Handoff procedure, report-authorship split, and the pre-merge gate this still owes |

---

## 6. Once implementation is complete

**Captain's decision (2026-07-22): this proceeds as a plain PR, not an OpenSpec change** — it is
QA tooling only, nothing under `src/` moves, so no `openspec/changes/` entry or `/opsx:verify`
step applies. Open the branch, push, open a PR against `main` in the usual way. Do not merge it
yourself: hand back to QA for the normal review pass (this work order's §4 acceptance criteria)
and the `pre_merge_check.py` gate (HK-006) before it touches `main`.
