# REFERENCE-SET replay harness, legs A and D (QA)

Spec: `arch/reference-set`, sections 2c, 2i, 2k, 2l. Platform-neutral (Windows and Linux); built, tested and run on `sol` first (2l item 1).

| file | role |
|---|---|
| `RefSet.csproj`, `Program.cs` | ONE PROCESS = ONE BLOCK. Decodes the 8 warm-up cycles (discarded) and the 32 scored cycles of a manifest block through `Ft8Decoder.DecodeTwoStageAsync`, writes a per-block working file (message text, scratch only) and an aggregate summary json (pins, readbacks, residual-pass counts per cycle, wall and CPU time) |
| `refset_score.py` | scoring: the W-pilot `ScoreCycle` ported row for row, readers, cycle-clustered bootstrap. Aggregates only; text never leaves it |
| `test_refset_score.py` | the pilot's self-test cases plus readers (synthetic Q-prefix calls only) |
| `run_refset.py` | driver: verify the corpus, one process at a time, pins, abandonment rule, checkpoints, tiers, gate mode (`--run <corpus run>`) |

Build (the checkout is the build under test): `dotnet build RefSet.csproj -c Release -p:RepoRoot=<checkout> -o <out>`.
Run: see the docstring of `run_refset.py`. Working files go to `--scratch`, which must be outside git (HK-037 as amended 2026-10-10) and is deleted at job close.

Rules the driver enforces: the native library SHA-256 equals `--expect-native-sha` at the start and end of every block; a block with any residual-pass abandonment is re-run once alone and, if it abandons again, the driver stops with exit code 10 (spec 2l item 2: stop and ask, never relax the deadline); excluded blocks are skipped, never replaced; a finished block's summary is its checkpoint.

First smoke (this PC, 2026-10-11, anchor DLL `a14fe354`, one 40 m twilight block of the anchor night, leg A): 207.6 s wall, 1,147 s CPU, 0 abandonments, 100 % of the live non-hashed rows reproduced, 0 extra. One block only: no gate result.
