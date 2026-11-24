# TA-RES R0 (route R, desk check): the capture harness builds on today's stack and captures the buffers that batches 4 and 5 decode from. One gap: per-decode provenance of a batch-4 row is not recorded.

**Written:** 2026-11-13, `date -u` read 10:28:13Z. **To:** Architect, then the Captain. **Authority:** the Captain's "go for route R" (R0 only). **Ruling basis:** `qa/rr-study/2026-11-13-1021-architect-ta-mask-ruling.md` §3 (R0). No PC window: the smoke below ran 3 cycles (about 25 s) with the station quiet and no competing process; no timing was compared. **Nothing is frozen; no R1 work has started.**

## 1. Does the harness build against today's stack? Yes

- **Today's stack** = the v2 tree `59eb5a8f` (`_qa-scratch\coh-res-cand-v2\tree`, build output `bin_v2`: `Ft8.FitProbe.exe`, `libft8.dll` SHA-256 `bbde6eb6…6528`, shim 20260072): v2 ON, CQ-AP, late round, coherent multi-set, as arm B ran it.
- **Build evidence:** `build_v2.log`: `0 Error(s)`, two nullable warnings in `LateSub.cs`. The build is `Replay81.csproj -p:RepoRoot=<tree> -p:HasInternals=true` and the product assembly name `Ft8.FitProbe`, so `StageProbe.cs` (the capture) compiles in. The harness source at `17dcb1fc` (`qa/rr-study/sub-feas/replay81`) is the one that built it.
- **Capture smoke (3 cycles of `20261110_1817`, arm B's exact flags plus `--cap-dir`):** exit 0; the readback lines match arm B's (Deep, nhard 24, osd-sign-fix 1, cohfb, cohms, cohaudio Both, ungated, late round); for all 3 cycles **`matchedbatch.csv` and the late-round line of `late.csv` are identical to arm B's** (the capture does not change what the arm publishes). A pitfall for the R1 command: the harness refuses relative `--nc-dump`/`--cap-dir` paths (HK-037: they must be absolute under `_qa-scratch`); it reports only `FATAL ArgumentException`.

## 2. What the capture writes per cycle (observed, then read in `StageProbe.cs:121-166`)

| file | content | batch it serves |
|---|---|---|
| `buffers\<stamp>_O.f32`, `_R2`, `_R3` | the DecodeAll calls 0, 1, 2: the normalised original, the residual pass's buffer, the third pass's buffer (180,000 float32 each) | R3 or R2 is the fallback's **residual audio** (first run and v2's third run); O is the second run's audio (**batch 4**) |
| `buffers\<stamp>_X3.f32` | the **4th DecodeAll call = the late round's own decode** on its residual (R3 minus the fits of batch 3 + batch 4 natives): RMS 0.140 against R3's 0.159 on the first cycle | **batch 5** decodes from exactly this buffer |
| `native\<stamp>.tsv`, `hash\<stamp>_<kind>.bin` | the natives each call returned (freq, dt, SNR, text) and the hash state saved just before the call (text: `_qa-scratch` only) | exact re-decode (`Recheck`) |
| `plan\<stamp>.tsv`, `capture_index.tsv` | the fallback's candidate plan; one line per cycle: call count, the buffer SHAs, **which buffer the first fallback run read (`level` R3 / R2 / O)** and the second (O) | audio provenance per run |

- Observed on the 3 smoke cycles: 4 DecodeAll calls each, `level` = R3, second = O, 3 fallback runs (residual, original, v2's residual third run), 18 / 16 / 19 natives in call 0.
- **Cost:** 3.4 MB per cycle (10 MB for the 3), so ≈ 1.7 GB for 500 cycles; D: has 1.5 TB free.

## 3. The gap, and two caveats for R1

1. **Provenance of a batch-4 row is not recorded.** `nc-dump` gives every fallback row `path = 2` (observed: batch 4 → path 2 on all 24 rows; batch 5 → path 1; batch 2, 3 → path 1; batch 1 → path 0). Batch 4 rows come from up to three runs merged (`CohFallbackAudioSelector.Merge(originalRows, residualRows)`): the residual run, the original run and v2's third residual run. **Which buffer a given published row came from is therefore not in any file the arm writes.** The row's `Provenance` field exists inside the harness (`StageProbe.cs:48-59`, written with `--gate-record` for GATED rows only). Options for the Architect: (a) a small QA-owned harness change to write provenance for every published fallback row (≈ 1 h incl. a self-test; no `src/`); (b) define the score as "present on R3 (the residual audio) **or** on O" (the two audios batch 4 reads), a union rule that needs no provenance, with its false side measured by the ghost control; (c) score batch 4 on R3 only. I recommend (a): it is the only one that scores "the buffer the decode came from" as the ruling says.
2. **X3 is positional.** The wrapper labels the 4th call `X3`, but when the third pass does not run, the late round's call is the **3rd** and lands under the label `R3`. The late round's own line (`late.csv` column `buffer`: R2 or R3) and the call count in `capture_index.tsv` disambiguate; R1's code must read them, not the file name.

## 4. Cost of R1 (firmer after R0)

- **PC window:** the arm's own wall time, ≈ 42 min for the 500 cycles (arm B's), plus the exclusivity checks: **45–60 min, daemon stopped, WSJT-X closed or idle**, as before. Capture is a copy per call and does not change published output (the 3-cycle check above; a 500-cycle `matchedbatch` comparison with arm B's is the V-REPRO row for R1).
- **QA effort:** the TA-RES stage as the ruling describes (frozen groups, A-KEEP / A-SEE / A-GHOST paired, a residue-made ghost control) ≈ 3–4 h, plus (a) above ≈ 1 h if chosen.
- **Not decided here:** the residue-made ghost control (how to build a ghost from residue rather than from a neighbour copy) is the Architect's spec; I flag that on R3/R4 the neighbour is subtracted and the residue of that subtraction sits in the same bins, so the ghost row may fail there, as the ruling says.

## 5. State

R0 = **feasible**. The smoke folder and its mini-selection were deleted (they held natives text). Nothing else changed; `_qa-scratch\ta-check\` and `ta-mask\` are kept. **Waiting on the Architect's TA-RES spec (and the Captain's PC window for R1).**
