# HANDOFF — D-001 Option B: Co-Channel Attribution Pass

**Date:** 2026-07-07
**From:** Architect
**To:** QA (execution owner)
**Type:** Offline log-analysis task — no product code, no OpenSpec change, no new live session
**Governing spec:** `dev-tasks/2026-07-07-d001-b-cochannel-attribution-spec.md` (method, rationale, thresholds)
**Defect:** D-001 (open, issue #3)

---

## Status & authority

- **Approved to execute.** Architect has approved the method; Captain has **locked the §3 decision
  thresholds: F ≥ 0.60 → recommend H7 scoping; F ≤ 0.30 → do not scope; 0.30 < F < 0.60 →
  scope-with-price-tag decision.** Do not re-open the thresholds during execution.
- This is the **required gate before any H7 (MMSE) scoping.** Option A stays closed until this
  pass reports.
- Read the governing spec first — this handoff is the work order, the spec is the reference. Where
  they appear to differ, the spec wins; flag the discrepancy back to Architect.

---

## Definition of done

A committed results report that states **which §3 branch the evidence selects**, backed by F (with
its window-sensitivity band), the per-class/per-SNR-band counts, the recoverable-recall upper
bound, and the error-direction caveat — for at least the 07-07 session, corroborated by 07-06 /
06-22 where their logs survive.

---

## Execution checklist

### Gate 0 — Data availability (do this first; it decides whether B can run at all)
- [ ] Confirm the **OpenWSFZ + WSJT-X `ALL.TXT` pair** exists on disk for the 07-07 session
      (`artefacts/20260706_live_run_2308/`). These are small text files; the 1.4 GB WAVs are **not
      needed**.
- [ ] Check the same for the 07-06 and 06-22 sessions (corroboration, not prerequisites).
- [ ] Confirm the endurance recall/matcher script for at least the 07-07 session is present
      (committed alongside its raw logs, local/git-ignored).
- [ ] **If no ALL.TXT pair survives for any session → STOP.** Do not proceed. Escalate to Captain
      per spec §7 (choose: accept Option C, or authorise a minimal instrumented live session whose
      only added requirement is retaining ALL.TXT pairs). Record the stop and reason.

### Step 1 — Miss set
- [ ] Reuse the endurance matcher to produce the **WSJT-X-only** set (WSJT-X decoded, OpenWSFZ did not), aligned by slot + freq + text.
- [ ] Exclude hashed (`<...>`) messages.
- [ ] Stratify by WSJT-X SNR; run primary analysis on `< −15 dB` and `−15…−10 dB` bands (report each separately + pooled).

### Step 2 — Neighbourhood & classification (spec §4.2–4.3)
- [ ] For each miss, gather same-UTC-slot decodes from the **union of both apps'** ALL.TXT; compute Δf to each.
- [ ] Classify each miss: **Tight co-channel** (Δf ≤ 15 Hz) / **Partial** (15 < Δf ≤ 50 Hz) / **Isolated** (no neighbour ≤ 50 Hz).
- [ ] Compute **F = Tight / total** and **F′ = (Tight + Partial) / total**.

### Step 3 — Rigour controls (spec §5 — none optional)
- [ ] Window-sensitivity sweep of the tight cutoff over {10, 12, 15, 20, 25} Hz; report F as a band. If the §3 verdict flips inside the sweep → result is "inconclusive → mixed-case path."
- [ ] State the error direction explicitly (undecoded interferers bias F **down**; so F ≥ 0.60 is conservative for A, F ≤ 0.30 must survive that bias).
- [ ] Classify only on neighbour presence + Δf, never on the miss's own SNR.
- [ ] Capture-effect sub-check: within Tight, tabulate SNR delta of miss vs nearest strong neighbour.

### Step 4 — Translate & decide (spec §4.4, §3)
- [ ] Compute the recoverable-recall **upper bound** in recall pp; pair with the 3–6 month estimate as cost-per-pp.
- [ ] Map the result to exactly one §3 branch.

### Step 5 — Report & privacy
- [ ] Write `qa/rr-study/results/<date>-<sha>-d001-cochannel-attribution/report.md` (QA authors Sections 1/5 per HK-001).
- [ ] Commit the classification script + its ALL.TXT-derived inputs **only after** the NFR-021 privacy check: scrub/aggregate real callsigns; commit only what the privacy policy permits (Q-prefix synthetic, or PD2FZ/public-figure exceptions).
- [ ] Deliver the one-paragraph recommendation (§8.3) to Architect + Captain, error-direction caveat included in the same paragraph.

---

## Escalation & boundaries

- **Runnable-but-thin data** (only 07-07 survives): proceed on that single largest sample; label 07-06/06-22 corroboration as "logs unavailable." Not a stop condition.
- **Verdict flips inside the window sweep:** report as inconclusive → mixed-case path; do **not** pick a side to force a clean answer.
- **Scope creep:** if the analysis tempts a re-decode, a new session, or a decoder change — stop; that is outside B and needs separate approval.
- **If B → A (F ≥ 0.60):** do **not** start H7 work. Note in the report that the harness precondition (spec §6: restore s7 to K=10, co_channel as primary oracle) is the next gate, owned separately.

---

## What this handoff explicitly does not authorise

New live sessions · WAV re-decode · any change to product/decoder/shim code · OpenSpec proposals ·
touching the s7 harness · re-opening the three endurance conclusions or the §3 thresholds.
