# RULING — OSD-FIX build review: three items from QA (speed-test re-baseline, R6 diagnostics, TRAIN count)

- **To:** QA (owner). cc Captain. **From:** Architect. **Date:** 2026-10-08 16:30Z (`date -u` 16:25Z at drafting, HK-017).
- **Rules on:** QA's cross-session message of 2026-10-08 (build `feat/osd-sign-fix` `3048176d`, local, shim 20260060, DLL SHA `60d5e70a…9187`; QA's U1/U3/U5 PASS).
- **Branch:** `arch/osd-fix` (local). Docs only: `git diff --stat -- src/ native/` is empty.

## 1. `SubfeasNativeSpeedTests` 8.1: **ACCEPTED as done**, with one small addition

Read at `3048176d`: `Pass0JobsAsRecorded` sets the switch to 0 only while the pass-0 job list is enumerated, then restores it. The golden `e1-base-5a6a4dc0.csv` is **not** re-pinned and is still compared exactly (5 rows).

That is the right choice. The test measures the **fit** against the base DLL, and the job list is only its input. Enumerating at switch 0 reproduces the recorded input exactly, so the comparison stays like-for-like. A golden re-recorded on the corrected build would be a new reference made by the code under test. As a side effect, the unchanged 5-row golden is extra R7 evidence: switch 0 still produces the 2 chance-CRC accepts.

**Addition (goes into the same small commit as §2):** one assertion that at switch **1** the pass-0 job list on `synth-qso-01` is exactly the **3** answer-key messages. The test then records what the fix changed, not only what it preserved. The PR lists the re-baseline under R5(d) with this reason.

## 2. R6 diagnostics: **YES, a separate small native commit, before TRAIN**

R6 required them: *"If the per-accept `nhard` and corr are not already returned to the harness, the Developer returns them"*. They are not returned. At `3048176d` the only writes are behind `#ifdef NHARD_DIAG` (`decode.c:679`, `:711`, `:749`, `:1105`, `:1131`, `:1158`), which is compiled out, so the shipped DLL records nothing. Without them, the mandatory `nhard` histogram (§5.3) cannot be produced, and neither can the evidence a different gate would be designed on after a `FIX-NO-GATE` verdict. TRAIN is the 8 h run that should carry them. Running it without them and again later would cost a second night.

What the commit must do:

- **What to return:** for each accepted OSD decode, `nhard`, `corr/norm`, `depth` and batch, through the existing per-decode outcome path (a struct field or out-array). No file I/O in the decode path. Numbers only, no text (HK-037).
- **Rejected candidates:** for gate rejections, a per-cycle count by reason (`nhard`-cap / corr). A count, not a list.
- **Must not change any decode:** at both switch values, decode outputs are identical to `3048176d` on QA's characterisation set (mechanically diffed).
- **Identity:** it is the **same unmerged change**, so the shim number stays 20260060 if `check_native_version` allows it, otherwise the next free number. The DLL SHA changes either way, and **the SHA is the identity** pinned in V1.
- **Re-runs:** A-SIGN′, A-OFF and the V2′ probe recalibration run on the **final** DLL (after this commit), not on `3048176d`.

## 3. TRAIN cycle count: **621 stands; 622 was my arithmetic**

The frozen lists give 311 + 310 = 621, which matches the OSD-OFF ruling's pooled count ("in 621"). The spec's 622 was my error. `selection.json` at `qa/osd-fix` `1f30263b`, SHA-256(LF) `27bb840f…db11e`, is accepted as the frozen TRAIN set. Nothing else in the spec depends on the number.

## 4. Order from here

Developer: the §1 + §2 commit → QA: U-checks on the final DLL, A-SIGN′, A-OFF, `--osd-sign-fix` flag, V2′ recalibration (committed) → **TRAIN, on the Captain's go**. TRAIN needs the **PC only** (offline replay of recorded audio), about 8 h of wall time, and can be split across sessions (every arm pins the DLL).
