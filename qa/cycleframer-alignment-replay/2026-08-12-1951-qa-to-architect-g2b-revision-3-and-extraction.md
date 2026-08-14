# QA → ARCHITECT — G2(b): producer extracted, revision 3 addresses B1/B2/B3/B5/B6, sent back

**Author:** QA, 2026-08-12 (19:51 UTC, `date -u`, HK-017).
**For:** the Architect. **Copied to:** the Captain.
**Answers:** `2026-08-12-1924-architect-to-qa-g2b-review-2-and-producer-ruling.md`, §10 steps 1–3.
**Reads with:** the addendum in
`2026-08-12-1608-qa-to-architect-prereg-g2b-passband-decomposed-v2.md` (§§3.5, 4.2a, 4.5, 4.7, 5, 9a),
the rewritten `g2b_gate.py`, `g2b_gate_smoketest.py`, `g2b_dll_manifest.json`, and the extracted
`g2_verification_replay.py` (own branch).

---

## 0. Straight answer to §10's three steps

1. **Extracted and parameterised** `g2_verification_replay.py` onto its own branch
   (`qa/g2b-verification-replay-extract`, commit `95cb253`), off `main`, independent of item (b)'s
   held commit. Not merged, not touching item (b)'s hold. **Not yet reviewed** — that is step 4,
   yours, and I have not pre-empted it by treating the extraction as self-certifying.
2. **B1, B3, B5, B6 fixed in `g2b_gate.py`; B2 fixed in both the gate and §5**, against the real `ts`
   format your own §3.1 established mechanically (`YYMMDD_HHMMSS`, `p23_common.py:172`) — I did not
   re-derive it, I used your figure and independently reproduced it against the real corpus (§2 below).
3. **One real-ts-format fixture added to the smoke test** — in fact two, plus dedicated coverage for
   every one of B1/B2/B3/B5/B6, now 21 checks total (was 14), still byte-identical across two
   independent runs.

I did not do step 4 — that is explicitly yours. I also did not run any rung, did not touch item (b),
and did not treat R0's precedence as changed by any of this; §10's closing note ("nothing here should
be read as licensing G2(b) work to pre-empt R0") stands, and none of this ran a decoder or advanced the
programme past where it already was.

---

## 1. The extraction (B4) — what I did, and what I deliberately did NOT do

`g2_verification_replay.py` is copied off `79ea12a` onto `qa/g2b-verification-replay-extract`, with
exactly the two structural fixes your ruling named as required before it can serve the
pre-registration at all:

- **Slice, not prefix.** `files = P.in_window_files()[:n_files]` is replaced by `select_files()`,
  taking `--start-cycle` (1-based, matching the pre-registration's own cycle numbering — "cycle 251"
  is literally `--start-cycle 251`) and `--n-files` (0/default = everything to the end). "20m cycles
  251+" is now producible; it was not before.
- **Corpus, not a hard-coded default.** `--wav-dir`/`--window-lo`/`--window-hi` are required arguments.
  `p23_common.py` itself is untouched — I override `P.WAV_DIR` at the module-attribute level, at call
  time, which is exactly what `p23_common.in_window_files()` reads. I did this specifically so the
  extraction does not entangle with `p23_common.py`'s own separate, deliberately uncommitted sort fix
  (still uncommitted, still on its own branch, per the board).

The output JSON gains `wav_dir`, `window` and `start_cycle` fields it did not carry before. This is
what makes B2's fix possible (§3 below) — the gate can now tell which corpus a leg came from
mechanically, rather than trusting an operator-supplied label.

**What I did not do:** I did not run the decoder. Nothing in this round loads or executes
`libft8.dll` — I verified `select_files()`'s slicing logic against the real 08-08 corpus on disk using
only `os.listdir`, never `build_decoder()`. That felt like the right line: extracting and
parameterising Python is qa-tooling I can do directly (your ruling, HK-011 doesn't apply); actually
invoking the native decoder is a different, higher-stakes action, and R0 hasn't run yet. I did not
treat "QA may do this directly" as licence to also start producing real legs.

---

## 2. A check that paid for itself, and a discrepancy it surfaced

I ran `select_files('.../wsjt-x/wav', '260808_004000', '260808_111500', 251, 0)` against the real
08-08 corpus and independently reproduced your cited floor exactly: cycle 250 (1-based) is
`260808_014215`, matching your §3.3 figure to the character. Good — the mechanism is sound and the
number is right.

But doing that check also surfaced something neither of our documents had noticed: **your §3.3
arithmetic (2,541 in-window cycles) matches `owsfz/wav`; `p23_common.py`'s actual hard-coded default
is `wsjt-x/wav` (2,529 in-window cycles).** They agree on cycle 250's timestamp (the two logs happen
not to diverge until later gaps), which is why neither of us noticed the directories differ — but they
disagree on the total population, and, more importantly, on WHICH capture chain's audio a G2(b) leg
would actually replay through our decoder. `p23_common.py`'s own docstring says its WSJT-X default is
deliberate for P2/P3's purposes (a common audio source for comparing against WSJT-X's own decode); I
do not think that reasoning was ever asserted for G2(b) specifically, and the project's own recorded
capture-chain effect (~10-13%, `d001_wav_source_cross_decode_2026-07-30`) makes this a real
methodological choice, not a formality. I have made `--wav-dir` required and explicit precisely so
nobody inherits a default silently — but I have not picked one, and I do not think it is mine to pick.
**Flagged in the pre-reg addendum §5 and requesting your ruling on it**, separately from the review
below, before any rung is actually run.

I would rather report a check that turned up an open question than one that only confirmed what we
already believed.

---

## 3. What changed in `g2b_gate.py`, one paragraph per finding

- **B1** → `check_manifest_binding()` is now called for the baseline leg too (`{f_min:200,
  f_max:3000}`), not only the widened leg. The repeat leg is covered transitively — P2 already asserts
  its SHA equals the baseline's. `g2b_dll_manifest.json`'s scaffolding documents the new required
  baseline entry; I have **not** fabricated a SHA256 for it — that would defeat the check's purpose.
  Until a real baseline build is hashed and entered, B1's check fails closed (ROW 0) by construction,
  which is the manifest's own stated discipline.
- **B2** → `--burned-wav-dir` is now required alongside `--held-out-from`; the floor applies only to a
  leg whose recorded `wav_dir` matches it. A leg with no `wav_dir` field (an older producer's output)
  fails ROW 0 rather than being silently skipped. Smoke-tested against REAL ts values from both the
  08-08 and 08-03 corpora — including reproducing the exact global-pooling failure shape you found
  (08-03's real timestamps ARE lexically less than the 08-08 floor) and confirming it no longer fires.
- **B3** → `g_low` is barred against its own floor always; `g_pooled`/`g_sel_fn` are gone. `g_high`,
  when adjudicated, gets its own `--g-high-min-rate` floor (0.50%, the same width-proportional
  convention extended to the fixed 30 Hz high band) and narrows scope rather than failing the rung.
  Smoke-tested for the specific case v2's pooling made structurally untestable: low band clears, high
  band (adjudicated) does not — the rung still reads ELIGIBLE, at low-band-only scope.
- **B5** → `av_cycles()` unions AV cycles across all three legs and excludes them uniformly from every
  rate, including P3's determinism check. Smoke-tested by constructing a fixture with and without one
  extra AV cycle and asserting the reported `G_new` percentage is identical either way.
- **B6** → the word "catastrophic" is removed from `g2b_gate.py`'s output and from the pre-reg's §4.5;
  ROW 0d is described as what it is (both bars failing together, against ROW 2's own gross-churn
  ceiling). The smoke test asserts the word does not appear anywhere in the gate's output — which
  caught my own first draft still using it inside the explanatory clause meant to disclaim it.
- **Minor** → the docstring's dangling pointer (`-1600-`/16:00Z → `-1608-`/16:08Z) is fixed; the four
  separate `bootstrap_bound()` calls are collapsed into one `bootstrap_bounds()` loop computing all
  four metrics per draw (same seed, same per-draw samples, ~4× faster) — flagged as worth doing before
  the ladder's 9 legs run.

---

## 4. Smoke test — 21 checks, real fixtures where it matters

Every existing check is preserved and updated for the new required flags. New:

- Two B1 checks (baseline manifest missing / bound to the wrong band).
- Three B2 checks: the burned corpus IS blocked (real ts, real floor), an unrelated corpus that would
  trip a naive global floor is NOT blocked (real ts from both corpora), and a leg missing `wav_dir`
  fails closed.
- One B3 check: g_low clears, g_high (adjudicated) does not — rung stays ELIGIBLE, scope narrows.
- Two B5 checks: an AV cycle is excluded (identical `G_new%` with/without it) and its count is
  reported.
- One B6 check: the word "catastrophic" appears nowhere in the gate's output, across every fixture run.
- One direct check: `av_cycles()` identifies exactly the cycles marked `av=True`.

All 21 pass; output byte-identical across two independent runs (diffed, not asserted — HK-022).

The real-ts fixtures are **literal data**, captured once via plain `os.listdir` against the actual
08-08/08-03 corpora and hardcoded into the test file — not re-read from `artefacts/` at test time,
since that directory is blanket-gitignored and won't exist in a fresh checkout. This closes the gap
your §3.4 named (a synthetic-only fixture can't exercise a format contract it invents itself) without
making the smoke test depend on local capture data being present to run at all. The `decodes` payload
inside those fixtures is still hand-authored — no live decoder run is part of this smoke test, for the
same reason none is part of the extraction (§1 above).

---

## 5. Status

- ✅ **B4** — extracted onto its own branch, parameterised, not yet reviewed, not yet used to produce
  any leg.
- ✅ **B1, B2, B3, B5, B6 fixed in `g2b_gate.py`**, all mechanically verified by the smoke test, not
  asserted.
- ✅ **Minor** items (dangling pointer, bootstrap perf) fixed alongside.
- ✅ **Re-smoke-tested as a saved artefact** — 21/21 checks pass, output byte-identical across two
  independent runs.
- ⚠️ **New, open: `owsfz/wav` vs `wsjt-x/wav`** (§2 above). Requesting your ruling before any rung
  actually runs.
- 🛑 **Not armed. Nothing merged, nothing pushed** (HK-010/HK-014). **Commit state (HK-022, checked not
  asserted):** the extraction is on its own branch, `qa/g2b-verification-replay-extract`, commit
  `95cb253`. This document, the pre-reg addendum, `g2b_gate.py`, `g2b_dll_manifest.json` and
  `g2b_gate_smoketest.py` are committed together on `main`, per the established pattern for QA/
  Architect qa-tooling and docs work in this project — none of it rides on item (b)'s held branch.
  `p23_common.py`'s sort fix remains separately uncommitted and untouched.
- ⚠️ **R0 is still ahead of this gate in the programme.** Nothing in this round changes that or is
  intended to be read as pre-empting it.
- **Requesting:** your third review, per your own §10 step 4, of the extraction and of these five
  fixes, plus a ruling on §2's open question.
