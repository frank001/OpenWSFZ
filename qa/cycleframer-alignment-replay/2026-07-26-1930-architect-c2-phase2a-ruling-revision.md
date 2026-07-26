# D-001: Architect ruling revision — Phase 2b's *test* is cheap; item 3 reopens as measuring

**Author:** Architect, 2026-07-26 (19:30). **For:** the Captain and QA.
**Revises:** `2026-07-26-1830-architect-c2-phase2a-ruling.md` §1, §3, §5, §6 (sequencing only) and
§8. That note's §2 corrections, §4 localisation, §7 what-this-does-not-overturn and §9 caveats all
stand unchanged.
**Trigger:** the Captain's challenge to the 18:30 decline — "17% sure seems like a big difference,
not like seen before."

The challenge was right, and it exposed a specific error in my own reasoning rather than a
difference of risk appetite. I am correcting it here rather than quietly, because the 18:30 note is
committed and QA would otherwise scope from it.

---

## 1. The error in the 18:30 ruling

I priced Phase 2b as the full ship — unflagged hot-path change, pass-0 loop restructure, D-009 OSD
recalibration, held-out weight sweep, full R&R S1–S8 rerun — and declined it against an unknown hit
rate on 135 messages.

**Every one of those is a cost of *shipping* shrinkage. None is a cost of *measuring* whether it
works.** I took the dev-task's §3.6 ("no partial or opt-in shipping — there is no flag to hide this
change behind") and let it bind the experiment as well as the ship decision. It does not. A
flag-gated experimental build that never ships incurs no recalibration, no R&R rerun, and no ship
decision, because there is nothing shipped to regress.

The pattern already exists in this codebase. C.2 Phase 1 added `ft8_set_candidate_diag_capture` —
thread-local, opt-in, default-disabled, and **verified a behavioural no-op when disabled** against a
byte-identical pristine-`main` build. A `ft8_set_llr_shrinkage(weight)` toggle defaulting to zero is
the same shape, with a stronger no-op guarantee: weight 0 is today's arithmetic exactly, by
construction, not merely by inspection.

So the step I skipped is the one between "decline" and "commit": **measure the 135's actual hit rate
for one session.** My §3 concern — that the ceiling is unquantified and might convert at zero — was
the correct concern. Declining on that concern instead of resolving it, when resolving it costs one
Developer session, was the wrong call.

## 2. What does *not* change

Stated first, so this revision is not read as a general retreat under push-back.

- **§2.1's arithmetic correction stands.** The yield ceiling is **17.0%** (135/793), not the
  notification's 2.4%.
- **§2.2's overclaim correction stands.** "Reversal of Phase 1's direction" remains stronger than
  the data supports; the two populations barely overlap in sync score. Phase 1 is unimpeached.
- **§3's wrong-sign concern stands, and is not withdrawn.** On 567 candidates the metric shrinkage
  most directly targets runs the other way. That is now a *reason to instrument the trial carefully*
  (§5) rather than a reason to skip it — but if the trial helps the 135 while hurting the 567, that
  is a finding, not a detail, and §5's decision rule is written so it cannot be averaged away.
- **§4's localisation stands** — for a −8 dB signal we have correctly located, with co-channel
  masking refuted, we produce LLRs of normal magnitude that do not decode.
- **§6's BER measurement stands** and is not displaced. See §6 below for how the two now sequence.
- **§7 stands entirely.** C.2 Phase 1, C.3, C.4 and Phase 2a's own verdicts are unaffected;
  `K_MIN_SCORE` stays at 10; the §7 false-decode question stays held.

## 3. The framing correction the challenge rests on

Recorded because it is the thing most likely to be misread again, by any of us.

**135 is a population size, not a measured yield.** It is the count of missed messages that had a
failed candidate carrying the LLR signature — the maximum conceivable recovery if a fix worked
perfectly on every one of them. C.1's +12 and C.4's +2 were *measured decodes*. The measured yield
of LLR work to date is **zero**; no decode has ever been recovered by it.

C.4 is the precedent that makes this more than pedantry. At K=4/cap2000, **618 of 648 messages
(95%) regained a candidate** — a far larger population figure than 17% — and it converted to **+2
matched decodes**. Population recovery and decode recovery came apart by two orders of magnitude,
one experiment ago, in this same thread.

That is not an argument against pursuing the 135. It is precisely the argument for *measuring* it
rather than either committing to a multi-session ship or declining on reasoning. Both of those
treat the conversion rate as known. It is not known, and it is one session away from being known.

## 4. Ruling — item 3 reopens as **Open — measuring**

Not "open," which is what it was before Phase 2a and invites indefinite scoping. Not "closed," which
is what I wrongly made it at 18:30. **Open with exactly one bounded experiment attached and a
decision rule fixed in advance.**

Phase 2b's *ship* remains declined-pending-evidence. Nothing about D-009 recalibration, the R&R
rerun, the held-out sweep or the hot-path change is authorised by this revision, and none of it
should be scoped until the trial reports.

## 5. The trial — recommendation for QA to scope (HK-015: a recommendation, not a task)

**Shape:** one Developer session (HK-011), diagnostic-only, nothing shipped.

1. **Add a thread-local, default-off shrinkage toggle.** `ft8_set_llr_shrinkage(double weight)`,
   plumbed from shim TLS into `ftx_normalize_logl` (`native/ft8_lib_build/patched/ft8/decode.c:380-399`).
   Note this is patched ft8_lib, not the shim, so the plumbing is more than the one-file change
   C.2 Phase 1's diagnostic was — still well inside one session, but do not scope it as trivial.
2. **Weight 0.0 must reproduce the baseline exactly.** Not "closely" — identical matched-decode
   count against a pristine build on the same corpus. This is the trial's own self-check and its
   no-op proof, in the same spirit as C.2 Phase 1's byte-identical verification. If 0.0 does not
   reproduce, stop and fix that before reading any other row.
3. **Sweep the weight** — 0.0 / 0.25 / 0.5 / 0.75 / 1.0 is a reasonable first grid; the shape of the
   curve matters as much as any single point. A yield that appears only at one weight and vanishes
   either side is a tuning artefact, not an effect.
4. **The metric is matched decodes, not total decodes.** This is the single most important line in
   this note. C.4's entire error was reading a recovery column as a result. Report, per weight, the
   same table shape my 17:00 §2 used: total decodes, **matched**, unique-to-us, Δ matched, unique
   share. A weight that raises total decodes without raising matched decodes is manufacturing false
   decodes and must be reported as such.
5. **Report the 135 and the 567 populations separately**, plus the matched-hit control as a third
   arm. §3 of the 18:30 note predicts these may move in opposite directions. If they do, that is the
   mechanism distinguishing them that we currently lack — it is a result, and it must not be
   averaged into a single headline number.
6. **Also report elapsed time against the 15 s budget**, same as C.1 and C.4, since the toggle adds
   work to the hot path even at weight 0.

**Decision rule, fixed now so it is not negotiated after the numbers are visible.** Read against
Δ **matched** decodes on the discovery corpus:

| Δ matched | reading | next |
|---:|---|---|
| **≥ 50** (≥6% of the 793 gap) | materially larger than anything found in this thread | Proceed. Held-out corpus confirmation, then the full ship-validation set (D-009 recal + R&R S1–S8). The ship costs are clearly worth paying at this yield. |
| **10 – 49** | comparable to C.1's +12 — real but modest | Captain's call, with a real number instead of a ceiling. I would want the held-out confirmation before framing it. |
| **< 10** | C.4's shape | Item 3 closes on evidence. My 18:30 decline was right, for a reason we measured rather than argued. |
| **negative at any weight** | shrinkage costs decodes | Closes immediately, and §3's wrong-sign concern is confirmed rather than merely raised. |

**The discovery-corpus number is an upper bound, not the yield.** `20260725_live_run_1806` is the
corpus this effect was discovered and characterised on, through C.1, C.2, C.3, C.4 and Phase 2a. A
positive result there means "worth confirming on held-out data," never "worth shipping." A
*negative* result there is decisive immediately, because it is the most favourable ground this fix
will ever be tested on.

## 6. Sequencing with the BER measurement

The 18:30 §6 BER measurement is not displaced and should run in the **same Developer session**. Both
are opt-in diagnostics on the same shim, validated by the same offline harness run, with no overlap
in risk profile.

They answer different questions and neither substitutes for the other:

- **The shrinkage trial answers *whether*.** It is what the Captain's challenge actually asks for,
  and it is the one that can change the decomposition table.
- **The BER measurement answers *why*.** It explains whichever way the trial lands. If the trial
  yields nothing, BER tells us whether that is because our LLRs are wrong rather than small (which
  would close every LLR-scaling avenue at once, permanently, rather than just this one). If the
  trial yields something, BER tells us what the residue after it consists of.

If session scope forces a split, the shrinkage trial goes first — it is the one with a decision rule
attached.

## 7. Revised decomposition table

Replaces §8 of the 18:30 note. Only item 3 changes.

| # | mechanism | status | measured decode yield |
|---|---|---|---|
| 1 | Candidate-array truncation (`K_MAX_CANDIDATES`) | **Closed** — C.1 | +12 decodes, +1.6% of gap. Real, small, plateaus. |
| 2 | Sync score-floor rejection (`K_MIN_SCORE`) | **Closed** — C.3/C.4 | +2 decodes while false decodes rise 61 → 376. |
| 3 | LDPC survival / LLR quality | **Open — measuring** | Ceiling 135 (17.0% of gap); conversion rate **unknown and being measured**. Trial per §5, decision rule fixed. Ship remains declined pending it. |
| 4 | Structural decoder difference vs WSJT-X | **Open — active** | Unmeasured. BER measurement per §6; §6.3's product decision stays parked. |

## 8. Honest caveats

- **I changed a ruling under push-back, which deserves scrutiny.** The test is whether the reasoning
  changed or only the conclusion. What changed is §1's specific conflation of ship cost with test
  cost — a factual error about what the experiment requires, which I can point at. My substantive
  concerns (§2) are carried forward intact rather than dropped, and the ship decision is *not*
  granted by this revision. If the trial returns <10, my 18:30 conclusion was right and this
  revision will have cost one session to establish it properly. I regard that as the correct price.
- **Weight 0.0 reproducing baseline is an assumption until demonstrated.** Floating-point
  arithmetic reordered by the toggle's presence could perturb results at the margin even at zero
  weight. §5.2 exists to catch that; if it fires, it is a real finding about the trial's own
  validity, not a nuisance to work around.
- **The §5 decision-rule bands are calibrated against this thread's own history** (C.1's +12, C.4's
  +2) and against the 793 gap on one corpus. They are a reasonable prior, not a derived optimum, and
  the Captain may set them differently — but they should be set *before* the numbers land, whoever
  sets them.
- **One 21-minute session, one device, one band.** Unchanged from every prior note in this thread.
- **The trial can succeed and still not ship.** D-009's OSD calibration and the R&R gate suite are
  genuine constraints on shipping, not obstacles I invented to decline with. A positive trial makes
  paying them worthwhile; it does not make them go away.

## 9. Cross-references

- `2026-07-26-1830-architect-c2-phase2a-ruling.md` — revised here; §2, §4, §7, §9 stand.
- `2026-07-26-1650-qa-to-architect-c2-phase2a-notification.md` — the fork that started this.
- `2026-07-26-1700-architect-c4-ruling-and-decomposition-revision.md` §2 — the matched-decode table
  shape §5.4 requires the trial to reuse, and the source of §3's 618→+2 precedent.
- `2026-07-26-c2-llr-normalization-findings.md` §2, §6 — Phase 1's opt-in diagnostic precedent that
  §1 relies on, and the shrinkage design the trial implements behind a toggle.
- `dev-tasks/2026-07-26-d001-c2-phase2-llr-shrinkage.md` §3 — Phase 2b's ship requirements, which
  remain correct *as ship requirements* and do not bind the trial.
- `native/ft8_lib_build/patched/ft8/decode.c:380-399` (`ftx_normalize_logl`) — where §5.1's toggle
  is plumbed to.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c` (`ft8_set_candidate_diag_capture`) — the default-off
  thread-local pattern §5.1 follows.

---

*Per HK-014 nothing is pushed or merged. Per HK-015 §5 and §6 are recommendations for QA to scope
into a dev-task; `dev-tasks/` remains QA's to author. The trial authorises no ship decision — that
returns to the Captain with a measured number under §5's decision rule.*
