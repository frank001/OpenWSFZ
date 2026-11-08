# H3 (#259): offline decodability of a late transmission, WSJT-X on `sol`: RESULTS

**To:** Architect (cc Captain). **From:** QA. **Stamped:** 2026-10-24 ~10:40Z (`date -u`). Branch `qa/refset`.
**Spec:** `qa/rr-study/2026-10-23-1735-architect-to-qa-spec-late-start-time-alignment.md` section 4 H3, with Amendment 1 (A1.1, A1.4).
**This report is QA's. The rulings, the prediction scoring and the ledger are the Architect's.**
`git diff --stat -- src/ native/` for this arm: empty (tooling and data only). Aggregates only (HK-037): no message text and no call sign anywhere in this report or in the committed result files.

## 1. Result in one paragraph

**The arm is VALID (V1 to V4 all PASS) and both gates PASS.** G1: style O at 4.9 s, -8 dB decoded **0/5** (the DT analysis in the spec stands). G2: style A at 3.5 s, -8 dB decoded **5/5** (bar >= 4/5). Aligned transmissions (style A) decode in WSJT-X up to a start offset of **4.9 s** (5/5 at -8 dB, 4/5 at -16 dB) and **not at 6.5 s or later** (0/5 at both SNRs at 6.5, 8 and 10 s). So Option A makes a late start decodable for t up to about 5 s, not up to the 11.25 s cut-off. That limit is the one thing in this table the Architect did not predict; section 4 states it.

## 2. Run record (every pin, HK-022)

| Item | Value |
|---|---|
| Freeze commit (design, render, play, analysis, manifest, placement report) | `a86f8c19` on `qa/refset`, committed BEFORE playback |
| `manifest.json` SHA-256 | `fe5c55ef22ffbc585e89747a2dfbd1403575c6e44aa28ea002d823963afaa379` (the same file was copied to `sol`; its `sha256sum` there starts `fe5c55ef22ffbc58`) |
| Scripts (SHA-256 prefix, equal to the freeze) | `h3_analysis.py` `a7f56491…`, `h3_design.py` `3c8a2e9a…`, `h3_play.py` `596f6b3a…`, `h3_render.py` `b7588df4…` |
| Renders | 180 `.npy` cycle buffers (720,000 samples each, float32 after the harness's finalise step); all 180 hash-checked on `sol` against the render report: **0 mismatches** |
| Decoder | WSJT-X 2.7.0 at `~/wsjtx-2.7.0/bin/wsjtx --rig-name=rr` on `sol`, started with `linux/restart-wsjtx-rr.sh` (up, fresh save WAV 09:40:45Z). Profile `rr`: `NDepth=3` (Deep), `FT8AP=false`, read from the ini before the run. **The version string was not re-read from the binary** (the PRECHECK canary was not run: this arm does not use the battery). |
| Playback | 2026-10-24 09:42:15Z to 10:29Z, 9 continuous batches of 20 cycles (`run_scenario._MAX_BATCH_TRIALS`), harness `_wait_for_cycle` and `_select_device` imported from `~/rr-work-b2` (commit `b9a82a98`, read only), `sounddevice` shim to `aplay plughw:0,0`, ALSA loopback. No restart, no stall. One slot is skipped between batches (by design; the log records every boundary). |
| `--filter` | none (no test suite was run for this report; the decoder under test is WSJT-X, no OpenWSFZ binary took part) |
| Inputs hashed (scratch, outside git) | `ALL.TXT` `4b29bcde…`, `playback_log.csv` `8fa1382f…` (also committed under `results/`), `save-stamps.txt` `4d34f384…` (196 save WAVs from 09:40:45Z), `result.json` `e12510bd…` |
| Machine | `sol` idle apart from the run (load 0.7 before the start); no battery, no replay, no compile in parallel; the Windows station daemon ran 09:45 to 10:07Z on another machine |

## 3. Validity rows and gates (frozen `h3_analysis.py`, no flag, no filter)

| Row | Reading | |
|---|---|---|
| V1 placement (A1.1): every clean clip cross-correlated against the DT = 0 render | 18 distinct (style, t) clips; **max lag error 0.0 ms** (tolerance 2 ms); O at t sits at +(t-0.5) s, A at 0.0 s, M at +1.86 s; A and M exactly zero before t, 240-sample raised-cosine ramp, remainder identical to the source | PASS |
| V2 liveness: a save WAV for the stamp of every cycle | 180 of 180 | PASS |
| V3 control: style F, t = 0.62 s, -8 dB >= 4/5 (bar stated in the analysis: the lateness-edge P3 32/32 is a different chain and build, so it is a reason for the bar, not a number inherited) | **5/5** | PASS |
| V4 attribution: no boundary carries more than one matched decode | 0; unattributed planted-text decodes 0; other lines in the window 0 | PASS |
| **G1** O at 4.9 s, -8 dB decodes 0/5 | **0/5** | PASS |
| **G2** A at 3.5 s, -8 dB decodes >= 4/5 | **5/5** | PASS |

Chain offset (descriptive): the F clip at 0.62 s (label DT +0.12 s) was decoded at median DT -0.3 s, so **Delta_chain = -0.42 s** on `sol` (lateness-edge on the Windows chain: -0.3 s). A, placed at label DT 0, decodes at **-0.4**; M, at label +1.86, decodes at **+1.4**; F at 2.36 s (label +1.86) decodes at +1.4. Every style's decoded DT equals its label plus Delta_chain, which is the independent confirmation of V1.

## 4. The table (descriptive; matched decodes out of 5, median decoded DT in seconds)

F = the three styles are the same audio at t <= 2.36 s (R1: full clip), played once. Wilson 95 % for 5/5 is [0.57, 1.00], for 0/5 [0.00, 0.43], for 4/5 [0.38, 0.96]: **5 replicates per cell locate an edge to one grid step and no better.**

| t (s) | SNR | F (t <= 2.36) | O (old) | A (aligned) | M (minimal skip) |
|---|---|---|---|---|---|
| 0.62 | -8 | 5/5 (-0.3) | | | |
| 0.62 | -16 | 5/5 (-0.3) | | | |
| 1.5 | -8 | 5/5 (+0.6) | | | |
| 1.5 | -16 | 5/5 (+0.6) | | | |
| 2.36 | -8 | 5/5 (+1.4) | | | |
| 2.36 | -16 | 5/5 (+1.4) | | | |
| 3.5 | -8 | | 0/5 | **5/5 (-0.4)** | 5/5 (+1.4) |
| 3.5 | -16 | | 0/5 | **5/5 (-0.4)** | 5/5 (+1.4) |
| 4.9 | -8 | | **0/5** | **5/5 (-0.4)** | 5/5 (+1.4) |
| 4.9 | -16 | | 0/5 | 4/5 (-0.4) | 5/5 (+1.4) |
| 6.5 | -8 | | 0/5 | 0/5 | 4/5 (+1.4) |
| 6.5 | -16 | | 0/5 | 0/5 | 3/5 (+1.4) |
| 8.0 | -8 | | 0/5 | 0/5 | 1/5 (+1.4) |
| 8.0 | -16 | | 0/5 | 0/5 | 0/5 |
| 10.0 | -8 | | 0/5 | 0/5 | 0/5 |
| 10.0 | -16 | | 0/5 | 0/5 | 0/5 |

Fraction of the clip's energy that is transmitted (from the placement check): A 0.76 at 3.5 s, 0.65 at 4.9, 0.53 at 6.5, 0.41 at 8, 0.25 at 10; M 0.91, 0.80, 0.67, 0.55, 0.40; O 0.91, 0.80, 0.67, 0.55, 0.40 (O and M carry about the same amount of the clip, from different parts of it: O keeps the start and cuts the tail, M keeps the end, at a different DT).

## 5. Reading, with its limits

1. **Option A works where it was meant to:** an aligned clip started 3.5 s or 4.9 s into the slot is decoded at DT = label + Delta_chain, which today's tail-cut clip is not (O is 0/5 at every t above 2.36 s, as the DT analysis predicts: label DT 3.0 s and above is outside WSJT-X's +-2.48 s search).
2. **A has a cliff between 4.9 s and 6.5 s (inference, not tested between):** at t = 6.5 s A has skipped 6.0 s, which is 37.5 of the 79 symbols, and it decodes 0/5 at both SNRs; at 4.9 s it has skipped 4.4 s (27.5 symbols) and decodes 5/5 (-8 dB) and 4/5 (-16 dB). The grid has no point between, so the edge is located only as "between 4.9 and 6.5 s". The same limit is **WSJT-X's own**: its start-skip rule produces the same clip, so a WSJT-X operator who clicks later than about 5 to 6 s into a slot sends a message no other WSJT-X decodes either (*inference*, the transmit side of WSJT-X was not run here).
3. **Consequence for the 11.25 s cut-off:** between about 5.5 s and 11.25 s the daemon will key and transmit a partial clip that this table says is not decodable by WSJT-X at the SNRs tested. It is no worse than today (O is 0/5 everywhere above 2.36 s), and it costs the retry accounting one transmission (note N1 of the HK-039 review). Whether the cut-off should move nearer the decodability limit is the Architect's decision; QA does not propose it here.
4. **M (descriptive, no code) decodes more than A at t >= 6.5 s** (4/5 and 3/5 at 6.5 s, 1/5 at 8 s) **and equals A up to 4.9 s** (5/5 at -8 dB for both, 5/5 against 4/5 at -16 dB at 4.9 s). It keeps more of the clip (0.67 against 0.53 at 6.5 s) at DT +1.86 s, which is inside the +-2.48 s window with 0.6 s to spare. This is one WSJT-X build, one chain, 5 replicates; QA does not draw a conclusion, only states the table is what the spec said M would show.
5. **Limits:** synthetic AWGN, one message at one frequency (1500 Hz) per cycle, no fading, no drift, no other signals; one WSJT-X 2.7.0 install; the other station is assumed to run WSJT-X (JTDX and MSHV not measured); two SNRs only; the noise realisations are shared between O, A and M of one cell (paired), so the styles are compared on identical noise. The noise level is set from one untruncated reference render, so the SNR label does not change with how much of the clip a style removes.
6. **What this does not show:** whether a real partner replies (propagation decides that), and how often a real late click falls beyond 5 s. The only count on file is n = 1 first transmission since v0.59 (spec section 1).

## 6. The live acceptance on the station (H4), for the record

Build `f683dc87` (VERSION 0.62, `libft8.dll` `aaf6b03e…`, provenance clean) deployed 09:24:48Z to `_run-main`, daemon started 09:45:57Z after the Captain started GridTracker, stopped 10:07:20Z. **L-1 (QA sent the Reply datagram, 10:00:20.002Z = 5.002 s into the correct-phase slot, answering a live CQ decoded in the cycle before):** the daemon logged one Information line `late start at 5015 ms into the slot - skipping 4515 ms of the clip, loading 8124 ms`; PTT keyed 5.02 s into the slot and released 13.33 s into it (spec: about 13.1 to 13.4 s). **L-2:** the three retransmissions that followed (12:00:45, 12:01:15, 12:01:45 local) carried no late-start line and held PTT 12.82, 12.83 and 12.82 s (full 12.64 s clip plus latency). The partner did not answer (descriptive). QA aborted the QSO after the third retry with `POST /api/v1/tx/abort`; `autoAnswer` was already false and is unchanged. Times from `date -u` and the daemon's own log; no call or message text recorded here. **At t = 5.015 s this live case sits just beyond the last A cell that decoded in the offline table (4.9 s, 5/5 at -8 dB, 4/5 at -16 dB), i.e. at the edge of the cliff in section 5.2.**

## 7. Predictions (the Architect's table; the Architect scores at ruling time)

| # | Prediction | Reading |
|---|---|---|
| V1 | G1: O at 4.9 s, -8 dB decodes 0/5 | **0/5** |
| V2 | G2: A at 3.5 s, -8 dB decodes >= 4/5 | **5/5** |
| V3 | A at 4.9 s, -8 dB decodes >= 3/5 | **5/5** |
| V4 | M decodes more than A at 4.9 s, -8 dB | **equal, 5/5 and 5/5** (M is higher from 6.5 s on) |
| V5 | the fix stays inside R5's files | see the HK-039 review (diff touches the three source files, their tests, OpenSpec and the version/doc sync) |

## 8. Next

(1) The Architect rules on section 5.2 and 5.3 (is the 5 s to 11.25 s band acceptable as it is, or is a finer grid between 4.9 and 6.5 s wanted first: QA can run t = 5.5 and 6.0 s, 5 replicates, 2 SNRs, 20 cycles, about 5 minutes of `sol` time). (2) The Captain's merge go for PR on `fix/late-start-time-align` (CI green on `f683dc87`; `pre_merge_check.py` READY; HK-039 APPROVED). (3) The board line and the QA ledger count in the close entry.
