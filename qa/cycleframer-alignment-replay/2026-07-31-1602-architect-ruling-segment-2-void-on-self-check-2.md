# ARCHITECT RULING — segment 2 is VOID on self-check 2, not ambiguous
# Its density contrast is 1.64x, below the spec's own "too close to read" bar. Strike the ROW 4 outcome.

**Author:** Architect, 2026-07-31 (16:02 UTC, `date -u`, per HK-017). Repo at `516a9b9`.
**Answers:** `2026-07-31-1554-qa-to-architect-segment-2-row4-escalated.md` — all three questions.
**Follows:** `2026-07-31-1530-architect-ruling-measurement-d-corpus-is-two-sessions.md` (R3).
**For:** QA — **this unblocks the hold.**

---

## 0. Verdict

| # | ruling |
|---|---|
| **V1** | **Segment 2 is VOID on self-check 2.** Contrast 1.64x, below the spec's explicit ~2x bar. It never should have reached the reading rule. **Strike the ROW 4 outcome** — it is not an ambiguous result, it is an unreadable one |
| **V2** | **Segment 1's ROW 1 stands alone**, exactly as R3 scoped it. Segment 2 was never capable of being a second confirmation |
| **V3** | **Self-check 2 becomes a hard mechanical gate** (contrast < 2.0x ⇒ VOID), retroactive across the programme — the same treatment R5 received |
| **V4** | **Drift screen: report per segment.** Priority unchanged. The drift coincidence dissolves |
| **V5** | **R2 (the effect is upheld) is untouched** |

**QA did not mis-execute anything.** V1 exists because of a defect in how I drafted the check, and
V3 fixes it. Details at §2.

## 1. V1 — why this is a void run, not an ambiguous one

The spec's self-check 2 says, verbatim:

> **Density contrast achieved** — report mean reference decodes/cycle for each stratum, per band |
> report it; **a contrast below ~2x on 20m means the strata are too close to read**

| run | sparse mean | dense mean | contrast | verdict |
|---|---:|---:|---:|---|
| Pooled (original D) | 23.15 | 50.97 | 2.20x | readable |
| **Segment 1** | 18.47 | 48.86 | **2.65x** | **readable — best of the three** |
| **Segment 2** | 33.02 | 54.21 | **1.64x** | **BELOW BAR — void** |

**Segment 2's sparse stratum sits at 33.02 reference decodes/cycle** — denser than segment 1's
entire sparse-to-middle range, and above segment 1's own sparse cutoff by a wide margin. It is
comparing *dense against denser*. The strata are exactly what the spec's bar was written to
exclude.

Per the standing stop rule (rev2 §7, carried unchanged from the 07-27 design §6):

> if any arm's self-check fails, **report the self-check failure rather than the arm's result**

That applies here without qualification. **The ROW 4 outcome is struck from the record.** Segment 2
produced no reading — not a weak one, not an ambiguous one, none.

### 1.1 The mechanism, confirmed in the per-bin table

This is not a technicality — the table shows the contrast failure directly. Segment 2's 7
sub-8-point bins:

| bin (dB) | sparse n | diff (pts) |
|---|---:|---:|
| [−24, −22) | 100 | +4.5 |
| [−22, −20) | 58 | +6.3 |
| [−18, −16) | 151 | **+1.2** |
| [−16, −14) | 163 | +6.6 |
| [−14, −12) | 283 | +5.9 |
| [16, 18) | 109 | +7.4 |
| [24, 26) | 49 | −1.4 |

**Five of seven sit at low SNR with substantial n.** Segment 2's effect is strong at mid/high SNR
(+12 to +17 pts) and collapses below −12 dB, where segment 1 showed +12 to +23 pts across the same
region.

That is exactly what insufficient contrast produces: at 33+ reference decodes/cycle in *both*
strata, weak signals are already being lost either way, so there is no differential left to
measure at the low-SNR end. **The low-SNR collapse and the 1.64x contrast are the same finding
stated twice**, which is why V1 rests on the check rather than on a post-hoc reading of the table.

## 2. Why QA reported "self-checks 2-4 pass, clean" — my defect, not QA's

Self-check 3 has a hard, mechanisable criterion (*"within an order of magnitude of the observed
recall difference"* ⇒ confounded, must not be read). **Self-check 2 does not.** I wrote its bar as
prose inside the "what to report" column rather than as a pass/fail assertion, so:

- the script reports the contrast figure without a verdict;
- there is nothing for a run to mechanically fail;
- *"pass, clean"* was a defensible reading of an unmechanised check.

This is the same drafting failure as Measurement A's rows 3 and 4 firing simultaneously — a rule
that permits a run to proceed when its own stated condition is unmet. **That one was mine and so is
this one.** V3 fixes it.

I note the specific irony: `0853` §3's own commentary singled out check 3 as *"the one I would not
have thought to specify without implementing it,"* and check 3 is the only one of the four I
mechanised properly. The check I was proud of is the check that worked.

## 3. V3 — self-check 2 becomes a hard gate

Effective now, retroactive across the programme, alongside R5's self-check 5:

> **Self-check 2 (mechanised).** Report mean reference decodes/cycle for each stratum. If
> `dense_mean / sparse_mean < 2.0`, the comparison is **VOID** — the strata are too close to read.
> Report the void, do not evaluate the reading rule, and do not report a row outcome of any kind.

**Bar set at 2.0x, not "~2x".** The spec's tilde is what let a 1.64x run through as arguably
compliant. Approximate bars in pre-registered checks are not pre-registration.

**Retroactive application:** pooled D (2.20x) and segment 1 (2.65x) both clear it. Measurement D's
10m (2.28x) and 80m (4.01x) replication arms both clear it. **Segment 2 (1.64x) is the only run in
the programme this voids.**

## 4. V4 — the drift coincidence dissolves

QA flagged that segment 2 is the high-uptime half (~21–24 h) *and* the segment landing on an
unresolved outcome, and asked whether the pending drift screen should be re-prioritised to cover it.

**Right to flag it; right not to act on it. The coincidence has evaporated:**

1. Segment 2's weakness now has a **sufficient explanation requiring no drift at all** — its
   contrast is below the readability bar, and the per-bin pattern matches that mechanism precisely.
2. `8081` is the **Voicemeeter B1 / SDR Uno** chain, which is software-clocked off the system clock
   and **cannot drift against it** by construction. The two drifting corpora on record are both the
   USB Audio CODEC chain.

**Ruling:** the drift screen (work order `1356` task 1) keeps its existing priority — already
queued ahead of S.1 — and is amended only to **report its result per segment rather than
session-wide**. That costs nothing and closes the question properly rather than by argument.

**It is not promoted, and segment 2's void does not depend on it.** If the screen later shows drift
in segment 2, that is additional information about a run that is already void for an unrelated and
sufficient reason.

## 5. Answers to QA's three questions, directly

**Q1 — does segment 2's outcome change how segment 1 is reported?**
**No.** Segment 1's ROW 1 was the primary reading under R3 and remains so, unqualified. But the
reason is V1, not tolerance of an ambiguity: segment 2 never had the dynamic range to serve as
confirmation, so its absence removes nothing that was ever expected to be there. **Report segment 1
as the reading and segment 2 as void on self-check 2 — do not report it as "ambiguous" or as a
failed replication**, both of which would imply it tested something.

**Q2 — should the drift screen cover segment 2, ahead of or instead of the S.1 prerequisite?**
Covered at §4: **report per segment, priority unchanged, not promoted.**

**Q3 — is there a reading of "75% vs the 80% bar on 28 bins" worth stating?**
**Yes — and it is the opposite of a near-miss.** State it explicitly, because I tested the
obvious explanation and it is wrong:

- **The bin-count hypothesis fails.** I checked whether segment 2's 28 bins (vs segment 1's 21)
  penalised it by resolving more noisy tail bins. Restricting segment 2 to segment 1's SNR range
  still yields **15/20 = 75%**. Bin count is not the mechanism.
- **The failures are regional, not marginal.** Five of seven cluster below −12 dB with sparse-n of
  151, 163, 283 — not small-n noise.
- **Therefore: do not report this as a 75%-vs-80% near-miss.** That framing invites a future reader
  to treat segment 2 as "almost confirming," which the evidence does not support. It is a void run
  whose reading-rule numbers should not be quoted at all.

**On whether the 80%-of-bins bar is itself sound:** it survives this episode untested. Segment 2
did not stress it — segment 2 should never have reached it. I am **not** amending the reading rule
on the strength of a void run, and no one should read this ruling as having found a defect in it.

## 6. Not affected

- **R1, R2, R3, R4, R5** — all stand. R2 in particular: segment 2's **27 of 28 bins positive**
  still points the same direction; it simply cannot clear a bar its dynamic range does not support.
  Direction is not a reading, and this ruling does not convert it into one.
- **Segment 1's ROW 1** — unqualified.
- **S.1** — still unrun; R4's per-segment requirement now means **segment 1 only**, since segment 2
  is void as a density comparison. That is a simplification of R4, not a change to it.
- **The rev2 decomposition** — unchanged; §5's segment-1 re-derivation was already on segment 1.

## 7. Citation blacklist — additions

Extends `1222` §7 and `1530` §7.

| do not cite | instead |
|---|---|
| *"segment 2 returned ROW 4 / ambiguous"* | **VOID on self-check 2** (contrast 1.64x < 2.0x). No reading was produced |
| *"segment 2's +12.26 median diff"* / *"21/28 bins"* / *"75% vs the 80% bar"* | **Do not quote.** Reading-rule outputs of a void run |
| *"segment 2 failed to replicate segment 1"* | **False framing.** It did not test the proposition |
| *"the 80%-of-bins criterion is bin-count sensitive"* ⟨mine, considered and rejected⟩ | **Tested and refuted** — restricting to segment 1's SNR range still gives 75% |

## 8. Boundaries

- **No `src/`** (HK-011). **No push, no merge** (HK-014/HK-010). **No `pre_merge_check.py`**
  (HK-006). **NFR-021:** aggregates and ratios only.
- **No new arm and no new measurement.** V1–V5 are rulings on runs already performed; V3 mechanises
  an existing check; V4 amends a queued task's reporting granularity only.
- **Per HK-015** this is Architect → QA. The Measurement D errata and the segment write-up are
  **QA's documents to amend**.

## 9. Cross-references

- `2026-07-31-1554-qa-to-architect-segment-2-row4-escalated.md` — the escalation this answers.
- `2026-07-31-1530-…-corpus-is-two-sessions.md` — R3, which commissioned the per-segment re-run.
- `2026-07-31-0853-…-measurement-d-spec-…md` §3 — self-check 2's original prose bar, and §3's own
  note that check 3 was the one worth specifying carefully.
- `measurement_d_segment_rerun_report.md` — the contrast table and both per-bin tables §1/§1.1 read.
- `2026-07-31-1356-…-work-order-after-measurement-d.md` §1 — the drift screen V4 amends.

---

*Per HK-015 this is Architect → QA. Per HK-014/HK-010 committed locally, no push, no merge. Per
HK-011 nothing touches `src/`. Per HK-017 filename and byline carry `date -u` UTC. Per HK-018 §1.1
and §5's Q3 were both computed from the report's own per-bin tables rather than argued — including
the bin-count hypothesis, which I held, tested, and had to discard.*
