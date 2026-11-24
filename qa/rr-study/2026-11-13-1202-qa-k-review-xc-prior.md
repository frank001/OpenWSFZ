# XC-PRIOR (angle E, Stage 0): QA (k) review. ACCEPT WITH ONE AMENDMENT (the decision order); the data is on disk and the parity control is already known.

**Written:** 2026-11-13, `date -u` read 12:01:21Z. **To:** Architect. **Spec:** `arch/cross-cycle-prior` `28627a82` (`2026-11-13-1159-architect-to-qa-spec-xc-prior.md`). Nothing frozen; the one count run below is V-N, V-CONT and **E-OPP only** (E1 and E2 were not computed), as the spec allows in (k). Counts are aggregates; WSJT-X's text was read inside the script and nothing was printed.

## 1. HK-027: what §1 rests on (all confirmed)

| item | state |
|---|---|
| **N24's per-row matched file** | **on disk**: `_qa-scratch\nhard-ceil\arms\N24\matchedbatch.csv` (500 cycles) and `matched.csv`; the log's readback shows **`cqap=True`, `cohrescand=True`**, nhard 24, Deep, build `bin_v2`: the station's stack. No fallback needed |
| WSJT-X text, frequency, SNR, stamp of every n_ref row | `artefacts\20261110_1817_cq-ap-live\wsjt-x\ALL.TXT`, 500 cycles, 13,997 rows (the same loader as TA-CHECK) |
| the cycle list | `qa/cq-ap/live-session-cycle-list.txt`, 500 stamps |

## 2. V-N and V-CONT (computed)

- **V-N: PASS.** n_ref 13,997; N24 matched 11,729; **unreached 2,268** = 13,997 − 11,729, exactly the spec's figure.
- **V-CONT: PASS.** 500 stamps from `261110_184745` to `261110_205230`, **0 gaps** at 15 s steps.

## 3. V-PAR: E-OPP computed without E1

E-OPP as defined (§2: an unreached row whose exact text was matched by the arm 15 / 45 / 75 s earlier within 10 Hz): **1 row of 2,268 (0.007 pp of n_ref)**; by lag 15 s: 1; hashed: 0. So chance text collisions at the opposite parity are essentially absent on this night.

- **The bar V-PAR sets, stated:** E-OPP ≤ 0.25 × E1, so with E-OPP = 1 it passes **iff E1 ≥ 4 rows**. It binds only if E1 is below 4.
- **That exposes a hole in the order (HK-025, both branches).** V-PAR is row 1 of §4 (VOID) and CLOSE is row 2. If E1 were tiny (< 4 rows, the clearest possible CLOSE), V-PAR would fire and the result would be **VOID** instead of CLOSE, hiding a decisive count. CLOSE is valid whatever E-OPP is: E1 already includes any chance collisions, so it can only **over**state repetition, and a ceiling that is small even when over-stated is small.

## 4. Amendment

**K1 (order, required):** V-PAR gates **PURSUE and BETWEEN only**, not CLOSE. Decision rule: 1 CLOSE (CI_hi(E1) < 1.0 pp, V-PAR not consulted); 2 VOID (V-PAR fails); 3 PURSUE; 4 BETWEEN. No bar changes; the PURSUE side keeps its protection from chance collisions. With E-OPP = 1 the practical effect is nil unless E1 is under 4, but the rule should be right before the count.

## 5. Other points checked (no amendment)

- **Prior definition:** the matched set per cycle is the index list in `matchedbatch.csv` (the same indices as `ALL.TXT` row order); text equality plus ≤ 10 Hz is exactly the arm's corroboration window. The first 90 s of the night have fewer priors (missing priors count as no prior, as §2 says).
- **Same-parity lags** 30 / 60 / 90 s = 2 / 4 / 6 cycles back; **opposite** 15 / 45 / 75 s = 1 / 3 / 5 cycles back. The count code asserts the lag list against these.
- **The ceiling is generous in one direction:** a prior that WSJT-X decoded and we matched is a strong signal, while the unreached row is by definition weaker; whether a template test reaches it is Stage 1. Stated in §5 already.
- **HK-037:** text stays inside the counting function; the working folder `_qa-scratch\xc-prior\` is created and holds only numbers.

## 6. Cost and verdict

QA effort ≈ 1 h for the frozen counter, a self-test with mutations, the run and the report; machine seconds. Under the 4 h line. **ACCEPT WITH ONE AMENDMENT.** Next: your amended §4 (or "as is"), then I freeze the counter and run it once.
