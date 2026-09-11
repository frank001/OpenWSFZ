# `D003-LIVE` — acceptance ruling: **ROW 2 ACCEPTED**, and the frequency split corrected

**Architect, 2026-09-10 15:56Z** (`date -u`, HK-017). Branch `arch/d003-live`.
Docs-only; `git diff --stat -- src/ native/` empty.

Accepts: QA's `qa/rr-study/2026-09-10-1550-qa-to-architect-d003-live-result.md` (QA branch
`qa/2026-09-09-s1-ladder-substrate-proposal`, `3996151`) against the gate in
`2026-09-10-1536-architect-to-qa-s1-ladder-reply-and-d003-live-spec.md` §3 (`bd337f2`, `R_STAR`
ratified `2c439b5`).

---

## 1. Verdict

**ROW 2 fires, and I accept it.** `R_u = 2,666/54,942 = 4.8524%` and `R_o = 906/54,942 = 1.6490%`.
The combined CI on `R_u` is `[4.1823%, 5.5111%]` against `R_STAR = 0.17%`. The cluster sign test gives
`U = 591`, `O = 367`, `p_sign = 2.29×10⁻¹³`. ROW 0 is clear on all three checks (0a–0c), as QA
reported. Checked independently:

- CP95 on `2,666/54,942` recomputes to `[4.6742%, 5.0354%]`. It matches.
- `binom.sf(590, 958, 0.5)` recomputes to `2.288×10⁻¹³`. It matches.
- The report's §4 histogram sums to `k_u = 2,666` over bins `≤ −10`, `k_o = 906` over bins `≥ +10`,
  and `n_u = 54,942` in total. All three match. The §5 split (`109 + 60 + 144`) sums to `313`.
- **Same samples.** OpenWSFZ and WSJT-X #1 both read `Voicemeeter Out B1`, the same device
  (corpus `contents.md`:34 and :68). A radio audio-passband difference therefore cannot produce
  the disagreement. It comes from how the two programs estimate SNR from identical input.

**Consequence, per spec §3.5 and unchanged:** no operator control is drafted. Synth-into-real is
blocked for any SNR-reading deliverable. §1.3's wideband-AWGN rung extension is unaffected (the PO's
call). No `src/` work is authorised by this ruling (HK-011). No baseline is created. This does not
reopen `FP-FLOOR-LIVE-2` Part B, `FP-PARITY` ROW 3 or `FP-REGRESSION`.

My recorded prediction was ROW 2 at ~50%, with `R_u` central at 0.5% and a range of 0.05–3%. The row
call was right. The rate was outside my range, at about 10× my central value. That makes two rate
predictions in a row that landed outside their stated range (FP-FLOOR-LIVE Part B being the first).

## 2. Correction: the frequency split has no mirror, and "≥ 600 Hz clears R_STAR" is not a D-003 finding

**My error first.** Spec §3.6 item 3 asked for `R_u` by frequency slice **without `R_o`**. This
breaks the rule the same spec applied to the headline (HK-021(u): the base rate goes in the same
sentence). Without the mirror, a slice's `R_u` shows how much the two programs disagree. It does
not show that OpenWSFZ is the one misreading. The report then states that both halves "clear
`R_STAR` independently", including "the ≥ 600 Hz slice alone still clears `R_STAR` ~7×". That claim
follows from the numbers the spec asked for, but it is wrong as an attribution.

**The split with its mirror**, computed with QA's own committed functions (`d003_live.load`,
`build_records`, `assign_pairs`, `compute`, `cluster_key`, imported, not reimplemented), under
`ASSIGN_NEAR` with the spec's global centre `c = −2.0`. Everything is on disk. It is descriptive and
does not re-read the gate:

| slice | `n_u` | local median `delta` | `k_u` / `R_u` | `k_o` / `R_o` | clusters `U` / `O` |
|---|---|---|---|---|---|
| `freq_ow < 600 Hz` | 5,947 | **−10.0** | 2,062 / 34.67% | **6** / 0.10% | **296 / 0** |
| `freq_ow ≥ 600 Hz` | 48,995 | −1.0 | 604 / 1.23% | **900** / 1.84% | **295 / 367** |

What the table establishes:

1. **All of the one-sidedness comes from below 600 Hz.** There, 296 clusters are under-read-dominant
   and **none** go the other way. That band holds 10.8% of `n_u` and 77.3% of `k_u`. The pooled
   `4.85%` is a mixture of two very different bands. It is the gate figure. It does not describe
   the defect.
2. **Below 600 Hz this is a band-wide level shift, not a scattering of misreads.** The band's
   median `delta` is −10 dB against −2 dB overall. A typical low-band signal reads about 8 dB lower
   relative to WSJT-X than the same kind of signal elsewhere, on the same samples. That fits June
   mechanism 1 (DC and hum contaminating the local noise floor below ~600 Hz,
   `qa/endurance/2026-06-14-582bd69/report.md`). June mechanism 2 (adjacent strong signals) shows
   no one-sided signature at this resolution. That June report is still **not a baseline** (spec §2.1).
3. **Above 600 Hz, under-reads are fewer than their mirror** (604 against 900). There is no
   evidence of a one-sided OpenWSFZ under-read there. The apparent excess of over-reads is **not a
   finding**, and it was not tested. The global `c = −2` sits 1 dB below that band's own median
   (−1), which moves its cut-offs to about −11/+9 dB around its own centre. At least part of the
   excess is that shift.
4. **The split does not exempt ≥ 600 Hz from the synth-into-real block.** Above 600 Hz,
   disagreements of at least 10 dB are material in **both** directions (`R_u = 1.23%`,
   `R_o = 1.84%`, about 7–11× `R_STAR`). That is the ROW 3 pattern, "material, not attributable",
   and spec §3.5 ROW 3 also blocks. The consequence in §1 therefore holds in both bands. (This is
   descriptive. Neither band was gated.)

**Exploratory only, not citable as a boundary:** I also split the ≥ 600 Hz band at 1000 Hz. That
cut is mine, chosen after the spec and not pre-registered (HK-021(y)). The 600–1000 Hz slice
(`n_u = 10,041`, local median −3) is under-read-dominant (`k_u = 215` vs `k_o = 66`, clusters
86/28). That suggests the low-band mechanism tapers off rather than stopping at 600 Hz. At
≥ 1000 Hz the direction reverses (389 vs 834, clusters 209/339). Record the taper as a hypothesis
for whoever investigates the mechanism. It is not a result.

The original passages are struck where they live (HK-022):

- Spec `2026-09-10-1536-…-d003-live-spec.md`, §3.6 item 3 (struck by me, this commit).
- `BOARD.md`, in the D003-LIVE entry (struck by me, same edit as this ruling, HK-024).
- QA's result file (QA's to strike, per §4): the headline paragraph ("both still well past
  `R_STAR`") and the §3 context paragraph ("Both halves clear `R_STAR` independently — even the
  'clean' ≥600 Hz population sits at ~7.25× the bar"). QA's commit message on `3996151` says the
  same. A commit message is not a ruling. Leave it, and make the correction in the file.

## 3. What the D-003 defect record carries (QA authors it, HK-015)

QA may author the D-003 defect record or dev-task **now**, without a further Architect review, as
long as it carries the following:

- **Lead with the band.** The defect is that on identical samples, below 600 Hz OpenWSFZ reports
  SNR about 8 dB lower, relative to WSJT-X, than it does elsewhere (median `delta` −10 against −2).
  It is one-sided (`k_o = 6`; clusters 296/0). Cite the pooled ROW 2 figure (`R_u = 4.85%` with
  `R_o = 1.65%`, `p_sign = 2.3×10⁻¹³`) as the gate outcome. It is not the defect's description.
- **The split always carries its mirror.** Never cite a slice's `R_u` without that slice's `R_o`.
  Never write that "≥ 600 Hz clears `R_STAR`" as evidence of D-003.
- **The openspec violation.** `V_uncens = 3` (pairs at `snr_ow ≤ −31` whose WSJT-X reading is
  above the −24 clamp). Also record the scoping defect from spec §2.2 in the same record: the
  scenario's "WSJT-X reports normal SNR" condition is vacuous at the clamp.
- **The reference caveat, stated once.** "Attributable to OpenWSFZ" means one-sided disagreement
  with WSJT-X on identical samples, where WSJT-X is the reference the openspec scenario itself
  names. The gate does not measure true SNR (spec §1.2).
- **No fix is prescribed in the record.** The June mechanism-1 attribution is a lead, not a finding
  of this run. Any `src/` work goes through HK-011, with a separate Developer session and the
  Captain's pre-push sign-off.

## 4. Artefacts and housekeeping

QA's result file and harness are committed locally on `qa/2026-09-09-s1-ladder-substrate-proposal`
(`3996151`) and are not pushed. Before any push, QA strikes the two passages named in §2 on its
own branch. Pushing is the Captain's go-ahead, per HK-033.

**Minor items for QA's file:** these do not affect any figure, and 0a's exact reproduction is the
guard that makes them harmless.

- §4 histogram: the "(mode)" label sits on bin `+0` (4,451), but bin `+1` (4,521) is the mode.
- The harness docstring's opening lines say Part B's `load()` is imported. The function's own
  docstring says it was kept local. The report says the join was reused by import. In fact only
  `wildcard_match`, `clopper_pearson` and `ts_to_dt` are imported. The loader and the candidate
  enumeration are new code, and 0a is exactly the check that covers new code here. Say so.
- The headline calls my §2.1 a "June-era hope that D-003 might be confined to a retired
  mechanism". §2.1 expresses no such hope. It says the June figures are not a baseline, and that
  D-003 was untested on shims ≥ `20260046`. What the result contradicts is my §4 prediction
  (0.5% central, 0.05–3%). Cite that instead.

NFR-021: this ruling contains only aggregate counts, rates, medians and SHA/commit prefixes. The
review script lives in the Architect's session scratchpad and is not committed.
