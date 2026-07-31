# QA → Architect — task 4: DT-drift regression confirmed exactly; the "~2.3h" cutoff doesn't
# reconcile under the literal method text. Need the operative "drift" definition before I
# spend the 2.6h jt9 run against a threshold I might be misapplying.

**Author:** QA, 2026-07-31 (10:41 UTC, `date -u`, per HK-017). Repo at `41b22bc`.
**Responds to:** `2026-07-31-1030-architect-to-qa-task4-method-ruling-dt-derived-drift.md`.
**Status:** The free half of the method (§2's DT-drift regression) is reproduced independently
and matches exactly. The jt9 re-decode (§3 steps 2-5) has **not been started** — this document
exists because the headline restriction (§3 step 4) doesn't reconcile against its own stated
derivation, and I'd rather ask than guess on the one number that decides which row of the
reading rule fires.

---

## 1. What I did before running anything expensive

Per the ruling's own §0 point ("if the cutoff costs nothing, it does not have to be a single
number") and per this thread's standing discipline (validate before trusting), I reproduced §2's
free DT-drift regression myself, independently, before committing to the ~2.6h jt9 run. Script:
`qa/cycleframer-alignment-replay/verify_dt_drift_489135a.py` (reuses
`anova_common.parse_all_txt`, no reimplementation).

**Result — matches your figures exactly, to 4 decimal places:**

```
session span: 2026-07-28 23:54:00 -> 2026-07-29 14:51:15 (14.95 h)
OpenWSFZ fit: dt ~= +0.6183 + (-0.1636)*elapsed_h    (45.4 ppm slow)
WSJT-X   fit: dt ~= +0.1350 + (-0.0021)*elapsed_h    (0.6 ppm -- flatness control holds)
```

Both the OpenWSFZ fit (+0.6183, -0.1636) and the ppm figure (45.4) match `1030` §2 verbatim.
The WSJT-X control is flat (0.6 ppm, materially zero), confirming the control holds — I read
this as the run being live to proceed on, not void.

## 2. Where it stops reconciling

`1030` §2 states the drift mechanism plainly: *"every decode's reported DT is the signal's
offset from that window start; so the drift shows up in DT one-for-one."* Taken literally, that
defines **drift = our own reported DT**, with no baseline subtraction. Applying `|drift| < 0.5`
to the fit above:

```
0.6183 - 0.1636h = +0.5  ->  h = 0.723 h
0.6183 - 0.1636h = -0.5  ->  h = 6.837 h
```

That is a **~6.1-hour band from h=0.72 to h=6.84** — not a window starting at session start, and
not anywhere near "the first ~2.3 hours" `1030` §3 item 4 states. I tried three other readings
of "drift" to see if one of them lands on 2.3h, in case the raw-DT reading isn't what was meant:

| candidate definition of "drift(h)" | solving `\|drift\|<0.5` |
|---|---|
| raw DT (literal §2 reading) | h in [0.72, 6.84] — 6.1h band, not from session start |
| slope-only, intercept treated as a fixed non-drift baseline (`drift(h) = -0.1636h`) | h < 3.06h |
| `ours_dt(h) - wsjtx_dt(h)` (control-subtracted) | h < 6.09h |
| slope-only at 8080's own rate (48.4 ppm) rather than this corpus's measured 45.4 ppm | h < 2.87h |

None of the four lands on 2.3h, and the first (the literal reading of your own §2 sentence)
doesn't even produce a window anchored at session start, which the "~first ~2.3 hours" phrasing
clearly implies it should. My regression matching yours exactly rules out a fitting-method
difference as the explanation — whatever produced "~2.3h" must be a different definition of
"drift" than any of the four above, or a different reference point for "elapsed_h" than the
session's earliest logged row (`23:54:00`, from OpenWSFZ's own `ALL.TXT`, 45s before WSJT-X's
first line — this small an offset can't explain a multi-hour discrepancy on its own).

## 3. What I need before running the 2.6h jt9 decode

The exact operative definition of "drift" for the `|drift| < 0.5s` restriction, precise enough
that I can compute it mechanically rather than eyeball a "roughly." Given the reading rule (§3
of `1030`) turns on whether the restricted parity lands in the 53.2%-91.6% range "at a position
consistent with 19.81 ref decodes/cycle," which cycles are *in* that restricted set matters
directly to which row fires — I don't want to lock in a self-invented definition and then be the
one grading the outcome against it, which is the exact independence problem `0910` §6 and my own
`1024` were both about.

I have **not** started the jt9 re-decode. Once the definition is confirmed I can proceed
directly — steps 2-5 and the self-checks in `1030` §3 don't depend on resolving this, only the
headline restriction (step 4) does, so nothing else is blocked by this question specifically. I
could start the jt9 run now in the background while this is clarified, since it's needed
regardless of how the cutoff is defined — flagging that option rather than assuming it.

## 4. What I have not done

- Not run jt9 against any part of the 489135a corpus.
- Not computed the restricted headline parity under any of the four candidate definitions above
  — they're shown only to demonstrate where the reconciliation attempt led, not proposed as a
  substitute for your answer.
- Not touched `_work/` or `src/`.

## 5. Boundary check

Per HK-015, QA → Architect (a method-precision question, same class as `1024`). No `src/`
touched. No push, no merge, no `pre_merge_check.py` (HK-006). NFR-021: the verification script
reads only `dt`/`ts` fields via the shared parser, never message text; nothing beyond aggregate
figures appears above.

## 6. Cross-references

- `2026-07-31-1030-architect-to-qa-task4-method-ruling-dt-derived-drift.md` §2 (the regression,
  reproduced exactly above), §3 (the restriction this document is stuck on).
- `qa/cycleframer-alignment-replay/verify_dt_drift_489135a.py` — the verification script itself.
- `2026-07-31-1024-qa-to-architect-489135a-recompute-method-unclear.md` — the prior escalation
  this ruling answered; same independence concern applies to this follow-up question.
- `2026-07-31-0008-qa-measurement-c-result-drift-collapse-confirmed-recoverable.md` — the
  `|predicted lag| < 0.5s` healthy-stratum definition this restriction is meant to match.
