# Reply: the S1-ladder substrate proposal. Two blockers, and one of them is measurable for free: spec `D003-LIVE`

**Architect, 2026-09-10 15:36Z** (`date -u`, HK-017). Branch `arch/d003-live`, cut from
`origin/main`@`4c33021`. Docs-only; `git diff --stat -- src/ native/` is empty.

Answers: QA's `2026-09-09-1706-qa-to-architect-fp-floor-live-2-audio-as-s1-ladder-substrate.md`
(`dee71da`, on `main` via #149).

✅ **`R_STAR = 0.17%` RATIFIED by the PO on 2026-09-10 at 15:44Z. The HOLD is LIFTED, and QA may
run §3.** ~~🛑 **HOLD. QA does not run §3 until the PO ratifies `R_STAR` (§5).**~~ The bar is now
frozen. It does not move after `R_u` is known, and that applies to everyone, including the PO and
me (§5).

---

## 1. The answer: synth-into-real is wanted in principle, but it has TWO blockers

The PO proposed this, and using real audio has already been proven right once (the FP-FLOOR-LIVE
withdrawal, §5). Your note is correct that D-003 has to be answered first. There is a second
blocker, and it is independent of the first.

### 1.1 Blocker 1, D-003: answerable from data already on disk, with no capture and no synthesis

See §3. The FP-FLOOR-LIVE-2 corpus pairs every OpenWSFZ decode with an independent WSJT-X reading
of the same transmission on the same audio path. A misread noise floor shows up directly in that
pairing as a large one-sided SNR disagreement.

### 1.2 Blocker 2, not measurable here: "true SNR" is undefined on a real substrate

An S1 ladder is an SNR bias and repeatability study, so it needs a known true SNR for every trial.
On synthetic AWGN the harness sets that value. On real band audio, the noise level under an injected
signal is whatever the band happens to supply, and it is non-stationary and full of other signals.
Two ways to supply it both fail:

- **libft8's own noise estimate cannot supply it.** Using the estimator under test to define the
  truth it is being tested against is HK-026.
- **Choosing a value means the bench measures the choice** (HK-021(d)).

A design needs an independent noise measurement that the physical system provides. I have not
designed one, and this document does not claim to. It is recorded so the blocker does not get
rediscovered after something has been built.

### 1.3 What is NOT blocked: extending S1's rungs on the existing wideband-AWGN path

Adding lower rungs to S1 on the current synthetic path (`run_scenario.py:249-257`, wideband, no
cutoff) has no exposure to D-003 and no truth problem. It gives up the realism the PO was after, and
that trade is **the PO's call**, not mine. It needs no answer from §3.

## 2. What the data already on disk says (no run: HK-018, HK-027)

### 2.1 D-003 has a field history and a normative scenario. It is untested on any current shim, not "untested"

- **Live matched-pair incidence (`OpenWSFZ − WSJT-X` SNR delta `≤ −10 dB`):** 2.1% at shim
  `20260010` (`qa/endurance/2026-06-13-b3446c8/report.md`) and **12.1%** at `20260012`
  (`qa/endurance/2026-06-14-582bd69/report.md` §3.3).
- **Two mechanisms were identified on `20260012`'s local noise floor:**
  - low-frequency sideband contamination below ~600 Hz, from DC and hum;
  - adjacent-strong-signal contamination of the 32-bin sideband.
  The "bandlimited noise" wording in `run_scenario.py:252` describes the older global-floor
  mechanism.
- **A normative scenario already exists** at `openspec/specs/ft8-decoder/spec.md:104-107`: *"No SNR
  values below −30 dB when WSJT-X reports normal SNR for the same message."*
- 🛑 **The June figures are NOT a baseline.** They come from a different shim era: before `c3a9ea8`,
  whose time_offset SNR collapse would *also* register as a matched-pair under-report. They also use
  an uncentred metric. Do not compare §3's number against them in either direction. They show that
  the metric is instrumentable and that the defect has occurred, nothing more.
- My withdrawal doc (`2026-09-08-1745-…` §2) says D-003 *"remains untested"*. That is accurate for
  every shim `≥ 20260046`, and too broad as a general statement. This paragraph is the precision.

### 2.2 🔴 The reference's SNR readout is CLAMPED at −24 dB

WSJT-X #1 over the frozen span: **0 of 91,046 decodes below −24**, and a spike of **3,099 at −24**
against 1,004 at −23. (This is the reference's own marginal distribution, computed with no pairing
and no OpenWSFZ join, so it is not the §3 outcome.)

- Any paired delta at WSJT-X = −24 is **censored.** The reference's true reading may be lower, so
  the observed delta can only **overstate** an OpenWSFZ under-read. §3 therefore excludes those
  pairs from the incidence and says which direction that biases the figure.
- **The openspec scenario's condition "WSJT-X reports ≥ −24" is vacuous:** every WSJT-X decode
  satisfies it. As written, the scenario can be tripped by a genuinely weak signal that WSJT-X
  clamps to −24 while OpenWSFZ reports it at its own level, and that shows no misread
  (HK-021(x)). §3 reports its count split by censoring. It calls only the uncensored ones
  violations.

### 2.3 🔴 The corpus's reference half was never in the corpus. Now snapshotted, and B turns out to be EMPTY

Part B's harness read WSJT-X from `%LOCALAPPDATA%`, which is outside `artefacts/`. Both files are now
copied into `artefacts/20260908_live_run_1827-fp-floor-live-2/wsjtx-{1-ft991a,2-sdruno}/`, with a
record in `wsjtx-SNAPSHOT.md`:

- **A:** SHA256 `dda9483aaee6…529d`, which matches Part B's recorded 0a prefix, so the file is
  unchanged since Part B ran.
- **B: 0 bytes, last written 18:16Z on 2026-09-08,** before the 18:33Z capture start. B's log holds
  nothing for this run. Part B's §4 statement *"confirmed mechanically: zero qualifying lines"* is
  **vacuous**, because an empty file passes any absence check. "No B coverage" still holds, but on
  the 18:52:45Z stop in `contents.md`'s timeline, not on the file. **`K_removed` is unaffected**:
  REF = A only, and B was never read.

## 3. SPEC `D003-LIVE`: does OpenWSFZ misread SNR on live audio, on the current binary?

### 3.1 Population and reference (fixed)

- **Corpus:** `artefacts/20260908_live_run_1827-fp-floor-live-2`, with the frozen span
  `[2026-09-08T19:36:45Z, 17:22:00Z close]` (Amendment 3). Nothing is re-examined.
- **REF:** WSJT-X #1, read from **the snapshot** (`wsjtx-1-ft991a/ALL.TXT`), **never from
  AppData.**
- **Join:** Part B's, reused **by import**: same cycle, `|Δf| ≤ 3 Hz`, `wildcard_match`. Do not
  write a new implementation.

### 3.2 The predicate, as code. Where this and the prose disagree, the code is the spec (HK-021(r))

```python
REF_SHA256   = "dda9483aaee6295369f8b51cb8057fc6fef054be84772f2fd003fdc3f65b529d"
WSJTX_FLOOR  = -24          # reference clamp (§2.2)
SIGMA2_REP   = 0.17         # S1 Repeatability sigma^2, dB^2: results/2026-09-07-4cc1984/report.md:41
TAIL_DB      = 10           # D-003's field definition (June reports); >= 10x the 1 dB readout quantum
R_STAR       = SIGMA2_REP / TAIL_DB**2      # = 0.0017. PO-RATIFIED 2026-09-10 15:44Z, FROZEN
assert abs(R_STAR - 0.0017) < 1e-12

assert sha256(REF_PATH) == REF_SHA256                        # harness STOPS on failure (not a row)
assert min(wsjtx_snr_all_in_span) == WSJTX_FLOOR             # clamp model holds; STOP on failure
assert count(wsjtx_snr_all_in_span < WSJTX_FLOOR) == 0

# candidates(d) = WSJT-X#1 decodes, same ts as OpenWSFZ decode d, |df| <= 3, wildcard_match(d.msg, cand.msg)
# ASSIGN_EXCL : keep d iff len(candidates) == 1
# ASSIGN_NEAR : keep d iff len(candidates) >= 1; choose min |df|, then exact text over wildcard,
#               then lower WSJT-X freq
for ASSIGN in (ASSIGN_EXCL, ASSIGN_NEAR):
    delta      = snr_ow - snr_wsjtx                          # both integer dB
    uncensored = snr_wsjtx >= WSJTX_FLOOR + 1                # -23 and up
    c          = median(delta[uncensored])                   # centre; absorbs any level offset (D-004)
    under      = uncensored & (delta - c <= -TAIL_DB)        # SIGNED: D-003 is one-sided (HK-021(l))
    over       = uncensored & (delta - c >= +TAIL_DB)        # the mirror: the base rate (HK-021(u))
    n_u, k_u, k_o = uncensored.sum(), under.sum(), over.sum()
    R_u, R_o   = k_u / n_u, k_o / n_u
    cluster    = (freq_ow // 10, int((ts - BOUNDARY).total_seconds() // 3600))   # ~a station-hour
    # CI(R_u): lo = min(CP95_lo, boot_lo), hi = max(CP95_hi, boot_hi)
    #   boot = 2,000-draw percentile cluster bootstrap, seed 20260910, cluster keys SORTED at construction
    # Sign test, CLUSTER level (HK-021(i)): among clusters holding >= 1 tail pair,
    #   U = #clusters with n_under > n_over, O = #clusters with n_over > n_under, ties dropped
    #   p_sign = binom.sf(U - 1, U + O, 0.5)                 # one-sided, P(X >= U)
```

### 3.3 ROW 0: validity preconditions. Evaluate all of them. HK-025: you may refuse any of them

| row | check | class, and why |
|---|---|---|
| **0a** | Under `ASSIGN_NEAR`, the join reproduces Part B **exactly**: 57,969 OpenWSFZ decodes in span; **55,607** corroborated; **313** corroborated at `snr_ow ≤ −24`; **6** corroborated at `snr_ow ≤ −31` (Part B's `K(s)` bins −36: 1, −32: 1, −31: 4). Any mismatch fires the row. | VALIDITY: a different join means a delta over different pairs |
| **0b** | The full reading rule (§3.4) gives the **same row** under `ASSIGN_EXCL` and `ASSIGN_NEAR`. If the rows differ, the row fires. | VALIDITY: unresolved assignment ignorance straddles a threshold (HK-021(w)) |
| **0c** | `delta[uncensored]` takes **≥ 5 distinct values** | VALIDITY, and a guard against the degenerate limit (HK-021(n)). A broken delta (reference parsed as a constant, or OpenWSFZ compared with itself) gives `k_u = k_o = 0`, which would otherwise read as ROW 1 "not material" |

Any ROW 0 fires ⇒ **ROW 5, VOID.** No rate is quoted, not even descriptively.

**The (k) check, which I ran on my own draft:** all three rows are VALIDITY, so the both-branch
evaluation does not apply. No row is precision-only.

### 3.4 Reading rule: strict order, exactly one row fires

| row | fires iff | meaning |
|---|---|---|
| **ROW 1** | `hi(R_u) ≤ R_STAR` | Live ≥10 dB under-reads are **below** the rate that would double S1's repeatability variance. **Not material.** |
| **ROW 2** | `lo(R_u) ≥ R_STAR` **and** `p_sign < 0.05` | **D-003 active and attributable to OpenWSFZ.** Under-reads are material and one-sided against their own mirror. |
| **ROW 3** | `lo(R_u) ≥ R_STAR` **and** `p_sign ≥ 0.05` | **Material disagreement, NOT attributable.** The two estimators disagree by ≥10 dB at a material rate, but no more one way than the other. |
| **ROW 4** | none of the above | **Straddle.** Decided by position, not width (HK-021(w)). |

**Why ROW 3 exists (HK-021(a): write the rule so it can express the true answer).** Mis-paired
decodes, and WSJT-X's own errors, inflate **both** tails. Only a one-sided excess implicates
OpenWSFZ. With ROW 3 absent, a noisy reference would fire ROW 2.

**Why `R_STAR = σ²_rep / 10²`, derived rather than chosen.** A misread of at least 10 dB at rate `r`
adds at least `100·r` dB² to the variance of SNR readings. At `r = 0.17%` that equals S1's entire
measured repeatability variance (0.17 dB²). Above it, an SNR ladder on this substrate would be
dominated by misreads. The inputs are a measured figure and D-003's field definition, and neither was
chosen with this outcome in view.

### 3.5 Consequences

- **ROW 1:** the D-003 blocker on synth-into-real (§1.1) is lifted. §1.2 remains, and I draft that
  design next, for the PO.
- **ROW 2:** synth-into-real is **blocked** for any SNR-reading deliverable (an S1 bias/R&R study, or
  any `F`-type minimum statistic, where one misread sets the answer). QA may author a D-003 defect
  record or dev-task carrying the rate and the frequency split (HK-015); any `src/` work goes through
  HK-011. §1.3's wideband extension is unaffected.
- **ROW 3:** draft nothing. Synth-into-real stays blocked on D-003 grounds, because this instrument
  cannot clear it. Only a reference with known truth could make the attribution. That is noted here,
  not proposed.
- **ROW 4:** report and draft nothing. Synth-into-real stays blocked.
- **ROW 5:** VOID. Nothing is quoted.

### 3.6 Report (HK-001, plus)

1. The row, and **under both assignments:** `n_u`, `c`, `k_u`, `k_o`; `R_u` and `R_o` **in the same
   sentence** (HK-021(u)); CP95 and cluster-bootstrap intervals **separately**; the number of
   clusters; `U`, `O`, `p_sign`. Also the censored-pair count.
2. A histogram of `delta − c` over `uncensored`, in integer bins.
3. ~~**Descriptive:** `R_u` for `freq_ow < 600 Hz` and `≥ 600 Hz`.~~ ⛔ **STRUCK 2026-09-10 15:56Z
   by the Architect (my error):** this asked for `R_u` per slice **without `R_o`**, which breaks
   HK-021(u) as applied to the headline above. A slice's `R_u` alone measures disagreement, not
   attribution. **Corrected: `R_u` AND `R_o`, plus cluster `U`/`O`, for each slice.** With the
   mirror, the one-sidedness sits entirely below 600 Hz, and above 600 Hz `k_u < k_o`. See
   `2026-09-10-1556-architect-d003-live-acceptance-ruling.md` §2. The 600 Hz boundary is taken from
   June mechanism 1's report, not from this data.
4. **Descriptive, and it does NOT reopen Part B's ROW 2 (closed, accepted `3e997e0`):** the 313
   corroborated-removed pairs split into:
   - (a) WSJT-X = −24, censored (the reference also puts them at the floor);
   - (b) uncensored and `under` (the misread class);
   - (c) uncensored and not `under`.

   This bears on *why* `T` costs genuine decodes, not on *whether* it does.
5. **The openspec scenario (§2.2):** `V = #pairs with snr_ow ≤ −31` (expected 6, per 0a), split into
   `V_cens` (WSJT-X = −24) and `V_uncens`.
   - `V_uncens ≥ 1` is reported as a **violation with an uncensored reference**, and QA decides
     whether to raise a defect (HK-015).
   - `V_cens` pairs are **not** called violations (the §2.2 scoping defect).
6. 🔒 **NFR-021:** aggregates only, with no `message_text`. Scan the harness and the report **prose**
   with an imported `scan()`.

**Direction of each bias, to be stated in the report:**
- Excluding censored pairs makes `R_u` a **lower** bound on OpenWSFZ under-read incidence, because it
  hides under-reads of signals WSJT-X reads at −24.
- Reference over-reads land in `under`; the sign test is what separates them.

## 4. Resolution, power and prediction (HK-021(m)/(v), stated before the run)

- `n_u ∈ [52,508, 55,607]`: 55,607 corroborated, less at most the 3,099 reference readings at −24.
- **Binomial straddle band around `R_STAR`, computed:** ROW 1 needs `k_u ≤ 70` (0.133%); `lo ≥ R_STAR`
  needs `k_u ≥ 109` (0.208%) at the low `n_u`, and `≤ 75`/`≥ 115` at the high end.
- **The cluster bootstrap will widen this band by a design effect I cannot compute without the
  outcome.** ROW 4 is therefore likelier than the binomial band suggests. I have declared this rather
  than estimated it.
- **My prediction:**
  - central `R_u ≈ 0.5%`, range 0.05–3%;
  - ROW 2 ~50%, ROW 1 ~25%, ROW 4 ~15%, ROW 3 ~10%.

  At 0.5%, `lo` clears `R_STAR` with near certainty, even at a design effect of 4, so the gate can see
  the value I expect (v).
- ⚠️ **Discount the prediction.** My record on categorical row calls is ~1 in 3 (HK-021 calibration),
  and my last one (FP-FLOOR-LIVE ROW 1, 0.5–4%) missed by more than 10×.

## 5. Decisions for the PO

1. ✅ **`R_STAR = 0.17%` RATIFIED on 2026-09-10 at 15:44Z (PO: "0.17% is approved").** It is now
   frozen. If anyone proposes moving it after `R_u` is known (the Captain, the PO or me), refuse and
   escalate. That is the prohibited re-read, and it would VOID the arm.
2. **Optional, and independent of §3:** whether to extend S1's rungs on the wideband-AWGN path now
   (§1.3).

## 6. What this does NOT do

- It does not reopen `FP-FLOOR-LIVE-2` Part B (ROW 2 accepted), `FP-PARITY` ROW 3, or any
  `FP-REGRESSION` guard. It creates no baseline.
- It authorises no `src/` work in any row.
- No capture run. Everything is on disk.
