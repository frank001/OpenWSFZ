# D-001 R.5 — the hybrid ladder, QA task spec

**Author:** QA, 2026-07-27 (18:36 UTC, `date -u`, per HK-017). **Operationalises:**
`2026-07-27-1822-architect-r5-hybrid-ladder-design.md` in full — the design fixes the question,
the five rungs, the reading rule and the stop rules; several construction details are left open
("one property at a time," no numeric band/SNR-reference/notching parameters) and are fixed here,
before any buffer is generated, same convention as every prior arm's task spec in this thread.
**QA-runnable directly: no `src`/native change (HK-011 does not apply), no push/merge (HK-014),
no `pre_merge_check.py` (HK-006), no `dev-tasks/` entry** — same posture as R.1/R.1b/R.4/R.4b.

---

## 1. Question (unchanged from the design)

Which property of real audio, added to a synthetic buffer, collapses decode rate from ~100% to
~61%? Five rungs interpolate between the two measured endpoints; the rung at which P(decode)
collapses names the property.

## 2. Operational choices this spec fixes

### 2.1 The new stop rule from the 15:22 ruling applies here first

The 15:22 R.4 ruling (§2) established: *"every planted signal must lie wholly inside the
intersection of both decoders' search bands ... the usable ceiling is ~2950 Hz, not 3000"* and
*"a flat SNR-independent offset between two decode curves is to be treated as a suspected harness
defect until excluded, never as curve shape."* R.5's own design (§0 self-reference) inherits this
directly since rung 0 reuses R.4's geometry. **Fixed here: the in-band planting window for every
synthetic rung (0-3) is `[200, 2950]` Hz for a signal's *base* frequency** (an FT8 signal occupies
`base .. base+43.75` Hz for the 8-tone alphabet used throughout this study, so 2950 keeps the
occupied ceiling at 2993.75, comfortably inside the 3000 Hz search band on both decoders — jt9's
default range is wider still). **This replaces R.4's original 8-slot layout (300-3300 Hz, which
produced the slot-7 defect) with an 8-slot layout spanning 200-2950 Hz for rung 0**, so R.5 does
not re-import the defect the 15:22 ruling caught.

### 2.2 Cycle selection

20 of corpus 1's 68 matched cycles (`b1.OURS_WAV_DIR` / `b1.WSJTX_WAV_DIR`), **selected by even
stride across the sorted cycle-timestamp list** (`numpy.linspace(0, 67, 20)`, rounded, deduplicated)
rather than the first 20 — the first 20 are all early-session and would bias density/SNR toward
whatever propagation looked like at the start of the run. Stride sampling spans the full session.
Cycle IDs are stated in the findings' persisted manifest, not printed to console (NFR-021 is not
implicated by timestamps alone, but the convention throughout this thread has been aggregate/count
reporting only).

### 2.3 Rung 0 — synthetic isolated baseline

8 slots, `200-2950` Hz range (slot width 343.75 Hz, message base frequency jittered `+20..+slot_width-40`
Hz inside its slot, same jitter convention as B.2/R.4), fixed `dt=0.6`, one buffer per selected
cycle (20 buffers, up to 160 planted-signal opportunities). **Reference SNR = -14 dB** on B.2's
`snr_db` scale — R.4's warmest swept grid point, already shown to give near-ceiling performance
(87.5% pre-correction, 100% once the out-of-band slot is excluded, R.4 findings §2). Uniform
`AMPLITUDE=0.15` (B.2's constant), synthetic AWGN via B.2's `noise_std = (AMPLITUDE/sqrt(2)) /
10**(snr_db/20)` formula. This `noise_std` at `snr_db=-14` is the **fixed reference noise floor**
carried into rungs 1 and 2 (§2.5).

**Self-check target:** the design says rung 0 "must reproduce 147/147." R.5 does not regenerate
R.4's exact 51-buffer/408-signal grid (that number belongs to R.4's own self-check, already passed
and on record) — it generates a *new*, smaller, differently-seeded set of 20 buffers at the same
reference condition. **Operational translation: rung 0's Wilson lower CI bound must be >= 90%
(effectively "no material miss population at a condition already shown to be ~100%"), both
decoders.** If it is not, that is a harness self-check failure per the design's own stop rule,
reported as such, and nothing downstream is trusted.

### 2.4 Rungs 1-3 — real layout from each cycle's WSJT-X decode list

For each selected cycle, read the **live WSJT-X `ALL.TXT`** rows for that cycle (`b1.parse_all_txt`,
restricted to that `ts`) — `(freq, dt, snr)` per message, already present in the existing corpus
data, no new capture. Two filters, applied identically to rungs 1-3, counts reported per cycle:

- **Band filter** (§2.1): drop any message whose `freq` is outside `[200, 2950]`.
- **Timing filter:** a planted signal needs `dt in [0, 2.3667)` s (12.64 s signal in a 15 s buffer,
  `(BUFFER_SAMPLES - SIG_SAMPLES) / SR = 2.3667`). Real WSJT-X `dt` values are centred near 0 and
  range roughly -2.4..+2.4 s in this corpus — wider than the window allows for the full spread in a
  single cycle. **Applied per cycle, not per message** (preserves relative timing geometry, the
  thing rung 1 is testing): `shift = 0.5 - min(dt in that cycle's band-filtered set)`, applied to
  every message in that cycle; any message whose shifted `dt > 2.30` (0.067 s safety margin) is then
  dropped, count reported. This is a QA construction choice the design does not fix numerically,
  flagged per this thread's standing convention.

The **surviving (freq, dt) list per cycle is the fixed layout shared by rungs 1, 2 and 3** — same
positions, so a collapse appearing at rung 2 but not rung 1 is attributable to amplitude, not to a
different population.

- **Rung 1** (population geometry only): synthetic Q-call messages planted at the real (freq, dt)
  layout, **uniform `AMPLITUDE=0.15`**, **same reference `noise_std` as rung 0** (`snr_db=-14`
  pinned, synthetic AWGN). Density and layout are the only things that change versus rung 0.
- **Rung 2** (plus real amplitude distribution): same layout, **per-message amplitude set from that
  message's own WSJT-X-reported SNR**, via the inverse of B.2's formula:
  `amplitude = noise_std_ref * sqrt(2) * 10**(snr_db/20)`, using the **same fixed `noise_std_ref`
  from §2.3** (so only signal level varies between rung 1 and rung 2, not the noise floor) and the
  message's real `snr` field taken directly off `ALL.TXT` (WSJT-X's own estimator, on WSJT-X's own
  scale — the caveat every prior arm in this thread has carried is carried here too, §5). Same
  synthetic AWGN at `noise_std_ref`.
- **Rung 3** (plus the real noise environment): same layout and the **same per-message amplitudes as
  rung 2** — the manipulation under test is the background, not the signal — but **background is the
  real cycle's own captured audio with its own decoded signals spectrally notched out** (§2.6), and
  **re-scaled per buffer**: rung 3's per-message amplitude uses `noise_std_real` (the RMS of that
  cycle's own notched residual, measured broadband over the full buffer) in the same formula in
  place of `noise_std_ref`, so rung 2 -> rung 3 isolates *noise character* at a matched nominal SNR
  rather than confounding it with a different absolute noise power (rung 3's synthetic `noise_std_ref`
  AWGN and the real notched residual's RMS are not guaranteed equal, and using the fixed reference
  would silently test both effects at once). This is a QA construction choice; flagged in §5.

### 2.5 Rung 4 — reused, not regenerated

Per HK-004 (check whether the data already answers this before generating new data) and the 15:22
ruling's own precedent for R.4b: **rung 4's "real signals, unmodified" component is already decoded
and persisted three times over** — WSJT-X's own `ALL.TXT` (ground truth), our offline decoder's
`ALL.TXT` (`b1.OURS_OFFLINE_ALL_TXT`), and B.1's own recorded jt9-depth-1 stdout
(`artefacts/d001_b1_jt9_ablation/A2_d1/stdout_raw.txt`) — all on the *same* unmodified WAVs this
arm would otherwise re-decode. **Rung 4 is computed by restricting all three to the 20 selected
cycles and reading off hit/miss per message, no fresh decode.** This is the R.4b endpoint at a
20-cycle sample rather than the full 68; self-check (§4) is that its aggregate rate lands near the
already-published 61%/55.4% (design §3's target), not an exact reproduction (a 20-cycle sample
carries its own sampling noise against a 68-cycle population).

### 2.6 Notching (rung 3's background)

**Spectral mask, whole-buffer, per the design's own description ("a spectral mask, not an
algorithm").** For each selected cycle's real WAV (12 kHz/16-bit mono, 180,000 samples, converted to
float32 `[-1, 1]`): `rfft` the full buffer, zero every frequency bin in `[freq - 5, freq + 43.75 + 5]`
Hz (5 Hz guard band each side of the occupied envelope) for **every message WSJT-X decoded in that
cycle** (the full list, not just the band/timing-filtered subset used for planting — the residual
should be clear of all known real signal energy, not only the subset R.5 replants), `irfft` back.
`noise_std_real` (§2.4) is the time-domain RMS of this residual, whole-buffer.

## 3. Decode + scoring

**Our decoder:** `b2.Native.decode_all(buf)` (candidate diag, `decoded` bool) is the mechanism used
throughout B.2/R.4 for planted-signal attribution, but it does not surface decoded *message text*,
which rung 4's WSJT-X-message-list ground truth needs for exact matching. **R.5 adds a thin wrapper
around the same loaded DLL** that reads `FT8Result.message` off `ft8_decode_all`'s own output array
(already computed inside `decode_all`, just not returned) — no native change, no new export, this
data is already produced by the shipped `ft8_decode_all` call and simply wasn't read out before.
For rungs 0-3, a planted message counts as decoded if its exact message string appears in that
buffer's decoded-message set (synthetic Q-call messages are unique by construction, same convention
as R.4 §2.1 — no location/tolerance matching needed).

**jt9:** each rung-0/1/2/3 buffer is written to WAV (`b2.SR`=12kHz, `r4.write_wav`'s convention) and
decoded via `jt9 -8 -d 1 -p 15` (single-file invocation, R.4's convention), matched against the
planted message strings exactly.

**P(decode) per rung**, both decoders, Wilson interval, computed over all planted-signal
opportunities pooled across the 20 cycles (rungs 0-3) or all WSJT-X messages restricted to the 20
cycles (rung 4) — **reported per rung, never collapsed across rungs**, since the collapse point
*is* the result.

## 4. Self-checks (must pass before any rung's number is trusted)

1. **Rung 0** (§2.3): Wilson lower CI >= 90%, both decoders.
2. **Rung 4** (§2.5): aggregate P(decode) on the 20-cycle sample, both decoders, reported alongside
   the full-68-cycle published figures (61.3%/55.4% — R.4b/B.1) with a note on whether the 20-cycle
   sample is consistent with that figure (Wilson CI overlap), not an exact-match requirement.
3. **Band/timing filter counts** (§2.4): reported per cycle and in aggregate — how many real
   messages were available, how many survived the band filter, how many additionally survived the
   timing filter and are the layout rungs 1-3 actually measure. If band+timing exclusion removes a
   large fraction of a cycle's real population, that cycle's rung 1-3 buffers are testing a
   thinned-out version of that cycle's real geometry, not the full thing — reported as a caveat, not
   silently absorbed.

## 5. Honest caveats (beyond the design's own §6)

- **Rung 3's amplitude/noise-power rescaling (§2.4/§2.6) is a QA addition**, not specified by the
  design. It is intended to isolate noise *character* from noise *power*, but it means rung 2 and
  rung 3 are not on byte-identical signal amplitudes in absolute terms — only in nominal-SNR terms
  against their respective (different) noise floors. Flagged so the reading is not overstated.
- **dt shift-and-drop (§2.4) changes relative timing for cycles whose real dt spread exceeds the
  buffer's 2.3667 s budget.** This is unavoidable given the buffer format this whole study has used
  throughout (WSJT-X's own 15 s capture cadence); it is reported per cycle, not hidden.
- **CPFSK vs GFSK** (every prior arm's standing caveat) applies to rungs 0-3 exactly as it does to
  B.2/R.4/R.4's Arm A; rung 4 (real audio, no synthesis) is exempt, same as R.4b.
- **WSJT-X's reported SNR is its own estimator**, inherited by rung 2/3's amplitude construction,
  same caveat as R.4/R.4b.
- **The notch (§2.6) is imperfect by construction** — a 2950 Hz-limited real cycle may have
  WSJT-X-decoded messages above 2950 Hz that still get notched (correctly, since they are real
  signal energy) but were never candidates for replanting; conversely, real signals WSJT-X did *not*
  decode (weak/missed) are not notched at all and remain in rung 3's "noise" background as
  unaccounted structure. This is the design's own §6 caveat, restated with the specific mechanism.

## 6. Cross-references

- `2026-07-27-1822-architect-r5-hybrid-ladder-design.md` — the design this operationalises.
- `2026-07-27-1522-architect-r4-ruling-and-r4b.md` §2 — the search-band stop rule §2.1 applies.
- `b2_synthetic_calibration.py`, `r4_sensitivity_gap.py`, `r4b_realworld_sensitivity_curve.py`,
  `b1_jt9_ablation.py` — machinery reused throughout (see script header for exact imports).
