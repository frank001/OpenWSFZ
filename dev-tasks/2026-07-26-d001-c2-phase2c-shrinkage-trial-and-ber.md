# Developer handoff: D-001 C.2 Phase 2c — LLR shrinkage trial + hard-decision BER measurement

**Authored by:** QA (per HK-000/HK-015), scoping the Architect's two recommendations below into one
session per the Architect's own instruction that they share risk profile and harness.
**Status:** **one Developer session (HK-011), diagnostic-only, nothing shipped.** Both diagnostics
are default-off and opt-in, in the shape C.2 Phase 1's `ft8_set_candidate_diag_capture` already
established and was verified a behavioural no-op when disabled.
**Supersedes (for scope, not for content):** `2026-07-26-d001-c2-phase2-llr-shrinkage.md` §3's
framing of Phase 2b as an unflagged, no-partial-shipping hot-path change. That framing was correct
for the *ship* decision and remains correct for it — §3 of that file is still the ship spec if this
trial succeeds. It was wrong applied to the *test*, which is what this file scopes instead. See
§5 below for exactly what does and does not carry forward.
**Source:**
- `qa/cycleframer-alignment-replay/2026-07-26-1930-architect-c2-phase2a-ruling-revision.md` §5
  (shrinkage trial design and decision rule), §6 (sequencing with the BER measurement) — the
  correction that reopens item 3 as "Open — measuring" after the 18:30 note closed it.
- `qa/cycleframer-alignment-replay/2026-07-26-1830-architect-c2-phase2a-ruling.md` §6 (BER
  measurement design, feasibility notes, reading table) — item 4's opening measurement, unchanged
  by the 19:30 revision.

---

## 1. Why this session now

Item 3 (LDPC survival / LLR quality) was closed-declined by the Architect at 18:30, then reopened
at 19:30 under Captain challenge — not because the underlying concerns were wrong, but because the
18:30 ruling priced the *experiment* at the cost of the *ship* (D-009 recalibration, R&R S1–S8
rerun, held-out sweep, unflagged hot-path change). A flag-gated, default-off diagnostic build incurs
none of that. This session is the one bounded experiment the 19:30 note authorises — nothing more.

Item 4 (structural decoder difference) opened at 18:30 with a single recommended measurement — the
hard-decision BER of our LLRs against the true codeword — which the 19:30 note explicitly keeps
un-displaced and schedules into the **same** session, since both diagnostics touch the same shim,
validate against the same offline harness, and carry no ship risk between them.

**Nothing about D-009 recalibration, the R&R rerun, the held-out weight sweep, or a hot-path change
is authorised by this file.** See §5.

## 2. Scope, part A — the shrinkage toggle (19:30 note §5)

1. **Add a thread-local, default-off shrinkage toggle**, `ft8_set_llr_shrinkage(double weight)`,
   plumbed from shim TLS into `ftx_normalize_logl`
   (`native/ft8_lib_build/patched/ft8/decode.c:379-399`). This is patched ft8_lib, not the shim
   proper — more plumbing than C.2 Phase 1's one-file diagnostic, but still one session's worth.
2. **Weight 0.0 must reproduce baseline exactly** — identical matched-decode count against a
   pristine build on the same corpus, not merely "close." This is the trial's own no-op proof. If
   it does not reproduce exactly, stop and fix that before reading any other row; floating-point
   reordering introduced by the toggle's mere presence is a plausible failure mode here, not a
   nuisance to route around (19:30 note §8).
3. **Sweep the weight**: 0.0 / 0.25 / 0.5 / 0.75 / 1.0 as the first grid. A yield that appears at
   one weight and vanishes either side is a tuning artefact, not an effect — say so if it happens.
4. **The metric is matched decodes, not total decodes.** Report, per weight, the same table shape
   as C.1's and C.4's findings: total decodes, matched, unique-to-us, Δ matched, unique share. A
   weight that raises total decodes without raising matched decodes is manufacturing false decodes
   and must be reported as such, not folded into a headline number.
5. **Report three populations separately, every weight**: the 135 (score ≥10, C.2 Phase 1's
   original population), the 567 (score 5–9, Phase 2a's expanded population, where the metric
   shrinkage targets currently runs the *other* way per the 18:30 note §2.2/§3), and the
   matched-hit control. If the 135 and 567 move in opposite directions, that is a finding to report
   as-is, not to average away.
6. **Report elapsed time against the 15 s budget**, same as C.1 and C.4 — the toggle adds work to
   the hot path even at weight 0.0.
7. **Run on the discovery corpus** (`artefacts/20260725_live_run_1806/`) only, for this session.
   The 19:30 note is explicit: a positive result there is an upper bound requiring held-out
   confirmation before it means anything for shipping, not a result to act on directly. Held-out
   confirmation is the next session, gated on §4's decision rule, not part of this one.

## 3. Scope, part B — hard-decision BER measurement (18:30 note §6)

1. **Verify the Gray/sync extraction round-trip first, before building anything on it.** The
   Architect flagged this unverified: `ft8_encode_message` (`ft8_shim.h:542`) returns 79 tone
   indices; stripping the 21 sync symbols and Gray-decoding the remaining 58×3 bits should recover
   the 174-bit codeword, but this has not been confirmed end to end. Confirm it round-trips against
   a known message (encode → strip/decode → compare to the codeword you started from) before
   relying on it for anything below. **If it does not round-trip**, the fallback is a small opt-in
   export of the codeword array from inside `ft8_encode_message` itself — treat that as in-scope
   for this session if needed, not a reason to stop.
2. **Add a native diagnostic export of the 174 raw LLR values** into `candidate_diag.csv` capture
   (currently aggregates only — `prenorm_var`, `postnorm_mean_abs_llr`). Opt-in, default-disabled,
   same shape as `ft8_set_candidate_diag_capture` — verify it a behavioural no-op when disabled,
   same discipline as Phase 1.
3. **For each missed message WSJT-X reported**, re-encode WSJT-X's own reported text to recover the
   true 174-bit codeword (via step 1's round-tripped path), and compare it against the hard decision
   of our LLRs for the candidate sitting at that message's frequency/time.
4. **Report hard-decision BER for the 135, the 567, and the matched-hit control, separately** — same
   population split as part A, for the same reason: if the two missed populations return different
   BERs, that is the mechanism distinguishing them.
5. **Read against the Architect's bands, but do not treat them as calibrated**: ≈50% → sync/
   demodulation front-end, kills all LLR-scaling avenues including the shrinkage trial's own
   permanently; ~15–25% → decode effort (BP iterations, OSD depth/gate), cheap constants; low with
   correct signs → LLR magnitude, reopens Phase 2b's ship case per §4's decision rule. These bands
   are illustrative, not derived from this codebase's actual LDPC/OSD correction power — say so in
   the findings write-up rather than reading a hard boundary into them.

## 4. Decision rule — fixed now, not after the numbers are visible

**Part A (shrinkage), read against Δ matched decodes on the discovery corpus:**

| Δ matched | reading | next |
|---:|---|---|
| **≥ 50** (≥6% of the 793 gap) | materially larger than anything found in this thread | Proceed to held-out corpus confirmation, then the full ship-validation set (D-009 recal + R&R S1–S8) — a new session, not this one. |
| **10 – 49** | comparable to C.1's +12 — real but modest | Captain's call, with a measured number instead of a ceiling. Architect wants held-out confirmation before framing it either way. |
| **< 10** | C.4's shape | Item 3 closes on evidence. The 18:30 decline was right, established this time by measurement rather than argument. |
| **negative at any weight** | shrinkage costs decodes | Closes immediately; confirms rather than merely raises the 18:30 note's wrong-sign concern. |

**Part B (BER)** feeds item 4, not item 3, and is read independently per §3.5's bands. The two
parts answer different questions (§6 of the 19:30 note: shrinkage answers *whether*, BER answers
*why*) and neither result should be allowed to soften the other's reading.

**If session scope forces a split, run part A (shrinkage) first** — it is the one with a decision
rule already fixed and it is what the Captain's original challenge asked for (19:30 note §6).

## 5. What this session does **not** authorise

- **No ship decision, on either item.** A positive shrinkage result at Δ≥50 authorises held-out
  confirmation as the *next* session, not a ship. A low BER does not authorise Phase 2b either — it
  reopens the case for the Captain/Architect to decide against a real number.
- **No D-009 recalibration, no R&R S1–S8 rerun, no held-out weight sweep, no unflagged change to
  `ftx_normalize_logl`.** All of these remain exactly as costed in
  `2026-07-26-d001-c2-phase2-llr-shrinkage.md` §3, and none of them start until this session's
  result triggers §4's ≥50 row and the Captain/Architect act on it.
- **`K_MIN_SCORE` stays at 10.** Untouched by anything in this file.

## 6. Definition of done

- [ ] `ft8_set_llr_shrinkage(double weight)` implemented, thread-local, default 0.0.
- [ ] Weight-0.0 no-op self-check passes (byte-identical matched-decode count vs. pristine build)
      before any other row is trusted. If it fails, that failure is reported and fixed first.
- [ ] Weight sweep (0.0/0.25/0.5/0.75/1.0) run on the discovery corpus; matched/total/unique-share
      table reported per weight, per population (135 / 567 / matched-hit control).
- [ ] Elapsed time reported against the 15 s budget for at least the highest-cost weight.
- [ ] Gray/sync round-trip verified against a known message before use; result (pass, or fallback
      export used) stated explicitly in the findings doc.
- [ ] 174-value LLR export added to `candidate_diag.csv` capture, opt-in/default-off, verified a
      behavioural no-op when disabled.
- [ ] Hard-decision BER reported for 135 / 567 / matched-hit control, separately.
- [ ] A written verdict against §4's decision rule for part A, and against §3.5's bands for part B —
      not left ambiguous, per this thread's own established convention.
- [ ] If Δ matched ≥ 10 (either the 10–49 or ≥50 row), or BER reads low-with-correct-signs, the
      Architect is notified per HK-015 before any further session is scoped.
- [ ] NFR-021: no callsigns or raw message text in anything committed. The BER measurement works
      directly with WSJT-X's reported message text and re-encoded codewords — aggregate the BER
      statistics before they reach any committed script output or findings doc, same discipline as
      `c4_matched_decode_verification.py`. Per-message codeword/LLR dumps, if produced for
      debugging, stay under `artefacts/` (git-ignored), never committed.
- [ ] `git status` clean of any rebuilt `libft8.dll` beyond what this diagnostic branch needs, with
      Captain sign-off before merge (HK-010/HK-011) — lower risk than Phase 2b's hot-path change,
      but still a native rebuild, not a dormant constant.

**Not on the Developer's checklist:** `python3 tools/pre_merge_check.py` (HK-006). That gate is
QA's own step, run during review after this session hands back a diff — not something to run as
part of implementing this task.

## 7. Cross-references

- `qa/cycleframer-alignment-replay/2026-07-26-1930-architect-c2-phase2a-ruling-revision.md` §1, §3,
  §5, §6, §8 — the trial's design, decision rule, and the honest caveats (no-op assumption, banding
  calibrated against this thread's own history) this file inherits verbatim.
- `qa/cycleframer-alignment-replay/2026-07-26-1830-architect-c2-phase2a-ruling.md` §6, §7 — the BER
  measurement's design, feasibility uncertainty (Gray/sync round-trip unverified), and reading
  bands; §7's "what this does not overturn" list, unaffected by this file.
- `dev-tasks/2026-07-26-d001-c2-phase2-llr-shrinkage.md` §3, §4 — Phase 2b's ship spec, gated on
  this session's part A per §4's decision rule; its costs are unchanged and not paid here.
- `qa/cycleframer-alignment-replay/2026-07-26-c2-llr-normalization-findings.md` §6 — Phase 1's
  shrinkage-toward-median design this trial implements behind the new toggle.
- `native/ft8_lib_build/patched/ft8/decode.c:379-399` (`ftx_normalize_logl`) — part A's toggle
  target.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.h:542`, `ft8_shim.c:1058` (`ft8_encode_message`) — part B's
  reference-side entry point.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c:1147` (`ft8_set_candidate_diag_capture`) — the default-off,
  verified-no-op pattern both parts of this session follow.

---

*Per HK-014 nothing is pushed or merged. Per HK-015 this is QA-authored dev-task material; the
Architect's §5/§6 recommendations across both source notes are scoped here into one session at
QA's own judgement on sizing (see the risk note below). Any result at or above §4's 10–49 row, or a
low-BER read in part B, routes back to the Architect before further scoping — sideways into a quiet
continuation is not the convention this thread has kept.*

**QA sizing note, stated plainly rather than folded into the checklist:** this session stacks three
non-trivial unknowns — new hot-path-adjacent plumbing in patched ft8_lib, an unverified Gray/sync
round-trip, and a new diagnostic export — into one HK-011 session. Each individually matches the
size of prior sessions in this thread; together they have not been attempted at once before. §4's
"if session scope forces a split, part A first" is the Architect's own escape hatch for this, and
the Developer session should invoke it and report back rather than push through on time pressure.
