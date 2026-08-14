# QA → Architect: handoff work queue (§4 W1-W4) done; RC1+RC2 dev-task drafted

**Author:** QA, 2026-08-06 (23:58 UTC, `date -u`, per HK-017). Repo `main` at `2ae5b0e`.
**For:** Architect. §5 is for the Captain.
**Executes:** `2026-08-06-2346-architect-to-qa-handoff-index-and-work-queue.md` §4 (W1-W4).
**Authorisation:** none of this touches `src/`; nothing here required or sought authorisation.

---

## 1. W1 — `_work_recal/` exposure gap: confirmed and fixed

Your suspicion was correct and worse than "unresolved" — it was live. `_work_recal/` was
untracked but **not gitignored**
(`qa/rr-study/d001-param-sweep-2026-07-22/.gitignore` only matched `_work/`, not
`_work_recal/`). I read the actual contents rather than trusting the run script's header
comment that claims it's git-ignored:

- `_work_recal/recall/{decoded,shards}/` — **real exposure.** 45× `"OpenWSFZ ALL.TXT"` (one
  per D-009 grid point) plus per-shard decode output, all real off-air callsigns decoded
  from `20260803_live_run_1713` (spot-checked several rows against standard callsign
  format — not Q-prefix synthetic). This is exactly the NFR-021 exposure a `git add -A`
  would have staged. Per NFR-021 the specific callsigns are not reproduced here or anywhere
  else outside the now-ignored working directory.
- `_work_recal/fp/{s5,s7}/` — **checked, clean.** S5 (noise-only) decodes 0 lines at every
  grid point I sampled. S7 uses Q-prefix synthetic callsigns throughout, matching the privacy
  policy. No real callsigns anywhere in the FP arm.

Fix: added `_work_recal/` to that `.gitignore`, with a comment explaining the gap so it isn't
reopened. Verified with `git status --ignored`: no other `_work*`-named directory anywhere in
the repo has the same gap — the sibling `_work/` dirs were already covered, this was the one
exception. `git status` now shows `_work_recal/` gone entirely (ignored, not untracked).

## 2. W2 — both corrections verified landed

**(a)** The 2123 note's §6 correction block is present in the working tree and matches
`2026-08-06-2144-…m0-m4.md` §0.1 word-for-word on the substance (279/466=59.9%,
141/328=43.0%, the "inverts" framing). Note: your handoff §2 table cites this as landing in
`f7717e3` §0.1, but the actual source is `1135406`'s file (the 2144 spec) — `f7717e3` only
added the M3-void note, which has no §0.1. Minor citation slip in the handoff, not a defect
in the correction itself; flagging per HK-021 discipline rather than silently correcting it.

**(b)** `ORCHESTRATION_REPORT.md`'s M3 section: provenance note present verbatim as
described, `s_low=0.217` marked non-citable, "instrument suspect" appears only inside the
quoted (and explicitly voided) prior reading — not asserted as current. The addendum's
marginal-signal hypothesis does not appear anywhere in the current document — consistent with
"withdrawn," not merely unstruck.

## 3. W3 — `play_pass_guarded()` fix: verified already correctly applied

All three items from the 2249 note §5/§5.1 are present in `replay_lib.py` as committed to the
working tree: the liveness check fires at `i == PREFLIGHT_CYCLES` (one cycle later, not the
old `PREFLIGHT_CYCLES - 1`), `WSJTX_DECODE_LATENCY_SLACK_S`/`PREFLIGHT_EXTRA_WAIT_S` are
fully deleted (grepped for the assignment — no match, not zeroed), and the phase-lock
assertion (`excess < 3.0` s) is in place at the end of the function. No change needed; I did
not touch this file.

## 4. W4 — corrected M3 window-selection rule: recorded, and the tooling updated to match

Your §5.1 rule (contrast>=3.0 AND wsjtx_total>=60, select max wsjtx_total, earliest-UTC
tie-break) existed only in the handoff text, as you said. I did two things, not one:

1. **Independently re-derived it from the archive** (fresh script, not copied from yours) to
   check the claim before trusting it. It reproduces your figures exactly: window
   `260803_234000..260803_234445`, `wsjtx_total=105`, `owsfz_total=157`,
   `mean_combined=13.10`, `contrast=3.031`, and is invariant to the floor at 40/60/80/100 —
   all four floors select the identical window. 4,716 candidates, matching your count.
2. **Updated `m3_select_window.py`** (which still implemented the *second*, void rule —
   10th-percentile ignoring contrast) to implement the third rule, and re-ran it end-to-end.
   Output confirmed identical to my independent check. `m3_window_selection.json` updated
   (ts tokens and integer counts only, NFR-021 clean). Documented both the rule and the
   result as an addendum in `ORCHESTRATION_REPORT.md`'s M3 section, dated and attributed,
   with the superseded second-attempt entry kept rather than deleted.

**This does not mean M3 has been played back.** Window selection is now unblocked
(contrast clears 3.0 where it previously failed at 1.937) and the playback fix is in place,
but the ~15 min live replay itself has not been run — that's still §5/§7.3, the Captain's
call on whether it's worth running at all now that a working reference instrument exists.

## 5. For the Captain — one item beyond W1-W4

Per §7.1 of your handoff, I drafted (did not run)
`dev-tasks/2026-08-06-d001-rc1-rc2-candidate-diagnostics-runtime-caps.md` — RC1 (per-decode
attribution getter) bundled with RC2 (runtime-settable candidate caps + the §3.2 array-sizing
fix you flagged), sequenced so RC2 does not proceed if RC1 fires ROW 2, per your spec. It is
**not authorised and does not ask to be** — it exists so that if/when Captain says go, there's
no drafting delay. RC1 alone is 15 min playback and gates whether RC2's 30-45 min is worth
running at all, matching your own framing.

I have not touched any of §7's five open decisions myself — they're listed there as the
Captain's, not mine, and nothing in §4's work queue asked me to adjudicate them.

---

*Per HK-015 this is QA → Architect. Per HK-014/HK-010 committed locally, no push, no merge
implied or requested. Per HK-011 the dev-task in §5 is a draft only — no `src/` change was
made or started. Per NFR-021 no message text or callsign appears in this document — §1's
finding is stated without reproducing any of the real callsigns it describes.*
