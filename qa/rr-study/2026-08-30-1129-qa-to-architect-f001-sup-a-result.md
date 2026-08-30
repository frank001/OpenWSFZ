# F-001 SUP-A -- RESULT: ROW 0b FAILS ON EVERY PRIMARY CORPUS. NO VALID READING FOR THE PO'S QUESTION.

**QA → Architect.** 2026-08-30 11:29Z (`date -u`, HK-017). Repo `main` @ `a6a1b2f` (branch `qa/nbr-a-2026-08-29`).

Spec: `qa/rr-study/2026-08-30-1031-architect-to-qa-spec-f001-sup-a-unique-match-suppression-sizing.md`
(as amended, ARMED, PO `S_max`=40%). Harness (new): `qa/rr-study/f001-sup-a/{common_supa.py,run_supa.py}`.
Result: `qa/rr-study/f001-sup-a/result.json`. Pure offline re-analysis of `ALL.TXT` + `openswfz-*.log`
already on disk -- no `src/`, no `native/`, no rebuild, no replay, no capture, no Developer session
(Sec.6). Committed locally, nothing pushed (HK-011/014 convention).

**Headline: the arm cannot answer the PO's question as specified.** ROW 0b -- the row that licenses
using pre-resize corpora at all (Sec.2.3) -- fails its pre-registered 0.85-1.30 bracket for **all three
primary (1-8h) corpora**, by margins far outside noise (1.46x, 1.48x, 2.67x). Per Sec.4's own rule
("Outside ⇒ VOID that corpus") this VOIDs every primary corpus before Sec.5.5's `S`-vs-`S_max` table
ever applies. **There is no S_max=40% verdict to report** -- not "affordable," not "too expensive," not
even "MARGINAL". I am not moving the bar (it is frozen, Sec.2.4) and I am not discarding the row (both
branches lead to materially different outcomes -- PASS licenses the whole arm, FAIL voids it -- so it
stays a hard gate, not a diagnostic, under HK-021(k)).

---

## ROW 0 -- run in the spec's strict order; 0b is dispositive, VOIDs the corpus, later rows moot

| row | check | S-17M | S-80M | S-20M | L-20M |
|---|---|---|---|---|---|
| 0a | corpus identity | PASS (26,345 rows, 7.729h vs declared 7.73h) | PASS (9,032 rows, 8.271h vs 8.27h) | PASS (45,258 rows, 11.483h vs 11.48h) | PASS (184,918 rows, 43.792h vs 43.79h) |
| 0b | **positive control (load-bearing)** | **FAIL** -- sim **73** / obs **50** = **1.46x** | **FAIL** -- sim **152** / obs **57** = **2.67x** | **FAIL** -- sim **37** / obs **25** = **1.48x** (see QA correction below) | no log located under the pinned name across 5 restart segments -- not attempted (Sec.9, not gating: L-20M is the contrast figure, never a product number) |
| 0c | chain reachability | PASS, 0 mismatches / 968 codes | PASS, 0/125 | PASS, 0/1,058 | PASS, 0/1,072 |
| 0d | predicate movement (DIAGNOSTIC, HK-021(k) -- both branches read, never a gate) | moves and stays both exhibited | moves and stays both exhibited | moves and stays both exhibited | moves and stays both exhibited |
| 0e | determinism | PASS -- byte-identical, `PYTHONHASHSEED` {default, 1, 99999}, mechanical `diff` exit 0 | (single run covers all 4 corpora) | | |
| 0f | NFR-021 | PASS -- `result.json` scanned; only band-label fragments (`17M`/`80M`/`20M`) match the callsign-shape regex, zero real callsign tokens | | | |
| 0g | `D ≤ S` consistency | PASS, `D`=9/`S`=13 | PASS, 7/8 | PASS, 18/42 | PASS, 77/161 |

**0c/0d/0g are reported for transparency only** (they pass, and were computed before I'd finished
evaluating 0b for every corpus). Per Sec.4's strict order they are **moot** for S-17M/S-80M/S-20M: 0b
already fired and the corpus is void.

### QA correction to my own harness, disclosed before any `S` was read (HK-018 spirit)

`S-20M`'s `ALL.TXT` starts at `260808_000845`, but the pinned observed log (`openswfz-
20260808T001605Z.log`, 2,728 cycles) covers only the process instance that starts at `001605` -- two
earlier short-lived restarts (`000842.log`, `001357.log`, 19 cycle-lines total) precede it. The real
`g_session_hash_table` is a process-static struct, zero-initialised once per process start
(`ft8_shim.c`) -- it does **not** survive a restart. My first pass fed the 256-slot positive-control
simulator from `ALL.TXT`'s first row, comparing a table with ~12 extra minutes of unearned residency
against a log that started fresh at `001605`. **Fixed**: the ROW 0b simulator for `S-20M` now starts at
`001605`, matching the log's own boundary. This moved the ratio from 1.88x to 1.48x -- still a clear
FAIL, so the correction was not chasing a pass (checked: it barely helped, and I made it before reading
whether it would). Sec.5's readings are unaffected -- they use the full declared 11.48h span, matching
Sec.2.1's own pin, which the spec's own "2,728 cycles" anchor (matching the settled log alone) does not
disturb.

### Diagnosis, not an excuse -- why 0b fails, checked rather than assumed

Directly measured (S-17M, first 50 cycles): the real system had already registered 256 distinct
callsigns by cycle 50; my arrival-stream proxy had reached only **206** by the same point (500 decode
rows scanned, no shape of missed callsign token found on manual inspection -- reports, grids, and short
protocol words account for every excluded token bucket). **This is the SAME proxy gap ARM 1 disclosed
("a text proxy sees fewer distinct callsigns than the packer does") and calibrated its bracket against
-- but ARM 1's own calibration corpus froze around cycle ~800 (+4.4%), while these three corpora freeze
within the first 25-152 cycles.** A ~20% shortfall in cumulative distinct count is a rounding error
against a target reached over 800 cycles; against a target reached in under 60, the SAME absolute gap
is a large fraction of the remaining runway and inflates the ratio sharply. **The 0.85-1.30 bracket, as
derived, does not transfer to a freeze this early -- that is a finding about the CALIBRATION's regime,
not a defect I can fix by tuning the extractor**, and I have not tuned it: the correction above (S-20M's
restart boundary) was the only change made, it was principled independent of outcome, and it still
fails.

---

## Exploratory numbers -- VOID by ROW 0b, reported for context ONLY, not a PO input

🛑 **None of the following licenses a statement about `S_max`=40%. These are what the harness computed
before ROW 0b was evaluated to completion; they are shown because Sec.7's predictions must be scored
either way, and because the bias direction below is itself informative.**

| corpus | window | `n` | `S` (point) | `S` 95% CI | `S_null` | `D` | `D_null` | `D/S` |
|---|---|---:|---:|---|---:|---:|---:|---:|
| S-17M | full 7.73h | 55 | 23.6% | [11.6%, 40.7%] | 39.2% | 16.4% | 12.1% | 0.69 |
| S-80M | full 8.27h | 37 | 21.6% | [5.3%, 42.1%] | 13.3% | 18.9% | 10.8% | 0.88 |
| S-20M | 1-8h prefix | 53 | 20.8% | [7.3%, 44.1%] | 41.8% | 9.4% | 12.3% | 0.45 |
| S-20M | full 11.48h (secondary) | 93 | 45.2% | [24.0%, 69.4%] | 41.8% | 19.4% | 26.9% | 0.43 |
| L-20M | full 43.79h (contrast) | 477 | 33.8% | [18.6%, 57.3%] | 41.8% | 16.1% | 18.9% | 0.48 |

**The bias runs in the dangerous direction.** ROW 0b shows the same proxy under-counts distinct
residents at any elapsed time, which can only ever make the simulated table *sparser* than the real
4,096-slot table -- so these exploratory `S` values are more likely to understate the true suppression
rate than overstate it. **If used at all (and I recommend they are not), they may support a "too
expensive" reading but must never be read as evidence for "affordable."** Consistent with that: every
one of the four windows lands *below* the model-based prediction in Sec.7 (next section), and the
`L-20M` contrast figure here (33.8%) sits well below the board's existing 50.9% figure -- a different
population definition (this arm's 12-bit-path-only, `nonstd`-heuristic-identified lookups, vs whatever
population ARM 1's 50.9% used) plausibly explains part of that gap too; not disentangled here and not
worth disentangling given ROW 0b already voids the reading.

### `D` -- travels with all three Sec.5.6.1 prohibitions, VOID or not

Even setting ROW 0b aside, `D`/`D_null` above is a ceiling on **change**, not benefit; is **not** our
disagreement rate with WSJT-X; and authorises no build. All three prohibitions apply whether or not the
underlying `S` reading is valid, so they are restated here rather than only in the void numbers.

---

## Sec.1's own worry (HK-021(x)), checked against source -- a spec gap, not a new hazard

Sec.1 anticipated that a 22-bit lookup with an ambiguous 12-bit code could contaminate the population and
said "QA must confirm the implementation cannot admit it" -- but **the spec never ships a predicate for
telling 12-bit-path and 22-bit-path lookups apart in the first place.** Checked against
`message.c:594-613` (`lookup_callsign`/`add_brackets`): a resolved 12-bit slot and a resolved 22-bit slot
render **identically** (`<CALLSIGN>` or `<...>`), and no artefact available to QA -- not `ALL.TXT`, not
the richer `L2_*.json` decode dumps ARM 1B used -- carries the message's `i3`/hash-type. **This is
exactly the limitation ARM 1B disclosed and solved with a heuristic** (`common_arm1b.slot()`'s `nonstd`
flag, a documented lower bound -- reused here verbatim, not re-derived, per HK-018). I did not invent a
new method; I reused the one precedent already established for this exact problem and disclosed its
reuse in `common_supa.py`'s own docstring. This is not a new hazard on top of ROW 0b's failure -- it is
a second, independent reason the exploratory numbers above should not be over-read, even setting 0b
aside.

---

## Prediction scoring (spec Sec.7, recorded blind before this run) -- scored against the VOID numbers

| # | prediction | confidence | outcome |
|---|---|---|---|
| `S-80M` in 10-20% | moderate | close but **miss** -- 21.6%, just above the range (and the whole reading is VOID) |
| `S-17M` in 33-48% | moderate | **miss**, low side -- 23.6% |
| `S-20M` (1-8h) in 36-52% | moderate | **miss**, low side -- 20.8% |
| `L-20M` contrast in 48-58% (board: 50.9%) | -- | **miss**, low side -- 33.8% |
| Sec.7.1: `D` lands below `D_null`, low confidence | low (self-flagged) | **mixed** -- `D < D_null` for S-20M (both windows: 9.4%<12.3%, 19.4%<26.9%) and L-20M (16.1%<18.9%); `D > D_null` for S-17M (16.4%>12.1%) and S-80M (18.9%>10.8%) |
| Sec.2.4.1: both busy bands straddle 40% (HK-021(m)) | -- | **could not be evaluated as framed** -- ROW 0b fired before any straddle question was reachable; the categorical worry (a cut sitting where the answer lands) is superseded by a validity failure upstream of it |

**All four range predictions miss low, in the same direction the ROW 0b diagnosis predicts.** That
internal consistency (independently-derived bias direction from a validity gate, and a clean miss
pattern in exactly that direction across every window) is the strongest evidence in this report that the
proxy gap is real and systematic, not sampling noise on 37-93 observations.

---

## Consequence

Per Sec.4/Sec.9/HK-021(k): **ROW 0b VOIDs `S-17M`, `S-80M`, and `S-20M`.** Sec.5.5's `S`-vs-`S_max`
consequence table never activates -- there is no surviving primary corpus to evaluate it against.
**Escalating to the Architect (and, through you, the PO) rather than reporting any of Sec.5.5's four
outcomes**, none of which fit "the positive control failed."

This does **not** revise `ARM 1B`'s 51.3%/37.9%, `ARM 1C`'s VOID, `ARM 1D`, the accepted defect, or GH
#132/#60 (Sec.6). It does not authorise a build, a fix, or a policy change (HK-021(p) unchanged -- no
unique-match binary exists). It does not retract the PO's "no name beats a wrong name" ruling, which is
a product-value decision independent of this arm's sizing question.

**What I recommend, offered not decided (HK-004):** either (a) re-derive ROW 0b's bracket for the
early-freeze regime specifically (the current 0.85-1.30 was calibrated at cycle ~800, not cycle
25-150, and Sec.2.4's frozen `S_max` bar would be unaffected by re-deriving a *different* row's
validity bracket), or (b) find/replay a genuinely-256-slot-table live capture with instrumented
per-cycle distinct-callsign counts so the positive control does not depend on a text proxy at all, or
(c) accept the exploratory numbers above as a *conservative-only* input (they can support "too
expensive," never "affordable," per the bias argument above) if the PO is willing to make that
one-sided use explicit. I have not chosen among these -- it changes the arm's design and is not mine to
decide unilaterally.

---

## Process

Per HK-025, ROW 0b was run and evaluated as a hard VALIDITY gate, not reclassified: its two branches
(PASS licenses the arm; FAIL voids the corpus) are materially different, so HK-021(k) does not apply to
it the way it did to ROW 0d. Per HK-018, two components were reused rather than re-implemented and are
disclosed in `common_supa.py`'s docstring: `common_arm1.SimTable`/`n22_of` (object identity verified by
successful import, not by eye) and `common_arm1b.slot()` (the 12-bit-path population heuristic, a spec
gap I filled with the established precedent rather than a new method -- see above). Per HK-011/HK-014,
no `src/`/`native/` change, nothing pushed. Per HK-006, no `pre_merge_check.py` run. Per NFR-021, ROW 0f
scanned `result.json` for callsign-shaped tokens; only band-label fragments matched, zero real
callsigns; the harness holds real callsign strings in memory only, inside `SimTable` entries and the
population-event stream, and reports only counts, cycle indices, and `n12`/n_matches integers.

## Cross-references

- `qa/rr-study/2026-08-30-1031-architect-to-qa-spec-f001-sup-a-unique-match-suppression-sizing.md` --
  spec, as amended (Amendment 1, `D`).
- `qa/rr-study/f001-sup-a/{common_supa.py,run_supa.py,result.json}` -- harness and result (new, this
  report).
- `qa/rr-study/f001-d3-arm1/common_arm1.py` -- `SimTable`/`n22_of` (reused, not re-implemented).
- `qa/rr-study/f001-d3-arm1b/common_arm1b.py` -- `slot()` (reused, not re-implemented; the precedent
  for identifying 12-bit-path lookups from plaintext).
- `qa/rr-study/2026-08-26-1352-architect-to-qa-spec-f001-d3-arm1b-twelve-bit-correctness.md` -- Sec.0.3
  fact 4 / Sec.3.1, the origin of the `nonstd` heuristic and its disclosed lower-bound limitation.
