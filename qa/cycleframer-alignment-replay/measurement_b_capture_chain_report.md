# Measurement B -- capture-chain replication, primary arm (D-001 ruling S6)

n = 300 cycles, |drift| < 0.5s (drift-free primary arm per S6.2).

## Pooled 2x2 (unique cycle,message decodes)

| | our WAV | WSJT-X WAV |
|---|---:|---:|
| **our decoder** | 6118 (a) | 6139 (b) |
| **jt9** | 10091 (c) | 10089 (d) |

capture-chain ratio, our decoder: 1.0034 (+0.3%)

capture-chain ratio, jt9: 0.9998 (-0.0%)

interaction ad/bc = 0.9964, 95% CI [0.9526, 1.0421]

## Paired per-cycle Wilcoxon signed-rank (decisive test, S6.2)

our decoder: mean(our WAV)=20.393, mean(WSJT-X WAV)=20.463, W=10526.0, p=0.4442

jt9: mean(our WAV)=33.637, mean(WSJT-X WAV)=33.630, W=8096.0, p=0.8364

## Pre-registered reading rule (S6.3, applies to this primary arm only)

| outcome | reading | consequence |
|---|---|---|
| Effect confirmed, paired p<0.01, direction as in S3 | The capture chain really does cost us decodes. | Folds into row 4 decomposition with measured magnitude and CI |
| Effect refuted, CI comfortably spans zero | n=30 was noise. | Drop it. Strike S3's percentages. |
| Ambiguous (0.01<=p<0.05, or CI includes zero but point estimate holds) | Underpowered even at n=300. | Report as bounded-small. Do not escalate n further. |

**Mechanical outcome: EFFECT REFUTED (interaction CI spans no-effect, p>=0.05) -> DROP. Strike S3's percentages.**

