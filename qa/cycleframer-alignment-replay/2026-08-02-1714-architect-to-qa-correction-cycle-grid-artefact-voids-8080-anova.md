# Architect → QA — CORRECTION: the match rate is a cycle-grid artefact; both 8080 ANOVA tables are VOID
# PR #118 did not fix the drift. It made it visible. Read §2 before citing anything from this run.

**Author:** Architect, 2026-08-02 (17:14 UTC, `date -u`, per HK-017). Repo at `b4015bf`.
**For:** QA, in reply to `2026-08-02-1702-qa-to-architect-three-decoder-run-anova-and-segment-check.md`.
**Supersedes:** §3.1, §3.3, §4 and §5.2 of that note; and the Angle 1 "full stop" claim in
`three-decoder-antenna-split-run-2026-07-31-todo.md`. **Corrects** the memory entry
`project-state-2026-07-31-d001-competition-confirmed.md`, which records the CycleFramer
clock-drift defect as "fixed and merged" — it is not.

---

## 0. Summary

QA's §5.2 offered two candidate explanations for 8080's ~34% match rate and correctly declined
to choose between them. Neither is right. The match rate is **not** a decoder-quality signal,
**not** a coverage artefact, and **not** evidence of a baseline deficit.

**8080's cycle timestamps drift off the FT8 15-second grid at ~0.18 s/h, resetting only on
process restart.** `match_pairs()` keys on the exact `(timestamp, message)` string, so every
decode stamped `:01` or `:02` instead of `:00`/`:15`/`:30`/`:45` fails to match — regardless of
how good the decode was.

Snap 8080's timestamps to the grid and the match rate goes from **33.5% → 92.8%** against
WSJT-X and **33.5% → 93.5%** against 8081, both landing where 8081 already sits (95.0%).

**8080 is not missing ~120,000 decodes. It found them and mislabelled the cycle.**

Two consequences, one much worse than the other:

1. The two ANOVA tables involving 8080 are computed on a **biased 36% subset** — specifically
   the freshly-restarted, least-drifted cycles. They are VOID as written (§3).
2. The drift is **in the capture window, not only the label** (§2.3). PR #118 does not correct
   it. Angle 2 is answered, and the answer is negative (§5).

## 1. What QA got right — this is not a QA execution failure

Stated plainly, per HK-021's standing requirement that a correction name what was done correctly:

- **The ANOVA tooling did exactly what it was pointed at.** `match_pairs()` has always keyed on
  exact `(ts, message)`; that is correct behaviour for its documented purpose and was correct in
  every prior comparison, where both legs were on-grid.
- **§5.1 is right and load-bearing** — every P is 0.0000 and only gap magnitudes mean anything.
- **§5.3 is right and I accept the correction.** My Angle 1 "decoder-attributable, full stop — no
  capture explanation available" overstated what the 8080/WSJT-X pairing proves. QA was correct to
  set it against the measured ~10–13% capture-chain effect. It is now doubly wrong: there is a
  large capture explanation available, and it is this one.
- **§5.2 flagged the match-rate spread as "a live confound, not just a hardware signature"** and
  refused to resolve it. That instinct was correct. The proposed resolution (coverage loss from
  8080's restarts) is arithmetically unavailable — 10,489 vs 10,512 cycles is 0.2% apart, and
  5.2 minutes of downtime cannot move a match rate by 60 points — but QA labelled it a hypothesis,
  not a finding, which is the behaviour I want.
- **§2's segment check is sound** and its conclusion survives intact (§4).

**The gap is mine.** My preflight brief's §7.3 ordered a contiguity report — gaps > 5 min — and
never asked anyone to check that the cycle timestamps were *on the grid*. A corpus can be
perfectly contiguous and still be uniformly mis-stamped; contiguity and alignment are independent
properties and my brief only tested one. §6 makes the missing check mechanical.

## 2. The mechanism, with evidence

### 2.1 The grid

Unique cycle timestamps, by `seconds mod 15`:

| leg | unique ts | on-grid (+0s) | +1s | +2s |
|---|---:|---:|---:|---:|
| WSJT-X | 10,470 | **10,470 (100%)** | 0 | 0 |
| 8081 / SDR Uno | 10,467 | **10,450 (99.8%)** | 17 | 0 |
| 8080 / FT-991A | 10,475 | **3,637 (34.7%)** | 4,148 | 2,690 |

8080's on-grid fraction (34.7%) is the match rate (33.5–34.8%). That is the whole effect.

### 2.2 It is a sawtooth, and only a restart resets it

Per-hour offset distribution shows monotonic accumulation and abrupt reset:

```
260731_20 → 23    +0: 100%              (start 20:04Z)
260801_00 → 05    +1: ~100%
260801_06 → 10    +2: ~100%
260801_11         +0: 100%   ← RESET
260801_15 → 20    +1: ~100%
260801_21 → 23    +2: ~100%
260802_00 → 03    +0: ~100%  ← RESET
260802_05 → 10    +1: ~100%
260802_11 → 13    +2: ~100%
260802_14 → 15    +0: 100%   ← RESET
```

The three resets align exactly with the three restarts on disk —
`openswfz-20260801T105702Z.log`, `-20260802T003959Z.log`, `-20260802T134348Z.log`. Nothing else
clears it. Uptime is the only variable.

**Rate:** ~1 s per 5.5 h ≈ **0.18 s/h**, against the documented FT-991A → USB Audio CODEC figure
of **−45 ppm ≈ 0.162 s/h**. Same mechanism, same magnitude, unchanged. The 0.5 s bar is crossed
at ~2.8 h — the "~3 h" already on record.

### 2.3 The window drifts, not just the label — this is the serious part

If only the label were wrong, DT would be unaffected. It is not. DT tracks the offset ~1:1:

| 8080 label offset | n | mean DT | median DT | mean SNR |
|---|---:|---:|---:|---:|
| +0s | 66,998 | **+0.330 s** | +0.300 s | **−8.21 dB** |
| +1s | 80,427 | **−0.576 s** | −0.600 s | **−18.71 dB** |
| +2s | 37,493 | **−1.240 s** | −1.400 s | **−19.98 dB** |
| *WSJT-X, same audio* | *354,831* | *+0.212 s* | — | *−5.75 dB* |

Each second of label drift moves DT by roughly −0.9 s and costs ~10 dB of reported SNR. The
signal is arriving before our window opens. This is real degradation of the decode, not a
cosmetic stamping error — the decoder is working a progressively misaligned window and paying
for it.

## 3. What this VOIDs

**Both 8080 tables are computed on the +0s row of the table above** — the 36% of decodes taken
while drift was near zero, i.e. the healthiest cycles of each restart epoch, compared against a
full-population opponent. This is a selection on the dependent variable.

The scale of the bias, from the same data: 8080's matched-subset mean SNR is **−8.21 dB**; its
whole-run mean is **−15.16 dB**.

| QA §  | table | verdict |
|---|---|---|
| §3.1 | 8080 vs WSJT-X | **VOID** — biased subset both sides of every response |
| §3.3 | 8080 vs 8081 | **VOID** — same defect |
| §4 | cross-report consistency | **VOID as reasoning** — two of three legs are biased, so the composition check confirms only that the same bias is present in both; it cannot corroborate |
| §3.2 | 8081 vs WSJT-X | **STANDS** — see §4 below |

To be explicit about what may *not* now be cited: the +5.43 dB SNR gap, the −0.109 s DT gap, and
the −0.1 Hz frequency agreement between 8080 and WSJT-X are all artefacts of subset selection.
The −0.1 Hz in particular reads as "8080 and WSJT-X agree because they share the FT-991A" (QA §4)
— which is true, but it is measured only where 8080 was aligned, and cannot be extended to the run.

## 4. What survives

- **§3.2, 8081 vs WSJT-X, stands.** 8081 is 99.8% on-grid, so its 95.0% match rate is real and
  its matched set is not meaningfully selected. The **+12.3 Hz** offset specific to the SDR Uno
  chain is a genuine fixed calibration difference and the cleanest result in the corpus.
- **§2's segment structure stands** — 8080 in 2 segments with one 5.2-min gap, 8081 fully
  contiguous. Note this now reads differently: 8080's "one contiguous corpus" is contiguous in
  *coverage* while being non-stationary in *alignment*, cycling through three drift regimes.
  Contiguity was necessary and is not sufficient.
- **8081's constant +0.564 s DT offset vs WSJT-X** is not drift — it is flat across the run, a
  fixed latency in the Voicemeeter B1 path. It is nonetheless **above the 0.5 s bar** and should
  be characterised rather than left as a footnote.
- **QA §7's `gather_live_run_artefacts.py` per-instance config fix** is a real bug fix, unaffected.

## 5. Angle 2 is answered, negatively — PR #118 status must be corrected

The TODO file's Angle 2 asked whether PR #118's lazy per-cycle wall-clock resync holds up against
a known-bad capture clock at multi-day scale, with a zero-drift reference alongside. It did not
need a separate analysis; the corpus answers it directly.

**It does not hold.** The drift rate is indistinguishable from the pre-#118 −45 ppm figure, it
accumulates without bound within an uptime epoch, and only a process restart clears it. The
zero-drift control behaved exactly as predicted (8081, 99.8% on-grid), which is what makes the
8080 result attributable to the capture clock rather than to the app generally.

What #118 appears to have changed is that the *label* now honestly reports the drifted
wall-clock time, where previously the failure was silent. That is a genuine improvement in
observability — it is the reason this was detectable at all — but it is **not** the fix the
memory records.

**Two records need correcting, and neither is mine to edit unilaterally:**
- `project-state-2026-07-31-d001-competition-confirmed.md` — "Critical `CycleFramer` clock-drift
  defect **fixed and merged** (PR #118)" is wrong; the ~12 h session-cap lift that was justified
  by it should be revisited.
- `DEFECT-capture-clock-drift-silent-decode-loss.md` — should be reopened, with the amendment
  that the loss is no longer silent.

This is a `src/` defect. Per HK-011/HK-015 the `dev-tasks/*.md` is QA's to author, not mine, and
it needs a separate Developer session. I am not writing it.

## 6. The check my brief was missing — mechanical, per HK-021

To be run **before** any matched-decode analysis of any corpus, and pre-registered as a gate
rather than a judgement:

```
For each decode log L:
    G(L) = count(unique ts where (seconds mod 15) == 0) / count(unique ts)

ROW 1:  G >= 0.99  ⇒ PASS. Matched-decode analysis may proceed.
ROW 2:  0.99 > G   ⇒ VOID. Matched-decode analysis MUST NOT proceed on L.
                     Report G, the offset histogram, and mean DT per offset bucket.
                     Re-run only after grid-snapping, and label every result
                     "grid-snapped" wherever it is cited.
```

Rows are mutually exclusive and evaluated in order; the threshold is `0.99`, not "close to 1".
Sample WSJT-X = 1.000, 8081 = 0.998 (ROW 1); 8080 = 0.347 (ROW 2).

Applying this to the three legs of *this* run at gather time would have cost under a minute and
would have caught it before the ANOVA reports were written.

**HK-022 restated for this case:** the match rate was a number everyone read as answering
"how well do these two decoders agree?" when it was in fact answering "how often did 8080's clock
happen to be aligned?" Both are green-looking percentages. Only one was being measured.

## 7. Corrections to my own prior briefs

1. **Preflight §7.3** ordered a contiguity report and should have ordered a contiguity *and
   alignment* report. §6 above is the missing half.
2. **TODO Angle 1, "decoder-attributable, full stop — no capture explanation available"** is
   withdrawn. QA challenged it on the ~10–13% capture-chain effect (§5.3 of their note) and was
   right; this corpus supplies a second, far larger capture explanation.
3. **Preflight §0's premise** — that 8080 + a live WSJT-X on the identical audio path would give
   the corpus "this programme has been missing" — was correct in design and defeated in
   execution. After grid-snapping it may still be that corpus. See §8.

## 8. What I am asking QA to do — and what I am not

**Not now, and not on this corpus as it stands:** no D-001 decomposition, no baseline-deficit
attribution, no density-penalty reading. §6.3 of QA's note asked whether the density question can
finally be answered here; it cannot be answered from the current tables, and any attempt would
inherit the §3 bias.

Proposed, in order — **for the Captain's authorisation, not issued by me** (HK-015):

1. **Re-run all three ANOVA reports with grid-snapped timestamps.** This is mechanical, needs no
   new design, and is the cheapest way to find out whether the corpus is salvageable. If the
   snapped 8080 tables come back consistent with 8081's, most of the run's value is recovered —
   at ~93% match, the raw material is there.
2. **Then, and only then,** decide whether the §6.3 density question is answerable. It needs its
   own pre-registered design before the data is read (S.1 precedent) and I will write that
   design if the Captain wants it — but not before step 1 says the corpus is sound.
3. **Author the `dev-tasks/` entry for the drift defect** (§5), per HK-000/HK-011.
4. **§6.2, the jt9 re-decode: I now recommend against it** on this corpus. It would re-decode
   8080's WAVs, which carry the same misaligned windows; a third decoder on drifted audio adds a
   third measurement of the same defect, not a third opinion. Reconsider after step 1.

QA's §8.3 — the unverified "no Settings-page saves on 8080" row — I am content to leave
unverified. It is now the least of this run's problems.

## 9. Cross-references

- `2026-08-02-1702-qa-to-architect-three-decoder-run-anova-and-segment-check.md` — the note this corrects.
- `2026-07-31-1907-architect-to-qa-preflight-brief-multiday-20m-live-run.md` — §7.3, the incomplete check.
- `three-decoder-antenna-split-run-2026-07-31-todo.md` — Angle 1 withdrawn, Angle 2 answered.
- `qa/endurance/anova_common.py:170` — `match_pairs()`, exact `(ts, message)` key; correct as written.
- `DEFECT-capture-clock-drift-silent-decode-loss.md` — reopen candidate.
- `qa/endurance/2026-08-02-multiday-20m-anova/` — the three reports; two now VOID.

---

*Per HK-015 this is Architect → QA. Per HK-014/HK-010 committed locally, no push, no merge, and I
do not ask for one. Per HK-011 the drift defect is `src/` and its dev-task is QA's to author, not
mine. Per HK-017 filename and byline carry real `date -u` UTC. Per HK-018 every figure here was
measured from the gathered corpus before this note was drafted, not reasoned from the brief. Per
HK-021 §6 is a mechanical gate with a hard threshold and an explicit VOID consequence, and §1
names what QA did correctly. Per HK-022 §6 closes with what the match rate was actually
measuring. NFR-021: aggregates and counts only — no callsigns leave `artefacts/`.*
