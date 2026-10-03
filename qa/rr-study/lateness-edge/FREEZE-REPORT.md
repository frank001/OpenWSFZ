# LATENESS / EDGE test: FREEZE report (before any playback)

- **From:** Engineer (owner of the edge test)  **To:** QA, Architect, Captain  **Date:** 2026-10-02 evening (HK-017)
- **Branch:** `eng/lateness-edge` (local, off `origin/main` `e5feb132`; never pushed by me). The freeze commit's own SHA is given in the message that announces it (a commit cannot contain its own SHA).
- **Spec:** `qa/rr-study/2026-10-02-0720-architect-to-qa-spec-lateness-tolerance.md` with Amendments 1 to 3 (Amendment 3 is on `arch/194-rr-improvements` `ccad519d`). `git diff --stat -- src/ native/` is empty.
- **Nothing has been played. No decoder, daemon, WSJT-X or station was used.** Everything below is CPU only.

## 1. What is frozen (SHA-256 over LF-normalised bytes = the git blobs; verify with `git show <commit>:<path> | sha256sum`)

| artefact | SHA-256 |
|---|---|
| `qa/rr-study/lateness-edge/manifest.json` (204 cycles, 2 432 signals, seed 20261002) | `49db08690850c92cf3e7383ba7ab3dc2252cfac39f7573717b7ec07dd1df75e2` |
| `renders_index.json` (SHA-256 of each of the 152 rendered cycle buffers) | `061cfa9f4ecfc62040dd100383665a1a3d29686d75282e05e4746ab0e389aec9` |
| `p1p2_pre_playback_report.json` | `83c55e612ff74c205b8a724035653da13419a31292b9cc7e17a3a7ff8cf11dc5` |
| `design.py` | `efeacdfc8cbe3e24719ef9c2cbfbe4e85311aa378863b74cf520f8e9f3a41b62` |
| `render.py` | `5f5b521bc43d97d84ffe7fe96e520326ac7dbffa450ea791ff770ff954b6e3b5` |
| `analysis.py` (P3 to P7, edges, DT form, Q2 DT fraction) | `72e2b3ee39921145e6a2d84e86eb120c960fcfcda79abd26f16400a1435a6a63` |
| `play_session.py` | `f757910b1c23de3310ff6d1390b260cdd095c3c2144dabe2479393074f2dbf8b` |
| `qa/rr-study/tests/test_lateness_edge.py` (24 tests, all pass) | `ae8bd47019fd377420f2a6d9db80474ff0f9a36a50aeb5763cbdaa0de29e4ce8` |

The renders themselves (≈ 560 MB of float32 at 48 kHz) are **not committed**; they live in `D:\Projects\claude\_qa-scratch\lateness-edge\renders\` and are reproducible bit-for-bit (two cycles re-rendered from scratch matched `renders_index.json`). The playback driver must check them against that index before playing.

## 2. Pre-playback rows

- **P1 PASS.** 2 432 of 2 432 signals: the cross-correlation lag of the clean, untruncated render at `L` against its own `L` = 0 render equals the label; maximum error 5.6e-16 ms (limit 2 ms). **Stated as the HK-026 caveat it is:** both renders come from the same `modulate`, so P1 can only catch a bug in the placement arithmetic, not a wrong convention. The convention is checked by P3/P7 on air.
- **P2 PASS.** 1 088 LATE signals (those with `L` > 1.86 s: `L` = 2.00 to 6.00, 17 grid points × 2 SNR × 32) are zero after the slot end and sample-identical to their untruncated render before it; the 512 LATE signals with `L` ≤ 1.86 are untouched (energy kept 1.0). Every EARLY signal lies wholly inside its 18 s buffer (energy kept 1.0 for all 832).
- **Sigma:** one fixed sigma = **2.0101724620706807**, from an untruncated unit render at `L` = 0 in a 15 s slot through `channel.noise_sigma_for_snr`; asserted identical in all 152 rendered (planted) cycles; the 52 idle cycles have no buffer.
- **Convention confirmation requested by the Architect (Amendment 3 (ii)):** the 2 500 Hz-reference sigma is used with the **same bandlimited (4 700 Hz) noise** that is played. Checked by measurement, not by argument: a unit signal scaled to −16 / −8 dB, noise from `add_awgn(sigma, noise_cutoff_hz = 4 700)`, in-band SNR measured with `channel.measure_inband_snr_db` (Welch, 0 to 2 500 Hz): −16.00, −15.97, −15.99 and −8.00, −7.97, −7.99 dB (three seeds each). A test pins this (`test_sigma_gives_the_labelled_inband_snr_with_the_bandlimited_convention`, tolerance ±0.7 dB).
- **Noise convention and the deviation from "no new mixing code":** `channel.mix_to_shared_floor` (`synth/channel.py:196`) sets sigma from the first signal's whole-array power; with truncated or shifted first signals that moves every cell's SNR label with `L`. `render.py` therefore sums the unit signals scaled by 10^(snr/20) (the primitives of `channel.py:189-191`) and calls `channel.add_awgn` (`:123`) with the one fixed sigma. An SNR label means the SNR the full, untruncated signal would have; a cut reply is sent at full power. Accepted by the Architect (Amendment 3).

## 3. Layout, in one line

Each early buffer is armed 3.0 s before its boundary, so the slot **before** it must be free: the idle cycle precedes each planted early cycle (idle, planted ×52), an equivalent of the spec's "followed by one idle cycle" accepted by the Architect on 2026-10-02 evening. Total 204 cycles: LATE 100 planted; EARLY 52 idle + 52 planted.

## 4. Precision paragraph (adds one sentence the Architect asked for)

32 signals per cell give a Wilson 95 % half-width of about ±16 pp at r = 0.5; the edge is located to one grid step (0.25 s) where the fall is steep, and no better; signals in one cycle share a noise realisation and decoder state. **Cycles of one composition are replicates, so the effective number of independent neighbourhoods per cell is 8, not 32:** the late block has 25 distinct 16-cell compositions, each used in exactly 4 cycles with different slot assignments (the early block 13 × 4), so each cell meets 8 different neighbour sets, 4 cycles each (QA's independent audit of the manifest, 22 of 22 rows). The cycle order is shuffled (correlation of cycle index with mean `L`: 0.01 late, −0.07 early). The report draws no conclusion from a one-step difference between decoders.

## 5. Post-playback predicates and outputs, as code (`analysis.py`)

P3, P3b, P4, P5, P6 as in the spec (constants named: 0.90, 3 signals, ±3 dB around −8, 152 planted cycles, ±10 Hz). **P7 (built in, descriptive, no bar):** per decoder, the median reported DT and its IQR at `L` = 0.00, −8 dB, from the LATE block and from the EARLY block's `L` = 0 cell; `Δ_chain` = the median WSJT-X DT of the LATE `L` = 0 cell. Every edge is also reported as `DT_edge = L_edge + Δ_chain`, labelled "WSJT-X DT convention, via this chain's offset"; `L` stays the primary grid. `q2_fraction(T2, k, DT_edge)` is the DT form of Q2 (the on-air data extraction for Q2 is a separate descriptive step on existing data and is not part of this freeze). A validity FAIL names the row and no edge is reported. Message text is read only inside `parse_all_txt`, which keeps a line iff its text is exactly one of the 2 432 planted synthetic texts and only counts the rest (HK-037).

**Playback mechanics (`play_session.py`), for the Captain's slot:** the harness's own, imported: `_select_device`, `_wait_for_cycle` (arms `_CYCLE_PREWARM_S` = 0.5 s before `boundary − early_by_s`, then `sd.play` at once), `sd.play` + `sd.wait`. LATE: continuous batches of ≤ 20 cycles (`_MAX_BATCH_TRIALS`; a stopped stream would clip the cut end of a late signal), so a slot may be skipped between batches (the log records every cycle's actual boundary). EARLY: each planted buffer alone, `early_by_s` = 3.0. **Note for P7:** because the harness starts `sd.play` 0.5 s *before* the boundary, most of the ≈ 0.33 s chain offset seen in the 09-23 audio is probably that prewarm less the device latency (≈ 0.16 s); that is an inference, and P7 is what measures it. Dry run (no audio device): schedule and log check out (204 cycles, early pairs 30 s apart, LATE batches 5 × 20). Total ≈ 51 min plus the 120 s warm-up lead.

## 6. Build, config and measurement discipline for the slot (QA to do; nothing here is a build)

- **Build:** current `main` (now `e5feb132`, `VERSION` 0.54); QA records the SHA and the `libft8.dll` SHA-256 (HK-022: "FT8_SHIM_VERSION identifies nothing, pin the DLL SHA-256") and the installed WSJT-X version. **Binary pin pair:** pinned = the DLL SHA-256 of the build under test, actual = the same hash read from the running process's DLL; to be quoted in the measurement report.
- **Flag:** `main` ships `decoder.subtractionEnabled` = true (`DecoderConfig.cs:139`). Set it to false by `POST /api/v1/config` (an OVERLAY on `main`, FR-074, HK-035) **after** the daemon has started once, then `GET /api/v1/config` and assert `decoder.subtractionEnabled == false` **and** `decoder.subtractionOnMigrationApplied == true` (`JsonConfigStore.cs:301-318`: otherwise a restart migrates a persisted `false` back to `true`). Read back again after the run.
- **`--filter`:** none applies before playback (no decoder ran). The test run for this freeze is `python -m pytest tests/test_lateness_edge.py -q` from `qa/rr-study/`: 24 passed, no filter.
- **Station:** one shared resource; the slot is booked through QA; RX only, radio out of the chain; no other CPU-heavy work during playback.

## 7. Open points (none blocks the freeze)

Q2's on-air extraction (the daemon's per-cycle lines and their FILE:LINE) is not done. Predictions LT1 to LT5 are the Architect's and are scored at ruling time.
