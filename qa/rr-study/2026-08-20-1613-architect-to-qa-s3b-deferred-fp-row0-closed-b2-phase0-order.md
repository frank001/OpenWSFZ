# ARCHITECT -> QA — S3b DEFERRED. FP ROW 0 closed mechanically. B2 Phase 0 is the live item.

**UTC:** 2026-08-20 16:13Z · Architect · Captain's ruling this session: *"go with the better order."*

**Supersedes the sequencing half of `2026-08-19-1840-architect-to-qa-gh-3-111-route-b2-authorised.md`
(the "S3b instrument first" ordering). Route B2's authorisation itself is UNCHANGED.**

---

## 0. The order, as ruled

1. FP ROW 0 check against G4's existing artefacts — **DONE in this document, Sec.1. Closed.**
2. **QA now: B2 Phase 0** — OpenSpec change + `dev-tasks/*.md` + harness + population, then run
   ROW 0c/0d on the current build, then **STOP** (HK-011).
3. **S3b full sweep: HELD.** Release condition in Sec.3. Not cancelled, not deprioritised — deferred
   until it sizes something that exists.

🔴 **Why the order changed, stated plainly because it corrects me.** My 18:40Z justification for
running S3b first was that Route B2 *"cannot be sized against a bench that mislabels its own truth."*
**That argument does not reach Phase 1.** Phase 1's gate runs on the **P-LIVE Stage 2 population**
(live replay, 3,916 clusters, `f_net` over reference-decoded/we-missed) — see the 18:50Z spec Sec.3.
The S3/S3b synth bench does not appear until **Phase 2**. So S3b is a prerequisite for Phase 2/3 and
I presented it as a prerequisite for Phase 1. It is not. Phase 1 may also return ROW 3 and kill limb
2 outright, in which case a 4.2 h hardware-committed sweep would have sized nothing.

---

## 1. FP ROW 0 — CLOSED. The hazard I raised is RETIRED.

**What I raised (this session, to the Captain):** G4 observed 8/100 spurious OpenWSFZ decodes at the
noise floor. S3b's entire response is a decode-rate attribute over ~2,000 cycles; at ~8%/cycle that
is ~160 spurious decodes landing hardest at the tail parts where the true rate is low, biasing the
measured boundary **outward**. I flagged it explicitly as *reasoning, not a measurement*.

**Measured now, against `qa/rr-study/harness/matcher.py` (HK-018 — a five-minute measurement beats a
paragraph of reasoning):**

| fact | evidence |
|---|---|
| Match predicate is a **conjunction** | `matcher.py:172` — `_text_matches(...) and _freq_matches(...)` |
| Text limb is **exact** equality | `matcher.py:119-121` — case-sensitive, whitespace-normalised `==` |
| Freq limb is **+/- 4.0 Hz** of truth | `matcher.py:31,125` — `FREQ_TOLERANCE_HZ = 4.0`, truth `base_freq_hz = 1500` |
| **DT is never used in matching** | recorded in output rows only (`:201,204,221,224,241,244`); no DT term in the predicate |

A spurious decode must therefore reproduce `CQ Q1ABC FN42` **exactly** *and* land within 4 Hz of
1500 Hz. G4's own 8 spurious decodes were at **SNR -25..-29 dB, frequencies away from 1500 Hz**, and
FT8 payloads are CRC-14 protected. **The response variable is not contaminated. ROW 0 passes; do not
carry this hazard into the S3b pre-registration.**

✅ **A design strength worth pinning so nobody "fixes" it later:** because DT is absent from the
predicate, S3b's attribute response is **DT-agnostic** — a negative-DT part cannot be scored a miss
merely because reported DT collapses to ~0. That is correct for an attribute study and it must stay
that way. Any future change adding a DT term to `matcher.py` **breaks S3b by construction.**

---

## 2. 🔴 NEW, and sharper than the one it replaces: the SLOT-ATTRIBUTION hazard

Grounding the above turned up a real threat to S3b that no gate so far has tested.

`matcher.py:110-116,155` buckets candidate decodes by **normalised UTC slot** (`_build_slot_buckets`),
and a truth row can only match candidates in **its own** bucket (`buckets.get(cycle_dt, [])`).

S3b renders genuinely early audio — up to **-2.7 s before the slot boundary** (`extended=True`, C1/C2).
**If either decoder attributes an early-starting signal to the PREVIOUS slot, the truth row scores a
MISS and the decode scores an FP** — a bookkeeping artefact that grows monotonically with `|dt|`,
i.e. **exactly along the sweep axis**, and which would present as a decode-rate collapse that looks
like a capability boundary.

🛑 **Nothing run so far can detect this:**

| gate | why it cannot see it |
|---|---|
| G1/G2 | offline placement only, no decoder, no slots |
| G3 | `jt9`, one file per invocation — **no slot attribution exists** in that path |
| G4 | `dt = 0` only — **zero early offset by construction** |

⚠️ This is compounded by the known **+0.65 s production time-origin offset** (`AO1`; `D1`: `K_ref` =
`K_ours` = +0.650 s), which shifts our framing relative to the slot boundary in the same direction
the sweep travels. **I am not asserting the two combine — I have not measured it. That is the point.**

**Binding on any future S3b pre-registration: a slot-attribution ROW 0 is MANDATORY.** It must be
mechanical per HK-021, and per HK-025 QA may refuse the spec if it is absent. Sketch, not final text:
for each part, assert that the decode matched to truth row `t` carries the **same** normalised slot as
`t`, reported per part; bar = 100% at `dt = 0`, and the row **VOIDS** the run if attribution slips at
any part. It must be **two-sided** (HK-021(n)) — attribution slipping early is as fatal as late.

🔴 **Do not draft this now.** It is recorded here so it is not re-derived from scratch when S3b is
armed, and so the sweep is not run without it.

---

## 3. S3b — hold, and the release condition

**HELD. Not cancelled.** All 10 parts stay in `s3b-dt-boundary.json`; the 100-trial floor stays
(`1.96*SE ~= 9.8 pp` at p=0.5 — mechanically required, not a preference). The `requires_extended_dt`
re-grid ruling (option b) stands and is unaffected.

**Released when B2 Phase 1 returns ROW 1 or ROW 2** — at which point Phase 2 is in view, the bench is
load-bearing, and the spec's reserved trade-off (*"cut PARTS, not TRIALS ... bring me the tradeoff"*)
can be decided with Phase 1's answer in hand instead of blind.

**If Phase 1 returns ROW 3**, S3b is re-examined on its own merits as a product measurement, not as
B2 sizing — it would still be the only decode-rate-vs-early-offset curve we have, with WSJT-X as a
same-audio contrast. That is a Captain call, not an automatic cancellation.

⚠️ **Standing correction to the board's own framing:** after G3 + G4, calling the S3b sweep
*"instrument repair"* is **STALE**. Placement is sample-exact (G1/G2), the audio decodes on the
reference across the full grid (G3), and the live chain works at `dt=0` (G4). What remains is a
**product capability measurement**. I wrote the "instrument repair, not gap closure" line on 08-19
and it must not be quoted forward without this correction.

---

## 4. QA's live item — B2 Phase 0

Per the 18:50Z spec Sec.5, unchanged by this document:

- Author the OpenSpec change (`r2-coherent-llr-instrument` or similar), following
  `r1-sync-refiner-instrument-validation`'s shape — the right precedent, and it worked.
- Draft the `dev-tasks/*.md` (HK-000/HK-015 — QA's to author, not mine).
- Build the measurement harness; re-derive the population. 🔴 **Report CLUSTER counts, not row
  counts**, and **check what any `limit=` argument does before reusing a population helper** —
  `compute_matched_hit_control(cycles, limit=N)` TRUNCATES in file order (HK-021(i)).
- Run **ROW 0c** (sign unit test, two-sided) and **ROW 0d** (`ber_grid` reproduces Stage 2's median
  31.03% within 1.0 pp) against the **current** build. Both are testable before any native code exists.
- **Then STOP.** No `src/` change. Phase 1 needs a Captain-opened Developer session (HK-011); nothing
  here authorises it.

⚠️ **HK-025 stands: QA may refuse this spec** if any ROW 0 fails the two-branch test. Please actually
run that check — several recent defects were in my specs, not in execution.

---

## 5. What I got wrong, on the record

1. **The 18:40Z ordering rationale was overstated** (Sec.0). S3b gates Phase 2/3, not Phase 1. The
   Captain had to ask *"what does the S3b sweep give us?"* to surface it.
2. **I raised the FP hazard as a blocker-shaped concern and it was not one** (Sec.1). I did label it
   reasoning-not-measurement, but HK-018 says measure first — I should have checked `matcher.py`
   before raising it, not after.

Both were caught cheaply. The slot-attribution hazard (Sec.2) is the thing that would actually have
corrupted the sweep, and it surfaced only because the first one was checked in the code.
