# DI7COH2 tooling commit (QA, 2026-10-22; Architect review K4)

The R&R series DI7COH2 runs the heavy tooling checked out at `b0e23bb` (the commit the MAINDEEP series logged as "tooling") **plus exactly the files below**, committed on the branch `qa/tooling-di7coh2` (cut from `b0e23bb`). The sweep's build line logs `git -C ~/rr-work-b2 rev-parse HEAD`, which is this commit; `git diff --stat b0e23bb..<this commit> -- qa/rr-study/` lists only these files.

| File | What | Note |
|---|---|---|
| `linux/battery-tp.sh` | the third-pass battery | **changed:** the config pin drops `decoder.coherentFallbackEnabled` (as it already drops `decodingDepth`) and prints both configs' values; **new K3 halt:** with `TP_REQUIRE_FLAG=true` any sweep config that does not carry the flag `true` halts before anything is started |
| `linux/series-tp.sh` | the N-sweep series driver | **changed:** after each sweep, with `TP_REQUIRE_FLAG=true`, runs `flag_readback.py` and logs the V-F verdict |
| `linux/flag_readback.py` | **new:** validity row V-F | config flag true, and the per-cycle `Coherent fallback:` line in >= 0.95 of the `Cycle ...: N decode(s) found` lines of the sweep's daemon log (Architect decision value; the full R14 live window had 504 of 504) |
| `linux/pull-series.sh`, `linux/depth_readback.py` | the pull and the V-D row | **unchanged**: they were used by the MAINDEEP/TPDEEP series from the home directory and were committed to `qa/refset` after `b0e23bb`; they are added here so the tooling commit is complete |
| `linux/DI7COH2-TOOLING.md` | this note | docs |

`b0e23bb` itself does **not** contain `battery-tp.sh`, `series-tp.sh`, `pull-series.sh` or `depth_readback.py` (they landed on `qa/refset` later, as home-directory scripts first). So the diff against `b0e23bb` shows five files as additions, not as changes; of those, only `battery-tp.sh`, `series-tp.sh` and `flag_readback.py` differ from what ran in the earlier third-pass series.
