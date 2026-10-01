# OpenWSFZ R&R Study Report — SUB-FEAS native subtraction, flag OFF vs flag ON

| Field | Value |
|---|---|
| Run date | 2026-09-29 (flag OFF 15:37:21Z–17:26:20Z; flag ON 17:31:25Z–19:20:35Z) |
| OpenWSFZ build | `feat/sub-feas-native-subtraction` @ `0d6b19377febf2a2aa5c2477742d543e27625407` (code identical to `91444300`, the reviewed fix; `0d6b1937` adds `tasks.md` only), built in scratch worktree `C:\Users\Frank\w-sf-rr-build`, `build_dirty=false` |
| Shim | `20260055` (read back from the running daemon's `/api/v1/status` on both runs) |
| `libft8.dll` SHA-256 | actual `5a6a4dc04a2cf6fbd987c12ce7635a968f4c9b69f73cacebe422af62827e38c5` — identical in the source tree and in the published output. **Pinned:** no independent pin exists. The only other place that value appears on disk is `libft8.version.txt`, the same file's own label, and the Developer's report of it; neither is an independent manifest (HK-022). |
| Config | `nhard=40`, `kMinScorePass2=10`, `osdCorrThreshold=0.10`; the two configs differ **only** in `decoder.subtractionEnabled` (false / true), their output directories, and one display-only block (see Limitations 3) |
| WSJT-X version | WSJT-X 2.7.0, profile `FT991A`, input `Voicemeeter Out B1` |
| Scenario list (exact) | `--scenarios S1,S1b,S2,S3,S4,S5,S7,S8 --skip-warmup --device "Voicemeeter AUX Input"`. No `--filter`; the whole battery ran both times. |
| Verdicts | Flag OFF: **PASS**. Flag ON: **PASS**. No gate fired on either. |

> 🔴 **SHA field corrected (HK-022) — third occurrence of the same defect.** `analyse.py` printed
> `62e8e74a…` (the QA *tooling* worktree's own `git rev-parse HEAD`, branch `qa/live-gap-map`), and
> wrote that SHA into `trend.csv`. That is **not** the code under measurement. The daemon in both
> batteries was built from `feat/sub-feas-native-subtraction` @ `0d6b1937`, recorded in
> `results/_supervisor_runs/20260929_1537_run/arm_config.json` and `…_1731_run/arm_config.json`
> (`build.commit`). Each battery used exactly one daemon start and one stop
> (`supervisor.log`: OFF 15:37:17Z start / 17:26:20Z stop; ON 17:31:22Z start / 19:20:35Z stop). The
> standing recommendation stands, still unactioned: `analyse.py` should read `arm_config.json`'s
> recorded build provenance instead of the analysis-time repo's HEAD.

**The standard per-run report directories** (analyser `report.md` with the corrected SHA header,
`report.html`, the seven PNG panels, `truth.csv`, `wsjt-version.txt`, same layout as
`2026-09-23-5f17b43/`) are `../2026-09-29-0d6b193-OFF/` and `../2026-09-29-0d6b193-ON/`. This file is
the comparative cover report over the pair. The analyser's unedited output (SHA field as the
analyser wrote it) also sits beside this file: `analyser-report-OFF.md`, `analyser-report-ON.md`. The raw per-run results (per-scenario matched CSVs, `truth.csv`, both
`ALL.TXT` copies, captured audio, supervisor logs) were preserved, with file counts and byte sizes
verified against the originals, in the gitignored
`artefacts/rr_2026-09-29_subfeas_off_on/` of the QA worktree (`…-OFF`, `…-ON`, the two
`-captured-audio` directories, `_supervisor_runs/`, the launcher logs). The scratch build and
tooling worktrees they were produced in have since been removed (HK-019). They were **not** copied
into this tracked tree (NFR-021: redact-then-rescan before any promotion).

## Section 1 — Study hypothesis

**Purpose of this run.** The Captain asked for an R&R S1–S8 sweep on the newest build with the SUB-FEAS
subtraction flag enabled. Because a flag-ON-only sweep cannot be attributed to subtraction (the
previous full sweep, `2026-09-23-5f17b43`, was a different build lineage: `decoding_improvement`,
shim `20260054`, versus this branch's `main` lineage, shim `20260055`), the Captain approved a
**paired design**: two full batteries on the *identical* DLL and config, differing only in
`subtractionEnabled`. Every seed and truth row is identical between the two runs (S7: 430 message
keys, all common).

**Null hypotheses in scope.**
- **H0(no harm):** with the flag ON, no gate degrades, no phantom decodes appear on signal-free
  slots, and the daemon never crashes or falls back.
- **H0(no effect on the routine net):** the flag changes none of S1–S8's headline metrics beyond
  their own run-to-run variation.
- **H0(runtime):** the residual pass costs no more per cycle than the 13 s hard budget on these
  scenes. **This one can only be tested on the synthetic scene sizes here (≤ 11 decodes per cycle),
  not on a busy real band** — see Section 3.

**What actually happened.** H0(no harm) holds on every measure available: both batteries PASS, S5
0/120 (Gate A) and 0/60 (Check B) with the flag ON, zero `Sub-feas` log lines (no access violation,
no deadline abandonment, no contained exception) across 436 flag-ON cycles. H0(no effect) is **not
rejected**: OpenWSFZ S7 rose by 8 messages (166 → 174 of 215) with the flag ON, but that movement
is inside the series' own range and S7 is instrument-suspect by standing rule (Section 5). H0(runtime)
is met on these scenes (max 2.49 s), and says nothing about the real-band worst case.

## Section 2 — Results, flag OFF versus flag ON (same DLL, same seeds)

| Metric | OFF | ON | Note |
|---|---|---|---|
| S1 %GR&R / ndc | 0.39% / 22 | 0.28% / 26 | both PASS (≤ 10%) |
| S2 %GR&R / ndc | 0.00% / 1470 | 0.00% / 1491 | |
| S3 %GR&R / ndc | 0.73% / 16 | 0.51% / 19 | |
| S1 SNR bias, WSJT-X | +0.82 dB | +0.75 dB | |
| S1 SNR bias, OpenWSFZ | **+1.45 dB** | **+1.18 dB** | both above this series' 0.82–1.12 dB range; see Section 5, item 5 |
| S1b decode rate (info), WSJT-X / OpenWSFZ | 58.33% / 50.00% | 66.67% / 50.00% | WSJT-X moved with no change to WSJT-X |
| S4 OpenWSFZ TP / FN / FP / TN | 96 / 12 / 0 / 180 | 96 / 12 / 0 / 180 | **identical**, Recovery 88.89% |
| S4 WSJT-X TP / FN | 101 / 7 | 100 / 8 | reference moved by one |
| κ OpenWSFZ vs truth | 0.909 | 0.909 | |
| S5 Gate A (AWGN) FP, WSJT-X / OpenWSFZ | 0/120 / 0/120 | 0/120 / 0/120 | 95% UB 2.47% each |
| S5 Check B (narrowband) FP | 0/60 / 0/60 | 0/60 / 0/60 | |
| Gate A-W / Gate A-Δ | 1/480 (UB 0.984%) PASS / PASS | 1/480 PASS / PASS | neither sweep contributed a new AWGN event |
| S7 recovery, WSJT-X | 94.42% (203/215) | 96.28% (207/215) | |
| S7 recovery, OpenWSFZ | 77.21% (166/215) | 80.93% (174/215) | **+8 messages** |
| S8 decode rate, WSJT-X / OpenWSFZ | 93.33% / 91.67% | 93.33% / 91.67% | identical |
| Unexplained decodes, OpenWSFZ | 1 (S8, Δf 25.0 Hz) | 1 (S7, Δf 3.0 Hz) | WSJT-X 0 / 0. See Section 5, item 3 |
| Pooled S7+S8 ratio (OpenWSFZ % of WSJT-X)¹ | 221/258 = **85.66%** | 229/262 = **87.40%** | reference-driven, see footnote 17 |

¹ Derivation in Section 6, footnote 17.

**Where the S7 movement sits.** Comparing the same 430 message keys across the two runs:

| Appraiser | flips miss → hit | flips hit → miss | Cells |
|---|---|---|---|
| OpenWSFZ | **8** | **0** | P0 ×4, P15 ×4 (both 2-stack, equal 0 dB co-channel cells) |
| WSJT-X (decoder unchanged) | 6 | 2 | P2 ×2, P3 ×2, P4 ×2 up; P5 ×2 down |

Two facts to hold together. **First,** WSJT-X, whose decoder did not change, flipped 8 messages
between the two runs too (net +4): the instrument's own run-to-run noise is of the same order as
OpenWSFZ's 8. **Second,** every one of OpenWSFZ's 8 flips is in the same direction, and both cells
are 2-stack co-channel cells, the geometry subtraction targets. **P2 (3-stack) stays 0/15 in both
runs.** That is a hint worth chasing. It is not evidence: one pairing, no pre-registered test, and
I am deliberately not quoting a p-value on it (standing rule on uncitable statistics).

**Reading it against the series (Section 6).** Since the S7 design reached N=215 (2026-09-06
onward, 11 comparable sweeps before today's two), OpenWSFZ S7 has read **165–181 of 215**. OFF's 166
sits at the low edge of that range; ON's 174 is mid-range. In the same-build repeat batch
(`4584900d`, six sweeps on one build) the readings were 165, 178, 178, 177, 181, 173. OpenWSFZ's
own P0 range over those 11 sweeps is 5–10 of 10 and P15's is 2–10 of 10. OFF read P0 = 5 and P15 =
6 (low end), ON read 9 and 10 (high end). **The OFF-to-ON difference is smaller than the span of a
single build's own repeats, and it comes from two cells whose OFF reading was at its historical
floor.** Regression to the mean explains it without any effect.

## Section 3 — Runtime and stability (inputs to tasks §7/§8.1, not a gate result)

Per-cycle `elapsed` from the daemon's own log line (pass-0 plus residual pass, one `sw` window),
436 cycles in each run:

| | mean | p50 | p95 | p99 | max | slowest cycle's decodes |
|---|---|---|---|---|---|---|
| OFF | 88 ms | 71 ms | 199 ms | 331 ms | 374 ms | 8 |
| ON | 351 ms | 164 ms | 1993 ms | 2305 ms | **2490 ms** | 11 |

- On cycles with at least one decode: OFF mean 104 ms, ON mean 634 ms (about 6×).
- ON by decode count: 1 decode mean 591 ms (max 2112 ms); 2–4 decodes mean 587 ms; 5–9 decodes mean 648 ms; 10+ decodes mean 1732 ms (max 2490 ms). Cost is driven by the number of re-encodable
  signals, as designed.
- **The 13 s hard budget is not approached on these scenes (max 2.49 s), and the cycle-elapsed
  ceiling was never near the deadline guard.** Zero `Sub-feas` warning lines in either ON log
  file: no native access violation, no contained exception, no deadline abandonment in 436
  flag-ON cycles.
- **What this does NOT show.** These are sparse synthetic scenes (at most 11 decodes per cycle).
  The Developer's own benchmark predicted ~26 s FFT-only for a busy **24-signal** cycle before
  parallelism. A busy real band has never been run through this build. **§8.1 is therefore not
  satisfied by this run.** Straight-line scaling from the 10+ bucket hints at a few seconds for 24
  signals with four-way parallelism, but that is an extrapolation and I am not citing it as a
  result.
- **§7 (stability gate) is not satisfied either:** 1 h 49 min, 436 cycles. That is a useful clean
  data point, not a multi-hour stress pass.

## Section 4 — Limitations, disclosed

1. **Order and time confound.** OFF ran first, ON about 5 minutes after OFF finished. No
   randomised or interleaved order; any same-day chain drift lands on the ON−OFF difference.
   WSJT-X's own S7 movement (+4 messages, net) is a direct read of that instrument noise.
2. **One pairing.** Every comparison here is n = 1 on each side.
3. **A display-only setting differs.** During the OFF run the Captain changed the daemon's decode
   display setting through the Settings page (`decodeNoiseSuppression.suppressSynthetic=false`,
   visible in the daemon-rewritten config). The ON config carried that setting from the start at
   the Captain's request. It affects what the UI shows, not decoding or `ALL.TXT`; both runs' `ALL.TXT`
   were produced by the same pipeline. The same save also **reset `cycleAudioArchive` to `off`**
   (defect, filed as [#193](https://github.com/frank001/OpenWSFZ/issues/193)); the QA restored it
   live at about 16:42Z after the Captain agreed. **The daemon-side captured audio for the OFF run is
   missing from about 15:58Z to 16:42Z** (S4's tail and most of S5). WSJT-X's own WAVs cover that
   window. The Captain does not need synthetic WAVs (discussion: [#194](https://github.com/frank001/OpenWSFZ/issues/194)).
   Decode results are unaffected.
4. **No per-cycle residual-pass instrumentation.** The daemon does not log which decodes came from
   the residual pass (tasks §4.2 is open). **I cannot say which of ON's decodes were residual-pass
   decodes.** The S7 gain above is inferred from OFF-vs-ON message flips, not observed directly.
5. **Attended tooling glitches**, all recorded in Section 5: PRECHECK needed a build-provenance
   file generated by hand; a console window was left visible; `analyse.py` SHA field wrong again.

## Section 5 — Recommendations

**No gate failures. No merge-blocking finding. Nothing here changes the code-review verdict (approved
for the code, flag default OFF).**

1. ✅ **Safety readings are clean.** Flag ON: S5 0/120 Gate A, 0/60 Check B, S4 confusion matrix
   identical to OFF, S8 identical, no native failure of any kind in 436 cycles. 0/120 has a 95% UB
   of 2.47%, so this cannot exclude a false-positive rate of a few percent; it does exclude a gross
   phantom-decode problem on noise.
2. 🛑 **Do not cite OpenWSFZ S7 +3.72 pp (77.21% → 80.93%) as a subtraction gain, and do not cite
   the pooled ratio movement.** Both are inside the series' own range, S7 is instrument-suspect
   under this table's standing rule, and the reference decoder moved on the same seeds. The
   direction and the cells (P0, P15; 8 gains, 0 losses) are consistent with the mechanism and are
   the reason to look further, nothing more. The one offline result that stands is SUB-FEAS's net
   **+8.89 pp** on the 40m corpus (after the replay control), one corpus, one pass.
3. ℹ️ **Unexplained decodes: OFF S8 ×1 (Δf 25 Hz), ON S7 ×1 (Δf 3.0 Hz), WSJT-X 0.** Each within the
   0–2 range every prior sweep shows. I have **not** located the specific ON decode. A decode 3 Hz
   from an injected signal is the shape a subtraction residue artefact would take, and it appears
   in the one scenario where subtraction acts; one event on one run cannot support any claim. **Follow-up:**
   identify that row and check whether OFF produced it at the same seed (offline, read-only).
4. **What decides §8.1 is a real-band replay, and it is cheap.** Take captured real cycles with ≥ 20
   decodes from the existing endurance corpus, replay them through this build flag-ON versus OFF
   offline, and read per-cycle elapsed. No live run and no source change. It also gives the busy-band
   worst case this battery cannot. **Architect accepted and wrote the pre-registered spec**
   (`qa/rr-study/2026-09-29-2010-architect-sub-feas-8-1-real-band-runtime-replay-spec.md`, with
   Amendment 1 after QA's R0 finding: R0 now runs through the DLL that produced each archive).
   Pool: 3,734 endurance cycles with ≥ 20 OpenWSFZ pass-0 decodes (611 with ≥ 25, 28 with ≥ 30),
   all with daemon-side WAVs present. **Not started: it waits on the post-§4.2 build decision,
   which is the Captain's.**
5. ⚠️ **OpenWSFZ's S1 SNR bias and S1 %GR&R are above the recent series in *both* runs, including
   the flag-OFF one** (bias +1.45 dB OFF / +1.18 dB ON against 0.82–1.12 dB in the 13 preceding
   sweeps in `trend.csv`; S1 %GR&R 0.39% / 0.28% against 0.17–0.37%). WSJT-X's bias is unchanged
   (+0.82 / +0.75). **Flag-OFF control run (Architect ruling 2; pre-registered `6ecf2a37` before
   any decode, Amendment 1 `4c77045d`; results `7e4fe882`; Architect ruling
   `2026-09-29-2030-architect-flagoff-control-ruling.md`):**
   - Three DLLs from git, each in its own process, 182 cycles (S1, S1b, S2, S7, S8; S3 dropped:
     25 of its 30 cycles fall in the archive gap). Actual SHA-256: merge-base `c3f42362`
     `91997e38…ad6c1c6`; `decoding_improvement` `84cac119` `38a21f84…a1cba`; this build `0d6b1937`
     `5a6a4dc0…e38c5`. **No independent pin exists for any of them.**
   - **C1: the build under test equals its merge-base on 182/182 cycles**, exact multiset of
     (frequency, DT bits, SNR), 0 access violations. All three DLLs are identical on every cycle.
     V0 (replay reproduces the daemon) 69/72 = 95.8%; the archive WAV is pre-normalisation.
   - **The S1 bias is +1.45 dB in all three DLLs, to the digit: not this change, not the build
     lineage.** 🛑 Do not cite it as a build effect. Its cause is the captured audio or the
     configuration around it, unseparated.
   - **Registered verdict, verbatim: "PASS but VACUOUS by term 1"** (294 decodes against the
     registered 300; the threshold was an unmeasured guess and was not adjusted). The Architect
     rules it non-disqualifying (term 2, 10 of 10 S1 levels biased ≥ 1.0 dB, passes; C1 is exact),
     and the **merge gate for ruling 2 is MET on the native path.**
   - **The claim must carry its limits wherever it is cited:** native `ft8_decode_all` only; the
     managed flag-OFF branch (`_subtractionEnabled && native.Length > 0`) was covered by code
     review, not run; synthetic audio; no independent DLL pins.
   - **Follow-up approved by the Architect, low priority, not merge-blocking, not run:** replay
     `5f17b43`'s own S1 audio through the same DLL to see whether the bias differs with the audio
     (pre-register both outcomes; add aggregate pre-normalisation audio descriptors for both sets).
6. 🔧 **Instrumentation gap.** tasks §4.2 (a distinct log line for the residual pass) is open, and
   this measurement needed it. Without it, attributing decodes to the residual pass requires a replay.
   **Architect agreed** (ruling 3): Developer handoff **after the Captain's go**, bundled with the
   dedicated tests 6.3/6.5/6.6 (source change, HK-011); if it is C#-only the `libft8.dll` pin should be
   unchanged, verified by hash.
7. **Tooling defects found this session** (none affected results): (i) `analyse.py` SHA field
   wrong, third time (the correction under the header table); (ii) the detached launcher left a visible, empty console window
   (its own "no console window" fix evidently regressed for one child); (iii) PRECHECK refused to arm
   until `tools/capture_build_provenance.py` was copied into the scratch build worktree and run
   (it derives its repo root from its own path, so it cannot run from another worktree);
   (iv) Settings-page save resets `cycleAudioArchive` ([#193](https://github.com/frank001/OpenWSFZ/issues/193));
   (v) `analyse.py` appended today's `trend.csv` rows in the scratch tooling worktree only, with the
   wrong SHA. **Corrected and appended to the tracked `qa/rr-study/trend.csv` with the daemon's
   real build SHA (`0d6b1937…`); the OFF and ON rows share that SHA and are told apart by order
   only (OFF first), since the file has no flag column.** The pre-existing `2026-09-23` row still
   carries the tooling SHA `345e75ff` (corrected in that report's prose, not in the CSV); left as
   found.
8. **Standing gate status for enabling the flag (tasks §8):** §7 not satisfied, §8.1 not satisfied
   (synthetic, sparse), §8.2 not satisfied (synthetic is not an independent real corpus), §8.3 is the
   Captain's decision. The flag stays OFF by default and in every live run.

## Section 6 — Historical trend: every full S1–S8 sweep to date

**HK-031: Section 6 of the last report (`2026-09-23-5f17b43`, twenty-seven runs) was read in full
before any analysis above; this section is that table carried forward with today's two rows
appended and footnotes 16–18 added. Footnotes 1–15 are copied verbatim.** `%GR&R` is each stage's
own Summary-table figure (AIAG %Contribution, threshold ≤ 10% PASS). S5 FP: from `4cc1984` onward the
ratified gate is the trailing-window Gate A-W/Gate A-Δ (R&R-011). S7/S8 are the "all"/overall
decode-recovery percentages. The final column is OpenWSFZ's pooled S7+S8 matched-decode count as a
percentage of WSJT-X's own.

**S4/κ is not a column in this table** (duplicate-row attribution defect, fixed at source from
`4584900d` onward; it annotates no cell here, so it carries no footnote number).

| Date | SHA | S1 %GR&R | S2 %GR&R | S3 %GR&R | S5 FP (WSJT-X / OpenWSFZ) | S7 recovery (WSJT-X / OpenWSFZ) | S8 decode rate (WSJT-X / OpenWSFZ) | OpenWSFZ, % of WSJT-X (S7+S8 pooled, excl. FP)¹ |
|---|---|---|---|---|---|---|---|---|
| 2026-06-06 | `4c34ef6` | 32.0% **FAIL** | 0.0% | 3.8% | 0.0% / 0.0% | 78.5% / 47.3% | — | 60.27%² |
| 2026-06-06 | `6bab388` | 6.5% | 0.0% | 3.9% | 0.0% / 0.0% | 77.4% / 46.2% | — | 59.72%² |
| 2026-06-07 | `4b3a4ca` | 1.4% | 0.0% | 3.4% | 0.0% / 0.0% | 76.3% / 54.8% | 95.0% / 86.7% | 80.47% |
| 2026-06-14 | `815b652` | 0.3% | 0.0% | 3.0% | 0.0% / 0.0% | 77.4% / 50.5% | 95.0% / 83.3% | 75.19% |
| 2026-06-20 | `6e821fa` | 0.4% | 0.0% | 3.0% | 0.0% / **91.7% FAIL**³ | 92.6% / 70.2% | 93.3% / 86.7% | 79.61% |
| 2026-06-22 | `f11f438` | 0.4% | 0.0% | 3.1% | 0.0% / 0.0% | 94.0% / 74.4% | 93.3% / 86.7% | 82.17% |
| 2026-07-04 | `793a298` | 0.5% | 0.0% | 3.4% | 0.0% / 0.0% | 96.3% / 73.0% | 93.3% / 86.7% | 79.47% |
| 2026-08-05 | `3bd4cd0` | 7.2% | 0.0% | 3.6% | 0.0% / 0.0% | 96.3% / 70.2% | 93.3% / 83.3% | 76.43% |
| 2026-08-15 | `8d6e1b1` | 0.5% | 0.0% | 1.4% | 0.0% / 0.8% | 95.3% / 74.4% | 93.3% / 86.7% | 81.23% |
| 2026-08-21 | `7d36038` | 0.3% | 0.0% | 0.4% | 0.0% / 0.8% | 95.3% / 68.4% | 96.7% / 83.3% | 74.90% |
| 2026-08-22 | `f5dec23` | 0.4% | 0.0% | 0.4% | 0.0% / **3.3% FAIL**⁴ | 98.1% / 79.5% | 91.7% / 91.7% | 84.96% |
| 2026-08-27 | `22b749c` | 0.3% | 0.0% | 0.4% | 0.0% / 0.0% | 97.7% / 78.6% | 96.7% / 91.7% | 83.58% |
| 2026-08-29 | `872ba65` | 0.25% | 0.0% | 18.65%⁵ | 0.0% / **7.66% FAIL** | 93.0% / 74.0% | 96.7% / 91.7% | 82.95% |
| 2026-08-30/31 | `2e60949` | 0.27% | 0.0% | 0.44% | 0.0% / 5.15%⁶ | 98.1% / 82.8%⁷ | 91.7% / 91.7% | 87.59% |
| 2026-09-02 | `3b52608` | 0.22% | 0.0% | 0.55% | 0.0% / **14.61% FAIL** | 94.4% / 83.7% | 100.0% / 91.7% | 89.35% |
| 2026-09-03 | `35378b9` | 0.21% | 0.0% | 0.55% | 0.0% / 10.12% FAIL | 96.3% / 81.4% | 95.0% / 91.7% | 87.12% |
| 2026-09-06 | `4c7d5ad` | 0.24% | 0.00% | 0.40% | 0.0% / 12.42% FAIL⁸ | 98.14% / 79.07% | 100.00% / 88.33% | 82.29% |
| 2026-09-07 | `4cc1984` | 0.20% | 0.0% | 0.59% | 0.0% / 6.33% FAIL⁹ | 99.07% / 79.07% | 91.67% / 91.67% | 83.96% |
| 2026-09-12 | `fbf8c0b5` | 0.37% | 0.0% | 0.35% | 0.0% / 0.0%¹⁰ | 87.44% / 82.79% | 93.33% / 91.67% | 95.49%¹¹ |
| 2026-09-12/13 | `4584900d #1` | 0.18% | 0.0% | 0.55% | 0.0% / 0.0%¹³ | 95.35% / 76.74% | 98.33% / 91.67% | 83.33% |
| 2026-09-13 | `4584900d #2` | 0.20% | 0.0% | 0.43% | 0.0% / 0.0%¹³ | 100.00% / 80.00% | 91.67% / 91.67% | 84.07% |
| 2026-09-13 | `4584900d #3` | 0.20% | 0.0% | 0.43% | 0.0% / 0.0%¹³ | 95.35% / 82.79% | 95.00% / 91.67% | 88.93% |
| 2026-09-13 | `4584900d #4` | 0.30% | 0.0% | 0.60% | 0.0% / 0.0%¹³ | 96.28% / 82.33% | 91.67% / 91.67% | 88.55% |
| 2026-09-13 | `4584900d #5` | 0.20% | 0.0% | 0.60% | 0.0% / 0.0%¹³ | 99.07% / 84.19% | 95.00% / 91.67% | 87.41% |
| 2026-09-13 | `4584900d #6` | 0.20% | 0.0% | 0.50% | 0.0% / 0.0%¹³ | 97.21% / 80.47% | 91.67% / 91.67% | 86.36% |
| 2026-09-14 | `db3a3085` | 0.19% | 0.0% | 0.75% | 0.0% / 0.83%¹⁴ | 94.42% / 81.86% | 96.67% / 91.67% | 88.51% |
| 2026-09-23 | `decoding_improvement@84cac119`¹⁵ | 0.19% | 0.0% | 0.72% | 0.0% / 0.0%¹³ | 90.70% / 83.72% | 91.67% / 91.67% | 94.00%¹¹ ¹² |
| **2026-09-29** | **`feat/sub-feas-native-subtraction@0d6b1937`, flag OFF¹⁶** | **0.39%** | **0.0%** | **0.73%** | **0.0% / 0.0%¹⁸** | **94.42% / 77.21%** | **93.33% / 91.67%** | **85.66%¹⁷** |
| **2026-09-29** | **`feat/sub-feas-native-subtraction@0d6b1937`, flag ON¹⁶** | **0.28%** | **0.0%** | **0.51%** | **0.0% / 0.0%¹⁸** | **96.28% / 80.93%** | **93.33% / 91.67%** | **87.40%¹⁷** |

¹ Value = pooled(OpenWSFZ S7+S8 matched decodes) ÷ pooled(WSJT-X S7+S8 matched decodes) × 100,
computed directly from each run's own `S7_matched.csv`/`S8_matched.csv` counts where available in
the QA worktree, else derived from published integers. For `2026-09-23` (this run): S7 195/215
(WSJT-X) vs 180/215 (OpenWSFZ); S8 55/60 (WSJT-X) vs 55/60 (OpenWSFZ); pooled 235/250 = 94.00%.

² `4c34ef6` and `6bab388` (2026-06-06) predate S8's introduction — their footnote-1 figure is
S7-only. One fact, stated as shared, not as a "first" — legitimately reused across exactly these
two rows.

³ Plain decode-rate era (pre R&R-004 ratified UB gate); not the same metric as later rows, fixed
under D-009. Not comparable to the UB figures below it.

⁴ Second-ever ratified-gate FAIL, N=120 (pre R&R-009 default restriction).

⁵ Not comparable to the S1–S3 series above it — confounded by a harness playback-timing defect
discovered in that same run (`872ba65`'s Section 5, Finding 1), not a decoder result.

⁶ N=120 (`resume_study.py` artefact — R&R-009's N=60 restriction not applied on resume), not the
routine N=60 battery. PASS at this N; not directly comparable to the N=60 rows around it.

⁷ S7 figure is from a 2026-08-31 targeted re-run (`results/2026-08-31-2e60949/`), same SHA.

⁸ `4c7d5ad` (2026-09-06) ran under the OLD single-gate S5 architecture (N=60 per R&R-009), before
the Gate A/Check B split introduced the following row — its 12.42% is that run's own 95% UB
(3/60 events), not directly comparable to the post-split N=120 Gate A rows around it. (Placed here,
after `872ba65`/`2e60949`/`3b52608`/`35378b9` in the numbering, because `4c7d5ad` was added back
into this table later — see the Section 1 history of prior reports — but its **row** always sat at
its correct chronological date; only the *number* trailed the row's own re-insertion.)

⁹ **First run scored under R&R-010's Gate A / Check B split** (ratified 2026-09-06 20:29 UTC;
`4c7d5ad`, footnote 8, ran earlier that same day under the old architecture and does not qualify).
The figure shown is **Gate A** (AWGN, parts 0/1, N=120). **Check B** (narrowband, parts 2/3, N=60) is scored
separately: 0/60, PASS, never pooled with Gate A. `a3738fc` (2026-07-04, a targeted N=300
S5-only confirmatory run, 8/300, PASS) is not in this table — not a full battery.

¹⁰ **The one and only first run under R&R-011** (2026-09-08): per-sweep Gate A becomes INFO only
from here on, superseded by the trailing-window Gate A-W/Gate A-Δ (≥480-AWGN-slot window). Gate
A-W PASS (14/480=2.917%, 95% UB 4.522%), FRAGILE (leave-one-out flips the verdict).

¹¹ **Reference-driven, not an OpenWSFZ improvement — this row and the `2026-09-23` row below
share the same mechanism and reuse this note (Architect finding, 2026-09-23 16:34Z; QA
footnoted 2026-09-25, HK-022, fixed where it lives — previously this cell carried no
qualifier at all).** This row's 95.49% (the series high until the row below) is carried by
WSJT-X's own S7 recovery dropping to 87.44% — the N=215-era low for that appraiser: every row
from `6e821fa` onward, once S7 moved to its current 215-message design, sat ≥92.6%, and the
earlier N=93-era sweeps ran 76.3–78.5%, below this reading — not by OpenWSFZ moving (82.79%,
within its established 170–180/215 range since `2e60949`). 🛑 **Do not cite 95.49% (or the row
below's 94.00%) as an OpenWSFZ-vs-WSJT-X gain** — read both through the same S7 instrument-suspect
flag every S7 movement carries under this table's own standing rule, not as narrowing the gap.

¹² **`2026-09-23`'s own counterfactual (Architect arithmetic, 2026-09-23 16:34Z, from this row's
own integers; footnote 11 above is the general framing this specific number supports — Section 5
of this report separately struck the underlying S7 P2 cell as instrument-suspect, no action
needed).** WSJT-X's S7 fall on this row is concentrated almost entirely in one cell: P2 read 3/15
against a constant 15/15 in every comparable row. Restoring P2 to its usual 15/15 (+12) gives a
counterfactual WSJT-X S7 of 207/215 and a counterfactual pooled ratio of 235/262 ≈ **89.7%** — in
line with the `db3a3085` row's 88.51%, not a step up. The published 94.00% is not wrong, but it is
this row's noisiest single input, not evidence of an OpenWSFZ gain.

¹³ **The `4584900d` same-build repeat-measurement batch (sweeps #1–#6), not itself a "first" of
anything** — a distinct fact from footnote 10 above, given its own number rather than folded into
it, precisely because reusing a footnote whose own text claims uniqueness would misdescribe six
non-first rows. Gate A-W PASS (8/480=1.667%, 95% UB 2.987%), identical across all six sweeps since
none contributed a new AWGN event; not FRAGILE. **Reused a third time for `2026-09-23`** (this
run) — a different, later fact than either sweep-batch use above, but the identical *statement*
("this row's own sweep added zero new S5 events, so its Gate A-W/Gate A-Δ reading is carried
entirely by other sweeps' events") — permitted under this table's own footnote rule because it is
genuinely the same fact, not a coincidence of wording.

¹⁴ **`db3a3085`'s own S5 Gate A-W/Gate A-Δ reading — a distinct fact again, not the same
number as 10 or 13.** This sweep is the first to register a new AWGN event since the batch above,
so its figures differ from every row footnotes 10 and 13 cover. Gate A-W PASS (1/480=0.208%, 95%
UB 0.984%), not FRAGILE (all four single-sweep leave-one-out deletions leave the verdict
unchanged). Gate A-Δ PASS (1/120 vs 0/360, Fisher p=0.2500) — the eight `4584900d`-batch-era
events have fully aged out of the trailing window by this sweep, leaving only this run's own
single new event (see Section 5).

¹⁵ **First row in this table on a `decoding_improvement` branch build, not `main`** — see the
correction note under the header table. SHA column shows `branch@commit-short` rather than a bare
SHA for this reason; every other row is implicitly `main` (or a feature branch merged into it by
the date shown). `decoding_improvement`@`84cac119` carries `DENSITY-REMEDY` Stage 1's shipped
suppression default (shim `20260054`, `suppression_triple=[-5,15,1]`) on top of the same
`PASSBAND-140` base `db3a3085` already tested (shim `20260051` there vs `20260054` here) — so a
small difference from the `main`-branch envelope this table mostly documents is licensed, not a
regression signal on its own; see Section 1/5 for the full framing. This run's own S5 Gate A-W/
Gate A-Δ reading carries zero new events from this sweep itself — see footnote 13's third use,
immediately above. Its own pooled-ratio reading (94.00%) is reference-driven, not an OpenWSFZ
gain — see footnotes 11–12.

¹⁶ **A same-day paired measurement, not two independent sweeps: first rows on the SUB-FEAS native
subtraction build** (`feat/sub-feas-native-subtraction` @ `0d6b1937`, shim `20260055`, `main`
lineage, `libft8.dll` SHA-256 `5a6a4dc0…e38c5`). The two rows are the **identical DLL and config**,
differing only in `decoder.subtractionEnabled`: OFF is the control (the design's "flag OFF leaves
output unchanged" path), ON is the measurement. OFF ran first; ON began about 5 minutes after OFF
ended. The SHA column shows `branch@commit-short` and the flag state; the analyser's own SHA field
for these runs (`62e8e74a`, the QA tooling worktree) is wrong — see the correction under the header
table. Both rows also carry a first-time S1 signature not seen in the 13 preceding sweeps in `trend.csv` (2026-09-02 onward): OpenWSFZ
S1 SNR bias of +1.45 dB (OFF) and +1.18 dB (ON) against 0.82–1.12 dB (this section's own
`trend.csv` column), see Section 5, item 5. That signature is present with the flag OFF, so it is
not attributable to subtraction; the flag-OFF control then showed it is identical (+1.45 dB) in the
merge-base, the `decoding_improvement` DLL and this build, so it is **neither this change nor the
build lineage** (cause: the captured audio or configuration, unseparated).

¹⁷ Same derivation as footnote 1, from each run's own `S7_matched.csv` / `S8_matched.csv`. **OFF:**
S7 203/215 (WSJT-X) vs 166/215 (OpenWSFZ); S8 55/60 vs 55/60; pooled 221/258 = 85.66%. **ON:** S7
207/215 vs 174/215; S8 55/60 vs 55/60; pooled 229/262 = 87.40%. 🛑 **Reference-driven and
instrument-noise-sized — do not cite the 1.74 pp movement between these two rows as an OpenWSFZ gain, nor
as an effect of the subtraction flag.** WSJT-X, whose decoder did not change, moved by +4 S7
messages between the same two runs (6 flips up, 2 down on identical seeds), and OpenWSFZ's +8 sits
inside its own 165–181/215 range since the N=215 design (footnote 11's framing). See Section 2.

¹⁸ **Both rows: this sweep itself contributed ZERO new AWGN events** (0/120 each) — the same
statement as footnote 13's third use, so Gate A-W/Gate A-Δ read 1/480 and 0/120 vs 1/360 for both
(the single event still inside the window is `db3a3085`'s). Check B (narrowband) 0/60 both. The
flag-ON row's 0/120 is the operative safety reading for the subtraction build (no phantom decodes
on signal-free AWGN slots); at N=120 its 95% upper bound is 2.47%, so it excludes a gross
problem, not a small one.

