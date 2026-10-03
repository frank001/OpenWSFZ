# QA → Architect: flag-OFF control (ruling 2) — results

- **Date (UTC):** 2026-09-29 20:00
- **Pre-registration:** `qa/rr-study/2026-09-29-1956-qa-flagoff-control-preregistration.md` (committed `6ecf2a37`, **before any decode**; Amendment 1 `4c77045d`, also before any decode). Harness: `qa/rr-study/sub-feas/flagoff_control.py`.
- **src/native changes:** none. DLLs extracted from git, never rebuilt. Nothing pushed.
- **Verdict, as registered: C1 PASS but VACUOUS by the flat guard — the S1 question is not cleared by the registered predicate.** Read Section 3 before anything else: the guard's decode-count term missed by 6 (294 vs 300) and I am not adjusting it afterwards. What the data show is clear all the same, and I set it out in Section 4.

## 1. What ran (HK-022)

| Item | Value |
|---|---|
| Scenarios (exact) | S1, S1b, S2, S7, S8 — **S3 dropped by Amendment 1**: 25 of its 30 cycles fall inside the daemon-side archive gap (≈15:58Z–16:42Z, #193), found by the harness's own missing-WAV assertion **before any decode**. S4/S5 excluded for the same reason. |
| Cycles | 182 (S1 30, S1b 12, S2 30, S7 105, S8 5). `--filter`: none; every stamp of those scenarios in the OFF sweep's `truth.csv`, every WAV present. |
| Stamp-list SHA-256 | `32a8f54eef3ae6a8f72e64f5987031c3dde69dc3225399c5eddf1c650d16c5d0` |
| Audio | the flag-OFF sweep's daemon-side captured WAVs (12 kHz, mono, 16-bit, exactly 180 000 samples, asserted per file) |
| Processing | the daemon's own: silence guard, D-002 RMS normalisation to 0.20 (float32), `ft8_set_ap_bits(empty)`, `ft8_set_decode_params(10, 0.10, 40)`, `ft8_decode_all`, 340-slot buffer. Each DLL in its own fresh process. |
| Outputs | gitignored `artefacts/rr_2026-09-29_flagoff_control/` (asserted ignored and untracked before decoding); `summary.json` SHA-256 `7cb6559b0999a7b15cde3042e647fc0093eec9f3373f2887b794617c7f7f5275`. Integers only; no message text ever left the decode function (HK-037). |

| DLL | Commit | Shim | Actual SHA-256 | Pin status |
|---|---|---|---|---|
| a (merge-base with `main`) | `c3f42362` | 20260051 | `91997e38038d9328edcb49cd1e8661706d0092ed2c73e808094c96c3980ad2c6` | Not quoted in its own `libft8.version.txt`; **is** quoted verbatim as the inherited pin in `0d6b1937`'s `libft8.version.txt` (checked by grep, 1 hit). That is a downstream record, not an independent manifest. |
| b (`decoding_improvement`, the `5f17b43` DLL) | `84cac119` | 20260054 | `38a21f840b00af146348c166786cb54e178cd2201c5ed4dba3016a4c589a1cba` | Quoted in its own version file (self-reference); also matches the value recorded in the 2026-09-22/23 provenance. |
| c (build under test) | `0d6b1937` | 20260055 | `5a6a4dc04a2cf6fbd987c12ce7635a968f4c9b69f73cacebe422af62827e38c5` | Quoted in its own version file (self-reference); identical to the DLL the sweeps ran. |

**No independent pin exists for any of the three** — only self-references and downstream records. That is the same limitation as in the sweep report.

## 2. Rows, as registered

| Row | Registered predicate | Reading |
|---|---|---|
| **V0** (validity) | replay of c reproduces the daemon's archived (SNR, frequency) in ≥ 95% of the 72 single-signal cycles (S1, S1b, S2) | **69/72 = 95.8% normalised → PASS** (un-normalised: 53/72, fails). The archive WAV is **pre-normalisation**, as the live path assumes; the replay is the live decode, on this evidence. |
| **C1** (the claim, blocks merge) | c == a exactly on every cycle: multiset of (frequency, DT float32 bits, SNR), and AV flags | **0 of 182 cycles differ**, 294 decodes in a; **0 access violations** in a, b or c. |
| **Flat guard (HK-026)** | ≥ 300 decodes in a **and** ≥ 3 S1 SNR levels with replayed bias ≥ 1.0 dB | **FAILS on its first term: 294 decodes (< 300).** Second term passes: **10 of 10** S1 levels have bias ≥ 1.0 dB. |
| **C2** (lineage reading) | bias(a) − bias(b) ≥ 0.30 dB and \|bias(c) − bias(a)\| ≤ 0.15 dB ⇒ SUPPORTED; \|bias(b) − bias(a)\| < 0.15 dB ⇒ REFUTED; else INCONCLUSIVE | S1 bias: **a = b = c = +1.45 dB, to the digit** ⇒ **REFUTED as lineage**. Per level identical in all three (−12.0 dB: +1.667 … 15.1 dB: +1.233). |
| **C3** (descriptive) | cycles in which b differs from a, and from c | **0 and 0.** |

## 3. Reading it as registered — and the flaw in my own guard

By the registered rule the verdict is **"C1 PASS but VACUOUS: cannot clear S1"**, and I report it as that. Two honest notes on why, so you can rule on it rather than take my word:

- The **300-decode threshold was an unmeasured guess**: I set it from the truth-row count (377 rows before Amendment 1) without knowing the yield. Dropping S3 removed about 30 decodes and the pool landed at 294. **I have not adjusted it** (the note forbids it, and doing so after the fact is exactly what the flat guard exists to prevent).
- The guard's **purpose** (HK-026: is the instrument's response flat where the boundary sits?) is served by its second term, which passes on every one of the 10 S1 levels: the audio covers the whole biased range, and the bias is present at each level (+1.10 to +1.80 dB), so this is not a flat, uninformative sample. Whether to treat the first term's miss as disqualifying is **your ruling to make, not mine.**

## 4. What the data show, independent of the guard

1. **The three DLLs are indistinguishable on this audio.** a, b and c decode the same 182 cycles to the same decode lists on the outcome fields, cycle by cycle (C1 and C3 both 0 of 182). Across shim 20260051 → 20260054 → 20260055, including Stage-1 suppression and the SUB-FEAS additions, nothing changes on outcome fields for these scenes.
2. **The +1.45 dB S1 bias is not in the decoder build.** The replay reproduces the sweep's live number exactly (+1.45), and it is the same for the merge-base, the `decoding_improvement` DLL and the build under test. So **not this change, and not the main-vs-`decoding_improvement` lineage** (the hypothesis you flagged as live). It cannot be subtraction either, as before.
3. **That leaves the audio the decoder received, or the configuration around it.** The S1 seeds are deterministic from the study's seed formula (verified identical between today's OFF and ON runs; I did not diff them against `5f17b43`'s truth file), so the difference from `5f17b43`'s +0.88 dB has to come from the captured audio (the chain, level, or what is on the wire), or from the explicit decoder-config values I passed (identical to the code defaults: 10, 0.10, 40). WSJT-X's bias is unchanged (+0.82 → +0.75 dB) on what should be the same audio, which is the awkward part: if the chain had changed, WSJT-X would likely have moved with it.
4. **Proposed follow-up (not run, needs your call):** replay `5f17b43`'s own captured S1 audio (present locally, gitignored: `results/2026-09-23-5f17b43-captured-audio`) through DLL c and compare its bias with today's +1.45 dB. If the same DLL reads about +0.88 dB on the earlier audio, the bias difference is in the captured audio and the decoder is cleared; if it reads +1.45 dB on both, the difference is something else and I have no cheap explanation. **Pre-registered before running if you want it.**

## 5. Effect on merge

C1 has **no failing cycle**, so the registered trigger for "defect, blocks merge" did **not** fire. By the registered predicate the S1 question is not cleared (Section 3), so it is your ruling whether the merge gate on ruling 2 is met: my own reading is that the evidence supports the "flag OFF is byte-identical" claim on this audio (the strongest form: three builds identical on every cycle), with the 294-vs-300 miss being a defect in my threshold, not in the data. I would rather you make that call than me.

## 6. Disclosures

- **Amendment 1 (S3 dropped)** is the only change to the registered set, made before any decode. The first run stopped at the missing-WAV assertion and produced no decode output.
- Native entry point only: `ft8_decode_all`. The managed flag-OFF path (`_subtractionEnabled && native.Length > 0`) is not exercised here.
- Synthetic audio only; nothing here says anything about a real band.
- 🔒 NFR-021 / HK-037: aggregates and stamps only; this note contains no message text and no callsign.
