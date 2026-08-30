# `NBR-A` RESULT — ROW 0c VOID (calibration saturated), Part D run independently: DENSITY not COUNT

**QA → Architect.** 2026-08-29 21:01Z (`date -u`, HK-017). Runs on `qa/rr-study/f-nbr-a/`, offline,
synthetic, no `src/`/`native/` change, no live capture — per spec Sec.4.3/Amendment 1 Sec.0.
`libft8.dll` SHA256 asserted `bc8efcf1…b051d7f`, shim `20260046`, both copies (ROW 0a).

**Spec:** `2026-08-27-2100-…-spec-nbr-a-…` (`427a5cf`), §5 option 1. **Amendment 1:**
`2026-08-29-2023-…-AUTHORISED-amendment-1.md` (`6757586`). Captain authorised 2026-08-29 20:23:55Z.

**Headline: the gate VOIDs at ROW 0c — the calibration set never leaves the saturated zone, so the
ΔF sweep and reading rows (ROW 1–4, tone-contention vs tile-artefact) were correctly NOT run.**
**Part D, which is non-gating and does not depend on ROW 0c's L\*, WAS run at full N=100 and gives a
clean pre-registered reading: P2's failure is a DENSITY effect, not a signal-COUNT ceiling.**

---

## 0. New code, disclosed before results (HK-018/HK-021 identifiability)

The existing `qa/rr-study/f-nbr-a/` harness (`row0.py`, `part_c.py`) implements **F-NBR-A**
(2026-08-23, already closed) — a different arm with its own ROW 0 (corpus-reproduction checks) and
Parts A/B/C. `NBR-A`'s ROW 0a–0e, the ΔF sweep + autocorrelation reading, and Part D are **new**, so
I wrote `qa/rr-study/f-nbr-a/nbr_a.py`, reusing every existing primitive rather than duplicating them
(`dll_common.load_decoder`/`both_copies_match_pin`, `scene_render.render_scene`/`trial_seed`/mutation
helpers, `part_c.py`'s own "interferer E fixed, victim F moved/releveled" pattern, `harness.matcher`'s
match convention). Smoke-tested at N=5 before arming for real (informal, not gated, not cited as
data below) — confirmed the plumbing behaves sensibly: a Δ=100 Hz positive control hit 5/5, and the
Part D scene shapes reproduced the expected qualitative pattern.

**One implementation choice, disclosed:** the spec's `R(Δ, L)` names "victim level deficit L" without
giving the arithmetic. Amendment 1's own worked example — *"F-NBR-A swept ΔF at a −3 dB level
deficit … 0/100 at 6.25, 12.00 and 18.75 Hz"* — reproduces the **already-committed C2 sweep exactly**
(unmodified S8HN scene: F `snr_db=-8`, E `snr_db=-5`; −8 − (−5) = −3). This fixes the arithmetic
unambiguously: **`L = victim_snr_db − interferer_snr_db`** (E held fixed throughout). Applied
uniformly to ROW 0c/0d/0e and would have applied to the sweep. Part D's own three-signal scenes state
plain absolute `0 dB` values (spec §3) and do **not** use this convention.

**ROW 0b (determinism), also disclosed:** the spec names it as "two full runs … byte-identical" but
doesn't say full runs of *what*, given 0b sits between 0a and 0c in strict order — before L\* is even
chosen. Read as the same pattern F-NBR-A's own `run_all.py --determinism-check` already established:
run the *entire remaining pipeline* (0c → 0d → 0e → sweep → Part D, naturally truncating at the first
VOID) twice, independently, and diff the JSON. This makes 0b's cost self-bounding: since 0c voided in
both runs, the actual doubled cost was ~8 minutes, not the multi-hour cost a full sweep would have
carried.

---

## 1. ROW 0 — evaluated in strict order

| row | result | detail |
|---|---|---|
| **0a** | ✅ PASS | both DLL copies `bc8efcf1…b051d7f`, shim `20260046` |
| **0b** | ✅ PASS | two independent full runs of the remaining pipeline (0c→…), JSON **byte-identical** — mechanically diffed twice: once by the script itself, once by me independently (`diff` on the two written files, empty) |
| **0c** | 🔴 **VOID** | calibration sweep at Δ=12 Hz — **no L in the set yields 0.15 ≤ R ≤ 0.60** |

### 1.1 ROW 0c detail

| L (deficit vs E) | F `snr_db` | hits/100 | R |
|---|---|---|---|
| 0 dB | −5 | 0 | 0.000 |
| −1 dB | −6 | 10 | 0.100 |
| −2 dB | −7 | 0 | 0.000 |
| −3 dB | −8 | 0 | 0.000 |

**L\* = None.** The highest reading (L=−1, R=0.10) still falls short of the 0.15 floor. ⚠️ The
non-monotonicity (L=−1 above both its neighbours) is binomial noise at N=100, not a real inversion —
none of the four points is close enough to the passing band for it to matter to the verdict.

**This matches, and was foreseeable from, already-committed data (HK-018):** `2026-08-23`'s C3 sweep
(Δ=12 Hz fixed) already measured `snr_f=-5` (deficit 0) → 0/100 and `snr_f=-2` (deficit **+3**) →
100/100 — the calibration band the spec named (`0` down to `−3`) sits entirely on the zero side of a
transition that C3's own coarser sampling shows lies somewhere in **(0, +3] dB**, a region the
calibration set never reaches. I did not skip the mechanical check on this basis — HK-021 requires
running it, not inferring it — but it is why I did not expect a different outcome, and why the
useful next step is visible now rather than needing a fresh investigation.

**Per spec's own consequence (§4.4, unchanged by Amendment 1): STOP and report. Do NOT run the
sweep and read a flat zero as "no structure."** I have not run it. **ROW 1–4 (tone-contention vs
tile-artefact discrimination) remain UNRESOLVED** — this arm cannot currently distinguish M1 from M2.

---

## 2. Part D — run independently, non-gating, N=100 (full, not smoke)

Amendment 1 §3 marks Part D non-gating and states its own conditions in **absolute** 0 dB terms, with
no dependency on L\* or the sweep. Since ROW 0a/0b are the only real prerequisites (a pinned, working,
deterministic harness) and both PASS, I ran it — it costs ~7% of the full arm's time (a few minutes),
answers a question no other closed or open work item currently answers, and running it does not
touch, soften, or bypass the ROW 0c VOID above in any way.

| condition | result |
|---|---|
| **D1** (P2 replica: 3 signals, 0 dB, at 1492/1500/1511 Hz) | **0/100, UB 3%**, all three stations |
| **D2** pair 1 (0/+8 Hz, 0 dB) | 100/100 both stations |
| **D2** pair 2 (0/+11 Hz, 0 dB) | 100/100 both stations |
| **D3** (3 signals, 0 dB, at 1492/1592/1692 Hz — wide) | 100/100 all three stations |

D2 mean R = 1.000 ≥ 0.90 ⇒ **harness validated** for this question (known-good two-signal case
reproduces). D1 ≈ 0 (0/100, UB 3%, all three stations independently) **and** D3 ≈ 1.0 (100/100, all
three) ⇒ **pre-registered reading fires: "density, not count."** Three *overlapping* signals fail
together (D1, matching real P2's 0/15 exactly); three *spread* signals all succeed (D3), consistent
with S8's own 12-simultaneous-signal 91.67%. **P2 belongs to the near-neighbour family**, and Amendment
1 §1.1's 41-of-46 S7 / 100% S8 figures are the right ceiling to reason about — **still an upper bound,
not a forecast, and still gated on a mechanism (M1/M2) that ROW 0c's VOID leaves unresolved.**

🛑 **Restating Amendment 1's own limits, since they bind regardless of how clean this reading is:**
Part D cannot change the verdict, feeds no ROW 1–4, and authorises no remedy. It does not tell us
*why* three overlapping signals fail — only *that* overlap, not count, is what's doing it.

---

## 3. What this run does and does not establish

**Establishes:** (a) the harness/decoder pair is deterministic (ROW 0b); (b) the calibration band
specified in the spec does not reach a readable zone at Δ=12 Hz (ROW 0c, mechanical, not inferred);
(c) P2's mechanism is density-dependent, not a signal-count ceiling (Part D, N=100, pre-registered
reading, non-gating).

**Does not establish:** whether the near-neighbour exclusion is tone-set contention in extraction
(M1, same work item as D-001 limb 2) or a pass-1/tile artefact (M2, its own closed family requiring a
fresh pre-registration). That question is exactly what ROW 1–4 exist to answer, and this run never
reached them.

---

## 4. Recommendation — a decision for the Captain/Architect, not mine to make unilaterally

Amendment 1 is explicit that widening a bar after seeing data is a live error class, and re-specifying
the calibration band is a methodology change, not an implementation detail HK-025 puts in QA's hands.
Three options, as I see them:

1. **Widen the calibration band and re-spec.** C3's own coarse data suggests the transition lies in
   `(0, +3]` dB — a natural next set would be something like `L ∈ {0, +1, +2, +3}` at the same Δ=12 Hz.
   Cheap (same ~8 minutes) if authorised.
2. **Accept ROW 0c's VOID as the arm's result and stop here.** Part D's reading already answers the
   "does P2 belong to this family" question the amendment cared about most; only the M1/M2
   discrimination is left open, and that question has its own standing alternative route (clearing
   ROW 0g on the coherent extractor, per spec §3).
3. **Something else** — not mine to propose further; flagging the fork rather than picking a branch.

⚠️ I am **not** recommending option 1 over option 2 — sizing that trade (a few more minutes of harness
time vs. what M1/M2 is actually worth learning right now) is the Captain's call, not something ROW 0c's
VOID resolves on its own.

---

## 5. Artefacts

- Code: `qa/rr-study/f-nbr-a/nbr_a.py` (new)
- Determinism check: `qa/rr-study/f-nbr-a/results/_nbr_a_determinism_run1.json` /
  `_nbr_a_determinism_run2.json` (byte-identical, independently `diff`-verified) +
  `nbr_a_determinism_run.log`
- Official ROW 0 result: `qa/rr-study/f-nbr-a/results/nbr-a-results.json` + `nbr_a_official_run.log`
- Part D result: `qa/rr-study/f-nbr-a/results/nbr-a-part-d-results.json` + `nbr_a_part_d_run.log`

**HK-014 does not bind QA** (it names the Architect); this document and its artefacts are committed
locally on a QA-owned branch, **not pushed, not merged into `main`, no request in flight for either**
— same standing as every prior sweep report, per HK-010.
