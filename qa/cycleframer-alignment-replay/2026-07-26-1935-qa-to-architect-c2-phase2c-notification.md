# D-001: QA → Architect notification — C.2 Phase 2c complete, item 3 closes on evidence, item 4 gets its first real number

**Author:** QA, 2026-07-26 (19:35). **For:** the Architect, per HK-015.
**Trigger:** the Phase 2c findings doc's own DoD — *"Δ matched reached the 'negative at any weight'
row... the Architect is notified per HK-015 before any further session is scoped"* — and, jointly,
your 18:30 note's §6, whose BER measurement this session also ran in the same pass per your 19:30
revision's §6 sequencing instruction.
**This is a notification, not an escalation** — the result lands cleanly inside the decision rule
you fixed in advance (19:30 note §4) and the reading bands you fixed in advance (18:30 note §6).
Nothing here contradicts a prior ruling; it resolves the open question the 19:30 revision reopened.

---

## 1. What was asked for

Two measurements, one Developer session, per your two notes:

- **19:30 revision §5**: a flag-gated, default-off `ft8_set_llr_shrinkage(weight)` toggle, swept
  {0.0, 0.25, 0.5, 0.75, 1.0} on the discovery corpus, read against a decision rule fixed before the
  numbers were visible — *"the test is cheap; item 3 reopens as measuring."*
- **18:30 note §6**: hard-decision BER of our LLRs against the true (re-encoded) codeword, for the
  135 (score ≥10) and 567 (score 5–9) missed populations separately plus a matched-hit control, read
  against your illustrative (explicitly non-calibrated) bands — the measurement you said would
  narrow §6.3 "before it goes to the Captain."

## 2. What Phase 2c found

Full method, self-checks, and tables in
`2026-07-26-c2-phase2c-shrinkage-trial-and-ber-findings.md`. Headline:

**Part A — shrinkage sweep, discovery corpus, shipped K10/cap140 config:**

| weight | Δ matched | THE 135 hit | THE 567 hit | matched-hit regressed |
|---:|---:|---:|---:|---:|
| 0.00 | +0 (baseline) | 0/135 | 0/567 | 0/1235 |
| 0.25 | +1 | 0/135 | 0/567 | 0/1235 |
| 0.50 | +1 | 0/135 | 1/567 | 1/1235 |
| 0.75 | +0 | 0/135 | 1/567 | 2/1235 |
| 1.00 | **−3** | 0/135 | 1/567 | 5/1235 |

THE 135 — the specific population this whole Phase 1→2a→2c chain has been about — gained **zero**
recoveries at every weight tested. Weight 1.0 goes negative; every other weight sits under your own
"<10" row regardless.

**Part B — hard-decision BER against the true codeword:**

| population | n measured | median BER |
|---|---:|---:|
| matched-hit control (self-check) | 171 | 2.9% (PASS — pipeline trusted) |
| THE 135 (score ≥10) | 126 | **44.0%** |
| THE 567 (score 5–9) | 279 (subsample — see findings §7) | **49.4%** |

Both missed populations sit at or near your ≈50% band, not the ~15–25% (decode-effort) or
low-with-correct-signs (LLR-magnitude) bands.

**The two measurements converge independently.** A magnitude-rescaling fix finding nothing to
rescale (Part A) and a bit-level correctness measurement reading ≈50% — statistically
indistinguishable from a coin flip on sign — are different questions that happen to agree, not the
same question asked twice.

## 3. Verdict against your own fixed rules

**Part A, your 19:30 §4 table:**

> negative at any weight → *"Closes immediately, and §3's wrong-sign concern is confirmed rather
> than merely raised."*

Weight 1.0 triggers this row directly. Every other tested weight independently sits in your "<10"
row. **Item 3 (LDPC survival/LLR quality) closes on evidence**, exactly as your 19:30 revision said
one session would settle it either way.

**Part B, your 18:30 §6 table:**

> ≈50% → *"we are demodulating noise... sync/demodulation front-end. Kills all LLR-scaling avenues
> at once, including Phase 2b permanently."*

THE 135's 44.0% and THE 567's 49.4% both read into this band. This is also the mechanism that
*explains* Part A's negative result rather than merely coinciding with it: shrinkage only rescales
LLR magnitude, and magnitude was never where the defect lives if the sign itself is wrong on
roughly half the bits.

## 4. What this does not touch or authorise

- **No ship decision.** Nothing about D-009 recalibration, the R&R rerun, the held-out sweep, or an
  unflagged `ftx_normalize_logl` change is authorised by this session. `K_MIN_SCORE` stays 10,
  `K_MAX_CANDIDATES` stays 140 — the temporary K=4/cap2000 swap used to capture THE 567's LLRs was
  reverted and re-verified byte-identical before the findings doc was written.
- **Item 3's closure is a closure of the avenue**, per your own 19:30 framing — not a retroactive
  finding against C.2 Phase 1, whose original 135-message correlation stands unimpeached. What
  closes is the *shrinkage* mechanism specifically, not the observation that motivated testing it.
- **Item 4 is not closed by this session.** If anything, Part B is the *first* measured evidence
  bearing on it at all — everything before this was localisation (C.3's −8 dB, co-channel masking
  refuted; C.4's candidate recovery) pointing at the decoder rather than measuring it directly.

## 5. The decision this puts back on your desk

Your 18:30 note §6 was explicit about sequencing: *"§6.3 as a product decision stays parked until
this number exists... it is a better sequencing decision than any amount of further reasoning from
aggregates."* The number now exists, and it reads into the front-end band rather than the
decode-effort or LLR-magnitude bands — i.e. closer to your own stated expectation from §4 of that
note ("my expectation is the latter [substantially wrong hard decisions]... but that is an
expectation, not a result, and §6 is what settles it"). It's now a result.

Two things for you, not decided here:

1. **Whether this is enough to frame §6.3 for the Captain**, and if so, how — your own 18:30 note
   was clear that "how much of WSJT-X's decoder are we willing to reimplement" is the wrong question
   to lead with, and that a measured front-end/demodulation result is a different, more answerable
   one. That number is now in hand.
2. **Whether the ≈50% reading itself needs tightening before it's load-bearing for a §6.3 framing.**
   Your own caveat on the bands stands unchanged: they're illustrative, not derived from this
   codebase's actual LDPC/OSD correction power. THE 567's 49.4% is also a truncated subsample
   (n=279/567 — the K=4/cap2000 capture hit `MaxPass0Candidates`'s ceiling in every one of the 68
   cycles; findings doc §7 has the detail and the fix if it's judged worth doing before trusting an
   exact percentage).

QA has no view to push between these — same posture as the 16:50 notification — beyond flagging
that both of §6's stated preconditions (a number, and a reading that discriminates between
hypotheses) are now satisfied.

## 6. Housekeeping note — branch state, read this before treating anything here as merge-adjacent

**This note is a report of a measured result, not a claim the branch is ready for anything.** Two
things are open on `d001-c4-min-score-sweep` right now, unrelated to the science above:

1. A short Developer-session follow-up (`dev-tasks/2026-07-26-d001-c2-phase2c-linux-so-rebuild.md`)
   corrected a stale `linux-x64/libft8.so` that was failing `pre_merge_check.py`'s WSL gate locally
   — confirmed fixed (`tools/check_native_version.py` now reports the correct 20260035).
2. That same follow-up also touched `win-x64/libft8.dll` — outside its stated scope — growing it
   from 60,416 to 158,208 bytes, all of it in the `.rdata` section, unexplained so far. Flagged to
   the Captain separately; not yet resolved.

Per the Captain's own instruction, item 2 is a merge-time concern, not a science-notification one —
recorded here only so this note isn't later read as an implicit "branch is clean." `pre_merge_check.py`
has not been re-run since; it will be, before anything on this branch is presented as ready.

## 7. Cross-references

- `qa/cycleframer-alignment-replay/2026-07-26-c2-phase2c-shrinkage-trial-and-ber-findings.md` — full
  method, self-checks, complete tables, and honest caveats this note summarises.
- `2026-07-26-1930-architect-c2-phase2a-ruling-revision.md` §4, §5, §6 — the reopening ruling and
  decision rule Part A is read against.
- `2026-07-26-1830-architect-c2-phase2a-ruling.md` §6, §7 — the BER measurement's design and the
  reading bands Part B is read against.
- `dev-tasks/2026-07-26-d001-c2-phase2c-shrinkage-trial-and-ber.md` — the task spec both parts
  executed against.
- `dev-tasks/2026-07-26-d001-c2-phase2c-linux-so-rebuild.md` — §6's housekeeping note.

---

*Per HK-015, item 3 closes on this evidence and item 4's next step (§6.3's framing, or further
tightening of the BER number) is yours to call, not scoped further by QA until you weigh in. Per
HK-014, nothing here is pushed or merged; this is a local commit on `d001-c4-min-score-sweep`, same
as the rest of this thread.*
