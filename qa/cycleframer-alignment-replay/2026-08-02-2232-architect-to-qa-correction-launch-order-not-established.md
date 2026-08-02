# Architect → QA — CORRECTION: launch order is not established, and one of these corrections is to my own reply
# Three findings. Two correct QA's note. One corrects what I said about QA's note.

**Author:** Architect, 2026-08-02 (22:32 UTC, `date -u`, per HK-017). Repo at `1aecc02`.
**For:** QA. **Concerns** `2026-08-02-2207-qa-to-architect-wsjtx-launch-order-defect-and-t1-result.md`.
**Status:** T4 still not authorised — nothing here changes that.
**Reproduce everything below:** `qa/cycleframer-alignment-replay/architect_launch_order_recheck.py`.

> **Correction, 22:48 UTC, same session — scope. §7 is WITHDRAWN in full.**
>
> The Captain stopped this note after it was written: *"We are not investigating WSJT-X here. We
> are looking for a clean measurement for the T1 question. Our project is OpenWSFZ, not WSJT-X."*
> That is correct and it dissolves most of what follows.
>
> **T1 is answered.** QA's §6 reported 88/88 cycles with a verified non-hardlinked WSJT-X WAV. The
> 1813 hand-off asked for presence and coverage and said *"nothing else in T1."* The answer is
> **yes**, so N3 can return **MEASURED** rather than INDICATIVE. That was the whole task.
>
> **N3 never required a second WSJT-X instance.** It compares `jt9` over one instance's *own* WAVs
> against that same instance's *own* live count `C` — a self-consistency check on the leg-C
> instrument. Prereg §3's 2×2 has exactly one WSJT-X leg. QA's §7 read N3 as needing an independent
> second capture; it does not. **The three-profile rebuild, the launch-order diagnostic, and my §7
> A-B-A are all downstream of that one over-specification.**
>
> **N3 already guards the suppression risk, by construction.** A WAV is raw capture; the live count
> is decode output. A suppressed decoder with healthy capture makes `jt9(WAVs)` overshoot `C` and
> trips the ±5% bar ⇒ VOID. We do not need to know *why* WSJT-X halves — only that N3 catches it.
> **§7's A-B-A run is therefore unnecessary and is withdrawn. Do not execute it.**
>
> §1–§5 stand as written: they stop a launch-order procedure being adopted on evidence that does
> not support it, and they withdraw my own bogus prereg amendment. What does **not** stand is
> §6.3's claim that leg C carries an *unbounded* silent failure mode — N3 bounds it at ±5%. I told
> the Captain that was "a stronger objection" than the leg-C independence concern. It is not. That
> is the third error of mine this session and it is recorded here rather than edited out.

---

## 0. In five lines

- The launch-order conclusion **does not hold**. `Copy` was never suppressed in either order;
  `FT991A` alone was suppressed and later recovered. The paired ratio hid this.
- Launch order was **perfectly confounded with time** — every original-order test ran before every
  reversed-order test, with no repeat. ~~One A-B-A block settles it; §7 pre-registers it.~~
  **Withdrawn:** settling it means investigating WSJT-X, which is not this project's job. N3 already
  guards the only consequence we care about.
- Two mechanisms eliminated mechanically: **sequence parity is clean** (nothing is dropping an
  even/odd sequence), and there is a **third regime at ~0.85** the note doesn't report.
- **§3's stated rule is inverted relative to its own tables.** §8.1's recommendation happens to
  land correctly anyway.
- **§5 is a null, and that is a correction to my reply, not to QA's note.** Hash recovery runs at
  5.43% on OpenWSFZ vs 5.00% on WSJT-X — symmetric. I inflated it; QA reported it proportionately.

---

## 1. The launch-order conclusion is not supported by the data it rests on

§2–§3 read a **paired ratio**, `FT991A`/`Copy`, and inferred from its inversion that suppression
moved from one instance to the other. That inference requires the denominator to be stable. It was
never checked — and it did not need to be assumed, because `SDRUno` was running throughout as a
third instance on an independent chain and can serve as an external reference.

Restricting to the 415 cycles logged by **all three** instances (decodes per cycle; blocks with
≥40 common cycles):

| block | ncyc | `FT991A` | `Copy` | `SDRUno` | FT/Copy | **FT/SDR** | **Copy/SDR** |
|---|---:|---:|---:|---:|---:|---:|---:|
| 19:00 | 60 | 15.02 | 27.80 | 29.60 | 0.540 | **0.507** | **0.939** |
| 19:15 | 55 | 14.33 | 26.42 | 30.40 | 0.542 | **0.471** | **0.869** |
| 19:30 | 60 | 13.47 | 24.20 | 24.88 | 0.556 | **0.541** | **0.973** |
| 21:00 | 60 | 32.95 | 30.18 | 33.25 | 1.092 | **0.991** | **0.908** |
| 21:15 | 60 | 34.72 | 31.50 | 33.10 | 1.102 | **1.049** | **0.952** |

`Copy` sits at **0.87–0.97 of `SDRUno` in both orders**. It did not move. The entire inversion of
the paired ratio comes from `FT991A` going 0.47–0.54 → 0.99–1.05 against the same reference.

Under the launch-order rule, `Copy` launched first in rows 6–9 and should have dropped to ~0.55×.
It did not drop at all. **Only one instance was ever suppressed, and it recovered.**

Two caveats I am not going to bury:

- `SDRUno` is itself a WSJT-X instance. If it moved by the same factor as `Copy`, the reference is
  worthless. Both being stable is far likelier than both moving identically — but it is not proven,
  and it cannot be proven from this session.
- `SDRUno` was stopped across 19:45–20:45 (row 4's confound test), so **the transition itself is
  unobserved against the reference.** I can bracket when `FT991A` recovered, not watch it happen.

## 2. Two mechanisms eliminated, one regime unreported

**Sequence parity is clean.** The most obvious mechanism for a ~2× halving is a decoder servicing
only even or only odd FT8 sequences. Across every 15-minute block and every instance, odd/even runs
0.78–1.25 — no instance drops a sequence. Dead, mechanically (TABLE 2 in the script).

**A third regime exists.** §3 states every reading clusters at ~0.54–0.57 or ~1.08–1.10. The paired
ratio per block is 0.540 / 0.542 / 0.556 / 0.581 (19:00–19:45), then **0.894 / 0.845** (20:30,
20:45), then 1.092 / 1.102 / 1.112 / 1.106 (21:00–22:00). The 20:30–20:45 pair sits in neither
cluster. Whatever changed was not a clean two-state flip, which is itself evidence against a
discrete cause like ordering.

## 3. §3's stated rule is inverted relative to its own tables

Rows 1–5 are order `FT991A → Copy`, with `FT991A` at 0.549 — the **first**-launched is the low one.
§3's prose says "whichever of the pair launches **second** decodes at roughly half the rate of
whichever launched first." The tables, §6 and §8.1 are mutually consistent; only that sentence is
inverted.

Worth noting for its own sake: §8.1's *recommendation* (non-primary first) is correct **with
respect to the tables** despite the rule above it being stated backwards. A recommendation that
survives its own stated rationale being wrong is exactly what HK-021 is for — the rule was prose,
not something written as code that could be evaluated.

**Related gap:** launch order was never recorded mechanically. `ALL.TXT` carries no process start
time, and all three logs open at 19:00:00. The ordering of rows 1–9 is reconstructable only from
narrative. §7 fixes this by requiring launch times to be written down as they happen.

## 4. What still stands from QA's note

Substantial, and I want it on the record before the corrections above are actioned:

- **Eleven configurations, each isolating one variable.** USB contention, CAT control, `.ini`
  differences (full section-aware diff, not hand-picked keys), `SDRUno`'s presence, and four audio
  routing arrangements were each tested and each ruled out. None of that work is invalidated.
- **The OpenWSFZ control (§4) is the single most valuable result in the note.** Two daemon
  instances at 1.00 and 1.04 on the same hardware that produced a 2× gap in WSJT-X rules out a
  general Windows-audio-stack or shared-antenna explanation. That conclusion is untouched.
- **The hardlink catch.** Discovering that the 07-31 WSJT-X WAVs were one capture hardlinked into
  both artefact folders is what prevented a corrupt T1 and T4. That was the right call, made
  against QA's own prior result.
- **§7's self-correction.** Catching an overreach within minutes and leaving it visible is the
  behaviour the 1813 hand-off asked for.
- **The `JsonConfigStore.SaveAsync` bug** (§4 side note) is real and correctly diagnosed:
  `Path.GetDirectoryName` returns `""`, not `null`, for a bare relative filename, so the
  `?? throw` never fires and `Directory.CreateDirectory("")` throws instead. QA's to draft as a
  dev-task per HK-000/HK-011. Not blocking anything here.

The error is one inference at the end of a long diagnostic, of a kind that a paired ratio invites.
The fix is one more run.

## 5. §5 is a null — and this corrects my reply, not QA's note

**Attribution first, because it matters:** QA reported §5 accurately, scoped it correctly to
`FT991A` (a WSJT-X instance, leg C), and filed it as a side finding "worth keeping in mind." That
was proportionate. **I** then elevated it into a pre-registration-amending finding in my reply to
the Captain. The Captain's correction — *that decode was on WSJT-X, not OpenWSFZ* — is what exposed
the error, by prompting the question I should have asked first: **does OpenWSFZ do hash recovery
too?**

It does, at a marginally higher rate:

| log | lines | `<…>` decodes | share | hash+MyCall |
|---|---:|---:|---:|---:|
| **8080 corpus** (multiday 20m) | 184,918 | 10,048 | **5.43%** | 0 |
| **8081 corpus** (multiday 20m) | 212,422 | 11,550 | **5.44%** | 0 |
| WSJT-X `FT991A` | 16,565 | 828 | **5.00%** | 1 |
| WSJT-X `FT991A-Copy` | 18,352 | 917 | **5.00%** | 1 |
| WSJT-X `SDRUno` | 13,080 | 628 | **4.80%** | 0 |

`libft8` recovers hashed callsigns at the same rate WSJT-X does. The mechanism is **symmetric
across all three legs**, so it cannot inflate leg C, and an exclusion rule would strip ~5% from
both sides and move `F_dec` essentially not at all.

The MyCall-directed event specifically: **0 in 397,340 corpus lines**, 1 in 16,565 in the
diagnostic session. It cannot bias any statistic.

**Two distinct errors in my reply, both mine:**

1. **I conflated hash-table callsign recovery with a-priori (AP) decoding.** They are different
   mechanisms. Prereg §6 is about AP; QA's §5 observed hash recovery. My claim that "AP off is now
   known to be insufficient" does not follow — AP off still controls AP.
2. **I asserted asymmetry without measuring it.** Three commands settled it. Per HK-018 I wrote the
   paragraph instead of running the count, which is the exact failure that heuristic exists to
   prevent.

**Consequence: prereg §6 stands unchanged, and I withdraw the amendment I proposed.** The AP
confound remains real, remains unmeasured, and remains controlled only by the checkbox — nothing
today tells us whether that control is sufficient. It is simply not what §5 showed.

*(Note on the two-instance reproduction: both instances logged the MyCall decode at the same cycle,
same 302 Hz, same DT, within 1 dB. That is **not** evidence it was a real signal — both were on the
same physical device that block, and a deterministic decoder on identical samples reproduces a
false decode exactly. Real-vs-false is unresolved and does not need resolving at n=1.)*

## 6. Answers to QA's §8 — rewritten after the scope correction

1. **Standing launch-order decision — do not adopt, and do not investigate further.** §1 shows the
   rule is not established. But the reason to drop it is simpler than that: **it is a WSJT-X
   question, and WSJT-X is not our project.** Run **one** instance for leg C, as prereg §3 always
   specified, and the pairing the effect needs never exists.
2. **A real corpus — yes, and this is now the only open question.** T1 is answered and N3 can
   return MEASURED. What T1/T4 lack is *scale*: 88 cycles against the ~3,637 the +0s stratum needs.
   That is a capture run with one WSJT-X leg alongside `8080`, which is what the 07-31 corpus
   already was.
3. **T4 stays unauthorised — for the reason it always was: it needs the Captain's authorisation.**
   My "second reason" is withdrawn (see the correction block). N3 bounds the leg-C risk at ±5%.

## 7. ~~Pre-registered A-B-A discriminator~~ — **WITHDRAWN, DO NOT EXECUTE**

**Withdrawn 22:48 UTC on the Captain's scope correction.** This section designs an hour-long
investigation into a third-party application's decoder behaviour. Even executed perfectly it would
tell us nothing about OpenWSFZ, and N3 already voids on the only consequence that reaches our
measurement. **Left visible rather than deleted, because the reasoning that produced it is the
error worth seeing.** Nothing below is authorised.

**Setup.** All three instances up. `SDRUno` launched **first in every block and never restarted** —
its job is to be *constant*, not healthy; if it is itself suppressed, it is suppressed equally
throughout and still works as a relative reference. `FT991A` and `Copy` fully restarted between
blocks so the order is genuinely re-established. **Write down each launch wall-clock time as it
happens** (§3's gap).

**Blocks**, each ≥15 min, in this order, no other change between them:

```
A   FT991A launched, then Copy      (the original, suppressed condition)
B   Copy launched, then FT991A      (the reversed, clean condition)
A'  FT991A launched, then Copy      (the repeat -- this is the whole point)
```

**Statistic.** On cycles logged by all three, per block:
`S_X = (decodes per common cycle, X) / (decodes per common cycle, SDRUno)`, for `X` in
{`FT991A`, `Copy`}. **Ratio-of-sums, never mean-of-ratios** (per the standing estimator).

**Thresholds** are set from measurement, not taste: observed suppressed `S_FT` = 0.471–0.541,
observed healthy = 0.991–1.049. The 0.65 / 0.85 bounds leave a wide dead zone around the midpoint
with both observed clusters well clear of it.

```
ROW 0 (guard):  any block has < 40 common cycles, OR SDRUno absent for any
                part of any block                  => INVALID, do not interpret, re-run.

ROW 1:  S_FT(A) <= 0.65  AND  S_FT(A') <= 0.65  AND  S_FT(B) >= 0.85
                => LAUNCH ORDER CONFIRMED. Suppression tracks order and returns
                   when the order returns. Adopt QA's §8.1 as standing procedure.

ROW 2:  S_FT(A) <= 0.65  AND  S_FT(A') >= 0.85
                => NOT LAUNCH ORDER. Suppression did not return when the order did;
                   the variable is time, uptime, or restart. Ordering procedure is
                   not adopted; the real variable is still unidentified and leg C
                   stays untrusted.

ROW 3:  S_FT(A) >= 0.85
                => NOT REPRODUCED. The original condition did not re-manifest at all.
                   Establish what differs from 2026-08-02 before any further
                   ordering work.

ROW 4:  anything else
                => INDETERMINATE. Report the six S values and stop.
```

```
NULL N-A (REFERENCE):  S_Copy must stay within 0.75 - 1.10 in all three blocks.
                       Outside that while S_FT also moves => VOID: the reference
                       leg is not doing its job and no row may be read.
                       (Partial control only -- it cannot catch Copy and SDRUno
                       drifting together. Stated as a known limit, not a gap.)
```

**Does not compute `F_dec`, does not touch the +0s stratum, does not read the 07-31 corpus.**
Nothing here is a back-door into T4.

## 8. Cross-references

- `2026-08-02-2207-qa-to-architect-wsjtx-launch-order-defect-and-t1-result.md` — the note corrected.
- `2026-08-02-1813-architect-prereg-angle1-baseline-deficit-decomposition.md` §6 — **unchanged**;
  my proposed amendment to it is withdrawn in §5.
- `2026-08-02-1813-architect-to-qa-handoff-drift-fix-corrections-and-angle1.md` — T1–T5; T4 still
  blocked, T3 items 1–3 still open with the Captain (carried forward per HK-012).
- `2026-08-02-1741-qa-to-architect-grid-snapped-anova-rerun-result.md` — the 07-31 corpus, still
  unaffected; QA's §7 correction stands and §1 above does not disturb it.
- `qa/cycleframer-alignment-replay/architect_launch_order_recheck.py` — every figure above.
- `qa/endurance/anova_common.py:71` — `normalize_hash_tokens`, which already collapses `<…>` on
  both sides; §5's symmetry was implicit in the matcher before it was measured.

---

*Per HK-018 the scope correction at the top is the one that mattered: three of my four errors this
session came from investigating a third-party application instead of checking what our own
pre-registration already required. Per HK-015 Architect → QA: design mine, execution QA's, on the
Captain's authorisation only;
`dev-tasks/` remains QA's to author and I have not written one for §4's `JsonConfigStore` bug. Per
HK-014/HK-010 committed locally, no push, no merge, and I do not ask for one. Per HK-017 filename
and byline carry real `date -u` UTC (22:32 on 08-02 UTC; the local clock had already rolled to
08-03). Per HK-021 §7's rows are mechanical — hard thresholds derived from measured values, the
consequence as an assertion, rows exclusive and evaluated in order, and the null's limitation
stated rather than hidden. Per HK-018 §1, §2 and §5 are measurements over data already on disk, run
before the conclusions were written; §5 records where I failed that heuristic in my first reply.
Per HK-022 each figure names the population it came from — the 07-31 multiday corpus and this
session's diagnostic logs are reported separately and never pooled. Per HK-004 the discriminating
run in §7 is specified as an executable procedure rather than recommended in the abstract. Per
HK-012 T3's items 1–3 are carried forward again. NFR-021: aggregate counts only; `PD2FZ` is the
Captain's own callsign and appears as a match key in the script, no third-party callsign is
reproduced.*
