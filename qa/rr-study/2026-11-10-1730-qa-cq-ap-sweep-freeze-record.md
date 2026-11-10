# CQ-AP A1.3 sweep (positive control): FREEZE RECORD, before any real-seed output

**QA · 2026-11-10T17:29Z (`date -u` read 17:29:26Z at the commit).** Spec: `arch/cq-ap` §8 A1.3. Nothing here is real audio, no real callsign exists (Q-prefix calls generated).

| item | value |
|---|---|
| Code | `qa/cq-ap/cqap_sweep.py`, commit **`d100e9aff73bc5348e223aef8cc97f6a7eeb4d4a`** (QA, `qa/same-chain`, local) |
| Build under test | `feat/cq-ap` `7ca00264` (reviewed, record `a6255625`); `libft8.dll` SHA-256 **`bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528`** (asserted in the code), shim 20260072 (asserted) |
| Decoder parameters | `ft8_set_decode_params(5, 0.05, 24)`, OSD sign fix 1: the station's live values; `ft8_decode_all` alone (native passes; not the managed staged pipeline: the question is the mechanism) |
| Messages | `CQ <Q-call> <grid>`, a fresh random call and grid per cycle, one signal per 15 s cycle, audio offset uniform in [600, 2800] Hz, DT uniform in [0.2, 1.5] s (inside the modulator's valid range, so the DT clamp defect cannot bite: out-of-range raises), clean-room encoder `qa/rr-study/synth` (NOT the build's own encoder) |
| Noise and SNR | white Gaussian noise, SNR = on-air signal power / noise power in 2500 Hz; buffer RMS-normalised to 0.20 as the decoder does |
| Phase A | OFF only, SNR −24 to −12 dB in 1 dB steps, **100 cycles per step**, seed **20261112**; **S50** = SNR where OFF's decode rate crosses 0.5 (linear interpolation, rounded to the nearest dB) |
| Phase B | SNR S50−4 to S50+1 dB, 1 dB steps (6 steps), **200 cycles per step**, seed **20261113**, OFF and ON on the SAME audio |
| Success | a decode whose text equals the message sent |
| **Bar (A1.3)** | at one or more steps **ON − OFF ≥ 10 percentage points AND ON's Wilson-95 lower bound > OFF's Wilson-95 upper bound**: PASS. Otherwise FAIL: the build goes back to the Developer and no replay arm runs |
| Descriptive | decodes of any other message (OFF, ON), `cq`-tagged decodes, ON-only and OFF-only successes per step, attempts, OSD entries (expected 0) |
| Disclosure | one plumbing run (5 cycles at −12 dB, seed 1, never the real seeds): OFF 5 of 5, ON 5 of 5, 1,057 attempts, 0 OSD entries |
| Run | `python -I qa/cq-ap/cqap_sweep.py --dll <the committed DLL> --out <scratch>\sweep_result.json` (run once; a crash is re-run unchanged) |
