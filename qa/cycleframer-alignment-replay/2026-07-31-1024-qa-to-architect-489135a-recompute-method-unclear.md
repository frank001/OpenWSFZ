# QA → Architect — dev-task 1 status, and task 4 (489135a recompute) needs a method ruling

**Author:** QA, 2026-07-31 (10:24 UTC, `date -u`, per HK-017). Repo at `41b22bc`.
**Responds to:** `2026-07-31-0910-architect-to-qa-consolidated-handoff-post-measurements-abc.md`
§3, tasks 1 and 4.
**Ask:** task 4 (the 489135a recompute) is queued and nothing waits on it, but I don't have a
mechanical method for it the way Measurement D got a full spec (`0853`). Rather than guess and
burn the ~2.6h re-decode on a design I invented myself, I'm putting the open question to you,
per this thread's own established discipline (A/B/C/D all got a pre-registered method before
running). Task 1 status is included below for completeness, not because it needs a ruling.

---

## 1. Task 1 (drift fix) — done, verified, awaiting the Captain's push sign-off only

Not part of the ask — recorded here so this document stands alone.

- **1a (oracle):** landed, confirmed red against `main` (4.17s / 2.0s drift, both cases).
- **Escalation from the Developer session:** the oracle's `FakeClock` never advanced in either
  test, which only mattered once a wall-clock-reading fix existed to test. Verified myself,
  independently — not taken on the write-up's word (see §3 of
  `2026-07-31-1013-qa-review-dev-task-1b-verified-and-accepted.md` for the full chain: reverting
  just the `src/` fix reproduces the original 4.17s/2.0s failures exactly on the patched oracle,
  confirming the harness change didn't launder the regression test).
- **My own dev-task was wrong on one point** — I'd specified flooring `cycleStart` to the
  nearest 15-second UTC grid line. Tested that literally: it still fails, ~4.17s/2.0s,
  materially unchanged from broken, because 48.4 ppm over 24h never accumulates a full 15s of
  drift for flooring to correct. The shipped fix (raw wall-clock reading, residual absorbed in
  the timestamp) is the one that actually works. Corrected in place in the dev-task doc with a
  visible addendum, not silently edited.
- **Full verification, run myself:** `Ft8.Tests` 301/301, `Daemon.Tests` 600/601 (the one
  failure is the already-catalogued full-suite-load flake, confirmed passing solo — not a
  regression), `E2E.Tests` 7/7 with no orphaned daemon processes afterward.
- **Outstanding:** the `src/` diff has not been pushed. Per HK-011 that needs the Captain's
  explicit sign-off, which hasn't been requested yet pending this document.

## 2. Task 4 — what's been done so far

Per the handoff's costing (§2.4/§6b.4 of the prior rulings), I went to locate the corpus and
confirm the cost estimate before asking anything, rather than asking blind.

- **Corpus located:** `artefacts/20260728_live_run_2354-8080/wsjt-x/wav/` — **3,575 WAV files**,
  exactly matching `anova_report_40m.md`'s "WAV cycles fed to jt9: 3575." Session spans
  `260728_235445` → `260729_145145` UTC (~14h57m).
- **"Did not retain its `jt9_ALL.TXT`" — confirmed**, not assumed: no `jt9`-named file anywhere
  under that artefact directory.
- **The ~2.6h cost checks out arithmetically**, which tells me something about scope: 3,575 WAVs
  × 2.66s/WAV (the measured jt9 rate from `6b.4`'s cost table) ≈ 9,510s ≈ **2.64h**. That's the
  cost of decoding the **entire** session, not a pre-filtered subset — meaning jt9 has to touch
  every WAV regardless of where the eventual drift-free cutoff lands, and the "drift-free
  window" must therefore be a filter applied **after** decoding, at parity-calculation time, not
  a restriction on which WAVs get fed to jt9. I'm fairly confident in this part; it's the next
  part I'm not.

## 3. Where I'm stuck — the cutoff method itself

Every other measurement in this thread (A/B/C/D) got a method spelled out before it ran: a
sampling design, a reading rule fixed in advance, self-checks. Task 4's entry in the handoff
(`0910` §3) gives cost and consequence but not method — it's the one item in the queue that was
scoped as "add it to the queue" (per `0029` ruling §6 item 3) rather than designed. I don't want
to invent the design myself and then be the one grading it, especially given this measurement's
entire point is to **restore or refute a claim you yourself withdrew** — that's exactly the kind
of result where an after-the-fact, QA-invented method inviting the same "one party designs,
runs, and reads it" problem your `0910` §6 disclosure flagged for Measurement D.

Two candidate methods, as far as I can see, and I don't think it's my call which:

1. **Measure this corpus's own drift directly.** Reuse `measure_drift_8080_session.py`
   (already validated: synthetic control, sign convention proven, used for Measurement C) on a
   sample of 489135a's own cycles, fit its own `lag_seconds ~ elapsed_h` regression rather than
   assuming the `20260729_live_run_1831-8080` session's coefficients
   (`-0.2366 - 0.1744*elapsed_h`) transfer to a different session on presumptively the same
   device. Per `6b.4`'s cost table this is cheap (~2 min), and it's the more rigorous option —
   but "presumptively the same device" is doing some work in that sentence and I haven't
   verified it.
2. **Reuse the other session's regression as-is.** Cheaper in the sense of one fewer step, but
   it assumes transferability across sessions that hasn't itself been checked, and this whole
   defect's history (three prior live-test rounds burned, per the handoff §4.3) argues for
   checking assumptions rather than carrying them forward.

Open questions I can't resolve without you:

- Is 489135a on **the same physical device** as `20260729_live_run_1831-8080` (the one with the
  established 48.4 ppm / regression), or a different one? If different, method 2 is not
  available at all, and I don't have independent confirmation either way beyond both being
  called "the affected device" in passing.
- Once a cutoff is obtained (by whichever method), is the read rule "restrict to cycles with
  `|predicted lag| < 0.5s`" (matching Measurement C's healthy-stratum definition exactly, for
  consistency), or something else specific to a single-corpus recompute rather than a two-arm
  comparison?
- Does the reference-method by-product (jt9-re-decode vs. live-WSJT-X-`ALL.TXT`, still
  unevidenced per `0029` §2.5) piggyback on this run at no extra cost the way it was scoped as a
  by-product in `6b.4`, or is that a separate ask?

## 4. What I have not done

- Not run jt9 against any part of this corpus.
- Not touched `_work/` or produced any per-cycle output.
- Not assumed a method and proceeded — this document exists specifically because I didn't want
  to guess on a measurement whose entire purpose is restoring/refuting a withdrawn claim.

## 5. Boundary check

Per HK-015, this is QA → Architect (a design/method question), separate from the QA → Captain
status update on task 1 above which needed no ruling. No `src/` touched. No push, no merge, no
`pre_merge_check.py` (HK-006 — Captain's trigger only, at merge time). Nothing here re-opens the
diagnostic programme beyond the one already-queued task 4 item; §0's stop rule is unaffected.

## 6. Cross-references

- `qa/cycleframer-alignment-replay/2026-07-31-0910-architect-to-qa-consolidated-handoff-post-measurements-abc.md`
  §3 task 4, §7 document map.
- `qa/cycleframer-alignment-replay/2026-07-31-0029-architect-ruling-measurements-abc-and-drift-root-cause.md`
  §2.4, §6 item 3 — where task 4 was queued and costed.
- `qa/cycleframer-alignment-replay/2026-07-30-2253-architect-ruling-cross-band-density-law-and-capture-chain.md`
  §6b.4 — the cost table task 4's ~2.6h and the reference-method by-product both come from.
- `qa/cycleframer-alignment-replay/2026-07-31-0008-qa-measurement-c-result-drift-collapse-confirmed-recoverable.md`
  — the validated cross-correlation method (`measure_drift_8080_session.py`) candidate method 1
  would reuse, and the healthy-stratum `|lag| < 0.5s` definition candidate cutoff rule 1 would
  match.
- `qa/endurance/2026-07-29-489135a/anova_report_40m.md` — the corpus's existing (contaminated)
  parity figure, 62.4%, suspended pending this recompute.
- `artefacts/20260728_live_run_2354-8080/wsjt-x/wav/` — the 3,575-WAV corpus itself, located and
  confirmed this session; git-ignored, NFR-021.
