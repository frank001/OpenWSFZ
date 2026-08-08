# PRE-REGISTRATION — 12m sparse-regime leg (four-decoder comparison)

**Author:** QA · **Written:** 2026-08-08 11:45 UTC · **Status:** registered BEFORE any 12m data exists

This document is written and fixed *before* the leg runs. Nothing below may be edited once the
daemons are armed; if the design proves wrong, it is superseded by a new document, not amended.
Drafted per HK-021 by writing the evaluator first (`w1`-style): every row is mechanical, the
thresholds are absolute numbers, the rows are mutually exclusive and evaluated in strict order,
and ROW 0 is explicit.

---

## 1. What this leg is for

The 2026-08-08 20m leg (`artefacts/20260808_live_run_0016-808{0,1}/`) measured, unexpectedly, a
**monotonic relationship between per-cycle decode density and OpenWSFZ's recovery rate**:

| quintile | mean density (dec/cycle) | recovery |
|---|---|---|
| Q1 | 15.3 | 60.2% |
| Q2 | 23.7 | 59.2% |
| Q3 | 28.2 | 56.9% |
| Q4 | 32.1 | 55.3% |
| Q5 | 37.5 | 50.5% |

Least-squares fit over the five quintile points:

    recovery(%) = 68.01 - 0.4237 * density        R^2 = 0.874
    max |residual| = 1.62 points

That slope was measured **within one band**, so band is held constant and cannot explain it. But
the 20m corpus bottoms out at 15.3 dec/cycle; it contains no genuinely sparse regime, which is the
standing open TODO ("Mechanism 1 needs a different WINDOW, not just a reference").

This leg does **not** simply extend that curve. Extending it on a different band would confound
density with band. The leg is designed as a **replication**: if 12m's points fall on the 20m line,
density is the driver; if they fall off it, band-specific factors (SNR distribution, Doppler,
signal population) matter and the 20m slope must not be read as a density law.

## 2. Configuration — frozen, and identical to the 20m leg

The decoder settings **must not change between legs**, or the replication is void:

    decoder.kMinScorePass2 = 10 · decoder.osdCorrThreshold = 0.1 · decoder.osdNhardMax = 60

Also unchanged: same self-contained publish of `main` @ `b8845cd` (both instances share the literal
same binary), same audio device (`{0.0.1.00000000}.{67987b85-...}`, "Microphone (2- USB Audio
CODEC )"), same shared-mode WASAPI path, `cat.enabled=false`, `ptt.method="AudioVox"`,
`tx.autoAnswer=false`, `cycleAudioArchive.mode="all"`.

**Changed for this leg, and only this:** `decodeLog.dialFrequencyMHz` 14.074 -> **24.915** on both
instances (backed up as `config.json.bak-20m`). This is mandatory and must precede the VFO moving:
with CAT disabled the dial frequency resolves to this manual fallback
(`WebApp.cs:1990-1997`), so an unchanged config would label 12m decodes as 14.074 while WSJT-X
labelled them 24.915 — producing zero apparent overlap and an uninterpretable corpus.

**Pre-arm checklist (all four must hold before the leg counts):**

1. Rig on 24.915 MHz; both WSJT-X instances retuned and logging `24.915` in their `ALL.TXT`.
2. Both OpenWSFZ configs read `24.915` (verified).
3. Both daemons report `Heartbeat: captureActive=true, audioActive=true, dataFlowing=true`.
4. Both supervisors attached to the correct current log, retries 0.

## 3. Definitions (mechanical)

- **Reference set** `W` = `(ts, message)` pairs present in **both** WSJT-X instances' `ALL.TXT`,
  `Rx FT8` lines only, dial `24.915`, within the leg window. Using the intersection, not the
  union, deliberately: it is the conservative reference, and it is what the 20m figure used.
- **Recovery** = `|A ∩ W| / |W|`, where `A` = OpenWSFZ 8080's decode set over the same window.
- **Density** of a cycle = number of decodes in `W` bearing that cycle's timestamp.
- **Quintiles** are computed over the leg's own cycles, ranked by density — **quantiles, never
  absolute constants** (HK-021b), so the stratification cannot fail to populate.
- All figures use **WSJT-X's own SNR/frequency fields**, never OpenWSFZ's, since OpenWSFZ's
  reported SNR carries a known gain error (`DEFECT-snr-reported-gain-error.md`).

## 4. ROW 0 — instrument failure (evaluated FIRST; if it fires, the leg reads NOTHING)

The leg is **VOID** if any of the following holds:

- **0a.** Fewer than **400** cycles in the window contain at least one reference decode.
  (400 cycles ~ 100 minutes of band time; below this the quintiles are too thin to read.)
- **0b.** The leg's **median cycle density is >= 15.3 dec/cycle** — i.e. 12m was not, in fact,
  sparser than the sparsest quintile of 20m. The leg then has no sparse regime and answers
  nothing it was built to answer.
- **0c.** The two WSJT-X instances agree with each other on **< 95%** of decodes (Jaccard). On 20m
  they agreed 99.6%; a collapse means the reference itself is unstable and no recovery figure
  computed against it is trustworthy.
- **0d.** Either OpenWSFZ instance logs a dial frequency other than `24.915`, or the two WSJT-X
  instances disagree on dial frequency, at any point in the window.

If ROW 0 fires, the correct action is to fix the instrument and re-run — **not** to reinterpret
whatever numbers came out. Per §1 of the band decision, 12m going dead is an expected outcome, and
the fallback is 17m (18.100) under this same pre-registration with `24.915` read as `18.100`.

## 5. Reading rule (evaluated in strict order; first match wins)

Let `p_i` be the observed recovery in 12m quintile `i`, and `f(d) = 68.01 - 0.4237 * d` the 20m
prediction at that quintile's mean density. Let `E = max_i |p_i - f(d_i)|`, the largest deviation
from the 20m line in percentage points. The 20m fit's own max residual was 1.62 points.

- **ROW 1 — replicates.** `E <= 4.0` points AND the 12m slope is negative.
  *Reading:* density is the driver. The 20m slope generalises across bands, and OpenWSFZ's
  recovery deficit is substantially a function of how much traffic it must resolve per cycle —
  which points at the time-bounded candidate/pass budget as mechanism. This would be the first
  cross-band-replicated quantitative law in the D-001 programme.
- **ROW 2 — replicates in sign, not in level.** `E > 4.0` but the 12m slope is negative and
  within a factor of two of `-0.4237` (i.e. in `[-0.85, -0.21]`).
  *Reading:* density matters and the direction is real, but the level is band-dependent. The
  20m intercept may not be quoted for any other band.
- **ROW 3 — no density effect on 12m.** 12m slope in `(-0.21, +0.21)`.
  *Reading:* the 20m slope is not a density law. It is more likely a proxy for something that
  co-varies with density on 20m (most plausibly the SNR distribution). **The 20m quintile table
  must then be withdrawn as evidence of a density effect.**
- **ROW 4 — inverted.** 12m slope `>= +0.21`.
  *Reading:* recovery *improves* with density on 12m. Treat as an instrument or framing failure
  before treating as a finding, and check the SNR stratification first (HK-021e).

## 6. Secondary readings (recorded, not gated)

These are reported alongside but carry no row and settle nothing on their own:

- **SNR-stratified recovery**, same bands as the 20m leg (`-30..-21 / -21..-18 / -18..-15 /
  -15..-10 / -10..-5 / -5..0 / 0..40`). 20m ran 19.8% -> 83.2% across these. The key question is
  whether the density slope survives when SNR is held fixed; if it does not, ROW 3's reading is
  strengthened regardless of which row fired.
- **OpenWSFZ self-consistency** (8080 vs 8081, Jaccard). 20m: 94.4%, against WSJT-X's 99.6%.
- **False-positive proxy**: share of OpenWSFZ decodes absent from both WSJT-X instances whose
  callsigns appear nowhere in the WSJT-X corpus. 20m: 9.1% of single-instance-only novel decodes
  had known callsigns, vs 86.7% of the ones both OpenWSFZ instances produced.
  ⚠️ **Agreement between 8080 and 8081 does NOT validate a decode** — same build, same audio, so a
  deterministic false positive appears in both. This proxy bounds FPs; it does not identify them.

## 7. Known confounds, stated in advance

1. **The audio is not bit-identical.** OpenWSFZ and WSJT-X are separate shared-mode WASAPI clients
   with independent cycle framing. The OpenWSFZ-vs-OpenWSFZ control (94.4% on 20m) bounds this
   confound; it does not eliminate it.
2. **Band change moves more than density** — see §1. This is why the leg is framed as replication
   against a pre-committed line, rather than as points appended to the 20m curve.
3. **12m via sporadic E is bursty.** Density may swing far more within the leg than 20m's did.
   That is not a defect — it widens the density range — but the quintiles must be read as the
   leg's own quantiles, never compared to 20m's quintile *boundaries*.
4. **Four decoders share one CPU.** Measured at 21.2% -> 22.8% total on 20m. If 12m is sparse,
   contention falls, which is itself correlated with density. This cannot be separated within
   this leg and is a live alternative explanation for any ROW 1 result.

## 8. Evaluator

`qa/endurance/2026-08-08-four-decoder-interim-comparison.py`, with the dial-frequency constant
changed to `24.915`. The ROW logic above is not yet coded; it must be written as an assertion
before the leg's data is examined, not after.
