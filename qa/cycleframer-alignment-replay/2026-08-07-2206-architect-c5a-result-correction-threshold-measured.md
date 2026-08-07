# C.5a result — our BP/OSD corrects **13 of 174 bits (7.5% BER)**. The threshold is measured at last.

**Author:** Architect, 2026-08-07 (22:06 UTC, `date -u`, per HK-017). Repo `main` at `ef1ad46`.
**For:** QA and the Captain.
**Answers:** the question first asked in `2026-07-26-2030-architect-c2-phase2c-ruling.md` §5 and
never answered — *"how many bit errors can this codebase's BP+OSD actually correct?"* — re-issued as
C.5a in `2026-08-07-2117-architect-to-qa-rc-programme-closed-c5-correction-threshold.md` §5.1.
**Scripts:** `qa/cycleframer-alignment-replay/2026-08-07-c5a-correction-threshold/`
(`c5a_waterfall.py`, `c5a_waterfall_result.json`).

---

## 1. The number

| pattern | `k_50` | as BER | first zero | 100% up to |
|---|---:|---:|---:|---:|
| **clustered-within-symbol (PRIMARY)** | **13 / 174** | **7.47%** | k=21 (12.07%) | k=6 (3.45%) |
| uniform-random (secondary) | 12 / 174 | 6.90% | k=17 (9.77%) | k=6 (3.45%) |

**Instrument VALID** — k=0 decodes 204/204 on both arms, so the demodulator contributes no errors of
its own and exactly the injected bits reach LDPC/OSD. Shim **20260033** (shipped `main` config),
204 trials per k, SNR 20 dB, seed 20260807.

The waterfall (clustered): 100% through k=6, then 98.5 / 98.5 / 96.6 / 91.7 / 88.2 / 77.5 / **58.8**
/ 43.6 / 33.3 / 17.2 / 8.8 / 2.9 / 1.0 / 0.5% at k=7…20. A clean, monotone transition about 14 bits
wide, centred near k=13.

## 2. Why the spec's literal form was impossible, and what I did instead

`ft8_shim.h` exposes **no LLR entry point** — `ft8_decode_all` takes audio, and the other exports are
getters, `set_ap_bits`, `encode_message` and `set_decode_params`. So my 07-26 claim that this needs
*"no native change, no rebuild"* is **false as written**, and my own §5.1 said to stop and escalate
if so.

I did not escalate, because an equivalent route exists entirely through exports that do exist, and
it is better than the one I specced:

```
message -> pack -> +CRC -> LDPC encode      (qa/rr-study clean-room synth)
        -> 174-bit codeword
        -> FLIP k BITS                       <-- the injected damage
        -> assemble_symbols() -> 79 tones
        -> GFSK modulate, 12 kHz, SNR 20 dB
        -> ft8_decode_all()                  <-- our shipped decoder, untouched
        -> did the ORIGINAL message come back?
```

The synth already had every layer (`packing` → `crc` → `ldpc.encode_ldpc` → `symbols.assemble_symbols`
→ `modulator`), and `assemble_symbols` takes a **174-bit codeword** — exactly the injection point
C.5a needs. **This is the fourth time today that opening the repo answered a question I was about to
escalate or spec.**

**One implementation detail that is a trap, recorded so it isn't rediscovered:** the 12 signals in
each buffer must carry **distinct messages**. The shim dedups by message hash (`ft8_shim.c:1387`), so
the same message at 12 frequencies collapses to one decode and 11 trials silently read as failures.

## 3. The one direction this measurement is biased, and why that is the safe one

An injected bit flip becomes a **confidently wrong** soft LLR. A real weak-signal demodulation error
is an **uncertain** LLR near zero, which belief propagation finds easier to repair. So this is the
pessimistic case:

> **The true correction capability is at least `k_50 = 13`.**

That is the safe direction for C.5b. A candidate whose measured BER sits below this threshold was
*definitely* correctable, so any resulting "we dropped a correctable codeword" count is a **lower
bound** — it can under-state a defect, never invent one.

## 4. A prediction of mine that did not survive

My §5.1 designated clustered errors primary on the reasoning that *"a threshold derived from uniform
errors may be optimistic."* **The opposite is true:** uniform gives `k_50 = 12`, clustered gives 13,
and clustered is the more forgiving pattern consistently across the whole transition (77.5% vs 60.3%
at k=12, ~5 SE; 58.8% vs 47.1% at k=13, ~3.5 SE — a real difference, not noise).

Clustered stays primary, because *real demodulation errors are symbol-correlated* and that reasoning
is untouched. But the justification I gave for the choice was wrong, and the two thresholds differ in
a way that matters at the margin — see §5.

**That is the second prediction I have recorded in advance today that the measurement did not
support** (the first: C.5c would clear RC3). Both were recorded before the result, which is the only
reason either is checkable.

## 5. What this already implies for C.5b — and the margin that decides it

Against the populations captured in July (`2026-07-26-2030-…` §4.2):

| population | n | median BER | **min BER** |
|---|---:|---:|---:|
| matched-hit control | 171 | 2.9% | 0.0% |
| **THE 135** (score ≥10) | 126 | 44.0% | **6.9%** |
| THE 567 (score 5–9) | 279 | 49.4% | 16.1% |

Two readings, and they pull in opposite directions:

- **The bulk is far beyond reach.** A 44% median against a 7.5% threshold is not marginal — it is
  six times the correctable limit. THE 567's *minimum* (16.1%) is above the first-zero point
  (12.07%), so **not one member of THE 567 was correctable at these constants.** The "front-end
  limited" reading of that population is now measured rather than asserted.
- **The margin sits exactly where the two patterns disagree.** THE 135's minimum is **6.9%**, which
  is *above* the uniform threshold (6.90%) and *below* the clustered one (7.47%). The count of THE
  135 that qualifies as correctable is therefore acutely sensitive to which pattern governs — the
  gap between 12 and 13 bits is the whole question.

**Consequence for the gate:** C.5b must compute `f_corr` at **both** thresholds and report the pair.
If they straddle a row boundary, that is a ROW 0 (instrument) outcome, not a verdict — and given the
numbers above, straddling is a live possibility rather than a formality.

**Citation limit:** every BER figure in §5 is from the **July** 68-cycle corpus
(`20260725_live_run_1806`). RC1's 87.9% CANDIDATE_NOT_DECODED population is the **August** window and
its BER has never been measured. The threshold is a property of the decoder and transfers; the
populations do not, and must not be assumed to.

## 6. What this retires

- **My 18:30 §9 caveat of 2026-07-26 is retired.** The threshold is measured.
- **Every "≈50% BER means front-end limited" reading in this thread was against a number I invented.**
  Those readings are now *supported* — 44% and 49% are both far above 7.5% — but they were not
  supported when they were made, and the record should say so.
- **`k_50 = 13` is permanently useful.** Every future LLR, BER or decode-effort question in this
  project reads against it, and it cost twenty minutes of wall clock and no `src/` change.

---

*Per HK-015 this is the Architect reporting a result; the C.5 dev-task remains QA's to author. Per
HK-014 committed locally, no push, no merge. Per HK-011 nothing here touches `src/` — the shipped
`libft8.dll` was loaded read-only via ctypes and not rebuilt. Per NFR-021 every test message uses
Q-prefix synthetic callsigns (ITU-unallocated); no real callsign exists anywhere in this measurement.
Per HK-009 all output is ASCII.*
