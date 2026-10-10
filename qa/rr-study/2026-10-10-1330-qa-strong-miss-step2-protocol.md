# STRONG-MISS step 2 (the probe): run protocol (QA, frozen before the run)

- **To:** Architect, cc Captain. **From:** QA. **Spec:** `2026-10-10-1015-architect-to-qa-spec-strong-miss-replay.md` section 4c (amendment 2, `a269424a`) and 4d (amendment 3, `a5f4bb26`); step (a) ruled valid (`349d467e`). **Go:** the Captain, in the QA window ("go"), after (a) was ruled.
- **Nature:** diagnostic and descriptive. One night (`20261009_1752`), one chain, first nhard 24 + corrected-OSD row. No gain claimable. Aggregates only (HK-037).

## What is frozen by the spec (not re-opened here)

SM-P1 at least 95 % of 500 seeded controls decode (BP-only) in the window; SM-P2 at most 1 % of 500 seeded empty points give a BP-only CRC hit (200 to 2800 Hz, at least 100 Hz from every decode on either side). Window 25 points (+-2 frequency steps of 3.125 Hz, +-2 time steps of 0.08 s). Classes P-INVALID / P-FILTER / P-CLEAN / P-WEAK, first match wins. `ft8_refine_candidate` for every P-WEAK target. BP only: `ft8_ldpc_decode_llrs` with `osd_depth` -1. Normalised PCM through the product's `NormalisePcm` (reflection). P-FILTER = key in the raw output of the native first-stage call on the original normalised audio (the product's `IsPlausibleMessage`, reflection). Payload by the product's own encoder (`ft8_encode_message`, Gray inversion). Gate: SM-DECODER >= 50 (met in (a): 471).

## Choices QA makes here, frozen before the pilot is read

| item | choice | reason |
|---|---|---|
| Process | the replay (a) is re-run inside the same process, then the probe runs on its SM-DECODER set | nothing per message may be written to disk, so the target set cannot be carried over from (a). Class counts are reported again beside (a)'s 471 as a consistency check |
| Thread | the probe runs synchronously on one dedicated thread (64 MB stack); no await between arming and reading | the tap is thread-local |
| Mapping | probe position = WSJT-X value + median(OpenWSFZ - WSJT-X) per axis over the 500-control sample's matched pairs; probe axes are the native result's own (the managed layer only rounds `dt` to 0.1 s) | spec 4c.2; checked in `ft8_shim.c` (the `dt` formula is the inverse of the probe's) |
| Control sample | the 1,671 controls sorted by (cycle, key, rank), Fisher-Yates shuffled with `System.Random(20261010)`, first 500 | seeded, deterministic |
| Null points | `Random(20261011)`: cycle uniform over the 433, frequency uniform 200 to 2800 Hz, time uniform 0.6 to 1.2 s (the OpenWSFZ time range of the controls), rejected if any decode (either side) in that cycle is within 100 Hz | spec says seeded and same cycles; time range is QA's choice from the controls' OpenWSFZ DT |
| "Decodes" | `ft8_extract_llrs_at` returns 0 and BP-only gives `crc_ok` 1 and the 77 message bits equal one acceptable expected payload where the text is packable; CRC-only where it is not (text with an unresolved `<...>`, or the encoder cannot pack it) | the decoder zeroes the 14 CRC bits after checking them, so the comparison is on the 77 message bits; `crc_ok` carries the CRC |
| **RR73 rule** | for a text whose last token is `RR73` BOTH payloads are acceptable: the special token (g15 32403, what the encoder gives) and the Maidenhead grid RR73 (g15 32373) | found in the smoke test on 5 controls outside the pilot sample: two RR73 controls decoded in the window only as the grid payload, and production prints both as `RR73`. The text is ambiguous; no other token is ambiguous with a grid |
| P-INVALID | no window point extracts (rc 0), or the armed decode returns a negative count | spec |
| P-CLEAN detail | pass-1 LLRs at the same point also decode BP-only; any suppression record within +-1 frequency bin (6.25 Hz) of the point | spec 4c.4 |
| P-WEAK detail | `ft8_refine_candidate` at the mapped point: refined position outside the window (|dF| > 6.25 Hz or |dT| > 0.16 s); sync score inside the pilot controls' P5 to P95 | spec amendment 3 |
| Armed point | the window's first hit nearest the centre if any, else the centre | spec: "the chosen point" |
| If SM-P1 fails | the targets are NOT probed; the pilot is reported (HK-026) | spec |
| If SM-P2 fires | the targets are probed anyway and reported with a flag "P-CLEAN not interpretable until the Architect rules" | spec says the Architect rules; probing costs minutes and is not an irreversible step |
| Self-checks before the pilot | Gray-inversion round trip through the DLL (encode, rebuild the codeword, BP-only recovers the same 77 bits); `IsPlausibleMessage` FALSE on 10 of 15 synthetic implausible Q-prefix texts, TRUE on 2 plausible ones; raw-output membership on 10 pilot controls; `ft8_get_decoder_params` read in-process (`osd_nhard_max` equals 24); all aborting | spec amendment 3 |
| Smoke test (disclosed) | before freezing, the machinery was run on 5 controls from OUTSIDE the seeded sample and 5 empty points on another seed, with fixed rough offsets: it found the RR73 rule and the CRC-field rule above. It is NOT the pilot and no pilot number was read | |

## Limits stated now

1. P-FILTER and every class refer to the native first-stage call; a target only the managed residual pass could produce is outside every class. 2. The product's own encoder builds the expected payload; encoding is not the stage under test. 3. The replay inside this process is again the two-stage call, not the daemon's early/final path; its SM-V2-style figures are reported again. 4. The plausibility filter is called with no grammar store (as the replay harness did and as (a) showed to be equivalent: SM-V2 99.91 %).

## Addendum (before any pilot number was read)

The first launch (12:16:00Z by the orchestrator's pin) was stopped by QA about a minute later, at the start of the replay and before any probe code ran, to add one aggregate counter the Architect asked for: how many pilot controls and how many P-CLEAN targets were accepted ONLY through the grid-RR73 alternative payload. Nothing else changed. The aborted artefact folder is kept as `artefacts/rr_2026-10-10_strong_miss_probe_ABORTED_counter-added` (its `pins.jsonl` records the aborted start). The relaunch's start pin is 12:17:55Z, from the committed harness (`12e43775`). (The commit message of `12e43775` says "about 3 minutes": the correct figure is about one.)

## Run

`python qa/rr-study/sub-feas/strong_miss_run.py --probe` (detached). Artefacts `artefacts/rr_2026-10-10_strong_miss_probe/`. Estimate: the replay about 80 minutes (11.2 s per cycle measured in (a)) plus the probe (minutes to under an hour; the extractor rebuilds a waterfall per call, to be measured).
