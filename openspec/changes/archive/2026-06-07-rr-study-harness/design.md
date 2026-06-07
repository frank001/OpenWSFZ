## Context

The clean-room FT8 synthesiser (`qa/rr-study/synth/`) and its §5 self-validation gate are
complete. Five scenario JSON files (`s1–s5`) and the study-messages manifest are committed.
The operator runbook (`RUNBOOK.md`) is merged. What remains is the **harness** — the Python
tooling that closes the loop between the synthesiser and the analysis report.

The harness is a pure CLI tool. It touches no .NET code and is excluded from `OpenWSFZ.slnx`.
Its only external contracts are (a) the audio output device (VB-CABLE "CABLE Input") and
(b) the `ALL.TXT` log files produced by WSJT-X and OpenWSFZ. The operator starts both
applications manually before running the harness; the harness does not launch or control them.

Three cooperating scripts implement the pipeline:

```
run_scenario.py → (PCM playback + truth.csv)
                            ↓
              matcher.py → matched.csv
                            ↓
             analyse.py → report.md + *.png + trend.csv
```

---

## Goals / Non-Goals

**Goals:**
- One-command scenario execution that aligns PCM playback to FT8 15-second UTC cycle
  boundaries and logs all injected-truth metadata to a versioned run directory.
- Post-run join of injected truth against WSJT-X and OpenWSFZ `ALL.TXT` files, tolerating
  the timestamp and formatting differences between the two writers.
- One-command report regeneration from `matched.csv` producing Minitab-style Gage R&R tables,
  six-panel charts, Kappa, bias/linearity, and a plain `report.md`.
- Determinism: identical seeds produce byte-identical audio, so any run can be replayed.
- Append-only `trend.csv` so improvement/regression is visible across runs over time.

**Non-Goals:**
- Automated audio capture (both apps capture independently via WASAPI shared-mode — no
  harness involvement required or desirable).
- Integration with the .NET CI pipeline (manual/on-demand QA tool only).
- Cross-platform audio — Windows + VB-CABLE is ratified (D7). Linux/macOS variants noted
  in `RUNBOOK.md` as not-yet-validated.
- Launching or controlling WSJT-X or OpenWSFZ (operator responsibility, per `RUNBOOK.md`).

---

## Decisions

### D1 — Audio playback: `sounddevice` (PortAudio)

**Chosen:** `sounddevice` with `sounddevice.play(samples, samplerate, device=..., blocking=True)`.

**Rationale:** PortAudio exposes WASAPI shared-mode on Windows, integrates directly with numpy
float32 arrays (zero-copy path from the synthesiser), and provides a clean blocking API.
`pyaudiowpatch` adds WASAPI loopback capture — not needed here. `winsound` cannot handle
arbitrary PCM arrays. `sounddevice` is the obvious choice.

**Cycle alignment:** The generator sleeps to `utc_cycle_start − 0.5 s` using
`time.sleep()` (Windows precision ≈ 10–15 ms), then calls `sd.play()`. The 500 ms lead
is deliberate — PortAudio needs time to prime its buffer before the first sample arrives.
A 15-second cycle is tolerant of ≤ 100 ms placement error in practice (FT8's sync
window spans ±1.0 s), so the 10–15 ms sleep jitter is negligible.

### D2 — Three separate CLI entry points

**Chosen:** `run_scenario.py`, `matcher.py`, `analyse.py` — each callable independently.

**Rationale:** Separating the steps allows QA to re-run matching or analysis without
replaying audio. It also keeps the signal-generation critical path (timing-sensitive) free
of I/O and computation that could introduce jitter. The three steps share only files
on disk; no in-process coupling is required.

### D3 — Run directory layout

**Chosen:** `results/<YYYY-MM-DD>-<git-sha7>/` created by `run_scenario.py` at startup.

All outputs for a run live under that directory:
- `truth.csv` — injected truth (one row per trial)
- `<scenario_id>_matched.csv` — matcher output (one per scenario run in this session)
- `report.md`, `*.png` — analyser output
- `trend.csv` lives at `qa/rr-study/trend.csv` (append-only, not inside the run dir)

The `results/` subtree is committed to the repository so the published report is
durable and reviewable without re-running the study.

### D4 — ANOVA method for Gage R&R

**Chosen:** Two-way crossed ANOVA (Part × Appraiser, interaction term included).

This is the standard AIAG Gage R&R method and what Minitab implements. The formulae
for variance components and %Tolerance follow the AIAG MSA Reference Manual (4th ed.).
scipy's `f_oneway` and manual SS decomposition are sufficient; no `statsmodels` dependency
is required. Kappa is computed via `sklearn.metrics.cohen_kappa_score`.

### D5 — ALL.TXT format tolerance

**Chosen:** Parse both files with the same regex; normalize timestamps to the slot start
by flooring to the nearest 15-second boundary (with ±1 s skew tolerance before flooring).

WSJT-X writes: `YYYYMMDD_HHMMSS   UTC  Freq  Dt  SNR  Mode  Message`
OpenWSFZ writes a compatible line (same format, confirmed via p9 decode-log spec).
Both are line-oriented; the matcher reads the file sections accumulated during the run
(identified by the cycle UTC key rather than a live tail).

### D6 — Seed formula

**Chosen:** `seed = abs(hash(f"{scenario_id},{part_index},{trial_index}")) % (2**31)`
using Python's built-in `hash()` with `PYTHONHASHSEED=0` fixed in the harness launcher
to ensure cross-session reproducibility. Documented in the runbook.

---

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| PortAudio startup latency shifts first-sample timing | 500 ms lead time before cycle boundary; FT8 sync tolerates ±1 s DT, so harness timing error is immaterial |
| `time.sleep()` precision on Windows (~10–15 ms) | Cycle alignment error << FT8 sync window; logged DT offset captures any consistent bias |
| WSJT-X / OpenWSFZ `ALL.TXT` timestamp skew | Matcher normalises to slot start with ±1 s tolerance before applying the 15 s floor |
| Python `hash()` varies between processes without `PYTHONHASHSEED=0` | Fixed seed set in the CLI launcher; documented in runbook; random-key defence is irrelevant for test-vector generation |
| sounddevice device enumeration returns different indices across sessions | `--device` CLI argument accepts a name substring match (not a bare index), matched against `sd.query_devices()` |
| Long scenario runs (S1: ~7.5 min; S1–S5 full suite: ~60 min) | Expected; operator follows runbook; no timeout imposed by the harness |
| `trend.csv` git conflicts if two operators commit results | Documented as a manual rebase-and-append; acceptable at the study's run cadence |
