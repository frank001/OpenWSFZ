# QA → Architect — Task 5 result: isolated-replay re-run, ROW 4 STRONG

**Author:** QA, 2026-08-04 (17:33 UTC, `date -u`, per HK-017).
**Executes:** `qa/cycleframer-alignment-replay/2026-08-04-1441-architect-to-qa-spec-isolated-replay-rerun-post-drift-fix.md`.
**Verdict: ROW 4 — STRONG.** `r = 0.1717 <= 0.333`. Drift accounted for **most** of the live-path
loss measured by PR #103. The fix is validated on the live path.

---

## 0. Harness confirmation and disclosed changes

Per Sec.5: confirmed `run_isolated_replay.py` / `materialise_isolated_sample.py` (committed
`0726bd6`) run correctly against the shape of data they expect, then wrote generic-corpus
adaptations rather than modifying the originals, so the originals stay a faithful record of the
07-07 pilot. **Disclosed changes, made before pre-registering, documented in each script's own
header** at
`qa/cycleframer-alignment-replay/2026-08-04-isolated-replay-rerun/`:

1. **Corpus path is a parameter.** Both arm corpora use `<corpus>/owsfz/ALL.TXT` +
   `<corpus>/wsjt-x/ALL.TXT` (the newer layout) instead of the original's flat,
   space-separated filenames. Line format inside each file is byte-identical (Format B).
2. **WAV source is `<corpus>/wsjt-x/wav/`, not a single shared `save/` folder.** The isolated-miss
   population is WSJT-X-decoded / OpenWSFZ-missed messages, so replaying the audio WSJT-X actually
   captured is the direct question; using OpenWSFZ's own (differently time-aligned, on arm A)
   capture of the same nominal cycle would be a different, less direct question.
3. Output paths are per-arm so neither run's `_work/` state collides.

Everything else — daemon lifecycle, boundary-aligned playback, cycle-block delimiter parsing, Gate
R (exact message + 30 Hz tolerance), CG-failure/LDPC-failure/Ambiguous classification — is
unmodified. Build under test: current `main` src state at commit `9492fcc` (both arms; no
intervening `src/` change, confirmed against the publish build's timestamp).

## 1. Mandatory self-checks (Sec.4)

**1. Contiguity/epoch structure**, from daemon-log boundaries:

- **Arm A** (`20260731_live_run_2004-8080`): 5 epochs — 14.88h, 13.70h, 13.06h, 0.10h (the
  Window-7 intermediate instance killed by the supervisor's heartbeat-stall watchdog), 2.03h. No
  gap merges an epoch boundary; matches the known Window 4/6/7 restart history exactly.
- **Arm B** (`20260803_live_run_1713`): 2 epochs — 1.76h, 18.96h (the decisive epoch), as already
  established in Task 1.

**2. Drift screen, both corpora** — not re-run; already on record (HK-018) and both are exactly the
required control/measurement pair:

- Arm A: **ROW 2 — FAIL**, −47.3 / −48.6 / −47.7 ppm (the pre-registered `--expect-fail` positive
  control that validated `drift_screen.py` itself before the 2026-08-03 PASS run).
- Arm B: **ROW 5 — PASS**, +0.0 ppm, 18.96h decisive epoch (`2026-08-04-1405-…-PASS.md`).

Per the pre-registered rule ROW 2 VOID check: arm A's corpus **does** fire ROW 2 FAIL on
`drift_screen.py` → not VOID.

**3. Hashed callsigns normalised before matching** — `is_hashed()` excludes any bracketed token
from both the WSJT-X-only miss population and the reference success pool, unchanged from the
original script.

**4. Grid alignment control** (`grid_alignment_control.py`, new, committed alongside the rule):

| arm | exact-ts matches | ±1 cycle | delta |
|---|---:|---:|---:|
| A | 59,227 | 59,234 | **+7** |
| B | 23,547 | 23,547 | **+0** |

Arm B: zero, as it did in the PASS report §8. **Arm A recovers 7 additional matches at ±1 cycle —
this is drift showing up in the labels**, as the spec anticipated it might on the drifting corpus.
7/59,227 = 0.012%: real, disclosed, and too small to materially change the miss-set construction
(exact-ts matching was used throughout, consistent with the original script and with arm B).

**5. Isolated/Tight/Partial classification counts per arm:**

| arm | isolated | tight | partial | total | isolated % |
|---|---:|---:|---:|---:|---:|
| A | 30,469 | 29,611 | 47,059 | 107,139 | 28.4% |
| B | 3,006 | 3,690 | 5,229 | 11,925 | 25.2% |

Isolated-fraction delta is 3.2 points — **not material**; the contrast is not confounded by class
balance.

## 2. Pre-registered rule evaluation (`evaluate_rule.py`, committed `7b7c968` before either arm ran)

**ROW 1 (population floor):** Arm A population 30,469; arm B population 3,006. Both clear 200. Not VOID.

**ROW 2 (positive-control corpus check):** Arm A fires ROW 2 FAIL on `drift_screen.py`. Not VOID.

**Arm A replay** (`arm-A/results.json`, `arm-A/replay_console.log`):

| stratum | tried | decoded_on_replay | reproduced |
|---|---:|---:|---:|
| < -15 dB | 35 | 15 | 20 |
| -15..-10 dB | 50 | 30 | 20 |

`recovery_A = 45/85 = 0.5294`

**ROW 3 (instrument sensitivity floor):** `recovery_A (0.5294) >= 0.10`. Not VOID.

**Arm B replay** (`arm-B/results.json`, `arm-B/replay_console.log`):

| stratum | tried | decoded_on_replay | reproduced |
|---|---:|---:|---:|
| < -15 dB | 23 | 3 | 20 |
| -15..-10 dB | 21 | 1 | 20 |

`recovery_B = 4/44 = 0.0909`

```
r = recovery_B / recovery_A = 0.0909 / 0.5294 = 0.1717
```

**ROW 4 — STRONG** (`r = 0.1717 <= 0.333`). Drift accounted for **most** of the live-path loss
measured by PR #103. The fix is validated on the live path.

## 3. What the classification detail says, without over-reading it

Every one of the 80 reproduced-miss records across both arms (20+20 per arm) classified
`ambiguous_busy_passband` (`total_candidates` in the 130–340 range throughout — well above the
`<=3` threshold that would trigger the reference-pool LLR comparison, so that comparison never ran
in either arm). This is the outcome the original spec's own §3.3 power caveat anticipated as
likely on a dense band, and it held on both a heavily-drifting corpus and a clean one. It says the
replay pipeline could not further distinguish candidate-generation failure from LDPC-convergence
failure on this data — it does not weaken the recovery-rate contrast, which does not depend on that
sub-classification.

## 4. What this does and does not decide, per Sec.6

- **Validates the fix on the live path, on this measurement.** Drift explains ~83% of the
  live-path Isolated-class miss recovery seen pre-fix (i.e. `1 - r` of the original effect no
  longer applies) — the fix did what it was built to do for this failure mode.
- **Not D-001.** Baseline deficit and density penalty untouched.
- **Not decoder quality.** A recovered decode is not a validated decode — no oracle exists here,
  same standing constraint as every other task in this handoff.
- **Not the settings-page stall, not the cap** (already lifted).
- **Absolute recovery rates are not clean figures** — WSJT-X is a co-appraiser (86.9–93.0%
  within-appraiser repeatability), so both arms' "live miss" sets carry WSJT-X's own noise. This
  is why only `r` is interpreted, per Sec.5's own instruction; neither `recovery_A` (52.9%) nor
  `recovery_B` (9.1%) is cited as a standalone figure of merit here, only as inputs to the ratio.
- **`jt9` was not used anywhere in this task** — replay ran through OpenWSFZ's own decode path via
  the live daemon, exactly as specced.

## 5. Where the evidence lives

`qa/cycleframer-alignment-replay/2026-08-04-isolated-replay-rerun/`:
`evaluate_rule.py` (the pre-registered rule), `materialise_isolated_sample_generic.py`,
`run_isolated_replay_generic.py`, `grid_alignment_control.py`, `arm-A/` and `arm-B/`
(`isolated_sample_candidates.json`, `results.json`, `replay_console.log` each — no message text or
callsigns in any committed file, per NFR-021).
