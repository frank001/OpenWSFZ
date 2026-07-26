# D-001: Architect ruling on the Sec.6 distribution re-read — items 1/2/4 accepted; the export is declined because §6.1 was **ill-posed**, not merely blocked

**Author:** Architect, 2026-07-26 (22:30). **For:** the Captain and QA.
**Answers:** `2026-07-26-2110-qa-to-architect-sec6-distribution-reread.md` §2.1 — QA's one open question.
**Revises:** `2026-07-26-2030-architect-c2-phase2c-ruling.md` §6.1 (replaced outright) and §6.3
(re-specified onto a better statistic). §1–§5, §7, §8, §9 of that note stand unchanged.

QA stopped at a native-code boundary and asked rather than routing around it. That was correct under
HK-011, and it was also correct on the merits: the reimplementation shortcut QA explicitly refused —
"a second decoder that happens to share a name with the first" — would have produced a number that
looked like a calibration and was not one. The refusal is the right instinct and I want it on record
as such.

**But the export is declined, and not on cost.** Checking QA's claim sent me back to my own §6.1
design, and the design has a free parameter I never specified that would have determined the answer.
The block did not stop a good experiment from running. It stopped a bad one.

---

## 1. Short answer

1. **§6.2 items 1, 2 and 4: accepted in full.** The reproduction of my §4.1 table before trusting
   anything new is the correct discipline and I am treating the numbers as sound. §2.
2. **QA's §2 factual claim is confirmed.** `bp_decode`/`osd_decode` are `static` in
   `patched/ft8/decode.c`; no export takes an LLR array. I verified this against `ft8_shim.h` and
   `decode.c` myself rather than accepting it. §3.
3. **The proposed `ft8_decode_llr174_diag` export is declined — because §6.1 is ill-posed.**
   "Inject *k* bit errors" does not determine a decode outcome. LLR *magnitude* does, and I never
   specified it. Any threshold that bench produced would have been an artefact of an implementer's
   free choice. §4.
4. **§6.1 is replaced by a synthetic-waveform sweep through the unmodified production path**, using
   exports that already ship. No native change, no HK-011 exposure, and it measures a **better**
   quantity on the **same instrument** as the corpus numbers. §5.
5. **§6.3's reading rule is re-specified onto an expected-count estimator `E`** instead of a
   threshold count — fixed in advance, before any number exists, and robust to exactly the matching
   artefact QA measured at 12.9%. §6.
6. **Item 4 stays open.** No verdict, and my own prior is recorded in §7 so it can be falsified.

## 2. What I accept from the delivered work

- **The self-check.** Reproducing my §4.1 table exactly — all three arms, all four statistics —
  before reporting anything new is what makes the rest of §3 usable. This is the third session in
  this thread to self-check before trusting, and it is now the thread's established standard.
- **§3.1 deciles, §3.2 the 12.9% control mismatch rate, §3.3/§3.4 the score and LLR-magnitude
  correlations.** All accepted as measurements.
- **§3.5's framing.** Reporting 8/126 and 26/126 as *explicitly not* item 3's answer, against bands
  QA correctly labelled non-calibrated, is the right way to report a number that is suggestive and
  not load-bearing. It did not get smuggled into a verdict.

### 2.1 Two readings the delivered data supports that were not drawn

**First — THE 135 splits roughly in half, and the halves differ in kind.** THE 567's p10 is 43.7%,
so 90% of that population sits above 43.7% BER. Reading THE 135's deciles against that line: its p40
is 40.1% and p50 is 44.0%, so **roughly 48% of THE 135 — about 60 candidates — sits cleaner than 90%
of the noise-like population.** The other half is statistically indistinguishable from THE 567.

That sharpens my §4.5 considerably. "THE 135 is not uniformly front-end limited" is right but vague.
The precise statement the deciles support is: **THE 135 ≈ a 567-like half plus a distinctly better
half.** The upper half needs no further work — it is front-end limited on the same evidence THE 567
is. Everything that follows is about the lower half, and that is where `E` in §6 does its work.

**Second — §3.4 is independent corroboration of item 3's closure.** `postnorm_mean_abs_llr` correlates
with BER at r = −0.135, essentially nothing. Shrinkage rescales magnitude. A quantity that barely
tracks decode quality is not a quantity worth rescaling. Part A closed item 3 by direct measurement
and needs no help — but this is a second, independent, mechanistically different arrival at the same
place, and it was captured for another purpose entirely. That is worth recording.

**Third, and a caveat rather than a finding — THE 135's mismatch rate is probably worse than 12.9%.**
The control arm matches candidates to messages *we decoded*, so a true candidate provably existed.
THE 135 matches candidates to messages *we missed*. Where our front end never located the true
signal, the ±10 Hz/±0.5 s match cannot return the right candidate; it returns a neighbour. So 12.9%
is a floor for THE 135's contamination, not an estimate of it. This cuts the same direction as my
§4.3: the upper tail is the untrustworthy part, the low tail is the artefact-proof part. §6's
estimator is chosen so this barely matters.

## 3. QA's block is confirmed — I checked it rather than accepting it

`bp_decode` and `osd_decode` are `static` in `native/ft8_lib_build/patched/ft8/decode.c`, called only
from `ftx_decode_candidate` / `ftx_decode_candidate_ap`, which take `(const ftx_waterfall_t*, const
ftx_candidate_t*)` — a waterfall and a candidate, never a caller-supplied LLR array. I read
`ft8_shim.h`'s full export list and the `decode.c` fallback block directly. QA's §2 is accurate in
every particular, including that `ft8_encode_message` is forward-only.

So §6.1 as written could not run without a new export. QA is right about that. It is the next
paragraph that changes the disposition.

## 4. Ruling — the export is declined, because §6.1 had a hidden free parameter

§6.1 said: inject *k* random bit errors for k = 0…45, run our own BP/OSD path, plot success against
*k*. **`bp_decode` does not take bits. It takes 174 floats.** To "inject k bit errors" you must
construct an LLR array whose hard decisions are wrong in k positions — and you must choose *how
wrong*. That choice is not a detail. It is the entire answer:

| the k erroneous bits carry… | what BP+OSD does |
|---|---|
| small \|LLR\| (barely-wrong bits) | corrects them almost trivially; threshold reads very high |
| large \|LLR\| (confidently-wrong bits) | fails at single-digit k; threshold reads very low |

The same k, the same code, the same constants, and a threshold that can be moved across most of its
plausible range by a parameter I never mentioned. **A curve from that bench would have measured the
implementer's choice of magnitude distribution, wearing the costume of a decoder property.** It would
then have been fed into §6.3's bands and turned into a verdict on whether we have a defect.

This is the same class of error as §4.1 — specifying a measurement against a reference I invented —
and I made it in the very section written to fix §4.1. Authorising a native export, a shim bump to
20260036, and a Linux `.so` rebuild to run an ill-posed bench would have compounded it with real
merge risk.

**QA's block did not delay the calibration. It caught it.** I am recording that with the same weight
I gave the sign-convention finding at 20:30 §2, because it is the same kind of save: a discipline
gate catching a defect that would otherwise have shipped silently into a downstream number.

### 4.1 Why the export is not authorised "anyway, since it's cheap"

It is genuinely cheap and well-shaped — QA's sketch is a faithful extraction of decode.c:707–730, the
risk profile is the one used four times already in this thread, and if I needed it I would authorise
it. I do not need it. §5 measures the same property with better fidelity using exports that already
exist, so the export would buy a strictly worse experiment at a strictly higher price. HK-011 costs a
Developer session, a Captain diff review, and a `.so` rebuild; those are worth spending on a
measurement we cannot otherwise get, and this is not one.

If §5's design fails in practice for a reason we cannot see yet, the export comes back on the table —
and QA's sketch is the shape I would authorise. It is not rejected, it is not needed.

## 5. Replacement for §6.1 — calibrate through the production path, on synthetic waveforms

**The fix to the free parameter is to stop choosing the LLRs and let the channel generate them.**
Synthesise a signal, add noise, decode it with the real decoder, and read out both what the LLRs
actually were and whether it actually decoded. Magnitude, sign, and error clustering then come out
jointly physical and mutually consistent, because they came from a channel rather than from a choice.

Every piece already exists and has already been exercised in this thread:

| piece | already exists as |
|---|---|
| message → 79 tones | `ft8_encode_message` (shim 20260017) |
| tones → true 174-bit codeword | `recover_codeword()` in `c2_phase2c_gray_sync_roundtrip_verify.py`, verified 6/6 by CRC-14 **and** all 83 parity rows |
| tones → 12 kHz PCM | trivial CPFSK in numpy; `Ft8AudioSynthesiser.cs` is the managed reference (48 kHz, decimate 4:1) |
| per-candidate raw LLRs | `ft8_set_candidate_diag_llr_capture` + `ft8_get_last_candidate_llr` (shim 20260035) |
| per-candidate decoded flag, score, freq, dt | `ft8_get_last_candidate_diag` (shim 20260034) |
| BER from raw LLRs vs true codeword | `c2_phase2c_ber_measurement.py`, sign convention already found and fixed |

**Method.** Plant 8–10 synthetic Q-prefix signals per 15-second buffer at known freq/dt, ≥150 Hz
apart, each at its own SNR; add AWGN; call `ft8_decode_all` at the **shipped** configuration
(`ft8_set_decode_params(10, 0.10f, 60)`, `K_MAX_CANDIDATES` 140, no constant swaps); for each planted
signal read its candidate's 174 raw LLRs and its `decoded` flag. Sweep SNR downward until BER spans
0% to ≳55%. Bin by measured BER and plot **P(decode | BER)** with Wilson intervals.

**Two arms, and the comparison between them is itself a result:**

- **Arm A — isolated signal in AWGN.** The clean calibration.
- **Arm B — co-channel.** Two overlapping signals at Δf ∈ {0, 3, 7, 15} Hz at similar SNR: the D-001
  condition itself, and the condition THE 135 actually live in.

If A and B produce the same curve, BER is a sufficient statistic for correctability and the threshold
is a property of the code. If they diverge, BER alone does not determine decodability, §6's count
must be computed from **Arm B**, and that is a finding in its own right — it would mean my entire
band framing, corrected once already, is still keyed on an insufficient statistic.

**Five things this gets right that §6.1 did not:**

1. **No free parameter.** The channel sets the LLR magnitudes.
2. **Symbol-correlated errors by construction** — the caveat §6.1 listed as an optional second arm.
3. **Same instrument on both sides.** The calibration BER and the corpus BER are computed by the same
   script from the same export. §6.1's k-injection would have produced a curve on a different axis
   from the corpus numbers it was meant to be read against, and nothing would have flagged that.
4. **Same conditioning.** The curve is conditioned on *candidate located*, exactly as THE 135 is
   (score ≥ 10, present in the candidate array). Planted signals too weak to be located simply do not
   contribute — which is the front-end limit measuring itself, and is correct.
5. **A free check on §3.2.** The planted-signal match rate at known ground truth is an independent
   measurement of the ±10 Hz/±0.5 s matcher's artefact rate, against QA's 12.9%.

**Cost.** No native change, no rebuild, no corpus, no live audio, no NFR-021 exposure. It does need
decode runs, which my 20:30 §6 wrongly promised it would not — synthetic only, ~250 buffers ≈ 20
minutes of compute for ~2000 measured candidates. I would rather spend 20 minutes of synthetic decode
than a Developer session on a bench that cannot answer the question.

**Sample-size target:** ≥40 measured candidates per 2.5% BER bin through the transition region. If
the transition proves narrow, concentrate the SNR sweep there on a second pass rather than widening
the bins.

## 6. §6.3 re-specified — fixed in advance, before any number exists

The threshold count I specified at 20:30 discretises a continuous curve at an arbitrary point and is
sensitive to exactly the artefact QA measured. Replace it with the estimator the curve makes
available:

> **E = Σ over THE 135 of P(decode | BER_i)**, using Arm B's curve (Arm A's if the arms agree).

**E is the expected number of THE 135 that our own decoder should have recovered given the LLR
quality we actually presented it with.** It is the number the Captain needs, and it has three
properties the threshold count lacks:

- **No arbitrary cut point.** Every candidate contributes its own probability.
- **Artefact-robust.** A mismatched candidate reads ≈50% BER, where P(decode) ≈ 0, so it contributes
  ≈0 to E. The contamination QA quantified at ≥12.9% therefore barely moves the estimator — it is
  concentrated exactly where E is insensitive.
- **Conservative in the safe direction.** Both known biases (matching artefact, and any true candidate
  our front end never located) push measured BER *up*, which pushes E *down*. **E is a lower bound on
  the decode-path residue.** A large E is trustworthy; a small E could be suppression. §6.1's row-0
  reading therefore needs more care than the others, and I say so before seeing it.

Report alongside E, for interpretability, not for the verdict: B50/B10/B90 from the curve, and
N = |{THE 135 : BER ≤ B50}|.

### 6.1 The reading rule

| E (expected recoverable, of 135) | reading | next |
|---:|---|---|
| **< 1** | nothing we located was ever correctable — front-end limited, as the median suggested | §4's correction is noted and overruled by measurement. §6.3 goes to the Captain with N = the front-end-limited count as its denominator. **Caveat: E is a lower bound; state the artefact-suppression risk explicitly rather than reading 0 as proof.** |
| **1 – 15** | a real but small decode-path residue | Chase it if the cause is a single constant or gate; otherwise fold the count into §6.3's framing and proceed. Captain's call, with a number. |
| **> 15** | we are dropping correctable codewords at material scale | **Stop. This is a defect, not a structural gap**, and it outranks §6.3. Item 4 re-decomposes around it. |

Bands unchanged from 20:30 §6.3 deliberately — I am changing the *statistic* because the old one was
poorly chosen, not the thresholds, which would be moving the goalposts. Same standing invitation to
the Captain to set them differently, provided it is done now rather than after.

## 7. My prior, on record before the measurement

Having just been wrong once about reading a distribution, I am stating my expectation in advance so
it can be falsified rather than quietly confirmed.

The code is (174, 91), rate ≈ 0.523. The hard-decision BSC capacity limit for that rate is
1 − H(p) ≥ 0.523, i.e. **p ≈ 10.2%** — no decoder using only hard decisions can go beyond it. Soft
decoding beats that, because hard-decision BER discards the magnitude information BP actually uses,
so I expect **B50 somewhere in 12–20%**, and I would be surprised by anything above 25%.

Against QA's deciles — THE 135's p10 is 17.2%, and 8/126 sit at ≤15% — that puts **E in the region of
5–15, i.e. the middle row**. Explicitly: I expect a real but small decode-path residue, not zero and
not a material defect.

**This is a prior, not a derivation, and it is exactly the kind of invented reference §4.1 caught me
using.** It must not substitute for the measurement or influence how the measurement is read. It is
here so that if the answer lands where I predicted, the Captain knows I predicted it; and if E comes
back at 40, the record shows the measurement overturned me rather than confirming me.

## 8. What this does not settle

- **Item 4 stays open — active, decomposing.** Decomposition table at 20:30 §8 is unchanged.
- **§6.3 (how much of WSJT-X's decoder to reimplement) stays parked**, one step further along, still
  not put to the Captain.
- **§9's `libft8.dll` size question is untouched and still the Captain's**, still my view that an
  unexplained binary delta is a merge blocker regardless of benignity.
- **`pre_merge_check.py` not run** — the Captain's trigger per HK-006, not mine and not QA's.
- **Nothing here says this branch is ready for anything.**

## 9. Honest caveats

- **I have now corrected my own instructions twice in consecutive notes** (§4.1's band statistic at
  20:30, §6.1's bench design here). Both corrections were prompted by someone else's work — QA's
  distribution report and QA's block respectively — not by my own review. The pattern is that I
  specify measurements against references I have not calibrated. §5 is an attempt to fix the pattern
  rather than the instance: it keys every number to a physically generated reference and to the same
  instrument used on the corpus.
- **CPFSK vs GFSK.** The synthesiser is phase-continuous FSK; WSJT-X transmits GFSK. The decoder's
  likelihood extraction is non-coherent per-tone-bin power, so Arm A is unaffected in any way I can
  see. **Arm B is more exposed** — adjacent-channel splatter differs between the two modulations, and
  Δf = 3 Hz co-channel behaviour could plausibly depend on it. If Arm B's curve is load-bearing for E,
  this caveat needs stating in the findings; it is not a reason to withhold the measurement.
- **Synthetic ≠ corpus.** The calibration measures what BP+OSD can correct on synthetic signals in
  synthesised interference. THE 135 came off a real antenna with real QRM, drift, and multipath. Arm B
  narrows that gap; it does not close it.
- **E is a lower bound, not an estimate**, per §6. I have designed the estimator to fail safe and I
  should be held to reading it that way, especially if it comes back near zero and agrees with what I
  originally expected.
- **One 21-minute session, one device, one band.** Unchanged from every prior note in this thread.

## 10. Cross-references

- `2026-07-26-2110-qa-to-architect-sec6-distribution-reread.md` — the notification this answers; §2
  (the block, confirmed), §2.1 (the export, declined), §3.1–§3.5 (accepted).
- `2026-07-26-2030-architect-c2-phase2c-ruling.md` — §6.1 replaced by §5 here; §6.3 re-specified by §6
  here; §1–§5, §7, §8, §9 stand.
- `native/ft8_lib_build/patched/ft8/decode.c` — `bp_decode`/`osd_decode` `static`, reached only via
  `ftx_decode_candidate`; the fallback block at ~707–730 QA's proposed export would have extracted.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.h` — export list checked; 20260034/20260035 capture exports are
  what §5 builds on.
- `qa/cycleframer-alignment-replay/c2_phase2c_gray_sync_roundtrip_verify.py` — `recover_codeword()`,
  the verified tones→174-bit path §5 depends on.
- `qa/cycleframer-alignment-replay/c2_phase2c_ber_measurement.py` — the BER instrument to reuse
  unchanged on both the synthetic and corpus sides.
- `src/OpenWSFZ.Ft8/Ft8AudioSynthesiser.cs` — 48 kHz CPFSK reference for §5's synthesis.

---

*Per HK-015 §5 and §6 are a recommendation for QA to scope into a dev-task; `dev-tasks/` remains QA's
to author. Per HK-011 no `src/` or native change is authorised by this note — the proposed export is
declined, not deferred. Per HK-014 nothing is pushed or merged. §6.3's product decision remains the
Captain's and is still not being put to them.*
