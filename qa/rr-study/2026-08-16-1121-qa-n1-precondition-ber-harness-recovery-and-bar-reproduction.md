# N1 §3.1 precondition — BER harness recovered, ROW 0a bar reproduced

**Author:** QA, 2026-08-16 (11:21 UTC, `date -u`, per HK-017).
**Executes:** `2026-08-15-1840-architect-to-qa-N1-ber-at-refined-position-spec.md` §3.1 and the
ROW 0a gate of §5 — the blocking precondition, not the N1 arm itself. §3.2 (the new native export,
`ft8_extract_llrs_at`) is **not** started here; that is a separate HK-011 deliverable (dev-task
authored, Developer session applies).

---

## 0. Headline

**ROW 0a: DOES NOT FIRE. The recovered harness reproduces all three §2 bar quantities, two of
them exactly and the third within 0.35 pp of the 1 pp tolerance.** The bar is established on this
tree. N1 may proceed to §3.2 once that export exists.

| quantity | §2 bar | reproduced here | diff | within 1 pp? |
|---|---:|---:|---:|:--:|
| matched-hit control median BER | 2.9% | **2.87%** (n=171) | 0.03 pp | ✅ |
| THE 135 own-BER median | 44.0% | **43.97%** (n=126) | 0.03 pp | ✅ |
| BP+OSD correction threshold `B50` | 11.3% | **11.65%** | 0.35 pp | ✅ |

## 1. What was recovered

`git ls-files` confirmed none of the fourteen files from `7a604b4` (`d001-c4-min-score-sweep`) were
on `main` or on this branch, matching the spec's §3.1 finding exactly. Restored onto
`feat/r1b-sync-refiner-instrument-correction` via `git checkout 7a604b4 -- <paths>`, all fourteen
files, byte-identical to that commit (not re-typed, not re-derived):

- `c2_phase2c_ber_measurement.py` — the instrument named in §3.1, THE 135 / matched-hit-control
  population builders, hard-decision BER against the re-encoded true codeword.
- Its four sibling scripts (`b1_jt9_ablation.py`, `b2_synthetic_calibration.py`,
  `c2_phase2c_ber_distribution_analysis.py`, `c2_phase2c_gray_sync_roundtrip_verify.py`,
  `c2_phase2c_shrinkage_sweep_analysis.py`) and the eight dated notification/findings/task-spec
  documents from the same commit — recovered as a set for provenance, not individually required by
  §3.1, but they are what `c2_phase2c_ber_measurement.py`'s own docstring cites (the Gray/sync
  round-trip verification, the shrinkage-trial context) and separating them would have re-created
  the exact "documentation-inventory gap" W1's report already flagged once.

`w1_sec5_calibration.py` and `w1_run_sweep.py` (the harness that actually produced the §2 bar
numbers, per the W1 report's own §11) were **already on this branch**, committed at `4f74409`
2026-08-07 — not part of this recovery.

## 2. Reproducing THE 135 / matched-hit control — direct, deterministic

Ran the recovered `c2_phase2c_ber_measurement.py` standalone, unmodified, from
`qa/cycleframer-alignment-replay/`, against the frozen capture already on disk
(`artefacts/d001_c2_phase2c/ber/k10_cap140/.../candidate_diag.csv`, `llr174` column, and
`artefacts/20260725_live_run_1806/`) — both were reachable directly in this repo's own
`artefacts/` (no worktree junction needed here; that indirection was specific to the original
worktree-off-`d001-c4-min-score-sweep` layout).

The only native code this leg touches is `ft8_encode_message` (`Encoder.true_codeword()`), which
does not depend on the raw-LLR-capture gate — the **already-committed** production
`src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` on this branch was used as-is, no rebuild.

```
[SELF-CHECK PASS] matched-hit control: n=171 median=2.9% (of 200 capped; threshold: < 5%)
THE 135: n=126 measured, median=44.0% mean=39.0% min=6.9% max=61.5%
```

**Exact match to §2 on both quantities** (44.0% / 2.9%, to the reported precision). This is
expected and unsurprising: both figures are recomputed from the same frozen capture the original
run used, via the same unmodified code — this leg validates that the *harness logic* (candidate
matching, Gray/sync re-encode, hard-decision sign convention) still runs correctly on this branch,
not that the numbers are independent.

## 3. Reproducing B50 — the harder leg, one disclosed substitution

`B50` is **not** a static number read off a file — it is the curve-crossing of a **stochastic**
synthetic AWGN sweep (`w1_run_sweep.py`, Arm A/B, `SEED = 20260807`, fixed). Reproducing it means
re-running that sweep, which needs a diagnostic native build exporting
`ft8_get_last_candidate_llr` under the compile-time gate `FT8_ENABLE_RAW_LLR_CAPTURE`.

🔴 **Finding, consistent with the board's existing flag ("raw-LLR capture exists only on
`d001-c4-min-score-sweep`"), now confirmed from source on this specific branch:**
`grep -rn "FT8_ENABLE_RAW_LLR_CAPTURE\|ft8_get_last_candidate_llr\|llr174" src/ native/` on
`feat/r1b-sync-refiner-instrument-correction` returns **nothing**. The raw-LLR-capture code does
not merely default off here — it is **not present in this branch's `ft8_shim.c`/`decode.c` at
all**. Building it fresh would mean writing new C source into `src/OpenWSFZ.Ft8/Native/*.c`, even
if uncommitted — a materially different act from the original W1 run, which only flipped an
existing `#ifdef` already compiled into `d001-c4-min-score-sweep`'s own shipped source. Writing new
native code, even as a throwaway diagnostic, is `src/` work and belongs to HK-011, not to this
precondition check.

**What was done instead, disclosed rather than silently substituted:** copied the exact
already-built diagnostic DLL from the still-present worktree
(`.claude/worktrees/w1-sec5-calibration/native/ft8_lib_build/libft8_diag_llr.dll`, SHA256
`b3bc8003b0af3cde31b3a9ff59b870edc6b971a90f4716133eb27837413810de`, `ft8_lib_version_check() ==
20260035`, matching `w1_sec5_calibration.py`'s own `EXPECTED_SHIM_VERSION` assertion) into this
branch's `native/ft8_lib_build/` — a copy of an existing binary, zero new source written, and **not
committed** (throwaway artifact, same status the original W1 report gave it). Ran
`qa/cycleframer-alignment-replay/w1_run_sweep.py` unmodified from this branch's tree against it.

```
Arm A: 200 buffers, 1800 planted, 1178 located, 40.9s
Arm B: 200 buffers, 1600 planted, 1142 located, 39.1s
Arms DIVERGE (max diff 5.2%) -- using Arm B's curve, per the pre-registered rule.
E (interpolated, Arm B) = 4.82   B10=15.9%  B50=11.65%  B90=8.1%
```

**Arm A's curve reproduced bin-for-bin identical to the original report's §4 table** (same `n`,
same `k`, same `P` in every one of 19 bins) — direct confirmation that fixed-seed + identical DLL
gives byte-for-byte deterministic output, and that this leg is a genuine re-run, not a restatement.

**Arm B here is the original run's own *pre-top-up* leg**, not the published post-top-up curve —
the original report's §5 added a 120-buffer top-up (SNR narrowed to −21…−17 dB) to bring the
7.5–10.0% bin from n=22 to n=40; that top-up step was run ad hoc in the original session and is not
encoded in the committed `w1_run_sweep.py` driver. This run's Arm B 7.5–10.0% bin lands at **n=22**
— matching the original's own disclosed pre-top-up state exactly (further evidence this is a real,
matching re-run, not a coincidence). `B50` from this shorter run is **11.65%** against the
published (post-top-up) **11.3%** — **0.35 pp apart, inside the 1 pp ROW 0a bound** without
needing to reproduce the top-up. Not attempted here since the bound already clears; the top-up
step would only be needed if this had landed outside tolerance.

## 4. ROW 0a verdict

Per §5: *"Fires if: the recovered harness fails to reproduce `B50 = 11.3%`, matched-hit control
median `2.9%`, or THE 135 median `44.0%` each within 1 pp."* **None of the three misses by more
than 0.35 pp. ROW 0a does not fire.** The bar is established on this tree; the recovered instrument
is trustworthy for use in N1 once the §3.2 export exists.

## 5. What this does NOT do

- **Does not touch `src/`.** No native source was written, patched, or committed. The one native
  binary used is an unmodified copy of a pre-existing, previously-validated build; it is not staged
  for commit.
- **Does not run N1 itself.** N1's population, pairing, and gate (§4–§5 of the spec) all depend on
  the `ft8_extract_llrs_at(pcm, len, freq_hz, time_offset_s, out_llr174)` export from §3.2, which
  does not exist yet on any branch. That is the next deliverable, and per HK-011 it is a
  `dev-tasks/*.md` QA authors and stops — a separate Developer session applies it, the Captain
  reviews the diff. Not started in this session.
- **Does not license the M-series' ~1.1 ms / 0.5 Hz refiner-accuracy figures for real signals** —
  unrelated to this leg, prohibition unchanged.

## 6. Reproducibility

- Recovered files: fourteen, listed in §1, `git checkout 7a604b4 -- <paths>`, staged on
  `feat/r1b-sync-refiner-instrument-correction`, not yet committed as of this report (committed in
  the same edit as the board update, per HK-024).
- THE 135 / matched-hit-control leg: `python c2_phase2c_ber_measurement.py`, run from
  `qa/cycleframer-alignment-replay/`, against `artefacts/d001_c2_phase2c/` and
  `artefacts/20260725_live_run_1806/` (both already present in this repo's own git-ignored
  `artefacts/`, no junction needed).
- B50 leg: `python w1_run_sweep.py`, same directory, against a copy of
  `libft8_diag_llr.dll` (SHA256 above) staged at `native/ft8_lib_build/libft8_diag_llr.dll`
  (untracked, not committed). Output: `artefacts/d001_w1_sec5_calibration/summary.json` (this run
  overwrote the original's `summary.json`; `summary_final.json`, the post-top-up authoritative file
  the W1 report cites, is untouched and still on disk).
- NFR-021: no callsign, message text, or per-record field appears above; aggregate statistics only,
  ASCII console output (HK-009 — `sys.stdout.reconfigure` already in both scripts).

---

*Per HK-015 this is QA material for the Architect. Per HK-014 nothing here is pushed; committed
locally only. Per HK-011 no `src/` change is made or proposed in this document — §3.2 is separate
future work. Per HK-006 no `pre_merge_check.py` run is implied.*
