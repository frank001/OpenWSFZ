# SUB-FEAS first on-air session: flag ON, 8 workers, overnight, receive only

| Field | Value |
|---|---|
| Window | 2026-09-30 19:30:58Z to 2026-10-01 13:24:58Z (17.9 h; supervisor start to daemon stop 13:25:48Z); 40m, 7.074 MHz |
| Arm | a **SUB-FEAS arm**: `decoder.subtractionEnabled = true`, `subtractionMaxThreads = 8`, `osdNhardMax = 40`, `tx.autoAnswer = false`, cycle-audio archive mode `all`. Receive only; no Settings-page saves; nobody clicked the decode panel |
| Build | `feat/sub-feas-two-stage-publish` @`247ac391`, shim `20260056`. `libft8.dll` actual `ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c` = pinned (arm_config.json and the pre-arm pin are the same string) |
| Chain | one radio (FT-991A) feeding the daemon and live WSJT-X (FT991A instance) through Voicemeeter B1; WSJT-X was decoding throughout |
| Instruments | `qa/endurance/tools/subfeas_arm_sampler.py` (every 30 min, 36 samples), `subfeas_arm_summary.py` (daemon logs), `subfeas_contention.py` (this report's two contention measures), `endurance_anova_wsjtx.py` (Section 4) |
| Filters | no test suite was run for this report, so no `--filter` applies; every figure comes from the daemon logs, both `ALL.TXT` files and the sampler |
| Data | `qa/rr-study/results/2026-10-01-sub-feas-first-on-air-run/{summary.json,contention.json}`; raw run under `artefacts/20260930_1930_endurance_run` and `…-gathered` (gitignored). **Aggregates only (HK-037): no message text, callsign or text-derived hash was read into an output** |

> **Bottom line.** At 8 workers, live, with WSJT-X running on the same machine, **0 of 4 298 residual passes were abandoned** and none threw. The busiest cycles
> (29 or more signals fitted, 10 cycles) took at most 9.4 s against the ~11 s cutoff. Memory was flat (−0.94 MB/h). The flag, thread count, auto-answer and archive mode
> were as armed at every sample that could read them. **This is descriptive evidence toward §8.2 (live use). It is not a decode-rate claim.**

## 1. Headline: live abandon rate at 8 workers, by signals fitted

Source: the daemon's `Sub-feas residual pass:` lines (4 298 lines; 4 300 `Cycle` lines).

| Signals fitted | Passes | Abandoned | Contained exceptions | Pass `elapsedMs` p50 / p95 / max |
|---|---:|---:|---:|---|
| ≤25 | 4 202 | **0** | 0 | 4 943 / 6 357 / 7 005 |
| 26–28 | 86 | **0** | 0 | 7 595 / 8 951 / 9 418 |
| 29+ | 10 | **0** | 0 | 8 765 / 9 421 / 9 421 |
| all | 4 298 | **0** | 0 | 5 001 / 6 423 / 9 421 |

- Most signals fitted in any cycle: **32** (the pre-arm replay corpus topped out at 30).
- Time to batch 1 (the unchanged first pass, from the per-cycle line): p50 526 / p95 593 / max 651 ms.
- Residual decodes reported by the passes: 16 701 (mean 3.89 per pass; mean 17.6 signals fitted). `WRN`/`ERR`/`FTL` lines in the daemon log: **0**.
- **Against the pre-arm check** (161 busy E1 replay cycles, 8 workers): that check's slowest passes were 11.0 to 11.4 s at 27 to 30 signals. Live, the same signal counts took 7.6 to 9.4 s. The replay corpus is the busiest slice of three corpora, so it is the harder test; the live evening had only 96 cycles with 26 or more signals and 10 with 29 or more.
- **Limits.** The tail is thin: 96 cycles at 26+ signals, 10 at 29+, none above 32. The cycles that stress the deadline are rare on this band at this time of year, so a busier night (a contest weekend) could still abandon. 0 of 4 298 puts the abandon rate below about 0.07 % (rule of three, 95 %) at the overall level; there is no useful bound for the 29+ band from 10 cycles.
- **Two cycles have no residual line** (4 300 `Cycle` lines, 4 298 residual lines). Not investigated; likely the first and last cycle at the window edges.

## 2. Memory and stability

| Quantity | Value |
|---|---|
| Samples | 36 (30-minute interval, plus start and end) |
| Private bytes | start 371.6 MB, end 345.7 MB, max 426.7 MB, range of samples 339 to 427 MB |
| Growth after the first 30 min (least squares) | **−0.94 MB/h** (private); 45.7 % of consecutive steps increasing (a monotonic leak would sit near 100 %) |
| Flags (`subtractionEnabled`, `subtractionMaxThreads`, `osdNhardMax`, `autoAnswer`, archive mode) | as armed at every sample that could read the daemon; the last real sample (13:02Z) `flags_ok`; **no `FLAG_MISMATCH`, no `DAEMON_PID_CHANGED`** |
| Sampler events | `SAMPLER_START` 19:31:40Z, then at 13:28:45–48Z (after the supervisor stopped the daemon at 13:25:48Z) `NO_DAEMON_ON_PORT`, `CONFIG_READ_FAILED`, `SAMPLER_END` (TTL). **Expected, not a fault** |
| Supervisor | 0 restarts; teardown clean; HK-019 orphan check found no supervisor, sampler, daemon or Replay81 process; gatherer exit 0 |
| Arm pre-flight | `all_pass` true. One check read `wsjtx_ini_dial_freq_matches_daemon: false` at arm time; **not re-investigated**. Both logs cover the same 4 296 cycles and the matched-pair frequency means agree (1 482.4 vs 1 482.3 Hz), so the two decoders heard the same 40m audio |

§7 stability (memory checked in the first on-air run) is **met on this record**: a flat trend over 17.9 h, 4 298 passes, 0 abandons, 0 contained exceptions, 0 warnings.

## 3. Contention with WSJT-X (the two measures requested)

Both decoders share one CPU (8 physical cores, 16 logical). Per-cycle counts come from the stamp prefix of each `ALL.TXT`; each residual pass is attached to the cycle it belongs to (4 296 cycles in the window, 4 296 passes keyed, 0 key collisions).

**Measure A: cycles in which WSJT-X reported 0 decodes while OpenWSFZ reported at least 10.**
**0 cycles.** WSJT-X had at least one decode in all 4 296 cycles, and so did OpenWSFZ (reverse case also 0). Cycles with 10+ decodes: OpenWSFZ 4 270, WSJT-X 4 293. *Blind spot (HK-026):* this reads decodes from the log, so a cycle in which WSJT-X ran slowly but still finished would not show; it detects only a WSJT-X cycle that produced nothing.

**Measure B: WSJT-X per-cycle decode count against the residual pass `elapsedMs`.**

| Pair | Spearman ρ (4 296 cycles) |
|---|---:|
| `elapsedMs` vs WSJT-X decodes | 0.80 |
| `elapsedMs` vs OpenWSFZ decodes | 0.86 |
| `elapsedMs` vs signals fitted | 0.91 |
| WSJT-X decodes vs signals fitted | 0.79 |

The strong correlation is **band activity, not proof of contention**: a busy cycle has more signals for OpenWSFZ to fit and more for WSJT-X to decode, so both rise together (WSJT-X decodes vs signals fitted is 0.79). To remove that confounder the cycles are split by signals fitted, then by tercile of WSJT-X decodes:

| Signals fitted | Cycles | ρ (`elapsedMs` vs WSJT-X n) | Median `elapsedMs` (ms), low / mid / high WSJT-X tercile |
|---|---:|---:|---|
| ≤15 | 1 328 | 0.81 | 3 084 / 3 233 / 3 576 |
| 16–20 | 1 877 | 0.48 | 4 633 / 5 927 / 6 061 |
| 21–25 | 995 | 0.25 | 6 125 / 6 197 / 6 227 |
| 26+ | 96 | 0.22 | 7 609 / 7 586 / 8 525 |

Reading: the dependence on WSJT-X's count **shrinks as the fitted-signal count rises**, and at 21 to 25 signals it is about 100 ms (≈2 %) across the terciles. That is what band activity would do (the signal count is a coarse control inside each band) and not what a heavy CPU rivalry would do. In the 26+ band the high tercile is 0.9 s slower (n = 27 against 42; one night, not tested for significance). **I cannot separate load from activity on this data, and the data gives no sign that WSJT-X lengthens the pass materially.** A direct test would be a pass-time comparison on the same audio with WSJT-X idle and busy (the 12-worker quiet check is the nearest such control).
Also visible: the per-hour median pass time falls from ≈6.0 s at night to ≈3.1 s at 10–13Z (a quiet band), so time of night is a large driver of the pass time.

## 3a. Spectrum scan (standing routine, run after the report was first written)

`spectrum_scan.py` over all 4 299 archived cycle WAVs (`spectrum_scan.json`, gathered dir), then `spectrum_scan_report.py` with the 2026-09-25 scan as control (the only earlier scans are 09-23 and 09-25, both direct-CODEC; **no same-chain (B1) control exists**, so the control is cross-chain).

| Check | This run | Control 09-25 |
|---|---|---|
| Files readable / format | 4 299 of 4 299; 12 kHz, 180 000 frames in every file | 2 884 |
| Clipping / silent / hot files | 0 / 0 / 0 | 1 clipping / 0 / n.r. |
| Level (median dBFS, MAD) | −28.2, 0.72 (range −35.0 to −22.5) | −28.2 |
| Hum band 2nd harmonic over floor (median) | 20.9 dB | 21.9 dB (delta −0.99, "consistent with control") |
| Hum band fundamental over floor (median) | 9.4 dB | 8.7 dB |
| Narrowband spur bins | top bin 1 290 Hz in 3.8 % of files, below the 5 % materiality bar: ordinary traffic, not an anomaly | n.r. |

**No anomaly found.** The hum-band figure (flagged in 58 % of files by the 20 dB bar) is the same as the earlier runs'. The dossier is `FINAL_REPORT_dossier.html` in the gathered dir (HTML; unpublished). The standard `FINAL_REPORT.md/.html` of the earlier runs was not composed.

## 4. Section 4 (HK-036): the historical series, read

Section 4 of `artefacts/20260930_1930_endurance_run-gathered/anova_report.md` was **read**. It holds four standardised runs (the table of earlier runs is limited to the standardised sidecars, which begin 2026-09-22). All are 40m, nhard 40, live WSJT-X reference, G = 1.0000 (ROW 1 PASS):

| Date | Hours | Build | Shim | Chain | Matched pairs | Matched % of ref | OWS-only % | SNR gap (dB) | DT gap (s) |
|---|---:|---|---:|---|---:|---:|---:|---:|---:|
| 2026-09-22 | 12.0 | `decoding_improvement` `84cac119` | 20260054 | B1 | 55 010 | 59.8 | 0.8 | −2.824 | +0.6548 |
| 2026-09-23 | 24.0 | `decoding_improvement` `84cac119` | 20260054 | direct CODEC | 97 279 | 61.1 | 0.7 | −3.225 | +0.6484 |
| 2026-09-25 | 12.0 | `decoding_improvement` `51e40b55` | 20260054 | direct CODEC | 46 917 | 60.9 | 0.6 | −2.638 | +0.6511 |
| **2026-09-30 (this run)** | 17.9 | two-stage `247ac391` | 20260056 | B1 | 94 307 | **72.8** | **1.1** | **−1.546** | **+0.6611** |

Applying the table's own rules: the only same-chain row is 2026-09-22 (B1); the other two are direct-CODEC and **not** comparable on the chain. **This run is a flag-ON arm and must never be pooled with the three flag-OFF rows above** (the row's chain cell says so; the sidecar is committed with that cell). Shim, DLL (`ee00d118…` vs `38a21f84…`) and flag all differ from every earlier row.

**Did anything change? Yes, on the face of the table:** matched-% of WSJT-X moved from 59.8–61.1 (three runs) to 72.8; OWS-only rose from 0.6–0.8 % to 1.1 %; the SNR gap narrowed from −2.6…−3.2 dB to −1.55 dB; the DT gap is unchanged (+0.648…+0.661 s).

**What this does and does not say.** Matched-% moved by about 12 pp against a spread of about 1.3 pp across three flag-OFF runs, so it is large against the observed night-to-night spread. But:
- it is a different night, a different build (shim `20260056`, not `20260054`) and a different flag state **at once**; a concurrent flag-OFF control does not exist;
- the SNR-gap noise floor between nights is known to reach about ±0.35 dB (the 2026-09-26 ruling), so only the size of this move, not its existence, argues against noise;
- `ALL.TXT` is post-plausibility and post-dedup, and the residual decodes were published as a second batch, so the "OWS-only 1.1 %" is not a false-positive rate.

**No decode-rate claim is made.** The controlled answer is the already-planned offline replay of this run's archived audio (4 299 cycles) with the flag OFF and ON against WSJT-X; the direction here is consistent with the offline net +8.89 pp [8.01, 9.75] (cite the NET figure only) but is not a measurement of it.

## 5. Findings and decisions for the Architect and Captain

1. **§8.2 (live use):** at 8 workers the live abandon rate was 0 over 17.9 h and 4 298 passes, with WSJT-X running. By the pre-registered shape (T′ is a Stage B bar and is **not** this arm's bar), nothing here refutes 8 workers; the 29+ band is only 10 cycles.
2. **Default thread count:** this record supports 8 on this CPU. It does not test the 12-worker alternative or a CPU of a different size; the decision still waits for the 12-worker quiet check and the per-fit completion log.
3. **Does the second batch help?** Residual decodes reached the panel and `ALL.TXT`; the answerer was not engaged (auto-answer off; no panel clicks). Nothing in this run exercises the "batch 2 does not reach the answerer" path, so that rule remains covered only by the Developer's tests and the S1–S3 acceptance.
4. **Summariser fix:** `subfeas_arm_summary.py` matched only `True`/`False` and so read 0 lines from the daemon's lowercase `true`/`false`. Fixed (case-insensitive, `.lower()` comparison); re-run counts 4 298 lines, equal to a direct count. No result was read from the wrong version.
5. **Next (per the Architect's plan):** the quiet-machine 12-worker check; the per-fit completion log; S2b; the offline flag-OFF/ON replay of this run's audio; then Stage B.

## 6. Limits (HK-026)

One night, one band (40m), one radio, one machine, flag ON only, no concurrent flag-OFF control; the corpus is the same single-station chain as every earlier endurance run. The contention measures are correlational. Pass times are the daemon's own `elapsedMs`; the cutoff is inferred from the design (about 11 s), not logged per pass. WSJT-X and the daemon share a CPU with the operator's browser and the supervisor tooling. Counts and stamps only; no message text, callsigns or text-derived hashes appear in this report or its data files (scanned: the result files hold numbers and field names only).
