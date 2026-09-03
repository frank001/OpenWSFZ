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

---

# AMENDMENT 1 — 2026-09-03 16:16Z: ✅ PO RULING — **OPTION 2**, and how to execute it safely

**The PO has ruled Option 2: delete `level_dbfs`, declare S5 single-level.** Ruling taken on QA's
2026-09-03 report (all four ROW 0 PASS) plus the Architect's and QA's concurring recommendations.
§7 above is discharged.

🔴 **Option 2 is not a free edit, and this amendment exists because I nearly handed it over as
one.** Two code paths read the key, and one of them is not the amplitude path.

## A1.1 What the deletion actually changes, read from the code (not assumed)

1. **`harness/run_scenario.py:514` — `level_dbfs = part.get("level_dbfs", -20)`.** The default is
   `-20`. ⇒ For the **three uniform-`-20` files** (`s5-noise-wide.json`, `s5-noise-wide-n300.json`,
   `s5-noise-diag40.json`) deleting the key feeds the amplitude formula the **identical constant**.
   Byte-identity there is provable from the default, not merely expected.
2. **The same line for `s5-noise.json` part 1 (`-10`)** changes the pre-normalisation amplitude
   from `10^(-10/20) = 0.3162` to `10^(-20/20) = 0.1`. Peak normalisation then divides by the
   buffer's own peak, so the delivered audio is **mathematically identical** — but two different
   float multiplies followed by a division are **not guaranteed bit-identical**. That is what ROW 0j
   below is for.
3. 🔴 **`harness/run_scenario.py:1113` — `true_snr_db = part.get("level_dbfs", "")`.** This is a
   *second, unrelated* consumer: it writes `truth.csv`'s `true_snr_db` column for S5. Deleting the
   key changes that column from `-20`/`-10` to the **empty string** for every S5 row. Architect's
   own read of the consumers: S5 is absent from `analyse.py`'s `DECODE_RATE_CONFIG`, and every
   downstream read coerces (`pd.to_numeric(..., errors="coerce")` at `analyse.py:601/868/998/1198`,
   `analyse_xplat.py:130/245`), so this *should* be inert — **"should" is not a verdict**, which is
   what ROW 0l is for.

## A1.2 🛑 Scope bar — do NOT delete the key from `qa/rr-study/awgn-fp-replay/scenarios/`

`s5-noise-row0c-minus10.json` / `-plus10.json` use `level_dbfs` **functionally**: they are rendered
through the level-*preserving* renderer, where the key is the only thing that creates the ±10 dB
legs ROW 0c measured. `s5-noise-m1m4.json` is a dated artefact of a completed arm. **All three stay
exactly as they are.** After this deletion `s5-noise-m1m4.json` no longer matches its parent
`scenarios/s5-noise.json`; that divergence is intended — **say so in the commit message** and leave
the artefact pinned, so the M1–M4 result stays reproducible from the file it was actually run from.

## A1.3 Pre-registered checks on the deletion itself (mechanical, HK-021)

Run in order. Rows are mutually exclusive and exhaustive; each branch changes the verdict.

- **ROW 0j — delivered audio unchanged, byte level.** Render S5 parts 0/1 for the 60 in-chain seeds
  through the **real, unmodified** `--dry-run --dump-wav-dir` path, before and after the deletion.
  SHA256 all 120 files. **PASS iff 60/60 pairs are identical.** ⇒ Option 2 lands with the
  fifteen-sweep comparability argument fully intact, which is the entire reason it was preferred.
- **ROW 0k — fires only if ROW 0j fails: is the difference decode-invisible?** Decode all 120 WAVs
  through the existing `AwgnFpReplayTests` seam. **PASS iff every slot's decode set is identical
  across the pair** (count, message, freq, DT, reported SNR). ⇒ Option 2 lands, **with the byte
  difference disclosed in the report and on the board** — never silently.
- **ROW 0l — `truth.csv` consumers survive the empty `true_snr_db`.** Regenerate a truth.csv with
  the key deleted; run `analyse.py` (and `render_report.py`) over an existing S5 matched CSV.
  **PASS iff no exception is raised and no S5 figure changes.**
- 🛑 **STOP branch, and it is a real one: if ROW 0k fails, do not chase bit-parity and do not tune
  the renderer.** Revert the deletion, leave the four scenario files exactly as they are, and report
  that the honest outcome is **record-correction-only** — which QA's §4 pass has already delivered
  in full. A mislabelled key that is provably inert costs less than a re-baseline nobody asked for.
  Escalate to the Architect; do not re-decide the option yourself.

## A1.4 Record correction — one addition to what QA has already done

QA's §4 corrections stand as made. Add one line, dated, to `STUDY-SPEC.md`'s R&R-009 correction
paragraph: that the key was **deleted** on the PO's 2026-09-03 Option 2 ruling, with the ROW 0j/0k
outcome stated as measured. The 37/15 event-count data stays untouched — the ban on rewriting
historical sweep reports (§4 item 3) is unaffected by this ruling.
