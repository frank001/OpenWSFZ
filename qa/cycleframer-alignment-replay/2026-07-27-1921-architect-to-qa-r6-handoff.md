# D-001: Architect -> QA handoff — R.5 rung 3 is void, one confound is closed, and R.6 is built
# but NOT validated. Its control arm is broken and its numbers must not be quoted.

**Author:** Architect, 2026-07-27 (19:21 UTC, `date -u`, per HK-017). **For:** QA, per HK-015.
**Follows:** `2026-07-27-1900-architect-r5-ruling-rung3-void.md`.
**Status: hand-off mid-investigation.** I built and partially debugged R.6 in this session; the
Captain stopped me at the point below. Everything I know is written down here, including what is
still wrong with it.

---

## 1. Read this first — the one thing that must not happen

`r6_clean_graft.py` currently prints a table with a REAL arm and an AWGN control arm. **The AWGN
control decodes 0.0% at every SNR tested while the real arm reaches 63%.** That is not a result, it
is a broken control. **Do not quote, summarise, or build on any R.6 number until the control passes
a ceiling check.** If the control is broken, the real-arm numbers are unanchored — precisely the
failure that made R.5's rung 3 void.

I have written the script so this is visible rather than hidden, but there is no automated gate on
it yet. **Add one (SC3 below) before the next run.**

## 2. What is now settled

### 2.1 R.5 rung 3 is void (ruled at 19:00, committed `51849d1`)

The notch empties the exact band the synthetic signal is then planted into. Measured residual power
in planted bands ~1e-28 (float64 zero) vs ~1e+2..1e+3 in control bands 150 Hz away; net +49.5 dB
effective in-band SNR versus rung 2. Rungs 0/1/2/4 stand. The rung2->3 divergence — reported as the
arm's most actionable lead and as a third instrument alongside C.3/R.4 — is **withdrawn**.

Recomputed on the four sound rungs, our decoder-specific excess loss is:

| step | ours-specific excess | share of the -20.5 pt gap |
|---|---:|---:|
| 0 → 1 population geometry | -5.7 pt | 28% |
| 1 → 2 real SNR distribution | -1.5 pt | 7% |
| **2 → 4 real audio, unreproduced** | **-13.2 pt** | **65%** |

### 2.2 NEW — the capture chain is excluded at rung 4, so row 4's label is wrong

I checked what "row 4" can still mean. **It cannot mean the capture/processing chain.** C.4's
findings §4.1 state, and I verified the directory exists with 68 files, that our offline decode ran
on `artefacts/20260725_live_run_1806/wsjt-x/wav68/` — **WSJT-X's own captured audio**. So at rung 4
all three of WSJT-X (ground truth), jt9 and our decoder read **byte-identical files**.

The 2→4 step is therefore **not** a capture difference. It is: *on the same audio file, against real
content our synthesis does not reproduce, we lose 18.6 pt where jt9 loses 5.4.* The design's row-4
wording ("the difference is in the capture/processing chain ahead of the decoder") is refuted; the
row's *shape* (no synthetic rung reproduces it) still fires. **My 19:00 ruling §4 endorses the
row-4 label too readily — treat this section as correcting it.**

### 2.3 The remaining fork

What real audio has that rungs 1-2 do not, splits cleanly in two:

- **(A) real ENVIRONMENT** — non-white/non-stationary noise, QRM, birdies, undecoded carriers
- **(B) real SIGNALS** — GFSK vs our CPFSK synthesis, fading/QSB, transmitter drift, timing jitter

R.5's rung 3 was supposed to test (A) and failed. **R.6 is the replacement.**

## 3. R.6 — the clean graft (design, and why it is the right instrument)

Graft a synthetic Q-message into **unmodified** real audio, in a frequency gap where WSJT-X decoded
nothing, at a controlled **local** in-band SNR measured from that buffer's own noise in that exact
band. No notch, no hole. Control arm: identical signals at identical in-band SNR in flat AWGN.

A grafted synthetic signal carries (A) but **not** (B). So:

- `ours_real ≈ ours_awgn` → the environment is not the problem → **the gap is in (B)**, real signal
  properties, and the study should turn to fading/drift/GFSK.
- `ours_real << ours_awgn` while jt9 holds up → **(A)**, noise-adaptive handling / candidate scoring.

This is the bisection R.5 was reaching for, without the construction that broke it.

## 4. What I built, and the two defects I already found in it

`qa/cycleframer-alignment-replay/r6_clean_graft.py` (committed, see §7). Reuses `b2` (synthesis,
Wilson), `b1` (corpus paths, `ALL.TXT` parsing, jt9 stdout parsing), `r5` (`read_real_wav_float`,
`decode_all_with_messages`, `write_wav`, `run_jt9_single`). Env knobs: `R6_N_CYCLES`,
`R6_MAX_GRAFTS`, `R6_SNRS`, `R6_GUARD`.

**Defect 1 (found and fixed).** The first draft set each graft's amplitude from a plain in-band RMS
of the gap. Any **undecoded** real carrier in the gap inflates that RMS, inflates the graft's
amplitude, and makes the real arm artificially easy. SC1 could not see it because SC1 divided by the
same contaminated estimate — **the check was circular.** This is the same class of bug as R.5's
rung 3: an amplitude pinned to a "noise" measurement that is not purely noise. Fixed by
`band_noise_rms_robust`, which uses the **median** per-bin power in the band instead of the sum.

**Defect 2 (found, NOT fixed — this is the blocker).** The AWGN control decodes 0.0% at -14, -10 and
-6 dB in-band, while an earlier run at 0 and +10 dB gave 100%. So the control's threshold sits
between -6 and 0 dB, while the real arm is already at 63% at -6 dB and 15% at -10 dB. **The control
is >6 dB harder than the real arm at matched measured SNR, which is backwards.** SC1 says the two
arms are within 1.54 dB, so the ~1.5 dB offset does not explain a 63-vs-0 split.

## 5. The next test — I was one command from running it

**Hypothesis: absolute level sensitivity.** The R.6 AWGN buffer has broadband RMS ~3.1e-3. R.5's
synthetic rungs 0-2 used `noise_std_ref = 0.53` — **~170x louder**. Every synthetic result this
study has ever produced (B.2, R.4, R.5 rungs 0-2) was generated at the loud level. If either decoder
degrades at low absolute input level, the R.6 control is simply too quiet, and the fix is to scale
both arms to a common working level.

The test I had queued (rejected before it ran, so **this is untested**):

```
# pure AWGN, 4 grafts, in-band SNR fixed at -6 dB, sweep ABSOLUTE level over ~45 dB
for sigma in [3.1e-3, 3.1e-2, 3.1e-1, 5.3e-1]:
    inband = sigma * sqrt(43.75/6000);  amp = sqrt(2)*inband*10**(-6/20)
    -> plant 4 messages at 400/1000/1800/2500 Hz, decode, count hits
```

**If hit-rate rises with sigma at fixed in-band SNR, the decoder is level-sensitive** — that is a
finding in its own right and would need checking against the real corpus's own levels before it is
called a defect. **If hit-rate is flat, the level hypothesis is dead** and the control failure is
something else; the next candidates I would check, in order:

1. `write_wav`'s peak normalisation interacting differently with the two arms (the real arm's peak
   is set by loud real signals; the AWGN arm's by noise).
2. 16-bit quantisation floor relative to graft amplitude in the quiet AWGN arm (this affects jt9 via
   the WAV, but **our** decoder reads the float buffer directly and also scored 0%, so it cannot be
   the whole story).
3. The `b2.synth_signal` amplitude convention vs. the in-band SNR definition — verify by measuring a
   single graft's post-hoc in-band SNR in a buffer that decodes and one that does not.

## 6. A correction to my own SC4 that you should make before trusting it

SC4 reports "gap contamination" as raw-in-band-RMS over robust-in-band-RMS, and prints median
+1.59 dB. **I believe most or all of that median is estimator bias, not contamination.** For a
periodogram the per-bin power is chi-squared with 2 dof, whose median is `ln(2) ≈ 0.693` times its
mean — i.e. **-1.59 dB**. The number I measured is almost exactly that.

So: the robust estimator **systematically underestimates noise power by ~1.6 dB** for white *and*
real noise, and SC4 as written measures that bias rather than carriers. Two consequences:

- Divide the median by `ln(2)` inside `band_noise_rms_robust` to make it unbiased.
- SC4 only becomes a contamination check **after** that correction; the informative statistic is
  then the **upper tail** (p95 +4.20 dB, max +9.66 dB in my 6-cycle smoke run), which does look like
  real carriers in some gaps.

This also means SC1's real-arm -1.45 dB is mostly this bias, and should move to ~0 once corrected.

## 7. Self-checks R.6 has, and the one it is missing

Present: **SC1** measured-vs-nominal in-band SNR, **both arms**, with an arm-to-arm offset gate;
**SC2** gap-clearance violations (0 in all runs so far); **SC4** contamination (see §6).

**Missing and required before the next run: SC3 — the control arm must reach a ceiling at the top of
the SNR grid** (say ≥90% at the warmest point, both decoders). That is the check that would have
turned "AWGN 0.0% everywhere" from a table row into a hard FAIL. **This is the generalised lesson
from the R.5 audit and I did not apply it to my own harness — the docstring claims SC3 exists and it
does not. Please add it.**

## 8. State of the branch

- `51849d1` — the R.5 rung-3 ruling (committed).
- `r6_clean_graft.py` — committed alongside this handoff. **Working but not validated**; smoke-run
  only (6 cycles, 27 grafts, 3 SNR points).
- `artefacts/d001_r6_clean_graft/measurements.json` — smoke-run output, git-ignored. **Contains a
  broken control arm; not a result.**
- Nothing pushed, nothing merged (HK-014). No `src/` or native change (HK-011). No
  `pre_merge_check.py` (HK-006, Captain's trigger).

## 9. What I recommend QA does, in order

1. **Run §5's level sweep.** It is ten lines and it either explains the control failure or kills the
   most likely cause. Do this before touching anything else.
2. **Fix `band_noise_rms_robust`'s `ln(2)` bias** (§6) and re-read SC1/SC4.
3. **Add SC3** (§7) and make it a hard gate.
4. **Only then** scale up: 34 cycles x 4 grafts x a 6-point SNR grid, both arms, both decoders
   (~400 jt9 invocations, 10-15 min).
5. Author the R.6 task spec properly — I have written a script and a rationale, not a spec, and per
   HK-015 the spec is yours. Treat §3 as the design and §§4-7 as known-defect notes to carry into it.

**Escalate to me if** the level sweep is flat *and* none of §5's three fallbacks explain the control
— that would mean the two arms differ in something I have not thought of, and the design needs
revisiting rather than the harness.

## 10. Honest statement of what is NOT established

- **No R.6 number is established.** Not one. The arm has produced no valid measurement yet.
- The (A)/(B) fork in §2.3 is **unresolved** — that is the whole point of R.6.
- §2.2's exclusion of the capture chain rests on C.4's own §4.1 provenance statement plus the
  directory's existence. I did not re-derive the decode from the WAVs; if that provenance is wrong,
  §2.2 falls. **Worth one cheap confirmation.**
- Everything in the running accounting is untouched: C.4's +2, B.2's E=5.69, C.3's SNR split and
  proximity refutation, B.1/B.1b's 437, R.1's withdrawal, R.4's 2.62 dB, R.4b's 7.4%/6.8%.
  **The 437 has still never moved.**

## 11. Cross-references

- `2026-07-27-1900-architect-r5-ruling-rung3-void.md` — the ruling; §4 of it is corrected by §2.2
  above.
- `2026-07-27-1850-qa-to-architect-r5-notification.md`, `-r5-hybrid-ladder-findings.md`,
  `-r5-hybrid-ladder-task-spec.md` — R.5 as delivered.
- `2026-07-26-c4-min-score-sweep-findings.md` §4.1 — the `wsjt-x/wav68/` provenance §2.2 rests on.
- `r6_clean_graft.py` — the harness; `band_noise_rms_robust` (§6), `build_pair`, `find_gaps`.

---

*Per HK-015 Architect -> QA; the task spec is QA's to author. Per HK-014 committed locally, no push,
no merge. Per HK-011 nothing here touches `src/` or native code. Per HK-018 §2.2 was checked against
the existing C.4 findings before being asserted, and §1/§4 record two defects found by measurement
rather than reasoning — one of them in my own harness.*
