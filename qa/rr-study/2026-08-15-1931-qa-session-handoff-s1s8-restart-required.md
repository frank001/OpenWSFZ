# QA session handoff — S1–S8 R&R study setup, machine restart required

**2026-08-15 19:31Z** · branch `feat/r1b-sync-refiner-instrument-correction` @ `8d6e1b1` (repo clean,
no uncommitted src changes — only local scratch files, see Cleanup below)

## Goal (Captain's request, this session)

Set up and run a full **S1–S8 R&R study** (`qa/rr-study/run_study.py`) against the current binary:
WSJT-X (`WSJT-X - FT991A` profile) listening to `CABLE Output`, OpenWSFZ daemon at port 8080 also
on `CABLE Output`. ALL.TXT files deliberately **not cleared** — confirmed non-issue, `matcher.py`
buckets by exact UTC 15 s slot key, stale entries from 6–8 days ago cannot collide with this run's
truth rows.

## What was done, in order

1. **Rebuilt the daemon** (`dotnet build src/OpenWSFZ.Daemon/OpenWSFZ.Daemon.csproj -c Release`).
   The prior `bin/Release` output predated the r1b native rebuild (committed `libft8.dll` at
   23:05 on 8/14, build output only from 17:07) — six hours stale, would NOT have carried the r1b
   correction (shim 20260041). Confirmed post-build via `/api/v1/status`: `"shimVersion":20260041`.
2. **Edited the live `config.json`** at `C:\Users\Frank\AppData\Roaming\OpenWSFZ\config.json` —
   this is the Captain's **production** daemon config (PTT/CAT, GridTracker external reporting,
   tx.callsign PD2FZ all live). Changed only:
   - `audioDeviceId`: was `{0.0.1.00000000}.{67987b85-f257-41bc-8ab0-b22d6bc5e452}` (Microphone,
     USB Audio CODEC) → now `{0.0.1.00000000}.{ECB41D74-1AA5-43B1-AC89-B69E40510F00}` (CABLE Output)
   - `audioDeviceFriendlyName`: was `"Microphone (2- USB Audio CODEC )"` → now
     `"CABLE Output (VB-Audio Virtual Cable)"`
   - **Nothing else touched** — `audioOutputDeviceId`/`audioOutputFriendlyName` (Speakers, USB
     Audio CODEC) left alone; `decoder.kMinScorePass2=10` / `osdCorrThreshold=0.1` /
     `osdNhardMax=60` are pre-existing non-default tuning, not changed by me, worth noting if S1–S8
     results get compared against an earlier run with different decoder settings.
   - **⚠️ Revert after the study** if live on-air monitoring should resume: restore the
     `audioDeviceId`/`audioDeviceFriendlyName` pair above to the Microphone values.
3. **Started the daemon** on port 8080 (`OpenWSFZ.Daemon.exe` from `bin/Release/net10.0/`,
   run from repo root so relative `ALL.TXT`/`logs` paths resolve correctly). Confirmed only ONE
   live `CABLE Output` endpoint exists (`Get-PnpDevice -Class AudioEndpoint`), so no stale-GUID
   ambiguity (the standing operational note about endpoint GUIDs going stale did not apply here).

## Blocker chased, and where it stood at the "restart required" call

- **First ~4 launches** (fresh process each time, not a stuck-retry-loop artefact): WASAPI capture
  failed immediately on `Initialize` with `0x887C001A` (`AUDCLNT_E_DEVICE_IN_USE`). Cross-checked
  with the repo's own `qa/rr-study/verify_wasapi.py` (read-only tone-injection diagnostic, same
  WASAPI path) — it opened without exception but recorded pure silence on `CABLE Output`, and its
  own built-in diagnosis flagged the VB-CABLE loopback as broken at the driver/OS level, matching
  the daemon's hard failure.
- **After the Captain's 2nd "try again"** (external fix applied outside this session — unconfirmed
  what, exactly; asked once, not answered): the lock symptom **cleared**. Daemon status went
  `captureActive:true`, `audioActive:true`, heartbeat `dataFlowing:true`. **However**
  `verify_wasapi.py` re-run at that point *still* reported `CABLE Output RMS = 0.000000 [SILENCE]`
  on both CABLE Output and Voicemeeter B2 taps, and the daemon logged repeated
  `Cycle skipped - RMS 0.000E+000 is below silence guard`. This is consistent with either (a)
  genuinely nothing being played into CABLE Input at that moment (expected/benign — no synth was
  running), or (b) the loopback path still not actually carrying signal even though the WASAPI
  *lock* is gone. **Not disambiguated before the restart instruction landed** — I did not confirm
  whether WSJT-X's own Band Activity panel was live/decoding during this window, which would have
  settled it.
- Captain then called for a **machine restart** — presumably to clear whatever driver/session
  state was behind the original `AUDCLNT_E_DEVICE_IN_USE`, or as the next step regardless of the
  ambiguous silence reading above.

## Next steps after restart

1. Rebuild is **not** needed again unless `src/` changed further — the Release output already
   carries shim 20260041 as of this session.
2. Confirm WSJT-X (`WSJT-X - FT991A` profile) is running and its `SoundInName=CABLE Output
   (VB-Audio Virtual Cable)` setting (already correct in its `.ini`, unchanged by me).
3. Relaunch `OpenWSFZ.Daemon.exe` from repo root; poll `/api/v1/status` for
   `captureActive:true` AND `audioActive:true` (not just the former — that's what falsely looked
   fine on the previous attempt while output was still silent).
4. Re-run `qa/rr-study/verify_wasapi.py` — require an actual RMS reading above its `0.005`
   threshold (not just "no exception") before trusting the loopback is live.
5. Only then hand off to the Captain to run `python run_study.py` interactively from
   `qa/rr-study/` (Captain's choice: they answer the warm-up/S8 confirmation prompts themselves,
   watching WSJT-X's panel — I cannot see the GUI).

## Cleanup / housekeeping

- Four local scratch log files at repo root are untracked and safe to delete or ignore:
  `daemon_s1s8_launch.log`, `daemon_s1s8_launch2.log`, `daemon_s1s8_launch3.log`,
  `daemon_s1s8_launch4.log` (`git status --short` confirms — nothing else uncommitted).
- The daemon process will die with the restart; no manual teardown needed.
- `config.json`'s audio-device edit (step 2 above) is the only durable state change outside git —
  it survives the restart on disk. Remember it's there.
