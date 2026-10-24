# REVIEW: what WSJT-X 2.7.0 "Deep" does, against OpenWSFZ `main`, and the ranked levers that follow

- **From:** Architect  **To:** Captain (cc QA)  **Date:** 2026-10-24 12:35Z (`date -u` 12:30:59Z)
- **Asked by:** the Captain, 2026-10-24 ("start the Deep read").
- **Branch:** `arch/wsjtx-deep-read`, off `origin/main` `5a9667ee`. Docs only; `git diff --stat -- src/ native/` is empty.
- **This is a source read, not a measurement.** No run was made. Every "expected" below is a judgement, and none is a figure to cite.

## 0. Sources, and the licence rule

- **WSJT-X:**
  - The 2.7.0 source tree that `sol`'s reference binary was built from: `~/src/wsjtx-build/wsjtx-2.7.0/src/wsjtx/lib/`. It is identical to the build-tree copy (`diff -rq` empty), and `wsjtx.patch` is 0 bytes.
  - Files read: `ft8_decode.f90` (SHA-256 `529e23906d358061…`), `ft8/ft8b.f90` (`cf336d20fd30a2cc…`), `ft8/decode174_91.f90`, `ft8/osd174_91.f90` and `ft8/sync8.f90`.
  - The Windows station runs the official 2.7.0 build, the same version.
- **OpenWSFZ:** `origin/main` `5a9667ee`:
  - `src/OpenWSFZ.Ft8/Native/ft8_shim.c`, `native/ft8_lib_build/patched/ft8/decode.c` and `native/ft8_lib_vendor/refine/coherent_fallback.c`;
  - QA's Python reference `qa/rr-study/n2-coherent-llr-extractor/coherent_extract.py`.
- **Reference configuration:** both references run Deep (`NDepth=3`) with AP off (`FT8AP=false`).
- 🔒 **Licence (standing policy, 2026-08-11):** WSJT-X may be READ for method; not one line is copied, transliterated or ported. This document describes methods and parameters in prose only.
  - **One consequence, for the Captain:** `coherent_fallback.c` states "NO WSJT-X source was opened or consulted". Any lever below that is built from this read can no longer carry that line. It would say "method described from a reading of WSJT-X; no code copied". The policy allows that. Whether he wants the stricter clean-room line kept is his call (§4, decision D1).

## 1. What Deep does (WSJT-X 2.7.0, AP off)

**Decode stages in the slot:**
- Decodes run at three points: about 11.8 s (`nzhsym` 41), 13.5 s (47) and the final 15 s (50).
- Decodes from the early stages are subtracted from the audio before the later stages.
- In Deep only, that early subtraction also refines each signal's time offset before subtracting (`lrefinedt`). Normal does not.

**Passes:** up to three passes per stage. Each pass re-runs the candidate search on the audio as subtracted so far. Pass 2 runs only if pass 1 decoded something, and pass 3 only if pass 2 found something new. Every decode is subtracted in the time domain the moment it is found.

**Candidate search:**
- The sync threshold is 1.3 in Deep, against 1.6 in Normal, relative to the 40th-percentile sync level (2.0 at the 11.8 s stage).
- Up to 600 candidates per pass, near-duplicates merged, and candidates within 10 Hz of the RX frequency first.

**For every candidate, in this order:**
1. **Fine sync:** downconvert to 200 Hz. Time peak over ±50 ms in 5 ms steps, then frequency peak over ±2.5 Hz in 0.5 Hz steps, then correct the frequency, downconvert again and re-peak the time over ±20 ms.
2. **A hard sync check:** count how many of the 21 Costas tones are the strongest bin in their symbol. Give up if 6 or fewer.
3. **Four bit-metric sets from the same complex symbol spectra, each decoded separately.** The first set that yields a valid message wins:
   - (a) single-symbol;
   - (b) a **joint** metric over non-overlapping 2-symbol groups, maximising over all 64 tone pairs of the coherent sum;
   - (c) the same over 3-symbol groups and all 512 tone triples;
   - (d) single-symbol, normalised bit by bit.
4. **Each set goes through BP and then OSD.** In Deep, OSD runs twice. Its inputs are the **BP-accumulated beliefs after iterations 1 and 2**, not the channel values (`maxosd` = 2; OSD order setting 2, i.e. order 1 with one pre-processing stage).
   - **Pass 1 is the exception:** it runs at depth 2, so OSD runs once, on the channel values.
   - **Normal runs that way on every pass.**
5. **Acceptance:**
   - hard errors ≤ 36 against the channel decisions;
   - not the all-zero codeword;
   - a legal message type that unpacks;
   - reject if hard sync ≤ 10 and SNR < −24 dB.

**What Deep does NOT add on this station:**
- **AP decoding** is off.
- **The "a7" decode** of messages seen in the previous cycle is gated on the AP flag (`lft8apon`), so it never runs here.
- ⇒ **Neither is part of WSJT-X's lead over us.** This confirms the 2026-10-05 demotion of CQ-AP, now from source rather than inference.

## 2. The same steps in OpenWSFZ `main`

| step | WSJT-X Deep | OpenWSFZ `main` | gap? |
|---|---|---|---|
| Decode stages | 11.8 / 13.5 / 15 s, early decodes subtracted, Deep refines DT in that subtraction | early batch at 13.0 s + full batch; batch 2 = SUB-FEAS residual pass; batches 3–4 = coherent fallback | comparable; DT refinement of the early subtraction **not checked** |
| Passes | up to 3, candidates re-searched after time-domain subtraction | pass 0, pass 1 on the spectrogram-suppressed waterfall, then the SUB-FEAS residual pass | comparable in count |
| Candidates | ≤ 600/pass, threshold 1.3 | 140 (pass 0) / 200 (pass 1), `K_MIN_SCORE` 10 (another scale) | GAP-LOCATE: losses are **not** in candidate search; low priority |
| Fine sync | **every candidate**, ±50 ms / ±2.5 Hz | **primary path: none** (3.125 Hz / 0.08 s lattice). **Fallback:** ±0.12 s at 5 ms, ±2 Hz at 0.1 Hz, **only for candidates the primary decode failed** | mostly covered: a candidate the primary decodes needs no refinement. The residue is timing (batch 4 rather than 1) and maybe subtraction quality |
| Bit metrics | **4 sets, each decoded on its own, first valid wins** | **primary:** one non-coherent single-symbol set. **Fallback:** ONE set, "V3" = order-1 **plus the summed** order-2 and order-3 contributions over every adjacent pair or triple containing the symbol | 🔴 **different design.** QA's N2 report flagged V3's cumulative sum as "a documented judgement call … not dictated by the spec text" (`coherent_extract.py:50–58`). WSJT-X does not fuse: it uses joint group metrics and tries each one separately |
| Decoder in the fallback | BP + OSD on every set | **BP only** (`ft8_shim.c:2242`, osd_depth −1) | 🔴 **no OSD on the coherent path** |
| OSD input in the primary path | Deep: BP beliefs after iterations 1 and 2, two OSD calls (pass 1: channel values) | channel values, once (`decode.c:676–699`) | ours equals Normal / Deep pass 1. ⚠️ The comment at `decode.c:432–434` says this "corresponds to WSJT-X's zsave(:,1)" under `maxosd`=2. It does not: with `maxosd` > 0 that slot holds the iteration-1 BP belief. Fixing the comment is a Developer matter (HK-011) |
| Acceptance | hard errors ≤ 36 on every decode, plus the sync/SNR reject | BP: CRC + plausibility; OSD: `nhard` ≤ 24 + corr ≥ 0.10 | tuned separately (OSD-FIX TEST); no lever |
| AP / a7 | off on the reference | AP only in QSO context | not a gap against the reference |

**Not checked in this read** (named so nobody cites it as checked):
- whether our `osd_decode(…, 2, …)` matches WSJT-X's order-setting-2 parameters;
- the SUB-FEAS residual pass internals against WSJT-X's in-pass subtraction;
- whether our early-batch subtraction refines DT.

## 3. Ranked levers

The data behind the ranking:
- the coherent fallback is the biggest lever since subtraction, NET **+3.82 pp [3.44, 4.21]** (step-4 replay, night `20260922_2056`);
- the primary-path OSD adds little, **+0.082 pp** over OSD off at cap 24 (OSD-FIX TRAIN, descriptive).

| # | lever | why it might pay | how to test | cost | likelihood of a measurable gain |
|---|---|---|---|---|---|
| **L1** | **Fallback: decode several metric sets separately (WSJT-X's method) instead of one fused V3 set** | It sits on the path that just paid +3.82 pp. WSJT-X tries 4 sets; we try 1, built by a summing rule nobody ruled on. Any extra set gives a weak candidate another independent chance | **Offline, no build:** QA's Python extractor + the existing BP export `ft8_ldpc_decode_llrs` on the fallback's candidates from a recorded night. Arms: V3 (today) vs "any of" {order-1, joint-2, joint-3, normalised order-1} vs V3 ∪ those | spec + Python variants + a `sol` or PC replay ≈ 1–2 days; a build only if it pays | **medium**: the best-founded of the four |
| **L2** | **Fallback: add OSD after BP** on the coherent LLRs, with the `nhard` gate | WSJT-X runs OSD on every set; our fallback never does. Weak candidates are where OSD is meant to help | **Same offline arm:** the BP export takes `osd_depth`, so it is a second factor (BP vs BP+OSD), not a second experiment | adds a factor to L1 | **low–medium**: primary OSD gave only +0.08 pp, but the fallback's candidates are the weak ones |
| L3 | Primary OSD on BP-accumulated beliefs (Deep's `maxosd` = 2) instead of channel values | Deep's OSD input differs from ours | needs a `native/` change, then a replay | build + replay | **low**: all of primary OSD is worth +0.08 pp |
| L4 | Fine sync before the primary decode, for every candidate | WSJT-X does it | needs a build | large | **low for decode count** (the fallback already covers failures); maybe latency and subtraction quality |
| L5 | DT refinement in the early-batch subtraction | Deep-only in WSJT-X | check our code first (§2, not checked) | a read, then maybe a build | **low** |
| — | candidate count / threshold | — | — | — | GAP-LOCATE: not where losses sit |
| — | AP / a7 | — | — | — | not a gap against the reference (§1) |

⚠️ **Risk shared by L1 and L2:** trying more sets or adding OSD gives noise more chances to pass CRC. The 2026-08 shift-union (P3) "bought decodes but manufactured them" (`X_guard` 0.897). The arm needs the fallback's U′ instrument and a bar set before data (HK-038), as COH-FALLBACK had.

⚠️ **My own bias:** I tend to predict a "findable localised defect". L1 is one: a judgement call that differs from the reference method. I price it accordingly: **P(L1 alone gives NET ≥ +0.5 pp offline) = 0.40.** That is a registered guess, to be pre-registered properly in the spec.

## 4. For the Captain

**D1, the provenance line.** It matters only if L1/L2 is built later; it is not needed for an offline test.
- (a) **Policy as it stands:** this read may inform the method. The new code's header says "method described from a reading of WSJT-X; no code copied".
- (b) **Keep strict clean-room:** the L1 spec is written only from FT8's public protocol plus standard coherent-detection theory, with no reference to this document. That is slower, and it rests on a claim I can no longer make myself, since I have read the source.
- My recommendation is (a). It is what the licence policy already allows, and nothing gets copied either way.

**D2, the go for an L1+L2 offline spec**, `To: QA`, for `sol` or the PC. It needs no Developer build and no `src/`/`native/` change, and runs on a recorded 40 m night with the fallback's U′ watch.

*Architect. Docs only; `src/`/`native/` diff empty.*
