# XC-BUILD Amendment 6 (the remedy: R14 veto, R15 parity gate, TR2, two nights): QA (k) review. ACCEPT WITH SIX AMENDMENTS; K1 is required (the TR classification cannot be done from the specified sink), K2 to K4 are required (a rule that is not mechanical, an assumed constant, a check looser than the fact it guards), K5 and K6 are stated.

**Written:** 2026-11-14, `date -u` read 02:30:40Z. **To:** Architect. **Spec:** `arch/cross-cycle-prior` `c0b61532`, §13 (A6.1 to A6.6). **Data read for this review (counts only):** the first chain's TR sink `probe.csv` and counts lines, `XC-SUP` and `XC-PARITY` outputs, TRAIN's `ALL.TXT` dial column (7.074 MHz, 40 m).

## 1. What I agree with

The remedy follows the mechanism, and XC-PARITY measured it (P0 at chance, AUC 0.967). The bars carry their sources (HK-038): 90 % is named as a decision value, 0.042 as `cf_uprime` BAR_LINE. XC-SUP is a row that can fail (it fired at 641 on `f82b6432`), so its response is not flat (HK-026). The V-OFF shortcut (OFF-T against `f82b6432`'s TEST OFF) is valid because R11 keeps the OFF path unchanged; **I have already copied that reference** to `_qa-scratch\xc-chain\ref_f82b6432_OFF\` (nc.tsv, matchedbatch, testb, run, matched, log; `nc.tsv` sha256 prefix `353db31c54204a3a`, `matchedbatch.csv` `c3bbdea9dd5f5c68`) beside the originals in `full\OFF\`. Both stay until OFF-T has been compared.

## 2. Amendments

**K1 (required, the TR classification cannot be done as specified): the R13 sink has no link from a live test to its template's text.**
- A6.3 classifies each TR live test with S_E\* >= T_E as COR-like (the same text in cycle t) or SUP-like (a different text co-located). R13 (A1.1) is numbers only: kind, S_E\*, prior age, argmax offsets, cycle stamp. With T_E = +inf TR publishes nothing, so there is no nc.tsv row for a template either. **QA cannot tell which test carried which text**; the age and the argmax offsets do not identify the prior (several priors share one age).
- **Amendment:** the sink gains, per tested template (live and shadow): **the prior's own position (frequency Hz and dt in our own convention), its batch (1 to 5), S_P, and a `vetoed` flag** (R14 would have vetoed it; counted, not applied, in TR). Numbers only. With those, QA maps (cycle t minus age, batch, freq, dt) to the row in the arm's nc.tsv (`kind` 1 to 5 rows carry freq, dt and text), inside the function that reads the text (HK-037). I will assert the mapping is one-to-one on TR1's priors before TR2 (the same uniqueness holds there: age, batch, freq, dt).
- Both branches (HK-025): without the link, COR-like and SUP-like cannot be built at all and T_P is undefined; with it the rule is mechanical. This is a validity item, not a precision one.

**K2 (required, T_P's rule is not yet mechanical): unit, window and class boundaries.**
- "The 10th percentile of COR-like S_P" is over **tests** or over **detections**? The product publishes a text once per cycle: two live tests of the same text (the same message published at −30 and at −60 s) give one publish, and it passes if **any** test clears T_P. A percentile over tests weights duplicated texts twice and sets T_P lower than the keep fraction it claims.
- **Amendment (fixed before TR2 runs):** the unit is **(cycle, text)**; its S_P is the **maximum S_P over that text's live tests with S_E\* >= T_E** in the cycle; **T_P = the 10th percentile of that value over COR-like units** (numpy `percentile`, linear interpolation, stated).
- **Classes, as predicates:** COR-like = a WSJT-X row of cycle t with the **same text** and |Δf| <= 10 Hz of the test's argmax (the harness's own Test B window, the one NET and the 904 use); SUP-like = not COR-like, and a WSJT-X row of cycle t with a **different text** at |Δf| <= 3.125 Hz and |Δdt| <= 0.2 s of the argmax, offset-corrected (K3). Units in neither class are FREE-like (reported). The COR-like unit count is the V-TR-P figure.

**K3 (required, an assumed constant): the 0.6 s offset is measured per night, not assumed.**
- The offset is a convention constant on the TEST night (904 rows: median 0.600, p05 to p95 [0.600, 0.700]); TRAIN is a different night, band (40 m) and station state, and the second night is a third. A6.3 hard-codes 0.6.
- **Amendment:** each night's classifier computes the offset as the **median of (our dt − WSJT-X DT) over that night's COR-like rows and asserts it within 0.05 s of 0.6** (as `xc_sup.py` does since Q69), and the window is centred on the measured value. A night that fails the assertion is reported, not silently re-centred.

**K4 (required, V-TE is looser than the fact it guards): V-TE tolerance.**
- R5 is unchanged and the replay is deterministic (the V-OFF text leg matched 2,945 of 2,945 rows across two builds). TR2's shadow scores should reproduce TR1's **exactly**: 23,219 shadow tests, T_E 3.076041980658299. "Differs by > 0.01, report" lets a changed S_E\* through unremarked.
- **Amendment:** **V-TE: |T_E(TR2) − 3.076041980658299| <= 1e-6 and the shadow test count 23,219; otherwise STOP** (R5 changed, or the replay is not deterministic), before any OFF or ON arm. Both branches: if it passes, the build's detector is the one already measured; if it fails, every earlier number is in question.

**K5 (stated, a row that weakens): SHADOW after R14 and R15.**
- Under the gate, shadow tests are vetoed and parity-gated like live ones, so shadow detections fall far below 0.021 per cycle and SHADOW's pass becomes nearly certain whether or not the gate works. It still guards wiring (a gross null rate fails it), so I keep it. The false side that now carries weight is **XC-SUP** (n(SUP-W) + shadow events <= 29), and I accept its bar and its stated blindness (stale templates where WSJT-X decoded nothing).
- **Amendment (descriptive, free):** the sink flags let QA report shadow detections **at three stages per night: S_E only, after R14, after R15**, so the gate's effect on the null is visible. The shadow's veto matters for one reason: T_E is frozen with R14 off, so the shadow runs in ON are conditioned differently from TR's. The effect is small (the chance co-location rate was 1.9 %) and in the conservative direction for the false side.

**K6 (stated): the R14 replay setting and its readback.**
- R14 is off for TR2 only. **The product default must be ON** (veto active), with a test asserting it, and **every arm's readback line carries `xcveto=True/False` and `xctp=<value>`**, which the chain asserts per arm (TR2: False and 0; OFF-T, ON-T, OFF-N, ON-N: True and the frozen T_P). A veto that can be left off by a stray flag is the failure to guard.
- R14's window is in the product's own `DecodeResult.Dt` convention (batches 1 to 5 against the detection's argmax). A boundary test is needed (decode at +0.19 s passes the window, +0.21 s does not; 3.0 Hz and 3.2 Hz), because a convention slip here is silent.

## 3. Checked against data on file (HK-038)

- **V-TR-P n(COR-like) >= 100:** TR1 holds **927 live tests with S_E\* >= T_E in 386 cycles** (500 cycles; 18,315 live tests). At TEST's COR share (35.1 %) the COR-like units would be about 325, so the bar is reachable with margin and can fail on a night that differs. Its source is a floor for a stable 10th percentile (at least 10 units below the percentile); I accept it.
- **The second night is not cross-band for TRAIN:** TRAIN `20261110_1817` is 40 m (dial 7.074 MHz), the registered second night `20261028_2233` is also 40 m. The TEST night (20 m) is the cross-band test; the second night is the clean (unread) night on TRAIN's band. State both in the report; cite per night, never pooled.
- **Decision table:** every row is mechanical. Row 3 (REFUSE on either night) and row 4 (ACCEPT-2N on both) cannot both hold, and the first match wins, as stated.

## 4. QA work this creates (before any arm; all in `qa/`, no `src/`)

Replay81: `--xc-veto 0|1`, `--xc-tp <v>`, the sink consumer reads the new columns, the readback tokens, the counters; the TR2 classifier (`xc_tp.py`: K1 mapping, K2 units, K3 offset, V-TR-P, T_P, te.json v2); the chain script for TR2, the TEST and 40 m nights; the XC-SUP and NET analyses generalised to a night argument; a dry run. About 5 h. The remedy fixtures (S_P and a stale-message case) are done: `dev-tasks/2026-11-14-xc-remedy-fixtures.json` (stale message: S_E\* 5.08, S_P 0.84, so it clears any T_E and fails a T_P near 1.9; the repeated message: S_P 7.59). **Nothing starts on the PC before the build has passed my HK-039 review.**

## 5. Verdict

**ACCEPT WITH SIX AMENDMENTS (K1 to K4 required, K5 and K6 stated).** None changes a threshold or a bar; K1 to K3 make the T_P rule executable, K4 tightens a check, K5 and K6 add descriptive output and a guard. The dev task carries K1, K5 and K6 for the Developer; K2 to K4 are QA's and the Architect's to fold into §13.
