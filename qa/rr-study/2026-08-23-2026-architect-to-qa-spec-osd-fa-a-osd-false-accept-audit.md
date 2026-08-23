# OSD-FA-A — the OSD false-accept audit: is E2 real, and where is the gate's operating point?

**Architect → QA.** Drafted 2026-08-23 20:26Z (`date -u`, HK-017).
Captain-directed: chosen over the 3–5-bin footprint follow-up and over parking D-001.

**Status: pre-registration. Not yet run. No `src/` change, no rebuild, no Developer session,
no capture run.**

---

## §0. What I measured while drafting, and one thing I got wrong first

### 0.1 🔴 A retracted recommendation, disclosed because it shaped this one

My first recommendation to the Captain this session was a **live near-neighbour attribution
arm** — stratify the WSJT-X-only miss population by frequency separation to the nearest
stronger neighbour, to connect F-NBR-A's exclusion-zone mechanism to X2's crowding term.

**That arm is X4.** `x4_spectral_locality.py:120` is `sep = min(abs(d["freq_hz"] - f) for f
in others)` — the identical measurement, on the identical corpus, through the identical
`t1_frequency_quantisation.load()`, standardised on the identical pinned L1 SNR edges. It ran
on 2026-08-10, produced `E_sep = +46.039 pp`, and X5's ROW 0d stop retired the whole line
**permanently** the next day. `E_sep` is named in the standing prohibitions list as
permanently uncitable.

Two standing rules blocked it: the retirement itself, and **"never re-read a closed gate with
a better metric."** My "use stronger-neighbours and a level ratio instead of raw separation"
refinement is exactly the better metric that rule exists to refuse. This was an HK-018 failure
— I reasoned forward from F-NBR-A's mechanism and never opened the closed-arms list, and I
read past `x2_density_floor.py`'s own docstring warning at line 12 while preparing the pitch.

**Consequence for QA: nothing in this spec may be extended toward a spectral-neighbourhood
metric on live data, under any name.** If any leg below starts to look like one, refuse it
under HK-025 and escalate.

### 0.2 What I verified in the code this session (facts, all re-checkable)

| # | fact | evidence |
|---|---|---|
| 1 | OSD runs **529 CRC-14 trials per candidate** at `ndeep=2`, `search_k=32` | `decode.c:429` |
| 2 | `osd_decode` returns the **FIRST** CRC-valid codeword found and stops searching | `decode.c:592–595`, `osd_try_codeword(...) → return 1` |
| 3 | The `nhard`/`corr` gate is applied **after** OSD has already chosen its winner | `decode.c:672–700` |
| 4 | `nhard ≤ 60` and `corr/norm ≥ 0.10` are the **only** defence between 529 CRC trials and an emitted decode | `decode.c:694–698` |
| 5 | Both thresholds are **runtime-settable with no rebuild** via `ft8_set_decode_params(k, corr, nhard)` | `ft8_shim.c:478–487`, `ft8_shim.h:862`, `/EXPORT:` in `rebuild_shim.bat:148` |
| 6 | `ftx_normalize_logl` is a **pure positive scale** (`sqrt(24/variance)`), no mean subtraction | `decode.c:403–408` |
| 7 | ⇒ **sign, and therefore every channel hard decision, is identical pre- and post-normalisation** — so `nhard` and `corr/norm` are exactly recomputable in Python from raw LLRs | follows from 6 |
| 8 | `ftx_ldpc_decode_llrs` exposes `out_path` (0=BP, 1=OSD, −1=neither) and `out_crc_ok`, but **does NOT export `nhard`**, and returns `out_path = −1` for a gate rejection *and* for "OSD found nothing" — the two are indistinguishable from the export alone | `decode.c:907–1010`, `ft8_shim.c:1719` |
| 9 | The gate's calibration is stated as **"against S5 noise and S7 genuine histograms"** and has never been re-checked since shim 20260028 | `decode.c:41` |
| 10 | DLL pin: **`bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f`**, shim **20260046** — I hashed **both** copies on disk this session, byte-identical | `native/ft8_lib_build/libft8.dll`, `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` |

**Fact 7 is what makes this arm cheap.** Every quantity below is obtainable from the
already-shipped, SHA-pinned binary with no `src/` change.

**Fact 8 bounds it.** The gate's own *rejections* are invisible to the export — which is why
Part B reaches them by **turning the gate off at runtime** (fact 5) rather than by
instrumenting it.

### 0.3 🔴 A structural finding I am NOT gating, recorded because it is load-bearing

From facts 2 + 3: **OSD is a first-hit search, and the gate is a post-hoc filter on its single
winner.** If the first CRC-valid codeword OSD reaches is a false accept, a genuine codeword
deeper in the enumeration order is **never tried** — the search has already returned.

So a CRC-14 false accept does not merely add junk. **It can displace a true decode.** That
couples the precision mechanism to the recall mechanism inside one function, and it means the
two open Captain decisions — RC4's `K_MAX_PASSES`/`K_MAX_DECODED` and D-009 Option B's
`osd_nhard_max` 60→40 — are two knobs on **one** operating point, not two independent items.

🛑 **This arm cannot test displacement.** Doing so requires continuing the enumeration past
the first CRC hit and ranking the survivors, which is a `src/` change and a new build. It is
**out of scope here and earns its own pre-registration.** Do not let any leg below drift
toward it, and do not report this arm's results as bearing on it.

### 0.4 What I deliberately did NOT run

**I did not compute `U`, `P_fa`, or `Q_gate`.** All three are gated primary statistics and
running them would make this pre-registration theatre. My predictions are in §8, on the record,
blind.

⚠️ **My last prediction was badly wrong.** F-NBR-A Gate A fired A2 when I had predicted A1 with
`R_forced ≥ 0.95` — the opposite corner. Weight §8 accordingly.

---

## §1. The question

**E2 — "our exclusive decodes are largely false" — is the leading D-001 candidate on five
independent signals. It has never been tested directly, and it now has a named mechanism.**

The five signals, none decisive alone:

1. C-ASYM-A Gate B's corrected `Delta_S` (a proxy, the strongest of them)
2. C-ASYM-A §3's SNR-implausible-decode table (circumstantial)
3. C-ASYM-A Part C's oracle-backed **8 vs 0** false positives (small-N, unambiguous)
4. The S5 FP gate regression — **4/120 slots, 95% UB 7.47% > the 6% ceiling**, second-ever ratified FAIL
5. F-NBR-A's **5/100 trials in which OSD converged to a CRC-valid but WRONG payload**

Signal 5 is the mechanism: a CRC-14 false accept out of 529 trials per candidate, gated only by
`nhard ≤ 60`. This arm asks three separable questions about it, in reading order:

- **(D)** Is the OSD path used often enough on **live** audio for its false accepts to matter at all?
- **(A)** Under oracle truth, what fraction of our emitted decodes are false?
- **(B)** Of what the gate removes, how much is junk and how much is a genuine decode?

**Part D is read FIRST and governs how A and B may be cited.** If OSD is a rare path live,
then A and B characterise a minor branch and may not be quoted as an explanation of D-001,
however they read.

---

## §2. Population and instrument

### 2.1 Synthetic legs (Parts A, B, C)

Rendered offline at the decoder's native 12 kHz, driving the **production** `ft8_decode_all`
unmodified. Oracle truth is the injected message set — the project's synthetic vocabulary is
**exclusively Q-prefixed** (`scenarios/study-messages.json`), so any non-`Q` callsign-shaped
token in an emitted decode is false **by construction**.

- **Signal-present scene:** `scenarios/s8hn-band-scene-highn.json` (S8HN), the scene F-NBR-A
  and C-ASYM-A Part C both used. **N = 1000 cycles**, fresh noise seed per cycle, seeds
  derived through `harness.common.compute_seed`.
- **Noise-only scene (Part C only):** `scenarios/s5-noise-wide-n300.json`.

### 2.2 Live leg (Part D)

**`artefacts/20260803_live_run_1713/`** — 4,614 `owsfz` cycles, confirmed in
`qa/ARTEFACT_INVENTORY.md:38`, which flags it **"D-001 replication corpus — DO NOT PROPOSE A
CAPTURE RUN FOR D-001."** Both decoders on one verified audio path. **Sample 1000 cycles**,
seeded.

🔴 **Two population numbers on the board disagree and I am not resolving it by assertion.**
C-ASYM-A reports OpenWSFZ **56,202** decodes on this corpus; F-NBR-A Gate B reports **64,417**
over 4,614 cycles. These are different filterings (distinct-key vs raw rows, or band
restriction). **ROW 0f below requires QA to derive both, state which definition each
corresponds to, and report the reconciliation.** Do not silently adopt either.

### 2.3 Instrument — reuse, do not rebuild (HK-018)

| component | source | use |
|---|---|---|
| `LdpcDecodeLLRs`, `a91_to_bits`, `dll_sha256` | `qa/rr-study/r2-coherent-llr-instrument/ldpc_decode_ctypes.py` | probe binding |
| DLL pin + `SYMBOL_PERIOD_S` correction | `qa/rr-study/f-nbr-a/dll_common.py` | binary identity, waterfall-origin offset |
| 12 kHz scene rendering + mutation helpers | `qa/rr-study/f-nbr-a/scene_render.py` | Parts A/B/C |
| cluster bootstrap, Clopper–Pearson | `qa/rr-study/f-nbr-a/stats_common.py` | all CIs |

**New code is limited to:** the `ft8_set_decode_params` binding, the Python `nhard`/`corr`
recomputation (fact 7), and the leg differencing.

### 2.4 🔴 Three carried hazards — apply them, do not rediscover them

1. **The +0.16 s waterfall-origin offset.** `ft8_extract_llrs_at` reads exactly one FT8 symbol
   period ahead of raw-PCM time (B-orig-A, CONFIRMED 2026-08-21; F-NBR-A ROW 0c). Any
   position-driven extraction in Part D **must** apply `dt + 0.16`, **uniformly**, never
   selectively.
2. **Hash-randomised set iteration.** `set(a) & set(b)` over string keys iterates
   per-process-randomly, so a fixed seed still draws different indices. **Sort at
   construction**, everywhere a sample is drawn.
3. **`limit=` truncates in file order, it does not sample.** If any existing population helper
   is reused, check what its `limit=` does before trusting it (HK-021(i)). **Report CLUSTER
   counts, never bare row counts.**

### 2.5 Gate-off configuration (Part B)

`ft8_set_decode_params(k_min_score_pass2=10, osd_corr_threshold=-1.0, osd_nhard_max=174)`.

- `nhard > 174` is unreachable (`FTX_LDPC_N = 174`) ⇒ feature 2 disabled.
- `corr/norm ≥ -1` always ⇒ feature 1 disabled.
- 🛑 **`k_min_score_pass2` stays at 10 in both legs.** It is a different knob and moving it
  would confound the contrast.
- Set parameters **before the first decode call** and never mid-run — the shim documents
  module-level writes against thread-pool reads (`ft8_shim.c:474–477`).

### 2.6 NFR-021

Parts A/B/C are Q-prefix synthetic throughout — not engaged. **Part D reads live `ALL.TXT`
with real callsigns.** Message text may be held in memory to build match keys and to compare
payloads; it must **never** be printed, logged, or written to any output file. Output is
**counts only**. Run `git check-ignore -v` on every artefact before any commit.

---

## §3. ROW 0 — preconditions, evaluated in strict order

Per HK-021(k)/HK-025, each row below is stated with the verdict it changes. A row that cannot
change a verdict is marked **DIAGNOSTIC** and must be reported, never gated on.

| row | check | bar | consequence if it fails |
|---|---|---|---|
| **0a** | SHA256 of the DLL actually loaded by the probe process | `== bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f` | **VOID (all parts).** A different binary is a different instrument. |
| **0b** | `ft8_set_decode_params` takes effect: set `nhard=0`, re-run one fixture, confirm OSD-path accepts fall to zero; restore defaults and confirm the original count returns | exact: `n_osd_accepts(nhard=0) == 0` **and** `n_osd_accepts(restored) == n_osd_accepts(baseline)` | **VOID Part B.** If the setter is inert, the gate-off leg measures nothing. A/C/D unaffected. |
| **0c** | Oracle labelling: on a clean high-SNR render (all stations ≥ +5 dB, no near neighbours), every emitted decode's payload is in truth | `n_false == 0` | **VOID Parts A/B.** False accepts at high SNR mean the render or the labeller is broken, not the decoder. |
| **0d** | Determinism: two independent full runs, all result JSON **mechanically diffed** | byte-identical | **VOID (all parts).** Not asserted — diffed. |
| **0e** | Part D probe fidelity: at live decode positions (with the +0.16 s correction), the probe reproduces production's own payload | `≥ 0.90` of a 200-decode control subset | **VOID Part D only.** Below this, `U` measures the probe, not the decoder. A/B/C unaffected. |
| **0f** | Population reconciliation: derive ours-only, ours-total, and cycle counts on the Part D population; state the definition behind **56,202** and behind **64,417** | — | **DIAGNOSTIC.** Report it. It cannot change any row below and must not gate one. |

### 3.1 ⚠️ What ROW 0c cannot detect (HK-022 drafting question)

If the renderer and the labeller read the **same** truth list, a wrong truth list passes 0c
silently — the error is shared by generator and consumer, which is precisely the shape HK-022
calls decorative. **Mitigation, mandatory:** derive the labeller's truth set from the scenario
JSON on disk, and assert its message count and its Q-prefix-only property independently before
any labelling. Report both counts.

### 3.2 If a ROW 0 check needs correcting to be runnable

**Correct it, and disclose the correction in full — a disclosed correction is a result; a
silent one voids the arm.** Apply any correction **uniformly** across controls and treatment
alike, never selectively. F-NBR-A's handling of ROW 0b/0c is the model.

---

## §4. Part D (READ FIRST, GATED) — is the OSD path used at all on live audio?

### 4.1 Method

Sample **1000 cycles** (seeded, sorted at construction) from the Part D population. For every
OpenWSFZ decode in those cycles, extract LLRs at its reported `(freq, dt + 0.16)` via
`ft8_extract_llrs_at`, then call `ft8_ldpc_decode_llrs(max_iters=50, osd_depth=2)` and record
`out_path`.

**Statistic:** `U` = (decodes with `out_path == 1`) / (decodes with `out_path ∈ {0, 1}`).
Decodes the probe fails to reproduce (`out_path == -1`) are excluded from both numerator and
denominator and **reported separately as a count** — they are ROW 0e's population.

95% CI by **cycle-clustered** bootstrap (HK-021(i) — 64k decodes over 4.6k cycles are not 64k
independent observations).

### 4.2 The bar and why it is that number

For OSD false accepts to be a first-order explanation of E2, junk must reach a material
fraction of our output. **Even if every OSD-path decode were false**, junk could not exceed
`U`. So `U` is a **necessary-condition bound**, and the bar is the same 10% used in Part A.

| row | condition | consequence |
|---|---|---|
| **D1** | `CI_hi < 0.10` | **The OSD mechanism for E2 is BOUNDED OUT on live data**, regardless of how A and B read. Parts A/B become characterisation of a minor path and **may not be cited as an explanation of D-001.** E2 must be pursued through a non-OSD mechanism or dropped. |
| **D2** | `CI_lo > 0.10` | OSD is used often enough to matter. **Part A's rate transfers** and may be cited against the live deficit. |
| **D3** | CI spans 0.10 | Unresolved. Report `U` and its CI; A and B are reported as synthetic-only characterisation. |

### 4.3 Resolution, computed while drafting (HK-021(m))

At 1000 cycles and ≈14 decodes/cycle the sample is ≈14,000 decodes in 1000 clusters. Taking a
conservative design effect for cycle clustering, the expected 95% half-width on a proportion
near 0.10 is **≈ ±0.010**. **The bar is therefore resolvable unless `U` lands inside
[0.090, 0.110].** D3 is a real, expected outcome in that window and must be reported as D3, not
rounded to either side.

Readout quantum (HK-021(o)): `U` is a ratio of integer counts over ≈14,000 decodes ⇒ quantum
≈ 7×10⁻⁵, four orders below the half-width. Resolution is sampling-limited, not readout-limited.

---

## §5. Part A (PRIMARY, GATED) — the oracle false-accept rate

### 5.1 Method

Render **1000 S8HN cycles**, decode each with `ft8_decode_all` at **production defaults**
(`k=10, corr=0.10, nhard=60`). Label every emitted decode against that cycle's injected truth
set: **TRUE** if its payload is in truth, **FALSE** otherwise.

**Statistic:** `P_fa` = FALSE decodes / all emitted decodes. 95% CI by cycle-clustered bootstrap.

⚠️ **Match on payload, not on displayed text.** A hashed-callsign rendering difference is a
text mismatch, not a false accept — that distinction is what separated station F from C-GAP-D's
T1/T3 population and it must not be re-confused here.

⚠️ **Scope the `ALL.TXT` read to this run's own cycles.** C-ASYM-A's first pass counted
447 vs 1 false positives because `matcher.py` scans every bucket in the whole file, including
yesterday's live traffic. Filter to the run's own `cycle_utc` values before counting anything,
and confirm zero non-`Q` tokens survive the filter.

### 5.2 Gate

| row | condition | consequence |
|---|---|---|
| **A1** | `CI_hi < 0.10` | Under oracle truth, false accepts are **not** a first-order share of our output. **E2's OSD mechanism is not supported**; the junk hypothesis must name a different source. |
| **A2** | `CI_lo > 0.10` | **E2 confirmed with a named mechanism.** The OSD operating point becomes a live D-001 lead, and Part B's reading governs which direction to move it. |
| **A3** | CI spans 0.10 | Unresolved. Report `P_fa` and its CI; no consequence fires. |

### 5.3 Resolution, computed while drafting (HK-021(m))

Prior: C-ASYM-A Part C measured **8 false positives in 275 decodes ⇒ 0.029** — used here
**only** to size the instrument, and it carries that arm's own disclosed contamination
correction, so treat it as an order of magnitude, not a point estimate.

At 1000 cycles × ≈11 decodes/cycle ≈ 11,000 decodes in 1000 clusters, the expected 95%
half-width near `p = 0.03` is **≈ ±0.005** ⇒ `CI_hi ≈ 0.035`, which sits **0.065 below the bar,
≈ 13 half-widths.** Decidable, and decidable at the far end too: `P_fa = 0.10` would produce
≈ 1,100 false decodes, unmistakable.

**Decision boundary, stated now:** with ≈11,000 decodes, A1 requires roughly **≤ 1,050 FALSE
decodes** and A2 roughly **≥ 1,150**. A count landing between those is A3 — **report it as A3
and do not round it toward either row.**

---

## §6. Part B (GATED) — what does the gate actually remove?

### 6.1 Method

Re-decode **the identical rendered PCM** from Part A with the gate disabled (§2.5). Difference
the two legs by `(payload, freq within ±4.0 Hz)`:

- `N_caught` = decodes present GATE-OFF, absent GATE-ON, payload **∉** truth → junk correctly removed
- `N_killed` = decodes present GATE-OFF, absent GATE-ON, payload **∈** truth → **a genuine decode the gate destroyed**

**Statistic:** `Q_gate` = `N_killed / (N_killed + N_caught)` — the fraction of the gate's
removals that were real. Signed and identifiable (HK-021(l)); no absolute value anywhere.

⚠️ **Report, do not discard:** decodes present GATE-ON but absent GATE-OFF. They should be rare;
if they are not, disabling the gate is perturbing the decode set through the shared
`K_MAX_DECODED` budget rather than only through the gate, and that is a **disclosed confound**
that must appear in the report with both legs' total decode counts.

### 6.2 Power precondition (routes to a row, does not void)

If `N_killed + N_caught < 100`, the arm cannot resolve `Q_gate` ⇒ **B3**. Per HK-021(k) this
precondition changes the verdict (B3 versus B1/B2), so it is a legitimate gate component and
not a diagnostic.

### 6.3 Gate

| row | condition | consequence |
|---|---|---|
| **B1** | `CI_hi < 0.05` | The gate removes junk and almost nothing real. **Tightening it is worth testing — D-009 Option B (`osd_nhard_max` 60→40) gets its first real evidence** and may be proposed as a diagnostic build. |
| **B2** | `CI_lo > 0.20` | **The gate already costs genuine decodes.** D-009 Option B is **contraindicated** and must be recorded as such; the live question becomes whether 60 is already too tight. |
| **B3** | otherwise, or `< 100` removals | Unresolved. Report both counts and the CI. No consequence fires in either direction. |

### 6.4 Resolution

`Q_gate`'s half-width depends on a removal count nobody has ever measured, which is exactly why
§6.2 exists. **At the 100-removal floor the 95% half-width on a proportion near 0.05 is ≈ ±0.045
— barely resolvable against the B1 bar.** QA should report the achieved removal count
prominently; if it lands near 100, say so and read B3 rather than stretching B1.

---

## §7. Part C (DESCRIPTIVE — NOT GATED) — where does the gate's cut actually sit?

No row, no consequence, no citation as evidence for any hypothesis. This exists because the
gate's calibration is documented as "against S5 noise and S7 genuine histograms"
(`decode.c:41`) and **has never been re-checked on the current binary.**

Using fact 7, recompute `nhard` and `corr/norm` in Python for every OSD-path accept in Parts A
and B, plus a noise-only run on `s5-noise-wide-n300.json`, and report:

1. `nhard` histogram for **TRUE** accepts vs **FALSE** accepts (signal-present)
2. `nhard` histogram for noise-only accepts (all false by construction)
3. Where **60** sits relative to both distributions, and what cut would separate them best
4. The same three for `corr/norm` against **0.10**

⚠️ **Reconstructing the 174-bit codeword:** `out_a91` gives 91 bits; `nhard` needs all 174.
Re-encode via the LDPC encoder already bound in `ldpc_decode_ctypes` and **verify the
round-trip** on a control before trusting any histogram — a round-trip against our own encoder
tests self-consistency, not correctness (HK-022), so also confirm at least one reconstructed
codeword reproduces a production decode exactly.

🛑 **Item 3 is a description of a separatrix, NOT a proposal to move the threshold.** Any
threshold change is a `src/` change requiring its own pre-registration with **FP as the primary
statistic** — the D-009 calibration history in `decode.c:43–50` shows this family has been
re-tuned five times and ceilinged once.

---

## §8. Architect predictions — on the record, blind, before any leg runs

| leg | prediction | confidence |
|---|---|---|
| **D** | **D1.** `U` ≈ 0.03–0.08 — BP converges for most decodes; OSD is a fallback for hard cases | moderate |
| **A** | **A1.** `P_fa` ≈ 0.02–0.05, consistent with C-ASYM-A Part C | moderate |
| **B** | **B1**, least confident of the three — I expect the gate to be mostly pure, but `N_killed > 0` would not surprise me at all | low |

⚠️ **If D1 and A1 both fire, this arm's headline is that E2's OSD mechanism is eliminated** —
a negative result, and a useful one, because it would redirect E2 to a non-OSD source of junk
while leaving the four non-mechanism signals intact. **That is a legitimate and expected
outcome, not a failed arm.** Do not reach for a rescue reading.

⚠️ My F-NBR-A prediction landed in the opposite corner of its gate. Score these accordingly.

---

## §9. What this arm does NOT do

- 🛑 **Does not test first-hit displacement** (§0.3) — needs a `src/` change; earns its own arm.
- 🛑 **Does not move any threshold.** No `osd_nhard_max` change, no `corr` change, no
  `K_MAX_PASSES`/`K_MAX_DECODED` change. B1/B2 authorise a *proposal*, not an edit.
- 🛑 **Does not go near spectral locality** in any form (§0.1). Refuse under HK-025 if a leg drifts.
- 🛑 **Does not reopen** the candidate-budget family (closed twice), OSR, subtract-and-resynthesise,
  input scaling, or the pass-1 suppression ramp (`diag-d001-h5-suppression-tuning`, REJECTED).
- 🛑 **Makes no claim about WSJT-X's behaviour** (HK-026 — `jt9 -d 3` offline is not a valid reference decoder).
- **Does not open E4** (fading/Doppler/drift/timing spread). Still last, still generator work.
- **Does not bear on station F.** F-NBR-A closed A2 on extraction locus; nothing here revisits it.
- **Does not touch `src/`, does not rebuild, does not push, does not merge** (HK-011, HK-014, HK-010).

---

## §10. Reporting and stopping

1. Read **ROW 0 first**, in order, and stop on the first VOID at the scope that row names.
2. Read **Part D before Parts A and B**, and state D's row before quoting either.
3. Report every row that fired, the statistic, its CI, its cluster count, and its distance from
   the bar in half-widths.
4. **Report cluster counts everywhere, never bare row counts** (HK-021(i)).
5. Disclose every correction in full (§3.2).
6. **Stop at the gate.** No push, no merge, no `pre_merge_check.py` (HK-006, HK-010, HK-014).
7. 🔴 **You may refuse to run this spec on HK-021(k) grounds without my agreement** (HK-025).
   If any pre-gate check above turns out to be a diagnostic dressed as a gate, name the row,
   state the evaluation under both branches, and **stop — no partial run.** I have now put a
   precondition ahead of a gate it could not change on three separate arms (X4, X5, and by the
   Captain's catch on C-ASYM-A). Assume I have done it again and check.
