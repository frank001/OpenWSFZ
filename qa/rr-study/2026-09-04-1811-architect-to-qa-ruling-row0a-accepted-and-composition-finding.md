# `FP-REGRESSION` -- Architect ruling on E2 / ROW 0a, and a finding that reaches the arm's premise

**Architect, 2026-09-04 18:11Z** (`date -u`, HK-017). Adjudicates
`2026-09-04-1537-qa-to-architect-fp-regression-e2-result.md` (commit `e644155`).

**Two things in here, and they carry different weight.** Sections 1-5 are the ruling on E2 and are
mine to make. **Section 6 is a finding about the ratified in-chain contrast that this arm was
commissioned to explain, and it REQUIRES PO RATIFICATION before any board figure moves.** Nothing in
section 6 has been applied to the board's ratified numbers.

---

## 1. ROW 0a's fire is ACCEPTED. The bisect is VOID. E3/E4 must not run.

Verdict independently reproduced from the committed CSVs, not read off the report:

```
n = 4000   n11 = 435   n10 = 0   n01 = 0   n00 = 3565
rate(B1) = 10.8750%    rate(B8) = 10.8750%    signed diff (B8-B1) = +0.0000 pp
n_decodes differs on 0 of 4000 slots
```

`diff = 0 ≤ 0` ⇒ **FIRES** ⇒ per spec §4 and the pack, the bisect is void. QA stopped on the firing
branch at HARD STOP 2 exactly as written, did not widen the corpus, did not check one more binary,
and did not improvise the re-scope. That is the pack working as designed.

## 2. The harness is CERTIFIED -- the same-binary artefact is excluded

A result of "identical decode sets" has one dangerous alternative explanation, and it is a real
Windows behaviour, not a hypothetical: `LoadLibrary` returns a handle to an already-loaded module of
the same base name, and every one of these binaries is `libft8.dll` in the repo. Both were loaded
into **one process** via `ctypes.CDLL`, so the risk was live. It is excluded on four independent
grounds:

1. **Distinct base names on disk** -- `B1_3bd4cd0_libft8.dll` / `B8_c3a9ea8_libft8.dll`; the
   collision condition never arises.
2. **Distinct sizes** -- 55,808 B vs 215,040 B (a ~4x difference; the vendored-toolchain rebuild
   `3bc2b9d` sits in this window).
3. **SHA256 asserted at load**, both matching the pre-registered manifest.
4. 🔴 **Decisive: `ft8_lib_version_check()` returned `20260033` from one handle and `20260046` from
   the other.** A cached module cannot answer with two different versions. Two live modules ran.

Corroborating: the outputs themselves diverge (below). Had they been byte-identical, the null would
have been uninterpretable. **QA's supplementary diagnostic is what makes the primary result
readable** -- it should be understood as the instrument's own positive control, not as a decoration.

## 3. CORRECTIONS -- three supporting figures in the E2 report are wrong

The verdict is untouched. These matter because they will be cited later.

| E2 report | Correct | What went wrong |
|---|---|---|
| `reported_snr_db` differs on **226 of 435** | **241 of 435 (55.4%)** | 226 is the count over the **416** single-decode slots; the 15 differing multi-decode slots were described in a footnote and then omitted from the headline, leaving a numerator and a denominator from two different populations. |
| "**15** slots carry 2 decodes each" | **19** slots carry 2 decodes | 15 is the number of multi-decode slots whose SNR *differs* -- a different quantity from the number that exist. (454 decode rows = 416x1 + 19x2.) |
| "small **±1-2 dB** shifts" | **Directional: `{-2:2, -1:18, +1:146, +2:76, +3:7, +4:1}` -- 230 of 250 positive** | An absolute-value framing erased the sign. **B8 reports systematically HIGHER SNR on noise than B1.** HK-021(l) is this project's own rule: signed, never `|x|`. |

`freq_hz` = 0 and `dt_s` = 0 differing slots, and `message` = 3, are confirmed exactly as reported.

**Disposition (PO-ratified):** this ruling carries the corrected figures and the board carries them;
the E2 report stays an untouched record of what QA reported. Cite this document, not the E2 table.

## 4. WHY ROW 0a fired -- a structural reason, not an instrument fault

The offline harness calls `ft8_decode_all` and counts event slots. **The in-chain FP metric is not
that quantity.** In-chain, every native decode passes through `Ft8Decoder.cs`'s managed
message-plausibility filter -- shape grammar, digit-run limits, token-count rules, prefix/suffix
validation (the code whose own comment says it "rejects `3AG9672ATCH`-class noise") -- before
anything reaches the metric.

⇒ The in-chain rate is a function of **two** layers. The offline instrument sees **one**. A native
DLL bisect can only ever localise within the native layer, and the offline seam is blind by
construction to the other. **ROW 0a was the correct gate and it did its job**: it detected that the
instrument does not span the space the question lives in, before four more blocks were spent
bisecting inside it.

🛑 **What ROW 0a does NOT license, and this is the trap:** it does **not** show the native DLL is
innocent. Its response is flat across B1→B8, and **an instrument may not be used to bound a region
where its response is flat** (HK-026, verbatim). "The regression is not in the native decoder" is
**barred** as a conclusion from this data. It is available only as a hypothesis for an instrument
that spans both layers.

**Recorded so it cannot steer a gate (§7 treatment, same as the barred `9500e03` hypothesis):** the
systematic upward SNR shift in §3 is a candidate mechanism for an in-chain rise that ROW 0a cannot
see -- SNR is computed *after* the accept decision, so a shift moves no offline event slot, while any
downstream SNR-dependent handling in the product would convert it into visible decodes. **No block
may test this first, and no block may stop when it fires.**

## 5. The leading post-hoc hypothesis is DISCONFIRMED as a rate mechanism -- by its own commit message

`9500e03` (`HASH_TABLE_SIZE` 256 → 4096) was recorded in spec §7 as the leading candidate and
deliberately barred from being tested first. Its own commit message states the scope:

> "SCOPE: this buys message TEXT only (fewer `<...>` where a resolvable callsign exists). **It CANNOT
> change the decode count** -- message.c's two call sites already discard a hashed callsign's
> resolution failure without affecting whether a decode is produced."

ROW 0a observed exactly and only that: **decode counts identical on all 4,000 slots; message text
differing on 3.** The hypothesis predicted a text-only effect; a text-only effect is what the data
show. It therefore **cannot** be the mechanism for a *rate* change.

⚠️ This is a **consistency finding, not an attribution** -- E1.3's bar stands, no commit is named as
a cause of anything. It removes a candidate; it does not appoint one.

## 6. 🔴 FINDING REQUIRING PO RATIFICATION -- the ratified contrast is not composition-controlled

**Nothing here is applied to any board figure. This is put to the PO, not decided.**

Read Section 6 of `results/2026-09-03-35378b9/report.md` before reading further (HK-031), and read
its closing caveat, which states the problem in the study's own words:

> *"S5's default N dropped from 120 to 60 slots starting 2026-08-27 (R&R-009, AWGN parts only).
> Early-vs-late numbers are as-reported; treat cross-redesign comparisons as directional, not
> strictly statistical."*

**The mechanism.** `58bc7ac` (R&R-009, 2026-08-23, effective from the 2026-08-27 sweep) restricted
the default S5 battery from four parts (N=120) to AWGN parts 0,1 only (N=60), on the documented
ground that **parts 2/3 produced exactly 1 of 53 all-time FP events and parts 0/1 produced 52.**
Verified from the scenario file: `trials: 30`, four parts ⇒ 120 slots, of which parts 0/1 = **60
AWGN slots**.

⇒ Parts 2/3 contribute **denominator but essentially no numerator**. The same underlying per-AWGN-slot
propensity therefore reads **~2x higher** in the N=60 battery than in the N=120 battery, mechanically.

**The pooled windows are not composition-matched:**

| Window | Composition | Slots | AWGN slots |
|---|---|---|---|
| Pre (08-05 → 08-21) | **100%** N=120 4-part sweeps (`3bd4cd0`, `8d6e1b1`, `7d36038`) | 360 | 180 |
| Post (08-22 → 09-03) | **mixture** -- `f5dec23` (N=120) + `2e60949` (N=120, footnote 4: R&R-009 not applied on resume) + four N=60 AWGN-only sweeps | 480 | 360 |

**Re-derived on a common per-AWGN-slot basis:**

| | As ratified (raw slots) | Composition-normalised (AWGN slots) |
|---|---|---|
| Pre | 2/360 = 0.556% | 2/180 = **1.111%** |
| Post | 13/480 = 2.708% | 13/360 = **3.611%** |
| Ratio | **4.88x** | **3.25x** |
| Fisher one-sided | **p = 0.0154** | **p = 0.0765** |
| 95% CP | -- | pre [0.135, 3.956]% vs post [1.937, 6.096]% -- **overlapping** |

🛑 **STATE THE CONCLUSION CAREFULLY. This is NOT a return to "no regression."** The direction is
unchanged and the point estimate is still a ~3x rise; the regression remains the best reading of the
data. What does **not** survive normalisation is the **significance claim** the arm was built on. The
Architect's original denial stays wrong for the reasons already ruled (a circular comparator, and
Section 6 unread) -- this is a third, separate defect in a figure both sides have been citing.

**Checked and cleared, so it is not raised as a confound:** the 2026-09-03 S5-LEVEL correction
(`level_dbfs` deleted, parts 0/1 shown to be two replicates of one level) was documentation-only --
**ROW 0j asserted byte-identical delivered audio, 60/60 SHA256.** The stimulus did not change.

**The one assumption I did NOT verify, and QA must:** that all 15 FP events fall in parts 0/1. It is
strongly supported (52/53 all-time) but assumed here. **R&R-009's own per-part attribution
machinery already exists** -- `58bc7ac` built it precisely because `matcher.py` never records
`part_index` on FP rows and an unscoped `ALL.TXT` read over-attributes. **Re-running that
reconstruction over the 15 events settles it with no decode and no capture.**

**Consequence if the PO ratifies:** `4.88x` / `p = 0.0154` is retired the way this project retires
figures, and any re-scoped arm is powered against a **~3.25x** effect, not a 4.88x one -- which is a
materially larger n. It also makes ROW 0a's exact null less surprising: a weaker true effect is
harder for any instrument to see.

**Proposed standing rule, for the PO:** HK-031 currently says *check a pooled comparator's date span
against the effect's*. It was created for exactly this failure and the composition variant walked
straight past it. ⇒ **"...and its population COMPOSITION, not only its date span. A denominator
change is a redesign even when the metric's name does not change."**

## 7. What happens next -- Architect's, and blocked on the PO

- **`FP-REGRESSION` E3/E4: barred.** The arm's re-scope is not drafted in this document.
- **Blocked on PO ratification of §6** before the re-scope is specified at all: the effect size a new
  arm must be powered for is the first input to its design, and it is currently in dispute with
  itself.
- **First QA task once ratified (no decode, no capture):** re-run R&R-009's per-part attribution over
  the 15 FP events in the two windows and report per-part counts, so the normalisation in §6 rests on
  measurement rather than on the 52/53 prior.
