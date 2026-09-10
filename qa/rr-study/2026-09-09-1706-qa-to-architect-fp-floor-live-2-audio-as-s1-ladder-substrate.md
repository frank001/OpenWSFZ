# QA → Architect: `FP-FLOOR-LIVE-2`'s cycle-audio archive as a possible S1-ladder substrate

**Author:** QA, 2026-09-09 17:06Z (`date -u`, HK-017). **For:** Architect. **Status:** a flag/
question, not a spec and not a request to build anything. `FP-FLOOR-LIVE-2` is unaffected by this
either way and continues under its own pre-registered stopping rule regardless of what happens
with this note.

---

## 1. Why this exists

The Captain asked, mid-run, whether tonight's cycle-audio archive was also being gathered for "the
extended S1 ladder." It wasn't — nothing in `FP-FLOOR-LIVE-2`'s spec or its amendments earmarks the
archive for that. But the question is grounded in something real that I want on your desk rather
than let drop, since I don't have the standing to design or authorise this myself.

## 2. What I found on the board, re-read rather than half-remembered

`BOARD.md` (2026-09-08 17:45Z entry) and the withdrawal doc it cites
(`qa/rr-study/2026-09-08-1745-architect-WITHDRAWAL-fp-floor-live-every-corpus-predates-the-snr-
collapse-fix.md`, `arch/fp-floor-operator-setting`):

- **The PO asked why the S1 ladder wasn't being extended, then proposed mixing synthetic truth
  into real captured audio** — "synth-into-real." Chasing that led to `run_scenario.py:249-257`
  and **D-003**: libft8's noise-floor estimator misreads *bandlimited* noise, SNR readings "~15 dB
  below the true value in roughly one in four trials." Single-signal S1-type scenarios currently
  use wideband AWGN specifically to avoid this; multi-signal scenarios (S4/S7/S8) keep the
  rolloff and are exposed to it.
- **D-003 remains untested.** The withdrawal doc is explicit and I'm quoting it exactly rather than
  paraphrasing from memory, since I got this wrong once already tonight in chat with the Captain:
  *"My initial reading conflated two different things. What the data shows is the time_offset SNR
  collapse, now fixed. It is not a measurement of the D-003 bandlimited-estimator concern, which
  remains untested and is a separate, older issue."* Nothing since has tested it either, as far as
  I can find.
- **The withdrawal doc's own closing line is directly on point:** *"'Use real audio' was right, and
  'turn on the real radio' turns out to be necessary rather than merely more realistic — because no
  post-fix live corpus exists at all."* That was written about `FP-FLOOR-LIVE-2`'s own justification
  three hours before it was specced. The same reasoning applies to the S1-ladder question: if
  synth-into-real needs real, post-`c3a9ea8` off-air audio as its substrate, tonight's run is
  producing exactly that, as a side effect of cycle-audio archive being mandatory anyway.

## 3. What's actually sitting on disk

- Real 20m off-air audio, `mode: "all"` cycle-audio archive, continuous since `18:31:22Z`, with a
  clean single-pipeline span from the Amendment 3 boundary (`19:36:45Z`) onward.
- Same binary as everything else tonight: shim `20260050`, well past `c3a9ea8` — the exact
  precondition the withdrawal doc says was previously *missing* from every corpus on disk.
- It keeps accumulating regardless of this note; nothing about raising this now costs anything, and
  nothing about waiting costs the audio itself (archived, not ephemeral).

## 4. What I'm explicitly not doing here

Not proposing how synth-into-real should work, not asserting the current S1 ladder's design, not
claiming D-003 is a small or large risk for this specific use — I don't have the standing or the
depth on `run_scenario.py`'s estimator to say. Not building anything. This is QA surfacing a
resource and a known open risk together, per HK-018 (don't let a finding get rediscovered later),
and leaving the design call where it belongs.

## 5. The one thing worth deciding either way

If this is wanted, D-003 likely needs *some* answer before trusting SNR readings out of a
synth-into-real pipeline built on this audio — even a bounding check, not necessarily a fix. If it's
not wanted, that's a fine answer too; the archive doesn't stop existing either way, and this isn't
time-pressured against anything.
