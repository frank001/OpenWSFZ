# QA result — Arm S.1 (spectral locality, segment 1) — VOID on the mandatory null (Sec5)
# All six self-checks PASS. The reading rule is not reached. Escalating, not interpreting.

**Author:** QA, 2026-07-31 (17:25 UTC, `date -u`, per HK-017). Repo at `d9057af`.
**Executes:** work order `1356` task 2, per
`2026-07-31-1649-architect-arm-s1-spec-rev3-segment-1-execution-ready.md`.
**Prerequisite cleared:** `2026-07-31-1719-…-drift-screen-8081-20m-per-segment-result.md`
(segment 1 peak drift 0.136 s vs the 0.5 s bar).
**For:** the Architect and the Captain. **Not QA's to resolve** — per the spec's own §9,
none of rows 0/4/5 are QA's, and by the same standing stop rule neither is a pre-reading-rule
VOID. This is a report of the void, not an attempt to rescue or interpret it.
**Script + full mechanical report:** `measurement_s1_spectral_locality.py` /
`measurement_s1_report.md` (regenerable, not hand-edited).

---

## 1. Headline

**All six mandatory self-checks pass, several exactly.** The mandatory null (Sec5) then
**FAILS**: mean Δ_local across 20 within-cycle frequency shuffles is **+2.432 pts**, outside
the pre-registered ±2 pt band, and **every one of the 20 runs is positive** (range +0.44 to
+4.09, none negative). **Per Sec5, the arm is VOID. The reading rule in §4 is never reached.
The observed real-data Δ_local (+29.2 pts) and Δ_cycle (+26.9 pts) are not the arm's result
and must not be cited as one** — they are reported below only as the descriptive numbers the
null was checking, exactly as segment 2's void under Measurement D's self-check 2 still
quoted its own numbers for the record without treating them as a reading.

## 2. Self-checks — all pass, self-check 6 exactly

| # | check | result | bar | verdict |
|---|---|---:|---:|---|
| — | cutoff reproduction (`stratify_cycles`) | q1=23.0, q3=41.0 | pre-registered 23/41 | MATCH |
| 1 | matching gate | 9751 | 9751 exactly | PASS |
| 2 | density contrast | 2.65x | >= 2.0x | PASS (matches spec's own "expected 2.65x") |
| 2b | locality contrast | sparse gap 1.376, dense gap 1.770 | >= 1.0 both | PASS |
| 6 | cut reproduction (W=50) | sparse 1620/1631, dense 4359/3410 | exact match | **PASS, exact** |
| 3 | common support | 18 usable bins | >= 10 | PASS (matches spec's own "expected 18") |
| 4 | duplicate-key confound | gap 0.000 pts both axes | < 1/10 of effect | PASS |
| 5 | temporal composition | segment 1 is one contiguous session | by construction | PASS |

Self-check 6 reproducing **exactly** — 1620/1631 and 4359/3410, to the decode — is strong
corroboration that this implementation's `n_local`, the fixed per-stratum cuts, and the
matching mechanism are bit-for-bit consistent with the figures the rev3 spec pre-registered
(computed independently by the Architect's own scratch probe per §8). That matters for what
follows: **the null failure below is not attributable to an implementation divergence from
the pre-registered cuts** — the one self-check designed to catch exactly that (self-check 6)
passes exactly.

## 3. The mandatory null — FAIL

20 within-cycle shuffles of reference `freq_hz`, fixed seed `20260731` for reproducibility,
recomputing `n_local(50)` and Δ_local each time per the spec's own cut points (which "need no
re-derivation under it," per Sec5 — confirmed: usable-bin counts stayed at 18 for 18/20 runs,
17 for 2/20, consistent with the stratum-wide lo/hi cell totals being invariant under a
within-cycle permutation and only per-SNR-bin composition fluctuating).

| | value |
|---|---:|
| mean Δ_local across 20 shuffles | **+2.432 pts** |
| stdev | 0.992 pts |
| range | +0.435 to +4.090 pts |
| runs with Δ_local > 0 | **20 / 20** |
| bar | within ±2.0 pts of zero |
| **verdict** | **FAIL — arm is VOID per Sec5** |

**This is not noise scattered around zero — it is a small, consistent, one-sided bias.** That
shape matters for where QA looked next (§4), even though diagnosing it further is not QA's
call to make on the record.

## 4. A structural candidate, offered as a lead only — not a rationalisation

Per Sec5's own text: *"the locality metric is measuring something structural about how
frequencies are distributed."* One candidate, checked far enough to be worth naming but not
far enough to be asserted as settled:

Because permuting `freq_hz` within a cycle permutes a **fixed multiset of values**, the
resulting **multiset of `n_local` values per cycle is itself invariant under the shuffle** —
only which row (hence which SNR, which matched flag) ends up holding each value changes. The
null therefore only randomises the **within-cycle** pairing between a decode's local-crowding
label and its (SNR, matched) outcome. It cannot detect a **between-cycle** confound — e.g. if
larger/busier cycles (which mechanically contribute more "hi" cells, since more neighbours
means more decodes crossing the hi threshold) also happen to carry a different SNR
composition than smaller cycles, for reasons having nothing to do with true frequency
locality. Self-check 4 (duplicate-key) checks a different confound and reads clean (0.000 pts
both axes) — it does not check this one.

**This is a lead for whoever investigates the null failure, not a finding, and not grounds to
treat the void as resolved.** QA has not attempted to test it further; doing so would be
scoping a new measurement, which per HK-015 is the Architect's to design.

## 5. Descriptive only — not a reading, per Sec5's own instruction

| | value |
|---|---:|
| Δ_local (real data, W=50) | +29.219 pts (sparse stratum +30.495, dense stratum +27.944) |
| Δ_cycle (real data, W=50) | +26.899 pts |

Both would have fired reading-rule row 3 ("two sub-mechanisms," ratio ≈ 1.086) had the null
passed. **They did not, and per Sec5 this outcome is not to be read, cited, or averaged into
anything.** Recorded here solely so the void's magnitude is on the record, exactly as
`1602`'s segment-2 void still quoted its own contrast figure for context without treating it
as a result.

## 6. What this does not authorise or decide

- **S.2a's status is unchanged by this VOID** — it was already gated on S.1 firing row 2 or 3
  (`1649` §9), and S.1 fired **no row at all**. S.2a does not run on the strength of anything
  in §5 above.
- **No new arm, no rescue metric.** §4's lead is not an instruction to try a different
  locality definition until one passes its null — that is exactly the researcher-degree-of-
  freedom failure mode the pre-registration exists to prevent.
- **No `src/`, no rebuild** (HK-011) — frozen artefacts and Python only, as specified.
- **NFR-021:** aggregate counts and fitted numeric quantities only; no message text leaves
  `match_flags`/`duplicate_key_rate_in`.
- **Per HK-015** this is QA → Architect. Whether to revise the null's design, retire S.1
  entirely, or something else, is the Architect's call, and any further authorisation is the
  Captain's per HK-010/HK-011.

## 7. Cross-references

- `2026-07-31-1649-…-arm-s1-spec-rev3-segment-1-execution-ready.md` — the spec this executes;
  §5 is the null being reported VOID here, §6 the six self-checks all reported PASS above.
- `2026-07-31-1719-…-drift-screen-8081-20m-per-segment-result.md` — the cleared prerequisite.
- `2026-07-31-1602-…-segment-2-void-on-self-check-2.md` — the precedent this follows for how
  to report a VOID (quote the descriptive numbers, do not treat them as a reading).
- `qa/cycleframer-alignment-replay/measurement_s1_spectral_locality.py` /
  `measurement_s1_report.md` — the script and its full mechanical output.
