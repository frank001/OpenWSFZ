# EARLY-DUP Part A1: runbook (two S4 plays on `origin/main`, classifier v2). Station; runs only on the Captain's go in QA's window.

Spec: `qa/rr-study/2026-10-09-1025-architect-to-qa-spec-early-dup.md` (`arch/122-latency`, amendment 1). Verdict rows: `early_dup_rows.py`. Counts and Hz only (HK-037).

## 0. Before the first play (no station)

1. `git fetch origin` and note `origin/main`'s SHA. Scratch worktree: `git worktree add --detach D:\Projects\claude\_qa-scratch\early-dup\tree origin/main`.
2. In that tree: `python tools/publish_selfcontained.py --rid win-x64` (never a raw `dotnet publish`), then `python tools/capture_build_provenance.py`.
3. **Identify the build by its DLL, not by a shim number (amendment 1):** `sha256sum src/OpenWSFZ.Daemon/bin/Release/net10.0/win-x64/publish/libft8.dll`. Write it to `pins.json` as `play1.start` and `play2.start`, with the commit SHA in the report. The 10-04 main sweep's DLL was `2fa6d993...` (shim 20260058); record whatever this publish holds.
4. Config: a full copy of `D:\Projects\claude\_qa-scratch\rr-fix\config-s4\` with the output folder renamed to `_rr_main<sha7>_s4_daemon_output` (and created under `artefacts\`). `earlyDecodeEnabled` true, `subtractionEnabled` true, `nhard` as the station has it (HK-035: a full file, not an overlay). `config.json` is read back by the launcher into `arm_config.json`.

## 1. Each play (two plays; the count varies between plays of the same stimulus)

1. Station: radio out of the chain, `Voicemeeter AUX Input` -> B1, WSJT-X FT8 Monitor ON, nothing else on the PC (the audio-setup sampler records any change).
2. Start the daemon on the config and run `python qa/rr-study/baseline_preflight.py --wsjt-all-txt <WSJT-X ALL.TXT> --owsfz-all-txt <daemon ALL.TXT> --out <json>`; then stop that daemon (the launcher refuses while another runs).
3. **Start the listener BEFORE the launch** so it sees the first S4 cycle: `python qa/rr-study/early-dup/ws_early_classify_v2.py <play>.jsonl --finalize-file <play>.finalize` (detached, `nohup ... & disown`). It retries the connection every 3 s until the daemon is up.
4. Launch the battery from `qa/rr-study/`: `python run_study_detached.py --daemon-exe <published exe> --config <config> --port 8080 --wsjtx-ini "<WSJT-X - FT991A.ini>" -- --scenarios S4 --skip-warmup --device "Voicemeeter AUX Input"` (detached). About 5 minutes.
5. When the supervisor status is DONE: record the DLL SHA-256 of the published folder again (`play<N>.end`). **Write the path of that play's own `truth.csv` into `<play>.finalize`** (`results\<date>-<sha7>\truth.csv`). The listener then classifies every buffered cycle against THAT truth and exits; wait for the `finalized` line. A play that finalizes with a missing cycle or a disconnect is ED-INVALID: replay once.
6. **Between the plays rename the first run folder** (`results\<date>-<sha7>` -> `...-play1`): the run directory is named after the QA tooling HEAD, so a second play from the same HEAD would reuse it. (Or commit between the plays, as on 2026-10-08.)
7. Teardown and orphan check (HK-019): no daemon, no listener, no `run_study` process left.

## 2. After both plays

`python qa/rr-study/early-dup/early_dup_rows.py play1.jsonl play2.jsonl --pins pins.json`. Report the verdict row, the label counts, the DUP unconfirmed rows per play beside the fix build's 8 and 3, and the exact build (commit and DLL SHA-256). If both plays show 0 unconfirmed rows the verdict is ED-NONE, which is not support for H-DUP.

## 3. Part A2 (optional, the Captain decides; S7 alone, about 28 minutes)

Same steps with `--scenarios S7`. The classifier's per-row label for rows with no same-text final (`NO_MATCH`) is extended to TRUTH / NONTRUTH only if A2 is chosen; it is not built here.
