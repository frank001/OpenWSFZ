# Architect ruling — flag-OFF control (ruling 2 of 2026-09-29 19:48Z): merge gate MET on the native path

- **Date (UTC):** 2026-09-29 20:30
- **Responds to:** `qa/rr-study/2026-09-29-2000-qa-to-architect-flagoff-control-results.md` (QA `7e4fe882`, local). I read the note in full; I did not re-run the harness or inspect `summary.json`.
- **src/native diff from this session:** none.

## 1. The guard's first term missed (294 < 300): not adjusted, and not disqualifying — my reasoning

- The registered verdict stays exactly as QA recorded it: **"C1 PASS but VACUOUS by the flat guard's first term."** Nobody edits the 300 after the fact.
- The ruling is mine to make, and I make it on what the guard is FOR (HK-026): can the instrument's response move where the boundary sits? Term 2 answers that directly: **10/10 S1 levels carry a replayed bias ≥ 1.0 dB (+1.10 to +1.80)**, i.e. the audio spans the biased range and the instrument reads the bias at every level. The instrument is not flat there.
- C1 is not a thresholded reading; it is an exact multiset match on (frequency, DT float32 bits, SNR) over 182 cycles/294 decodes, with an unrelated third DLL (b) also matching. A count 2 % under an unmeasured guess does not make an exact match vacuous. The 300 was a drafting defect in the pre-registration (a threshold set without knowing the yield: the same class of mistake as my own ROW 0g); recorded as such, not as a QA fault.

## 2. Ruling

- **Ruling 2's merge gate is MET for the native flag-OFF path:** c == a on 182/182 cycles, 0 AV, V0 69/72 (the replay is the live decode on the pre-normalisation archive WAV). This is what "flag OFF is byte-identical" can mean on native outcome fields on synthetic audio.
- **Limits that stay attached to the claim (say them wherever it is cited):** native entry `ft8_decode_all` only; the managed flag-OFF branch (`_subtractionEnabled && native.Length > 0`) is NOT exercised and rests on code review; synthetic audio only; no independent pin for any of the three DLLs (self-references and a downstream record).
- The merge itself (HK-010) and any push (HK-033) remain the Captain's. Open before merge still: tasks 6.3/6.5/6.6 tests, 6.8 Linux/macOS, 5.1, and the Captain's go on §4.2. §7/§8.1/§8.2 remain what they were (my unverified reading: they gate live use, §8.3).

## 3. The S1 bias: what is now known

- **+1.45 dB is not the decoder build, not the lineage, not this change** (a = b = c to the digit; the replay reproduces the live sweep exactly). Do not cite the bias as a build effect anywhere.
- WSJT-X unchanged (+0.82 → +0.75) while OpenWSFZ moved is the awkward part, as QA says; I don't have an explanation and won't guess one.

## 4. Follow-up: replay `5f17b43`'s own S1 audio through DLL c — APPROVED, low priority, NOT merge-blocking

- It cleanly splits "audio/chain" from "something else". Pre-register before running (HK-021), with the predicate stated for BOTH outcomes: c reads ≈ +0.88 on the old audio ⇒ the difference is in the captured audio; c reads +1.45 on both ⇒ unexplained, park it.
- Add to the pre-registration an **aggregate pre-normalisation audio descriptor per S1 cycle** (RMS, and a noise-floor proxy from the empty band regions), both sets, so that "the audio differs" can be checked rather than asserted. Integers/aggregates only (HK-037).
- Treat S1 bias reads as instrument-suspect until this closes: no S1-bias figure goes into a trend claim, and the 2026-09-29 rows in `trend.csv` stay as recorded, footnoted.
- Time-box it: if it does not resolve in one replay, park it. Zero decode-rate value; it exists so the trend table is not left with an unexplained step.
