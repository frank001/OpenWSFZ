# `DT-MISS` — do we miss late-starting stations more? A counts-only check on C3

**Architect, 2026-09-22 17:54Z** (`date -u`, HK-017). Branch `arch/live-gap-map` (the M1 follow-up of
`LIVE-GAP-MAP`, spec `2026-09-21-1555` §3.10). Docs-only; no `src/` or `native/` change.

**Authorised:** the Captain, 2026-09-22: *"have QA run the DT miss-rate check"*. No capture and no rebuild.
It runs on the existing C3 archive logs.

---

## §1. The question, and why it can matter

The ANOVA shows our reported DT sits **+0.653 s** above WSJT-X's, with a per-decode SD of 0.051 s. The same
offset appears in every clean run since July. About 0.5 s of it is a **definition difference only**: we measure
from the slot start (`Ft8LibInterop.cs`, "time offset (s) from cycle start"), WSJT-X from the nominal 0.5 s TX
start. That part is cosmetic and changes nothing in decoding.

What **can** cost decodes is window geometry. The candidate search covers buffer starts from −1.6 s to +3.04 s
(`decode.c:290`, `time_offset` −10…+19 in 0.16 s blocks). The buffer is 15 s (`monitor.c:113`). An FT8
transmission is 12.64 s long, so it fits whole only if it starts ≤ **2.36 s** into our buffer. Translated with the
0.653 s offset, that edge sits at **REF DT ≈ +1.71 s**. Past it, trailing symbols fall outside the buffer.

**Question:** is our miss rate higher for stations that start late, and does that cost a material share of
decodes?

## §2. Data and definitions (predicates as code, HK-021(r))

- **Corpus:** C3 with the Amendment 3 cut applied (`AMD3_EXCLUDE`, same harness path), so `n_ref` = 127,482.
- **Matching:** the harness's existing REF↔OWS matcher, unchanged. A REF row is a **miss** if the matcher leaves
  it unmatched.
- **REF DT is column `[5]`** of WSJT-X's `ALL.TXT` (`[4]` is SNR, `[6]` is frequency). 🛑 Swapping 5 and 6 inverts
  results (`architecture-ft8-lib.md`). Assert it in code: the median REF DT over C3 must lie in [0.0, 0.6] s,
  otherwise STOP.
- **Population:** REF rows with REF SNR ≥ −10 dB, which is the `H10` population. Reporting it here removes the
  confound that late stations might just be weaker.
- **Bands of REF DT (s):** `<−0.5`, `[−0.5,0.0)`, `[0.0,0.5)`, `[0.5,1.0)`, `[1.0,1.5)`, `[1.5,2.0)`, `≥2.0`.
- **CORE** = `[0.0, 1.0)`. **LATE** = `≥ 1.5`.
- `miss(B)` = misses / rows in band B. `Δ = miss(LATE) − miss(CORE)`.
- **Excess** = `Δ × n(LATE) / n(pop)` × 100, in pp of the population. This is how much of the total miss rate
  the late-start effect accounts for.
- **CI:** 95 % bootstrap on `Δ`. Same scheme and seed as the harness's `H10` (resample by distinct frequency,
  N = 2000, seed 20260921).

## §3. Rows (strict order, first match wins, mutually exclusive)

| row | predicate | reading |
|---|---|---|
| **T0** | `n(LATE) < 300` | Underpowered. Report the table, route nothing |
| **T1** | `CI_lo(Δ) > 0` **and** `Excess ≥ 0.5` | **Timing costs a material share of decodes.** The Architect specs a window fix (start later or lengthen, about 0.15 s scale) for a Developer session |
| **T1b** | `CI_lo(Δ) > 0` **and** `Excess < 0.5` | Real but small. Record it. No fix is licensed on this alone |
| **T2** | otherwise | No measurable late-start penalty. Timing is ruled out as a cause of the strong-miss pool |

The 0.5 pp bar is the project's existing `GAIN_BAR` (the smallest gain worth shipping), not a new number.

## §4. Descriptive (report every one, gates nothing)

- **D-a:** for each band, report `n`, misses, `miss(B)`, and share of all misses. Do it on the `H10` population
  **and** on all REF rows.
- **D-b:** a 0.1 s-resolution miss-rate curve over REF DT [−1.0, +2.5] on the `H10` population, as a table
  plus one chart. This is where a cliff near +1.7 s would show.
- **D-c:** OWS DT − REF DT for **matched** pairs, per band. Is the 0.653 s offset constant across DT?
- **D-d (replication, no row):** D-a on C2 (the `A1` corpus). 🛑 C2 is nhard 60 and a different day. Only the
  shape across DT is comparable, never the level.

## §5. ROW 0

- **0a:** the harness reproduces the Amendment 3 figures before any DT split: `n_ref` 127,482,
  `H10` 19.2686 pp. Mismatch ⇒ STOP.
- **0b:** the column-`[5]` assertion in §2.
- **0c:** band `n`s sum to `n(pop)` exactly. No row may be dropped silently. Rows with an unparseable DT are
  counted and reported.

## §6. Architect predictions (blind, before any datum; scored at ruling time)

| # | prediction | P | class |
|---|---|---:|:---:|
| T-1 | T1 fires | 0.20 | H |
| T-2 | T1b fires | 0.45 | H |
| T-3 | T2 fires | 0.30 | H |
| T-4 | T0 fires | 0.05 | C |
| T-5 | D-b shows the steepest rise in miss rate between +1.5 and +2.0 s | 0.55 | C |

Reasoning: the geometry predicts a cliff near +1.71 s, so something should show in the late band. But stations
starting that late are few, so the **excess** is probably under the bar. 🔴 This is my "findable localised
defect" direction, so T-1 is priced low on purpose.

## §7. What this does NOT do

- 🛑 No `src/`/`native/` change, no rebuild, no push, no merge (HK-011, HK-014, HK-010).
- 🛑 No DT display calibration. That is cosmetic and a separate decision for the Captain.
- NFR-021: counts, rates and DT/SNR values only. No callsigns or message text. Scan the report prose.
- Report to be committed locally on `qa/live-gap-map`. Push needs the Captain's go (HK-033).
- 🔴 HK-025 is available in full. If any row here is a diagnostic dressed as a gate, refuse it and say why.
