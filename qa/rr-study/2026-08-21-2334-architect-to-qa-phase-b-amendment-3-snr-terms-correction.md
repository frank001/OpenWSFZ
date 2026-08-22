# Architect -> QA: Phase B AMENDMENT 3 -- corrections to Amendment 2

**Author:** Architect
**Date:** 2026-08-21 23:34Z (`date -u`, HK-017)
**Status:** SPEC ONLY. NOT BUILT. HK-011 engaged (native + `src/`).
**Amends:** the 23:11Z **Amendment 2** (`ft8_get_last_snr_terms`), commit `1729f6e`.
**Companion:** the 23:34Z preservation + **B-dt-A** document. That one is the RUN. This one
is the RECORD.

**Precedence.** Where this document and Amendment 2 conflict, **this document wins**.
Amendment 2's own precedence clause (1525Z beats it) is unchanged and still applies to
everything neither document touches.

**Amendment 2 is not withdrawn. It is corrected, and it is now CONDITIONAL** on
B-dt-A ROW 2 firing. See section 5.

---

## 0. Why this exists

I reviewed Amendment 2 against the code and re-derived its evidence from the raw CSVs
rather than trusting my own quotation of them. The code citations were exact. **The
inference was wrong**, and three of the acceptance criteria have defects -- one of them
structural.

This document records what was wrong, in place, rather than silently reissuing Amendment 2
with better numbers. The audit trail is worth more than a tidy document.

---

## 1. CORRECTION 1 -- section 1.3's central claim is RETRACTED

Amendment 2 section 1.3 states:

> "**The mechanism is unidentified and cannot be identified from outside the shim.**"

**Retracted. It was identifiable from outside the shim, from data already on disk.**

The mechanism is keyed to **true DT**, not to signal crowding. Full derivation, tables and
the discriminator against a synthesis artefact are in section 2 of the companion B-dt-A
document; not duplicated here.

Summary of the correction:

| Amendment 2 said | Actually |
|---|---|
| Error is a single-signal vs multi-signal split | Error is a `true_dt == 0` vs `true_dt > 0` split |
| Multi-signal is the trigger | Multi-signal was a **confound** -- all S4/S7/S8 parts are synthesised at DT 0.0 |
| 650 vs 1650 Hz split is unexplainable | It is a DT split; 1650 Hz is one of the few S8 stations at DT > 0 |
| Mechanism not identifiable outside the shim | Identifiable, and identified, by one stratification |

This is HK-018 in the exact form the rule describes -- a paragraph of reasoning standing in
for a five-minute measurement that was already available.

---

## 2. CORRECTION 2 -- section 1.2's evidence table is WRONG for S3

Amendment 2 section 1.2 gives the single-signal OpenWSFZ range as **"+1.0 .. +1.2 dB"**
across S1, S1b, S2, S3. Re-derived from `results/2026-08-21-7d36038/*_matched.csv`:

| Scenario | Amendment 2 | Actual mean | Actual median |
|---|---|---|---|
| S1 | +1.0 .. +1.2 | +1.08 | +1.10 |
| S1b | +1.0 .. +1.2 | +1.17 | +1.00 |
| S2 | +1.0 .. +1.2 | +1.00 | +1.00 |
| **S3** | +1.0 .. +1.2 | **-0.20** | +1.50 |

**S3's mean is negative and sits outside the range I quoted.** The scenario-level mean hid
a bimodal distribution: S3 part 0 (DT 0.0) reads -16.0 dB, parts 1-9 read +1.0 .. +2.0.

The corrected table is the DT stratification, not a per-scenario one. **A per-scenario
aggregate is the wrong cut for this defect** -- which is the same identifiability argument
Amendment 2 section 2.2(b) makes correctly about per-decode vs per-cycle, applied one level
up and missed.

The WSJT-X ranges also want widening: single-signal is **+0.5 .. +0.9** as stated only if
S2 (+0.93) is rounded down. Use **+0.5 .. +1.0** across all seven.

**Unaffected and still exact:** n = S4 96 / S7 147 / S8 50; the 650/1650 figures
(-20.0 / -1.8, an 18 dB split); and the entire HK-022 basis of the amendment -- H5 at
`20260011` predating the local noise floor at `20260012`. That argument stands untouched.

---

## 3. CORRECTION 3 -- AC-N1 gates on a binary that section 7 destroys

**Structural, and the reason the companion document's TASK 1 is urgent.**

AC-N1 requires a replay diff "against the pre-Amendment-2 Phase B binary." That binary is
**uncommitted** -- last commit touching `libft8.dll` is `5d3cac5`, shim 20260043,
pre-Phase-B -- and section 7 step 2 rebuilds in place over it.

**AC-N1 as written becomes unrunnable at the moment the Developer session starts.**

Corrected AC-N1 (replaces Amendment 2 section 5 AC-N1 in full):

> **AC-N1 -- INERTNESS. GATES.**
> **Precondition:** the archived Phase B binary from TASK 1 of the companion document
> exists and verifies against its recorded SHA256
> (`a3d32b78...` win / `13d9799d...` linux). If it does not, **STOP** -- the reference is
> gone and inertness cannot be established at all.
> Re-run `r0_ac1_ac2_diff.py`, 250 cycles, BOTH platforms, new binary against that
> **archived** reference. **Required: ZERO decode differences.** Any non-zero difference
> => **STOP and escalate.**

**Attribution, which Amendment 2 asserted without stating:** the guard fix rides the same
rebuild (section 7), so a reader is entitled to ask whether a decode diff could come from
it rather than from the getter. It cannot. `ftx_ldpc_decode_llrs` is called from exactly
one place -- `ft8_ldpc_decode_llrs` at `ft8_shim.c:1656`, the diagnostic export -- and
never from `ft8_decode_all`. Verified by grep across `patched/ft8/` and
`src/OpenWSFZ.Ft8/Native/`. The guard fix is provably off the decode path, so AC-N1's
consequence ("it is not read-only") does follow. **State this in the report; do not make
the next reader re-derive it.**

---

## 4. CORRECTION 4 -- three smaller acceptance defects

**(a) AC-N2's threshold sits exactly on the quantum.** The gate is
`abs(... - snr[i]) <= 0.5`, and 0.5 dB is precisely the maximum error of `(int)roundf`.
A conforming implementation can produce exactly 0.5, which in float may compare as
0.5000001 and fail a correct build.
**Corrected:** `<= 0.5 + 1e-3`. The epsilon is a float-representation allowance, not a
loosening of the criterion -- the next distinguishable failure is a full quantum away.

**(b) AC-N4's capacity cases are degenerate on quiet cycles.** `capacity = count - 1` is
undefined when `count == 0` and equals 0 when `count == 1`, collapsing two of the three
cases.
**Corrected:** run AC-N4 on a cycle with `count >= 3`, asserted before the case is
evaluated; if no such cycle occurs in the run, report that and re-run on a denser scenario
rather than evaluating the degenerate case (HK-021(n)).

**(c) The contract has an unspecified case.** Amendment 2 section 2.1 says either out
pointer may be NULL. **Both NULL is not specified.**
**Corrected:** with both NULL, the function writes nothing and returns the count it would
have written. Add this to the doc comment and to AC-N4.

**(d) Section 4 cites `build_linux.sh:43` with no path,** and three copies exist -- the
live one is `native/ft8_lib_build/build_linux.sh`; the other two are under
`.claude/worktrees/`. Line 43 (`gcc -shared`) is correct in the live copy. Use the full
path.

---

## 5. CORRECTION 5 -- AC-N5 becomes a real measurement, and Amendment 2 becomes conditional

**Amendment 2 is now CONDITIONAL on B-dt-A ROW 2 firing** (companion document, section 3.5).
If ROW 1 fires -- the Phase B origin fix already resolves the collapse -- the getter is
**DEFERRED pending re-scope**, and no Developer session is opened on it.

If ROW 2 fires, AC-N5 replaces Amendment 2's version in full:

> **AC-N5 -- THE MEASUREMENT. REPORTED, NOT GATED.**
> Run S3 (the DT sweep) and S8. For every decode report `signal_db`, `local_noise_db`,
> the reconstructed SNR, and `true_dt`.
> **Stratify by `true_dt`, not by scenario, and not by neighbour density.**
> The question is now specific: **at `true_dt == 0`, which of the two terms moves?**
> Still no threshold and no pass/fail -- but it is no longer "we do not know what we are
> looking for." We do.

Amendment 2's rationale for exporting **both** terms (section 2.2(c)) was correct and is
now load-bearing rather than precautionary: the whole measurement is which term carries
the collapse. That design decision, and (a) and (b), all stand unchanged.

---

## 6. CORRECTION 6 -- my section 8 predictions are INVERTED

Amendment 2 recorded:

| Prediction | Confidence I gave |
|---|---|
| The isolated-vs-crowded difference localises to `local_noise_db` | 75% |
| The 650/1650 Hz split localises to `local_noise_db` | 60% |

Both rows are built on the crowding framing that section 1 above retracts, so neither is
answerable as written. On the DT framing, a displaced analysis window would make
`signal_db` low while leaving `local_noise_db` roughly correct -- **the opposite term.**

Corrected and re-recorded, replacing those two rows:

| Prediction | Confidence |
|---|---|
| The `true_dt == 0` collapse localises to `signal_db`, not `local_noise_db` | 80% |
| `local_noise_db` at `true_dt == 0` is within 3 dB of its `true_dt > 0` value | 65% |

The other three rows of Amendment 2 section 8 (AC-N1 zero-diff 95%, AC-N2 passes 85%,
a third mechanism proposal needed 40%) are unaffected and stand.

**Calibration note, recorded rather than buried:** this is the third failed mechanism claim
from me on this dataset. Two were proposals refuted by the data; this one was an assertion
that the data *could not* answer the question, refuted by the data I already had. The first
kind is normal science. The third is not, and the predictions above should be read at a
discount because of it.

---

## 7. What is unchanged from Amendment 2

Everything not listed above, specifically:

- The symbol, its signature, and the parallel-array design (section 2.1, 2.2(a)).
- Per-decode rather than per-cycle aggregation (2.2(b)) -- and the DT finding **strengthens**
  it: the collapse is a between-decode, within-cycle difference in S8.
- TLS storage sized `K_MAX_DECODED`, reset per `ft8_decode_all` (2.3). `K_MAX_DECODED` is
  defined at `ft8_shim.c:552`.
- The version bump 20260044 -> 20260045 and the managed pin at
  `Ft8LibInterop.cs:335` (section 3), and the reasoning that a new export is an ABI change.
- The Windows `/EXPORT:` requirement at `rebuild_shim.bat:139-153` (15 exports today), the
  Linux no-op, and the `dumpbin /exports` verification (section 4).
- AC-N3 (count contract) in full.
- Section 6's whole "does not license" list -- H5 stays closed, the SNR formula and
  suppression stay untouched, no bearing on ROW 0g / task 4.3 / Route B2 / B3.
- Section 7's sequencing: one rebuild carrying both the guard fix and the getter, with
  `tasks.md` section 11 running **last**, on the final binary.

---

## 8. Order of operations, consolidated

1. **TASK 1** of the companion document -- archive the Phase B binaries. Blocking. Now.
2. **B-dt-A** -- the DT re-measurement on the post-B1 binary. No `src/` change.
3. **ROW 1 fires** => report, stop, Amendment 2 deferred. **ROW 2 fires** => continue.
4. Developer session: guard fix + getter + `/EXPORT:` + version bump + managed pin.
5. Rebuild both platforms; re-pin both SHA256s.
6. AC-N1 (corrected) .. AC-N4 (corrected) + the standing Phase B AC1/AC2.
7. AC-N5 (corrected) -- the DT-stratified measurement.
8. **THEN** `tasks.md` 11.1 -> 11.2 -> 11.3, unchanged.

Steps 4-8 do not begin unless step 3 reaches ROW 2.
