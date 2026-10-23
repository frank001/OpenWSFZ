# Developer task: #259, a late transmission is time-aligned (the start of the clip is skipped, the tail is not cut)

**Date:** 2026-10-23
**Prepared by:** QA
**Audience:** Developer (to execute); Captain (sign-off required before merge, HK-010)
**Authorised by:** the Captain, 2026-10-23: "Option A" (Architect's window, ~17:30Z), and "yes to all" in QA's window for the issue text and these steps. Architect spec: `qa/rr-study/2026-10-23-1735-architect-to-qa-spec-late-start-time-alignment.md` (`arch/late-start-align`, `47659e13`). QA (k) review with amendments M1 to M4: `qa/rr-study/2026-10-23-1745-qa-k-review-late-start-time-alignment.md`. Issue: #259 (https://github.com/frank001/OpenWSFZ/issues/259). Evidence: `qa/rr-study/2026-10-23-1810-qa-o2-late-start-trace.md`.
**Status:** Proposed. Per HK-011 this is a `src/` change for a separate Developer session. **No push, no PR, no merge, no `pre_merge_check.py` on your own initiative** (QA runs it on a clean checkout before any push, the Captain's rule).
**Branch:** `fix/late-start-time-align`, cut from **`origin/main`** (`85fbaadc` or later; #258 has merged). Never commit to `main`. **Do not touch `native/`.**
**OpenSpec change:** `openspec/changes/late-start-time-alignment/` (proposal, design, tasks, MODIFIED deltas for `qso-answerer` and `qso-caller`) on QA's branch `qa/refset`: copy it onto your branch unchanged and say if you edit it.
**Version:** `User-facing: yes`, so a `VERSION` bump is required by G9b (next number from `origin/main`'s `VERSION`). **Set the README.md and REQUIREMENTS.md anchor sentences to the same version in the same commit and run `python tools/check_version_docs.py` (G9a)**: two branches have now failed exactly there.

---

## 0. Why (one paragraph)

When a QSO answer starts late in its 15 s slot, `TransmitAsync` keys at once and plays the 12.64 s clip from its first symbol, cutting the tail at the boundary (`Ft8TimeHelper.ClampSampleCountToWindowBoundary`, D-CALLER-021). The signal then sits at DT about +(t - 0.5) s, beyond WSJT-X's sync search of +-2.48 s once t is more than about 3 s; WSJT-X skips the start of the clip and allows no start after 11.25 s. Seen in #257's live check: first TX at 4.89 s, audio cut to 10.1 s. Option A: keep transmitting straight away, but align the clip as WSJT-X does and add its 11.25 s cut-off.

## 1. Precise scope (line numbers are on `origin/main` `85fbaadc`)

Only `src/OpenWSFZ.Daemon/Ft8TimeHelper.cs`, `QsoAnswererService.cs`, `QsoCallerService.cs`, and their tests.

1. **One helper in `Ft8TimeHelper`** (new function; the existing clamp `:46-59` stays): inputs `now`, the buffer length, the sample rate; output: samples to skip, samples to load, or "do not key". Let t = `now` minus the start of the current 15 s window. At 48 kHz the buffer is 606,720 samples (12.64 s).
   - **t <= 2.36 s:** skip 0, load all (2.36 = 15 - 12.64 = `LateBatch.LatestWholeStart`).
   - **2.36 s < t < 11.25 s:** skip `round((t - 0.5) x 48,000)`, load the rest. Playback ends about 13.14 s into the slot.
   - **t >= 11.25 s:** do not key (no `LoadAudio`, no `KeyDownAsync`); log at **Information** (today's Debug at `:1629-1633`).
2. **`TransmitAsync` in both services** (`QsoAnswererService.cs:1614`, the clamp call at `:1627`; `QsoCallerService.cs:1321`) calls the helper, then applies the existing clamp as a safety net AFTER the skip. **t comes from `_timeProvider.GetUtcNow()`, not `DateTimeOffset.UtcNow`** (QA amendment M3).
3. **One Information log line at every start with t > 2.36 s:** the offset, the samples skipped and the samples loaded, as milliseconds; **no message text**. A "not keyed at t >= 11.25 s" decision is also Information. Write the line at the moment the skip is computed (QA amendment M2: the audio really starts 0.05 to 0.3 s later because of PTT lead and device latency, so the clamp can still fire at the 2.36 s edge; it stays as the safety net).
4. **The three manual-engage fire sites retain at t >= 11.25 s** (return without clearing the target, so the next correct-phase batch re-evaluates it; about 18.75 s later; the 60 s stale expiry is unchanged): the answerer pending target (`:783-801`), the answerer jump-in (`:715-730`), the caller pending responder (`QsoCallerService.cs:777-784`). Compute t from `_timeProvider`. `ArmPendingTarget` and the 60 s expiry keep `DateTimeOffset.UtcNow` (`:466`, `:764`): do not mix the two in the new check. The existing test-only arming helpers (`:482-500`) exist for this.
5. **An aligned (shortened) transmission counts for retry, watchdog and ADIF exactly as a full one does.** A transmission not keyed at t >= 11.25 s keeps today's zero-remaining accounting: **state in the commit message what that is.**
6. **No ramp on the cut start.** The cut begins mid-symbol with no ramp, so the key goes down with the tone at full amplitude (key-click risk; QA amendment M4). This is an open question to the Architect, not part of this task: implement NO ramp and say so in the commit.
7. **Not changed:** `LateBatch` (the auto-reply hold at 2.36 s), the audio synthesiser, anything in `native/`. If you find the change must reach further, **stop and tell QA** (the Architect's prediction V5).

## 2. Tests (test-first; HK-025(k): each must be able to fail)

Inject `TimeProvider` as the existing D-CALLER-021 tests do; no unbounded sleeps; waits are `OpenWSFZ.TestSupport.Poll.*` with a timeout. The sample counts below are checked arithmetic.

| id | what it proves |
|---|---|
| T1 helper table | t = 0, 0.62, 2.36 s: skip 0, 606,720 loaded, identical to the input |
| T2 just past whole | t = 2.37 s: 89,760 skipped, 516,960 loaded; **the first loaded sample equals input[89,760]** (the start is cut, not the tail) |
| T3 the #257 L-2 case | t = 4.9 s: 211,200 skipped, 395,520 loaded; first loaded = input[211,200] |
| T4 last start | t = 11.24 s: 515,520 skipped, 91,200 loaded |
| T5 cut-off | t = 11.25 s and 14.9 s: nothing loaded, PTT never keyed, one Information log line |
| T6 manual engage past the cut-off | answerer pending target, answerer jump-in, caller pending responder, each consumed 12 s into a correct-phase window: not fired, retained, fired in the next correct-phase window |
| T7 late but before the cut-off | the same three at 5 s and 6 s (today's D-CALLER-021 A and C cases): fire immediately, aligned as T3 |
| T8 existing tests | the D-CALLER-021 G case (8 s in) and the caller's 9 s case rewritten to the new rule (8 s: 360,000 skipped, 246,720 loaded; 9 s: 408,000 skipped, 198,720 loaded); the H/I cases and the retry-budget tests J stay; all green |
| T9 regression | the full unfiltered suite |

**QA's mutation at review:** with today's tail-truncation restored in the helper, **T2, T3 and T4 must fail**; T1 passes either way. Show T2 to T4 failing on the old behaviour before your change (as you did for #257).

## 3. Not in scope

`LateBatch`'s hold; style M (a smaller skip) as code; pre-keying PTT earlier; the O1 log line; a ramp (above); any `native/` change; any station config edit.

## 4. What QA will read (the report)

- The **full unfiltered** `dotnet test OpenWSFZ.slnx`: the exact command line and the counts (passed / failed / skipped); a filtered run does not count (HK-022).
- `openspec validate --all --strict`; `check_version_docs.py` (G9a) and `check_version_bump.py` (G9b).
- The commit hash(es); the list of replaced and changed tests and why; T2 to T4 failing on the old behaviour; what the "not keyed" accounting is; anything surprising.
- `git diff --stat -- native` empty, and the file list limited to the scope in section 1.
- **Stop and tell QA before pushing anything.** QA reviews the commit (HK-039) with the mutation, runs `pre_merge_check.py` on a clean checkout of the exact tip before any push, then asks the Captain for the push go. The merge is the Captain's.

## 5. After the merge (QA, the Architect and the Captain, not you)

QA runs the offline decodability check on `sol` (styles O, A and M over start offsets, with every WAV cross-correlated to prove its placement). Live acceptance at the radio on the Captain's say-so: L-1 a late double-click more than 3 s into the slot (the new log line shows the offset and the skip; PTT ends about 13.1 to 13.4 s into the slot); L-2 the on-time transmissions of the same QSO load the full 12.64 s with no late-start line. Close #259 with the PR link; the next `decoding_improvement` sync carries it.
