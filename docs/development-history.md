# Development history

The phases and OpenSpec changes delivered so far, oldest first. The README links here so the project
overview stays short. For the current state of the work, open the [Programme Dossier](programme-dossier.md)
and the GitHub issues, not this table.

**The *Merged* column** is the date the change's OpenSpec folder was archived, which follows the merge by
hours to days, except where noted: `tx-ux-improvements` is its merge-commit date, `sub-feas` is the merge of
PR #196, `early decode` the merge of PR #208, `osd-sign-fix` the merge of PR #221, and `p17` is approximate (not
separately archived).

| Phase | Deliverable | Merged | State |
|---|---|---|---|
| p0 — Foundation | Build pipeline, CI quality gates, tooling | 2026-05-19 | ✅ merged |
| p1 — Walking skeleton | Daemon, embedded web server, WebSocket | 2026-05-20 | ✅ merged |
| p2 — Audio config | Device enumeration, JSON config, Settings REST round-trip | 2026-05-20 | ✅ merged |
| p3 — Web frontend | Dark-theme UI, Settings page, real-time waterfall | 2026-05-20 | ✅ merged |
| p4 — Audio pipeline | PCM capture (WASAPI / arecord / sox), STA threading fix | 2026-05-21 | ✅ merged |
| p5 — FT8 decoder | Cycle framer, spectrum analyser, initial decode pipeline | 2026-05-29 | ✅ merged |
| p6 — File logging | Per-session log files, retention, log-level config | 2026-05-28 | ✅ merged |
| p7 — Device display name | Friendly device names; legacy config migration | 2026-05-28 | ✅ merged |
| p8 — FT8 decode performance | kgoba/ft8_lib (a submodule at the time; since vendored), P/Invoke shim, SNR calibration | 2026-05-28 | ✅ merged |
| p9 — Decode logging | all.txt-style per-cycle decode log | 2026-05-31 | ✅ merged |
| p10 — Ground truth | Replay harness; G6 gate; WSJT-X corpus recovery-rate test | 2026-05-31 | ✅ merged |
| p12 — ft8_lib port | Production P/Invoke decoder; full UAT-01 sign-off | 2026-05-30 | ✅ merged |
| p13 — Cross-platform decoder | libft8.so (Linux x64) + libft8.dylib (macOS ARM64) | 2026-05-30 | ✅ merged |
| p14 — Decode start/stop | FR-017: controlled decode lifecycle; CancellationToken wiring | 2026-05-31 | ✅ merged |
| p15 — Iterative subtraction | Spectrogram-domain second-pass decoder; 69.1% recovery rate | 2026-05-31 | ✅ merged |
| p16 — CAT control | `IRadioConnection` abstraction; `SerialCatConnection`; `RigctldConnection`; `CatPollingService`; CAT config section; Settings CAT UI and status-bar indicator | 2026-06-03 | ✅ merged |
| p17 — Settings UX & freq persistence | Tabbed Settings page; serial port enumeration; three-tier effective-frequency resolution; dial frequency persisted across restarts (FR-035–FR-039) | ≈ 2026-06-04 | ✅ merged |
| p18 — Settings dirty state | "Unsaved changes" badge and breadcrumb/browser navigation guard (FR-040, FR-041) | 2026-06-03 | ✅ merged |
| p19 — Frequency management | Configurable FT8 frequency list; `FrequencyStore`; REST tune endpoint; dial-frequency selector on main page (FR-042–FR-045) | 2026-06-05 | ✅ merged |
| p20 — FA digit width | Self-calibrating digit-width computation in `SerialCatConnection` FA tune command | 2026-06-05 | ✅ merged |
| ft8-qso-answerer-v1 — FT8 TX & QSO answerer | FT8 TX pipeline (native encode, GFSK synthesis, WASAPI playback); `IPttController` abstraction; QSO answerer state machine (auto-answer CQ, 6-message exchange, retry, watchdog, operator abort); ADIF 3.x log writer; `tx` config section; Settings TX fields | 2026-06-15 | ✅ merged |
| tx-ux-improvements — TX UX & config hardening | D-TX-002: config bounds enforced at four layers (HTML, JS, API, config-load) with `Math.Clamp` backstop; `RetryCount = 0` means unlimited retries; FR-UX-002: abort reasons surfaced in scrolling TX history panel; UI-001: obsolete "Enable auto-answer" toggle removed; `ITxEventBus` interface extracted for daemon-level unit testing | 2026-06-24 | ✅ merged |
| gui-tx-panel — main-page TX control | TX enable/disable and live state moved onto the primary page; no longer activated by a Settings toggle or confirmed only via logs | 2026-06-25 | ✅ merged |
| qso-caller — Call CQ origination | `QsoCallerService`: the station can now originate CQ calls, not only answer them — completing both FT8 TX roles | 2026-06-26 | ✅ merged |
| qso-log-dialog — pre-log confirmation | WSJT-X-style confirmation dialog at final transmission; enrich (name, TX power, comments) or discard before the ADIF record is written | 2026-06-27 | ✅ merged |
| decoder-settings-page — live OSD tuning | The three D-009 OSD gate parameters (`K_MIN_SCORE_PASS2`, `OSD_CORR_THRESHOLD`, `OSD_NHARD_MAX`) exposed as live-configurable settings — false-positive/sensitivity trade-off tunable without a native rebuild | 2026-07-02 | ✅ merged |
| lan-remote-access — LAN + passphrase auth | Kestrel bind-address selectable via config; `LanBindPolicy` + `PassphraseAuthPolicy` (`X-Api-Key` / `?key=`); login page; Remote Access settings section. Loopback always trusted; internet exposure out of scope | 2026-07-02 | ✅ merged |
| f-002 — callsign-structure region lookup | Shape-aware callsign parsing and region/entity lookup surfaced to the operator | 2026-07-04 | ✅ merged |
| f-001 — hashed-callsign resolution | Session-scoped 22-bit hash table resolves nonstandard/compound callsigns (`PJ4/Q1ABC`, special-event calls) announced once via a Type 4 message and later referenced by hash | 2026-07-05 | ✅ merged |
| f-003 — AP-assist for nonstandard callsigns | AP-assisted decode of nonstandard callsigns (Gap B) building on the f-001 hash table | 2026-07-05 | ✅ merged |
| f-004 — operator visibility | Native shim ABI version exposed in the UI; TX/Call-CQ button visual states (armed vs transmitting); log viewer (Settings Logs tab + standalone full-log page); waterfall display modifiers | 2026-07-05 | ✅ merged |
| gridtracker-udp-reporting — external reporting | Speaks the WSJT-X UDP network protocol so GridTracker2, JTAlert and similar tools can plot spots and log QSOs; inbound Reply is opt-in, while Halt Tx is always honoured as a safety path; multiple simultaneous targets; off by default. Later: a leader/follower role lets two running instances present as a single connection | 2026-07-12 | ✅ merged |
| remote-daemon-restart — restart from the UI | `POST /api/v1/system/restart` restarts the daemon in place, so settings that only apply after a restart (PTT method, LAN bind) can be applied from a remote browser | 2026-07-15 | ✅ merged |
| daemon-background-mode — detached daemon | `--background` starts the daemon detached from its console so the terminal can be closed | 2026-07-16 | ✅ merged |
| cat-tx-ptt — transmitter keying | Operator-selectable PTT method (`AudioVox` default, `CatCommand`, `SerialRtsDtr`) with a hard watchdog ceiling and guaranteed release on exception, dispose and shutdown paths | 2026-07-18 | ✅ merged |
| engage-window — late-click engage | A manual engage fires whenever the cycle phase is right and stops at the window boundary if the click was late, instead of deferring a whole cycle | 2026-07-15 | ✅ merged |
| engagement-target-validation — TX target gate | A decoded token that is not a plausible callsign is refused as a TX target (checked against the region prefix table when real region data is loaded) | 2026-07-18 | ✅ merged |
| qso-transcript-panel — QSO transcript | The TX panel shows the actual messages of the live QSO, so the thread is not lost when a decode-panel filter hides the rows | 2026-07-18 | ✅ merged |
| cycle-audio-archive — per-cycle recordings | Optional `.wav` capture of each 15-second receive window (`Off` default, `All`, `Decoded`, `NoDecodes`), in WSJT-X-compatible 12 kHz mono 16-bit PCM | 2026-07-26 | ✅ merged |
| capture-stall-detection-unattended — unattended capture watchdog | Capture health is evaluated by one daemon-lifetime loop, independent of any connected browser, so a silent capture stall on an unattended run is noticed; `GET /api/v1/status` and the WebSocket status carry live, non-latching data-flow fields, and `audioActive` means the same thing on every surface (FR-067 to FR-069) | 2026-09-27 | ✅ merged |
| capture-device-reresolution — a stale audio device heals itself | A Windows endpoint ID that changed after a replug or driver reset is re-resolved by its friendly name before every automatic capture start; automatic restarts use a bounded backoff and never give up; the status endpoint reports the recovery state; enumerated devices report whether they are available (FR-070 to FR-073) | 2026-09-27 | ✅ merged |
| config-save-preserves-unsent-settings — a save never resets a setting | `POST /api/v1/config` applies the request as an overlay on the stored configuration: a key the request does not send keeps its value at any depth, so an unrelated Settings save cannot silently reset, for example, the cycle audio archive; every save logs the paths it changed (FR-074, FR-076) | 2026-10-01 | ✅ merged |
| sub-feas — residual-decode subtraction | An additional decode pass that subtracts the decoded signals and decodes what they were hiding, with a configurable worker count; the normal decode is shown first and the pass's extra decodes follow as a second batch. Built behind a flag, then **on by default since v0.54** with a one-time migration of existing installs (FR-077, FR-082) | 2026-10-01 | ✅ merged |
| early decode (#122 step 4) | A decode of the first part of each window that runs about 2 s before the window ends, so rows reach the decode panel sooner. Early rows are marked *early* and are replaced by the final row when the full decode agrees, or stay marked *unconfirmed* when it does not. **Panel only**: nothing early is written to ALL.TXT, sent over UDP, used by the QSO automation or archived. **On by default** (the Captain's decision of 2026-10-04); to turn it off untick *Show early decodes* in Settings, Advanced Decoder Settings, or set `decoder.earlyDecodeEnabled` to `false` (FR-083) | 2026-10-04 | ✅ built, on by default |
| osd-sign-fix (#215) — correct the OSD fallback's input sign | The ordered-statistics fallback read its soft decisions with the opposite sign to the extractor and belief propagation, so every OSD accept since shim 20260025 was a chance CRC hit. The fix gives OSD and its acceptance gate the same corrected array; a process-global switch (replay use only, not configurable) restores the old behaviour for A/B measurement. A correctness fix, **not** a decode-rate lever. The OSD gate cap (`nhard`) had been set on the inverted output, so it was re-derived on the corrected one: calibration chose 24, and **`decoder.osdNhardMax` now defaults to 24** (valid range [24, 100], an existing install's 40 migrated once, FR-085). Decision replay on 860 cycles of a different 40 m night: **F-GO, +0.208 pp [+0.117, +0.326]** of WSJT-X's decodes (about one extra decode per 16 cycles), SNR reporting unchanged; replay, one band, not measured live (FR-084, FR-085; shim 20260060; deployed on the station 2026-10-09 14:01:15Z, which starts a new data era) | 2026-10-09 | ✅ merged (PR #221) |
