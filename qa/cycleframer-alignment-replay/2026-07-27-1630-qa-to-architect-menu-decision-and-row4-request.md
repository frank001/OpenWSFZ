# D-001: QA -> Architect notification — the Captain has ruled on the B.3 menu; row-4 scoping requested

**Author:** QA, 2026-07-27 (16:30). **For:** the Architect, per HK-015.
**Answers:** `2026-07-26-2359-architect-b3-costed-menu.md` §4 — the menu put to the Captain.
**This is a notification carrying a decision and a request, not an escalation.**

---

## 1. The Captain's decision

Given the menu as costed (§3, two-corpus-de-risked per `2026-07-27-0130-architect-b1b-acceptance-
and-menu-standing.md`), the Captain has ruled: **lean rows 4/5, not row 1.** Per your own §4.2, the
next step is not implementation on either row — it is the **row-4 scoping decomposition** you
flagged as QA-runnable and "deliberately not designed here, because designing it presumes the
answer to the menu" (§3.4). The menu no longer needs presuming; the Captain has answered it.

This is not yet a commitment to row 4 over row 5 — per your own §4.2, the scoping study's output is
the cost estimate that comparison needs. It is a commitment to *not* taking row 1, and to spending
the next increment of work finding out what row 4 actually costs before choosing between 4 and 5.

## 2. Request

Please design the row-4 scoping decomposition per §3.4's sketch: isolating which front-end stage —
sync detection, candidate scoring, symbol demodulation — is responsible for the 437-message
measured floor, "QA-instrumented, cheap in the same way B.1 was (e.g., comparing candidate
populations and sync-stage behaviour between jt9 and ft8_lib on the same cycles)." QA will run
whatever you spec, same discipline as B.1/B.2/B.1b: reading rules fixed before numbers exist.

Two things worth your attention while designing it, both raised in your own menu memo and neither
resolved yet:

- **§6, second bullet**: row 4's 437 is a floor with an asterisk — it measures WSJT-X's front end's
  prize, not our cost of reaching it. If the scoping design can produce even a rough cost signal
  (not just a stage attribution), that is worth more to the Captain's eventual 4-vs-5 choice than
  attribution alone.
- **Corpus**: B.1b's replication covered two corpora for the *existence and shape* of the 437 floor.
  Whether the scoping decomposition needs to run on both, or can run on one with the other held in
  reserve for a later validation pass, is your call to make explicit in the design — it wasn't
  settled by B.1b's own scope.

## 3. What this does not settle

- **Row 5 (GPLv3 adoption) is untouched** — no licensing position taken by the Captain's ruling here;
  it remains the benchmark row per §3.5 until the scoping study gives a real row-4 cost to compare
  it against.
- **Rows 2 and 3 stay sequenced behind row 4**, per §3.2/§3.3 — unchanged.
- **The other two pending items are untouched by this notification**: branch disposition remains
  open; the `libft8.dll` size question is answered separately
  (`2026-07-27-1600-qa-to-architect-dll-size-notification.md`) and awaits your ruling on whether it
  still blocks merge.
- **No native or `src/` change, no push, no merge** (HK-011/HK-014 untouched). **No
  `pre_merge_check.py`** (HK-006, Captain's trigger, not run).

## 4. Cross-references

- `2026-07-26-2359-architect-b3-costed-menu.md` §3.4, §4.2, §5, §6 — the menu and its scoping
  sketch, executed by this request.
- `2026-07-27-0130-architect-b1b-acceptance-and-menu-standing.md` — the two-corpus de-risking this
  decision rests on.
- `2026-07-27-1600-qa-to-architect-dll-size-notification.md` — the sibling notification from this
  session.

---

*Per HK-015, the scoping design is yours to author; QA runs it once specified. Per HK-014, nothing
here is pushed or merged. Per HK-011, nothing here touches `src/` or native code.*
