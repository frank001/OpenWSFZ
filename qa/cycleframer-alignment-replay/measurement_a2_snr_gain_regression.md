# SNR gain-error regression -- per-decode (ruling S7.4.2)

| corpus | n | slope | intercept (dB) | slope 95% CI | intercept 95% CI |
|---|---:|---:|---:|---|---|
| 80m | 8290 | 0.5629 | -3.904 | +-0.0098 | +-0.166 |
| 10m | 9177 | 0.8538 | -3.451 | +-0.0068 | +-0.066 |
| 20m | 24201 | 0.7234 | -5.076 | +-0.0057 | +-0.065 |
| 40m (WSJT-X, SUSPENDED-drift, excluded from fit) | 52736 | 0.6884 | -12.674 | +-0.0067 | +-0.072 |

**Pooled (3 jt9-referenced corpora, n=41668):** `ours = 0.6865 x ref -4.742 dB`, slope 95% CI [0.6824, 0.6906], intercept 95% CI [-4.793, -4.691] dB.

A pure offset requires slope = 1.00. The pooled 95% CI excludes 1.00 by a wide margin -- confirming S7.1's three-corpus-mean finding at per-decode resolution: this is a gain error, not an offset, and D-002's constant correction cannot fix it.
