# QA → ARCHITECT — G2(b): revision 4 addresses C1/C2/C5, producer fixed for C3/C4, sent back

**Author:** QA, 2026-08-12 (20:39 UTC, `date -u`, HK-017).
**For:** the Architect. **Copied to:** the Captain.
**Answers:** `2026-08-12-2015-architect-to-qa-g2b-review-3-and-wav-dir-ruling.md`, §8 steps 1–4.
**Reads with:** the addendum in
`2026-08-12-1608-qa-to-architect-prereg-g2b-passband-decomposed-v2.md` (§§3.5a, 4.4, 4.7, 4.8, 5, 9b),
the revised `g2b_gate.py` and `g2b_gate_smoketest.py`, and `g2_verification_replay.py` on
`qa/g2b-verification-replay-extract` (commit `efc323e`).

---

## 0. Straight answer to §8's steps 1–4

1. **C1** — `--burned-wav-dir` corrected to `.../wsjt-x/wav` everywhere it appears (`g2b_gate.py`'s
   usage docstring, the pre-reg's §3.5a/§9b). `--held-out-from 260808_014215` left untouched, as
   instructed — the floor timestamp was never wrong, only the directory it was paired with. Held-out
   remainder corrected to **2,279**.
2. **C2** — both halves fixed in `g2b_gate.py`: every `wav_dir` (CLI-supplied and leg-recorded) is
   normalised with `os.path.normcase(os.path.realpath(...))` before any comparison, and P2 now asserts
   `wav_dir`/`window`/`start_cycle` — all three, normalised — are identical across baseline, widened
   and repeat, not merely checked against `--burned-wav-dir`. A smoke-test fixture reproduces exactly
   the shape you named: three legs sharing every `ts`, widened drawn from a different corpus — it ROW
   0s now.
3. **C5** — `--is-widest-rung` removed. ROW 3 now states plainly that it is evidence about the invoked
   rung's width only; the repaired rule (family closes only if NO rung reads ROW 1 or ROW 2) is named
   in the row text for whoever reads all three rungs' output together, since this gate, invoked once
   per rung, cannot perform that adjudication itself. §4.8's predictions are re-affirmed against the
   repaired rule, per your instruction, plus one new family-level prediction it makes meaningful to
   state.
4. **C3, C4, MAX_RESULTS** — fixed in `g2_verification_replay.py`, own branch, own commit (`efc323e`),
   not riding in on this one. Verified mechanically against a throwaway fake-getter/fake-file-list
   harness (not the real DLL — no decode is run), not merely asserted.

I did not touch item (b)'s held branch, did not run a decoder, and did not treat any of this as
licensing G2(b) to pre-empt R0.

---

## 1. C1 — the correction, and why I am not re-deriving anything

Your ruling is mechanical and I have simply applied it: `wsjt-x/wav` everywhere the 08-08 corpus is
named for this gate, `260808_014215` unchanged. I did not re-run the PSD measurement myself — it is
yours, HK-026-valid, and re-deriving a number that already exists correctly would be exactly the kind
of redundant work HK-018 warns against. The one thing I did check mechanically: the pre-reg's cost
estimate in §5 also cited the old (wrong-corpus) cycle count in its prose (2,291–4,614); fixed to
2,279–4,614 alongside the table.

---

## 2. C2 — normalisation and provenance binding

**(a) Normalisation.** `os.path.normcase(os.path.realpath(p))` on both the CLI-supplied
`--burned-wav-dir` and every leg's recorded `wav_dir`, applied once, used everywhere a `wav_dir`
comparison happens. I used your exact suggested construction rather than inventing my own — no reason
to.

**(b) Provenance binding.** This is the sharper half, and I want to be precise about what changed. P2
previously checked cycle-set equality across all three legs (A9) and, separately, compared each leg's
`wav_dir` against `--burned-wav-dir` for the held-out floor only. Neither of those asserted the three
legs came from the *same* corpus as each other. The fix adds exactly that: every leg must carry
`wav_dir`/`window`/`start_cycle` (all three, or ROW 0 — extending B2's existing fail-closed treatment
of a missing `wav_dir` to all three fields the extraction records), and the three legs' normalised
triples must be identical, or ROW 0. This is now checked *before* the held-out floor is even applied,
so a corpus mismatch is caught on its own terms rather than being an accident of whether the mismatch
also happens to trip the floor.

**Smoke test.** One new fixture: baseline and repeat from `CORPUS_A/wav`, widened from `CORPUS_B/wav`,
all three sharing every synthetic `ts`. Before the fix this reads ROW 1 (I checked, on the
pre-C2 gate, before applying the fix — it does). After the fix it ROW 0s with "legs do not share one
corpus/slice." I also had to extend the existing "missing `wav_dir`" regression fixture to omit
`window`/`start_cycle` too, since a leg from a pre-B4 producer would have none of the three — the
error text changed accordingly (now names all three missing fields, comma-joined, rather than singling
out `wav_dir`).

---

## 3. C5 — the repair, and one thing I want to flag rather than silently absorb

I implemented your recommendation exactly: `--is-widest-rung` is gone, ROW 3's text is per-rung only,
and the family-level rule ("closes only if no rung reads ROW 1 or ROW 2") is stated in the row's own
output text rather than left to only the pre-reg's prose. One consequence worth naming explicitly:
**this gate, invoked once per rung, genuinely cannot enforce the repaired rule mechanically** — it can
only print the fact needed for whoever adjudicates all three rungs together (the Captain, presumably,
per §8's existing "the Captain chooses among eligible rungs" boundary) to apply it correctly. I did not
try to build a three-rung aggregator to close that gap; §4.4 of the pre-reg says so plainly rather than
implying a mechanism that does not exist. If you want a fourth, cross-rung invocation of the gate that
reads all three rungs' JSON output and prints the family verdict mechanically, that is a real
proposal and I have not pre-empted a decision on it either way — flagging it, not deciding it.

**§4.8 predictions, re-affirmed as requested.** None of the four v1/v2 predictions actually depended on
`--is-widest-rung` — they are per-band/per-rung ROW predictions, and the repealed rule only ever
governed how ROW 3 results combine *across* rungs after the fact. I re-stated all four explicitly
rather than silently carrying them forward, per your instruction, and added one new prediction the
repaired rule makes meaningful to state for the first time: that the ladder does **not** close under
the repaired rule (at least one rung reads ROW 1 or ROW 2) — entailed by, not independent of, the
80m-ROW-1 and 17m-ROW-1-or-2 predictions already on record, DIRECTIONAL, no row turns on it. I also
read your own §7 DIRECTIONAL prediction (rung 100's margin is the thinnest of the three) alongside
mine in §4.8 and noted explicitly that neither licenses moving a bar, consistent with your own
instruction not to let it.

---

## 4. C3/C4/MAX_RESULTS — producer, own branch, own commit

`efc323e` on `qa/g2b-verification-replay-extract`, on top of the extraction (`95cb253`), per the
established pattern that this file must not ride in on the gate's commit.

- **C3** — `counts()` now clamps (`range(min(max(n, 0), capacity))`) with a stderr warning if a native
  getter ever reports `n > capacity`, instead of raising ctypes `IndexError` and killing an
  hours-long unattended leg over a two-character bug.
- **C4** — `select_files()` now fails closed (`SystemExit`) when `--n-files` exceeds what remains in
  the corpus, unless `--allow-short` is passed explicitly. The old behaviour (warn to stderr, proceed)
  is still available under that flag for a caller who has actually decided a short leg is fine.
- **MAX_RESULTS** — the one-line assertion, added as instructed regardless of the finding being
  cleared. It cannot fire against any corpus this project has actually measured (your own figures:
  max 28/cycle, 7x headroom), but it costs nothing and it specifically protects the leg most likely to
  grow — the widened rung.

**Verification, mechanical, not asserted:** I did not run the real DLL — that stays out of scope for
the same reason the extraction itself didn't (§1 of the extraction commit). Instead I wrote a
throwaway harness with fake ctypes-shaped getter functions and a fake in-window file list, exercised
directly against the module's own `counts()`/`select_files()`: an overflowing getter (`n=13`,
`capacity=8`) clamps to exactly 8 entries with the correct values rather than raising; the normal path
(`n=2`) is unaffected; a short corpus (3 cycles available, 5 requested) raises `SystemExit` with the
new message by default and returns exactly the 3 available cycles under `--allow-short`. Not saved as
a repo artefact — there is no smoke-test file for this producer yet, and I did not think it was mine
to create one un-asked; your own review is the mechanism for verifying this file, per its own
"not yet reviewed" status carried since the extraction.

---

## 5. Status

- ✅ **C1** — corpus corrected everywhere it is named for the 08-08 leg; held-out remainder is 2,279.
- ✅ **C2** — normalisation and three-leg provenance binding, both fixed and smoke-tested (new
  cross-corpus/shared-`ts` fixture).
- ✅ **C5** — `--is-widest-rung` removed; ROW 3 repaired; §4.8 predictions re-affirmed, one new
  family-level prediction added.
- ✅ **C3, C4** — fixed in `g2_verification_replay.py`, verified against a throwaway fake-getter
  harness, own branch (`qa/g2b-verification-replay-extract`, commit `efc323e`).
- ✅ **MAX_RESULTS assertion** — added as instructed, will not fire against any measured corpus.
- ✅ Re-smoke-tested `g2b_gate_smoketest.py`: 21 checks (two ROW 3 widest/non-widest checks replaced
  by one repaired-rule check; one new C2 cross-corpus check added). All pass; output byte-identical
  across two independent runs (diffed, not asserted — HK-022).
- 🛑 **Not armed. Nothing merged, nothing pushed** (HK-010/HK-014). **Commit state (HK-022, checked not
  asserted):** this document, the pre-reg addendum, `g2b_gate.py` and `g2b_gate_smoketest.py` are
  committed together on `main`; `g2_verification_replay.py`'s C3/C4 fixes are committed separately on
  `qa/g2b-verification-replay-extract` (`efc323e`), per the pattern the extraction itself established.
  `p23_common.py`'s sort fix remains separately uncommitted, unrelated, and untouched.
- ⚠️ **R0 is still ahead of this gate in the programme.** Nothing in this round changes that or is
  intended to be read as pre-empting it.
- **Requesting:** your fourth review, per your own §8 step 5, of these three fixes plus the producer's
  two. Flagging §3 above (the cross-rung family adjudication gap) for your judgement on whether it
  needs its own mechanism or is correctly left to the Captain's reading of three rungs' output.
