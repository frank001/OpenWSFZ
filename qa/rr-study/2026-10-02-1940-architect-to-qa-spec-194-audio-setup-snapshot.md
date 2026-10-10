# SPEC — #194: AUDIO-SETUP SNAPSHOT — record the station's audio settings during every run, so an anomaly never depends on anyone's memory

- **To:** QA (owner; QA may assign the Engineer, one owner on the board) — cc Captain  **From:** Architect  **Date:** 2026-10-02 ~19:40Z (HK-017)
- **Branch:** `arch/194-rr-improvements`. Docs only: `git diff --stat -- src/ native/` empty. **QA tooling under `qa/` only. No daemon change.**
- **Captain, 2026-10-02:** *"yes, add the audio-setup snapshot when you are sure this is possible."* Feasibility was **proved first, read-only** (§2).
- **Why (HK-027):** the scan found a shared event at 11:08:45Z on 2026-09-23. The event log was empty, and the Captain (rightly) cannot recall a minute nine days back: *"I'm only human."* A human is an actuator, not a recorder. The instrument must record the state.
- **Priority:** after the edge test and the scan's validation. 🛑 **Do not add it to the edge test, which is already frozen.**

## 1. What it is

A small **sampler process** started with a run and stopped with it. Every **5 s** it reads the audio setup and appends to `audio_setup.jsonl` in the run's gathered directory:
- one **full snapshot** at start and end;
- a **change record** (UTC, field, old → new) whenever any field changes;
- a **heartbeat** every 60 s (UTC and a SHA-256 of the full state), so a gap in sampling is visible as a gap in heartbeats.

A sampler rather than snapshots at batch boundaries, because the harness plays up to 20 slots as **one continuous stream** (`run_scenario.py:1196`). A mid-batch change would fall between batch snapshots. The scan joins on UTC: every flagged slot lists the setup changes within ±30 s.

## 2. Proved possible (Architect probe, 2026-10-02 ~19:30Z, read-only, no run active)

| Source | Readable, shown on this PC | Method |
|---|---|---|
| **Voicemeeter Remote API** | ✅ type 2 (Banana) v2.1.1.9 running. `Strip[i].Gain/Mute`, routing `Strip[i].A1…B2`, `Bus[j].Gain/Mute`, `Option.sr` (48 000), `Bus[j].device.name`. Login and Logout returned 0 | `ctypes` on the installed `C:\Program Files (x86)\VB\Voicemeeter\VoicemeeterRemote64.dll`. **Not vendored**: called at run time like an OS API. `VBVMR_IsParametersDirty` before reads |
| **Windows Core Audio** | ✅ 19 active render and 13 capture endpoints, each with master volume (scalar) and mute. Default render device. Per-app render sessions (process, volume, mute) | `pycaw` 20260927 + `comtypes` 1.4.17, **both MIT** (licence policy: permissive only, OK). Add them to `qa/` requirements |
| Device format (rate, bits) per endpoint | ⚠️ **present but not decoded**: the `PKEY_AudioEngine_DeviceFormat` blob exists, but `pycaw` does not parse it | QA proves a WAVEFORMATEX decode, **or drops the field and says so**. Voicemeeter's `Option.sr` and the WAV headers already cover the rate |

The probe also showed what the snapshot is for, as a **descriptive** example, not a finding: the Windows default playback device is **"Voicemeeter Input" (VAIO, `Strip[3]`)**, at −30 dB and **not routed to B1**. `Strip[4]` (AUX, where the harness plays) **is** routed to B1. So, at these settings, Windows notification sounds do not reach the decoders. The snapshot makes that a per-run fact, not an assumption. It also narrows the scan's notification-sound blind spot (PC1 ruling A7): a sound can only reach the decoders if a snapshot shows a route to B1 from a strip that carries system audio.

## 3. Fields (schema-versioned JSON; enumerate by the API's reported Voicemeeter type, never by hard-coded counts)

- **Voicemeeter:** type, version, `Option.sr`; per strip: label, gain, mute, every bus route (A1…B2 for Banana); per bus: gain, mute, device name.
- **Windows:** default render and capture devices (console and communications roles); per active endpoint: friendly name, the last 12 characters of the ID (enough to tell apart; endpoint GUIDs go stale anyway), flow, volume scalar, mute, and device format if §2 proves it; per render session: process name, volume, mute.
- **WSJT-X:** SHA-256 of the instance's `.ini`, plus the values of its audio-device keys (QA names them with FILE:LINE from the file itself, read-only).
- 🔒 NFR-021: hardware and app names only. If any user-visible field could carry a callsign, the sampler drops it and says so.

## 4. Pre-registered rows (validation, once, on a quiet station; no run active)

| Row | Predicate |
|---|---|
| AS1 schema | the full snapshot validates against the committed schema; every Voicemeeter strip and bus the API reports is present |
| AS2 positive control (HK-026) | with no run active, QA changes and restores **two** settings that do not feed the decoders: `Strip[3].Gain` by +1 dB through the API (then back), and the volume of an unused endpoint (e.g. "Voicemeeter In 5") by −0.10 (then back). **PASS iff** each change and each restore appears as a change record within **≤ 10 s**, with the right old and new values, and a read-back confirms both settings are restored |
| AS3 cost | the sampler's CPU over 10 min is ≤ 1 % of one core, and one sample takes ≤ 500 ms (it must not perturb a timing run) |
| AS4 teardown (HK-019) | the sampler stops with the run, by explicit teardown; orphan check empty; heartbeats show no gap > 70 s |
| AS5 Voicemeeter absent | with Voicemeeter not running (simulated by pointing at a missing DLL path), the sampler logs `voicemeeter: unavailable` and keeps sampling Windows. It never crashes the run |

AS2 writes to the station's Voicemeeter. 🔴 **Only with no run active, only those two settings, and restore verified by read-back.** No other write ever. The sampler itself is **read-only**.

## 5. Integration (after AS1–AS5 pass)

Started by the R&R run tooling and by the endurance launcher, stopped by their teardown, and gathered into the run's `-gathered` directory (HK-016). The scan (§7 of its spec) gains one column: setup changes within ±30 s of each flagged slot.

## 6. Predictions (blind)

| # | Prediction | P | Class |
|---|---|---:|:---:|
| AS-P1 | AS1–AS5 pass first time | 0.60 | H |
| AS-P2 | the device-format blob decodes (the field is kept) | 0.55 | H |
