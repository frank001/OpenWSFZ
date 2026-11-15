# Endurance run HANDOFF (rewritten at every phase; last write 2026-10-23T08:01:25Z)

**Phase now: DONE**  

This run is UNATTENDED. Corpus dir: `D:\Projects\claude\OpenWSFZ\worktrees\qa\artefacts\20261022_1949_endurance_run`
- Window (UTC): start `2026-10-22T19:49:19Z`, end `2026-10-23T08:00:00Z`.
- Everything is in `supervisor.log` + `events.jsonl` (restarts, health strikes). `heartbeat.json` = last loop tick.
- Arm-time record (recorded, never configured by this script): `arm_config.json`.
- This script does NOT run analysis. Once phase is DONE, run the STANDARD POST-RUN ROUTINE
  (Captain's instruction, 2026-09-24 -- spectrum scan BEFORE reading any decode-rate number,
  every time, no exceptions) against the gathered `<gathered>` dir, in order:
    1. `python qa/endurance/endurance_anova_wsjtx.py --ours-all-txt <gathered>/owsfz/ALL.TXT
       --wsjtx-all-txt <gathered>/wsjt-x/ALL.TXT --out <gathered>/anova_report.md
       --arm-config D:\Projects\claude\OpenWSFZ\worktrees\qa\artefacts\20261022_1949_endurance_run/arm_config.json --hours <run length> --radio-chain "<as configured>"`
       (pass --hours explicitly -- omitting it silently drops this run's own historical row,
       found live 2026-09-24)
    2. `python qa/endurance/spectrum_scan.py --wav-dir <gathered>/owsfz/wav
       --out-json <gathered>/spectrum_scan.json`
    3. `python qa/endurance/spectrum_scan_report.py --scan-json <gathered>/spectrum_scan.json
       --wav-dir <gathered>/owsfz/wav --all-txt <gathered>/owsfz/ALL.TXT --out-dir <gathered>
       [--control-scan-json <a prior comparable run>/spectrum_scan.json]`
    4. `python qa/endurance/render_dossier.py --run-dir <gathered>` -- writes
       `<gathered>/FINAL_REPORT_dossier.html`, ready to publish with the Artifact tool.
  HK-037: steps 2-4 never print or persist message text, only aggregate counts -- do not
  hand-roll a spur investigation with ad-hoc `python -c` message-text prints instead of this
  pipeline; that is exactly how a real callsign reached a published Artifact on 2026-09-24.

## If you are the next QA session
1. `Get-Content <corpus>\heartbeat.json`, `Get-Content <corpus>\supervisor.log -Tail 40` -- is it alive, which phase.
2. If phase is DONE: gathered artefacts are wherever the standard gatherer's own README says
   (its output dir is recorded in `events.jsonl`'s `gathered` event). Run the STANDARD POST-RUN
   ROUTINE above, in order -- step 1 appends this run to the historical table automatically.
3. If the supervisor is DEAD before DONE: the daemon may still be capturing. Do NOT delete
   anything. `python <corpus>\tools\endurance_supervisor.py --resume <corpus> --daemon-exe
   ... --config ... --port ... --wsjtx-ini ...` (same arguments as the original arm) re-attaches
   from `state.json`.
4. HK-019 at the end: no OpenWSFZ.Daemon.exe left running.
