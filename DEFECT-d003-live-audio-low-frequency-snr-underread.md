# Defect: D-003 — Below 600 Hz, OpenWSFZ Under-Reads Live SNR by ~8 dB, One-Sided Against WSJT-X

**Raised by:** QA, 2026-09-10 (16:03 UTC, `date -u`, per HK-017), per the Architect's acceptance
ruling §3 (`qa/rr-study/2026-09-10-1556-architect-d003-live-acceptance-ruling.md`, `arch/d003-live`
`1d09325`) on QA's own `D003-LIVE` measurement, ROW 2
(`qa/rr-study/2026-09-10-1550-qa-to-architect-d003-live-result.md`).
**Severity:** High — confirmed, live, current binary, one-sided. Blocks synth-into-real for any
SNR-reading deliverable (an S1 bias/R&R study, or any `F`-type minimum statistic where one misread
sets the answer) until resolved or otherwise mitigated.
**Affects:** Reported SNR on live (non-synthetic) FT8 decodes, dominantly below ~600 Hz audio offset,
on the current binary (shim ≥`20260046`). Likely locus: the local noise-floor estimation path shared
with D-002/D-004 (`compute_local_noise_floor_db`, `src/OpenWSFZ.Ft8/Native/ft8_shim.c`) — **not
measured here**; see §5.
**No fix proposed here.** Per HK-011/HK-015 this is QA-authored; any `src/` investigation or fix
routes to a separate Developer session with the Captain's pre-push sign-off.

---

## 1. The defect, leading with the band

On identical live audio, samples where OpenWSFZ's decoded audio offset is **below 600 Hz** show a
band-wide SNR level shift relative to WSJT-X: local median `delta` (OpenWSFZ − WSJT-X) is **−10 dB**,
against **−2 dB** for the corpus overall — roughly an **8 dB** relative under-read, and it is
**one-sided**: 296 station-hour clusters are under-read-dominant there, **zero** are over-read-
dominant. This is a band-wide shift, not a scattering of individual misreads.

**Every slice below carries its mirror** (`R_o`, the over-read rate), per the Architect's ruling §3
— a slice's `R_u` alone shows disagreement, not which side is misreading:

| slice | `n_u` | local median `delta` | `k_u` / `R_u` | `k_o` / `R_o` | clusters `U` / `O` |
|---|---:|---:|---:|---:|---:|
| `freq_ow < 600 Hz` | 5,947 | −10.0 dB | 2,062 / 34.67% | 6 / 0.10% | 296 / 0 |
| `freq_ow ≥ 600 Hz` | 48,995 | −1.0 dB | 604 / 1.23% | 900 / 1.84% | 295 / 367 |

**≥600 Hz shows no D-003 signature and is not evidence of this defect.** There, under-reads are
*fewer* than over-reads (604 vs 900). Disagreement of ≥10 dB is still material in both directions
there (`R_u = 1.23%`, `R_o = 1.84%`, ~7–11× the bar below), but it is the "material, not
attributable" pattern, not this defect. **Never cite "the ≥600 Hz slice clears the bar" as a D-003
finding** — it measures a different thing (undirected disagreement) than the below-600 Hz band does
(one-sided under-read).

**Gate outcome (the pooled figure — cited as the trigger, not as the defect's description):**
pooled over both bands, `R_u = 2,666/54,942 = 4.8524%`, combined CI `[4.1823%, 5.5111%]`, against the
programme's bar `R_STAR = 0.17%` (`σ²_rep(S1)/10²`, PO-ratified) — clears by ~25–32×. Cluster sign
test `U = 591` vs `O = 367`, `p_sign = 2.29×10⁻¹³`. This is what fired ROW 2 of the pre-registered
`D003-LIVE` check; it is a mixture of the two bands above and should not stand in for either.

**Reference caveat, stated once:** "attributable to OpenWSFZ" means one-sided disagreement against
WSJT-X on identical samples, where WSJT-X is the reference the openspec scenario below itself names.
The gate does not, and cannot, measure true SNR (spec §1.2 of
`2026-09-10-1536-architect-to-qa-s1-ladder-reply-and-d003-live-spec.md`) — no independent noise
measurement exists on this substrate. Same device, ruling out a passband explanation: OpenWSFZ and
WSJT-X #1 both read `Voicemeeter Out B1` (`contents.md`:34,:68), so the disagreement comes from how
the two programs estimate SNR from identical input, not from the radio audio chain.

## 2. The openspec violation, and a scoping defect in the same scenario

`openspec/specs/ft8-decoder/spec.md:104-107` (*"No SNR values below −30 dB when WSJT-X reports
normal SNR for the same message"* — this is the scenario that names D-003 by class):

```
V = 6 pairs with snr_ow <= -31 (a stricter cut than the scenario's -30, still a clean instance)
V_cens   = 3   (WSJT-X itself reads the clamp floor, -24 -- see below)
V_uncens = 3   (WSJT-X reads well above -24 -- an uncensored violation)
```

`V_uncens = 3 ≥ 1`: three decodes report `snr_ow ≤ −31` while WSJT-X — not itself clamped on those
three — reads them well above that. Small-`n`, but a clean, uncensored instance of the same
mechanism this record's ROW 2 establishes at scale, not an independent finding.

**Scoping defect in the scenario itself:** WSJT-X #1's SNR readout is clamped at −24 dB over the
whole frozen span (0 of 91,046 readings below it; a spike of 3,099 at exactly −24 against 1,004 at
−23). The scenario's precondition — "WSJT-X reports an SNR within its normal range (≥ −24 dB)" — is
therefore **vacuous**: every WSJT-X decode satisfies it, including ones the clamp has itself
distorted. As written, the scenario can be tripped by a genuinely weak signal that WSJT-X clamps to
−24 while OpenWSFZ correctly reports it lower, which is not a misread. This record's `V_cens = 3`
pairs are exactly that ambiguous case, and are **not** counted as violations above for this reason.
The scenario's precondition should be tightened (e.g. to an uncensored WSJT-X reading) before it is
relied on again — no fix is proposed here (§5).

## 3. Field history and why this is a live, current finding

- Live matched-pair incidence at `|delta| ≥ 10 dB` has been seen before: 2.1% at shim `20260010`
  (`qa/endurance/2026-06-13-b3446c8/report.md`) and 12.1% at `20260012`
  (`qa/endurance/2026-06-14-582bd69/report.md` §3.3), with **two** mechanisms identified there: (1)
  low-frequency sideband contamination below ~600 Hz from DC/hum, and (2) adjacent-strong-signal
  contamination of the 32-bin sideband window.
- **Those June figures are not a baseline** — they predate `c3a9ea8` (the `time_offset` SNR-collapse
  fix), use an uncentred metric, and cannot be compared against this record's figures in either
  direction. They show only that the phenomenon is instrumentable and has occurred before.
- **D-003 was untested on any shim ≥`20260046` before this measurement.** This record is therefore
  the first live confirmation that a D-003-class mechanism is active on the current binary, not a
  re-occurrence of a known-open issue.
- The band this record measures (**below** 600 Hz) matches June mechanism 1's frequency region.
  **Consistency with mechanism 1 is a lead, not a finding of this run** — the estimator mechanism
  was not measured here (§5).
- Separately, `openspec/specs/ft8-decoder/spec.md:93-97`'s frequency-invariance requirement records
  that D-003 (together with D-004) was formally addressed by moving to a per-signal local noise
  floor, closing a *high*-frequency (2800–3000 Hz) rolloff defect. This record's finding sits in a
  *different* frequency region (below 600 Hz) and was measured on live audio, not the synthesised
  S1 scenario that requirement's own validation scenario (spec.md:99-102) prescribes. **Whether the
  formal ±2.0/±4.0 dB region-consistency bound in that requirement is itself violated is not
  established here** — that would need the S1-prescribed synthesised comparison, which this record
  does not perform. Noted as context, not claimed.

## 4. What is NOT established

- **The estimator mechanism.** June mechanism 1 (DC/hum contaminating the local noise floor below
  ~600 Hz) is a lead, consistent with the band this record measures, and nothing more. Not measured
  here.
- **Whether mechanism 2** (adjacent-strong-signal contamination) contributes at all on this shim —
  not distinguished from mechanism 1 by anything in this record.
- **The exploratory 1000 Hz sub-split** in the result file (600–1000 Hz still under-read-dominant,
  ≥1000 Hz reversing) is a post-hoc, non-pre-registered cut (HK-021(y)) and is a hypothesis about
  tapering, not a result.
- **The correction shape**, if any — an estimator fix, a scoping change to the affected band, or
  something else — is genuinely open and is not decided by this record.
- **Whether the rate is stable** over time, hardware, or propagation conditions beyond the one frozen
  span this record measures (`FP-FLOOR-LIVE-2`, `[2026-09-08T19:36:45Z, close)`).

## 5. Recommended next step (not a fix)

Per HK-011/HK-015: a Developer session, with the Captain's sign-off, scoping an investigation of
`compute_local_noise_floor_db` (and any related low-frequency handling — DC/hum rejection, high-pass
staging ahead of the sideband window) for behaviour specific to audio offsets below ~600 Hz. **No
code change is proposed by this document.** The June mechanism-1 attribution is a lead for that
investigation, not a finding of this run.

## 6. Process

Per HK-015 this is QA-authored, on the Architect's acceptance ruling §3 clearing QA to author it
without further review. Per HK-011 nothing here touches `src/` — no fix is proposed. Per HK-014/HK-010
committed locally only; no push, no merge implied — push is the Captain's call (HK-033). Per HK-006 no
`pre_merge_check.py` run implied. Per NFR-021 only aggregate counts, rates, medians, and SHA/commit
prefixes appear here; scanned with the project's `nfr021_pre_merge_scan.py` `scan()` before commit —
0 flagged tokens.

## 7. Cross-references

- `qa/rr-study/2026-09-10-1550-qa-to-architect-d003-live-result.md` — the measurement (`ROW 2`),
  corrected in place per the ruling below.
- `qa/rr-study/2026-09-10-1556-architect-d003-live-acceptance-ruling.md` (`arch/d003-live`,
  `1d09325`) — the acceptance and the frequency-split correction this record is built on.
- `qa/rr-study/2026-09-10-1536-architect-to-qa-s1-ladder-reply-and-d003-live-spec.md` (`arch/d003-live`,
  `bd337f2`) — the pre-registered spec, `R_STAR` derivation, and §2.2's clamp finding.
- `qa/cycleframer-alignment-replay/d003_live.py` — the harness.
- `qa/endurance/2026-06-14-582bd69/report.md` §3.3, `qa/endurance/2026-06-13-b3446c8/report.md` —
  June field history (not a baseline).
- `openspec/specs/ft8-decoder/spec.md:93-97,99-102,104-107` — the frequency-invariance requirement
  and the two scenarios (S1 post-fix validation; the D-003-class scenario this record's §2 addresses).
- `DEFECT-snr-reported-gain-error.md` — D-002, a related but distinct SNR defect (a slope/gain error
  across the whole reported range); this record is D-003, a one-sided band-specific under-read. The
  two are independent per that record's §2.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c` — `compute_local_noise_floor_db`, the likely-locus function,
  not modified or measured directly here.

---

*Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>*
*Claude-Session: https://claude.ai/code/session_01NseChs8GHWxH7dJ8L9pwC2*
