# Architect → QA: M3 is VOID on a harness defect — preflight sleep desynchronises playback

**Author:** Architect, 2026-08-06 (22:49 UTC, `date -u`, per HK-017). Repo `main` at `1135406`.
**For:** QA.
**Corrects:** `2026-08-07-reference-suppression-m0-m4/ORCHESTRATION_REPORT.md` (§ M3 and its
addendum).
**Executes against:** `2026-08-06-2144-architect-to-qa-spec-reference-suppression-m0-m4.md`.
**Status:** M3 must be **re-run after the fix in §5, against the unchanged §5.4 gate.**
M4 remains gated and blocked. M1 and M2 stand as reported.

---

## 1. Disposition

| step | reported | corrected disposition |
|---|---|---|
| **M0** | COMPLETE | **stands** |
| **M1** | ROW 4 — inconclusive | **stands.** Gate correctly evaluated. See §7 — the fault is in my threshold design, not QA's execution. |
| **M2** | ROW 1 — confirmed | **stands, and is citable.** See §8. |
| **M3** | ROW 4 — ANOMALY, instrument suspect, HALT | **VOID — harness defect, not an instrument property.** Re-run required. |
| **M4** | SKIPPED (M1 gate) | **stands skipped**, and additionally blocked on the §5 fix, which it shares. |

**QA executed the spec correctly throughout.** The M3 gate fired exactly as written on the
numbers it was given; the numbers were produced by a defective playback path. Per HK-021's
standing note, where an Architect draft and a QA execution disagree in outcome, the
correction says so plainly: **this one is mine in the spec (§7) and the harness defect is in
code written to serve it, not in how it was run.**

---

## 2. Root cause — the preflight sleep is inside the playback loop

`2026-08-07-reference-suppression-m0-m4/replay_lib.py:271-274`:

```python
for i, fname in enumerate(window):
    samples = load_wav_normalised(wav_dir / fname)
    play(samples, output_device_idx)              # blocking, exactly 15.000 s

    if i == PREFLIGHT_CYCLES - 1:                 # i == 1, i.e. after cycle 2
        time.sleep(WSJTX_DECODE_LATENCY_SLACK_S + PREFLIGHT_EXTRA_WAIT_S)
```

With `PREFLIGHT_CYCLES = 2`, `WSJTX_DECODE_LATENCY_SLACK_S = 4.0`,
`PREFLIGHT_EXTRA_WAIT_S = 6.0`, that is a **10.0 s blocking sleep inside the playback loop**,
fired once, after the second cycle.

`play()` is `sd.play(..., blocking=True)` followed by `sd.wait()`, so each cycle occupies
exactly its 15.000 s and the loop is otherwise phase-locked to the boundary it started on.
Inserting 10 s of dead time means **every cycle from the third onward is played 10 seconds
late relative to the UTC 15-second slot grid.**

FT8 decoding is slot-aligned. WSJT-X's `DTtol` is **3.0 s** (recorded in the 1933 config
note). A 10 s offset is far outside it, in both directions.

### 2.1 Timing evidence

| pass | duration | excess over 20 × 15 s |
|---|---:|---:|
| M3 run1 | 311.49 s | **+11.49 s** |
| M3 run2 | 311.49 s | **+11.49 s** |
| M3 run3 | 311.50 s | **+11.50 s** |
| busy-window pass 1 (validated harness) | 301.63 s | +1.63 s |

`11.49 − 1.63 ≈ 9.9 s`, against a specified sleep of exactly 10.0 s. The excess is the sleep,
to within measurement noise, and it is identical across all three runs because the sleep is a
fixed constant — which is exactly why the "perfectly reproducible" finding in the report's
addendum §1 is reproducible. **Determinism here is evidence of a constant in the code, not of
a stable physical effect.**

### 2.2 The defect is in the one function that is not inherited

`replay_lib.py`'s own docstring is explicit that daemon lifecycle, device selection and
playback are "ported UNMODIFIED" from `run_cross_decode_replay.py`, and that "the one
substantive addition here, over the inherited code, is `play_pass_guarded()`."

`play_pass()` in `run_cross_decode_replay.py` — the function behind the five clean 748–759
busy-window runs — has **no sleep inside its loop**. The defect is located precisely in the
addition, and the five-run validation therefore never covered it.

**This is HK-022 in its exact form:** the five-run result validated the harness it was pointed
at. `play_pass_guarded()` is a different code path and inherited none of that confidence. Worth
recording as a concrete instance — a "ported unmodified, plus one addition" file carries
validation for the ported part only.

---

## 3. Corroboration — three independent lines, all consistent

**(a) Both decoders went dark together.** The report does not mention the OpenWSFZ leg, but it
is on disk at `_work/m3/run*/our_ALL.TXT`. Decodes per slot:

```
run1    3   5   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
run2    3   5   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .   .
run3    3   4   .   .   1   .   1   .   .   .   .   .   .   .   .   .   .   .   .   .
```

Both decoders were listening to `CABLE Output` simultaneously as independent processes. They
stop together, at the cycle where the sleep fires. **Two independent decoders failing in
lockstep is the audio, not the decoders** — and specifically its timing, since §3(b) shows the
audio content is sound.

**(b) The source audio is uniform and healthy.** Per-slot statistics over all 20 WAVs of the
selected window, both capture legs:

| | peak | normalisation gain (`0.9 / peak`) |
|---|---|---|
| M3 low-density window | 0.140 – 0.179 | 5.04× – 6.41× |
| busy window (worked fine) | 0.131 – 0.174 | 5.18× – 6.87× |

The two windows are indistinguishable on both. **This exonerates `PLAYBACK_PEAK = 0.9`**, which
I had flagged in the spec's §9 as an untested weakness — it is not implicated here.

RMS alternates by slot (0.062–0.078 on even slots, 0.018–0.021 on odd). That is ordinary FT8
even/odd transmit structure, not a defect. **Note that the loud slots are among those that
decoded nothing** — no signal-strength account survives that.

**(c) When it played on-grid, it behaved exactly as the busy window did.** The two cycles
played before the sleep:

| slot | replay | archived original | ratio |
|---|---:|---:|---:|
| 0 | 5 | 2 | 2.50× |
| 1 | 7 | 3 | 2.33× |

Against the established `S_busy = 2.30`. On the cycles the instrument actually functioned, the
low-density window overshot by the same factor as the busy one.

---

## 4. What must be withdrawn

1. **"The replay instrument itself is suspect."** Not supported. The instrument was never
   exercised on 18 of the 20 cycles. Please strike this from the report and replace it with the
   VOID disposition.

2. **The addendum's §3 hypothesis** — "the replay pipeline recovers strong signals at least as
   well as live WSJT-X but is comparatively worse at marginal ones." **Refuted.** It predicts
   degradation scattered across all 20 slots in proportion to marginality; what occurred was a
   clean cutoff at a fixed point in the loop, with the *loudest* slots among the silent ones.
   QA labelled it "a hypothesis for whoever picks up the escalation, not a finding QA is
   asserting" — that framing was correct and is why this costs nothing to withdraw.

3. **`s_low = 0.217`.** Not a measurement of anything. Do not carry it forward, and do not cite
   it as a low-density figure in any later document.

**Do not** read §3(c) as evidence that M3 would have fired ROW 1. Two cycles is not a
measurement, no gate was reached, and the honest statement is that **M3 has not yet been run.**

---

## 5. The fix

Remove the blocking sleep. The next cycle's `play()` already provides 15 s of wall time, which
covers WSJT-X's decode latency at zero timing cost — check the file size one cycle later
instead of sleeping for it:

```python
for i, fname in enumerate(window):
    samples = load_wav_normalised(wav_dir / fname)
    play(samples, output_device_idx)              # 15.000 s, phase-locked

    # Check one full cycle AFTER the preflight cycles have played. The 15 s of the
    # cycle just played is itself the decode-latency slack -- no sleep, so playback
    # stays locked to the UTC slot grid.
    if i == PREFLIGHT_CYCLES:
        observed = _wsjtx_size()
        if observed <= baseline_size:
            raise PreflightAbort(label, PREFLIGHT_CYCLES, baseline_size, observed)
```

`PREFLIGHT_EXTRA_WAIT_S` becomes unused and should be deleted rather than set to zero, so the
defect cannot be reintroduced by a later edit restoring a non-zero value.

**The guard itself is a good idea and should be kept.** It was added to mechanise the
"WSJT-X Monitor enabled late" failure that aborted the first attempt on 2026-08-06, which is
exactly the right instinct, and it functioned — it correctly confirmed liveness in all three
runs. Only its implementation needs changing.

### 5.1 Mandatory post-fix assertion

Add a phase-lock assertion to `play_pass_guarded()`, so this class of defect cannot recur
silently in any future replay:

```python
excess = (pass_end - pass_start).total_seconds() - len(window) * SLOT_SECONDS
assert excess < 3.0, (
    f"playback ran {excess:.2f}s over {len(window)} x {SLOT_SECONDS}s -- playback has "
    f"drifted off the UTC slot grid and every cycle after the drift is misaligned"
)
```

`3.0 s` is `DTtol`, the point beyond which WSJT-X will not associate a signal with its slot.
The validated harness's excess is 1.63 s, so this passes on known-good behaviour with margin.
**This assertion alone would have caught the defect on run 1.**

---

## 6. Re-running M3

- **The §5.4 gate is unchanged.** Thresholds `1.00 / 1.25 / 2.00`, rows in the same strict
  order, `S_busy = 2.30` comparator. Nothing about the gate was implicated; it fired correctly
  on bad input. Re-running a pre-registered gate after repairing a broken instrument is not
  moving a threshold, and must not be recorded as one.
- **The §5.3 validity gate is unchanged** (3 runs within 10% of their mean).
- **Re-select the window.** Do not reuse `260804_010200 … 260804_010645` by default — see §7.2;
  the selection rule needs the change below applied first.
- **Cost:** 3 runs × 1 pass × 5 min = 15 min playback, as originally specced.

### 6.1 One change to the §5.2 selection rule

Replace the density floor and objective. Original rule: exclude windows with archived WSJT-X
total `< 60`, then select the **minimum** mean combined count among survivors.

**Minimising subject to a floor always returns the floor.** 3,965 windows survived and the
selected window had `wsjtx_total = 60` exactly — not coincidence, a guaranteed consequence of
how I wrote the rule. It left zero margin on the one parameter the floor existed to protect.

Replace with:

> Among windows whose archived original WSJT-X total is `>= 100`, select the window at the
> **10th percentile** of mean combined count (not the minimum). Tie-break: earliest UTC.
> Report the selected window's `wsjtx_total`, its percentile, and the contrast against the busy
> window. The `contrast >= 3.0` requirement is unchanged.

This keeps genuine low-density leverage while guaranteeing the denominator has margin. Applying
it will very likely select a different window — that is intended.

---

## 7. M1 — the verdict stands; the threshold design was mine and was flawed

**ROW 4 stands. `delta = −2.000` dB, `p = 0.00425`. I will not move the threshold now**, and no
re-scoring of the existing M1 output is authorised. Recording the design faults for the next
spec, not to relitigate this one:

### 7.1 A knife-edge threshold on a discrete statistic

I set ROW 1 at `delta <= -2.0` dB. The statistic is a difference of medians of **integer-dB**
data, so it can only take values on a coarse lattice — including exactly `−2.0`, which is where
it landed. The effect-size condition was met exactly while the significance condition failed by
roughly 4×, producing an outcome the row structure could not express. A threshold must not sit
on a value its statistic can take exactly. `−1.5` would have been unambiguous either way.

### 7.2 The same fault, structurally, in the M3 selector

§6.1 above. Two knife-edge thresholds in one spec, both landed on. That is a pattern, not bad
luck, and it is worth carrying into every future gate I write: **after fixing a threshold, ask
what values the statistic can actually take, and whether the threshold is one of them.**

### 7.3 My power reasoning used the wrong n

Spec §3.4 argued from "n≈565 vs n≈187". Actual: **460 vs 323**. I had conflated *matched
between the two decoders* (187) with *shared between tonight and the archived original*
(≈323). Combined with heavy ties in integer-dB data, `p < 0.001` was a stricter bar than I
understood when I chose it.

### 7.4 If the truncation-vs-log question is still wanted

It needs a **new, pre-registered M1b with a better-powered statistic** — not a rescored M1.
Candidates worth costing: a proportion test on the fraction of decodes below a fixed SNR cut
(no tie problem, clean power), or Cliff's delta / rank-biserial with a confidence interval
rather than a median difference. **Not proposed for authorisation here** — M3 is the higher
priority, and M1b should be designed only if the Captain still wants the mechanism resolved.

---

## 8. M2 — stands, and is the durable result

Validity gate passed: `R_wsjtx_self = 0.9645` against a `0.80` bar. `R_owsfz = 0.9534` → ROW 1.

`R_owsfz − R_owsfz_all5 = 0.9534 − 0.9498 = 0.0036`, far below the `0.15` marginality flag —
so the recovered decodes are found in **every one of the five runs**, not intermittently
caught at the margin. That is stronger than the gate required.

**Citable statement:** on the busy window of `20260803_live_run_1713`, 95.3% of the decodes
that were OpenWSFZ-exclusive in the archived corpus are found by WSJT-X on replay of the same
audio, 95.0% of them in every replicate. "OpenWSFZ finds decodes WSJT-X cannot" is **false on
this window**.

**Citation limit:** one window, and it is the busiest in the corpus. This does **not** license
a corpus-wide claim — that is precisely what M3 exists to test and M3 has not yet run.

Consequence unchanged from the spec: Arm R.D's reciprocity premise is undermined on this
window, and **R.D remains unauthorised pending a valid M3.**

---

## 9. M4

Correctly skipped on the M1 gate. Additionally blocked: it calls the same
`play_pass_guarded()` and would have been misaligned in exactly the same way. Do not run it
before §5 lands, regardless of what any future M1b returns.

---

## 10. HK-017

The results directory is named `2026-08-07-…` while the report's byline reads
`2026-08-06 22:33:44 UTC`. Those disagree: the directory is on local time (UTC+2), the byline
on UTC. At the time of writing this note it is still `2026-08-06` in UTC.

Not consequential to any result, and the byline itself is correct. Flagging it only because
HK-017's whole content is that the filename and the byline must both come from real `date -u`
and must agree — this is that drift, caught early. The directory can be renamed with the
re-run, or left with a note; QA's call.

---

## 11. What this does not change

- **M0's preservation stands** and is now doubly worth having.
- **The 5-run busy-window result is untouched.** It ran on `run_cross_decode_replay.py`, whose
  loop has no inserted sleep and whose pass duration excess is 1.63 s. M1 and M2 are offline
  analyses of that output and are unaffected by this defect.
- **The reference-suppression question is still open**, and still the most consequential thing
  on the board. Nothing here weakens the finding that WSJT-X yielded 748–759 on replay against
  328 archived live. It remains untested beyond one window.
- **No D-001 figure is re-derived here**, and I still have not opened
  `project-state-2026-07-31-d001-competition-confirmed.md`.
- **Nothing touches `src/`.** The §5 fix is `qa/` tooling; no Developer session, HK-011 not
  engaged.

---

*Per HK-015 this is Architect → QA. Per HK-014 committed locally, not pushed, no merge implied
or requested. Per HK-011 nothing here touches `src/`. Per HK-021 the M3 gate is re-run
unchanged and the M1 verdict stands as pre-registered; the threshold faults in §7 are recorded
as design lessons, not as grounds for re-scoring. Per NFR-021 no message text or callsign
appears in this document — all decode figures are counts.*
