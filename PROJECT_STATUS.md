# OpenWSFZ — Project Status

This is the detailed companion to the [README](README.md#status) **Status**
section: every OpenSpec phase and change that has shipped, in order, plus the
one currently in flight. **Update this file in the same commit as any update
to README's Status section** — the README carries only a summary and a link
here.

Current version: see the root [`VERSION`](VERSION) file (CI-checked, gate G9
— do not hand-edit the number anywhere else). As of this writing: **v0.45**.

---

## Active change

### `fix-cycle-boundary-clock-drift` — not merged, held

**Status: implemented and fully gated, but explicitly not ready to merge.**
Root cause is isolated with strong evidence; no fix shape has been chosen yet
(task 8.3, open); three separate live-endurance re-confirmation gates (6.6,
7.6, 8.6) remain unchecked and blocking per HK-011. Do not retune constants
again without resolving 8.3 first.

**Problem:** OpenWSFZ's decoded FT8 DT drifts at ~−0.171 s/hr relative to
WSJT-X. A measured ~−42 ppm capture-device clock-rate error, combined with
`CycleFramer` computing its cycle boundary once at startup and advancing it
purely by sample count (never re-synced to wall clock), predicts −0.153 s/hr
of drift (89% of the measured figure) — accumulating to ~2.6 s of
decode-window lag over a 17-hour session, plausibly contributing to a prior
pilot's ~23.4% "Isolated-class" low-SNR miss rate. The fix is scoped to
`CycleFramer` (the platform-agnostic point downstream of all capture
implementations), not the capture/resampler layer.

**Three implementation rounds, each defeated by live endurance testing:**

1. **Sections 1–4 (original fix):** periodic drift check against `IClock`,
   threshold-gated bounded correction, with `cycleStart` re-anchoring.
   Passed pre-merge gates, but a live pre-merge run found the correction
   firing every single cycle — driven by real capture-pipeline scheduling
   jitter, not genuine device drift.
2. **Section 6 (persistence-gate fix):** requires 3 consecutive same-sign,
   non-decreasing drift readings before correcting, to filter out transient
   pipeline noise. Passed gates, but a 7h54m live endurance run found it
   firing correctly yet only removing ~6% of accumulated drift (960 of
   16,155 samples) — net residual rate still ≈0.171 s/hr, matching the
   original unfixed defect.
3. **Section 7 (correction-sizing fix):** size the correction to the full
   confirmed deviation once the persistence gate fires, bounded only by a
   much larger sanity ceiling. Passed gates, but a 6h16m live re-run found
   corrections sized exactly per formula yet the very next reading returned
   to within ±4% of the pre-correction value — sized correctly, but doesn't
   converge on real hardware.
4. **Section 8 (root-cause instrumentation, in progress):** added
   Debug-level pipeline-stage timing and a hash-table-reject-count log line.
   Two isolated, confound-free unit tests (8.7) **confirmed** a working
   hypothesis: a "discard" (lengthen) correction requires waiting in real
   time to receive discarded samples at the device delivery rate, so the
   very next drift check re-measures that self-inflicted wait as fresh
   deviation — the discard branch's premise that relabelling/skipping
   samples is "free" in real time is false. This narrows, but has not yet
   resolved, what fix shape to implement next.

Full detail: `openspec/changes/fix-cycle-boundary-clock-drift/` (`proposal.md`,
`design.md`, `tasks.md`).

---

## Shipped phases and changes (archived, chronological)

Legend: no tag = shipping product/feature/fix; **[DIAGNOSTIC]** = an
investigative change with a pass/reject verdict, not a standing deliverable;
**[MEASUREMENT]** = a re-run recovery-rate finding, not a code change;
**[HOUSEKEEPING]** = docs/process correction, no behaviour change;
**[REVERTED]** = shipped and later fully reverted, net effect below.

| Date | Change | Deliverable |
|---|---|---|
| 2026-05-19 | `p0-foundation` | Build/CI/tooling foundation: solution/global.json/`Directory.Packages.props`, placeholder `OpenWSFZ.Abstractions`, `TraceabilityCheck`/`LicenseInventoryCheck` tools, three-OS CI workflow. |
| 2026-05-20 | `p1-walking-skeleton` | `OpenWSFZ.Daemon` + `OpenWSFZ.Web`: Kestrel, static files, `/api/v1/status`, WebSocket status/heartbeat, `LoopbackBindPolicy`. |
| 2026-05-20 | `p2-audio-config` | Audio device enumeration (`OpenWSFZ.Audio`) and JSON config persistence (`OpenWSFZ.Config`); `/api/v1/audio/devices`, `/api/v1/config`. |
| 2026-05-20 | `p3-web-frontend` | Real HTML/CSS/JS frontend: main page (waterfall placeholder, decode list, status bar), Settings page, WebSocket status client. |
| 2026-05-21 | `p4-audio-pipeline` | Fixes WASAPI STA-thread enumeration defect; real PCM capture (`IAudioSource`, WASAPI/arecord/sox) at 12 kHz mono float. |
| 2026-05-28 | `p6-file-logging` | Configurable rolling file-logging sink (session + scheduled rotation, retention) via Serilog; Settings Logging section. |
| 2026-05-28 | `p7-device-display-name` | Fixes raw OS device-ID display; friendly device names with legacy-config migration. |
| 2026-05-28 | `p8-ft8-decode-performance` | Homegrown-decoder performance fix: candidate pre-filter, parallelised sweep, cached Goertzel coefficients, CI perf-regression test. |
| 2026-05-29 | `p5-ft8-decoder` | First cleanroom FT8 DSP decoder (`OpenWSFZ.Ft8`): `CycleFramer`, GFSK extraction, Costas sync, LDPC(174,87), CRC-14, message unpacking. |
| 2026-05-30 | `p12-ft8lib-port` | Replaces homegrown DSP internals with P/Invoke wrapper around `kgoba/ft8_lib`. |
| 2026-05-30 | `p13-cross-platform-decoder` | Fixes silent empty-decode defect on Linux/macOS; builds/wires `libft8.so`/`libft8.dylib`. |
| 2026-05-31 | `p10-decoder-ground-truth` | Real-signal ground-truth oracle: captured WAV fixtures + WSJT-X answer keys, replay harness, decoder-correctness CI gate. |
| 2026-05-31 | `p14-decode-start-stop` | FR-017: operator start/stop control for the decode pipeline. |
| 2026-05-31 | `p15-iterative-subtraction` | Second spectrogram-domain decode pass (tile suppression + residual re-decode) to close co-channel gap vs WSJT-X. |
| 2026-05-31 | `p9-all-txt-decode-logging` | WSJT-X-compatible `ALL.TXT` decode log writer; configurable dial-frequency field. |
| 2026-06-02 | `p10-decoder-ground-truth` | **[MEASUREMENT]** 69.1% recovery on the 42-WAV corpus; confirms p15 landed, gap accepted as spectrogram-domain ceiling. |
| 2026-06-03 | `p16-cat-control` | Read-only CAT frequency polling: `IRadioConnection`, `SerialCatConnection`, `RigctldConnection`, `CatPollingService`, Settings CAT section. |
| 2026-06-03 | `p18-settings-dirty-state` | "Unsaved changes" badge and navigation-guard on the Settings page. |
| 2026-06-05 | `p19-frequency-management` | Curated FT8 working-frequency list (`frequencies.json`), CRUD REST endpoints, rig-tuning endpoint. |
| 2026-06-05 | `p20-serial-cat-freq-width` | Fixes hardcoded 11-digit CAT frequency format; self-calibrating digit width (8–11 digit rigs). |
| 2026-06-07 | `fix-d001-pcm-sic` | **[REVERTED]** PCM-domain SIC decode pass. Two fatal crashes, zero measurable improvement — see next entry. |
| 2026-06-07 | `revert-fix-d001-pcm-sic` | **[REVERTED — net effect]** Full revert of PCM-SIC: `K_MAX_PASSES` back to 2, shim 20260003→20260002, tests deleted. PCM-domain SIC did **not** ship; codebase returned to the pre-fix two-pass baseline. |
| 2026-06-07 | `fix-d001-revised` | Captain-gated options menu for the post-revert D-001 path forward; no single implementation committed. |
| 2026-06-07 | `fix-rr001-snr-linearity` | Removes the R6 weak-signal SNR post-correction causing a 0.512 SNR-bias slope (R&R study finding). |
| 2026-06-07 | `fix-snr-tone-bin-selection` | Fixes SNR estimator to read only the transmitted tone's FFT bin instead of max over all 8 tone bins. |
| 2026-06-07 | `rr-study-harness` | Python Gage R&R study harness (`run_scenario.py`, `matcher.py`, `analyse.py`). |
| 2026-06-07 | `s8-realistic-band-scene` | Fixed 12-station realistic band-scene R&R scenario (S8), informational decode-rate benchmark. |
| 2026-06-11 | `fix-d002-snr-bias` | Fixes confirmed +2.42 dB SNR over-reporting bias via RMS PCM normalisation; adds ±2.0 dB SNR-accuracy spec requirement. |
| 2026-06-12 | `diag-d001-h3b-gfsk-sic` | **[DIAGNOSTIC, rejected]** H3b: GFSK quadrature PCM-SIC synthesiser. S7 recovery fell −17.21 pp; superseded by H4. |
| 2026-06-12 | `diag-d001-pcm-sic` | **[DIAGNOSTIC, rejected]** H3: re-attempted PCM-domain SIC with heap buffers. S7 recovery fell −13.98 pp. |
| 2026-06-12 | `diag-d001-three-pass-sic` | **[DIAGNOSTIC, rejected]** H2: `K_MAX_PASSES` 2→3. S7 fell −4.30 pp to 50.54%. |
| 2026-06-12 | `fix-synth-brickwall-noise-filter` | R&R synthesiser: FFT-brickwall noise filter replaced with windowed Kaiser FIR lowpass (QA tooling only). |
| 2026-06-12 | `rr-corpus-replay` | S6 real off-air-corpus R&R study (42 WAVs, K=3 randomised replay via VB-CABLE). |
| 2026-06-12 | `siggen` | Standalone multi-signal audio scene generator (QA tooling only). |
| 2026-06-12 | `synth-cli-args` | R&R synthesiser constants exposed as CLI flags; standalone one-shot WAV generator (QA tooling only). |
| 2026-06-13 | `diag-d001-h4-review-fixes` | **[HOUSEKEEPING]** Stale H3b/shim references corrected; missing shim-history entries added. |
| 2026-06-13 | `diag-d001-h4-spectrogram-reinstate` | H4: reinstates spectrogram-domain soft-SNR tile suppression as a stable baseline (shim 20260010) after two rejected PCM-SIC diagnostics. |
| 2026-06-13 | `diag-d001-h5-suppression-tuning` | **[DIAGNOSTIC, rejected]** H5: shifted soft-suppression SNR ramp window. 46.24% vs 56.99% gate; constants later reverted. |
| 2026-06-13 | `p10-decoder-ground-truth` | **[MEASUREMENT]** 69.2% recovery; gap deferred as accepted limitation. |
| 2026-06-14 | `fix-d004-local-noise-floor` | Fixes SNR bias up to −22 dB at high audio frequencies via per-signal local noise floor (shim 20260012); reverts rejected H5 constants. |
| 2026-06-14 | `p10-decoder-ground-truth` | **[MEASUREMENT]** 70.2% recovery, 7 false positives (down from 24). |
| 2026-06-14 | `settings-audio-output-device` | Audio output-device enumeration/selection; TX-audio-routing plumbing ahead of TX feature. |
| 2026-06-15 | `fix-qso-answerer-uat-defects` | Fixes silence-guard retry-timing miscount and un-prepopulated TX settings fields from the just-shipped QSO answerer. |
| 2026-06-15 | `ft8-qso-answerer-v1` | First TX capability: FT8 encode/GFSK TX pipeline, `IPttController`, automated QSO answerer FSM (auto-answer, 6-message exchange, retry, watchdog), ADIF 3.x log writer. |
| 2026-06-16 | `waterfall-audio-frequency-cursors` | Click-settable RX/TX/combined frequency cursors on the waterfall; "Hold TX Freq" mode. |
| 2026-06-24 | `tx-general-settings-page` | UI restructuring: TX fields moved to a dedicated "General" settings tab (no backend change). |
| 2026-06-25 | `gui-tx-panel` | Main-page TX control panel (Enable/Abort TX, partner status, message rows); `IQsoAnswerer`→`IQsoController` rename. |
| 2026-06-26 | `qso-caller` | `QsoCallerService` (originate-CQ role), `CallerState` machine, clickable-responder partner selection. |
| 2026-06-27 | `qso-log-dialog` | Modal QSO confirmation/enrichment dialog (Name, TX Power, Comments, Prop Mode) at last-TX. |
| 2026-07-02 | `decoder-settings-page` | Three native decoder gate parameters exposed as live-configurable settings (`ft8_set_decode_params`). |
| 2026-07-02 | `lan-remote-access` | LAN remote access: `LanBindPolicy`, `PassphraseAuthPolicy`, login page, Remote Access settings section. |
| 2026-07-04 | `f-002-callsign-structure-region-lookup` | ITU Article-19 structural-grammar callsign check; advisory prefix→country/continent region lookup. |
| 2026-07-04 | `rr-study-hashed-callsign-effectiveness` | R&R harness extended to score linked two-cycle "resolved" outcomes for Type-4 nonstandard-callsign messages (QA tooling). |
| 2026-07-05 | `adopt-canonical-version-source` | Canonical `VERSION` file as single version source; new CI gate G9 (version-bump enforcement on archive). |
| 2026-07-05 | `f-001-hashed-callsign-resolution` | Native decoder's callsign hash table made session-scoped (FIFO-bounded), so hashed nonstandard callsigns actually resolve. |
| 2026-07-05 | `f-003-ap-assist-nonstandard-callsigns` | AP-assisted decode extended to cover hashed nonstandard callsigns via `Ft8CallsignPacker`. |
| 2026-07-05 | `f-004-operator-visibility-improvements` | Shim ABI version display; armed-vs-transmitting TX button colours; Call CQ/Stop CQ toggle; modifier-gated waterfall click; Logs viewer. |
| 2026-07-06 | `f-005-hash-table-saturation-diagnostic` | Read-only getter exposing `g_hash_table_reject_count` for external confirmation of hash-table saturation (observability only). |
| 2026-07-06 | `g9-automate-release-tagging` | CI job auto-creates/pushes an annotated `v<VERSION>` git tag on every `main` push. |
| 2026-07-08 | `rr-study-s4-per-message-matching` | R&R S4 scenario matching fixed to score each injected message independently, removing a ceiling effect (QA harness only). |
| 2026-07-09 | `adif-qso-confirmation` | `qso-confirmation` capability: in-memory worked-before index from `ADIF.log`; Partner/Country/Region columns. |
| 2026-07-09 | `f-006-region-lookup-country-file-refresh` | Operator-triggered fetch/convert/install of the real country-files.com DXCC dataset; Region Data settings tab. |
| 2026-07-10 | `decode-panel-filtering` | Daemon-owned decode-table filter popups gating `QsoAnswererService`/`QsoCallerService` auto-engagement decisions. |
| 2026-07-11 | `cq-row-dblclick-to-answer` | CQ-row click-to-answer changed single→double-click to reduce accidental TX arming (frontend only). |
| 2026-07-11 | `decode-noise-suppression` | Persisted settings to suppress Unknown-region and R&R-Synthetic decodes from panel/worked-before/automation. |
| 2026-07-11 | `decode-status-control-merge` | Decode-state badge and start/stop button merged into a single `#decode-toggle` control (frontend only). |
| 2026-07-11 | `qso-confirmation-band-awareness` | Worked-before columns renamed and made band-aware tri-state; CQ-Zone/ITU-Zone dimensions added. |
| 2026-07-12 | `gridtracker-udp-reporting` | WSJT-X-protocol-compatible outbound/inbound UDP for GridTracker2/JTAlert interop; External Programs settings tab. |
| 2026-07-15 | `engage-window` | Removes late-start rejection guard so manual engagement fires immediately; window-boundary TX truncation added. |
| 2026-07-15 | `remote-daemon-restart` | `POST /api/v1/system/restart` self-re-exec endpoint (refused mid-transmission); Settings "Restart Daemon" action. |
| 2026-07-16 | `daemon-background-mode` | `--background` CLI flag: fully console-detached daemon spawn (Win32/POSIX), detached-status propagation. |
| 2026-07-16 | `fix-adif-partner-grid-capture` | Fixes `QsoCallerService` discarding the partner's parsed grid instead of writing `ADIF.log` `GRIDSQUARE`. |
| 2026-07-18 | `cat-tx-ptt` | Real transmitter keying: `IRadioConnection.SetPttAsync`, CAT/serial PTT controllers, watchdog failsafe — the v1.0 gate item. |
| 2026-07-18 | `engagement-target-validation` | TX-engagement gate rejecting callsigns that don't structurally conform to their matched region-table prefix. |
| 2026-07-18 | `fix-decode-filter-new-value-admission` | Fixes decode-filter allow-lists silently excluding new DXCC/continent/zone values; tracking moved browser→daemon. |
| 2026-07-18 | `fix-jump-in-rr73-adif-capture` | Fixes jump-in `SendRr73` completion path skipping the ADIF write; real `RstRcvd` parsed instead of hardcoded `+00`. |
| 2026-07-18 | `fix-version-bump-gate-timing` | CI gate G9b checks version bump at feature-merge time instead of only at archive-time. |
| 2026-07-18 | `qso-transcript-panel` | Chronological "QSO Transcript" section on the TX panel, sourced ahead of the decode filter so it's never hidden. |
| 2026-07-19 | `fix-external-reporting-clear-and-reply-filter` | Fixes `ExternalReportingService` sending a WSJT-X Clear datagram every cycle instead of only on shutdown; opt-out filter-bypass flag for inbound Reply. |
| 2026-07-19 | `fix-tx-report-real-snr` | Fixes all four TX-composition sites sending a fixed `+00`/`R+00` placeholder instead of the real measured SNR. |
| 2026-07-19 | `fix-tx-transcript-real-message` | Fixes TX panel/QSO Transcript still showing the stale `+00` template after real SNR shipped server-side. |
| 2026-07-21 | `fix-flaky-test-delay-synchronization` | Shared poll-until-condition test helper; ~150 fixed-`Task.Delay` sites migrated; advisory CI lint gate G10 against new fixed-delay tests. |

---

## CI quality gates (current)

- **G1** — `dotnet build` with zero warnings
- **G3** — Requirement traceability (every FR/NFR ID mapped to a test)
- **G5** — Dependency licence inventory (MIT / Apache-2.0 / BSD only)
- **G6** — Real off-air signal recovery: three committed 40 m band fixture WAVs decoded against WSJT-X answer keys on Windows x64, Linux x64, and macOS ARM64
- **G7** — Secrets scan (gitleaks over full commit history)
- **G8** — OpenSpec validation (`openspec validate --strict --all`)
- **G9 / G9a / G9b** — Canonical `VERSION`-bump enforcement, checked at feature-merge time and at archive-time; release tag auto-cut
- **G10** — Advisory lint against new fixed-delay (`Task.Delay`/`Thread.Sleep`) test code

(G2 performance and G4 UI-visibility are inert placeholders, awaiting the tests they will gate.)

See [`TECHNICAL_SPEC.md`](TECHNICAL_SPEC.md) for architecture and
[`REQUIREMENTS.md`](REQUIREMENTS.md) for the v0.x scope and versioning scheme.
