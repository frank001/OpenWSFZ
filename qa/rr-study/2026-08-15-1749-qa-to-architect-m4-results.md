# M4 results — M1's question re-asked at the corrected anchor

**QA → Architect** · 2026-08-15 17:49Z · branch `feat/r1b-sync-refiner-instrument-correction`
Spec: `qa/rr-study/2026-08-15-1658-architect-to-qa-m4-corrected-anchor-spec.md`.
Harness: `qa/rr-study/m4-corrected-anchor/` (new, committed with this report).
DLL SHA256 `04cedc598593e89569b7212deef66efaa413322994216108841525ca2ebc45bf`,
`FT8_SHIM_VERSION` 20260041 — asserted at load, matches M1/M2/M3/R1b exactly.

**Blocking precondition discharged before arming:** the M2 and M3 harnesses, results
and reports were committed at `961c12b` (they were sitting untracked while the board
already described their findings as established — spec's own top-of-document warning).

---

## 0. Verdict, up front

**ROW 2 fires: `rho_conc` = −0.0241, 95% CI [−0.0363, −0.0119], p ≈ 0.0001 (z=−3.89).**
`|rho_conc| ≤ 0.10` and `CI_hi < 0.30` — both ROW 2 conditions met, cleanly.

**But read §4 before treating this as settled.** This run surfaced a finding the spec
did not anticipate: HIT and MISS rows (both WSJT-X-anchored) show a strong, coherent
**residual positive bias** in signed `coarse_dt_samp` at the corrected anchor — not
noise, not what NULL shows. It is reported, not corrected for, and not folded into the
gate (§10 of the spec prohibits any anchor re-derivation in this round) — but it bears
directly on whether ROW 2's "the refiner does not locate real signals" reading is safe
to accept as stated, or whether it is measuring a still-slightly-short anchor. **QA is
flagging this, not resolving it (HK-015).**

---

## 1. Population and run

51,586 rows called, 1 call each, 0 `rc != 0`, 0 stopped early. 1,052.2 s (20.40 ms/row).

| Arm | n |
|---|---|
| HIT | 20,892 |
| MISS | 14,082 |
| NULL | 16,212 |
| CONTROL | 400 |
| **Total** | **51,586** |

Population reused verbatim: M1's manifest in full (no subsampling, no reseeding) +
M2's positive-control manifest verbatim. Both match the spec's §5.1 table exactly
(dry-run count checked before arming).

---

## 2. HK-025 — re-derived independently before evaluating

Concurs with the spec's own §7 table: all four ROW 0s are VALIDITY, none is
DIAGNOSTIC (both branches route to genuinely different actions in every case). No
refusal. Full reasoning in `m4_evaluate.m4_hk025_check()`'s docstring.

---

## 3. Gate, in strict order

| Row | Condition | Measured | Bar | Fires? |
|---|---|---|---|---|
| 0a | control median `\|coarse\|` ≤ 3, no `rc!=0`, control `dt_offset`=0 | median=1.000, `rc!=0`=0, offset OK | ≤3 | **No** |
| 0b | ≥4 strata with ≥200 both arms | 7/7 strata OK | ≥4 | **No** |
| 0c | railed fraction ≤25% both arms | HIT **24.46%**, NULL 16.73% | ≤25% | **No — HIT within 0.54pp of firing** |
| 0d | NULL median \|signed\| ≤2 steps **OR** slope test | see §5 | both | **No — see §5, neither condition clears its own bar, but not by much** |
| 1 | `rho_conc`≥0.30 & CI_lo>0.10 | −0.0241 / −0.0119 | — | No |
| 2 | \|`rho_conc`\|≤0.10 & CI_hi<0.30 | 0.0241 / −0.0119 | — | **YES** |

**>>> ROW 2 <<<**

ROW 0a and 0b pass with comfortable margin. **ROW 0c passes but HIT sits at 24.46%
against a 25% bar — 0.54 percentage points from firing**, worth carrying forward as a
margin note, not a pass-and-forget. ROW 0d does not fire, but see §5 — it is close on
both of its two independent conditions, not just one.

---

## 4. THE HEADLINE CAVEAT — a residual bias in real-signal rows, not in NULL

Recomputed directly from `m4_results.json`, not anticipated by the spec:

| Arm | median (abs) | median (signed) | mean (signed) | % positive | % negative | railed at **+12** | railed at **−12** |
|---|---|---|---|---|---|---|---|
| HIT | 8.0 | **+8.0** | +6.77 | **87.2%** | 9.5% | 5,089 | 21 (242:1) |
| MISS | 8.0 | **+7.0** | +5.68 | **81.7%** | 15.3% | 2,909 | 274 (10.6:1) |
| NULL | 8.0 | −2.0 | −0.95 | 43.3% | 53.6% | 1,168 | 1,545 (0.76:1) |
| CONTROL | 1.0 | — | — | — | — | 0 | 0 |

**HIT and MISS — both anchored at WSJT-X's own reported (freq, DT), the same way M1
built them — sit overwhelmingly on the POSITIVE side of the coarse grid, railing at
+12 almost exclusively (242:1 and 10.6:1).** NULL, by contrast, is close to balanced
(0.76:1) and matches its own already-established buffer-origin attractor (M4 spec §3).

**Reading, offered as a hypothesis, not asserted as a finding:** the corrected anchor
(`anchor_dt_s + 0.45`) may itself still be short for real-signal positions by roughly
another 7–8 coarse samples (**35–40 ms**), specifically and consistently on HIT/MISS,
not on NULL. Supporting evidence: **S2 (HIT vs MISS positional `rho_conc`) = 0.0074,
CI [−0.0064, 0.0211] — statistically indistinguishable from zero** (§7), meaning HIT
and MISS share this same residual bias to within noise, which is exactly what "a
property of the anchor construction, not of decodability" would look like. This is
also very likely what is driving ROW 0c's HIT fraction to within 0.54pp of its bar —
HIT rows pegging the +12 rail while trying to reach a true peak the fixed anchor still
undershoots.

🛑 **QA has NOT acted on this** — no re-sweep, no re-derivation of the anchor, no
change to the gate (spec §10 prohibits all three in this round). It is reported because
it directly bears on how ROW 2's consequence should be read: **`rho_conc`'s negative
point estimate may be measuring "HIT is systematically pushed to one side of a still-
slightly-short anchor" rather than "the refiner cannot locate a real signal at all."**
Both readings are consistent with the same number. The Architect should weigh this
before treating ROW 2's "permanent" consequence (§6 of the spec) as settled.

---

## 5. ROW 0d in full — did not fire, but closer than a clean pass

**Condition 1 — NULL median signed `coarse_dt_samp`:**

```
measured = −2.000  (exactly)
bar:  fires if |median| > 2 steps (10 ms)
```

**Lands EXACTLY on the bar, on the non-firing side (strict `>`).** This is the SECOND
time in this programme NULL's own statistic has landed exactly on a pre-registered
ROW 0d bar by coincidence of value (M3: NULL median `dt_win` = exactly −0.150s, its own
bar). The M3 report's tie-break explanation was already shown not to fully cover the
first occurrence; a second exact-boundary landing on a differently-constructed
statistic (discrete coarse samples here vs. a continuous 0.05s sweep grid in M3)
suggests this is not coincidence-of-coincidence but something about NULL's distribution
shape itself sitting near these bars generally. Flagged, not explained, not acted on.

**Condition 2 — OLS slope, NULL signed `coarse_dt_samp` on `anchor_dt_s`, cluster-robust
(4,053 cycles):**

```
slope    = 1.0177 steps/s
SE       = 0.2212  (cluster-robust, CR1 sandwich, small-sample corrected)
p        = 0.000004
bar:  fires if p < 0.01 AND |slope| > 2.0 steps/s
```

**p clears its half of the bar by five orders of magnitude. The slope does not** —
1.02 is roughly half of the 2.0 bar. This is precisely the scenario the spec's own
conjunction was designed to separate: *"a statistically significant but physically
trivial slope is guaranteed [at this n], and a bare p would fire this row on nothing."*
The conjunction did its job — but the fact that **the highly-powered p-value is this
extreme while the effect size sits only 2x under the bar** means NULL's directional
dependence on `anchor_dt_s` is real and non-trivial, even though it does not clear the
pre-registered magnitude bar. Consistent with, not proof of, the buffer-origin
attractor mechanism the M4 spec's §3 already hypothesised at profile level.

**Neither condition is a comfortable pass. Both are close. ROW 0d correctly does not
fire per its own mechanical bar — this is reported exactly as computed, not softened,
per the spec's own instruction not to re-centre a blind bar against the observed
value.**

---

## 6. Full distributions against the uniform floor

Uniform-argmax floor (25-point coarse grid, spec §2): median **6.0**, mean **6.24**,
rail **8.0%**.

| Arm | median \|coarse\| | mean \|coarse\| | railed | vs uniform |
|---|---|---|---|---|
| HIT | 8.0 | 7.30 | 24.46% | worse than floor, 3.1× the rail |
| MISS | 8.0 | 7.30 | 22.60% | worse than floor, 2.8× the rail |
| NULL | 8.0 | 7.21 | 16.73% | worse than floor, 2.1× the rail |
| CONTROL | **1.0** | 1.40 | 0.0% | far better than floor |

**All three real arms sit worse than the no-information floor on this metric, exactly
as CONTROL shows the passing world looks like (median 1.0, 0% railed).** This is
consistent with §4's residual-bias reading: real rows are being pulled toward the rail
by a genuine, unresolved directional need, not merely "noisier than uniform".

`fine_dt_samp` — prohibited as a positional metric (spec §2.1), recorded only:

| Arm | median \|fine\| | mean \|fine\| |
|---|---|---|
| Uniform floor | 10.0 | 10.24 |
| HIT | 8.0 | 8.47 |
| MISS | 8.0 | 8.63 |
| NULL | 9.0 | 9.35 |
| CONTROL | 9.0 | 9.11 |

CONTROL (known truth) again sits at or worse than the uniform floor — R1b's −4.5ms
inter-stage origin disagreement still dominates Stage C, exactly as §2.1 predicted.
Not gated on, not read as a finding.

---

## 7. Secondary S1/S2 — computed, WITHHELD (ROW 2, not ROW 1)

Per spec §5.4, computed always and reported here with their number stated, but not as
findings:

| Statistic | Contrast | pooled | 95% CI | Status |
|---|---|---|---|---|
| S1 | HIT vs MISS, `score` | 0.0001 | [−0.0131, 0.0134] | **WITHHELD** |
| S2 | HIT vs MISS, position (`rho_conc`) | 0.0074 | [−0.0064, 0.0211] | **WITHHELD** |

Both sit at zero to within noise. **S2 is cited in §4 above only as supporting evidence
for the residual-bias hypothesis (HIT and MISS behaving identically), not as an
unblocked finding about the sync-vs-extraction question** — that question stays
withheld exactly as the gate requires.

---

## 8. Replication leg (spec §5.5) — flagged per spec's own instruction

M3's `dt_offset=+0.45` column supplies an independent 700 HIT + 700 NULL subsample
(100/stratum/arm), all 1,400 rows present (`n_missing_dt45_call=0`).

**Its pooled `rho_conc` is `nan` (row-if-gated-alone = ROW 3), which mechanically
disagrees with the primary's ROW 2.** Per spec: *"If the two legs land in different
ROWs, escalate rather than choosing one."* **Escalating, with the mechanical cause
identified, not resolved:**

`rho_conc` is lifted from `m1_evaluate.pooled_contrast` unchanged (spec's own
instruction). That function has its own hardcoded power floor, `STRATUM_MIN_N=200`
per arm per stratum. M3's replication subsample has exactly **100** HIT and **100**
NULL per stratum — by construction (spec S5.5 itself calls it "underpowered
(100/stratum/arm...) so it does NOT gate"). Every one of the 7 strata therefore reads
`power_ok=False` and is excluded from the pooled sum, giving `nan` — **not a
computation failure and not evidence of a wiring problem**, but the same power floor
that gates M4's own ROW 0b being applied, unmodified, to a leg the spec already knew
would be too small for it.

The per-stratum (unpooled) values, which ARE computed, for a qualitative check:

| Stratum | Fresh full run `rho_conc` (SE) | Replication `rho_conc` (SE≈0.08, n=100/100) |
|---|---|---|
| [−24,−21) | +0.0309 (0.043) | +0.0686 |
| [−21,−18) | −0.0450 (0.028) | −0.1074 |
| [−18,−15) | −0.0202 (0.018) | +0.0512 |
| [−15,−12) | −0.0555 (0.016) | +0.0609 |
| [−12,−9) | +0.0215 (0.016) | −0.0012 |
| [−9,−6) | +0.0035 (0.019) | +0.0428 |
| [−6,inf) | −0.0403 (0.010) | +0.0619 |

The two legs' per-stratum signs disagree in 4/7 strata, but **every replication value
is well within roughly one of its own ≈0.08 per-stratum SE of zero, and well within
noise of the corresponding fresh-run value** — this reads as sampling noise around a
small near-zero effect, not a contradiction of the primary's magnitude or its sign.
**QA is not choosing this reading over "escalate" — both are stated; the Architect
rules on whether the mechanical power-floor explanation discharges the escalation.**

---

## 9. Mandatory sign unit test (spec §5.3) — ran and passed before arming

`test_m4_rho_conc_sign.py`, 3/3 PASS. Both required assertions (`rho_conc==+1` when
every HIT row is strictly more concentrated than every NULL row; `==−1` reversed) are
asserted at the **per-stratum** `rho_rb` value, not the pooled one — perfect separation
by construction makes every cluster-bootstrap draw return an identical value, so
`se_bootstrap=0.0` exactly and `pooled_contrast`'s own inverse-variance pooling
(lifted unchanged) correctly excludes a zero-variance stratum from the pooled sum,
giving `pooled_rho_rb=nan` in that specific synthetic edge case. Documented as an
assertion in the test itself (`assert ... se_bootstrap == 0.0`), not silently worked
around. Real M4 data never approaches this degeneracy (§6's distributions all overlap
heavily), so it is a property of the synthetic sign-test construction only.

---

## 10. Scope discipline

No `src/` change. No Developer session. No ABI bump. No new DLL, no `FT8_SHIM_VERSION`
bump. No capture run. HK-011 not engaged. No widening of the coarse aperture, no
sweep, no argmax over anchors, no re-derivation of the anchor (§4's finding is reported
as data, not acted on). No re-read of M1/M2/M3's closed gates. R2 is not scoped,
proposed, or estimated in this document.

---

## 11. Consequence per spec §6 ROW 2 — stated, with §4's caveat attached

Per the pre-registered gate, ROW 2's consequence applies exactly as written:

- H2 (withdrawn at the M2 ruling) returns as the leading reading and must be
  re-argued from scratch, not resurrected as previously stated.
- R2 as framed is dead.
- The prohibition on citing R0/R1/R1b's ~1.1ms/0.5Hz figures for real signals becomes
  **PERMANENT**.
- The next round is instrument re-validation, not decode-path wiring.
- S1/S2 stay withheld (done, §7).

**QA is stating this consequence because the gate is mechanical and pre-registered —
not because §4's caveat has been resolved.** §4 raises a specific, evidenced question
(is the anchor still ~35-40ms short for real signals specifically?) that a clean ROW 2
reading would not by itself answer, and that this round's own scope (§10) prohibits
QA from chasing further. The Architect should rule on whether ROW 2's consequence
applies as stated, or whether §4 first needs its own narrow follow-up (a fixed,
finer-grained anchor check on HIT/MISS only, no sweep) before H2 is treated as settled.

---

## 12. Architect's predictions, scored

| Prediction | Credence | Outcome |
|---|---|---|
| ROW 1 | ~55% | MISS |
| ROW 2 | ~15% | **HIT** |
| ROW 3 | ~30% | MISS |
| `rho_conc` in 0.25–0.55 | range, 8/15 running | MISS (measured −0.0241, negative and far outside the range) |
| ROW 0d does not fire | ~70%, directional | HIT |
| HIT railed fraction < 12% at fixed anchor | ~65%, directional | **MISS (measured 24.46%, 2× the predicted ceiling)** |

The directional call on HIT railing was the more confident of the two directional
predictions (~65%) and missed by the largest margin — consistent with §4's finding
that HIT is being pulled toward the rail by something the spec did not anticipate.

---

## 13. Deliverables

1. `qa/rr-study/m4-corrected-anchor/` — `m4_common.py`, `m4_run_harness.py`,
   `m4_stats.py` (rho_conc lifted from `m1_evaluate.pooled_contrast`, cluster-robust
   OLS), `m4_evaluate.py`, `test_m4_rho_conc_sign.py`, committed with this report.
2. `results/m4_results.json`, `m4_gate_report.json`, `harness_run.log`,
   `m4_evaluate.log` — committed.
3. This report.
4. Board updated in the same edit (HK-024).

**QA does not author the next spec (HK-015). QA does not scope R2 (spec §10).**
