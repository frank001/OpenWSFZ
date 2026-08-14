# QA -> Architect: reference-suppression investigation, M0-M4 -- results

**Author:** QA (autonomous orchestrator), 2026-08-06 22:58:49 UTC (per HK-017).
**Executes:** `2026-08-06-2144-architect-to-qa-spec-reference-suppression-m0-m4.md`, run in full per the Captain's instruction to run the entire chain unattended, M4 gated on M1's own outcome as specced.
**Script:** `qa/cycleframer-alignment-replay/2026-08-07-reference-suppression-m0-m4/orchestrate.py`.

---

## M0 -- evidence preservation

**Status: COMPLETE.** Preserved to `D:\Projects\claude\OpenWSFZ\artefacts\20260806_cross_decode_replay_2009`.

## M1 -- SNR signature of the suppressed decodes

**ROW 4.** INCONCLUSIVE. M4 MUST NOT RUN. Report delta, p, both medians, both n, escalate.

- delta = -2.000 dB, p = 0.00424967 (Mann-Whitney U = 65387.0)
- median(NEW) = -9.0 dB (n=460), median(SHARED) = -7.0 dB (n=323)

## M2 -- direct set test, OpenWSFZ-exclusive population

**ROW 1.** CONFIRMED -- 'OpenWSFZ finds decodes WSJT-X cannot' is false on this window; that population is a reference-suppression artifact. Arm R.D's reciprocity premise is undermined on this window; R.D remains unauthorised pending M3.

- R_owsfz = 0.9534, R_owsfz_all5 = 0.9498, R_wsjtx_self = 0.9645

## M3 -- does it generalise? low-density window replay

> **Provenance note.** The first attempt at this stage (this same report, prior version) reported `ROW 4 -- ANOMALY, instrument suspect, s_low=0.217`. That result is **VOID**, not a finding: `replay_lib.py`'s preflight check contained a 10.0s blocking sleep inside the playback loop, which desynchronised every cycle from the 3rd onward off the 15s UTC slot grid. See `2026-08-06-2249-architect-to-qa-m3-void-preflight-desync.md` for the full root-cause analysis. **`s_low=0.217` must not be cited anywhere.** The playback fix (no sleep; a mandatory <3.0s phase-lock assertion added instead, verified present in `replay_lib.py` below) is applied. The window-selection rule went through two more revisions after that — see the addendum below; the entries immediately following (candidate window, contrast=1.937) are the now-superseded second attempt, kept for the record rather than deleted.

**Status: NOT RUN** (as of the second attempt, below).
Reason: density leverage contrast < 3.0

- candidate window (target 10.0th pct, floor >= 100): 260804_054145 .. 260804_054630, mean_combined=20.50/cycle, wsjtx_total=130
- contrast against busy window = 1.937 (required >= 3.0)

> **Addendum — 2026-08-06 23:56 UTC (QA, `date -u`, per HK-017), corrected window-selection rule, third revision.**
> Per the Architect's handoff §5.1 (`2026-08-06-2346-architect-to-qa-handoff-index-and-work-queue.md`), the second rule above (10th-percentile among `wsjtx_total >= 100` survivors) also failed — it optimised density alone and ignored the `contrast >= 3.0` constraint entirely, which is exactly why it returned a window at contrast=1.937. Both prior rules are void; neither is to be reused.
>
> **Rule (third revision, replaces spec §5.2 and the 2249 note's §6.1):** among windows satisfying **both** `contrast >= 3.0` **and** `wsjtx_total >= 60`, select the one with the **maximum** `wsjtx_total` (objective on denominator stability, not fighting the constraint). Tie-break: earliest UTC.
>
> `qa/.../2026-08-07-reference-suppression-m0-m4/m3_select_window.py` has been updated to implement this rule (previously implemented the second/void revision) and re-run. Result, over all 4,716 candidate windows:
>
> | quantity | value |
> |---|---|
> | selected window | `260803_234000 .. 260803_234445` |
> | `wsjtx_total` | 105 |
> | `owsfz_total` | 157 |
> | `mean_combined` | 13.10/cycle |
> | `contrast` | 3.031 (>= 3.0 required — **passes**) |
> | surviving windows (both constraints) | 447 |
>
> QA-verified independently (re-derived from the archive, not just re-run): the selection is invariant to `MIN_WSJTX_TOTAL` at every floor from 40 to 100 (same window, same `wsjtx_total=105`), which is the handoff's own citable evidence that this is the corpus's real Pareto frontier rather than an artifact of where the floor sits. Full output: `m3_window_selection.json` (ts tokens and integer counts only — NFR-021 clean, no message text).
>
> **This does not mean M3 has been played back.** Window selection is now unblocked (`contrast=3.031 >= 3.0`, where it previously failed at 1.937), and the playback-timing defect is fixed (`replay_lib.py`, verified above) — but the actual replay (WSJT-X + OpenWSFZ both listening live, ~15 min) has not been run. Per the handoff §5/§7.3, whether it is still worth running given the corpus already has a working reference instrument is the Captain's call, not QA's or the Architect's.

## M4 -- load sweep (gated on M1 ROW 1)

**Status: SKIPPED.**
Reason: M1 fired ROW 4, gate requires ROW 1

---

*Per HK-015 this is QA (autonomous) -> Architect. Per HK-014/HK-010 written locally, no push, no merge implied. Per HK-011 nothing here touches `src/`. Per NFR-021 no message text or callsign appears in this document. Per HK-021 every gate above is the spec's own pre-registered code, evaluated mechanically by `gates.py`, not re-derived here.*
