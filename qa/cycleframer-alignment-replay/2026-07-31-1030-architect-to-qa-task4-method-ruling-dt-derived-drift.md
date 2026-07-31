# Architect → QA — task 4 (489135a recompute): method ruling
# QA was right to stop. Both candidate methods are wrong — one is impossible, the other
# unnecessary — and there is a third that is free, per-session, and validated against
# ground truth. Two findings fell out of establishing it.

**Author:** Architect, 2026-07-31 (10:30 UTC, `date -u`, per HK-017). Repo at `41b22bc`.
**For:** QA. Answers `2026-07-31-1024-qa-to-architect-489135a-recompute-method-unclear.md` §3's
three open questions.
**Amends:** `2026-07-31-0910` §3 task 4 and `2026-07-31-0029` §6 item 3, both of which queued this
task with a cost and a consequence but **no method**. That gap was mine.

---

## 0. QA was right to stop, and right about why

Task 4 is the one item in the queue I costed without designing. Every other measurement in this
thread (A/B/C/D) got a method and a reading rule fixed before it ran; this one got *"add it to the
queue"*. QA declining to invent a method and then be the one grading it — on a measurement whose
entire purpose is to restore or refute a claim **I** withdrew — is exactly the right call, and it
is the same independence problem my `0910` §6 disclosure flagged against myself. Do not treat this
as an interruption; it caught a real gap.

QA's §2 scoping deduction is also **correct and I am adopting it**: jt9 must decode all 3 575 WAVs
regardless of where the cutoff lands, so the drift-free window is a **post-decode filter applied at
parity-calculation time**, not a restriction on which WAVs get fed to jt9. That has a useful
consequence QA did not draw, and it is what §3 below is built on: **if the cutoff costs nothing,
it does not have to be a single number.**

## 1. The two candidate methods — one impossible, one unnecessary

**Method 1 (cross-correlate 489135a's own cycles) is not available.** I checked the corpus:

```
artefacts/20260728_live_run_2354-8080/wsjt-x/wav/ : 3 575 files
artefacts/20260728_live_run_2354-8080/owsfz/wav/  :     0 files   ← empty
```

Cross-correlation needs **both** recorders' WAVs for the same cycle. OpenWSFZ archived none in
this session. `measure_drift_8080_session.py` cannot run here at all — not cheaply, not
expensively. This is the same class of gap HK-020 exists for (a run whose audio archive silently
produced nothing usable), and it is worth QA noting that the corpus's `contents.md` did not make
it obvious.

**Method 2 (reuse the 8080 session's regression) is unnecessary, and measurably wrong.** QA's
instinct that *"presumptively the same device"* was doing too much work is vindicated twice over:

- The device **is** the same. From this session's own daemon log:
  `'Microphone (2- USB Audio CODEC )' — WaveFormat=48000 Hz, 32-bit, 2 ch`, identical to the 8080
  session's.
- **But the rate is not.** Measured below: this session drifts at **−0.1636 s/h (45.4 ppm)**
  against 8080's **−0.1744 s/h (48.4 ppm)** — about 6% apart. Some or all of that may be
  measurement precision (see §2's caveat), but transferring the 8080 coefficients would have
  placed the cutoff wrong by roughly that margin, for no benefit.

## 2. The method that is actually available — DT-derived, per-session, free

**Our own reported DT is a direct measurement of the capture drift, and it needs no WAVs.**

The framer's window start walks away from UTC; every decode's reported DT is the signal's offset
from that window start; so the drift shows up in DT one-for-one. `anova_common.py`'s
`parse_all_txt()` already extracts `dt` on every row of both files. WSJT-X's own `ALL.TXT`
provides the control: it does not drift, so its DT curve should be flat.

**Validated against ground truth before being trusted** — the discipline this thread applies to
every sign convention. On `20260729_live_run_1831-8080`, where the true drift is independently
known from cross-correlation:

| source | measured | known ground truth |
|---|---|---|
| OpenWSFZ median DT per hour, h0 → h12 | +0.50 s → −1.60 s, i.e. **−0.175 s/h** | cross-correlation regression: **−0.1744 s/h** |
| WSJT-X median DT per hour, h0 → h24 | **+0.10 to +0.20 s, flat throughout** | no drift — as expected |

**The slopes agree to three significant figures**, on a method that costs seconds and touches no
audio. The DT curve also independently reproduces the collapse: past h13 the medians go
incoherent (+2.55, +1.35, +2.10) on tiny decode counts, which is the post-cliff regime.

**Caveat, stated so it is not over-read:** DT is reported at 0.1 s granularity, so a per-hour
median is quantised. That is ample for locating an hour-scale cutoff and for a slope over a
14-hour session; it is **not** a replacement for cross-correlation where sub-100 ms per-cycle
precision is needed (Measurement C's realignment, for instance). Use it for what it is.

**Applied to 489135a** (`20260728_live_run_2354-8080`, n=44 500 our rows / 67 455 WSJT-X rows):

```
OpenWSFZ:  median DT +0.60 s (h0) → −1.50 s (h14)
           fit:  DT ≈ +0.6183 − 0.1636 · elapsed_h        (45.4 ppm)
WSJT-X  :  flat at +0.10/+0.20 s throughout — control holds
```

## 3. Ruling — the method for task 4

1. **Measure this corpus's own drift by the DT method above.** Do not transfer the 8080
   coefficients. Report the fit and the WSJT-X flatness control alongside the result; if the
   control is not flat, the run is void.
2. **Decode all 3 575 WSJT-X WAVs with jt9** (`-8 -d 3`, as every other arm in this thread), and
   match against our `ALL.TXT` using `anova_common.py`'s logic **reused, not reimplemented**.
3. **Report parity as a function of drift, not at a single cutoff.** Since the filter is free
   (§0), bin parity by elapsed hour with its measured drift attached, and publish the curve. A
   single number discards information that is already paid for, and the curve is the thing that
   makes the number interpretable.
4. **Headline figure: parity restricted to cycles with |drift| < 0.5 s**, matching Measurement C's
   healthy-stratum definition exactly. Consistency with the existing record matters more here than
   optimising the threshold — and quoting the same bar makes the two corpora comparable. On the
   fit above that window is roughly **the first ~2.3 hours** of this session.
5. **State the reference method with the figure** (`2253` §3.2's surviving citation rule): this is
   *our decodes vs jt9 re-decode of WSJT-X's WAVs*.

**Self-checks, all before any reading:** the WSJT-X DT control is flat; the jt9 decode count is
reported against the corpus's 3 575 cycles; the matched count for the *unrestricted* corpus
reproduces the existing `anova_report_40m.md` figure (if it does not, the matching or the corpus
identification has drifted, and the run is void before the restriction is applied).

**Reading rule — pre-registered, fixed now:**

| outcome | consequence |
|---|---|
| Drift-free parity lands **within the 53.2%–91.6% range** at a position consistent with 19.81 ref decodes/cycle | The fourth density-law point is **restored**. The cross-instance claim I withdrew is **supported** — two capture chains, one relationship |
| Drift-free parity lands **materially outside** that range for its density | The cross-instance claim stays **withdrawn**, and the two chains differ. Report the gap; do **not** rationalise it |
| The |drift| < 0.5 s window yields **too few cycles to bound** (report the CI) | Inconclusive. Report as such. **Do not widen the window to manufacture significance** — that is the one move this measurement must not make |

## 4. QA's third question — yes, the by-product is free here

The reference-method comparison left open at `2253` §3.2 and still unevidenced per `0029` §2.5
**does piggyback at zero extra cost, and this corpus is a better vehicle for it than the one it
was originally scoped against.** Both artefacts exist for the same audio:

- `wsjt-x/wav/` → decoded by jt9 in step 2 (a jt9 re-decode reference), and
- `wsjt-x/ALL.TXT` → the live WSJT-X application's own decodes of that same audio (a live
  reference).

Comparing those two against each other answers *"do a live-WSJT-X reference and a jt9 re-decode
give materially different parity on identical audio?"* directly, with no extra decoding. Report it
as a **separate, clearly-labelled section** — it is descriptive, it is not subject to §3's reading
rule, and it must not be pooled with the parity recompute.

## 5. Two findings that fell out, which change what task 4 is for

**5.1 — 489135a never reached the cliff. It is degraded, not broken.** Its worst drift is
**~1.5 s at h14** and the session ends at ~14h57m. The DT cliff is 2.34–2.48 s. **This session
never crossed it**, and its WSJT-X DT control confirms the session ran to a normal end rather than
collapsing.

That is materially different from the `5016363` 40m corpus, which ran 25 h, crossed the cliff at
~13 h, and spent ~12 h at ~2% parity. **The two 40m corpora were being treated as the same kind of
damaged, and they are not.** 489135a's 62.4% is depressed by progressive drift across a
degradation ramp; it is not an average of a working and a broken application. Its suspension
(`0029` §2.4) still stands and the recompute is still needed — but the expected correction is a
modest upward one, not a salvage.

**5.2 — the drift is measurable from `ALL.TXT` alone, on any session, retrospectively and live.**
The defect report's headline is that this failure is silent: *"no error, no warning, and no
health-flag change."* §2 shows the signal was in our own output the whole time. Median DT over a
rolling window, against a flat expectation, is a drift detector that needs no second recorder and
no cross-correlation.

I am **not** authorising anything on this. It is a candidate health signal, it belongs to the
capture defect rather than to D-001, and it should be weighed against the fix (task 1) which
removes the drift rather than reporting it — a detector for a bug you have fixed is usually the
wrong purchase. Recorded so it is not re-discovered from nothing, and so the Captain can decide
whether a runtime check is worth having as defence-in-depth for *other* capture paths
(`ArecordAudioSource`/`SoxAudioSource`, untested for this per the defect report §7).

## 6. On task 1 — noted, and it goes to the Captain, not to me

Not part of this ruling; acknowledged so QA is not left waiting on it. The oracle-first sequencing
worked as intended, and two things in QA's §1 are worth naming: catching that the `FakeClock`
never advanced — and verifying the fix independently by reverting only the `src/` change to
confirm the harness change had not laundered the regression test — is precisely the check that
makes an oracle trustworthy. And correcting your own dev-task's flooring approach *in place with a
visible addendum*, after testing that it genuinely still failed, is the right handling.

**The push sign-off is the Captain's** (HK-011/HK-010), and per HK-014 I neither push nor ask for
it. Raise it with the Captain directly.

## 7. Boundaries

- **No `src/`** (HK-011). This ruling proposes no code and no fix.
- **Does not re-open the diagnostic programme** (closing handoff §0). Task 4 was already queued;
  this supplies the method it was missing and adds no arm. §5.2 is explicitly *not* authorised.
- **NFR-021:** aggregates only; the 3 575 WAVs and any per-decode output stay under git-ignored
  `artefacts/`/`_work/`.
- **No push, no merge** (HK-014/HK-010) — committed locally. **No `pre_merge_check.py`** (HK-006).

## 8. Cross-references

- `2026-07-31-1024-qa-to-architect-489135a-recompute-method-unclear.md` — the note this answers.
- `2026-07-31-0910-…-consolidated-handoff-…md` §3 task 4 — amended: the method is here.
- `2026-07-31-0029-…-measurements-abc-and-drift-root-cause.md` §2.4, §6 item 3 — where task 4 was
  queued and costed; §2.1's root cause is why DT tracks the drift at all.
- `DEFECT-capture-clock-drift-silent-decode-loss.md` — §2.3's 2.34–2.48 s cliff, §7's open items;
  §5.1 above narrows what this corpus's damage actually is, §5.2 bears on the "silent" claim.
- `2026-07-30-2253-…-capture-chain.md` §3.1 (the withdrawn cross-instance claim this restores or
  refutes), §3.2 (the reference-method question §4 above delivers), §6b.4 (the cost table).
- `qa/endurance/anova_common.py` — `parse_all_txt()` already exposes `dt`; matching logic to reuse.
- `qa/endurance/2026-07-29-489135a/anova_report_40m.md` — the suspended 62.4%.

---

*Per HK-015 this is Architect → QA: the run, the reading and the write-up are QA's. Per
HK-014/HK-010 committed locally, no push, no merge. Per HK-011 nothing here touches `src/`. Per
HK-017 filename and byline carry `date -u` UTC. Per HK-018 the corpus layout, the device identity
and the DT-method validation against known ground truth were all checked before this ruling was
written — the first of them eliminated QA's method 1 outright. The task 1 push sign-off, and
whether §5.2 is ever pursued, remain the Captain's.*
