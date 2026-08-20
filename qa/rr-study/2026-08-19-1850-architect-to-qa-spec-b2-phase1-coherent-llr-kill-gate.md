# ARCHITECT → QA — Route B2, phased. Phase 1 is a KILL GATE and it is cheap.

**2026-08-19 18:50Z · Architect · Captain authorised Route B2 at 18:40Z (S3b instrument first)**

**SPEC ONLY — NOT RUN, NOT BUILT.** No `src/` touched by this document. HK-011 is engaged by
Phase 1 and nothing here authorises a Developer session; that remains the Captain's.

**Read §0 first.** Grounding this against the code (HK-018) turned up three things that change
what Route B2 *is*, and one of them makes the ledger's own description of it wrong.

---

## 0. Three corrections to the 08-18 ledger's framing of Route B2, found while drafting

### 0.1 ✅ The `C:\Temp` build blocker is GONE. The ledger's §9.1 risk is STALE.

§9.1 lists as a reason not to raise B2's number: *"it depends on `C:\Temp\ft8_lib_headers`,
**outside version control** — a `C:\Temp` clear makes the library unbuildable with no commit
recording why."*

**That was fixed by R0 and I did not notice.** `rebuild_shim.bat:13-122` now compiles every
translation unit from `native/ft8_lib_vendor/` — tracked, 22 files, with `PROVENANCE.md` recording
upstream remote, branch, HEAD SHA `d18ed84f…`, and a content-identity check against upstream that
came back empty modulo line endings. **The single largest operational risk attached to Route B2 no
longer exists.** `memory/architecture-ft8-lib.md`'s "🔴 The native sources are NOT in the repo"
section is stale in the same way and should be corrected in QA's next board-touching edit.

### 0.2 🔴 Half of Route B2 IS ALREADY BUILT — and I described it to the Captain as unstarted.

`native/ft8_lib_vendor/refine/sync_refiner.c`, **460 lines**, OpenWSFZ-original, clean-room by
construction (its header records that no WSJT-X source was available in or consulted during the
session that wrote it — a stronger position than the licence ruling requires). Exported as
`ft8_refine_candidate()`, `FT8_SHIM_VERSION` 20260040 → 20260041.

It already does the thing the ledger describes as the new work: **downconverts the candidate's PCM
region to complex baseband with phase retained, correlates coherently against the three Costas 7×7
arrays summing COMPLEX values across all 21 symbols and taking magnitude LAST**, then searches
coarse-time → frequency → fine-time. Its header explicitly contrasts itself with
`ft8_decode_multi_symbols()`'s magnitude-then-sum shape.

**It has no production call site.** Reachable only from the validation harness and tests.

### 0.3 🛑 AND THE BUILT HALF IS THE HALF THAT HAS ALREADY BEEN MEASURED AND FAILED.

This is the part that matters, and it cuts against the route the Captain has just authorised. I am
stating it at the top rather than burying it in a risk section.

| arm | what it tested | outcome |
|---|---|---|
| `M4` | does the refiner LOCATE real signals? | **ROW 2** — `rho_conc` = −0.0241, CI [−0.0363, −0.0119]. It does not. Citation of the ~1.1 ms / 0.5 Hz figures for real signals became **PERMANENTLY PROHIBITED**. |
| `N1` | does extracting at the refined position move BER across the correction threshold? | **ROW 2 — limb 1 DEAD.** "The failure is in how the bits are formed, not where they are read." |
| P-LIVE Stage 2 | the same question at scale, corrected anchor | **ROW 3 — HARM.** `d_ber` = −3.45 pp, CI95 [−3.45, −2.87], p = 0.0000, 3,916 clusters. Refinement *hurts*. `f_cross` = **0.15%** (23/3,916). |

⚠️ **In fairness to the refiner:** the M-series carried a study-design confound of my own making —
`m1_build_population.py:105-109` anchored from WSJT-X's `ALL.TXT` while the harness read OUR WAV,
the ~0.65 s convention offset, which voided M1+M2 and which a real integration would never have
had. But **Stage 2 ran with the corrected anchor** (Part A independently re-derived +0.65 s, ROW 0d
found all four quartiles landing on it exactly) **and still fired HARM.** The confound does not
rescue limb 1.

🔴 **Consequence for the spec below, and it is the whole design:**

> **Route B2's remaining value rests ENTIRELY on limb 2 — coherent multi-symbol LLR formation —
> which is NOT built and has NEVER been measured. Limb 1 is dead three times over. Phase 1 must
> therefore test limb 2 and ONLY limb 2, and it must be built so that limb 1's death cannot
> contaminate it.**

**The design decision that achieves that: form coherent LLRs AT THE EXISTING GRID POSITION.** No
refinement, no dependence on `ft8_refine_candidate()`'s position estimate. If coherent bit metrics
work, they work at the position we already have, and the gain arrives without the refinement that
three arms have now shown is at best neutral and at worst harmful. If they only work at a refined
position, we would be stacking a live bet on a dead limb.

⚠️ **Stated plainly for the Captain:** this sequence lowers my confidence in B2 relative to the
ledger's figure. Every arm that has touched this shared machinery has come back negative, harmful,
or void. I am not putting a number on it — the ledger's §11 bars its credences from
pre-registrations and I will not smuggle one in through prose — but the direction is down, and the
kill gate below is designed on that basis rather than in spite of it.

---

## 1. What Phase 1 builds, precisely

One new diagnostic-only native export, alongside the existing refiner and under the same boundary
(no production call site, `ftx_decode_candidate()` and `ft8_decode_all()` byte-for-byte unchanged):

```
int ft8_coherent_llr_at(
    const float *pcm, int num_samples,
    int cand_freq_idx, int cand_time_idx,   /* the EXISTING grid position — not refined */
    float *out_log174,                      /* 174 coherent LLRs                        */
    float *out_diag);                       /* optional diagnostics                     */
```

**Method** (clean-room from this description; WSJT-X read for method only, nothing copied,
transliterated or ported — the licence line is absolute and `sync_refiner.c` already demonstrates
the standard this project holds itself to):

1. Downconvert the candidate's region to complex baseband at the candidate's grid frequency, phase
   retained. **Reuse `sync_refiner.c`'s existing downconversion** — it is written, reviewed and
   clean-room, and re-implementing it would add risk for nothing.
2. For each of the 58 data symbols, correlate the baseband coherently against each of the 8 tone
   hypotheses — **complex accumulation across the symbol, magnitude taken last.**
3. Form **1-, 2- and 3-symbol coherent metrics** and combine them into per-bit LLRs, max-log over
   the tone hypotheses consistent with each bit.
4. Normalise to the same scale `ftx_normalize_logl` expects, so the output is drop-in comparable
   with the magnitude-only `log174`.

🛑 **Explicitly NOT in Phase 1:** no production wiring, no runtime flag, no change to pass
structure, no candidate-cap change, no OSR change, no use of `ft8_refine_candidate()`. Anything
beyond the export above is out of scope and QA should refuse it (HK-025 grounds if it appears).

---

## 2. The arithmetic that sets the thresholds — do not skip this

The addressable population is **not** the whole gap. `RC1`'s decomposition: 3.1% of misses are
out-of-band, **8.9% have no candidate at all**, 87.9% are candidate-present-and-failed. An LLR
change can only touch the last group.

> **Ceiling: 0.879 × ~42 pp ≈ 37 pp.** Route B2 cannot exceed this no matter how well limb 2 works.

Within that population, let **`f_net`** be the net fraction of clusters that coherent LLRs move
*across the correction threshold* — from not-correctable to correctable, minus the reverse. Recall
gain is approximately `f_net × 37 pp`, because crossing the threshold is the *necessary* condition
for BP+OSD to convert a miss into a decode.

| to deliver | `f_net` must be about |
|---|---|
| half the 20m gap (~21 pp) | **~57%** |
| a material 10 pp | **~27%** |
| a marginal 3 pp | **~8%** |

🔴 **This arithmetic is why the gate is worth running and why it is cheap.** It is a *large*
required effect, measured on a population of 3,916 clusters where the resolvable distance is well
under 1% — so the answer separates from zero, or from the bar, in one offline run with no
production code. **We find out whether B2 can work before building the expensive half.**

---

## 3. The pre-registered gate

**Primary statistic — `f_net`.** Over the P-LIVE Stage 2 population (reference decoded, we did
not, candidate present), paired per cluster:

- `n_in`  = clusters with `n_err_grid > 19` **and** `n_err_coh ≤ 19`
- `n_out` = clusters with `n_err_grid ≤ 19` **and** `n_err_coh > 19`
- **`f_net` = (`n_in` − `n_out`) / `n_clusters`**, cluster-bootstrapped 95% CI (by `ts` cluster).

**Secondary, reported always, gates nothing — `C_ber`** = median(BER_coh) − median(BER_grid),
signed, cluster-bootstrapped. Reported so a null on `f_net` can be distinguished from "coherent
LLRs did nothing at all".

### Mechanical definitions, fixed now (HK-021(o) — resolve against the readout quantum)

- **A codeword is 174 bits ⇒ the BER quantum is 1/174 = 0.575 pp.** The correction threshold
  `B50` = 11.3% does not land on a quantum, so the comparison is defined on the **bit count**:
  **correctable ⇔ `n_err ≤ 19`** (= 10.92%, the conservative side of 11.3%). No float comparison
  against 0.113 anywhere in the harness.
- **`f_net`'s quantum is 1/3,916 = 0.0255%** — the bars below sit 200×–600× above it.
- **Resolvable distance, stated while drafting (HK-021(m)):** at `f_net` ≈ 10%, cluster-level
  SE ≈ 0.48%, CI half-width ≈ 0.94%. The 5% and 15% bars are ~10 half-widths apart. **This gate
  can resolve what it is asked to resolve.** If the delivered cluster count is below 1,500, STOP
  and escalate rather than running — the bars stop separating.
- **HK-021(j) λ check:** at a true `f_net` of 5%, expected crossings ≈ 196 ≫ 5. **Absence is
  diagnostic here**, so ROW 3 is entitled to condemn the route.
- **HK-021(l):** `f_net` is signed and nets the reverse crossings. Never gate on `n_in` alone.

### ROW 0 — controls. Any failure VOIDS the run; QA reports and stops.

| id | check | bar |
|---|---|---|
| 0a | DLL SHA256 asserted against a pre-registered manifest, `FT8_SHIM_VERSION` asserted | exact match — **never infer the binary from a label** |
| 0b | Population re-derived, **CLUSTER counts reported, not row counts** | ⚠️ **check what any `limit=` argument does before reusing a population helper** — `compute_matched_hit_control(cycles, limit=N)` TRUNCATES in file order (HK-021(i)) |
| 0c | Sign unit test, **two-sided** (HK-021(n)): a known-good codeword's baseband ⇒ `n_err` ≈ 0; white noise ⇒ `n_err` ≈ 87 | both directions must pass |
| 0d | `ber_grid` reproduces Stage 2's median **31.03%** on the same population | within 1.0 pp |
| 0e | **Candidate identity**: coherent and magnitude LLRs computed at the *same* `(freq_idx, time_idx)`, asserted per row | 100% — candidate mismatch inflates BER toward 50% and would fake a null |
| 0f | Determinism: run twice, **mechanically diff** the outputs (HK-022) | 0 rows differ — diffed, never asserted |

### The rows — strictly ordered, first match wins, provably exclusive

**ROW 1 — STRONG. Fires if `CI_lo(f_net) > 15%`.**
⇒ Coherent LLR formation converts a large fraction of the addressable miss population.
**Phase 2 authorised.** Expected recall gain ≈ `f_net × 37 pp`; quote it as an estimate with the
Phase 3 live measurement as the citable number, never this one.

**ROW 2 — MATERIAL BUT NOT SUFFICIENT. Fires if `CI_lo(f_net) > 5%` (and not ROW 1).**
⇒ Real, worth shipping, **does not close D-001.** Phase 2 authorised *as a product improvement*,
and the Captain gets an explicit re-decision: the project's stated purpose is not met by this
outcome and he should hear that in those words.

**ROW 3 — KILL. Fires if `CI_hi(f_net) < 5%`.**
⇒ 🛑 **Route B2 is dead. Limb 1 was already dead; limb 2 is now dead; the per-candidate
complex-baseband front end is not the treatment for D-001.** No re-read with a better metric
(standing prohibition). The honest consequence, which I will state to the Captain myself rather
than leave implied: **D-001 would then have no remaining identified route**, and the decision in
front of him becomes whether to re-open root-cause work from the RC1 decomposition or to stop.

**ROW 4 — anything else (the CI straddles 5% or 15%).**
⇒ No verdict. QA escalates with the numbers. **Do not average, do not pick the nearer bar.**

*Exclusivity proof:* ROW 1 ⊂ ROW 2's condition and is evaluated first. ROW 2 requires
`CI_lo > 5%`, ROW 3 requires `CI_hi < 5%`, and `CI_lo ≤ CI_hi` ⇒ they cannot both hold. ROW 4 is
the complement. ✅ No input fires more than one row.

---

## 4. Phases beyond the gate — outline only, each earns its own spec

| phase | goal | gate to enter | rough cost |
|---|---|---|---|
| **0** | OpenSpec change + harness + population re-derivation. No native code. | authorised now | days |
| **1** | `ft8_coherent_llr_at()`, diagnostic-only. **Run the §3 gate.** | Captain opens a Developer session | 1–2 weeks |
| **2** | Production wiring behind a runtime flag; A/B on the replay corpus | ROW 1 or ROW 2 | weeks |
| **3** | Live validation + **false-positive gate** | Phase 2 green | ~1 week + live run |
| **4** | Ship decision, `K_MAX_PASSES`/cap re-tune against the new front end | Phase 3 green | — |

🔴 **Phase 3's FP gate is not optional and I am naming it now so it cannot be dropped later.** `P3`
showed that a change which buys decodes can simultaneously manufacture them — union-gained decodes
were **89.7% not in `REF`**, unmatched output rising 17.6% → 44.8%. A new front end that lowers
BER lowers it for noise too. **Recall without an FP bound is not a result.**

---

## 5. Who does what (HK-015 / HK-011 / HK-000)

- **QA now:** author the OpenSpec change (`r2-coherent-llr-instrument` or similar, following
  `r1-sync-refiner-instrument-validation`'s shape — it is the right precedent and it worked), draft
  the `dev-tasks/*.md`, build the measurement harness, re-derive the population, and run ROW 0c/0d
  **before** any native code exists (both are testable against the current build). **Then stop.**
- **Captain:** opens the Developer session. Phase 1 touches native code ⇒ HK-011. **Nothing in this
  document authorises that.**
- **Developer:** implements `ft8_coherent_llr_at()`, rebuilds, `opsx:apply` (build and tests only,
  never `pre_merge_check.py`).
- **QA then:** runs the §3 gate, reports the row, stops. **No Phase 2 work on a ROW 1 without the
  Captain saying so.**
- **Architect:** rules on the row. If ROW 3, I write the consequence to the Captain in plain words,
  including what it means for the project.

⚠️ **QA may refuse this spec on HK-025 grounds** if any ROW 0 or row here fails the two-branch
test. Please actually run that check — several of the recent defects were in my specs, not in
execution.

---

## 6. Risks I can name now

1. 🔴 **The shared-machinery risk (§0.3).** Limb 2 uses the same downconversion whose position
   estimate failed M4. Mitigated by design — coherent LLRs are formed at the grid position, so a
   bad *position estimate* cannot propagate — but if the downconversion itself is defective on real
   signals rather than merely its search, limb 2 inherits that. **ROW 0c is the guard**, and it is
   why it is two-sided.
2. ⚠️ **`B50` = 11.3% is a July-corpus figure** (n = 126 measured) and the threshold is doing real
   work in this gate. It is the best number we have and it is not a fresh one. If the Captain wants
   it re-measured first that is a defensible call and costs a re-run, not a rebuild.
3. ⚠️ **The 8.9% no-candidate misses are outside the addressable population by construction** and
   Phase 1 says nothing about them. The 37 pp ceiling in §2 already accounts for this; do not let
   it be dropped when the number is quoted.
4. ⚠️ **`FT8_SHIM_VERSION` collides twice across five unmerged `d001-*` branches.** Phase 1 mints
   another version. **Pin the SHA256, never the integer** — and the allocation record is already
   behind reality (`D1` ran 20260042 while the reserved-range note stops at 20260041).

---

## 7. Housekeeping

- HK-017: filename `2026-08-19-1850-…` and the byline `2026-08-19 18:50Z` both derive from a real
  `date -u` in this session and agree.
- HK-018: grounded by reading `ft8_shim.c`, `ft8_shim.h`, `sync_refiner.c`, `rebuild_shim.bat`,
  `native/ft8_lib_vendor/PROVENANCE.md`, the `M4` results, the Stage 2 board entry and `RC1`'s
  decomposition **before** drafting. §0.1–§0.3 are what that turned up, and two of the three
  contradict what I told the Captain an hour ago.
- HK-011: engaged by Phase 1. **Not authorised here.**
- HK-014: committed locally only, not pushed, and I have not asked.
- No measurement run while authoring. No `src/` touched. No DLL rebuilt.
- NFR-021: counts, rates and paths only. No callsigns, no message text.
