# D-001 B.2 — synthetic-waveform BER calibration: findings

**Author:** QA, 2026-07-26. **Executes:** `2026-07-26-2230-architect-sec6-redesign-ruling.md`
§5, §6, per `2026-07-26-b2-synthetic-calibration-task-spec.md`. QA-run directly, no
`src/`/native change — the exports used (shim ≥20260035) already ship, opt-in and default-off.

---

## 0. Verdict

**E = 5.7** (Arm B curve, the arm the ruling's own rule selects once the arms are shown to
diverge — see §3). This sits in the **1 ≤ E ≤ 15** band: **a real but small decode-path
residue**, not zero (front-end-limited would read <1) and not a material defect (>15 would
outrank §6.3). This lands close to the Architect's own stated prior (§7 of the 22:30 ruling: "E
in the region of 5–15... a real but small decode-path residue, not zero and not a material
defect") — recorded plainly, in the same spirit as that note's own request to state whether the
measurement confirms or overturns the prior.

## 1. Method, as specified

Two arms, 48 SNR levels each (broadband time-domain sweep knob, not a claim to match any other
dB convention in this codebase — see task spec §3), 8 repeats/level:

- **Arm A** — 8 isolated planted signals/buffer, ≥150 Hz apart, same `dt`, shared per-buffer AWGN.
- **Arm B** — 4 co-channel pairs/buffer, Δf ∈ {0, 3, 7, 15} Hz, same `dt` within a pair.

Decoded through the unmodified shipped path (`ft8_set_decode_params(10, 0.10, 60)`,
`K_MAX_CANDIDATES`=140), with `ft8_set_candidate_diag_capture(1)` +
`ft8_set_candidate_diag_llr_capture(1)` enabled. True codewords via `ft8_encode_message` +
verified Gray/sync stripping. Hard-decision BER via the empirically-established sign convention
(`hd = 1 if llr > 0 else 0`) — reused, not re-derived, from `c2_phase2c_ber_measurement.py`.

**A methodological correction made during this session, recorded rather than silently fixed:**
the first pass hard-clipped the synthesised buffer to [-1, 1] before decoding. Checking the
`clipped`-sample counter showed this was **not cosmetic** — median 11% of samples clipped across
all located measurements, rising to a median 41% inside the BER 5–20% transition region that the
curve's shape (and therefore `E`) depends on, because a fixed per-signal amplitude cannot keep
headroom against a noise sweep spanning tens of dB. Hard-clipping is itself a nonlinear channel,
which conflicts with the ruling's own design principle ("let the channel generate the LLRs," not
an implementer's choice) — the same class of self-inflicted defect this whole B.2 redesign exists
to avoid at the *macro* level (§6.1's free parameter), just recurring in miniature at the
synthesis level. **Fixed** by replacing the per-sample clip with a global linear rescale
(`buf *= 0.9 / peak` whenever the pre-scale peak exceeds 0.9) — this changes the SNR ratio not at
all (both signal and noise are scaled together) and produces **zero** clipped samples in the
reported run. Re-running end to end after the fix moved `E` from 5.97 (clipped) to 5.69 (clean) —
a ~5% shift, not a reversal, but the clean run is the one reported and trusted; the clipped run is
not used anywhere below.

## 2. Self-check

Arm A's own curve is the sanity check the ruling's design implies rather than states outright:
**P(decode) = 100.0% at BER 0.0–2.5%** (n=1653) and falls to **~0% by BER 20%** — the physically
required shape, obtained with no free parameter chosen by the implementer. The clean transition
(monotonic decline from 100% to single digits between BER 7.5% and 17.5%) is itself evidence the
synthesis → decode → LLR-capture → hard-decision pipeline is behaving as a real channel should,
independent of the CPFSK-vs-GFSK caveat below.

## 3. Arm A vs Arm B: they diverge — read as a finding, not noise

| BER bin | Arm A P(decode) | Arm B P(decode) |
|---|---:|---:|
| 7.5–10.0% | 89.8% | 97.2% |
| 10.0–12.5% | 58.4% | 72.5% |
| 12.5–15.0% | 11.0% | 34.3% |
| 15.0–17.5% | 2.9% | 11.6% |

**Arm B reads systematically *higher* P(decode) than Arm A at the same measured hard-decision
BER**, across the whole transition region — the opposite direction from the naive "co-channel
should be strictly harder" expectation, and exactly the divergence the ruling's §5 flagged as
possible ("if they diverge... that is a finding in its own right"). Two candidate mechanisms,
both about **which candidates get located at all**, not about decode quality once located:

1. **Location-rate selection bias.** Per-Δf location rates: Δf=15 Hz 50.5%, Δf=7 Hz 87.6%, Δf=3 Hz
   94.3%, Δf=0 Hz 100.0% — rising as the pair gets *closer* together, the opposite of what a
   naive "closer = harder to see" story predicts. The Δf=0 number is the tell: **at Δf=0 the two
   planted messages sit at the identical frequency**, so the ±10 Hz/±0.5 s matcher used to attach
   a candidate to each planted signal necessarily returns the *same* candidate object for both —
   "100% located" there is a matching artefact, not two independently-detected signals. This is a
   real limitation of this session's matching approach for the Δf=0 slice specifically, flagged
   rather than resolved (see §5). For Δf ∈ {3, 7, 15}, the falling location rate as Δf *widens* is
   the more physically legible reading: at small Δf the decoder's candidate search sometimes
   collapses two close signals into a shared detection (inflating apparent location success in a
   way that also — mechanically — only keeps candidates whose combined energy was strong enough to
   register, a survivorship filter that skews the *located* subset toward higher decodability at a
   given raw BER).
2. **This is exactly the mechanism the 22:30 ruling anticipated** (§5, point 4): "candidates too
   weak to be located simply do not contribute — which is the front-end limit measuring itself,
   and is correct." The located-conditioned population in Arm B is not the same population as Arm
   A's at a given BER; the divergence is a real, structural property of the co-channel condition,
   not a bug in this session's numbers.

**Consequence, per the ruling's own fixed-in-advance rule:** since the arms diverge, `E` is
computed from **Arm B**, not Arm A (§6 of the ruling). Reported for comparison only: `E` from
Arm A's curve = 4.45 — close to Arm B's 5.69, so this particular divergence, while real and worth
recording, does not swing the reading-rule band (both land in 1–15).

## 4. E and the interpretability numbers

- **E (Arm B) = 5.69.** Falls in the ruling's **1 ≤ E ≤ 15** band.
- **E (Arm A, comparison only) = 4.45.**
- **B10 = 17.2%, B50 = 43.7%, B90 = 52.3%, N(BER ≤ B50) = 63** — THE 135's own measured BER
  distribution (n=126 of 135; 9 messages' true codeword could not be re-encoded, same known
  exclusion as every prior session touching this population). These are **not independently
  re-derived** here — `measure_population`/`compute_135_population` from
  `c2_phase2c_ber_measurement.py` were imported and called directly, per the task spec's "reused,
  not re-derived" instruction, so this is confirmation the reused call still runs cleanly inside a
  new harness, not a fresh corroboration. For the record, these numbers match the independently
  computed 21:10 notification's deciles closely (17.2%/44.0%/52.5% there) because they come from
  literally the same underlying capture and the same population-selection code.

**Reading, per the ruling's §6.1 table (1–15 row):** *"a real but small decode-path residue.
Chase it if the cause is a single constant or gate; otherwise fold the count into §6.3's framing
and proceed. Captain's call, with a number."* That number is **5.69, of 135** (≈4.2%) — well
short of the >15 threshold that would outrank §6.3, and per the ruling's own conservative-in-the-
safe-direction framing (§6, three bullets), a lower bound: the true decode-path residue may be
somewhat larger than 5.69, not smaller.

## 5. Honest caveats

- **CPFSK vs GFSK** (ruling §9, unchanged): the synthesiser is phase-continuous FSK; WSJT-X
  transmits GFSK. Arm A is unaffected by this in any way visible from the likelihood extraction
  (non-coherent per-tone-bin power); Arm B's co-channel adjacent-splatter behaviour is more
  exposed and this caveat carries forward unresolved.
- **Δf=0's location-rate is a matching artefact, not a measurement of Δf=0's real detectability**
  (§3). It does not change the E reading (Δf=0 is one quarter of Arm B's pooled population and the
  overall E stayed inside the same band under both the clipped and clean runs), but a future
  session wanting a clean per-Δf curve at Δf=0 specifically would need a different attribution
  rule (e.g., treat a shared-candidate match as "one located, one not," rather than counting both).
- **The clipping catch (§1)** is disclosed in full rather than only reporting the corrected run,
  per this thread's own standing practice of recording self-corrections at the same weight as
  findings. The ~5% shift in E between the clipped and clean runs is small relative to the
  1–15 band's width, but the clean run is the only one trusted for the verdict.
- **SNR is an internal sweep knob**, not calibrated against WSJT-X's own reported-SNR dB
  convention or against this codebase's own SNR formula (`ft8_shim.h`'s
  `signal_db - noise_floor_db - 26.5`) — the x-axis that matters for this measurement is BER, and
  the knob's only job was to traverse it, which it did (BER 0% → >50% across the swept range).
- **Synthetic ≠ corpus** (ruling §9, unchanged): calibrates what BP+OSD can correct on synthetic
  signals in synthesised interference; THE 135 came off a real antenna with real QRM, drift, and
  multipath.
- **One session, one arm design, no second corpus.** Unchanged from every note in this thread.

## 6. Cross-references

- `2026-07-26-2230-architect-sec6-redesign-ruling.md` §5, §6 — design and reading rule executed
  here, unchanged.
- `2026-07-26-b2-synthetic-calibration-task-spec.md` — pieces reused, synthesis parameters.
- `b2_synthetic_calibration.py` — driver; raw per-buffer/candidate data under git-ignored
  `artefacts/d001_b2_synthetic_calibration/` (NFR-021).
- `c2_phase2c_ber_measurement.py` — THE 135 population/measurement, imported not re-derived.
- `c2_phase2c_gray_sync_roundtrip_verify.py` — Gray/sync stripping this harness's
  `true_codeword()` mirrors.
- `2026-07-26-2110-qa-to-architect-sec6-distribution-reread.md` §3.1 — THE 135 deciles this
  session's B10/B50/B90 match (same underlying data, same code, called from a new harness).
