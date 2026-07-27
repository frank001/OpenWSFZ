# D-001 R.4 — the cost signal in dB, QA task spec

**Author:** QA, 2026-07-27 (15:03 UTC, `date -u`, per HK-017). **Operationalises:**
`2026-07-27-1730-architect-row4-scoping-design.md` §4 (R.4), as resequenced by
`2026-07-27-1444-architect-r1b-ruling-and-r3-amendment.md` §7 ("R.4 → R.3 (amended) → R.2") and §4
point 3 ("R.4 ... generates and persists the shared buffer corpus that R.3's amended detection axis
now depends on"). R.4's method, reading rule and limits are stated as **unchanged** by the 1444
note — this spec operationalises the 1730 design's §4 text directly, adds the buffer-persistence
obligation the 1444 note places on it, and does not reopen any judgement call.
**QA-runnable directly: no `src/`/native change, HK-011 does not apply, no `dev-tasks/` entry** —
same posture as R.1/R.1b/B.1/B.2/B.1b.

---

## 1. Question

**ΔSNR:** how many dB more sensitive is WSJT-X's `jt9` (minimum-effort, depth 1 — the same arm
B.1/B.1b used) than our shipped decoder (K_MIN_SCORE=10, K_MAX_CANDIDATES=600, N_LDPC_ITER=60),
decoding **byte-identical synthetic buffers**? And: **how many of each corpus's currently-missed
messages does closing x dB of that gap recover**, for x from 0 to ΔSNR?

## 2. Method

### 2.1 Buffer generation (shared with R.3 per the 1444 ruling — persisted, not discarded)

Reuses `b2_synthetic_calibration.py`'s Arm A geometry verbatim (imported, not copied):
`Native`, `synth_signal`, `plant`, `make_message`, `q_call`, `wilson_interval`, the 12 kHz / 15 s
buffer format, 8 isolated signals per buffer at well-separated frequency slots, `AMPLITUDE=0.15`.
**New seed** (`20260727`, distinct from B.2's `20260726`) so this is a fresh buffer set, not a
replay of B.2's own measurements — R.4 needs its own buffers written to WAV for `jt9`, which B.2
never did.

**Grid.** B.2's own Arm A raw data (`artefacts/d001_b2_synthetic_calibration/arm_a_raw.json`)
already shows our decoder's P(decode) falling from ~87% to ~11% between **-20.5 and -23.0 dB** on
its synthetic `snr_db` scale — a fast enough transition that a **-14 to -30 dB grid, 1 dB steps
(17 levels), 3 repeats/level** (51 buffers, 408 planted-signal opportunities per decoder) should
bracket both decoders' 50% points, on the working assumption (stated, not proven) that `jt9` is
more sensitive and therefore crosses 50% at a more negative `snr_db` than we do. If the sweep does
not bracket `jt9`'s crossing, that is reported as a self-check-adjacent finding (§4) and the grid
widens in a follow-up rather than being silently extrapolated.

**Per buffer:** synthesise, decode via our native decoder (`Native.decode_all`, reused from B.2)
to get located+decoded per planted message; separately write the identical PCM to a 12 kHz/16-bit
mono WAV (`rewindow.write_wav_int16`, reused) and invoke `jt9 -8 -d 1 -p 15` **once per buffer**
(single-file invocation, not B.1's multi-file batch — avoids any risk of mis-attributing decode
lines across files when filenames carry no real session semantics). Match jt9's decoded message
text against the known planted message strings exactly (synthetic `CQ Q#XXX GRID` messages are
unique by construction; no tolerance-band matching needed, unlike the corpus arms).

**Persistence (owed to R.3):** all 51 WAVs plus a manifest (`buffer_id -> [(message, freq_hz, dt,
snr_db) x8]`) are written to `artefacts/d001_r4_sensitivity_gap/buffers/` so R.3 can decode them
again for its D-miss/X-loss/E-cand/Decoded classification without regenerating (same ground truth,
reused per the 1444 note's instruction).

### 2.2 ΔSNR

Bin both decoders' results by `snr_db` (already on a fixed grid, no binning needed), compute
Wilson intervals, find each curve's 50%-crossing SNR by linear interpolation between the two grid
points straddling 50%. **ΔSNR = our_50 − jt9_50** (positive if jt9 is more sensitive, i.e. crosses
50% at a more negative `snr_db`).

### 2.3 dB-to-messages curve (per corpus, never collapsed)

**Miss population.** Reuses `b1_jt9_ablation.py` (corpus 1) and `b1b_second_corpus_ablation.py`
(corpus 2) directly: `parse_all_txt` on each corpus's WSJT-X `ALL.TXT` and our own offline
`ALL.TXT`, restricted to the corpus's own cycle set (same technique both scripts already use),
gives the per-cycle missed-message rows — each row already carries WSJT-X's reported `snr` field.
No new capture; this is the same `missed_by_cycle` computation both scripts already perform,
re-run here to keep the SNR values (the existing scripts only ever printed counts).

**Current threshold — an operational choice this spec makes explicit, not one the design fixed.**
The 1730 design says "x dB of our current threshold" without defining the threshold numerically,
and it cannot be the synthetic `snr_db` scale directly (§4's own honest-limits language: WSJT-X's
SNR is "its own estimator, not a calibrated absolute" — the two scales are not known to coincide).
**Defined here as the 5th percentile of WSJT-X-reported SNR among that corpus's own *shared-hit*
(successfully decoded by us) messages** — i.e., the weakest signal we are empirically already
decoding on that corpus, read entirely off real corpus data, with no synthetic-to-real conversion
needed for the threshold itself. Only the **step size** (how far x can extend, capped at ΔSNR) is
imported from the synthetic measurement, which is exactly where the design's own caveat already
lands.

**Curve:** for x ∈ [0, ΔSNR] in 0.5 dB steps, `messages_recovered(x)` = count of missed messages
with `snr ∈ [threshold − x, threshold)`, cumulative. Reported as a table and **never collapsed
across corpora** — the 1444 note's added rule (§6.2) that caps must never be collapsed applies by
the same logic to corpora here, and the original design already required this (§5).

## 3. Reading rule

**Unchanged from the design** (§4's own table) — reported as a curve with ΔSNR's Wilson interval
alongside it, no summary number quoted alone. Two shapes, both already anticipated:

| shape | reading |
|---|---|
| Most of the corpus's `437` recovers within a small fraction of ΔSNR | Row 4 is divisible — a partial front-end improvement is a real, incrementally-priceable product option. |
| The curve stays flat until close to the full ΔSNR | Row 4 is an indivisible commitment; price it against row 5 in full. |

## 4. Self-check before trusting any number

**jt9-invocation correctness, reusing B.1's own recorded evidence rather than re-trusting a fresh
assumption.** `artefacts/d001_b1_jt9_ablation/A2_d1/stdout_raw.txt` already holds B.1's real depth-1
decode output for corpus 1's `260725_180615.wav`. This script re-runs `jt9 -8 -d 1 -p 15` on that
**exact, unchanged WAV** via the same single-file invocation path R.4 uses for its own buffers, and
compares the resulting decode set (message text, normalised via `normalize_hash_tokens`) against
the lines already on record for that timestamp. **Reported as a match/mismatch count only — never
as message text (NFR-021)**, since that stored file carries real off-air callsigns even though it
lives under git-ignored `artefacts/`. If the sets do not match exactly, stop and report the
self-check failure, not the arm's result (design §6's stop rule, reused verbatim).

**Grid-bracketing check (§2.1):** if `jt9`'s 50%-crossing SNR is not found within the swept grid
(i.e. `jt9`'s P(decode) has not fallen below 50% by the coldest grid point, or is already below
50% at the warmest), that is reported as a bracketing failure, not extrapolated past the measured
range.

## 5. What this does not authorise

Same guardrails as the design doc §7 and R.1's task spec §5: no native/`src/` change, no
push/merge, no `pre_merge_check.py` (HK-006), NFR-021 (Q-prefix synthetic messages throughout
§2.1-§2.2 by construction; §2.3/§4 touch real corpus data and report aggregate counts/SNR values
only, never message text, staying inside git-ignored `artefacts/`).

## 6. Cross-references

- `2026-07-27-1730-architect-row4-scoping-design.md` §4 (R.4), §5 (corpus ruling), §6 (sequencing/
  stop rules) — the design this operationalises.
- `2026-07-27-1444-architect-r1b-ruling-and-r3-amendment.md` §4, §6.1, §7 — the resequencing and
  the buffer-persistence obligation to R.3.
- `b2_synthetic_calibration.py` — synthesis/decode harness reused verbatim.
- `b1_jt9_ablation.py`, `b1b_second_corpus_ablation.py` — jt9 invocation and corpus miss-population
  machinery reused verbatim; `artefacts/d001_b1_jt9_ablation/A2_d1/stdout_raw.txt` — self-check
  ground truth.
- `rewindow.py` — `write_wav_int16`, reused for buffer persistence.

