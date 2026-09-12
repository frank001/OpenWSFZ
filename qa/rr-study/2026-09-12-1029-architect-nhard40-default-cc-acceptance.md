# `NHARD40-DEFAULT` `CC` — acceptance ruling: **CC-S1 ACCEPTED**, structurally (`C = 0` in every family); `NT-S1 ∧ CC-S1` ⇒ **the dev-task is LICENSED**

**Architect, 2026-09-12 10:29Z** (`date -u`, HK-017). Branch `arch/osd-nhard40-default`.
Docs-only; `git diff --stat origin/main -- src/ native/` empty.

Accepts QA's work on branch `nhard40-default-nt-result`, `50db5d3`, against Amendment 1
(`2026-09-12-1000-…-amendment-1-cc-leg.md`) §2:

- `qa/rr-study/2026-09-12-1025-qa-to-architect-nhard40-default-cc-result.md`

---

## 1. Recomputed

From `artefacts/2026-09-12-nhard40-default-cc/cc.json`, with my own counting and my own
Clopper–Pearson bounds:

| family | cycles | station-cycles | `G` (`p60`) | `K` | `C` | gains at 40 / at 0 | `CI_hi` (0 of N_cycles) | false decodes/cycle, 60 → 40 → 0 |
|---|---:|---:|---|---:|---:|---|---|---|
| co_channel | 300 | 700 | 399 (0.570) | 0 | 0 | 0 / 0 | 1.83% (N=200) | 0.250 → 0.003 → 0 |
| near_collision | 500 | 1,000 | 987 (0.987) | 0 | 0 | 0 / 0 | 0.74% | 0.390 → 0.012 → 0 |
| time_freq | 300 | 600 | 600 (1.000) | 0 | 0 | 0 / 0 | 1.22% | 0.303 → 0.027 → 0 |
| capture | 400 | 800 | 503 (0.629) | 0 | 0 | 0 / 0 | 0.92% | 0.300 → 0.015 → 0 |
| co_channel_sweep | 600 | 1,200 | 1,192 (0.993) | 0 | 0 | 0 / 0 | 0.62% | 0.243 → 0.015 → 0 |
| **pooled** | **2,100** | **4,300** | **3,681** | **0** | **0** | 0 / 0 | **0.185%** | **0.299 → 0.014 → 0** |

**CC-S1:** pooled `CI_hi = 0.185% < BAR_S = 5%`, and no family has `CI_lo ≥ 5%` (every `K_f = 0`).
**ACCEPTED.**

**The hard families matter most, because they are where a rescue would show.** In `co_channel`, 43%
of station-cycles fail to decode at all. In `capture`, 37% do. **Those are the stations BP loses to
interference, and OSD rescues none of them at any setting**: `p0 = p60` for every station-cycle.

## 2. ROW 0

- **0a, 0c, 0d:** clear, as reported. 0c: 300 cycles, 900 comparisons, 0 mismatches. 0d:
  `G = 3,681 ≥ 1,000`.
- **0b substitution: ACCEPTED.** QA pinned the scenario file's SHA-256 (`aed34c69…5761f`) and added a
  structural assertion, instead of a field-by-field comparison. **Checked against the code:**
  `part_cc.py:204` builds every rendered signal dict **directly from the pinned file's own fields**
  (`msg_id` → text, `freq_hz`, `dt_s`, `snr_db`). So "the rendered list equals the file" holds by
  construction, and the hash guards the file. That is equivalent to what 0b asked for, and less
  error-prone. Disclosed.
- **QA's self-caught `row` variable clobber** (only the persisted `gate_row` field was wrong; the
  console and all counts were right): fixed, re-run, disclosed. My recompute used the raw per-cycle
  arrays, not that field, so it is unaffected.

## 3. The R6 question, answered

In the `co_channel` family (parts 0–2, the R6 diagnostic's own geometry), there are **75 OSD accepts
at 60, and none is genuine**. **The 2026-06-20 R6 "genuine" S7 population
(`results/diag-nhard-2026-06-20/`) was false accepts.**

🛑 **`decode.c:41`'s calibration note, "60 calibrated against … S7 genuine histograms", rests on a
mislabelled population. Never cite it as evidence that genuine decodes need `nhard` up to 60.** This
explains why the R6 "genuine" and FP histograms were identical: they were the same thing.

## 4. What the two gates establish together, and what they do not

**Established (synthetic, AWGN, oracle truth):** across **4,391 genuine decodes** (NT 710 + CC
3,681), in isolated near-threshold and five co-channel geometries, **OSD rescued zero, at any
`nhard`**. Meanwhile 60 → 40 removes **98% of false decodes in NT** (0.1385 → 0.0025 per cycle) and
**95% in CC** (0.299 → 0.014 per cycle).

**Not established (unchanged caveats):**

- **Fading, drift, Doppler, timing spread** (E4, never opened). This is the likeliest remaining place
  a genuine OSD rescue could live. The live Part D3 probe classified 10 WSJT-X-confirmed decodes as
  OSD-path, but that probe's path classification has a known blind spot (E3 ruling §4).
- **Live:** E3's corroborated-removal floor, 2 of 1,491, about 0.09 per hour, bounds genuine loss
  **from below only.**

⇒ **Cite:** *"no genuine loss detected, at 60 → 40, in isolated near-threshold or S7 co-channel
conditions on AWGN; 95–98% fewer false decodes."* **Never "safe".**

📊 **A lead, not a proposal:** if OSD rescues nothing genuine in any condition tested, it is fair to
ask whether OSD earns its keep at all. **That is a separate arm, not opened.** It would need E4-type
impairments before anything could be concluded.

## 5. Predictions (Amendment 1 §2.10)

| predicted | result | score |
|---|---|---|
| CC-S1 0.35 / S3 0.30 / S2 0.35 | S1 | landed, at a third-choice-level probability |
| `C > 0`: 0.7 | **`C = 0`** | **wrong** |

My physics argument, that interference would push genuine codewords into an OSD rescue at
`nhard` 45–60, was wrong on this geometry. That is the second arm running where I over-weighted it.

## 6. Consequence: Amendment 1 §1 item 3 fires

**`NT-S1 ∧ CC-S1` ⇒ the Architect asks QA to author the dev-task per base §1, with M2.** Specifically:

1. **`DecoderConfig.cs`:** 60 → 40 in **both** the `[JsonConstructor]` parameter default (`:36`) and
   the property initialiser (`:68`). Update the doc comment to cite this arm, and **drop the "S7
   genuine histograms" calibration claim** (§3).
2. **Native default stays 60** (no rebuild). State the deliberate divergence in the C# doc comment.
3. **M2 migration (PO 09:15Z):** a persisted `osdNhardMax` of **exactly 60** becomes 40 **once**. It is
   logged, and a marker (a new config field, shape to be specified in the dev-task) stops it
   re-applying after an operator deliberately sets 60. **It needs tests:** persisted 60 without the
   marker migrates; with the marker it doesn't; 55 or 70 is untouched; a missing `decoder` key gets
   the new default.
4. **Test consequences (base §1.4):** `DecoderConfigTests` 60 → 40. **`FpParityP3Tests` ROW 0o's
   meaning changes** (the live-effective value becomes 40), so the dev-task must say explicitly what
   that Fact asserts afterward. **From the change onward every offline FP rate states its `nhard`**;
   `10.325%` becomes "at `nhard` 60".
5. **QA harness constants:** relabel `p23_common.DECODE_PARAMS` as "pre-change defaults"; don't
   silently change them.
6. **Rollback:** set `Decoder.OsdNhardMax = 60` in `config.json`.

Then a Developer session implements it (HK-011), QA verifies it, and the merge needs the Captain's
sign-off (HK-010). **Nothing about this licence skips any of those.**

## 7. Housekeeping

- `OSD-FA-A` is pushed: **PRs #157 / #158 / #159 are OPEN, and every check is SUCCESS or SKIPPED**
  (checked 10:28Z). Merge needs the Captain.
- **`nhard40-default-nt-result` is stacked on #158's branch.** HK-008: once #158 squash-merges and its
  branch is deleted, rebase with `git rebase --onto`. Pushing it (and `arch/osd-nhard40-default`)
  needs its own Captain go (HK-033).
