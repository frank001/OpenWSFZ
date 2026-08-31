# S7 stability re-run — §B.1 pre-work (W1/W2/W3) complete, R2 retroactively validated against ROW 0, two runs remain

**From:** QA
**For:** Architect (spec owner), Captain (bench time / next run)
**Date:** 2026-08-31 18:28 UTC
**Concerns:** `2026-08-31-1601-architect-to-qa-s7-jump-is-instrument-not-decoder-and-spec-s7-stability-rerun.md`
Part B (S7 stability re-run spec). Branch `qa/s7-stability-rerun-2026-08-31`, off
`qa/rr-sweep-2026-08-30-31` (not `main`, not `qa/sup-b-step7-2026-08-31` — this travels with the
sweep thread per the board's existing note). Not pushed.

**Trigger:** Captain asked to set up the S7 re-run, offering to restart WSJT-X/FT991A and clear
`ALL.TXT`+WAV files, or leave the chain running as-is. Before answering that, the spec's §B.1
pre-work had to be done — none of it had been started.

---

## 1. W1 — comparator base rates: CONFIRMED, exact match to the Architect's derivation

Recomputed independently from each of the five sweeps' own S7 per-part tables (not from the
rounded percentages), summing the 21-part truth/matched counts by hand:

| Sweep | SHA | WSJT-X (msgs/215) | OpenWSFZ (msgs/215) |
|---|---|---:|---:|
| 2026-08-15 | `8d6e1b1` | 205 (95.35%) | 160 (74.42%) |
| 2026-08-21 | `7d36038` | 205 (95.35%) | 147 (68.37%) |
| 2026-08-22 | `f5dec23` | 211 (98.14%) | 171 (79.53%) |
| 2026-08-27 | `22b749c` | 210 (97.67%) | 169 (78.60%) |
| 2026-08-29 | `872ba65` | 200 (93.02%) | 159 (73.95%) |

**WSJT-X uncapped range: 211 − 200 = 11 messages** (93.02%–98.14%). **OpenWSFZ uncapped range:
171 − 147 = 24 messages** (68.37%–79.53%). Both match the Architect's stated derivation
(≈11 / ≈24) exactly, to the message.

**W1 precondition (truth total = 215):** confirmed all five — each sweep's part table sums
10×20 + 15 = 215 by construction (identical 21-part structure across all five), and the reported
"all" percentages back-derive to exactly these integer message counts with no rounding slack.
No sweep excluded.

## 2. W2 — ROW 0d threshold: 9 messages

Grouped each sweep's WSJT-X per-part counts into the spec's six batches (P0–P3, P4–P7, P8–P11,
P12–P15, P16–P19, P20) and took the minimum cell across the full 5-sweep × 6-group grid:

| Group | 8d6e1b1 | 7d36038 | f5dec23 | 22b749c | 872ba65 | min |
|---|---:|---:|---:|---:|---:|---:|
| G1 P0–3 (/45) | 45 | 39 | 43 | 40 | 38 | 38 |
| G2 P4–7 (/40) | 40 | 40 | 40 | 40 | 40 | 40 |
| G3 P8–11 (/40) | 40 | 40 | 40 | 40 | 40 | 40 |
| G4 P12–15 (/40) | 30 | 36 | 38 | 40 | 32 | 30 |
| G5 P16–19 (/40) | 40 | 40 | 40 | 40 | 40 | 40 |
| G6 P20 (/10) | 10 | 10 | 10 | 10 | 10 | **10** |

Global minimum cell = **10** (G6, every sweep — P20 alone is WSJT-X's only perfectly clean part
historically). **ROW 0d threshold = 10 − 1 = 9 messages**, fixed now, applied identically to all
six batches of every future run, per the spec's literal text ("the minimum cell across all
(sweep × group)" — read as one scalar over the whole grid, not six separate per-group floors).

⚠️ **HK-022 caveat, stated so it isn't rediscovered as a surprise later:** because this is one
flat message-count threshold applied to batches of very different sizes, it is **not equally
sensitive** across batches. G6 (10 trials) fails at 2 lost messages; G1 (45 trials) would have to
lose 37 before the same threshold fires. **G6 is the batch that will actually gate ROW 0d in
practice** — a chain that degrades only in the P12–P19 range could still pass 0d on every other
batch's slack. This is a property of the pre-registered mechanism, not something to correct
post hoc.

## 3. W3 — R1 (the destroyed collapsed reading) recovered

Re-ran `matcher.py --scenario S7` against the three surviving originals in
`results/2026-08-30-2e60949/` (`truth.csv`, `owsfz-all.txt`, `wsjt-all.txt` — confirmed by content,
not mtime, since a branch checkout resets mtimes: `truth.csv`'s S7 block is 215 rows and, byte-for-byte
excluding the `cycle_utc` column, identical to R2's — see §4.5), writing to a separate output
directory so the existing `S7_matched.csv` (R2's) was never touched, then copied the result in as
**`S7_matched.R1-collapsed.csv`** (never the bare name, per the spec's C.2 rule 4).

**R1, recovered:**

| Appraiser | Matched | Total | Recovery |
|---|---:|---:|---:|
| WSJT-X | 57 | 215 | **26.51%** |
| OpenWSFZ | 36 | 215 | **16.74%** |

Cross-checked two ways (the matcher's own summary line, and an independent per-part tally from
the written CSV) — both agree exactly.

**Per-part shape confirms the "collapse ~18–19 min in" account precisely, and localises it
tighter than the original narrative did:**

| Part | WSJT-X | OpenWSFZ |
|---|---|---|
| P0–P3 | 10/10, 10/10, 15/15, 8/10 | 7/10, 9/10, 0/15, 10/10 |
| P4 | 10/10 | 4/10 |
| P5 | 4/10 | 6/10 |
| P6–P20 | 0/10 (or 0/15) every part | 0/10 (or 0/15) every part |

The chain was decoding normally through P4, degraded mid-P5, and produced **zero true-positive
matches for both appraisers from P6 onward** — a hard floor, not a gradual fade. 19 rows of
noise-hallucinated garbage decode text were found in the process (both apps, all in the P6+
window); redacted per standing NFR-021 policy before this file was committed — see §6.

## 4. R2 retroactively evaluated against ROW 0 — all five rows PASS

R2 (`results/2026-08-31-2e60949/`, the capped re-run already on record at 98.14%/82.79%) predates
this spec's write-up and was never formally gated. Its saved artefacts are sufficient to evaluate
ROW 0 against it now, mechanically, using this pre-work's own threshold:

### 4.1 ROW 0a — BUILD PIN: **PASS**

`git cat-file -p main:src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll | sha256sum` =
`e22524e8fb4964496e34a2c3f08d6e10d8f6f48eaadb0626fe6a8799fa84e33e`, matching the pinned SHA for
shim `20260048` used by both R1 and R2. `wsjt-version.txt` records `WSJT-X 2.7.0`. ⚠️ This is the
committed binary's hash, not a hash captured live during R2's own playback (R2 predates a
per-run capture step) — inherited from the already-established SUP-B pin rather than
independently re-hashed at run time. Flagging the gap rather than silently treating it as
equivalent; **R3/R4 going forward should re-hash the on-disk DLL actually loaded, not just the
committed one**, to close this.

### 4.2 ROW 0b — HARNESS PIN: **PASS**

`_MAX_BATCH_TRIALS = 20` present (`harness/run_scenario.py:53`). `s7_rerun_2026-08-31.log` shows
**exactly 6** "played back-to-back" flush markers — 20, 20, 20, 20, 20, 5 trials — summing to
**105**, matching the S7 scenario's total trial count exactly (and, not coincidentally, aligning
part-for-part with the W2 batch groups: P0–P3/P4–P7/P8–P11/P12–P15/P16–P19 = 20 trials each,
P20 = 5).

### 4.3 ROW 0c — CHAIN AT START: **PASS**

First S7 cycle: `2026-08-31T14:59:15Z`. Both `owsfz-all.txt` and `wsjt-all.txt` show a decode at
`260831_145815`/`145915` — inside the preceding 300 s window (≤60 s before). ⚠️ R2 ran with
`--skip-warmup` (detached run, no interactive TTY for the scripted pre-flight check) — this is an
*incidental* warm-up signal, not the scripted one. Recommend R3 use the scripted warm-up if this
session is interactive (stronger 0c evidence than relying on finding a decode after the fact).

### 4.4 ROW 0d — CHAIN HELD: **PASS**, using this pre-work's threshold (≥9/batch)

Recomputed from `S7_matched.csv` (R2's, untouched) grouped the same way as W2:

| Group | WSJT-X matched |
|---|---:|
| G1 P0–3 | 43/45 |
| G2 P4–7 | 40/40 |
| G3 P8–11 | 40/40 |
| G4 P12–15 | 38/40 |
| G5 P16–19 | 40/40 |
| G6 P20 | 10/10 |

Every cell ≥ 9. No batch came close to the threshold — closest margin is G4 at 38 (29 above
floor).

### 4.5 ROW 0e — TRUTH IDENTITY: **PASS**

`diff` of the sorted S7 truth blocks from both result directories, **excluding only the
`cycle_utc` column** (which differs by construction — the two runs are a day apart): byte-identical.
Seeds, SNR/DT/frequency, and message text all reproduce exactly across the two calendar days —
this is a positive finding in its own right: **the scenario's RNG seeding is confirmed
deterministic across a full day boundary**, which is exactly the property ROW 0e exists to catch
the absence of.

### 4.6 Conclusion

**All five ROW 0 checks pass for R2.** R2 formally qualifies, retroactively, as the first of the
spec's pre-registered **N = 3** independent runs. **Two more runs remain: R3, R4.**

📌 **Preview only, not a verdict (ROW 2/3 require all three runs, per §B.4):** R2's own diagnostic
numbers already line up with what ROW 2 will need — OpenWSFZ P2 = 0/15, P4 = 5/10, P12 = 5/10,
P13 = 5/10, P14 = 5/10, all exactly on the pre-registered null-control values. WSJT-X's R2 count
(211) sits exactly at the top of the W1 uncapped range (211), i.e. at its historical ceiling, not
above it.

## 5. Setup for the next run (R3) — direct answer to the Captain's question

🔴 **Restart WSJT-X. Do not run R3 against the currently-running instance.** Checked before
writing this: WSJT-X (PID 3880) has been running continuously since **2026-08-30 21:37:37
local**, i.e. since immediately after the hardware-failure recovery, **straight through R2's own
playback on 2026-08-31**. If R3 reuses that same process, R3 and R2 share a WSJT-X session,
directly violating §B.2's independence requirement ("no two runs may share a daemon session...
full daemon + WSJT-X restart between them") — R3 would not be an independent sample of chain
state, it would be the *same* one R2 already used. A genuinely new process is required, not just
a fresh decode.

The daemon side is not a live decision — `dotnet.exe` is not currently running at all (checked:
no process, nothing on port 8080), so it starts fresh regardless.

✅ **Also recommended, both for hygiene and for a cleaner ROW 0c signal:** clear `ALL.TXT` on
both sides before starting. Two independent reasons, not one: (1) the standing NFR-021 note that
an uncleared `ALL.TXT` contaminates every `*_matched.csv` this harness produces — W3 just found a
fresh instance of exactly that contamination class (19 rows, §6); starting clean avoids adding to
it. (2) A clean log makes ROW 0c's "warm-up decode within 300 s" check unambiguous instead of
incidental — right now it's only satisfied because normal traffic happened to appear near the run
start, not because a deliberate warm-up was verified.

**WAV files:** clearing them is not gating (nothing in ROW 0 depends on stale WAVs, and the
harness regenerates its playback audio fresh from the scenario's own seeds each run — confirmed
by W3's finding that seeding reproduces byte-identically across days). Recommend clearing anyway
for tidiness and to avoid any confusion about which files belong to which reading, matching the
precedent set during the 2026-08-30 hardware-failure recovery (full daemon + WSJT-X restart was
done then too) — but this one is genuinely the Captain's call, not a spec requirement.

⚠️ **Calendar-day note, not a blocker:** R2 was 2026-08-31. The spec requires the *set* of three
runs to span ≥2 distinct calendar days, which is already satisfied the moment either R3 or R4
lands on a different day — it does not require R3 itself to be on a different day than R2. Running
R3 today, with a genuine restart, is spec-compliant. **Recommend R4 lands on a different day than
both R2 and R3**, to keep the "chain fully cooled between samples" rationale intact rather than
resting on the letter of "≥2 days" alone — but flagging this as a recommendation, not re-reading
the mechanical minimum upward on my own authority.

## 6. NFR-021 finding and fix, scoped to this branch's own new file

Before committing `S7_matched.R1-collapsed.csv`, scanned it with the same predicate
`nfr021_pre_merge_scan.py` uses and found **19 rows carrying 32 distinct callsign-shaped
noise-hallucinated tokens** — all in unmatched/false-positive rows from the P6+ collapse window
(same class as the two tokens already redacted from `report.md` in `7d513f8`, now shown to be a
much larger set once the raw collapse data itself is examined token-by-token rather than by the
three examples quoted in prose). Redacted (whole `message_text` field →
`[NFR-021 redacted: callsign-shaped noise tokens]` for the 19 affected rows only; `matched`/
`false_positive` columns and all other rows untouched) **before** committing — re-scanned clean,
zero flagged tokens remaining, match counts (57/215, 36/215) verified unchanged by the edit.

✅ **Checked and ruled out, not assumed:** whether the *already-committed* `owsfz-all.txt` /
`wsjt-all.txt` (which contain this same collapse-period text) are themselves an exposure on
`qa/rr-sweep-2026-08-30-31`. They are not — both are gitignored per-results-directory
(`.gitignore:162-163`), confirmed via `git check-ignore -v`, and `git diff --name-only
main...HEAD` confirms neither file is tracked or part of any diff. The only VCS-facing copy of
this text was the new derived CSV this session created.

## Sources

- `2026-08-31-1601-architect-to-qa-s7-jump-is-instrument-not-decoder-and-spec-s7-stability-rerun.md`
- `results/{2026-08-15-8d6e1b1, 2026-08-21-7d36038, 2026-08-22-f5dec23, 2026-08-27-22b749c,
  2026-08-29-872ba65}/report.md` — S7 per-part tables (W1/W2)
- `results/2026-08-30-2e60949/{truth.csv, owsfz-all.txt, wsjt-all.txt}` — W3 originals
- `results/2026-08-30-2e60949/S7_matched.R1-collapsed.csv` — W3 output (new, this session)
- `results/2026-08-31-2e60949/{S7_matched.csv, truth.csv, wsjt-version.txt}` — R2 retroactive ROW 0
- `qa/rr-study/s7_rerun_2026-08-31.log` — R2 batch/flush and cycle-timing evidence
- `qa/rr-study/nfr021_pre_merge_scan.py`, `.gitignore:162-163`
