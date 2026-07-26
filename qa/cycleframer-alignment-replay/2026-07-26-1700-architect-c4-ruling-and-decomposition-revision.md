# D-001: Architect ruling on the C.4 escalation, and a revised decomposition

**Author:** Architect, 2026-07-26 (17:00). **For:** the Captain and QA.
**Answers:** `2026-07-26-1500-qa-to-architect-c4-min-score-escalation.md` §5, decisions 1 and 2.
**Supersedes:** `2026-07-26-0015-d001-consolidation-and-clean-slate.md` §3 (the two-mechanism
decomposition) and re-sequences its §6. The §1 gap decomposition and the §2 closed list in that
document are untouched and still stand.

QA was right to escalate rather than revise the table quietly, and right that my §3 claim —
"these are the only two things standing between us and the 740" — does not survive C.3/C.4. It is
withdrawn below. But the revision the evidence supports is not the one the escalation proposes.

---

## 1. Short answer

**C.4's headline verdict does not survive verification. It inverts.** Lowering `K_MIN_SCORE`
recovers candidates spectacularly and decodes essentially nothing. The score floor is a real gate
on candidate *generation* and a non-factor in the D-001 decode gap.

Decision 1 (revise the decomposition): **yes** — to record score-floor rejection as a *closed*
avenue with near-zero decode yield and a material false-decode cost, not as a large open one.

Decision 2 (re-sequence §6.3): **yes, but upward.** The escalation asks whether the structural
avenue can now be skipped. The opposite follows: C.4 removes the cheap explanation for the gap and
supplies the first direct evidence that the residue is structural.

## 2. The measurement C.4 did not make

`c4_min_score_sweep_analysis.py` reports `recov648`: how many of C.3's 648-message population gain
*any candidate* at a given floor. The script's own closing note states this is "not the same as a
decode." The findings doc's §1 and §6 nonetheless present the resulting series — 16.2% → 50-51% →
55-91% → 58-95%+ — as the experiment's verdict, and the escalation's §2 table carries it forward as
"Confirmed, and large."

The quantity that closes the D-001 gap is **matched decodes**: how many of WSJT-X's 2028 messages
we actually decode. `total decodes` cannot distinguish a recovered signal from a false decode.
Matched decodes can. Computed from each setting's own committed artefacts
(`c4_matched_decode_verification.py`, alongside this note):

| setting | total decodes | **matched** | unique-to-us | Δ total | **Δ matched** | unique share |
|---|---:|---:|---:|---:|---:|---:|
| K=10 @600 (shipped floor) | 1300 | **1239** | 61 | — | — | 4.7% |
| K=8 @600 | 1358 | **1241** | 117 | +58 | **+2** | 8.6% |
| K=6 @600 | 1365 | **1241** | 124 | +65 | **+2** | 9.1% |
| K=4 @600 | 1368 | **1242** | 126 | +68 | **+3** | 9.2% |
| K=8 @2000 | 1357 | **1241** | 116 | +57 | **+2** | 8.5% |
| K=6 @2000 | 1573 | **1241** | 332 | +273 | **+2** | 21.1% |
| K=4 @2000 | 1617 | **1241** | 376 | +317 | **+2** | 23.3% |

Row counts equal deduped counts at every setting, so `matched = total − unique` exactly; there is
no dedup artefact hiding in this table.

**618 of the 648 gap messages regained a candidate at K=4 @2000. Two of them decoded.** Every other
message added by lowering the floor is absent from WSJT-X's output. C.4's own §6 reasoning — that
recovery "rises sharply and monotonically" while false positives stay "bounded" — is measuring
candidate recovery against a false-positive proxy, and both halves fail on inspection.

## 3. Why the added decodes are not decodes

Three independent axes, all computed over the same artefacts:

| setting | n unique | persistence (unique) | persistence (matched) | median SNR (unique) | median SNR (matched) | callsign reuse |
|---|---:|---:|---:|---:|---:|---:|
| K=10 @600 | 61 | **0.0%** | 24.9% | −17 dB | −3 dB | 8.2% |
| K=8 @600 | 117 | **0.0%** | 25.2% | −19 dB | −3 dB | 4.3% |
| K=6 @2000 | 332 | **0.0%** | 25.2% | −22 dB | −3 dB | 3.0% |
| K=4 @2000 | 376 | **0.0%** | 25.2% | −22 dB | −3 dB | 2.9% |

- **Persistence** — share of distinct message texts appearing in more than one cycle. A station
  calling CQ transmits every other cycle; across a 68-cycle (~17 minute) corpus, real traffic
  repeats, and the matched population duly does at ~25%. Not one of 376 unique-to-us messages
  recurred in a second cycle, at any setting. With n=376 and zero repeats, this is not a marginal
  signal.
- **SNR** — the unique population's median falls to −22 dB as the floor drops. FT8's decode
  threshold is approximately −21 dB. A population centred *below* the physical decoding limit is
  not a population of signals.
- **Callsign reuse** — the share of unique-to-us messages containing a callsign-shaped token that
  appears anywhere in the known-real matched population *falls* as the floor drops, 8.2% → 2.9%.
  Genuine additional decodes of the same band's traffic would move the other way.

### 3.1 Two metrics in the C.4 report that should not be relied on again

- **Grammar validity is uninformative.** The findings doc does not lean on it explicitly, but it is
  worth recording before someone does: the unpacker emits syntactically legal text for *any* 77-bit
  payload that clears CRC, so ~98% grammar validity is guaranteed by construction at every setting,
  including for pure noise. It is not evidence of authenticity.
- **The `uniq/recov` ratio is not a false-positive signal.** §8 of the findings doc treats its
  0.34–0.61 band as evidence that recovery outpaces noise. It divides unique-to-us decodes by
  *candidate* recovery — two quantities with no causal relationship. Because the denominator grew
  6× while the numerator grew 6×, the ratio stayed flat while the underlying false-decode rate rose
  from 4.7% to 23.3% of output. The ratio's stability was an artefact of its own denominator. The
  honest denominator is our own total output, which is the last column of §2's table.

## 4. Ruling 1 — the revised decomposition

§3 of the consolidation doc is replaced by the following. My "only two things" claim is
**withdrawn**: it was inferred from decile aggregates that could not see candidate identity, and
C.3 was correct to break it.

| # | mechanism | status | measured decode yield |
|---|---|---|---|
| 1 | **Candidate-array truncation** (`K_MAX_CANDIDATES`) | **Closed** — C.1 | +12 decodes, +1.6% of gap. Real, small, plateaus. |
| 2 | **Sync score-floor rejection** (`K_MIN_SCORE`) | **Closed** — C.3/C.4 + this note | **+2 decodes** while false decodes rise 61 → 376. Candidate generation was never the binding constraint. |
| 3 | **LDPC survival / LLR quality** | **Open — now primary** | C.2 Phase 1 bounded at 135 messages; Phase 2 scoped, unshipped. |
| 4 | **Structural decoder difference vs WSJT-X** | **Open — promoted from last resort** | Unmeasured. See §5. |

The escalation proposes entering the score floor as "large, largely unscoped" (its §5.1). It is
large only on the candidate-recovery metric. On decodes it is closed, and closing it is the
genuine contribution of C.3 and C.4 — a cheap avenue eliminated with a clear number, which is worth
more than the sprawl §2 of the consolidation doc was written to stop.

### 4.1 What C.3 got right and where its inference broke

C.3's population split (1235 / 135 / 10 / 648) is correct, independently reproduced twice, and
remains the best map of the missed-message set we have. Its statistical results stand: co-channel
masking is refuted, and the gap population is decisively weaker-signal (p = 1.1×10⁻⁷⁴).

The step that does not hold is the causal one — from "no candidate exists near that
frequency/time" to "candidate generation is therefore the constraint." C.4 supplied the missing
candidates and the decodes did not follow. Absence of a candidate was a *symptom* of a signal our
demodulator cannot resolve, not the *cause* of its being missed. This is a good-faith inference
that the experiment it motivated then falsified, which is the system working.

## 5. Ruling 2 — §6.3 moves up, not away

The escalation asks whether the structural-comparison avenue "may not need to be reached at all,
or at least not next," on the premise that `K_MIN_SCORE` could close the majority of the gap. That
premise is now withdrawn, so the question resolves the other way.

More than that, C.4 has produced the first *positive* evidence for the structural hypothesis, which
we did not previously have. At K=4 we can place a sync candidate at the exact frequency and time
where WSJT-X decodes a message at −8 dB, hand it to LDPC/OSD, and still fail. That is no longer
"we cannot find these signals." It is **"we can find them and cannot demodulate them"** — which
localises the residue downstream of sync, in LLR quality and in decode-pass structure. Those are
items 3 and 4 of §4's table.

Revised sequencing:

1. **C.2 Phase 2 (LLR normalisation) proceeds, and is now the primary D-001 avenue.** C.4
   strengthens rather than bounds it: the 648 population is not a separate territory that Phase 2
   cannot reach, it is the same downstream weakness measured at the sync stage. Phase 1's "caps out
   at ~17% of the remaining gap" bound was computed against a population split that assumed the 648
   were unreachable by LLR work. That assumption is now doubtful, and re-deriving Phase 2's ceiling
   against the K=4 candidate set is the cheapest way to test it.
2. **§6.3 (structural comparison) is no longer a last resort.** It stays behind Phase 2, but as the
   named successor rather than a contingency. It remains a Captain-level product decision — how
   much of WSJT-X's decoder we are willing to reimplement — and I still want Phase 2's number
   before framing it. That framing is now much better supported than it was at 00:15.
3. The follow-up conditions the findings doc §10 lists — the ceiling-free K=4 number, D-009 OSD
   re-calibration, a full R&R S1–S8 rerun — are **not needed**, because they exist to qualify a
   `K_MIN_SCORE` ship decision and no such decision should now be scoped. Dropping them is a real
   saving; taken literally they were several sessions of work.

## 6. What this does not overturn

Stated explicitly, so this note is not read as broader than it is:

- **C.1's verdict stands** (`K_MAX_CANDIDATES` real but small). Unaffected.
- **C.2 Phase 1's verdict stands** (LLR normalisation confirmed, bounded). §5 above raises its
  priority; it does not question its result.
- **C.3's population split and statistics stand.** Only the causal inference in its §4/§6 is
  revised, per §4.1.
- **The `MaxPass0Candidates` 140 → 600 fix is correct and should be kept**, exactly as the Captain
  signed off. C.4's §3 found a genuine managed-side truncation bug of the same class as C.1's
  `K_MAX_CANDIDATES_ANY_PASS` landmine, and finding it was real work. That fix is independent of
  whether the sweep's conclusion held.
- **The consolidation doc's §1 and §2 stand unchanged.** D-001 remains a decoder problem at 98.5%
  of the gap, and nothing on the closed list reopens.
- **C.4 was a well-executed experiment.** It caught its own methodology bug mid-flight (§3), it
  recorded its deviations, and it declined to ship a constant. The error is confined to which
  column was read as the result.

## 7. Held, not scoped: false decodes at the shipped settings

The verification surfaces something outside D-001's scope: **at the currently shipped floor, 61 of
1300 decodes (4.7%) are unique to us, with 0.0% cross-cycle persistence and a median SNR of
−17 dB.** On the §3 axes these look like the same population as the ones the lower floors multiply
— which would mean false decodes are reaching the UI and ADIF today.

Two honest qualifications. WSJT-X is a reference, not absolute ground truth, so "unique to us" is
not identically "false"; and some CRC-collision rate is expected from any LDPC+14-bit-CRC decoder,
so a non-zero floor here is normal. Whether 4.7% *is* that expected floor or a defect is not
settled by this note, and I am not asserting it.

**Per the Captain's instruction this is held, not scoped.** Recorded here so it is not rediscovered
from scratch. When it is picked up, the decisive test is cheap and offline: decode noise-only audio
containing no signals and count messages, sweeping the floor. Every decode is false by
construction, which yields the per-cycle false-decode rate directly and calibrates whether 61 is
the expected CRC-collision floor. It needs a Developer session for the rebuild (HK-011) and one
harness run — it does not need a live run, an R&R rerun, or an OSD re-calibration.

## 8. Honest caveats

- This is one 21-minute session, one device, one band — the same single-sample caveat as the
  consolidation doc's §7, and it applies to my conclusions exactly as it applied to its own.
- The persistence and SNR axes are strong joint evidence about the unique-to-us population, not
  proof. The noise-only test in §7 is what would settle it, and it is deliberately not being run
  yet.
- I have not re-derived *why* a candidate at the right frequency and time fails to decode. §5
  asserts that this localises the residue downstream of sync, which follows from the candidate
  existing; it does not identify which downstream stage, and Phase 2 is what tests that.
- Promoting §6.3 is a change of expected sequencing, not a commitment. It remains a product
  decision and nothing about it should be scoped before Phase 2 reports.

## 9. Cross-references

- `2026-07-26-1500-qa-to-architect-c4-min-score-escalation.md` — the escalation this answers.
- `2026-07-26-0015-d001-consolidation-and-clean-slate.md` §3, §6 — revised by §4 and §5 here.
- `2026-07-26-c4-min-score-sweep-findings.md` — C.4; §5's tables are the source data, §1/§6's
  verdict is what this note revises.
- `2026-07-26-c3-candidate-generation-gap-findings.md` — C.3; population split stands, §4/§6's
  causal inference revised per §4.1.
- `2026-07-26-c2-llr-normalization-findings.md` — C.2; Phase 2 promoted to primary per §5.
- `2026-07-26-c1-candidate-cap-sweep-findings.md` — C.1; unaffected.
- `c4_matched_decode_verification.py` — the verification behind §2 and §3, reproducible against the
  committed artefacts.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c:472` (`K_MIN_SCORE`) — stays at 10. No change is proposed.

---

*Per HK-014 nothing is pushed or merged. Per HK-015 this is Architect → QA material;
`tasks.md` and `dev-tasks/` remain QA's to author, and the §5 sequencing above is a
recommendation for QA to scope, not a task. The §7 false-decode question is held at the
Captain's instruction.*
