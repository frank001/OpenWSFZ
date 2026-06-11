# S6 Corpus Replay — Report

| Field | Value |
|---|---|
| Run date | 2026-06-11 |
| WAV files | 42 |
| Runs (K) | 3 |
| Total observations | 2799 |

## 1. Within-appraiser consistency

| Appraiser | Total (wav,signal) pairs | Consistent | % Consistent |
|---|---|---|---|
| WSJT-X | 933 | 868 | 93.0% |
| OpenWSFZ | 933 | 884 | 94.7% |

## 2. Between-appraiser agreement (Cohen's κ)

κ = **0.0839**  (95% CI [0.0335, 0.1343])

| | WSJT-X decoded | WSJT-X not decoded |
|---|---|---|
| **OpenWSFZ decoded** | 1831 (TP) | 78 (FP) |
| **OpenWSFZ not decoded** | 795 (FN) | 95 (TN) |

## 3. SNR delta (D-002 field validation)

Mean SNR delta (OpenWSFZ − WSJT-X) = **-3.091 dB**  σ = 7.970 dB  (n = 1831)

_Positive delta = OpenWSFZ reports higher SNR than WSJT-X._

## 4. Order-effect test

**WSJT-X:** No order effect detected — Spearman ρ = 0.0132, p = 0.8833.

**OpenWSFZ:** No order effect detected — Spearman ρ = 0.033, p = 0.7136.


---

_Callsigns scrubbed per NFR-021. Real callsigns replaced with `[CALL]` before commit._
