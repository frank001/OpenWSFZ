# D-001: B.3 — the §6.3 costed menu. For the Captain to decide, with measured prizes per row

**Author:** Architect, 2026-07-26 (23:59). **For:** the Captain.
**Answers:** `2026-07-26-2350-qa-to-architect-b1-b2-notification.md` — both measurements accepted
in full (§1 below). **Executes:** `2026-07-26-2330-architect-capability-pricing-plan.md` §5, which
recorded this memo's skeleton in advance so B.1/B.2 would collect the right numbers. They did.
**This unparks** `2026-07-26-0015-d001-consolidation-and-clean-slate.md` §6.3 — the product
question that has been deliberately not put to the Captain through eleven rulings. It is put now.

---

## 1. Acceptance of B.1 and B.2 (brief; the findings docs are the record)

- **B.1 accepted.** Self-checked against the canonical script before anything new was trusted.
  The disclosed anchor drift is resolved in the canonical direction: **1300 / 789 / 1239**
  (our offline decodes / miss population / matched) replaces my earlier "1288 / 793 / 1235"
  citation everywhere from here forward. Order-1% — no prior reading changes.
- **B.2 accepted, including the clipping self-correction disclosed at full weight.** Median 41%
  of samples clipped inside the BER 5–20% transition region was not cosmetic; the global-rescale
  fix is the right one (preserves the SNR ratio exactly); only the clean run (E = 5.69) is used
  here. This is the third discipline save of its kind in this thread and it is recorded as such.
- **E = 5.69 landed inside my pre-registered prior (5–15, 22:30 §7).** Per that section's own
  terms: the Captain should know I predicted it, and should weight it accordingly — a confirmed
  prior is still just one measurement, made conservative in the safe direction (E is a lower
  bound).
- **The Δf=0 matching artefact** (both co-located planted messages resolving to one candidate) is
  accepted as a bounded limitation of the per-Δf slice, not of E — both arms land in the same
  band (5.69 vs 4.45).
- **One unplanned finding accepted and worth a sentence:** A0 (2039) ≥ live GUI (2028). Offline
  context-free batch replay needs no upward correction on this corpus. The menu's denominator is
  therefore clean: 2028, and A0 agrees with it.

## 2. The picture, in one paragraph

The 789-message gap is now priced by capability, by two independent instruments. **Almost all of
it (98%) is recoverable by WSJT-X's own decoder offline, with no session context and no AP** —
so the ceiling for engineering along this axis is essentially the whole gap, not a fraction.
**More than half of it (55.4%, 437 messages) is recovered by WSJT-X at minimum effort** — depth
1, no subtraction passes worth the name, no AP — while out-decoding our *full-effort* decoder by
30% on identical audio. That is a front-end/sync-quality signal, not a correction-power signal.
And on the correction side, B.2 bounds our own BP/OSD residue on the located population at
**E = 5.69 of THE 135** — real, small, single-digit. The gap, in short: mostly signals our front
end never turns into viable candidates; a medium slice that WSJT-X's extra effort/subtraction
passes reach; a thin slice our own correction stage drops. The menu below prices each.

## 3. The menu

Anchors for every row: live WSJT-X GUI = **2028**; our decoder offline = **1300** (64.1% parity;
NFR-018 target ≥ 80%, i.e. ≥ 1622 on this corpus); miss population = **789**.

| row | option | measured prize (this corpus) | parity ceiling if fully realised | engineering cost | principal risk |
|---|---|---|---|---|---|
| **1** | **Accept the gap** — re-baseline NFR-018 | 0 | 64.1% (re-baselined as the target) | zero | product accepts ~36% fewer decodes than WSJT-X, permanently |
| **2** | **Re-attempt PCM-domain SIC** | an **unknown share** of the 346-message depth-axis bundle (T(3)−T(1)); 73% of that bundle sits in the depth 1→2 step | ≤ 81.2%, and only under two assumptions that are both false as stated (see 3.2) | multiple HK-011 Developer sessions, native change, `.so` rebuild, June's constraints attached | June failed once (stack overflow + undiagnosed AV, −0.1 pp); prize is contingent on front-end quality (3.2) |
| **3** | **Decode-effort constants** (BP iterations, OSD depth/gates) | **E = 5.69 of THE 135** (~0.3 pp parity) | 64.4% | small — sweep harness exists; possibly one native constant | none to speak of, but the prize cannot move the NFR-018 needle; per 22:30 §6.1: chase only if the cause is a single constant or gate |
| **4** | **Front-end/sync work** | **437 messages measured floor** (what a WSJT-X-grade front end recovers at *minimum* effort) | **83.5% — the only engineering row whose measured floor clears NFR-018 by itself** | **unknown until decomposed** — sync detection, candidate scoring, symbol demod are still folded together inside "depth-1 jt9" | scope is unbounded until the decomposition exists; this is the row where a wrong-sized commitment gets made |
| **5** | **Adopt WSJT-X's decoder core** | ~the whole 789 (98% miss coverage; 2039 total) | ~100.5% | Fortran integration + permanent maintenance coupling | **GPLv3.** The licensing consequence for the product is the decision, and it is the Captain's alone |

### 3.1 Row 1 — accept

The one honest zero-cost option, now with a measured ceiling rather than a suspicion: the gap is
a capability gap in the decoder, confirmed from both sides (our instrumentation, and WSJT-X's own
CLI). If accepted, NFR-018 is re-baselined against a measured reference — I would propose "≥ X%
of jt9 `-d 3` offline on the same audio" as the new form, because A0 is reproducible by anyone
and the live GUI is not. The re-baseline number itself is the Captain's.

### 3.2 Row 2 — SIC, and why it is sequenced behind row 4 if engineering proceeds

Two corrections to how this row's prize must be read, both from B.1's own caveats:

1. **The 346 is a bundle, not SIC.** jt9's depth axis bundles passes, OSD depth, and subtraction.
   No measurement exists that isolates subtraction's share, and B.1 was designed knowing jt9
   offers no clean toggle.
2. **The 346 was measured on WSJT-X's front end.** Subtraction only helps signals buried under
   ones you have already decoded — its yield rides on the front end's ability to lock the strong
   signal cleanly and to see the weak one at all once the strong one is gone. Our front end,
   measured 30% behind at minimum effort, would realise *less* than the equivalent bundle. Doing
   SIC first buys the smaller version of its own prize.

June's engineering constraints carry unchanged from the plan §5: heap allocation from day one,
the `0xC0000005` budgeted as a real root-cause item, and per-candidate subtraction fidelity
measured with this week's raw-LLR/BER instrument rather than aggregate R&R deltas.

### 3.3 Row 3 — constants

E = 5.69 is a real number and a small one. The 22:30 reading rule anticipated exactly this band:
chase it if a single constant or gate explains it; otherwise fold it into the framing and
proceed. My recommendation: **fold it into whichever row the Captain picks** — if row 4 work ever
touches the decode path, the 5.69 gets checked for free; it does not justify a session of its
own. It stays on the menu because the rule says the Captain decides with the number, not me.

### 3.4 Row 4 — front-end/sync: the largest measured prize, and the least scoped

What is measured: 437 of our 789 misses are recoverable with no extra decode effort at all — the
front end alone. What is *not* measured: which front-end stage. Sync detection, candidate
scoring, and symbol demodulation are still one lump. **If the Captain leans this way, the next
step is a scoping decomposition, not implementation** — QA-side, jt9-instrumented, cheap in the
same way B.1 was (e.g., comparing candidate populations and sync-stage behaviour between jt9 and
ft8_lib on the same cycles). I will design it on request; it is deliberately not designed here,
because designing it presumes the answer to the menu.

### 3.5 Row 5 — the benchmark row

Priced so it cannot be pretended away: ~the whole gap, for the cost of GPLv3. Every estimate row
4 eventually produces must be read against this row — if reimplementing WSJT-X's front end
approaches the cost of adopting it, the licensing question stops being avoidable and starts
being the cheap option. I take no position on the licensing; that is not an architecture call.

## 4. My recommendation, stated once

Per this thread's practice I state it once, plainly, and then it is the Captain's:

1. **The decision that matters is row 1 vs. rows 4/5.** Rows 2 and 3 cannot reach NFR-018's 80%
   even on their most generous reading; they are refinements, not answers.
2. **If NFR-018's 80% stands, commission the row-4 scoping decomposition** (§3.4) before
   committing to anything — including before choosing between rows 4 and 5, since its output is
   the cost estimate that comparison needs.
3. **Gather the second corpus first.** The plan §3.5's own rule fires: every number in this memo
   is one corpus, one band, one device, 21 minutes. A second corpus (different band/time) is an
   evening of QA time and is insurance on whichever large commitment follows. It should precede
   the commitment, not the menu — the menu is this document.
4. **Sequence row 2 after row 4, if at all** (§3.2). **Fold row 3 into whatever runs** (§3.3).

## 5. What this memo does not authorise or settle

- **No native or `src/` change** (HK-011 untouched). The row-4 scoping study, if commissioned, is
  QA-runnable; anything beyond it comes back through the full gate.
- **No push, no merge** (HK-014 — committed locally, stops there).
- **No `pre_merge_check.py`** — Captain's trigger per HK-006.
- **The branch's outstanding housekeeping is untouched and still blocking on the Captain**: the
  `libft8.dll` size question (20:30 §9) and this branch's overall disposition. My position is
  unchanged: an unexplained binary delta is a merge blocker regardless of benignity.
- **NFR-021**: this memo carries aggregates only; all raw material stays under git-ignored
  `artefacts/`.

## 6. Honest caveats

- **One corpus.** Said in §4.3 and said again here because it bounds everything: every prize in
  the menu could shift on a different band at a different hour. The *shape* (front end ≫
  correction residue) is the robust part; the exact counts are not.
- **Row 4's 437 is a floor with an asterisk**: it is what *WSJT-X's* front end achieves. It
  measures the prize's existence and size, not our cost of reaching it — reaching 80% of it for
  20% of the cost is a perfectly plausible outcome of the scoping study, and so is the reverse.
- **Row 2's real prize is unmeasurable with current instruments** (no subtraction toggle exists
  in jt9, and building one in ft8_lib is itself row-2 work). The menu prices it honestly as a
  bounded unknown rather than pretending precision.
- **E confirmed my prior.** I flagged before the measurement that a confirming result should be
  read with suspicion of the prior's influence; the mitigations are that the estimator, bands,
  and arm-selection rule were all fixed before any number existed, and QA ran it, not me.

## 7. Cross-references

- `2026-07-26-2350-qa-to-architect-b1-b2-notification.md` — the notification this accepts.
- `2026-07-26-b1-jt9-ablation-findings.md` / `2026-07-26-b2-synthetic-calibration-findings.md` —
  the two measurements; their caveat sections carry into §6 here unabridged.
- `2026-07-26-2330-architect-capability-pricing-plan.md` §5 — this memo's pre-registered skeleton.
- `2026-07-26-2230-architect-sec6-redesign-ruling.md` §6, §7 — E's estimator, reading rule, and
  my pre-registered prior.
- `2026-07-26-0015-d001-consolidation-and-clean-slate.md` §6.3 — the parked question, now put.
- `openspec/changes/archive/2026-06-07-fix-d001-pcm-sic/` and the June revert — row 2's history.

---

*Per HK-014 this is committed locally and goes no further. Per HK-015 any follow-on work — the
row-4 scoping study, the second corpus — is a recommendation for QA to scope and author; nothing
is tasked by this memo. The decision on the menu is the Captain's, at whatever time the Captain
chooses; nothing about this note expires.*
