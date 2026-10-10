# QA → Architect: #194 audio-setup snapshot sampler — AS1–AS5 validation report

- **To:** Architect — cc Captain  **From:** QA (owner)  **Date:** 2026-10-03 ~11:00Z (stamped from `date -u`, HK-017)
- **Branch:** `qa/audio-setup-194` (local, **not pushed**, HK-033). Code under `qa/audio-setup/` only; `git diff --stat -- src/ native/` is empty.
- **Station:** quiet for every row (`validate.py` refuses to start if a python/dotnet/OpenWSFZ process is running; the Engineer was asked to hold builds during AS3).
- **Evidence:** `qa/audio-setup/validation-2026-10-03/` (all results and logs). Libraries: `pycaw` 20260927, `comtypes` 1.4.17, `jsonschema` (all MIT; `qa/audio-setup/requirements.txt`).

## 1. Verdict per row, as pre-registered

| Row | Result | Evidence |
|---|---|---|
| AS1 schema | **PASS** — with a caveat (§3.1) | `as1_result.json`: schema-valid; Banana v2.1.1.9; 5 strips, 5 buses, 32 active endpoints, 5 sessions; 0 fields read as null |
| AS2 positive control | **PASS on run 2; run 1 FAILED** (both reported) | `as2_result.json`, `as2_run1_result.json`. Run 2: gain +1 dB latency 8.78 s, restore 4.81 s; endpoint −0.10 4.84 s, restore 4.88 s; read-back confirms −33.0 and 1.0 restored |
| AS3 cost | **CPU PASS, sample-time FAIL as written** | CPU 0.313 % of one core over 605 s (parent + worker). Sample time: warm max **34.4 ms**; the single cold first sample **1 147 ms** > 500 ms. I do not relabel a row after the fact: see §3.2 for the amendment I propose |
| AS4 teardown | **PASS** (third attempt; two earlier attempts FAILED, §2) | `as34_result.json`: 0 worker crashes, max heartbeat gap 60.5 s (≤ 70), explicit stop-file teardown, return code 0, pidfile removed, orphan check empty, last record is the `end` snapshot |
| AS5 Voicemeeter absent | **PASS** | `as5_result.json`: `voicemeeter: unavailable` logged, Windows still sampled (32 endpoints), clean exit, 0 stderr bytes |

Prediction ledger: **AS-P1 (all five pass first time, 0.60) is MISS**: AS2 failed once, AS4 failed twice, AS3 fails on its sample-time clause. **AS-P2 (device format blob decodes, 0.55): not attempted.** The field is **dropped and says so** (spec §2 allows it); Voicemeeter `Option.sr` (48 000) and the WAV headers cover the rate.

## 2. Defects the validation found in my own instrument (all fixed, none hidden)

1. **Read-back was stale (AS2 run 1).** A Voicemeeter read straight after a set returns the OLD value; run 1's read-back said −32.0 although the live value was −33.0 (checked separately). Fix: the validator waits 1.5 s, reads, waits again, reads.
2. **Native crash, twice, in 10-minute runs (AS4 attempts 1 and 2).** `Windows fatal exception: access violation` inside `pycaw.GetAllSessions`, raised from a COM `Release` during garbage collection (stack in `validation-2026-10-03/as34_attempt2_crash_stderr_head.txt`, 3 995 repeated lines in the full 4.2 MB stderr; attempt 1 died with only 557 bytes of stderr because the pipe was unread, see `as34_attempt1_crash_result.json`). It could not be reproduced on demand (200 s at a 0.5 s period was clean). A native fault cannot be caught in Python, so the sampler is now **a supervisor plus a worker process**: a worker death is logged as a `worker_crash` record (exit code, stderr tail) and the worker restarted (`restart` snapshot). The worker also runs with the cyclic GC disabled, which is the path in the stack. **I have not proved the GC change removes the crash; the supervisor is what guarantees the run survives.** AS4 attempt 3 had 0 crashes; one clean 10-minute run does not prove absence.
3. **The first 12 s of AS2 run 1 was a false positive hunt:** `Strip[3].Gain` read −30 / −21 / unmuted in the start snapshot, then −33 / −24 / muted five seconds later. A login-settle step (two reads must agree) was added, but see §3.3: it is **not shown to fix** this.
4. **Cheap enumeration.** `AudioUtilities.GetAllDevices()` cost ~700 ms per sample; `EnumAudioEndpoints` with a per-process friendly-name cache costs ~12 ms.
5. **The validator's own "run active" guard** matched my bash wrapper's command line and refused to start; it cost 15 minutes. Fixed (matches only python/dotnet/OpenWSFZ processes).
6. **Test harness:** subprocess calls inherited an invalid stdin handle (`WinError 6`), and the test polled for 15 s, which a build on the PC outlasted. Fixed: every subprocess takes `DEVNULL`; the poll deadline is a named constant (60 s). 80 consecutive passes after the fix, 9 tests.

## 3. Findings for the Architect

1. **AS1 cannot be checked against the API.** Voicemeeter's Remote API returns rc 0 and `0.0` for ANY index (`Strip[5].Gain`, `Bus[9].Gain`). It has no count call. "Every strip and bus the API reports is present" is therefore checked against a table keyed by the **reported type** (Banana = 5 strips, 5 buses, routes A1–A3 B1–B2), asserted in `test_sampler.py`. The count comes from Voicemeeter's documentation, not from the instrument. A non-Banana type would need its row verified the same way.
2. **Cold first sample.** The first sample after start takes ~1.1 s (COM initialisation, name cache). **Proposed amendment (needs your ruling, I do not self-apply it):** AS3's ≤ 500 ms clause applies to warm samples (every sample after the first), and the cold sample is reported separately with a ≤ 2 s bound. Under that reading AS3 is a PASS (34.4 ms warm max). Under the row as written it is a FAIL.
3. **Unexplained start-state readings (open).** In two of the runs the sampler's start snapshot read `Strip[3].Gain` = −30 (and in run 1 also `Strip[1].Gain` −21, `Strip[0]` unmuted) while 25 fresh Voicemeeter logins in a row read −33. In run 1 the correct values appeared at the next tick; in the AS4 attempt-2 run the −30 persisted from 10:24:42 until a recorded change to −33 at 10:29:00. Either the API serves stale values for a few minutes after some logins, or a person or macro changed the setting. **The instrument cannot tell which**, and I did not name a cause. That is exactly the question the sampler exists to answer; treat any start snapshot as `unverified` until a second tick agrees.
4. **Detection latency is bounded but not generous.** A change is seen about 1–2 s after the sample that follows it, because the API itself lags: at a 1 s period the lag is 0.7–2.1 s; at 5 s it is 4.0 s (down) and 7.0 s (up), worst observed in AS2 8.78 s against the ≤ 10 s bound. **Margin 1.2 s.** Recommend a 2 s production period (cost: warm sample ~30 ms, about 1.5 % of one core at 2 s, to be re-measured) if you want margin; I have kept the spec's 5 s.
5. **Descriptive, not a finding:** Windows default playback is the VAIO strip and Strip[3] is at −33 dB, not −30 dB as in your probe. It changed between 2026-10-02 19:30Z and today, outside any run of mine.

## 4. Writes performed on the station (disclosure)

AS2 run 1 and run 2: `Strip[3].Gain` +1 dB and "Voicemeeter In 5" volume −0.10, each restored (`finally`) and read back. **One more repeat of the same Strip[3].Gain write** (+1 dB and back, four trials at 1 s and 5 s sampler periods) was done to measure detection lag; same setting, no new one, restore read back as −33.0 after every trial. No other write. The sampler contains no setter (`test_sampler.py` greps its source for them).

## 5. Not done / next

- **§5 integration** (R&R tooling and endurance launcher start/stop it; gather into `-gathered`; scan column ±30 s) **not started**: it edits `run_study.py`/the endurance launcher, and I want your ruling on §3.2 and §3.4 first.
- **WSJT-X keys** named from the file itself, read-only: `qa`-side `…\WSJT-X - FT991A\WSJT-X - FT991A.ini` lines 248–251 at the time of reading: `SoundInName`, `AudioInputChannel`, `SoundOutName`, `AudioOutputChannel` (+ SHA-256 of the whole file).
- **NFR-021:** hardware and app names only (the one token the scan flagged, `G70D`, is a monitor's audio device). No callsigns, no message text. A 12-character tail of each endpoint ID is stored, not the full GUID.
- **Push:** none. HK-033 needs the Captain's go for my own new work.
