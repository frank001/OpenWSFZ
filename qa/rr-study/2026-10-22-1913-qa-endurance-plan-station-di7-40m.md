# QA: plan for a 40 m endurance run on the station PC with the synced `decoding_improvement` daemon and every improvement setting on

**Stamped:** 2026-10-22T19:13:08Z by `date -u`. **Status: PREPARED, NOT STARTED.** The Captain's instruction (QA's window, 2026-10-22): *"prepare a separate plan on the local station. The same decoding_improvement daemon with all the improvement settings on for an endurance run, 40m. usual B1 audio path. end time about 10:00 am tomorrow. I will clean and start wsjt-x FT991A."* Separate from the `sol` R&R plan (`2026-10-22-1900-qa-rr-sweep-x3-sol-di7-coh-plan.md`). Nothing runs without the Captain's go (§7). No push, no `src/` change.

## 0. What it is, in one paragraph

One unattended window on the station PC, 40 m (7.074 MHz), the live radio on Voicemeeter Stereo Input 1 routed to **Out B1**, the OpenWSFZ daemon and the Captain's WSJT-X (FT-991A profile) both reading **Voicemeeter Out B1**. It is the existing endurance machinery (`dxped225-arm.py` is the template: the #225 run of 2026-10-19/20, 19.4 h, which I will copy to a new arm script `di7-endurance-arm.py`, with `--end-utc`), run on the synced `decoding_improvement` build, **receive-only** (CAT off in the daemon's config because WSJT-X holds CAT; no TX; no external reporting).

**End time.** "About 10:00 am tomorrow" read as the Captain's local time. The PC is on W. Europe Standard Time (CEST, UTC+2 in the daemon log), so **10:00 local = 08:00Z on 2026-10-23**. *Please confirm this reading* (§7). The arm script derives the hours from the real start minute (`--end-utc 2026-10-23T08:00:00Z`).

## 1. The gate: what must be true before the run starts

1. DI sync 7 accepted: the Developer's merge `56736264` reviewed (HK-039 record `4d9c1230`), QA's acceptance runs green (the pre-merge check, the decode-identity check against `main`, both under way at 19:13Z), the PR into `decoding_improvement` merged on green CI (the Captain's go covers it).
2. The daemon is **published from the merged DI tip** with `tools/publish_selfcontained.py --rid win-x64` (never a plain `dotnet publish --self-contained`: that is a Native AOT build with broken WASAPI), in a scratch worktree under `_qa-scratch\endur-di7\tree` (not the station's own deploy folder), `tools/capture_build_provenance.py` run next to it, `build_provenance.json` `build_dirty` false.
3. **The pin is asserted in code, not in prose:** the arm script carries the published `libft8.dll` SHA-256 and the commit hash as constants and aborts before one decode if either differs (as `dxped225-arm.py` does). They are filled in from the published tree after the merge; I will quote them in the report before starting.
4. The station state, which the Captain controls: the station daemon (pid 37328, port 8080, CAT, 20 m) **stopped** so port 8080 is free and CAT is released; WSJT-X (FT991A profile) **cleaned and started by the Captain**, tuned to 7.074 MHz on 40 m, `SoundInName` = *Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)* (the script reads the `.ini` and aborts otherwise), and it must **not transmit**. I stop the station daemon only on the Captain's word.

## 1a. After the Architect's (k) review (`arch/di7-era-runs` `dfa31391`, K5 to K9), recorded 2026-10-22T19:45Z by `date -u`

- **K5, the build pin.** PR #255 is **merged** (2026-10-22T19:43:25Z, merge commit `39038171ad84c2f973d522395d4c7d91e4e10b8f`). The merged tip's **tree is identical to `56736264`'s** (`git rev-parse <tip>^{tree}` = `f717a850557d6949…` for both), so `git diff --stat 56736264 origin/decoding_improvement -- src native` is **empty**. The arm script therefore **keeps `COMMIT` = `56736264…` and `DLL_SHA` = `0e180dfc…`** (the published Windows DLL is the committed one; CI rebuilds only the Linux and macOS binaries, in a follow-up PR like #254). If that follow-up PR changes anything but `.so`/`.dylib`, I say so before arming.
- **K6 (done and tested).** The arm script now exits non-zero **and stops the run** (mutes the radio strip, stops the daemon, the supervisor and the watcher) if the read-back is not flag `true`, depth `Deep` and `subtractionMaxThreads` 8. The stop expression was tested on a decoy process (it stops the decoy and spares itself).
- **K7** corpus location OK. **K8** the station-daemon stop happens only on the Captain's word; he gave it at 19:19Z ("just close the station daemon") and it was stopped then.
- **Threads 8** (§2): the Captain's later decision replaces "auto"; K9 is resolved.

## 2. The configuration: all improvements on, explicit

Built by the arm script from the proven base (`rr-main` config) plus the station's own decoder section, with these **asserted** before launch:

| Setting | Value | Why |
|---|---|---|
| `decoder.decodingDepth` | **Deep** (third pass) | read back from `/api/v1/status` `thirdPass.decodingDepth` |
| `decoder.coherentFallbackEnabled` | **true, written explicitly** | the new default is on, but the station's own config carries an explicit `false` from the R14 teardown, and the read-back is compared with an explicit value |
| `decoder.osdNhardMax` | 24, migrations applied | the station's decoder section, as in #225 |
| `decoder.subtractionEnabled`, `earlyDecodeEnabled` | true | the station's decoder section |
| `decoder.subtractionMaxThreads` | **8** (asserted `== 8` in the arm script) | the earlier parameter as in #225, the R&R runs and the replays: the Captain's later decision, relayed by the Architect (~19:5xZ), **supersedes his first answer "0 = auto"** (§7a). K9 is resolved: the thread count is like-for-like with #225; the run is still a different build and era, so it is **never pooled** with #225 |
| `cat.enabled` | false (asserted) | WSJT-X holds the radio |
| `tx.autoAnswer`, `externalReporting.enabled` | false (asserted) | receive-only; no spots leave the PC |
| `cycleAudioArchive` | mode `all`, 16 GiB cap, 48 h | so the night can be replayed offline afterwards (the 20 m live run could not be, which cost us requirement 9) |
| `audioDeviceId` / name | Voicemeeter Out B1 | the usual path |
| Decode log / daemon logs / ALL.TXT | inside the corpus folder `artefacts\<stamp>_endurance_run` | HK-016 |

Everything else in the decoder section is the station's own (the Architect's rule for #225: no other change). **Validity rows (Architect's review, 2026-10-22, K2, K6 and the endurance V-F ruling):** V-D depth read back Deep **at the start** (the arm script exits non-zero and stops the run if it is not Deep, K6). **V-F the fallback ran:** the config read back `true` (`GET /api/v1/config`) **at the start only** (no "end" read-back: the night's per-cycle line count is the end evidence; a start mismatch also stops the run, K6), and the daemon's per-cycle `Coherent fallback:` line present in ≥ 95 % of the `Cycle ...: N decode(s) found` lines (the denominator is the per-cycle Cycle lines; 95 % is the Architect's decision value; the FULL R14 live window had **504 of 504 = 1.000**, counted by QA 2026-10-22 19:41Z from the daemon file log). **Descriptive V-F reading:** the R12′ lines show `workers=8` (the config's `subtractionMaxThreads`); the first line's value is quoted at the arm read-back. A V-F mismatch voids the era row, not the run.

## 3. Voicemeeter and the run itself

- Strips (read and asserted before launch, as in #225): Strip[0] (radio) routes to B1; Strip[2] does **not** feed B1; Strip[4] (AUX, the WAV replay) **muted**. Strip[0] is **unmuted** just before the start and **muted again** by a detached watcher 2 minutes after the window ends (`vm_strip.py`, every write read back and logged to `voicemeeter_actions_<stamp>.jsonl`). QA may mute and unmute strips only (standing permission).
- `run_endurance.py` (the existing runner) starts the daemon and its supervisor (`endurance_supervisor.py`: the PRECHECK appraiser gate incl. device-name match and dial match, the watchdogs, the gather on close); a detached **F2 poller** (1 Hz, ends 10 min after the window) records the capture counters.
- The arm script writes `arm_readback.json` (config and status read back 20 s after the start) and prints the **depth read-back**; I stop and look if it is not Deep, and the same for the flag.

## 4. What the run answers, and what it does not (HK-022, HK-038)

- **It answers:** how the full improvement set (Deep third pass, residual pass, early decode, the coherent fallback as batch 4) behaves over about 10 h of real 40 m traffic on the station PC, read against the **live WSJT-X on the same audio**: the standard Section 4 rows (live WSJT-X, same band; HK-036), the decode counts per batch, the fallback counters (R12′ per cycle: attempted, published, abandoned, wall time, workers), the timing of batch 4 from slot start, capture health (overruns, channel drops), and, because the audio is archived, an offline replay afterwards.
- **A new data era.** The Captain's "count against the new data era" holds here as for the R&R series: this run is a row of its own, **label `DI7COH-E`**: DI synced with `main` (merge 2026-10-22 18:17:34Z), shim 20260070, Deep, fallback on, `nhard` 24. **Never pooled** with #225 (flag-less, `main` `5229beec`-era), the 2026-10-18/19 MAINDEEP, TPDEEP, B2CAP, or the flag-ON live check (20 m, with a transmitter, 2 h).
- **It does not answer:** whether the fallback's gain over WSJT-X (+3.82 pp on the 09-22 replay) appears live at the same size (the run measures matched counts against WSJT-X, descriptive); anything about TX or QSO behaviour (receive-only); the deferred-reply path.
- **No pass/fail bar of QA's own is added** (HK-038: an invented bar would need a source). The run's read follows the established endurance reading: Section 4, HK-036, the capture counters, the F2 clamp check, the live-WSJT-X rows.

## 5. The close (after 08:00Z)

`artefacts\<stamp>_endurance_run` is gathered by the supervisor; I read Section 4 before any number is cited (HK-036), `f2_station_count.py` on the corpus, confirm Strip[0] muted, run the offline replay of the archived audio if the Captain wants it, copy the folder into `qa\endurance` (the standing results location), update the board in the same edit (HK-024), and report once. **Nothing is pushed.**

## 6. Risks I see

1. **Timing.** The gate has to be met before the start: the identity check is about 45 min, then push, PR, CI (two runs of about 8 min), merge, publish. If the merge slips, a start after about 22:00Z shortens the window (10 h from 22:00Z; 08:00Z is fixed by the Captain's end time).
2. **The station is the live station.** Stopping the station daemon ends the 20 m listening and CAT control; the Captain's WSJT-X takes over. After the run the station daemon is **not** restarted by QA; whether it comes back on the merged build, with the flag explicit, is the Captain's (the board's M5 decision).
3. **CPU on the PC.** The run is CPU-heavy by design; **nothing else CPU-heavy runs on the PC during it** (a Developer build or test run would perturb the timing and the capture). The `sol` series is on another machine and does not compete.
4. **Disk.** The PC's D: drive has 1.5 TB free; the archive cap is 16 GiB.
5. **A daemon crash or WSJT-X stall** is handled by the supervisor and the watchdogs as in #225; QA cannot attend overnight, so the read after the close is the safety net.

## 7a. The Captain's answers (QA's window, 2026-10-22, recorded 19:16:05Z by `date -u`)

1. **End time: confirmed** (10:00 local = 08:00Z on 2026-10-23). 2. **`subtractionMaxThreads`: first answer 0 (auto); SUPERSEDED by the Captain's later decision, relayed by the Architect after the (k) review (his words: "tell QA to comply with the earlier 8-thread parameter") = 8.** QA implemented 8 and asks him to confirm it in QA's window, since his own answer here was "auto". 3. **Cycle-audio archive: on.** 4. **The go and the station-daemon stop: he asked for an explanation (given in the reply; his go is still to come).** 5. **After the close: leave the PC up.**

## 7. Decisions for the Captain (with their data; nothing started)

1. **End time:** 10:00 local = 08:00Z on 2026-10-23? *Data:* the PC logs UTC+2.
2. **`subtractionMaxThreads`:** **8** (as #225 and the R&R and replay runs: comparable with them, 8 fallback workers) or **0 = auto** (the station's own config; 14 workers resolved live on this PC; what the station will actually run after a redeploy). *My recommendation: 0 = auto,* because the question of this run is how the station behaves; the resolved worker count is in every R12′ line, so either reading stays honest. *Consequence:* timing numbers are not comparable with the 8-thread replay (the 20 m live check already ran at 14 workers).
3. **Cycle-audio archive on** (recommended, 16 GiB cap) or off.
4. **Go**, after §1 is met, and **your word to stop the station daemon** (pid 37328) when the time comes; your WSJT-X start follows.
5. **After the close:** hibernate the PC (as on 2026-10-21) or leave it up for the replay and the analysis?
