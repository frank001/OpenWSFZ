# `FP-PARITY` — ROW 0q and ROW 0m result (this session's assigned scope)

**QA, 2026-09-03 ~17:10Z** (`date -u`, HK-017). Spec:
`qa/rr-study/2026-09-03-1616-architect-to-qa-spec-fp-parity-and-inchain-floor.md`
(Architect → QA, 2026-09-03 16:16Z). Handoff:
`qa/rr-study/2026-09-03-1616-architect-to-qa-handoff-post-po-rulings.md` — priority item 2 assigns
**ROW 0q then ROW 0m, both zero-run, "minutes"**, in that order (ROW 0q first because it changes
how ROW 1 would be computed). This report covers **only those two rows.** ROW 0n/0o/0p/1/2/3 are
**not run** — see §4.

Script: `qa/rr-study/fp-parity/fp_parity_checks.py` (HK-021(r) — both predicates shipped as code).
Raw output: `qa/rr-study/fp-parity/fp_parity_results.txt`. Zero `src/`/`native/` diff
(`git diff --stat -- src/ native/` empty, verified before writing this report).

**Per spec §1 (HK-018): read, not re-derived — the offline 10.875% figure and the two known
defects between the numbers. Per spec §5 step 1, `qa/ARTEFACT_INVENTORY.md` was read first**
(covers `artefacts/` live-run hardware corpora; it does not index `qa/rr-study/results/` sweep
directories, so it does not itself answer what ROW 0q/0m need — that check is §1 below, done
directly against `qa/rr-study/results/`).

---

## 0. What was on disk (spec §5 step 1)

- `_work/m1m4_s5/` WAVs: **present** (4,000 files, already used for the M1–M4 arm; not re-rendered).
- `m1m4_s5_decodes.csv` / `m3_s1_decodes.csv`: **present**, `awgn-fp-replay/results/` (454 + 3,056
  rows).
- The six named sweeps' raw `owsfz-all.txt` + `truth.csv`: **all present**, `qa/rr-study/results/`.
  One disambiguation needed: `2e60949` matches **two** directories —
  `2026-08-30-2e60949` (the full S1–S8 battery, has `S5_matched.csv`/S5 truth rows) and
  `2026-08-31-2e60949` (an **S7-only rerun** sharing the same short SHA, no S5 data at all — the
  same trap as the earlier "S7 R3 rerun" board note). Used `2026-08-30-2e60949`.
- S1b sweep data: **not located/confirmed this session** — needed for ROW 1, not for ROW 0q/0m.
  Reported here per spec §5 step 1's "report what is missing" instruction; not chased further,
  since ROW 1 is out of this session's scope.

Nothing was missing for ROW 0q or ROW 0m. Nothing was rendered or captured.

## 1. ROW 0q — the `int` SNR conversion: truncation or rounding?

**Mechanically classified from data, not merely read from source** (though source directly
answers it too — `ft8_shim.c:1732`, `r->snr = (int)roundf(snr);`, and C's `roundf` is
round-half-away-from-zero). Compared each row's integer `reported_snr_db` against
`reconstructed_snr_db` (= `signal_db − local_noise_db − 26.5`, float) across **both** existing
decode CSVs: **3,510 rows** (454 from `m1m4_s5_decodes.csv`, 3,056 from `m3_s1_decodes.csv`).

🔴 **Scope note, disclosed rather than silently resolved:** the spec's own text says "2,754 rows
already on disk" for these two files. The actual combined row count is 3,510. **2,754 = 454 +
2,300** is M1M4's full count plus **only M3's genuine (truth-matching) subset** — a number from
the M1–M4 report, not from either CSV's own row count. Since the int↔float cast rule being tested
is a shim-level property of *every* decode (genuine or spurious — the cast happens before any
truth join could possibly apply), restricting to genuine-only has no stated justification anywhere
else in ROW 0q's own text. Read as an editorial miscount, not a scope instruction, and **all 3,510
rows were classified**, not 2,754.

| Candidate rule | Agreement |
|---|---|
| **round-half-away-from-zero** | **3,510/3,510 (100.00%)** |
| round-half-to-even | 3,505/3,510 (99.86%) |
| truncate-toward-zero | 2,004/3,510 (57.09%) |
| floor | 1,775/3,510 (50.57%) |

**Exactly one rule reaches 100% agreement: round-half-away-from-zero. ROW 0q does not fire.**

**Consequence (spec §2.2):** the conversion is **rounding, not truncation** — there is **no
systematic upward bias**. The mechanical error from reading an integer SNR back as a float excess
is **at most 0.5 dB, in either direction**, not a one-sided truncation artefact. For any future
floor computed on reconstructed in-chain excess (ROW 1, not run this session), the conservative
correction is to **subtract 0.5 dB** — round-half-away-from-zero can report an excess up to 0.5 dB
*higher* than the true underlying float value for a negative excess.

## 2. ROW 0m — in-chain numerator, recounted independently

**Method:** for each of the six named sweeps, loaded that sweep's own `truth.csv`, restricted to
`S5` parts 0/1 (the AWGN population — `s5-level`'s own ROW 0f enumeration; parts 2/3 are
carrier/multi-carrier). Parsed the sweep's raw `owsfz-all.txt` with
`harness/common.py`'s `parse_all_txt`/`normalise_slot` — a shared, non-aggregating line-format
parser (also used *by* `matcher.py`, but carrying none of its Pass-2/OR-dedupe/attribution-join
logic, which is what HK-026 and the spec bar reusing). **No `*_matched.csv` was read anywhere in
this check, and `matcher.py` itself was never imported.** An event is a slot (cycle) with ≥1
decode landing on it, per §2.1.

| Sweep | Denom (S5 p0/1 cycles) | Recounted `k` | Published `k` | Match | Published denom | ==60? | Max ALL.TXT gap (s) | S5 cycles outside ALL.TXT span |
|---|---|---|---|---|---|---|---|---|
| `7d36038` | 60 | 1 | 1 | ✅ | 120 | ❌ | 2280.0 | 0 |
| `f5dec23` | 60 | 4 | 4 | ✅ | 120 | ❌ | 1935.0 | 0 |
| `22b749c` | 60 | 0 | 0 | ✅ | 60 | ✅ | 1185.0 | 0 |
| `872ba65` | 60 | 1 | 1 | ✅ | 60 | ✅ | 795.0 | 0 |
| `2e60949` | 60 | 2 | 2 | ✅ | 120 | ❌ | 1335.0 | 0 |
| `3b52608` | 60 | 4 | 4 | ✅ | 60 | ✅ | 315.0 | 0 |

**Every recounted `k_i` matches the published number exactly — all 6/6.** The Architect's own
blind prediction (§7, P(fires) ≈ 0.75, "I expect at least one published numerator not to
reproduce") **did not materialise on the numerator axis**: the attribution join, unaudited as it
was, got every one of the six numbers right. **ROW 0m still fires**, but on the **denominator**
condition only — 3 of 6 published denominators are 120, not 60, exactly the already-known
Amendment 2 A2.1 defect, now independently confirmed rather than merely re-arithmetic.

**Coverage sanity** (what this row cannot otherwise detect, per the spec's own caveat): zero S5
cycles fall outside any sweep's observed `owsfz-all.txt` timestamp span. The largest gaps between
consecutive `ALL.TXT` records range 315–2,280 s across sweeps — none of them swallow an S5 cycle,
so there is no sign of a logging dropout during the S5 window in any of the six sweeps.

**⇒ Consequence, per spec §4 (fires either way changes what is citable):**

> **The recounted `Σk_i/360` and its exact Clopper–Pearson 95% CI replace `[1.15%, 3.85%]` as the
> in-chain comparator for all future work. The 2.22% figure is retired, not merely corrected.**

**`12/360 = 3.333%` [95% CP CI 1.934%, 5.345%], n=360.** This is the number Ruling 3 on the board
flagged as "pending `FP-PARITY` ROW 0m" and explicitly marked **not yet ratified** ("a
re-arithmetic of the same unaudited rows"). **It is now ratified** — independently recounted from
raw decode logs, not re-arithmetic on `matcher.py`'s own output.

## 3. What this changes, stated plainly

- **Retired:** `2.22%` and its CI `[1.15%, 3.85%]` (both from the mixed-denominator ROW 1 band).
- **New in-chain comparator:** `3.333%` **[1.934%, 5.345%]**, n=360, 12 events — independently
  recounted, not a correction of the old figure.
- **Offline chronic rate, unchanged this session:** `10.875%` [9.93%, 11.88%], n=4,000
  (`M1-M4-report.md` — solid per spec §1, not re-run).
- **Ratio, now citable as a single number rather than a band:** `10.875 / 3.333 ≈ 3.26×`. The
  board's prior caveat — *"~5× is NOT citable... say ~3×–5×, pending `FP-PARITY` ROW 0m"* — is
  **discharged for the denominator/numerator-provenance part of the gap**. The ratio is **not yet
  the final word**: ROW 0n (normalisation parity) and ROW 0o (decode-param parity) are still
  unrun, and either could move the *offline* side of this ratio (spec §5 orders 0o/0p/0n *after*
  0m for exactly this reason — 0m was cheapest and came first per the handoff).

## 4. What was NOT run this session, and why

Per the handoff's explicit priority-2 scope ("Start with ROW 0q ... then ROW 0m ... Both are
zero-run"), only those two rows were executed:

- **ROW 0n** (normalisation parity, paired re-decode of `_work/m1m4_s5/` with `NormalisePcm`
  applied) — a real decode run at N=1,000/part (2,000 slots), not zero-run; needs HK-013/HK-023
  supervised-run treatment if it runs long. Tests-only per spec §3 (zero `src/`/`native/` diff),
  but genuinely out of *this* pass's assigned scope.
- **ROW 0o** (decode-param parity against live `config.json`) and **ROW 0p** (WAV→decoder path
  identity assertions) — quick, but likewise not on the handoff's explicit list for this pass.
- **ROW 1** (`F`, the in-chain genuine excess floor) — needs an S1b sweep confirmed on disk (§0,
  not located this session) and, per spec §5's own ordering, comes after 0o/0p/0n close clean.
- **ROW 2/ROW 3** — depend on ROW 1.

**Nothing in §0's bars is touched: this report proposes no hardware capture and authorises no
filter build.**

## 5. NFR-021

No message text, no callsign-shaped content anywhere in this report, the script, or
`fp_parity_results.txt` — both rows operate on integers/floats (SNR values, timestamps, event
counts) only. Scanned individually with the project's own `nfr021_pre_merge_scan.py` `scan()`
(imported, not reimplemented — HK-022's directory-walk trap avoided the same way as the
`S5-LEVEL` and `redact_row0k_decodes.py` passes): 0 flagged occurrences across all three new files.
