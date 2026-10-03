# #122 gate 4a: Amendment 1 (V4 replaced by V4'), committed by the Engineer before any result was read

- **Source:** the Architect's amendment, commit `45c1d016` on `arch/122-latency`, 2026-10-03 13:53Z by `date -u` ("Amendment 1" in `qa/rr-study/2026-10-03-1015-architect-to-qa-spec-122-gate4a-truncation-replay.md`). This file records what the Engineer implemented. It does not replace the spec.
- **Committed:** 2026-10-03, before any catch figure was read. The run was still in progress (arm X17-T) and no output had been analysed. The harness (`9dd89f3f`) is unchanged; only `analyse_trunc.py` changed, and `test_analyse_trunc.py` was added.

## What changed

V4 (`C(4.0) <= C(0.5) - 0.20`) is replaced, per corpus, by **V4'**: PASS iff

1. **(i)** `C(4.0) <= 0.98`, and
2. **(ii)** the 95 % block-bootstrap CI lower bound of `D = C(0.5) - C(4.0)` is `> 0`. This is the section 5 bootstrap: the same blocks of 10 consecutive listed cycles, the last partial block kept, B = 10 000, seed 20261003, with numerator and denominator resampled together.

A V4' FAIL withholds **that corpus's** catch figures. A V0–V3 failure still stops everything.

## Always reported, PASS or FAIL

- V4 as first registered, labelled "superseded by Amendment 1; reported, not used".
- `C(0.5)`, `C(4.0)`, `D` and its CI.
- V1's result beside them. V1 is asserted in-process before every cut decode, and a failure stops the run with exit 3, so an exit of 0 carries it.

## Not changed

Every other row, every output and the predictions TR1–TR6. TR1 to TR6 are scored as registered. TR5 stays "V0–V4 all pass the first time", scored against the ORIGINAL V4 (the Architect's prediction; Amendment 1 leaves predictions unchanged), with V4' shown beside it as a note.

## Why (the Architect's reasoning, in short)

In the Engineer's discarded 4-cycle smoke test `C(4.0)` was about 0.78. FT8's LDPC code still decodes many strong signals from a window that ends at 11 s. The 0.20 margin rested on the edge run's tail tolerance at −8/−16 dB, which does not carry over to strong real signals. V4' is derived from the failure V4 exists to catch: a cut that never reaches the decoder gives `C(x)` = 1.000 at every `x`.

## Test

`qa/rr-study/trunc-replay/test_analyse_trunc.py` (6 tests, synthetic counts only):
- the uncut signature fails on clause (i);
- a real loss passes;
- a small loss that the superseded V4 would fail passes V4';
- a loss that is noise fails on clause (ii);
- the 0.98 boundary is inclusive;
- the same blocks and seed give the same CI.

Run it with `python -m unittest qa/rr-study/trunc-replay/test_analyse_trunc.py`.
