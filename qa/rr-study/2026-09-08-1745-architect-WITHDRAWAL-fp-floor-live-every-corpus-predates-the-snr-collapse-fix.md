# 🛑 WITHDRAWAL — `FP-FLOOR-LIVE` is withdrawn: every corpus in it predates the SNR-collapse fix

**Architect, 2026-09-08 17:45Z** (`date -u`, HK-017). Branch `arch/fp-floor-operator-setting`.

**`FP-FLOOR-LIVE` (`2026-09-08-1710-…`, ratified by the PO at 17:24Z) is WITHDRAWN before arming.**
QA must not run it. The gate design, the ROW structure and the ratified bar are all sound; **the
population is invalid**, and no amendment fixes that.

---

## 1. What happened

The PO asked why we were not extending the S1 ladder, then proposed mixing synthetic truth into real
captured audio. Chasing that led to `run_scenario.py:249-257`, which documents that libft8's
noise-floor estimator misreads **bandlimited** noise — *"SNR readings ~15 dB below the true value in
roughly one in four trials (D-003)"* — and that single-signal scenarios use **wideband** AWGN to
avoid it, while the multi-signal ones (S4/S7/S8) keep the rolloff.

I flagged that to the PO as a probable dominant risk to the whole operator-setting proposal. **I then
ran the free check against sweep data already on disk, and it corrected me.**

## 2. What the data says — the effect was REAL, LARGE, and is FIXED

Truth-matched OpenWSFZ decodes **reported at ≤ −24 dB**, i.e. decodes the proposed filter would
destroy. All matched `*_matched.csv` on disk, 262 files, aggregates only:

| scenario | n | killed by the cut | true SNR of killed (min/med/max) |
|---|---|---|---|
| **S4** (density, multi-signal) | 960 | **122 — 12.71%** | −18 / −12 / −6 |
| **S8** (band scene, multi-signal) | 790 | **60 — 7.60%** | −15 / −12 / −12 |
| S7 (multi-signal) | 12,418 | 0 — 0.00% | — |
| S8HN | 275 | 0 — 0.00% | — |
| S1 / S1b / S2 (wideband) | 1,169 | 1 — 0.09% | −24 → reported −24 (**correct**, not an error) |

🔴 **But split by sweep date, it disappears:**

| sweep | S4 n | S4 killed | S8 n | S8 killed |
|---|---|---|---|---|
| 2026-08-05 | 96 | **39.6%** | 50 | **20.0%** |
| 2026-08-15 | 96 | **27.1%** | 52 | 9.6% |
| 2026-08-21 | 96 | **32.3%** | 50 | **20.0%** |
| 2026-08-22 | 96 | 0.0% | 105 | 7.6% |
| **2026-08-27 →** | 96 | **0.0%** | 55 | **0.0%** |
| 2026-08-29 / 08-30 / 09-02 / 09-03 | 96 each | **0.0%** | 55 each | **0.0%** |

✅ **Cause identified from version control, not inferred:** `c3a9ea8` —
**`fix(ft8): negative time_offset SNR collapse (shim 20260046)`**, landed **2026-08-22**, the exact
sweep at which S4 goes 32.3% → 0.0%. Its own header notes it *"DOES touch the production decode
path"* (`ft8_shim.c:1485-1513`). Current `main` is `20260050`, five versions past it.

⚠️ **"0.0%" means "below ~0.40%", not "zero".** Pooled post-fix: **0 of 755** (S4 480 + S8 275),
rule-of-three 95% upper bound **0.397%**. Quote it that way.

⚠️ **S7's and S8HN's zeros are NOT evidence of anything.** S7's true-SNR support is **−6 … +3** — it
never visits the danger zone at all. Reading its zero as reassurance would be reading a flat
instrument response as a measurement (HK-026).

⚠️ **My initial reading conflated two different things.** What the data shows is the **time_offset
SNR collapse**, now fixed. It is **not** a measurement of the D-003 bandlimited-estimator concern,
which remains untested and is a separate, older issue.

## 3. ✅ `FP-PARITY` is NOT contaminated — checked, not assumed

`F = 8.00 dB` was computed *"over every **post-`c3a9ea8`** sweep on disk"* (`FP-PARITY` §4 ROW 1),
and §2.2 chose the separate `signal_db`/`local_noise_db` terms explicitly to be *"immune to the
`c3a9ea8` SNR-scale change"*. `C = +1.622` is a **maximum** over false accepts, which an artificially
*low* reading cannot inflate. 🛑 **ROW 3 stands, uncontaminated. Nothing here reopens it.**

## 4. 🔴 Why `FP-FLOOR-LIVE` must be withdrawn rather than amended

Its §2.1 corpora, against the fix date of **2026-08-22**:

| corpus | date | status |
|---|---|---|
| `20260803_live_run_1713` (primary) | 2026-08-03 | 🛑 **PRE-FIX** |
| `20260808_live_run_0016-8080` / `-8081` | 2026-08-08 | 🛑 **PRE-FIX** |
| `20260808_live_run_1154-*-17m` | 2026-08-08 | 🛑 **PRE-FIX** |
| `20260809_live_run_0155-*-80m` | 2026-08-09 | 🛑 PRE-FIX (already excluded on provenance) |

**Every corpus in the spec predates `c3a9ea8`.** The 873 and 794 decodes my §2.3 drafting probe
found at ≤ −24 dB were produced by a decoder carrying a defect that collapsed reported SNR — the
arm would have measured **a decoder that no longer exists**, and its ROW 1/2/3 verdict would have
described `20260049`-era behaviour while being read as a licence to ship a setting on `20260050`.

🛑 **No amendment repairs this.** There is no post-`c3a9ea8` corpus to substitute: the artefact
inventory's newest dual-decoder live comparison is **2026-08-09**, and everything after it
(`2026-08-30-rr-s1s8-…`, `2026-09-02-…`, `2026-09-03-…`) is R&R cycle-audio, **not** a
two-decoder live capture. **The population the spec needs does not exist on disk.**

## 5. What survives, and what it costs

- ✅ **The gate design survives intact** — ROW structure, the inherited `T`, the wildcard-matching
  requirement, ROW 0b's positive control, Amendment 1's rounding bound, Amendment 2's power
  disclosure and the PO-ratified `hi ≤ 0.02`. All of it is reusable verbatim against a valid corpus.
- 🔴 **What it costs is a capture run**, and that is the Captain's to authorise — not proposed here,
  and this document is **not** a request for one.
- ✅ **The PO's instinct is vindicated twice over.** "Use real audio" was right, and "turn on the
  real radio" turns out to be **necessary rather than merely more realistic** — because no post-fix
  live corpus exists at all. Neither of us identified that reason in advance.

## 6. Record

- 🔴 **This is an Architect drafting defect, not QA's and not the PO's.** HK-018's own instruction is
  to check the data before building on it; I pinned four corpora by *provenance* (audio-path
  integrity, hardlink status, band) and **never checked them against the binary's own fix history** —
  while the shim-version discipline that would have caught it is written down in this project's
  standing rules and was quoted in my own §0.2 disclosure.
- ⚠️ **The spec was ratified by the PO before this was found.** The ratification stands as a record
  of a decision correctly taken on the information available; it is not evidence the arm was sound.
- ✅ Probes committed alongside so every number here is re-runnable:
  `fp_floor_live_d003_footprint.py`, `fp_floor_live_effect_currency.py`.
