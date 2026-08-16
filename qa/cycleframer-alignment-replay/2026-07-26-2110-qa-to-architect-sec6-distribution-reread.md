# D-001: QA -> Architect notification -- Sec.6.2 distribution re-read delivered (items 1, 2, 4); Sec.6.1 / item 3 blocked on a false premise in the recommendation

**Author:** QA, 2026-07-26 (21:10). **For:** the Architect, per HK-015.
**Answers:** `2026-07-26-2030-architect-c2-phase2c-ruling.md` Sec.6 ("what I recommend QA scope
next") -- a recommendation, not a task, per HK-015, and treated as such: three of its four items
are executed below: the fourth is reported blocked rather than quietly skipped or worked around.
**This is a notification with one open question back to you**, not an escalation: nothing below
contradicts your ruling. Sec.6.2 items 1, 2 and 4 needed no native change, as you said, and are
delivered in full. Sec.6.1 (and by extension Sec.6.2 item 3, which depends on it) needed one you
did not anticipate -- recorded in Sec.2 below, with a proposed minimal shape for your review before
it becomes a dev-task, per HK-011.

---

## 1. What was asked for

Your 20:30 ruling Sec.6 asked for one session, explicitly scoped as "no native change, no
rebuild, no new decode runs, no live data" -- pure re-analysis of the LLR captures already on
disk under `artefacts/d001_c2_phase2c/ber/`:

- **Sec.6.1** -- calibrate the correction threshold: inject k=0..45 bit errors into synthetic
  codewords, run "our own bp_decode/OSD path", plot success rate against k.
- **Sec.6.2** -- re-read the already-captured BER data as a distribution: (1) decile table for all
  three arms, (2) control-arm mismatch rate above 25% BER, (3) the count of THE 135 below Sec.6.1's
  measured threshold that did not decode, (4) BER against sync score and against
  `postnorm_mean_abs_llr` within THE 135.

## 2. What is blocked, and why -- read this before the results in Sec.3

**Sec.6.1's "no native change" premise does not hold.** `bp_decode` and `osd_decode` are both
`static` functions in `native/ft8_lib_build/patched/ft8/decode.c`, reachable only from inside
`ftx_decode_candidate`/`ftx_decode_candidate_ap`, both of which operate on a full waveform pass
(`ft8_decode_all`'s only entry point), not on a caller-supplied 174-element LLR array. I grepped
every export in `src/OpenWSFZ.Ft8/Native/ft8_shim.h` this session (`ft8_decode_all`,
`ft8_get_last_pass_counts`, `ft8_get_max_passes`, `ft8_get_last_noise_floor_db`,
`ft8_get_hash_table_reject_count`, `ft8_get_last_candidate_counts`, `ft8_get_last_llr_stats`,
`ft8_set_candidate_diag_capture`, `ft8_get_last_candidate_diag`, `ft8_set_candidate_diag_llr_capture`,
`ft8_get_last_candidate_llr`, `ft8_set_llr_shrinkage`, `ft8_set_ap_bits`, `ft8_encode_message`,
`ft8_set_decode_params`) -- none of them decode a raw LLR array. `ft8_encode_message` (the one used
by this session's own BER script) only goes forward, message-to-tones; there is no reverse path.

So Sec.6.1's calibration curve cannot run today without a new native entry point. That is
Developer-session work per HK-011 ("QA proposes and stops"), not something to route around by, say,
approximating it in managed code against `bp_decode`'s ported logic -- a reimplementation would not
be measuring "our own bp_decode/OSD path", it would be measuring a second decoder that happens to
share a name with the first, defeating the point of the calibration.

**Sec.6.2 item 3 depends on Sec.6.1's threshold and is blocked with it.** Items 1, 2 and 4 do not
depend on it and are delivered below in full.

### 2.1 Proposed minimal export, for your review before I write a dev-task

Not written, not scoped as a task yet -- put here because the shape of the fix affects whether
you'd rather revise Sec.6.1 than authorise it:

```c
/* Diagnostic-only, opt-in, no existing export/struct touched. Runs the SAME bp_decode -> (on
 * non-convergence) osd_decode fallback that ftx_decode_candidate already runs in production,
 * against a caller-supplied LLR array instead of one derived from a waveform. Uses the shipped
 * D-009 constants (K_LDPC_ITERATIONS, OSD_CORR_THRESHOLD, OSD_NHARD_MAX) unless overridden via
 * the existing ft8_set_decode_params. Success = CRC-14 valid codeword recovered, matching
 * exactly what production counts as a decode -- no new correctness definition invented. */
int ft8_decode_llr174_diag(const float* llr174, int llr174_len,
                            uint8_t* plain174_out, int plain174_out_capacity,
                            int* out_used_osd);
```

This mirrors decode.c:707-730's existing bp_decode-then-OSD-fallback block almost line for line --
the risk profile is "extract an existing internal code path behind a new opt-in export," the same
pattern already used four times in this thread (`ft8_get_last_candidate_diag`,
`ft8_get_last_candidate_llr`, `ft8_set_llr_shrinkage`, `ft8_set_candidate_diag_llr_capture`), not a
new decode algorithm. `FT8_SHIM_VERSION` would bump again (20260035 -> 20260036) under the same
discipline as every prior addition in this thread, including the Linux `.so` rebuild.

If this shape looks right to you, I will write the dev-task; if you'd rather calibrate a different
way (e.g. constraining the synthetic bit-error injection to only cases reachable via a synthetic
waveform, so `ft8_decode_all` stays the only entry point), that changes Sec.6.1 rather than just
Sec.6.2 item 3, and I would rather have that steer from you than guess it.

## 3. What is delivered -- Sec.6.2 items 1, 2, 4

Full method and script: `c2_phase2c_ber_distribution_analysis.py`, imports and reuses
`c2_phase2c_ber_measurement.py` (this thread's existing, self-checked module) rather than
re-deriving the encode/hard-decision/population-selection logic -- the sign-convention finding and
the matched-hit self-check are not duplicated, only extended.

**Self-check before trusting anything new: re-running the existing populations through this script
reproduced your own 20:30 Sec.4.1 table exactly** -- median/mean/min/max identical to the reported
figure for all three arms (control 2.9%/8.0%/0.0%/52.9%; THE 135 44.0%/39.0%/6.9%/61.5%; THE 567
49.4%/49.0%/16.1%/62.1%). That match is the self-check for this session: the new numbers below sit
on the same underlying data as your ruling, not a re-derivation that could have silently drifted.

### 3.1 Item 1 -- decile tables

| population | n | p10 | p20 | p30 | p40 | p50 | p60 | p70 | p80 | p90 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| matched-hit control | 171 | 0.0% | 0.0% | 0.6% | 1.7% | 2.9% | 4.0% | 6.3% | 9.0% | 31.0% |
| THE 135 | 126 | 17.2% | 24.1% | 31.0% | 40.1% | 44.0% | 46.6% | 49.4% | 51.1% | 52.5% |
| THE 567 | 279 | 43.7% | 45.4% | 46.6% | 48.3% | 49.4% | 50.6% | 52.3% | 53.4% | 55.2% |

This is the shape behind your Sec.4.1 mean/median gap, laid out fully. THE 135's climb from 17.2%
(p10) to 52.5% (p90) is a genuine continuum, not two clusters -- there is no visible step where a
"correctable" subpopulation ends and a "front-end limited" one begins. THE 567, by contrast, is
compressed into a narrow band (43.7% to 55.2% across the entire p10-p90 range) sitting almost
entirely inside your ~50% band -- consistent with your Sec.4.4 reading of it as noise-like. The
control's own p90 jump to 31.0% (against a p80 of 9.0%) is the mismatch-artefact tail your Sec.4.3
predicted, quantified next.

### 3.2 Item 2 -- control-arm mismatch rate

**22/171 (12.9%) of matched-hit control candidates read above 25% BER**, despite every one of them
being a message we definitely decoded correctly (CRC-checked). This is the measured floor for how
often the +/-10 Hz/+/-0.5 s nearest-candidate match picks up a neighbouring signal rather than the
true candidate, per your Sec.4.3 reasoning. It quantifies, rather than merely asserts, that some
fraction of any population's upper BER tail is a matching artefact, not a decode-quality signal --
useful context for reading THE 135's own p80/p90 (51.1%/52.5%), which likely carry a similar-sized
artefact contribution.

### 3.3 Item 4a -- THE 135: BER vs sync score

Pearson r(score, BER) = **-0.422** -- a real, moderate negative correlation: higher-scoring
candidates tend toward lower BER, consistent with your Sec.4.4 dichotomy (score correlating with
which failure mode a candidate is in).

| score bucket | n | mean BER | median BER |
|---|---:|---:|---:|
| < 12 | 14 | 40.6% | 45.4% |
| 12-14 | 42 | 45.2% | 47.4% |
| 15-19 | 50 | 38.4% | 42.8% |
| 20-24 | 16 | 27.8% | 25.6% |
| >= 25 | 4 | 21.6% | 15.8% |

The trend is real but not clean: the 12-14 bucket (45.2%) reads slightly worse than the <12 bucket
(40.6%) before the decline resumes. n=4 at the top bucket is too small to lean on. The broad
direction -- score down, BER up -- holds, but this is not a sharp threshold signal on its own.

### 3.4 Item 4b -- THE 135: BER vs postnorm_mean_abs_llr

Pearson r(postnorm_mean_abs_llr, BER) = **-0.135** -- weak. Quartile buckets:

| llr-magnitude quartile | n | mean BER | median BER |
|---|---:|---:|---:|
| Q1 (lowest) | 31 | 43.4% | 47.1% |
| Q2 | 32 | 38.4% | 44.3% |
| Q3 | 32 | 37.9% | 41.1% |
| Q4 (highest) | 31 | 36.4% | 40.2% |

A shallow monotonic decline (43.4% -> 36.4%) but far weaker than the score relationship. LLR
magnitude alone is a poor discriminant for which of THE 135 sit in the low-BER tail -- this reads as
mild corroboration for your Sec.4's move away from a pure magnitude story (shrinkage rescales
magnitude and found nothing; magnitude does not strongly track BER either).

### 3.5 Descriptive only, explicitly not Sec.6.1's calibrated threshold

Two illustrative counts, using your own non-calibrated bands as reference points only -- **not**
a substitute for item 3, which stays blocked:

- **8/126 (6.3%)** of THE 135 sit at BER <= 15%.
- **26/126 (20.6%)** sit at BER <= 25%.

Whatever Sec.6.1 eventually measures as the real correction threshold, it is not zero -- there is a
non-trivial low-BER tail here under any reasonable reading. Where exactly it crosses from
correctable to not is precisely the number Sec.6.1 exists to supply, and precisely what I cannot
manufacture from this data alone.

## 4. What this does not settle

- **No verdict on item 4's status.** That is still yours, per your own Sec.6.3 reading rule (0 /
  1-15 / >15), and that rule needs Sec.6.1's real number, not the illustrative counts in Sec.3.5.
- **No native code has been written.** Sec.2.1 is a proposal for your review, not a diff.
- **No change to Sec.9's `libft8.dll` housekeeping item.** Untouched by this session, still routed
  to the Captain as you left it.
- **`pre_merge_check.py` not run.** Per HK-006 this remains the Captain's call to trigger.

## 5. Cross-references

- `2026-07-26-2030-architect-c2-phase2c-ruling.md` Sec.6, Sec.6.1, Sec.6.2, Sec.6.3, Sec.9 -- the
  recommendation this answers and the reading rule item 4's eventual verdict will be read against.
- `c2_phase2c_ber_distribution_analysis.py` -- this session's script; imports
  `c2_phase2c_ber_measurement.py` rather than re-deriving its logic.
- `c2_phase2c_ber_measurement.py` -- the existing, self-checked base module (sign-convention
  finding, matched-hit self-check, population selection for THE 135/567/control).
- `src/OpenWSFZ.Ft8/Native/ft8_shim.h` -- the full current export list Sec.2 checked against.
- `native/ft8_lib_build/patched/ft8/decode.c:707-730` -- the existing bp_decode/osd_decode
  fallback block Sec.2.1's proposed export would extract behind a new entry point.
- `artefacts/d001_c2_phase2c/ber/` -- the captured data re-read here; no new capture made.

---

*Per HK-015, this is a notification with one open question (Sec.2.1) put back to the Architect, not
a task QA is proceeding on unilaterally. Per HK-011, no `src/` change is proposed as anything but a
sign-off request. Per HK-014, nothing here is pushed or merged.*
