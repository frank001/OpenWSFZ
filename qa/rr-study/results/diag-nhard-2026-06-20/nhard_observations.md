# D-009 R6 — nhard/sync Diagnostic Observations

**Date:** 2026-06-20
**Shim:** 20260028 (D-009 R5: OSD_NHARD_MAX=60, OSD_CORR_THRESHOLD=0.10, Rules A/B/C)
**Build:** NHARD_DIAG — probe fires after CRC-14 check, writes to C:\Temp\nhard_diag.log
**Populations:**
- **FP** (S5 AWGN, 40 trials): 205 OSD CRC-valid hits in pure noise
- **Genuine** (S7 P0-2 co-channel, 5 trials each): 92 OSD CRC-valid hits during real signal decoding

**Acceptance criteria met:** AC1 = True (need ≥30 FP hits, got 205); AC2 = True (need ≥20 genuine hits, got 92)

---

## 1. nhard axis

### 1.1 Descriptive statistics

  FP (S5 noise): n=205, min=35.0, max=60.0, mean=51.8, median=52.0, stdev=4.9
  Genuine (S7): n=92, min=37.0, max=60.0, mean=51.4, median=52.0, stdev=5.0

### 1.2 nhard histogram — FP population (S5 AWGN)

```
    [ 35- 39] ## (2)
    [ 40- 44] ############## (14)
    [ 45- 49] ######################################## (50)
    [ 50- 54] ######################################## (71)
    [ 55- 59] ######################################## (61)
    [ 60- 64] ####### (7)
```

### 1.3 nhard histogram — Genuine population (S7 P0-2)

```
    [ 35- 39] # (1)
    [ 40- 44] ####### (7)
    [ 45- 49] ##################### (21)
    [ 50- 54] ################################### (35)
    [ 55- 59] ######################### (25)
    [ 60- 64] ### (3)
```

### 1.4 Best threshold on nhard axis (reject if nhard > T)

  nhard T=60 (reject if > T):
    FP rejected 0/205 = 0.0%  |  Genuine kept 92/92 = 100.0%

### 1.5 Verdict

**nhard: PARTIAL separation — only 0.0% FP rejected at 97% genuine keep**

---

## 2. sync axis

### 2.1 Descriptive statistics

  FP (S5 noise): n=205, min=7.0, max=13.0, mean=8.1, median=8.0, stdev=1.2
  Genuine (S7): n=92, min=7.0, max=21.0, mean=8.6, median=8.0, stdev=2.2

### 2.2 sync histogram — FP population

```
    [  7] ######################################## (67)
    [  8] ######################################## (84)
    [  9] ############################## (30)
    [ 10] ################ (16)
    [ 11] ## (2)
    [ 12] #### (4)
    [ 13] ## (2)
```

### 2.3 sync histogram — Genuine population

```
    [  7] ######################## (24)
    [  8] ################################### (35)
    [  9] ############# (13)
    [ 10] ################ (16)
    [ 11] ## (2)
    [ 21] ## (2)
```

### 2.4 Best threshold on sync axis (reject if sync < T)

  sync T=7 (reject if < T):
    FP rejected 0/205 = 0.0%  |  Genuine kept 92/92 = 100.0%

### 2.5 Verdict

**sync: PARTIAL separation — only 0.0% FP rejected at 97% genuine keep**

---

## 3. Representative samples

### 3.1 FP samples (first 10 from S5)

| nhard | sync | corr   | norm   |
|-------|------|--------|--------|
|    52 |    8 |  164.0 |  709.6 |
|    55 |    8 |   75.4 |  681.9 |
|    55 |    7 |  118.9 |  690.0 |
|    48 |   11 |  191.4 |  682.3 |
|    48 |   11 |  191.4 |  682.3 |
|    45 |    9 |  207.5 |  673.7 |
|    50 |    7 |  173.5 |  705.9 |
|    47 |    8 |  248.1 |  723.4 |
|    54 |    8 |  143.7 |  674.3 |
|    57 |    8 |  148.1 |  674.0 |

### 3.2 Genuine samples (first 10 from S7)

| nhard | sync | corr   | norm   |
|-------|------|--------|--------|
|    56 |    9 |  143.4 |  658.6 |
|    47 |    8 |  220.9 |  675.1 |
|    48 |    8 |  234.7 |  654.9 |
|    53 |    8 |  211.8 |  660.3 |
|    56 |    8 |  100.1 |  662.0 |
|    56 |    7 |   92.4 |  661.4 |
|    60 |    7 |  111.3 |  710.6 |
|    52 |    7 |  245.2 |  655.0 |
|    53 |    8 |  246.1 |  695.3 |
|    50 |    8 |  225.4 |  694.3 |

---

## 4. Decision variable (per `2026-06-20-d009-r6-decision-fork.md` §2)

| Axis  | Best T | FP rejected at T | Genuine kept at T | Separates? |
|-------|--------|------------------|-------------------|------------|
| nhard |     60 |             0.0% |            100.0% |         NO |
| sync  |      7 |             0.0% |            100.0% |         NO |

**R6 branch triggered: B2**

neither nhard nor sync separates — escalate to scope decision (§4)

*(Architect selects the specific implementation per `2026-06-20-d009-r6-decision-fork.md` §3. Developer does not implement.)*

---

## 5. Methodology notes

- **FP population:** OSD hits in pure wideband AWGN (S5, 40 trials, 40 × 15 s = 600 s, no FT8 signal). All CRC-14 successes are by definition false positives. Probe emitted AFTER CRC-14 check so each line corresponds to an actual decode event visible in ALL.TXT.
- **Genuine population:** OSD hits during S7 P0-2 co-channel decoding (3 parts × 5 trials = 15 slots). Signal IS present; OSD fires when BP fails on the co-channel candidate. Most CRC-14 successes in S7 correspond to true signal decodes; rare spurious CRC coincidences from the co-channel noise are possible but statistically minor.
- **Probe placement:** Post-CRC, not pre-gate. Only OSD hits that passed BOTH the OSD_NHARD_MAX=60 gate AND the OSD_CORR_THRESHOLD=0.10 gate AND CRC-14 are captured. This is the target population for the R6 fix: candidates that slip through the current shim 20260028 filters.
- **Why OSD_NHARD_MAX=60 was not removed:** The diagnostic tests within the existing gate (nhard 0-60). If the data shows no gap in [0,60], we confirm the nhard avenue is exhausted (Branch B); if there IS a gap, we lower the gate to that T (Branch A). Either conclusion is correct.
- **NFR-021 compliance:** No real callsigns appear in this document or in the committed data files (nhard_fp_s5.txt, nhard_genuine_s7.txt contain only numeric tuples). ALL.TXT snapshots from both runs are NOT committed: the S5 ALL.TXT contains ITU-assignable CRC coincidences (random bit strings from AWGN that happen to pass CRC-14 and decode as plausible callsigns — e.g. `UA9HPL`, `SQ9HQT`); these are not transmissions from licensed amateurs but could coincide with real calls. The S7 ALL.TXT contains only Q-prefix synthetic callsigns (MSG-01/02/03 from study-messages.json) but is withheld for consistency. Raw diagnostic logs (nhard_s5_raw.log, nhard_s7_raw.log) contain only numeric tuples and are committed as supporting data.
