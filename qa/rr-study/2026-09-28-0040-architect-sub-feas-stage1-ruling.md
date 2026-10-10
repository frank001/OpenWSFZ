# `SUB-FEAS`: Stage 1 ruling. **FAIL stands as pre-registered.** One Architect defect found in the gate: the PASS bar sat below the instrument's own real-audio floor

**Architect, 2026-09-28 00:40Z** (`date -u`, HK-017). Branch `arch/subtraction-feasibility`. Docs only:
`git diff --stat origin/main -- src/ native/` is empty. Rules on QA
`qa/rr-study/2026-09-28-0023-qa-to-architect-sub-feas-stage1-results.md` (`qa/sub-feas`). Spec
`2026-09-27-1855` plus Amendments 1–3.

## §1. Accepted (the Architect checked these against `sub_feas_result.json`, HK-018)

- **ROW 0: every row passes** (0a–0i, 0b′). The Amendment 2 drift term works: 0b "drift" reads |X| ≤ 0.04 dB at
  every SNR, and 0b′ is 135/135. 0h: 0.83 % of rows on the box edge.
- **Stage 1 (split B, n = 2,063, `W*` = 0.32 s): median X = 8.75 dB [8.47, 9.10], median D = 19.25 dB ⇒ `FAIL`**
  (`ci_hi` > 6.0).
- **Controls:** L0 − L2 = 19.12 dB [18.91, 19.25]; L1 − L2 = 10.33 dB [10.07, 10.68]; L0 alone = 27.03 dB ⇒
  C-FLAG does not fire. **June's failure was a modelling failure.** The data-aided fit plus a time-varying
  envelope removes about 19 dB more than the June model does, on real audio.

## §2. HK-026 check the spec lacked: what X reads where there is nothing to subtract

The spec validated the noise floor `N̂` on **synthetic** audio only (ROW 0c). It never asked what `X`
reads on **real** 40m audio in a band with no decoded signal. The Architect ran that control before
ruling (read-only; QA's own `fitter.residual_metrics`, untouched):

- 300 split-B cycles (seed 20260927); every 10 Hz step across 250–2,700 Hz with no decode from **either**
  program within 60 Hz. That gave 21,319 band samples; about 28 % of the passband is "empty" by that test,
  with a median of 40 decodes per cycle.
- **`X_empty` (no subtraction at all): median 3.46 dB** (p25 −0.36, p75 6.52).

⇒ 🔴 **The PASS bar (`ci_hi` ≤ 3.0 dB) was below the median reading of an untouched, empty band.** A
perfect subtraction would, to first order, leave a band like these and read about 3.5 dB. **PASS was
effectively unreachable on this corpus.** This is the Architect's defect: the same class as 0g's
original bar (a bar set without measuring its input's floor), and HK-026 exactly (the instrument could
not bound its own blind spot). Busy 40m is full of energy that neither decoder decodes. A 20th-percentile
floor sits below it.

## §3. What the ruling does and does not do with that

🛑 **The gate is NOT re-read against a corrected floor.** "Never re-read a closed gate with a better
metric" is a standing prohibition, and it exists for exactly this moment. Stage 1 reads **FAIL**, as
pre-registered. Two facts go on the record beside it, not in place of it:

1. **The PARTIAL bar (6.0 dB) was reachable.** It sat about 2.5 dB above the empty-band median, and the
   result misses it by `ci_lo` 8.47 − 6.0 = **2.47 dB**. So FAIL is not produced by the defect in §2 alone.
2. **The distance to "perfect" is smaller than the headline suggests.** 8.75 − 3.46 ≈ **5.3 dB** of
   residual above what empty spectrum reads, not 8.75 dB above silence. This is **descriptive only**:
   empty bands and signal bands are not matched populations, so it is not a corrected X.

**Also descriptive:** `W*` = 0.32 s is the **smallest** member of the family, and X falls monotonically
with W (18.53 → 8.15 dB on split A). The optimum may lie below the family. That is an edge-of-family
reading, and it limits what "FAIL" can say about the method class as opposed to this parameterisation.

## §4. Disposition

- **Stage 1 = FAIL. Stage 2 is not licensed by the gate** (spec §8).
- The one measurement that doesn't depend on `X`'s floor at all is **Stage 2's**: subtract, re-decode,
  and count WSJT-X-corroborated new decodes. Running it now would be a **new, Captain-initiated
  diagnostic**, labelled as run **despite** a FAIL. It is not a continuation licensed by this arm, and
  its result could not retro-promote Stage 1. **That is the Captain's call.** The Architect's
  recommendation is in §5.
- The build prohibition on subtract-and-resynthesise **stands unchanged** whichever way he decides.

## §5. Architect recommendation

**Run Stage 2 as a labelled diagnostic, with its §8 bars unchanged, plus one extra `W` = 0.16 s leg
reported descriptively.** Reasons: it is offline and cheap (~2 h, harness built, ROW 0 passed); it
answers the only question the Captain actually asked ("does it find more signals?"); and §2 shows that
Stage 1's `X` was a weaker proxy for that question than the spec assumed. **If Stage 2 reads `NONE`,
close the subtraction line for good, with a measured reason.** The alternative, closing now, is also
defensible: the pre-registered read is FAIL, and nothing here overturns it.

## §6. Scored now (ledger rule 1)

| # | prediction | P | class | outcome |
|---|---|---:|:---:|---|
| 3 | Stage 1 PASS / PARTIAL / **FAIL** | 0.30 / 0.35 / **0.35** | H | **FAIL**. The tied mode was PARTIAL/FAIL; PASS was unreachable (§2), so 0.30 on it was mis-placed mass |
| 4 | L0 − L2 ≥ 3 dB | 0.70 | H-mech | **HIT** (19.12 dB) |
| 5 | Given PASS, Stage 2 WIN | 0.35 | H | **VOID**: its condition never occurred |
| A2 | 0b passes with the drift term | 0.70 | C | **HIT** |
