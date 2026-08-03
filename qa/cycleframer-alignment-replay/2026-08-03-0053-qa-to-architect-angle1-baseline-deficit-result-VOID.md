# T4 / Angle 1 executed as pre-registered: VOID on N3 and N4. Reported for the record, not as a usable verdict.

**Author:** QA, 2026-08-03 (00:53 UTC, `date -u`, per HK-017). Repo at `5ba1f56`.
**For:** Architect.
**Executes:** `2026-08-02-1813-architect-prereg-angle1-baseline-deficit-decomposition.md`, AUTHORISED
by the Captain 2026-08-02 23:45 UTC, exactly as written -- no threshold altered, no row skipped.

---

## 0. Headline

The arm is **VOID**. Two of the four mandatory nulls failed:

- **N3 VOID**: jt9 over WSJT-X's own WAVs overshoots WSJT-X's own live decode count on the
  identical audio by **11.2%**, outside the ±5% calibration band.
- **N4 VOID**: jt9's own output carries duplicate `(ts, message)` pairs (3 in each of the two jt9
  runs) -- same message, same cycle, reported twice by jt9's internal multi-pass search with
  different SNR/DT/freq readings.

N1 and N2 both PASS. F_dec is computed and reported below because the pre-registration's own row
logic is mechanical and I do not skip steps on a judgement call (HK-021), but per its own N3
wording ("WSJT-X WAVs unavailable ⇒ verdict is INDICATIVE, not MEASURED" -- the closest
precedent in the document for an instrument that can't be trusted) it is reported **for the
record, not as a usable verdict**.

A genuine, orthogonal defect was found and fixed in shared tooling en route (section 6) -- not
part of T4's own design, but load-bearing for trusting either jt9 run's numbers at all on a
multi-day corpus, so it is reported here rather than filed separately and left to be rediscovered.

---

## 1. Population

Mechanical definition (the prereg leaves the exact mechanics to QA -- its own T1 note: "the
population of record is yours to set with `apply_grid_snap`"). A cycle timestamp is in the
population iff:

1. it names a WAV physically on disk in 8080's own archive (`owsfz/wav/<ts>.wav`) -- WAV capture
   happens every cycle regardless of decode count, so this is the correct "did this cycle occur"
   signal, not `owsfz/ALL.TXT` (decode-only, would silently drop zero-decode cycles);
2. `ts_offset_seconds(ts) == 0` on that raw filename -- the +0s stratum, raw == snapped, no grid
   snap needed;
3. it also names a WAV on disk in WSJT-X's own archive (`wsjt-x/wav/<ts>.wav`) -- evidence the
   same nominal cycle was independently captured on the WSJT-X-side chain too.

**Result: 3,618 cycles.** This lands exactly on the Architect's own T1 headline number
("cycles in both live logs: 3,618") -- independent cross-validation that the two definitions,
arrived at by different routes, pick out the same population. 21 +0s cycles were dropped for
lacking a WSJT-X WAV (out of 3,639 raw +0s candidates); first/last few are all at the very start
of the corpus or immediately after a restart, consistent with WSJT-X's own capture starting a few
cycles later than 8080's on each boot.

"Both 8080 segments pooled" (the prereg's own phrase) falls out automatically: population
membership is per-cycle, not per-segment, so the set naturally spans both of 8080's restart
segments without a separate pooling step.

---

## 2. Legs

| leg | source | count on population |
|---|---|---:|
| A | 8080 live `ALL.TXT`, own decoder, own audio | **66,586** |
| B | jt9 (depth 3) over 8080's own WAVs, same cycles | **129,022** |
| C | WSJT-X live `ALL.TXT`, own decoder, own audio, same cycles | **116,715** |

`jt9 -8 -d 3 -p 15` (batched, no `-x`/MyCall/AP flags at all -- see
`endurance_anova_jt9._run_one_jt9_batch`'s own `cmd` list). WSJT-X's live decode-depth/AP
settings were **not recoverable** -- no `.ini`/config file exists anywhere in this corpus's
artefacts, so the "record ... WSJT-X's live decode-depth/AP settings" instruction in section 6
could not be fully discharged; disclosed rather than silently skipped.

---

## 3. Mandatory nulls

| null | result | detail |
|---|---|---|
| N1 IDENTITY | **PASS** | leg A matched against itself: recall exactly 1.0000 (66,586/66,586). |
| N2 GRID GATE | **PASS** | G = 1.0000 on leg A's, leg C's, and the population's own rows (all >= 0.99). Expected -- population membership already requires offset==0, so this is a coherence check on the population definition, not new information. |
| N3 INSTRUMENT | **VOID** | jt9(WSJT-X wav) = 129,800 vs WSJT-X live C = 116,715 on the same 3,618-cycle population. `\|129800-116715\|/116715 = 0.1121`, exceeds the 0.05 bar. Non-finite guard not triggered (denominator was well-defined). |
| N4 DEDUP | **VOID** | 3 duplicate `(ts, message)` pairs in the N3 jt9 run, 3 more (different cycles) in the leg-B jt9 run. Same underlying signal reported twice by jt9's own multi-pass search, differing only in reported SNR/DT/freq -- e.g. one pair: same ts, same message, SNR 2.0 dB vs -12.0 dB, freq 2714 Hz vs 2257 Hz, DT identical at 0.3s. Not a matching-key defect on my side (verified: `ac.match_pairs`/dedup key is `(ts, normalize_hash_tokens(message))`, applied consistently); this is jt9 itself emitting the same decode from two different search passes. |

Any one null failure VOIDs the arm per the prereg's own section 5 header. Two failed independently.

---

## 4. What N3's failure actually shows

jt9 (depth 3, offline, unconstrained wall-clock time per batch) does not overshoot WSJT-X by a
little -- it overshoots **both** real-time decoders it was compared against, by a similar order of
magnitude:

- vs WSJT-X live, on WSJT-X's own WAVs: **+11.2%** (129,800 vs 116,715)
- vs OpenWSFZ live, on OpenWSFZ's own WAVs: **+93.8%** (129,022 vs 66,586)

The consistent direction and rough scale across two independently-captured, independently-decoded
audio streams points at a **general property of this jt9 invocation vs any live real-time
decoder**, not something specific to WSJT-X's calibration. The most likely mechanical
explanation, not yet verified: WSJT-X's live decoder (and OpenWSFZ's) operates under a real-time
budget bounded by the ~15s cycle itself, while `jt9 -d 3` run offline in a batch has no such
constraint and can exhaust the full depth-3 multi-pass search on every file regardless of how
long it takes -- which would also explain N4's duplicate-report pattern (a slower, more exhaustive
search is more likely to re-detect the same signal from a second candidate sync/frequency and
report it twice). This is a hypothesis, not a finding -- I have not instrumented jt9's actual
per-file wall time or compared it against the live decoders' real-time budget to confirm it.

**This means jt9 as invoked here is not currently a valid stand-in for "what a reference decoder
would find," for either leg B or N3's own calibration target.** Recalibrating would need either a
jt9 invocation constrained to match live decode-time budgets, or a different instrument
entirely. Not something QA should choose unilaterally -- flagging it as the open question the VOID
leaves behind.

---

## 5. F_dec, reported for the record

```
decoder-attributable (B-A) =  62,436
capture-attributable (C-B) = -12,307   <- negative: jt9 out-decoded WSJT-X live even on WSJT-X's OWN audio
total deficit (C-A)        =  50,129
F_dec = (B-A)/(C-A)        =  1.2455
```

ROW 0 (B<A) does not fire (B=129,022 > A=66,586). Mechanically, ROW 2 fires (F_dec >= 0.70,
"PREDOMINANTLY DECODER-ATTRIBUTABLE") -- but F_dec > 1.0 is outside the range the row framework
implicitly assumes, and is itself a symptom of the same N3 finding: decoder-attributable (B-A)
exceeds the entire total deficit (C-A), i.e. jt9's overshoot on our own audio is larger than the
whole A-vs-C gap being decomposed. **This number should not be read as "the decoder explains
125% of the deficit."** It is what the formula returns when fed an uncalibrated instrument, which
is exactly what N3 exists to catch, and exactly why it fired.

**AP-eligible sensitivity (section 6):** 0 C-decodes matched the hash-resolution heuristic
(a same-ts leg-B decode, identical token-for-token except a `<...>` placeholder where C has a
resolved value). F_dec unchanged (+0.0 points) under exclusion. Given N3's finding, this null
result is unsurprising -- jt9 already out-decodes C outright, leaving little room for a C-only
decode that AP alone would explain -- but per the docstring's own disclosure, this is a heuristic
proxy (WSJT-X's `ALL.TXT` format carries no explicit AP-pass marker in this pipeline), not an
authoritative AP count.

---

## 6. Defect found and fixed en route: `endurance_anova_jt9.py`'s HHMMSS resolution

`run_jt9()`'s default path built **one dictionary**, keyed by bare `HHMMSS`, across the *entire*
input WAV list before batching, then reused that single dictionary to resolve every batch's jt9
stdout back to a full cycle timestamp. `parse_jt9_stdout`'s own docstring already warns that an
endurance session "commonly spans UTC midnight" and that a naive date assumption "would silently
mislabel" decodes -- but the global-dict construction recreated exactly that hazard one level up:
two WAVs on different calendar dates sharing the same time-of-day `HHMMSS` collide in the shared
dict (Python keeps whichever key was inserted last), silently misattributing every jt9 decode line
for the losing date to the wrong day's cycle for the rest of the run.

**Confirmed live, not hypothetical:** this corpus's +0s population (spanning 2026-07-31 and
2026-08-02) has **394 such collisions** across its 3,618 cycles. Both N3 and leg B needed this
fixed before their counts could be trusted -- this was found while building the population step,
before either jt9 run was launched.

**Fix:** build `hhmmss_to_ts` per batch, from only that batch's own files, rather than once
globally. Collision-safe by construction -- one batch's own time span is always far under 24h
(<=37.5 min at the default 150-file batch size), so no real collision can occur within a single
batch. A caller-supplied `hhmmss_to_ts` is still honoured unchanged, for any existing caller that
has already worked around this. This is a `qa/`-tooling change, not `src/` -- made directly per
HK-011 ("Docs/qa-tooling unaffected") and the precedent already set when QA extended
`anova_common.py` directly on 2026-08-02.

**Scope note:** `endurance_anova_jt9.py`'s own `main()` (its CLI entry point, used for standard
endurance-session ANOVA reports) also calls `run_jt9()` without an explicit `hhmmss_to_ts`, over
whatever WAV directory it's pointed at -- any past or future run of that CLI against a corpus
spanning multiple calendar days inherited this bug too. I have not audited past `anova_report_*`
outputs for whether any of them actually hit a collision (would require checking each corpus's own
WAV-name overlap, not done here) -- flagging as a possible follow-up, not asserting past reports
are wrong.

---

## 7. Artefacts written

Per Captain's instruction (2026-08-03, mid-turn): jt9's raw decode output saved alongside the
`ALL.TXT` it was compared against, ALL.TXT-format, per the existing `write_jt9_all_txt`
convention:

- `artefacts/20260731_live_run_2004-8080/wsjt-x/jt9_ALL_n3_calibration.TXT` (129,800 lines)
- `artefacts/20260731_live_run_2004-8080/owsfz/jt9_ALL_legB.TXT` (129,022 lines)

Intermediate JSON (population, per-step results) in `qa/cycleframer-alignment-replay/_work/`.

---

## 8. What this does NOT do

Same three boundaries the prereg itself stated, still respected:

- Does not touch the S.1 VOID.
- Does not address the density penalty (~19.8 pts) -- still needs its own pre-registration.
- Does not settle ~48% vs ~34% -- not attempted here, and moot anyway given the VOID.

## 9. Cross-references

- `2026-08-02-1813-architect-prereg-angle1-baseline-deficit-decomposition.md` -- the design executed.
- `2026-08-02-2316-architect-to-qa-handoff-t1-closed-and-corrected-scope.md` -- T4 authorisation, T1's population figure this cross-validates against.
- `qa/cycleframer-alignment-replay/measurement_angle1_population.py`, `_n3_calibration.py`, `_legb.py`, `_fdec.py` -- this measurement's own tooling.
- `qa/endurance/endurance_anova_jt9.py` -- the HHMMSS collision fix (section 6).
- `qa/cycleframer-alignment-replay/_work/angle1_*.json` -- raw computed results backing every number above.

---

*Per HK-015 this is QA -> Architect. Per HK-014/HK-010 nothing pushed, nothing merged, no sign-off
requested -- this is qa/-tooling plus an offline analysis, not `src/`. Per HK-017 filename and
byline carry real `date -u` UTC. Per HK-018 the population figure was cross-checked against T1's
own number before being trusted, not assumed to match. Per HK-021 the prereg's rows were evaluated
mechanically and in order, including reporting the row that fired even though the arm is VOID,
rather than substituting judgement for the written procedure. Per HK-004 the tooling defect
(section 6) was fixed directly, not merely flagged as a recommendation. NFR-021: no raw callsign
or message text appears anywhere in this note or in console output during its production --
duplicate characterisation in section 3 uses ts/SNR/DT/freq/message-length only.*
