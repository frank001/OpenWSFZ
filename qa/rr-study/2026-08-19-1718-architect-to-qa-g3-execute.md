# Architect → QA: EXECUTE G3 — what you run, and the one part you cannot

**UTC:** 2026-08-19 17:18Z
**Supersedes nothing.** Operates under `2026-08-19-1709-architect-to-qa-g3-arming-instruction.md`
(the "17:09Z instruction"). **Where this disagrees with that document, that document wins** — its
§5 gate is unchanged and is the only thing that can pass or fail G3.
**Captain's order:** execute G3.

---

## §0 — The honest split, stated up front

**QA can do everything here except twenty mouse clicks.**

G3's gate reads WSJT-X's Band Activity panel after `File > Open`. That is a GUI action. QA has no
means to drive it — same convention as `gate_render.py`, which has carried a manual §5 step since
June for exactly this reason.

🔴 **I considered two ways to remove the manual step and I am rejecting both. Both would silently
change what G3 measures:**

1. **Play the WAVs through the Captain's live Voicemeeter chain instead.** Tempting — the rig is
   warm and QA can drive playback. **Rejected.** WSJT-X in live mode decodes on 15 s slot
   boundaries; our files are 15.04 s, 15.34 s and up to 17.70 s. A failure would then be ambiguous
   between *synth defect* and *slot-alignment artefact*, which is precisely the isolation G3's own
   docstring was written to preserve (*"a failure here is the synth's problem, not evidence about
   the decoder's live-capture time response"*). **It would convert a clean gate into an
   uninterpretable one.**
2. **Substitute `jt9.exe` offline as the decoder of record.** **Rejected** — see §B. It is barred
   as a reference decoder, and its known duplicate-`(ts, message)` pathology would fire **ROW 0b**
   as a false VOID.

**So: QA runs §A and §B now, autonomously. The twenty clicks stay with the Captain.** I am not
going to dress that up.

---

## §A — Run now, autonomously

1. **Re-take the `ALL.TXT` snapshot immediately before anything else.**
   `C:\Users\Frank\AppData\Local\WSJT-X - FT991A\ALL.TXT` — record **bytes and line count**.
   Architect's 17:09Z baseline: **9 595 310 bytes / 146 167 lines**, mtime 2026-08-15 23:56.
   If it has grown since, say so — it means the instance is decoding something and the boundary
   needs re-establishing, not that anything is broken.

2. **Pre-flight is already cleared, do not redo it.** Architect verified at 17:14Z via
   `Win32_Process`: one `wsjtx.exe` (PID 30016, `--rig-name=FT991A`), `jt9.exe` (PID 15764) with
   `-a "C:\Users\Frank\AppData\Local\WSJT-X - FT991A"` — the running instance is bound to the
   snapshotted `ALL.TXT`. ⚠️ **Do not audit the Captain's per-profile save-folder configuration.**
   WSJT-X setup is the Captain's domain, they have reported all instances now write to separate
   folders, and with one instance running on a file-based gate the old collision is unreachable —
   the check cannot change the verdict (HK-025). The Architect started that audit and was
   correctly stopped.

3. **Build the tally sheet before any result exists**, 20 rows, columns:
   `filename | scenario | label dt_s | decode appeared (Y/N) | decoded text | decode line count`.
   Pre-fill the first three columns from the directory listing so the only thing added later is
   observation. **Committing an empty tally sheet before the run is encouraged** — it is the
   cheapest possible protection against the sheet being shaped by what was seen.

4. **Write the results-report skeleton** with §5's row table pasted in verbatim and the fired row
   left blank. Do not pre-compute `N`.

---

## §B — `jt9` PRE-SCREEN: run it, and it is NOT the gate

`D:\WSJT\wsjtx\bin\jt9.exe` reads `*.wav` directly (`jt9 [OPTIONS] file1 [file2 ...]`). Run it over
all 20 files.

🛑 **STANDING PROHIBITION ACKNOWLEDGED, AND THIS IS NOT AN EXCEPTION TO IT.** `jt9 -d 3` offline is
barred as a **reference decoder** — it ran **+93.8 %** against OpenWSFZ and emitted duplicate
`(ts, message)` pairs, and it VOIDed Angle 1. That prohibition stands untouched. What follows is
not a reference measurement and produces no comparative number.

**Its status, in three hard statements:**

- 🛑 **It CANNOT pass G3.** Only the §5 gate read off WSJT-X's GUI can. A clean jt9 sweep does not
  reduce the Captain's twenty clicks to nineteen.
- 🛑 **It CANNOT fail G3, and specifically it cannot fire ROW 0b.** jt9's documented duplicate-pair
  pathology means a ">1 decode from one file" observation from *jt9* is uninformative about our
  buffer. **ROW 0b reads WSJT-X's panel only.**
- 🛑 **It is NOT citable.** Not in the G3 report's findings, not on the board, not anywhere
  downstream. It goes in an appendix headed *"pre-screen, non-citable, barred decoder."*

**Why run it at all — two genuine uses, both diagnostic:**

1. **It tells the Captain whether to expect trouble before spending twenty clicks.** If jt9 reads
   all 20 correctly, the manual pass is likely a formality. If it stumbles, we know which files to
   watch.
2. 🔴 **It is the sharpest available test of the §5.1 aperture hazard.** If the Captain's GUI pass
   later fails on **S3 parts 8/9** while jt9 read those same two files correctly, that is strong
   evidence the failure is **`File > Open`'s own window**, not our render — the HK-026 distinction
   §5.1 was written to protect. **Record jt9's result on parts 8/9 specifically, before the manual
   pass, so that comparison is available and was not constructed after the fact.**

⚠️ Run jt9 with its **default depth**, and record the exact command line and any `-d` value in the
appendix. Do not tune it to make files decode.

---

## §C — Handover to the Captain

When §A and §B are done, report to the Architect with:

- both `ALL.TXT` figures (baseline and pre-run),
- the empty tally sheet, committed,
- the jt9 pre-screen appendix, clearly marked non-citable, **with parts 8/9 called out explicitly**,
- and a one-line statement of what the Captain now has to do.

**Then STOP and hand back.** Do not attempt the GUI step, do not substitute a decoder, do not play
audio through the live chain.

---

## §D — Standing constraints (unchanged)

- **No `--device` flag anywhere in this task.** If you are choosing an audio device you are running
  the wrong gate.
- **Do not re-render the WAVs.** All 20 are on disk and verified.
- **Never commit `ALL.TXT` or anything derived from it.** Grep every file individually before
  committing — precedent is 203 920 real-callsign rows inside one `S1_matched.csv` that a report
  had already called clean. Anything you must keep goes to `artefacts/` (gitignored).
- **No `src/` change. HK-011 not engaged. No push, no merge (HK-014).**
