# PRE-REGISTRATION — flag-OFF control (Architect ruling 2, 2026-09-29)

- **Date (UTC):** 2026-09-29 19:56. **Committed BEFORE any decode of this control was run.**
- **Author / executor:** QA. **src/native changes:** none (HK-011); replay only, DLLs extracted from git, never rebuilt.
- **Harness:** `qa/rr-study/sub-feas/flagoff_control.py`, committed in the same commit as this note. The predicates below are the harness's own constants and branches; if the two ever disagree, the harness is what ran and this note is the record of intent.
- **Question:** the design claims that with `subtractionEnabled=false` the build's decode output is byte-identical to pre-change. OpenWSFZ's S1 SNR bias read +1.45 dB (flag OFF) and +1.18 dB (flag ON) in the 2026-09-29 paired sweep, against 0.82–1.12 dB in the 13 preceding sweeps. Is that bias (a) caused by this change, or (b) lineage / configuration?

## 1. Conditions (three DLLs, each in its own fresh process)

| Label | Source commit | Meaning | Shim |
|---|---|---|---|
| a | `c3f42362` | merge-base of `feat/sub-feas-native-subtraction` with `main` | 20260051 |
| b | `84cac119` | the `decoding_improvement` DLL R&R `2026-09-23-5f17b43` ran | 20260054 |
| c | `0d6b1937` | the build under test | 20260055 |

Each DLL is extracted with `git show <commit>:src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`. The report quotes each DLL's actual SHA-256 and whether that SHA appears in that commit's own `libft8.version.txt`. **That is a self-reference, not an independent pin (HK-022); the report will say so.** Expected actuals from the earlier sweep records: a = `91997e38…ad6c1c6`, b = `38a21f84…a1cba`, c = `5a6a4dc0…e38c5`.

## 2. Audio and processing

- **Audio:** the flag-OFF sweep's daemon-side captured WAVs (`…-OFF-captured-audio/owsfz/wav/`), for every cycle stamp in `truth.csv` for scenarios **S1, S1b, S2, S3, S7, S8**. S4 and S5 are excluded because the daemon-side archive has a gap from about 15:58Z to 16:42Z (#193). Each WAV asserted 12 kHz mono 16-bit, exactly 180 000 samples. The frozen stamp list's SHA-256 goes in the report.
- **Processing (the daemon's own, in code):** silence guard (RMS < 1e-6), D-002 RMS normalisation to 0.20 in float32 arithmetic (as `Ft8Decoder.NormalisePcm`), `ft8_set_ap_bits(empty)`, `ft8_set_decode_params(10, 0.10, 40)` (the explicit config values of the sweep), `ft8_decode_all` with a 340-slot buffer. Single thread.
- 🔒 **NFR-021 / HK-037:** only integers leave the decode function: frequency (Hz), DT as its float32 bit pattern, SNR (dB). Message text is never read out of the result buffer; the only line-level read of `ALL.TXT` keeps stamp, SNR, frequency. Outputs go to a gitignored directory that the harness asserts is ignored and untracked before decoding.

## 3. Rows

**V0 — instrument validity (must pass or STOP; nothing below is read).** For DLL c, in at least **95 %** of the single-signal cycles (S1, S1b, S2, S3: 102 stamps), the replay's sorted list of (SNR, frequency) equals the daemon's archived `ALL.TXT` record for that stamp. Two variants are evaluated for c: **N** (normalised, as the live path) and **U** (un-normalised); this settles whether the archive WAV is pre- or post-normalisation. N is used if it passes; else U only if it passes; **but a and b are only run as N, so a U-only pass STOPs** (no improvising after the fact). Neither passes ⇒ STOP: the replay does not reproduce the daemon and nothing is citable. The tolerance is not adjusted afterwards.

**C1 — the claim (blocks merge).** Over **every** compared cycle, the decode list of c equals that of a **exactly** as a multiset of (frequency, DT float32 bits, SNR), and the access-violation flags agree. **Any** differing cycle ⇒ **FAIL: defect, blocks merge, goes to the Developer.** Zero differing cycles ⇒ the claim holds *for this audio set and this native entry point only* (the C# flag-OFF path, `_subtractionEnabled && native.Length > 0`, is separately covered by tests and by reading, not by this row).

**Flat guard (HK-026).** C1 PASS is **vacuous** unless the audio actually exercised the biased range: DLL a decodes at least **300** signals in total, **and** in S1 at least **3** SNR levels show a replayed bias (reported − true SNR, DLL c) of at least **1.0 dB**. If the guard fails, the report says the S1 question is *not cleared*, whatever C1 reads.

**C2 — lineage reading (descriptive, with the reading fixed now).** S1 bias per DLL = mean over matched S1 cycles of (reported SNR − true SNR); a decode matches the truth signal if its frequency is within 3 Hz. Reported overall and per SNR level for a, b, c.
- **Lineage SUPPORTED** iff bias(a) − bias(b) ≥ **0.30 dB** and |bias(c) − bias(a)| ≤ **0.15 dB** (a and c agree on the higher bias; b lower).
- **Lineage REFUTED** iff |bias(b) − bias(a)| < **0.15 dB**.
- Otherwise **INCONCLUSIVE**.
Threshold provenance, disclosed: the 0.30 dB gap was chosen knowing the two sweep readings (+1.45 dB for c, +0.88 dB for `5f17b43`, a 0.57 dB difference), before any replay data existed; 0.15 dB is the same figure as the residual tolerance and is set below the observed OFF/ON difference of 0.27 dB.

**C3 — descriptive only:** the number of cycles in which b differs from a, and from c. No bar.

## 4. Blind spots and what this does not test

- Native entry point only: `ft8_decode_all`. The managed flag-OFF path is not exercised here.
- The audio is the sweep's synthetic scenes (single-signal S1/S1b/S2/S3, multi-signal S7/S8), not a real band. C1 says nothing about real-band divergence.
- Byte-identity of the DLL's decode output is tested on **outcome fields**, not rendered text (the callsign hash table is process-global; comparing text across processes is not the question).
- No decode-rate claim is made from this control.

## 5. Reporting

The result goes to the Architect with: the three DLLs' actual SHA-256 and pin status, the exact scenario list and stamp-list SHA, V0's two counts, C1's differing-cycle count with stamps only, the flat guard's two numbers, and C2's three biases (overall and per level). If C1 FAILS or V0 STOPs, that is reported as such and nothing else is interpreted.
