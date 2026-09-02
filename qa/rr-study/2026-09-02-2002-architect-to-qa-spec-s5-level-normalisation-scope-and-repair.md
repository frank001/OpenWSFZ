# Architect → QA — `S5-LEVEL`: scope and repair of the `level_dbfs` normalisation defect

**Architect, 2026-09-02 20:02Z.** Base `main`@`b4dd754`, shim `20260049`.
Trigger: the `AWGN-FP` ROW 0 report's Recommendation 2 (`qa/rr-study/awgn-fp-replay/results/ROW0-report.md`
§4), raised by QA, ruled by the PO on 2026-09-02 as *"take it as its own pre-registered look."*

**This is a scoping-and-repair task, not a measurement arm, and §0 says why.** It is small — a few
hours, no capture, no rebuild, no Developer session, no `src/`/`native/` change.

---

## 0. Read this first — the arm you might expect is NOT the arm being specced

QA's finding is real: `harness/run_scenario.py` peak-normalises every rendered slot to a fixed 0.9
peak (`_PLAYBACK_PEAK_LEVEL`, call sites `:621` and `:1156`), and for a pure-Gaussian buffer that
cancels the `level_dbfs` amplitude term **exactly**. The declared level has never been delivered,
on hardware or offline.

The instinct is to re-measure every historical S5 reading. **Do not — three things already
constrain the damage, and two of them are measurements we already hold:**

1. 🔴 **The blast radius is one part-pair in one file.** `level_dbfs` appears in **exactly four**
   scenario files, all S5 (`s5-noise.json`, `s5-noise-wide.json`, `s5-noise-wide-n300.json`,
   `s5-noise-diag40.json`). Three of the four declare a **single uniform `-20`** across all parts —
   a constant that cancels identically everywhere, changing nothing. Only `s5-noise.json` varies it:
   parts 0/2/3 at `-20`, **part 1 at `-10`**. That one intended 10 dB step is the whole defect.
   ROW 0f below makes QA re-derive this mechanically rather than inherit it from me.
2. ✅ **For every signal-bearing scenario the normalisation is correct and the code comment
   (`:1147–1155`) is right**: uniform scaling divides signal and noise by the same constant, so SNR
   — a ratio — survives exactly. S1/S2/S3/S7/S8 are untouched by this, and no re-reading of them is
   in scope. The comment is only wrong for a **noise-only** slot, where there is no ratio and
   absolute level is the *only* thing `level_dbfs` controls. S5 parts 0/1 are the sole such pair in
   the study.
3. ✅ **The contrast that was never delivered would very likely have shown nothing anyway.**
   `AWGN-FP` ROW 0c rendered the same seeds at a genuine, verified ±10 dB (baseline/−10/+10 →
   6/7/7 events, all inside the pre-registered [2,10] band) and **passed**: the false-accept rate is
   not measurably level-dependent over exactly the range part 1 was supposed to probe. That is a
   real pre-registered measurement, already in hand.

⇒ **The S5 false-positive gate arithmetic is NOT invalidated.** The gate counts AWGN slots — 2 parts
× 30 trials = 60 — and they are 60 slots at one delivered level. `4/60`, `1/60`, `3.3%/N=120` and
every other ratified-era S5 FP figure stand as computed. 🛑 **Do not restate any of them, and do not
let this defect be cited as a reason to doubt them.**

**What IS void is narrower and must be stated exactly:** any claim that S5 parts 0 and 1 constitute
a *level contrast*, and the "moderate" vs "higher level (hotter band)" part notes in
`s5-noise.json` itself. Parts 0 and 1 are **two replicates of one condition**, and have been since
2026-06-20.

---

## 1. Objective

Establish the exact scope mechanically, then repair the harness and the record. Deliver a decision
to the PO on which of two repairs to take.

**Non-objectives, explicitly:** re-running any S5 sweep; re-computing any historical FP rate;
touching `_PLAYBACK_PEAK_LEVEL` itself (it exists for a real reason — without it ~70% of samples
hard-clip; see the `:1147` comment).

## 2. ROW 0 — mechanical scope checks, all four before any repair

Every row is a hard predicate on data, evaluated by shipped code. Ship the predicates as a script
(`qa/rr-study/s5_level_scope.py`) and commit it with the result — HK-021(r).

| Row | Check | Threshold | If it fails |
|---|---|---|---|
| **0f** | Enumerate every `.json` under `qa/rr-study/scenarios/` containing `level_dbfs`; for each, collect the distinct declared values across parts | **Exactly 4 files; exactly 1 of them has >1 distinct value** | My §0 claim 1 is wrong ⇒ **STOP and report**. The scope is wider than this spec assumes and the spec must be re-drafted, not patched |
| **0g** | For the one varying file, render every part with the shipped `run_scenario.py --dry-run --dump-wav-dir` and measure actual RMS dBFS per part | **All parts within 2.0 dB of each other** | If parts differ by ≥2 dB the cancellation is not exact and §0 claim 1's mechanism is wrong ⇒ STOP |
| **0h** | Render the same parts with `awgn-fp-replay/render_row0c_level_preserving.py`'s level-preserving path | **Part 1 − part 0 = 10.0 ± 1.0 dB** | The workaround does not actually restore the declared step ⇒ ROW 0c's own validity is in question ⇒ STOP and escalate |
| **0i** | `grep` the shipped `_finalize_playback_samples` (`:609`) and the main-loop site (`:1156`) | **Both present and both applying `_PLAYBACK_PEAK_LEVEL`** | Only one path normalises ⇒ live and offline renders differ ⇒ a *separate and worse* finding; STOP and report it as such |

🔴 **ROW 0f is the one that can overturn this spec**, which is why it is first and why its failure
branch is STOP-and-redraft rather than a patch. HK-021(k): it changes the verdict, not just the
precision.

## 3. The repair — two options, PO decides, QA does not pick

Both are `qa/rr-study/` only. Neither touches `src/`, `native/`, or the decoder.

**Option 1 — make `level_dbfs` functional (normalise to a fixed *reference*, not to each slot's own peak).**
Replace the per-slot peak divisor with a constant chosen once from the loudest condition the study
renders, so relative levels between parts survive while absolute headroom is still guaranteed.
*For:* the declared parameter starts meaning what it says; S5 regains a real level axis.
*Against:* it changes the delivered audio for **every** scenario on the next sweep, so the whole
S1–S8 battery becomes non-comparable to all fifteen historical sweeps at a stroke. That is a large
price for an axis ROW 0c suggests is inert.

**Option 2 — delete `level_dbfs` and declare S5 single-level (Architect's recommendation).**
Remove the key from all four scenario files, correct part 0/1's notes to say they are replicates,
and add an assertion in the renderer that fails loudly if any scenario ever declares a level again
without the renderer honouring it.
*For:* the delivered audio does not change at all, so every historical sweep stays comparable;
the record stops claiming a contrast that does not exist; the trap cannot silently reopen.
*Against:* the study loses a level axis it never actually had.

🔴 **I recommend Option 2 and I want to be honest about why it is a judgement call, not a
derivation:** it rests on ROW 0c's single ±10 dB reading (n=60 per leg) being representative. If the
PO wants a level axis for future work, Option 1 is defensible — but it should then be taken
deliberately as a **new instrument**, with a paired sweep to re-baseline S1–S8, not slipped in as a
bug fix.

## 4. The record correction — required under either option

1. `scenarios/s5-noise.json` part 0/1 notes: replace "moderate level" / "higher level (hotter band)"
   with a factual statement that both are the same delivered level, dated, with the reason.
2. `qa/rr-study/STUDY-SPEC.md`'s S5 section: strike any two-level framing, same correction.
3. 🛑 **Do NOT edit historical sweep reports.** They recorded what the instrument reported and that
   record stands. The correction belongs in the board and in the spec, per the project's
   `## S7`-style "extends, never overwrites" convention.

## 5. Deliverable

A short report at `qa/rr-study/awgn-fp-replay/results/` or a sibling dated directory, carrying: the
four ROW 0 verdicts with their measured numbers; the scope statement as *measured* (not as quoted
from §0); the recommended option with its cost; and an explicit list of every figure this defect
does and does not touch. NFR-021: scan before committing — and note the shipped scanner cannot scan
an uncommitted directory (see §6).

## 6. Two known traps, both already bitten once

- 🔴 **`nfr021_pre_merge_scan.py` cannot scan an uncommitted directory.** Its `changed_files()` is
  `git diff --name-only base...HEAD`; pointed at a fresh result dir it prints "CLEAN — 0 text files"
  — an HK-022 false green. Import its own `scan()`/`classify()` over a directory walk instead.
  Wiring a real directory mode into the tool is a **separate unclaimed follow-up** — take it if you
  want it, but do not silently fold it into this task.
- 🔴 **The result CSVs are UTF-8-with-BOM and CRLF.** Any rewrite must be byte-level; a text-mode
  rewrite silently normalises every line ending. Assert BOM and CRLF counts before and after.

## 7. What has NOT been decided, and is not QA's to decide

The PO has ruled that this gets its own look. The PO has **not** ruled between Option 1 and
Option 2 — §3 is written to be handed back with a recommendation, not executed. Do the ROW 0 checks
and the scope statement, then stop and report.
