# `GAP-LOCATE` — where are the strong misses lost? Not found, found-and-misread, or filtered after decode

**Architect, 2026-09-22 18:07Z** (`date -u`, HK-017). Branch `arch/live-gap-map`: this is the §3.7 M1
consequence of `LIVE-GAP-MAP` (spec `2026-09-21-1555` §3.10). Docs-only; no `src/` or `native/` change.

**Authorised:** the Captain, 2026-09-22: *"write the localisation spec"*. Runs on the **existing** C3 archive
with **existing** instruments. No capture, no rebuild.

---

## §0. What this is, and what it reuses (HK-018)

`LIVE-GAP-MAP` ruled M1: on 2026-09-21/22, on `fa8a56ae` (DLL `38a21f84…1cba`), the strong-miss pool is
`H10` = 19.27 pp, CI [18.586, 19.967] (Amendment 3 cut corpus, `n_ref` 127,482). `DT-MISS` ruled out window
timing (T2). The question now: **at which stage is each strong miss lost?**

| stage | meaning | how this arm sees it |
|---|---|---|
| **S — after decode** | our decoder produces it, and the managed layer or the live/replay seam drops it | a raw full-cycle replay decodes it |
| **F — not found** | the signal is decodable where it is, but production never decodes it there (not a candidate, outranked or capped, or sync lands on a bad cell) | forced decode at WSJT-X's position succeeds |
| **N — found or not, it can't be decoded** | even at the right position, our extraction plus LDPC/OSD cannot decode it | forced decode also fails |

**Reused instruments, none new:**
- `ft8_decode_all`: the production decode, used for the raw replay.
- `ft8_extract_llrs_at` + `ft8_ldpc_decode_llrs`: forced decode at a position on production's own lattice,
  through production's own BP/OSD sequence and gate (spec `ft8lib-interop`, `n1`/`r2` changes).
- `qa/rr-study/f-nbr-a` `row0._forced_success`, as reused verbatim by THRESH-A (`qa/rr-study/thresh-a/run.py`).
  It applies `dll_common`'s +0.16 s waterfall-origin correction internally. 🔴 **Do not add a second
  correction on top.** ROW 0c below is the check.
- The `LIVE-GAP-MAP` harness matcher (`lgm_harness.py`, `AMD3_EXCLUDE`), unchanged.

**Precedent:** THRESH-A (isolated, synthetic, at threshold) found `R_forced` = 0.18 %, i.e. a perfect candidate
stage buys nothing at threshold. This arm asks the same question on **real, strong** misses, which THRESH-A
never covered.

## §1. Corpus and population

- **C3 with the Amendment 3 cut**, the `cycle-audio/` WAV archive, and both `ALL.TXT` files. Gitignored,
  NFR-021.
- **Population M:** every REF row with REF SNR ≥ −10 dB that the harness matcher scores as a **miss** (the `H10`
  pool, about 24.5k rows). If the full forced leg is projected to take more than 4 h, QA may draw a **seeded
  uniform random sample** of M (seed 20260922, n ≥ 4,000) **before** running anything. State it.
- **Control population K:** REF rows with REF SNR ≥ −10 dB that the matcher scores as a **hit**. Seeded random
  sample, n = 2,000, seed 20260922.

## §2. Legs (predicates as code, HK-021(r))

**Leg R (raw replay).** One process, cycles in chronological order, so the hash table warms as it did live
(standing lesson: rendering depends on history). `ft8_decode_all` on every included cycle's WAV at production
params (`nhard` 40, suppression default, passband `[140,3075)`). A row of M is **S** if the replay produces a
decode in that cycle that the harness matcher (wildcard-aware, outcome-based) matches to the REF row.
🛑 Never compare rendered text across processes as a decode difference.

**Leg F (forced).** For each row of M that is not S:
- Position: `freq` = REF freq (column `[6]`). `t` = REF DT (column `[5]`) + `δ`, where `δ` is the **median
  OWS DT − REF DT over matched pairs** in C3, recomputed in ROW 0c (expected ≈ 0.653 s).
- Try the nearest lattice cell **and** its 8 neighbours, ±1 step in time and in frequency: 9 cells.
- The row is **F** if any cell yields a CRC-valid decode (BP or OSD, production gate unchanged) whose message
  matches the REF row by the harness matcher. Otherwise it is **N**.
- 🔴 **Text match is required.** THRESH-A found CRC-valid wrong-payload OSD accepts (16/16 at `path=1`). A
  CRC-only success is **not** F. Count those separately as `F_wrong`.
- Record, per row: which cell succeeded (centre vs neighbour only), path (BP/OSD), and ldpc errors.

**Leg K (control).** Leg F, unchanged, on population K. `P_ctrl` = share of K that is F.

**Definitions:**
- `s = |S| / |M|`
- `R_F = |F| / (|F| + |N|)`
- `R_norm = R_F / P_ctrl`, i.e. forced success on misses measured in units of forced success on rows we do
  decode (HK-021(aa): the bar is relative to a measured baseline).
- CIs: 95 % bootstrap, resampling by distinct REF frequency (as `H10`), N = 2000, seed 20260921. For `R_norm`,
  resample M and K jointly.

## §3. ROW 0 (strict order; any fail ⇒ all §4 rows VOID, report the gap)

| row | check | pass |
|---|---|---|
| **0a** identity | loaded DLL SHA-256 = `38a21f84…1cba`; `ft8_extract_llrs_at`, `ft8_ldpc_decode_llrs` and `ft8_decode_all` resolve | exact |
| **0b** harness | reproduces `n_ref` 127,482 and `H10` 19.2686 pp, and |M| = the harness's strong-miss count | exact |
| **0c** position mapping | `δ` recomputed on matched pairs; **`P_ctrl` ≥ 0.90** | If the control can't be forced-decoded at REF's position, the mapping is wrong and F/N is meaningless |
| **0d** audio | every WAV used is the length `ft8_extract_llrs_at` expects (else rc = −1); count and exclude rows whose WAV is missing | exclusions ≤ 1 % of M |
| **0e** replay sanity | Leg R's decode count per cycle vs live `ALL.TXT`, over all included cycles: replay ≥ live in ≥ 0.95 of cycles | Raw replay bypasses the managed filter, so it should decode **at least** what live did. If not, the replay is not the live decoder |

## §4. Rows

Two independent families, each first-match-wins and mutually exclusive within itself.

**Family S (does the managed layer or seam lose material decodes?)**

| row | predicate | reading |
|---|---|---|
| **S1** | `CI_lo(s) ≥ 0.10` | A material share of strong misses is **decoded then dropped** after the decoder. Next: attribute it to `IsPlausibleMessage` R4/R5, text dedup or hash rendering (LIVE-GAP-NOW's seam finding). Likely a cheap fix |
| **S0** | otherwise | Post-decode loss is not material. The pool is a decoder-stage problem |

**Family L (on the rows that are not S: not found, or can't be decoded?)**

| row | predicate | reading |
|---|---|---|
| **LA** | `CI_lo(R_norm) ≥ 0.50` | **Mostly not found.** The signals are decodable where they are, so the loss is in candidate search, ranking or cap, or sync placement. Next: a candidate-stage arm. That needs a per-candidate export, which is a `src/`/`native/` change, so it goes to the Captain first (HK-011) |
| **LB** | `CI_hi(R_norm) < 0.20` | **Mostly can't be decoded even at the right place.** Extraction and bit formation, the same answer as THRESH-A but now on strong signals. Next: the Captain's decision (the density/interference lines are parked) |
| **LC** | otherwise | Mixed. Report the split and route nothing on it alone |

HK-021(k): ROW 0c changes the verdict (a bad mapping drives `R_F` toward 0 ⇒ false LB), and so does 0e (a bad
replay inflates or deflates `s`). Both are real preconditions, not decoration.

## §5. Descriptive (report every one, gates nothing)

- **D1:** the three-way split S / F / N, in counts and as pp of `n_ref`, so it adds up to `H10`.
- **D2:** F by centre cell vs neighbour only. Neighbour-only success hints at sync placement, not absence.
- **D3:** F and N by REF SNR band (−10…−6, −5…−1, 0…+4, +5…+9, ≥ +10).
- **D4:** S / F / N by cycle-load quintile (`LIVE-GAP-MAP` D4's edges, a cycle-count axis). If F concentrates
  in the busiest quintile, that points at a candidate cap.
- **D5:** `F_wrong` count and path. Leg F's BP vs OSD share.
- **D6:** for S rows, which managed step drops them, if the harness can tell cheaply (R4/R5 port from
  LIVE-GAP-NOW, dedup). Otherwise say "not attributed".
- 🛑 **No `EXPOSED`/neighbour split.** The Captain's D7 licence was "this arm only" for `LIVE-GAP-MAP`, and it
  licenses no further live stratification.

## §6. Architect predictions (blind, before any datum; scored at ruling time)

| # | prediction | P | class |
|---|---|---:|:---:|
| G-1 | ROW 0 passes (0a–0e) without a routing change | 0.70 | H |
| G-2 | S1 fires | 0.20 | H |
| G-3 | LA fires | 0.25 | H |
| G-4 | LB fires | 0.25 | H |
| G-5 | LC fires | 0.45 | H |
| G-6 | `P_ctrl` ≥ 0.95 | 0.60 | C |

Reasoning: `LIVE-GAP-MAP`'s D7 put 7.5 of the 19.2 pp in rows next to a stronger signal. Those should mostly be
N (a neighbour corrupts magnitude-only extraction wherever you look). The other 11.7 pp are the ones that
could be F. That gives a mixed reading. 🔴 LA is my "findable localised defect" direction, and **G-3 is priced
below the modal call on purpose.** DT-MISS was my last reminder: my modal call carried the bias there too.

## §7. What this does NOT do

- 🛑 No `src/`/`native/` change, no rebuild, no capture, no push, no merge (HK-011, HK-014, HK-010).
- 🛑 No new instrument. If a leg needs one, STOP and report. Do not build it.
- 🛑 Nothing re-opens DENSITY (parked), FADE/E4 (parked), THRESH-A (closed), or spectral locality (retired).
  An L-row routes a **question**.
- NFR-021: counts, rates, SNR/DT/freq values only. No callsigns or message text leave the corpus dir. Scan the
  report prose.
- Supervised if it runs long (HK-013/HK-023). Artefacts go in a dated, `README.md`'d dir (HK-016).
- Commit the report locally on `qa/live-gap-map`. Push needs the Captain's go (HK-033).
- 🔴 HK-025 is available in full. If any row is a diagnostic dressed as a gate, refuse it and say why.
