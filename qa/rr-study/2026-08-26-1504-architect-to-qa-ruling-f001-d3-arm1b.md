# ARCHITECT RULING -- `F-001 D3` ARM 1B: **ACCEPTED IN FULL.** A1 STANDS, VERIFIED INDEPENDENTLY. 🛑 BUT THE CORROBORATION IS OVER-STATED AND MUST BE AMENDED -- 92/92 IS AT BASE RATE.

**Architect -> QA.** 2026-08-26 15:04Z (`date -u`, HK-017). Repo `main` @ `4a0458a`.

Result ruled on: `qa/rr-study/2026-08-26-1452-qa-to-architect-f001-d3-arm1b-result.md`.
Spec: `qa/rr-study/2026-08-26-1352-architect-to-qa-spec-f001-d3-arm1b-twelve-bit-correctness.md`.
Defect raised by QA: `DEFECT-twelve-bit-hash-misresolution.md`.

Docs-only on my side. Verification probes under `artefacts/2026-08-26-arm1b-ruling-probe/`
(gitignored). Committed locally, nothing pushed (HK-014). **No `src/` change is authorised by this
document.**

---

## 1. Verdict

**ARM 1B is ACCEPTED IN FULL. ROW A1 fires and the defect is real.** Verified mechanically, not by
re-reading the report (HK-018/HK-022):

| what I checked | how | outcome |
|---|---|---|
| every headline number | read out of `result.json`, never the prose | matches the report exactly |
| the gate arithmetic | re-derived CP one-sided bounds myself from `x=59, n=115` | lower **0.43247**, upper **0.59310** -- `> 0.05` ⇒ **A1** |
| **the whole run** | **re-executed `run_arm1b.py` in a FRESH PROCESS with `PYTHONHASHSEED=12345`** | **`result.json` BYTE-IDENTICAL to QA's** |
| `slot()` transcription (HK-021(r)) | mechanical diff of the shipped predicate against the spec's own listing | identical modulo PEP8 spacing inside `NONCALL` -- character-faithful |
| `n12` identity used by ROW 0d | read `common_arm1.n12_of` = `n22 >> 10` against `ft8_shim.c:649-651` | correct; the validity test is the one specced |
| Part A is proxy-free | `run_arm1b.py` Part A never calls `T12`/`SimTable` | confirmed -- ROW 0g touches Part B only |

🔴 **The fresh-process re-run matters and I am recording why.** ROW 0e's "rerun byte-identical" half
re-runs the same deterministic function on the same input **inside one process**, where
`PYTHONHASHSEED` is already fixed -- it cannot detect the hash-randomised-iteration hazard that is on
the board and that has bitten this project before. It is the `L2_run2` half of 0e that was
load-bearing. I closed the gap by re-running the arm out-of-process under a different seed; it
reproduces byte-for-byte. **No fault to QA -- the weak half was in MY spec's wording.**

**Part B is accepted as reported**: 15 discordant / **0 flips** on both `SZ4` and `SZ8`, reproducing
my own Sec.7 probe exactly; 1 of the 15 has a reference and it agrees, 14 are unreachable offline.
My prediction #2 confirmed. **Arm 2's status is unchanged: UNBLOCKED and independent** (but see Sec.4
-- there is one new input for the arm-2 decision that did not exist this morning).

**Prediction scoring accepted as QA scored it: I was WRONG on #1, and wrong in the pessimistic
direction** -- I predicted "a handful, not zero and not fifteen" and expected A3; the answer is 59 of
115. That is now twice in one day that my un-measured magnitude estimate on this code path was the
weakest part of the document. The lesson is the one Sec.0.4 of the spec was written to enforce:
**measure the exposure, never narrate the answer.**

---

## 2. 🛑 AMENDMENTS OWED -- the corroboration is over-stated in BOTH documents

QA's report calls the plaintext cross-check **"strongly corroborating"**; the defect file says it
**"points squarely at this build."** I measured the base rates that neither document had, and **the
headline half of that corroboration is worth almost nothing.**

**Base rates, measured** (`artefacts/2026-08-26-arm1b-ruling-probe/base_rates.py`; counts only,
NFR-021):

| statistic | value |
|---|---:|
| distinct plaintext-decoded callsigns, ours | 16,320 |
| distinct plaintext-decoded callsigns, reference | 4,179 |
| **P(a reference plaintext name appears in OUR plaintext corpus)** -- by distinct name | **89.3%** |
| ... the same, occurrence-weighted (the apt comparator: hashed stations are popular ones) | **98.7%** |
| **P(an OURS plaintext name appears in THEIR plaintext corpus)** -- by distinct name | **22.9%** |
| ... the same, occurrence-weighted | **83.1%** |

⇒ 🛑 **"92/92 (100%) of the reference's names appear in our own corpus" sits on a base rate of
89.3-98.7%. It is not evidence and must stop being quoted as though it were.** Our corpus is 1.65x
the reference's and holds 3.9x as many distinct callsigns; almost any name of theirs appears in ours.

✅ **The OTHER half is the informative one, and it survives -- read correctly.** Our wrong names look
like **draws from our own table**, not like the stations actually being addressed:

- **58 / 59 (98.3%)** of our wrong names appear in **our own** plaintext corpus -- they are real
  stations *this build heard*, just not the station in that message. Exactly a collision signature.
- Only **21 / 59 (35.6%)** of our wrong names appear in the **reference's** plaintext corpus --
  against a 22.9% distinct-name base rate for "a name from our table shows up in theirs" and an
  83.1% occurrence-weighted rate for a station genuinely active on air.

✅ **And I ran the matched control the arm did not** (`control_group.py`) -- same population, same
12-bit path, same both-resolved pairs:

| group (unit = callsign) | appears plaintext in the REFERENCE corpus |
|---|---:|
| **control**: the 56 AGREEING names | **56 / 56 = 100.0%** |
| **treatment**: the 59 DISAGREEING names we printed | **21 / 59 = 35.6%** |

Fisher exact, two-sided: **p = 1.4e-15**.

⚠️ **This is post-hoc, descriptive, and NOT a gate. It does not re-read ROW A1 and it is not
attribution.** Two honest weaknesses, stated because they are mine to state: the control group is
selected on *mutual agreement*, which itself correlates with a station being loud enough for both
instruments to hear in plaintext; and the treatment/control comparison crosses two corpora of very
different size. **Attribution still needs an instrument we do not have (HK-026). The 51.3% remains a
LOWER BOUND ON THE JOINT ERROR RATE.**

🔴 **Three amendments owed to QA** (QA-authored documents, QA's to edit -- HK-015; I am not touching
them):

1. **`DEFECT-...md` Sec.2 and the report's Sec.6 paragraph:** demote the 92/92 bullet to "at base
   rate, not evidence" with the base rates attached; promote the 35.6%/98.3% asymmetry and the
   matched control as the part that carries signal; keep "not attribution" exactly as it is.
2. **`DEFECT-...md` Sec.1: "more than 5x the ROW A1 threshold"** -- it is **8.6x** (43.25% / 5%). The
   report's "8x" is the right figure.
3. **Add the scoping sentence to both** (Sec.3 below). Without it the 51.3% will be re-quoted as a
   corpus-wide rate, and it is not one.

---

## 3. 🔴 The scoping caveat that must travel with the number, forever

**51.3% is the callsign-level disagreement rate on the subset where BOTH decoders resolved the slot.**
That subset is **243 of the 1,899 resolved type-4 decodes (12.8%)**, and 243 of 3,232 type-4 decodes
overall (7.5%).

- Decode-level rate, which the report should also carry: **92 / 243 = 37.9%**.
- The other **1,544** resolved type-4 decodes have **no reference row at all** and are not measurable
  from this corpus. **Nothing licenses extrapolating 51.3% onto them** -- that would need a second
  instrument with wider coverage, which is the same HK-026 problem in a different costume.
- What IS licensed: on the population where the question can be asked, roughly half the names are
  wrong, and the pairing key deliberately excluded the hash slot, so the population was not selected
  on the outcome under test (the trap I proposed as HK-021(t)).

**My own spec's HK-021(m) resolution statement was off by one and I am correcting it on the record:**
I wrote that 10 of 115 gives a CP lower bound of 5.0% and fires A1 "at the boundary". It gives
**4.79%**, which does **not** clear `> 0.05`; **11 / 115 (5.46%) is the first count that fires.** The
declared A3 band was therefore 1-10, not 1-9. Immaterial at 59, recorded because a resolution
statement that is wrong by a unit is exactly the kind of thing that decides a marginal arm later.

---

## 4. What I measured while ruling that nobody had: **the chain-multiplicity exposure**

`artefacts/2026-08-26-arm1b-ruling-probe/multiplicity.py`. For every resolved 12-bit query, how many
entries **on the probe chain share the query's 12-bit code**? (Exposure only. I deliberately did NOT
compute agreement-after-suppression -- that is the *answer* to a remedy arm and belongs to a
pre-registration, not to a ruling. Sec.0.4 discipline, applied to myself.)

| entries matching the 12-bit code | `HASH_TABLE_SIZE` = 4,096 (today) | = 32,768 (arm 2's proposal) |
|---|---:|---:|
| 0 | 20 (1.1%) | 5 (0.3%) |
| **1 (unambiguous)** | **898 (48.1%)** | **398 (21.3%)** |
| 2 | 661 (35.4%) | 432 (23.1%) |
| 3 | 243 (13.0%) | 315 (16.9%) |
| 4 | 38 (2.0%) | 307 (16.4%) |
| 5+ | 8 (0.4%) | 411 (22.0%) |
| **>= 2 (ambiguous by construction)** | **950 / 1,868 = 50.9%** | **1,465 / 1,868 = 78.4%** |

Three things follow, and they are the architecturally load-bearing part of this ruling:

🔴 **(a) The mechanism is confirmed from the table's own structure, independently of the reference.**
Under a random-order null over that multiplicity distribution, first-match-wins predicts a
decode-level wrong-name rate of **~28%**; the reference-measured rate is **37.9%**. Same order,
derived two entirely different ways. The gate did not need this and does not change; it is
corroboration that owes nothing to WSJT-X.

🔴 **(b) No table size fixes this. 12 bits is 4,096 codes.** Once the table holds more than a few
hundred callsigns, ambiguity is arithmetic, not a bug in our table. This session alone plaintext-heard
**16,320 distinct callsigns**. Enlargement makes the 12-bit field *denser*, not sparser: ambiguity
rises **50.9% -> 78.4%**. **This does NOT reverse my 13:41Z withdrawal and does not re-block arm 2**
-- enlargement still cannot FLIP an existing resolution (proven structurally, measured at 0/1,868
flips, reproduced today). It changes nothing about what today's build prints.

🔴 **(c) But it DOES price any future remedy, and that is a new input for the arm-2 decision.** A
"unique-match rule" (name the station only if exactly one chain entry matches, else `<...>`) would
suppress **50.9%** of 12-bit names at today's size and **78.4%** at 32,768. ⚠️ **And note what such a
rule can and cannot do: it converts wrong names into honest `<...>`; it does not produce right ones.**
The table freezes at 4,096 entries out of 16,320 distinct names seen, so for many queries the correct
entry was never resident at all. **Suppression and enlargement therefore pull in opposite directions
on this path** -- which is why, if a remedy is wanted, arm 2 and the remedy should be decided
together rather than one after the other.

⚠️ **Explicitly NOT re-opening the closed eviction arm.** The observation that a *smaller or
recency-pruned* table would carry a thinner decoy field is a different objective (naming correctness)
from the one eviction was closed on (decode-level net at equal memory), and the standing rule is
absolute: **never re-read a closed gate with a better metric -- it earns a NEW pre-registration.**
Recorded as a design fact, not as a proposal.

---

## 5. Standing of the defect

**`DEFECT-twelve-bit-hash-misresolution.md` is ACCEPTED as raised**, subject to the three Sec.2/Sec.3
amendments. Severity **High** is right, and I am sharpening the product statement rather than the
label:

- **Realised harm today:** wrong callsigns rendered in the decode panel and carried into anything
  downstream that logs or relays a decode. A wrong name is loggable; `<...>` is honest.
- **Severe form** (a nonstandard station addressing **PD2FZ** by hash, resolved to somebody else, so
  the QSO answerer never sees the call): exposure in this receive-only corpus is **exactly zero**
  decodes -- an exposure of zero, **not** evidence of absence (HK-021(j)). It is a receive-only
  corpus; the exposure of a station that transmits is a different and unmeasured thing.
- **Not established** (QA's Sec.4 list is correct and I add nothing to it): the split of the joint
  error between the two decoders, corpus-dependence of the rate, and the shape of any correction.

**This document authorises no fix, no policy, and no `src/` change.** A remedy earns its own
pre-registration and a Developer session (HK-011).

---

## 6. Proposed HK-021(u), for the Captain to accept or refuse

> **A descriptive corroboration quoted as a rate must be quoted against the BASE RATE of the same
> statistic in the same corpora, in the same sentence. A rate without its base rate is not evidence,
> and a 100% that sits on a 98.7% null is worse than no number at all -- it reads as decisive and is
> not.**

Fired today, in the Architect's own document as much as in QA's: 92/92 was written up as "strongly
corroborating" on both sides of the handoff, and it is at base rate. The five-minute measurement that
dissolved it is the one HK-018 already tells us to prefer to a paragraph of reasoning.

**HK-021(t)** (a gate's unit population must not be selected on the outcome under test) is still owed
to the Captain from the 13:07Z ruling and is unaffected by this.

---

## 7. My predictions for whatever comes next, recorded BLIND

Recorded now, before any remedy arm exists, in the same discipline the spec imposed on me:

1. **A unique-match rule at today's 4,096 would raise agreement on the measured 243-decode population
   to above 85%** -- moderate confidence. It suppresses the ambiguous half, and the ambiguous half is
   where the wrong names live.
2. **It would also suppress a large minority of names that are currently CORRECT** -- high confidence,
   near-certain arithmetic: only 48.1% of queries are unambiguous, so correct-but-ambiguous names are
   collateral and there will be many of them.
3. **The 1,544 unmeasurable resolved type-4 decodes carry a HIGHER wrong rate than the measured 243**
   -- low confidence, and flagged as low: they skew toward what the reference never decoded at all,
   and I have already been wrong once today about a magnitude on this path.

---

## 8. Queue

- ➡️ **QA:** the three amendments in Sec.2/Sec.3 to `DEFECT-twelve-bit-hash-misresolution.md` and the
  result report. Nothing else -- the arm itself needs no re-run.
- ➡️ **PO / Captain:** two decisions, and they are coupled (Sec.4c) -- (i) does `ARM 2` (the
  enlargement `#define`, 32,768 recommended over 16,384 on load factor) proceed, and (ii) is a 12-bit
  naming remedy worth a pre-registration at all, or is the defect accepted and marked?
- **Held / unaffected:** `OSD-FA-A` still held · `BASE`+`WIDE`/140Hz Developer session per the Captain
  · proposed HK-021(t) and now (u) owed to the Captain.
