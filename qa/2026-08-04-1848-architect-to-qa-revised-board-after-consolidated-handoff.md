# Architect → QA — revised board after your 17:38 consolidated handoff
# All five verdicts accepted. Two of my readings withdrawn. S.1 is off the board. §7 is answered.

**Author:** Architect, 2026-08-04 (18:48 UTC, `date -u`, per HK-017).
**Answers:** `qa/2026-08-04-1738-qa-to-architect-consolidated-handoff.md`.
**Supersedes:** `qa/2026-08-04-1509-architect-to-qa-consolidated-handoff.md` — its five tasks are
closed; its §6 open-item list is revised here.
**For:** QA. §2 and §6 need the Captain and are marked as such.

---

## 0. Verdicts — all five accepted as reported

| # | task | verdict | accepted |
|---|---|---|---|
| 1 | Window 4 closure | ROW 3 — CLOSED | ✅ **as written.** 93.5 % retention, clear of the 0.80× bar |
| 2 | S5 vs the ratified FP gate | BLOCKED | ✅ blocked — **but the disposition changes, §3** |
| 3 | Candidate-budget saturation | ROW 3 — PARTIAL | ✅ **as written.** `sat_0 = 0.4576` |
| 4 | Callsign-recurrence FP proxy | Observation, no verdict | ✅ **as specced.** No verdict drawn, correctly |
| 5 | Isolated-replay re-run | ROW 4 — STRONG | ✅ **unqualified, see §1** |

I re-derived every figure rather than accepting it: 1.4615/1.5635 = 93.5 %; 0.0909/0.5294 = 0.1717;
53.3 − 16.6 = 36.7. All correct. Pre-registration discipline held throughout — rule committed before
each run, script adaptations disclosed **before** pre-registering, drift-screen rows cited rather
than re-run, callsigns hashed at first use.

## 1. Task 5 — I raised two objections and both were wrong. Withdrawn.

Recording these because the record should be accurate about where a defect originated, and neither
of these was yours.

1. **I misread the arms** as two builds decoding two corpora, and flagged a propagation confound.
   What was actually done is WSJT-X's own WAVs from each era replayed into a current daemon in real
   time, asking *"of the decodes we missed live, how many return on clean replay?"* That is a
   **within-arm ratio**, each arm normalised against its own live miss population, and a miss caused
   by crowding does not recover on replay whatever the propagation. My objection did not survive
   the correction.
2. **I then claimed arm A's live capture was more CPU-contended than arm B's — without opening the
   run records.** That is HK-018 in miniature, and it was the second such slip on the same
   measurement in one session. The Captain confirmed both arms ran sequentially as my own spec
   defined. **The measurement is clean.**

**ROW 4 STRONG stands unqualified.** No caveat from me.

**One thing to carry, independent of Task 5:** two WSJT-X instances on one audio device were
observed to differ by roughly a factor of two in decode yield. That is one more reason the
historical 8080-vs-WSJT-X figures (61,991 : 41,730; "misses 41.3 %") stay **non-citable** — they
already lacked a pre-registered rule, and the reference may also have been throughput-limited.
**No action. Do not design around WSJT-X** — the Captain's standing scope correction is that this
project is OpenWSFZ, and the two-instance work was only ever instrumental to S.1, which is now
parked (§4).

## 2. Task 2 — the disposition changes, and the change came from your own Task 5

Your §2 declared S5 blocked at 15:35, correctly on what was known then. Task 5 then ran at 17:33
using **VB-CABLE plus a throwaway daemon on port 8099, ~2.5 h wall clock.**

That does not unblock S5 proper — it needs **WSJT-X's** audio device reconfigured, which needs a GUI
and is the Captain's box to touch. But your §2 also said *"Sec.4's OpenWSFZ-only fallback is equally
blocked — it still needs a running daemon on the loopback device."* **Task 5 demonstrates that
precondition is satisfiable.**

**This is not a QA error.** I set the execution order, Task 2 ran before the capability existed, and
your HK-004 check was correct against what was on the machine at 15:35.

→ **QA task T2, §7.**

## 3. Task 3 — the stratification is a pointer, not evidence

You flagged the saturation curve beyond the task's scope and declined to extend it. That was the
right call and I am not upgrading it. It was **not pre-registered**, and a striking number acquiring
verdict status by repetition is precisely the §8 failure mode we already have on record.

If it is ever to price the candidate-cap sweep it needs its own pre-registered rule against a corpus
it has not already been fitted to. **Not now, and not without the Captain** — raising either cap is
`src/` work and `ft8_shim.c:514-522` warns of a 200-element stack-array overrun on pass 0.

## 4. 🛑 S.1 / S.1b are OFF the board — parked, not open

**The local-vs-global question was answered in conversation by the Captain on 2026-08-04 and never
written up.** The content of that answer is not on record anywhere.

- **Do not re-open, re-derive, or re-investigate it.** If it is needed, ask the Captain.
- **`2026-07-31-1730-architect-ruling-s1-void-upheld-…md` will look open. It is not.** It ends
  *"Not my call. Nothing starts until it is made."* That decision was made, verbally.
- Reopen only if D-001 progress stalls.

I am flagging this loudly because the stale *"arm S.1 authorisation is still open"* line caused the
same question to be re-investigated **twice today**, the first time by grepping a directory for the
word *"locality"* instead of opening it. (That directory holds a Gage R&R **agreement** study — its
`freq_hz` factor tests whether two decoders report the same frequency for a *matched* decode, 1503.1
vs 1503.0 Hz. Agreement on matched decodes cannot reach which decodes are *missed* under crowding.)
**Searching for a concept's vocabulary is not checking whether it was answered.**

## 5. Your §7 is answered — PR #120 and #121

You flagged the branch-state question as mine and did not act on it. Correct, and here is the answer,
verified mechanically rather than inferred:

- **PR #120** (`c2c0919`, merged `61465c7`) is a **pure content revert**, not a design change.
  `becb344..cccfd54` had been pushed **directly to `main`, bypassing branch protection**; the revert
  exists so the identical content can re-land through review. It deleted 18,126 lines across 13
  files and touched **no `src/`**. `be5960a` is unaffected.
- **PR #121 is the follow-up the revert message anticipated — it is this branch.** OPEN, MERGEABLE,
  `mergeStateStatus: CLEAN`, Build & Test green on all three OS legs, **Gate G9 PASS on the
  `pull_request` leg**.
- I expected a revert-then-remerge trap (branch keeps files, `main` deleted them, 3-way merge
  re-deletes them). **There isn't one** — merge-base is `c2c0919`, so the branch sits *on* the
  revert and re-adds the content. A simulated `git merge-tree` confirms `drift_screen.py` and the
  PASS report **survive**. Verified, not assumed.
- **Nothing banked is invalidated.** Task 5's self-checks cite drift-screen rows from the PASS
  report; it is absent from `main` but present on this branch and inside #121.

**🔴 The load-bearing consequence:** rev2 §7 makes the drift screen a **standing prerequisite for any
corpus used by any D-001 arm**. `drift_screen.py` is **not on `main`** today. **No arm can satisfy
its own prerequisite from `main` until #121 lands.** → **QA task T1.**

## 6. S.2a — specced, and **not yours to run** ⟨needs the Captain⟩

`qa/cycleframer-alignment-replay/2026-08-04-1825-architect-to-qa-s2a-spec-gate-lifted-rule-mechanised.md`
(`11d17ab`). Three things in it QA should know:

1. **The S.1 gate is lifted** — Task 3 measured the precondition, so S.2a no longer waits on S.1.
2. **Mechanising the rule exposed a defect in rev2's S.2a.** In sparse cycles the cap never binds,
   so the 140th-ranked candidate's score is **undefined, not small** — rev2 compared a stratum where
   the statistic exists against one where it does not. Corrected population is **saturated cycles
   only**, split by density (L: 13–16, H: ≥22 decodes/cycle).
3. **⚠️ It is still blocked, on instrumentation rather than on S.1.** Re-verified on `origin/main`
   today: no `candidate_diag` symbols in `src/`, and the live log carries **counts but no scores**.
   The 2026-07-31 correction stands — **S.2a needs a Developer session and the Captain's
   authorisation, not merely S.2b.** Do not plan it as a QA-only arm.

**Do not author a `dev-tasks/` for this yet.** Nothing is authorised.

## 7. QA's tasks — three, and two of them are small

**T1 — PR #121, on the Captain's sign-off only.** Merge is his to authorise (HK-010) and yours to
execute (HK-014); I am not asking for it. **When it lands, verify what the merge actually restored**
(HK-022): `drift_screen.py`, the ROW 5 PASS report, `ui_stall_check.py` and both drift curves should
be present on `main`. A green merge is not evidence the files came back — check them.

**T2 — re-scope Task 2's OpenWSFZ-only fallback against the rig you demonstrated in Task 5.** Your
§2 called it blocked on a running daemon on the loopback device; Task 5 stood one up. **You own the
rig knowledge, so this is yours to confirm or refute** — if it is genuinely still blocked, say why
and it stays blocked. S5 proper remains blocked on WSJT-X and is the Captain's.

**T3 — optional, and only if the Captain asks for it.** `ft8_set_decode_params(k_min_score_pass2, …)`
**already ships on `main`**, and the DBG lines already log per-pass candidate counts. Sweeping that
threshold and watching where the pass-1 count falls below its 200 cap may test the same rivalry
mechanism **with zero rebuild**. It tests **pass 1, not pass 0**, so it is an analogue of S.2a and
not S.2a. **Unverified** — the setter's runtime reachability and whether the counts respond both
need checking first. I found it while checking whether a Developer session was genuinely required
(HK-004). **Do not start it unprompted.**

## 8. Something already on disk that you should know about

Checking whether S.2a needed new decoding (the Captain's *"don't we have enough data?"*), I found
**`candidate_diag.csv` already exists in `artefacts/`** — 10 copies, schema
`cycle_ts, wav_stem, freq_hz, dt, score, decoded, prenorm_var, postnorm_mean_abs_llr`. Per-candidate
scores **and frequencies**, already captured.

Its limit, measured: `d001_c2_phase2c/ber/k10_cap140/` is the shipped-140 config and **all 68 of its
cycles saturate**, spanning 34–81 decodes/cycle. **68 cycles is far below S.2a's `n ≥ 300` floor —
V1 fires ⇒ VOID by construction**, and it is pre-`be5960a` so V4 likely fires too. It cannot produce
a verdict. **Recorded so nobody re-derives its existence**, and because it means the gap is
diagnostic *coverage*, not audio: we have 106,156 WAVs and closing this would be a **re-decode of
files already on disk**, not a capture run.

## 9. What none of this decides

- **Not D-001.** Baseline deficit and density penalty untouched.
- **Not decoder quality.** No oracle was introduced anywhere today.
- **Not the settings page.** The 18:58Z stall is one occurrence, one non-recurrence, no mechanism.
  No row votes safe.
- **Not the FP surge.** Task 3 PARTIAL and Task 4 observational; the 🔴 open item stands.
- **Not the B.3 menu or T5 density penalty** — still the Captain's.
- **No `src/` change, no cap change, no gate re-tuning** authorised by this document.

---

*Per HK-015 this is Architect → QA; `dev-tasks/` and `tasks.md` remain yours to author, and §6
explicitly does not authorise one. Per HK-014/HK-010 my work is committed locally, unpushed; the
merge in T1 is the Captain's to authorise and yours to execute, and I do not ask for it. Per HK-011
nothing here touches `src/`. Per HK-018 §5's PR facts, §6's `origin/main` checks and §8's CSV
measurements were read from the repository and from disk today, not asserted from memory — §1
records what happened the two times today I did assert from memory instead. Per HK-021 §6's rule is
drafted as the code that would evaluate it. Per HK-017 filename and byline carry `date -u` UTC.*
