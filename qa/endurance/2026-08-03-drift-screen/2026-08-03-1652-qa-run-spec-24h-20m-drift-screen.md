# QA run spec — 24 h contiguous 20m capture, doubling as the FT-991A cap drift screen

**Author:** QA, 2026-08-03 (16:52 UTC, `date -u`, per HK-017)
**Repo at:** `5e70297` (contains `be5960a`, the CycleFramer grid-realignment fix)
**Authorised by:** the Captain, 2026-08-03 — 24 h, evening to evening.

---

## 0. What this run is for

One run, two questions. They are **not** equally weighted and must not be conflated.

| | question | status |
|---|---|---|
| **Primary** | Does the capture window stay anchored to the UTC grid on the real FT-991A / USB Audio CODEC chain, past the ~13.7 h point where the defect previously became total? | pre-registered, mechanical (§5) |
| **Secondary** | Does WSJT-X suffer the same density penalty we do — the same-family control for D-001? | **opportunistic only**; no pre-registered rule, no verdict from this run |

The primary question exists because the ~6 h session cap on that chain is *mitigation* for
`DEFECT-capture-clock-drift-silent-decode-loss.md`. The defect is fixed and merged (`be5960a`),
but the cap lifts **as a decision by the Captain**, never as an inference from a green unit test.
The previous ~12 h cap was lifted on the belief that PR #118 had fixed this; that belief cost
2,702 cycles in the +2 s regime.

**This run deliberately exceeds the standing ~6 h cap.** That is the point — a screen that stops
at 6 h proves 6 h. The exceedance is a one-off authorised for this run; the cap remains in force
afterwards until the Captain lifts it explicitly, whatever §5 returns.

## 1. The instrument is already validated — before the run, not after

`drift_screen.py` in this directory **is** the pre-registered check (HK-021: draft the check by
writing the code that would evaluate it). It was validated against the **pre-fix** corpus
`20260731_live_run_2004-8080` (43.6 h, captured on the defective build) with `--expect-fail`:

| epoch | span | audio slope | ppm | max abs lag |
|---|---:|---:|---:|---:|
| 0 | 14.88 h | −0.1704 s/h | −47.3 | 2.802 s |
| 1 | 13.70 h | −0.1749 s/h | −48.6 | 2.582 s |
| 2 | 13.06 h | −0.1716 s/h | −47.7 | 2.469 s |

Three independent epochs recovering −47 to −48.6 ppm against a documented 48.0 ppm device drift,
with the sawtooth resetting at each restart. **The instrument can see drift.** Without this, a
green screen would be indistinguishable from a broken script pointed at the wrong folder (HK-022).

Two defects in the instrument were found *by* that control and fixed before the run:

1. **Filename pairing hid the evidence.** Once the window drifts past a second, our WAV's
   second-field diverges from WSJT-X's and the pair vanishes from an exact-name intersection —
   discarding precisely the drifted cycles that carry the signal. On the control corpus that
   dropped 6,851 of 10,469 pairs (65%). Pairing is now by nearest timestamp (±7.5 s), and
   coverage is computed from **every archived cycle** via `cycle-archive.csv`, so a pairing
   failure can never shrink the run into a false coverage VOID.
2. **Row ordering could have let drift exonerate itself.** Because drift destroys pairing, a
   VOID-before-FAIL ordering meant the worse the drift, the more certainly the run would VOID
   instead of FAIL. FAIL is now evaluated first, and the label curve — full coverage, no pairing
   needed — can fire it alone.

A third was pre-empted: a stub epoch (6 cycles, 0.10 h) produced a label slope of −2.3544 s/h,
~13× the real device drift, purely from too short a baseline. Slopes now require ≥20 points and
≥1.0 h of span; under-determined epochs abstain rather than voting with a wild number.

## 2. Prerequisites — all must hold before arming

| # | item | owner | state |
|---|---|---|---|
| 1 | Daemon rebuilt from a tree containing `be5960a` | QA | ✅ published 16:44 UTC; HEAD confirmed a descendant of `be5960a`; `CycleFramer.cs` confirmed to carry the `consume` re-anchoring (tree read, not commit message) |
| 2 | Capture directory cleared of the previous session's `ALL.TXT` and 90 leftover WAVs | **Captain** | in progress |
| 3 | New binary deployed into `D:/Projects/claude/OpenWSFZ-8080-capture` | QA | **pending item 2** |
| 4 | `config.json` preserved: `mode:"all"`, 14.074 MHz, own archive dir, `maxSizeMb:20480` | QA | ✅ verified, no change needed |
| 5 | Radio on 20m; one WSJT-X instance on the same audio path, own `save\` folder | **Captain** | — |
| 6 | No orphaned supervisors or daemons (HK-019) | QA | ✅ verified clean, nothing running |
| 7 | Free disk covers ~2 GB/day plus WSJT-X's own WAVs | QA | ✅ 1.6 TB free |

**Item 1 is the one that silently wastes the run.** The binary staged in the capture directory
was dated 2026-08-02 23:12 — roughly nineteen hours *before* the fix landed. Arming on it would
have gathered 24 h on the defective framer.

## 3. Arming

```
RESTART_WAIT_SECS=60 bash qa/endurance/2026-07-31-supervisor-8080.sh
```

The 07-31 supervisor is reused unchanged — it is live-tested, carries the HK-013-addendum
rotation guard (`find_latest_log()` re-resolves the newest log each poll), caps at 5 retries, and
keeps the unreviewed cross-instance decode check gated off.

**The cooldown must be 60 s, not the 300 s default.** A gap over 5 minutes splits the corpus into
segments that cannot be re-joined; kill + 300 s + start-up guarantees that. This is the failure
that made the last 20m corpus two sessions and rendered its segment 2 uncitable.

Note the two thresholds are independent and both matter: 60 s keeps the *corpus* contiguous,
while the *drift screen* still sees every restart, because `rotationSchedule:"session"` gives one
daemon log file per process start and that — not the gap — is what `drift_screen.py` reads as an
epoch boundary. Gap-based epoch detection would merge restarts at a 60 s cooldown and average a
sawtooth into a flat line, hiding the defect.

## 4. During the run — sample, do not interact

Per the 07-31 brief §6. **No Settings-page saves on 8080 for the duration**, no retunes, no
band changes. Wake the Captain only for: archiving stopped (WAV count flat >2 cycles),
projected disk exhaustion, `|dt|` crossing 0.5 s, or a **second** supervisor restart.

## 5. THE PRE-REGISTERED CHECK — fixed in git before the run starts

Evaluated by `drift_screen.py --corpus artefacts/<run>`. Rows are evaluated in **strict order**;
first match wins; they are mutually exclusive and exhaustive. Thresholds are constants in the
script, not judgement calls at analysis time.

| row | condition | consequence |
|---|---|---|
| **1 — VOID** | longest uninterrupted uptime epoch `< 14.0 h` | **NO VERDICT.** Cap STAYS. Re-run; do not reinterpret. |
| **2 — FAIL** | any admissible epoch with `abs(audio slope) >= 0.05 s/h` **or** `abs(label slope) >= 0.05 s/h` **or** `max abs lag >= 0.5 s` **or** `max abs label >= 0.5 s` | Cap STAYS. Defect **REOPENS**. |
| **3 — VOID** | decisive epoch has `< 200` locked audio pairs | **NO VERDICT.** Cap STAYS. Label curve alone cannot rule out a label-only fix. |
| **4 — INCONCLUSIVE** | `abs(slope) >= 0.02 s/h` **or** `max abs lag >= 0.2 s` | Cap STAYS. No reopen; escalate to the Architect. |
| **5 — PASS** | none of the above | QA **recommends** the Captain lift the ~6 h cap. |

Threshold provenance — none are round numbers chosen for comfort:

- **14.0 h** — 48.0 ppm reaches FT8's ~2.36 s guard interval at ~13.7 h, where the defect became
  total. Margin above it.
- **0.05 s/h** — under a third of the measured 0.173 s/h defect signature, so a returning defect
  cannot hide beneath it.
- **0.5 s** — the programme's healthy-window bar, retroactively justified by the measured 0.15-pt
  matched-parity cost of sub-0.5 s misalignment.
- **0.2 s** — the bar the fix's own oracle is held to.
- **0.02 s/h** — an order of magnitude under the defect signature, and ~27× above the 0.75 ms per
  24 h the fix predicts, so a genuinely fixed framer clears it with room.
- **200 locked pairs** — statistical floor below which a slope fit is not worth reading.

**ROW 5 is a recommendation, not a lift.** The cap comes off when the Captain says so.

## 6. Post-run, in this order

1. **Gather artefacts (HK-016)** — `tools/gather_live_run_artefacts.py`. This is the step that
   gets skipped; only 1 of 19 prior runs complied.
2. **Contiguity/segment report before any analysis** — gaps > 5 min in `cycle-archive.csv`, per
   segment durations and density ranges. Establish segment structure as a fact of the corpus up
   front, not as a later discovery (self-check 5).
3. **Run the screen** — `drift_screen.py --corpus artefacts/<run>`, and report the row it fires
   verbatim, including a VOID.
4. **Regenerate the artefact inventory** — `python qa/artefact_inventory.py`.

**`jt9` offline may be gathered as an artefact but is NOT a reference leg.** Measured 2026-08-03:
it overshoots WSJT-X by 11.2% on WSJT-X's own audio and OpenWSFZ by 93.8% on ours, and emits
duplicate `(ts, message)` pairs from its own multi-pass search. The reference for both the drift
screen and the same-family control is the **live WSJT-X** instance. This corrects the 07-31
brief's item 7.2 framing, which predates that measurement.

## 7. What this run does NOT decide

- It does not lift the cap. It informs a decision that remains the Captain's.
- It does not settle D-001, the B.3 menu, or the density penalty. The secondary question is
  opportunistic and carries **no** pre-registered rule; any density finding from it is a
  hypothesis for the Architect, not a result.
- It does not touch `src/` (HK-011), and `pre_merge_check.py` is not run (HK-006 — the Captain's
  trigger only).
- **NFR-021:** real callsigns stay inside git-ignored `artefacts/`. Only aggregates and counts
  appear in anything committed. `drift_screen.py` reads WAV PCM, `cycle-archive.csv` and log
  filenames only — never `ALL.TXT`, never message text.
