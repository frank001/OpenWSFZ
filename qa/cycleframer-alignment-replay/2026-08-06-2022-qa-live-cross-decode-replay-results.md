# Live cross-decode replay — WSJT-X vs OpenWSFZ, results

**Author:** QA, 2026-08-06 (20:22 UTC, `date -u`, per HK-017). Repo `main` at `f6c5b46`.
**Requested by:** the Captain, 2026-08-06 — a live, VB-CABLE-based replay of matched WAV
pairs from `20260803_live_run_1713`, both decoders decoding the same audio simultaneously,
in real time, to compare SNR/DT/freq/decode counts without touching offline `jt9` (barred as
a reference decoder, `three-decoder-antenna-split-run-2026-07-31-todo.md`).
**Script:** `qa/cycleframer-alignment-replay/2026-08-06-live-cross-decode-replay/run_cross_decode_replay.py`.
**First attempt aborted** (WSJT-X's Monitor was enabled late into pass 1; killed cleanly,
nothing committed from that run). This note covers the clean re-run.

---

## 1. Method

20 consecutive matched-filename cycles, the busiest 5-minute window in the corpus by
original combined decode count: `260804_085845` → `260804_090330` (owsfz=466, wsjtx=328
originally). Two passes, same 20 cycles both times:

- **Pass 1**: WSJT-X's own originally-captured WAVs replayed.
- **Pass 2**: OpenWSFZ's own originally-captured WAVs replayed.

Both passes played out to `CABLE Input (VB-Audio Virtual Cable)`, 15-second slot-aligned,
peak-normalised to 0.9. WSJT-X (launched `--rig-name=FT991A`, own AppData directory,
`Deep`/`AP off`, confirmed unchanged since the 3rd) and a fresh OpenWSFZ daemon (current
`main`, no `src/` changes since the last publish) both listened on `CABLE Output`
simultaneously throughout. Matching: exact `(ts, normalised message)`, identical convention
to every other script in this directory.

## 2. Decode-count matrix

| | OpenWSFZ decoder | WSJT-X decoder |
|---|---:|---:|
| **WSJT-X-source WAVs** (pass 1) | 461 | 752 |
| **OpenWSFZ-source WAVs** (pass 2) | 451 | 747 |

Zero duplicate `(ts, message)` rows on either side, either pass — checked explicitly, not
assumed. Exactly 20 distinct cycles present on both sides, both passes.

**Source effect is small**: OpenWSFZ's own count barely moves between the two audio sources
(461 vs 451, −2.2%); WSJT-X's barely moves either (752 vs 747, −0.7%). Corroborates the
WAV-content-comparison note's finding that in-band audio is nearly identical between the two
capture chains — whichever WAV set is replayed, both decoders see essentially the same
signal.

## 3. Matched-pair SNR / DT / frequency

| | Pass 1 (wsjtx-source) | Pass 2 (owsfz-source) |
|---|---:|---:|
| matched pairs | 447 | 443 |
| SNR delta (ours − wsjtx), dB | mean −2.31, median −2.00, sd 4.28 | mean −2.07, median −2.00, sd 4.46 |
| DT delta (ours − wsjtx), s | mean +0.633, median +0.600, sd **0.047** | mean +0.629, median +0.600, sd **0.047** |
| freq delta (ours − wsjtx), Hz | mean +0.1, median 0.0, sd 1.0 | mean +0.0, median 0.0, sd 1.0 |

- **Frequency: no difference worth the name.** Sub-1-Hz spread — rules out a
  frequency-calibration or passband-alignment explanation for anything else measured here.
- **SNR: OpenWSFZ reads ~2–2.3 dB low, consistently.** Direction and rough size match the
  already-tracked S7 gain-error calibration issue (slope 0.6865, cited in the Arm R.D spec)
  — a clean replication, not new news.
- **DT: a tight, near-noiseless +0.63 s systematic offset, both passes** (stdev 0.047 s on a
  0.63 s mean — a ~7% coefficient of variation, about as clean a systematic bias as this kind
  of live measurement produces). **Caveat before citing this elsewhere:** this number is
  measured on tonight's *replay* pipeline (WAV → Python playback → VB-CABLE analogue loop →
  both apps' capture), which has its own buffering/latency character. The 2026-07-30 note
  recorded a DT-sign split by *original* capture hardware (SDR Uno/Voicemeeter instance:
  OpenWSFZ trails by +0.65 to +0.67 s; physical-radio/USB-CODEC instance: OpenWSFZ *leads* by
  −0.27 to −0.64 s). Tonight's source corpus is the USB-CODEC-hardware family, which that note
  would predict a *negative* delta for — instead this measures **+0.63 s, matching the
  SDR-Uno-family sign, not the hardware this audio was originally captured on.** Read as: DT
  offset likely tracks the *measurement pipeline* (live antenna vs. cable replay) at least as
  much as the original capture hardware, not hardware alone as previously framed. Flagging the
  discrepancy rather than resolving it — worth the Architect's attention if DT ever becomes
  load-bearing for anything.

## 4. The standout result — not what this experiment set out to measure

**WSJT-X decoded 2.2–2.3× more messages tonight, replaying its own originally-captured audio,
than it decoded live on 2026-08-03/04 for those exact same 20 cycles** (752 tonight vs. 328
in the original archived `wsjt-x/ALL.TXT` for this window). OpenWSFZ's replay count closely
reproduced its own original (461 vs. 466, −1%). This is not a couple of outlier cycles:

| cycle | wsjtx original | wsjtx tonight |
|---|---:|---:|
| 085845 | 16 | 39 |
| 085900 | 16 | 40 |
| 085915 | 18 | 43 |
| ... | ... | ... |
| 090330 | 18 | (all 20 cycles run 31-47 tonight vs. 12-20 originally — uniform, not clustered) |

Every one of the 20 cycles is elevated tonight, roughly 2× across the board — this reads as
systematic, not a glitch in one or two cycles. **No root cause established.** Leading
candidate, unverified: the original 08-03/04 live session may have had WSJT-X competing for
CPU with something else running at the time (the corpus's own `contents.md` doesn't record
what else was running), silently truncating how many Deep-mode iterative-subtraction passes
WSJT-X completed per cycle before the next cycle's audio arrived — tonight's replay had no
such contention. This is a hypothesis, not a finding; verifying it would need the original
session's system/process logs, which QA has not gone looking for as part of this note.

**Why this matters beyond tonight:** if real, this means WSJT-X's *live* decode yield during
the original corpus may itself have been suppressed by something other than genuine decoding
difficulty — which would sit underneath every "OpenWSFZ misses N% of WSJT-X's decodes"
figure computed against that corpus's live WSJT-X `ALL.TXT`, including the Architect's
42.2%/61.8% R.D scouting figures and Measurement D's own reference counts. **Not claiming
those figures are wrong** — this is one 5-minute window, one hypothesis, not re-run — but it
is a large enough and clean enough effect that it should not sit unflagged.

## 5. What this does and does not establish

- **Confirms the decoder-algorithm gap is real, large, and reproducible on a fully live
  instrument** (no `jt9`): WSJT-X out-decodes OpenWSFZ by ~63–66% on identical replayed audio,
  both directions. Consistent with, though not identical in size to, prior figures — expected,
  different corpus slice, different instrument.
- **Rules out frequency/passband as a contributor** to anything measured tonight — the two
  decoders agree on frequency to within ~1 Hz.
- **Does not resolve the 29.9%-agreement TODO directly**, though this window's matched-pair
  rate against the union (447/(461+752−447) = 58.4%) is notably higher than the corpus-wide
  29.9% — plausibly just this window, not investigated further here.
- **Opens a new, unverified but large question** (§4) that looks more consequential than the
  experiment's original SNR/DT/freq/decode-count remit — flagged for the Captain/Architect to
  weigh, not chased further by QA without direction, per this project's standing cost
  discipline around marginal-yield chases.

## 6. Cross-references

- `qa/cycleframer-alignment-replay/2026-08-06-1920-qa-wav-content-comparison-1713.md`,
  `2026-08-06-1933-qa-decode-config-comparison-wsjtx-vs-openwsfz.md` — the two prior pieces
  of this evening's investigation (audio content, decoder configuration) that this experiment
  follows on from.
- `2026-07-30-2221-qa-to-architect-capture-chain-and-cross-band-findings.md` §2 — the DT-sign
  by-hardware finding §3 complicates.
- `2026-08-05-1459-architect-to-qa-spec-reciprocal-density-asymmetry.md` — the 42.2%/61.8%
  scouting figures and the S7 gain-error citation.
- `qa/cycleframer-alignment-replay/2026-08-06-live-cross-decode-replay/summary.json`,
  `_work/daemon_run/pass_windows.json` — raw output (git-ignored `_work/`, summary.json
  committed, NFR-021: aggregate numbers only, no message text or callsigns).

---

*Per HK-011 nothing here touches `src/`. Per HK-014/HK-010 committed locally, no push, no
merge implied. Per HK-021, §4's hypothesis is stated as unverified and not chased further
without direction.*
