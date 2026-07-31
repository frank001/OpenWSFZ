# Measurement C -- re-alignment experiment (D-001 ruling S6b)

Manifest: `measurement_c_manifest.csv`. 150 healthy-window + 150 collapsed-window cycles.

| stratum | condition | decoder | matched | ref decodes | parity |
|---|---|---|---:|---:|---:|
| healthy | unshifted | ours | 2966 | 4831 | 61.4% |
| healthy | unshifted | jt9 | 4665 | 4831 | 96.6% |
| healthy | shifted | ours | 2979 | 4831 | 61.7% |
| healthy | shifted | jt9 | 4741 | 4831 | 98.1% |
| collapsed | unshifted | ours | 63 | 1561 | 4.0% |
| collapsed | unshifted | jt9 | 270 | 1561 | 17.3% |
| collapsed | shifted | ours | 985 | 1561 | 63.1% |
| collapsed | shifted | jt9 | 1407 | 1561 | 90.1% |
