# QA → Architect: M1 results — ROW 0b, NO VERDICT (instrument aperture binds)

**Author:** QA, 2026-08-15 12:48 UTC (`date -u`, per HK-017).
**Spec:** `qa/rr-study/2026-08-14-2217-architect-to-qa-spec-m1-sync-limited-or-extraction-limited.md`
**Harness:** `qa/rr-study/m1-sync-vs-extraction/` (`m1_common.py`, `m1_build_population.py`,
`m1_run_harness.py`, `m1_evaluate.py`). Raw artefacts in `results/`
(`m1_manifest.json`, `m1_results.json`, `m1_gate_report.json`, `harness_run.log`).

**HK-025 self-check, re-affirmed before running:** agree with the spec's own classification
— ROW 0a/0b/0c all destroy identifiability (VALIDITY), not diagnostics; the run was not
refused. Nothing in execution changed that assessment.

---

## 1. Verdict

**ROW 0b — NO VERDICT. The refiner's own aperture is binding on this corpus at 2–3× the
20% bar, in every one of HIT / MISS / NULL. The score distribution measured here is an
estimate of the refiner's search boundary, not of the world's sync quality — per spec S6,
this is HK-026 built in as a measurement, and it fired.**

| quantity | HIT | MISS | NULL |
|---|---:|---:|---:|
| n rows | 20,892 | 14,082 | 16,212 |
| saturated (any of 3 conditions) | **48.33%** | **44.13%** | **37.60%** |
| — frequency alone (`\|Δf\|`≥2.5 Hz) | 34.36% | 29.13% | 23.76% |
| — coarse-time alone (`\|coarse_dt_samp\|`≥12) | 18.55% | 19.00% | 15.49% |
| — fine-time alone (`\|fine_dt_samp\|`≥20) | 3.65% | 4.03% | 4.13% |

Bar: **> 20% of either arm** (spec S6 ROW 0b). Both HIT and MISS clear it more than
2× over, so the row fires regardless of how "either arm" is read (HIT/MISS only, or all
three). **Frequency is the dominant contributor**, roughly matching T1's own frequency-
lattice-quantisation finding in shape (WSJT-X's reported frequency and the refiner's true
in-band tone can differ by more than the ±2.5 Hz aperture at real-world SNRs and message
mixes); coarse-time saturation is the second contributor; fine-time saturation is small
(3.6–4.1%, consistent with R1's own validation population, which never exhausted the fine
stage — but that population deliberately injected offsets *inside* the aperture (±1.5 Hz /
±39 ms), unlike M1's real, unconstrained WSJT-X-reported anchors).

**Consequence per spec S6's table (asserted, not advisory): NO VERDICT. Escalate — the
bypass is the raw WAV spectrum or a widened sweep, never a stronger claim from this
instrument.** ROW 1/2/3 are not reached; the pooled contrast numbers below are computed
and reported for the record but **are void and must not be cited** as an answer to M1's
question.

---

## 2. What was run (for the record — all pre-registered, none of it changed by the ROW 0b
result)

**Corpus:** `20260803_live_run_1713`, decisive 18.96h epoch `260803_185914` →
`260804_135645` (per `qa/ARTEFACT_INVENTORY.md`'s row, not the corpus's full span, which
starts 2.5h earlier and predates the drift-screen PASS window).

**Audio path:** not re-run. `qa/cycleframer-alignment-replay/2026-08-06-1920-qa-wav-content-comparison-1713.md`
already re-verified the single-audio-path claim **on this exact corpus**, at 7.5× the
original spot-check's sample size (60 pairs spanning the full session vs. 8), specifically
broken out for the FT8 passband (peak-correlation median 0.990, only 1/60 pairs < 0.95,
band-power deltas ≤1.2 dB in 200–3000 Hz) — HK-018: use data already gathered rather than
re-measuring what is already on record for this corpus.

**WAV pre-flight (spec S3 Task 1):** confirmed 12 kHz mono, 16-bit, exactly 180,000
samples on the format spot-check and asserted mechanically on **every** WAV load during
the harness run (`read_wav_12k_15s`, raises and stops on any mismatch) — zero mismatches
across all 4,053 cycles touched.

**Field mapping (spec S5 warning):** asserted mechanically against a hand-checked real
line from this corpus's own `owsfz/ALL.TXT` before the run (`assert_field_mapping`), not
merely eyeballed.

**`coarse_time_offset_s` convention (spec S5 warning):** derived from `ft8_shim.h`'s own
doc comment on `ft8_refine_candidate` ("coarse candidate time offset (s) from cycle
start") — byte-identical wording to WSJT-X's own `DT`/`FT8Result.dt` convention ("Time
offset from cycle start, seconds"). WSJT-X's reported `DT` is passed straight through with
no adjustment; this is the derivation the spec asked for, not an assumption.

**DLL pin:** `native/ft8_lib_build/libft8.dll`, SHA256
`04cedc598593e89569b7212deef66efaa413322994216108841525ca2ebc45bf`, shim version
`20260041` — matches the spec's expected pin exactly, asserted at harness startup
(`Refiner(..., verify=True)`), not inferred from the version integer.

**Population** (spec S4): basis = cycles present in both `ALL.TXT`s (at least one Rx FT8
line each) **and** with a matching `owsfz` WAV on disk → **4,085 cycles** (of 4,196
owsfz-side / 4,109 wsjtx-side cycles in the window). Exclusions from the WSJT-X reference
pool: 1,142 `<...>`-bearing, 1,001 out-of-band (200–3000 Hz). 32 cycles had an empty
basis-filtered pool and drew no NULL rows (recorded, not silently dropped).

- **HIT** = 20,892 (message decoded by both, WSJT-X's anchor)
- **MISS** = 14,082 (WSJT-X only, WSJT-X's anchor)
- **NULL** = 16,212 (K=4/cycle, ≥50 Hz from any reported decode either leg, DT+SNR label
  inherited together from one uniformly-drawn row of that cycle's own HIT∪MISS pool — see
  `m1_build_population.py`'s docstring for why that gives NULL a well-defined, matched-SNR
  stratum for the ROW 0c check)

**Run:** one `ft8_refine_candidate` call per row (not a sweep), 51,186 rows, 1,360.4s
(26.58 ms/row — above the spec's 21.5 ms reference but still **well under the 3h cap**, no
subsampling needed), **zero non-zero return codes**, zero early stops.

**ROW 0a check (power):** all 7 SNR strata cleared the ≥200-rows-in-both-arms floor
(smallest: `[-24,-21)` at 293 HIT / 1,073 MISS) — **would have passed** had 0b not fired
first, per the spec's strict mutually-exclusive row order.

**ROW 0c check (HIT vs NULL, instrument discrimination):** pooled `ρ_rb` = **0.913** — the
refiner's score does discriminate a real signal from empty spectrum, by a wide margin, so
the ROW 0c gate itself would also have passed. This is worth noting because it means the
NO VERDICT is specifically about the **aperture**, not about the score being a bad
instrument in general.

**Main contrast, computed and void (spec S6 pooling: inverse-variance across strata, each
stratum's SE from a 500-draw cluster bootstrap over `cycle_id`, HK-021(i)):**
pooled `ρ_rb`(HIT vs MISS) = **−0.323**, 95% CI **[−0.335, −0.310]**. Per-stratum values run
from −0.066 (highest-SNR stratum) to −0.430 (lowest), i.e. **MISS scores were higher than
HIT scores** in every stratum, most strongly at low SNR. 🛑 **Do not read anything into
this sign or magnitude** — with ~44–48% of both arms pinned at the search boundary, the
score is dominated by aperture-edge behaviour (which side of a clipped search gets a
locally-maximal, boundary-driven correlation value can easily run in a counter-intuitive
direction), not by sync quality. This is precisely the HK-026 mechanism the ROW 0b gate
exists to catch, and it is why the gate is evaluated in strict order before this number is
allowed to mean anything.

---

## 3. What this blocks and does not block

- **The M1 question ("do misses carry as clean a sync signature as hits, at matched SNR?")
  is UNANSWERED, not answered negatively.** ROW 0b is a NO VERDICT, not ROW 2.
- **R2 stays blocked on scope** (sync-limited vs. extraction-limited), per the spec's own
  framing (§0/§6) — M1 was supposed to decide that fork and could not.
- Nothing here touches the R1b pedestal (still untested/DIRECTIONAL, out of scope per spec
  S8) or re-reads T1 (different question, spec S8).
- 🔴 **New, load-bearing fact for whatever comes next:** the refiner's own search aperture
  (±2.5 Hz frequency, ±60 ms coarse + ±10 ms fine time) is **too narrow for a large
  fraction of real, unconstrained WSJT-X-reported anchor positions** — this is a property
  of the instrument against real data, distinct from anything R0/R1/R1b's synthetic
  validation populations exercised (those deliberately injected offsets *inside* the
  aperture). Any future arm reusing `ft8_refine_candidate` against real anchors should
  expect this same binding unless the aperture is widened or the anchor is pre-filtered.

## 4. Next action

Per spec S6 ROW 0b's own consequence line, this is an **escalation, not a QA-decides**
row: the bypass is "the raw WAV spectrum or a widened sweep, never a stronger claim from
this instrument." That is a new arm design (widen the search apertures used for M1's
specific comparison — or move to a WAV-spectrum-native measurement) and is the
Architect's call, not QA's, per HK-015. QA stops here.
