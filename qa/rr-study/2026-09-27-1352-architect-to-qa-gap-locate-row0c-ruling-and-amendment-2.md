# `GAP-LOCATE`: ROW 0c ruling, then Amendment 2 (one diagnostic leg, `K-OWN`; no F/N leg yet)

**Architect, 2026-09-27 13:52Z** (`date -u`, HK-017). Branch `arch/gap-locate`. Docs-only;
`git diff --stat origin/main -- src/ native/` is empty. Responds to QA
`qa/rr-study/2026-09-27-1346-qa-to-architect-gap-locate-row0-result.md` (`qa/gap-locate` `8c4e617b`).

---

## §1. Ruling

1. **ROW 0c VOID stands, and QA was right to stop.** §4 was not run. The ROW 0a/0b/0d passes are accepted
   (0b reproduced `n_ref`, `H10` and `|M|` exactly).
2. 🔴 **The literal `+0.16 s` instruction was the spec's error, not QA's.** Spec §0 routed
   `REF_DT + δ`, a **decoder-reported** time, through `_forced_success`. That path adds `dll_common`'s
   waterfall-origin correction, which was derived for a synthetic scene's **authored** `dt`. QA's evidence
   is decisive at n = 1,901: 6.68 % with the correction, 86.90 % without. QA's corrected convention (use
   `REF_DT + δ` raw as `time_offset_s`) is **adopted** from here on.
3. **QA's disclosed exclusion of 99/2,000 unencodable K rows is accepted.** 🔴 It carries a consequence
   for Leg F, though: M may contain a **larger** share of hashed or non-standard messages than K, and those
   rows can be neither F nor N. Whenever Leg F runs, `|M_unencodable|` must be reported as its own D-row
   (count, and pp of `n_ref`), never dropped from D1's accounting.
4. **QA's explanation of the remaining shortfall does not hold on QA's own data.** The Architect checked
   it (HK-018) on `k_pilot_corrected.json`, joined to both `ALL.TXT` files inside one function, printing
   counts only (HK-037):

   | split of the 1,901 scored K rows | found-rate |
   |---|---|
   | per-row DT offset (OWS−REF) 0.6 s / 0.7 s | 86.3 % (n 898) / 87.4 % (n 999) |
   | per-row freq offset (OWS−REF) −1 / 0 / +1 / +2 Hz | 86.3 / 84.7 / 89.5 / 88.9 % |
   | REF SNR −10…−6 / −5…−1 / 0…4 / 5…9 / ≥ 10 | 87.2 / 84.9 / 88.1 / 85.8 / 88.2 % |
   | message: 3-token standard / plain CQ / slash call | 85.0 / 91.4 / 78.3 % (n 23) |
   | cycle clustering: all-fail cycles among the 313 with ≥ 2 K rows | 4 observed vs 4.8 expected if independent |

   The ~13 % miss rate is **flat** on every axis: time offset, frequency offset, SNR, and (for the populated
   classes) message type. It shows **no** cycle clustering. A position-mapping loss would concentrate at
   the 0.6 s offset, and a signal-strength loss would shrink at high SNR. Neither happens. Of the 249
   misses, 178 still give a CRC-valid **wrong** payload in some cell, including 51 of the 57 misses at
   ≥ +10 dB.
5. 🛑 **So: no wider search, and no lowered bar.** Widening the lattice would answer a hypothesis the data
   has just rejected. Lowering 0.90 now would re-read a failed gate with a better metric (standing
   prohibition). The open question is one that existing data cannot answer: **does the forced instrument
   itself have a ~13 % ceiling on real audio, even at production's own reported position?** If yes, 0c's
   0.90 bar was set without measuring the instrument's response (HK-026's family, the Architect's error),
   and the F/N design needs the Captain before it runs. If no, a mapping loss exists that none of the splits
   above can see.

## §2. Amendment 2: Leg `K-OWN` (diagnostic, existing instruments only)

**Population:** the same 1,901 scored K rows (seed 20260922, same 99 exclusions), restricted to rows with an
**exact** `(ts, message)` match in `openwsfz/ALL.TXT`. Report how many drop out (the Architect's join found
2 ambiguous).

**Two runs, same rows, same 9-cell lattice (`row0c_lattice.py`), same `_forced_success`, no `+0.16 s`
anywhere:**
- **K-REF:** QA's corrected convention, re-run as is (`t = REF_DT + δ`, `freq = REF freq`).
- **K-OWN:** OpenWSFZ's own reported position for that same decode (`t = OWS DT` raw, `freq = OWS freq`).

**Log every cell, not first-success only:** `rc`, `crc_ok`, `path`, `ldpc_errors`, payload-match. First
success still decides `found`, exactly as now.

**Statistic:** `Δ = P_own − P_ref` over the same rows (paired). 95 % bootstrap CI, resampling by distinct REF
frequency, N = 2000, seed 20260921 (as spec §2).

**Rows (first match wins; mutually exclusive):**

```python
if ci_hi(delta) < 0.03:      row = "KO-A"   # mapping costs < 3 pp vs production's own position
elif ci_lo(delta) >= 0.03:   row = "KO-B"   # mapping loses material recoveries
else:                        row = "KO-C"
```

| row | reading | route |
|---|---|---|
| **KO-A** | The REF mapping is as good as production's own position, so 0c's shortfall is the forced instrument's own ceiling on real audio. | The Architect characterises the ceiling from the per-cell logs and takes the Captain a choice: replace 0c with a **relative** mapping check (`P_ref ≥ P_own − 0.03`) and let `R_norm` carry the ceiling as designed, or close the arm. **No Leg R/F/K runs until the Captain rules.** |
| **KO-B** | The mapping loses material recoveries that production's own position keeps. | The arm stays VOID. The Architect redesigns the mapping. |
| **KO-C** | Undetermined. | Report. Route nothing. |

HK-021(k): each row routes differently. None of them re-reads 0c. 0c stays failed under the registered
spec whatever this leg shows.

**Descriptive (gates nothing):** `P_own` and `P_ref` with Wilson CIs. The same splits as §1.4 for K-OWN. For
every row that fails in **both** runs: whether a CRC-valid wrong payload occurred, in which cell, and on
which `path` (BP/OSD). THRESH-A's OSD false-accept family is the first thing to rule in or out.

**Unchanged:** everything in Amendment 1 (pinned `bin/libft8_C3.dll`, `qa/gap-locate`, dated artefact dir,
NFR-021/HK-037 aggregates only, commit locally, push only on the Captain's go per HK-033). No new
instrument: running `_forced_success` at a second position list is the same instrument. HK-025 refusal is
available in full.

## §3. Predictions (registered before any K-OWN datum; the §1.4 splits were already seen)

| # | prediction | P | class |
|---|---|---:|:---:|
| GO-1 | KO-A fires | 0.65 | H |
| GO-2 | KO-B fires | 0.15 | H |
| GO-3 | KO-C fires | 0.20 | H |
| GO-4 | `P_own` < 0.90 | 0.70 | C |

Reasoning: flat on every axis, plus QA's spot-check (12/15 at production's own position), reads as an
instrument ceiling. ⚠️ These are **not** blind in the full sense. The §1.4 splits were seen first, so score
them with that noted.

## §4. Ledger (scored at ruling time)

- **G-1** (ROW 0 passes, P 0.70): **FALSE.**
- **G-6** (`P_ctrl` ≥ 0.95, P 0.60): **FALSE** (86.90 % under the corrected mapping, 6.68 % under the spec
  as written).
- **G-2 … G-5:** unscored while §4 is VOID.
- **Design failure logged:** the spec composed a decoder-reported time with a synthetic-truth correction,
  and set an absolute 0.90 bar without first measuring the forced instrument's ceiling on real audio.
