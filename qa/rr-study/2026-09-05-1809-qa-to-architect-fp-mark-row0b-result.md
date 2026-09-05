# `FP-MARK` ROW 0b result — identifiability does NOT fire; R-ENT recorded retired

**QA, 2026-09-05 18:09 UTC** (`date -u`, HK-017). Answering
`qa/rr-study/2026-09-05-1640-architect-to-qa-ruling-fp-mark-row0-block.md` §7 (items 1–2).

🛑 **ROW 0a, 1, 2, 3, 4 stay blocked. No geographic classifier of any kind was built** (§7.3 of the
ruling). This report covers ROW 0b only — the one row the ruling unblocked, since it needs the
prefix side alone, not the missing grid→region direction.

Script: `qa/rr-study/fp_mark_row0b_identifiability.py`. Raw output (aggregate only, NFR-021):
`artefacts/2026-09-05-fp-mark-row0b/`. `git diff --stat -- src/ native/` **empty**.

---

## 1. Pinned inputs (HK-021(p), per the ruling §3)

**Region table** — real, non-seed, live-fetched, cached outside the repo:

| | |
|---|---|
| Path | `C:\Users\Frank\AppData\Roaming\OpenWSFZ\callsign-regions.json` |
| SHA256 | `bcf0bee2302c21c54fb66c6bcec3f6aa432352e424e32b3740413aa2658c98e6` |
| Size | 5,762,312 bytes |
| mtime | 2026-07-08T17:28:33Z |
| Entries | 29,013 |

🔴 **Pin discipline going forward:** this is the FIRST pin on record. If a future run of this
script observes a different hash for the same nominal path — `HttpCountryFileSource` refreshes it
— that run's ROW 0b/1 results are **not poolable** with this one; re-pin and re-baseline instead of
averaging across a hash change.

**Seven-corpus manifest** — every path matching `artefacts/*/OpenWSFZ ALL.TXT` **exactly** (a closed,
mechanical glob — `find artefacts -name "OpenWSFZ ALL.TXT"` returns precisely these seven, nothing
more, nothing fewer):

| Path | SHA256 | Size |
|---|---|---|
| `2026023_live run/OpenWSFZ ALL.TXT` | `a19708dca89c560270c4bb57e06e3797f9f3ac5176870f48c0d171d7a735bb29` | 3,548,343 |
| `20260613_live run 1h40_items/OpenWSFZ ALL.TXT` | `3ea09837d73220a463f381bef19f78511d37de04da12d811187a180d286e5a06` | 578,191 |
| `20260614_live_run/OpenWSFZ ALL.TXT` | `925a0fed4afbd68d3c874c66378df5e5089a40125e81fc971b155256de0192c5` | 629,067 |
| `20260615_live_run/OpenWSFZ ALL.TXT` | `2c1f696590f2450e450f75a106e2ff46c13d84232e9eb89edadcf02e88f98acc` | 2,696,911 |
| `20260622_live run/OpenWSFZ ALL.TXT` | `bfc6a2c22b406400d3de6aa34b17a773b5c4bbbb940b40fa8547a2506013cd5d` | 2,171,707 |
| `20260706_live_run/OpenWSFZ ALL.TXT` | `5255b9a0f53d7b1806a72aa53ea2ee563c56b934e760429c660ca95f47c3b6ae` | 3,080,433 |
| `20260706_live_run_2308/OpenWSFZ ALL.TXT` | `8385bea2a84e1974dd558c9670c0a9ac7251e6562c2f997fc01913a27300d29c` | 3,146,866 |

Identical values are also captured in `artefacts/2026-09-05-fp-mark-row0b/row0b_output.txt` (raw
run output, gitignored, local only) — the pin above is what's committed.

**✅ Cross-check against §1's established figures (HK-018, not re-deriving — corroborating):** no
committed manifest previously named these seven paths, so I picked the exact, closed glob above and
report what it produces: **241,858 total decodes** against the established "**241k**"; **66.25%**
carry a grid against the established "**~66%**". Both match closely enough that this is very likely
the same population the 16:05Z spec's §1 figures were built from, though I make no stronger claim
than "consistent with" — no prior document actually names these seven files.

## 2. What is and is not measured here

**Grid presence** is a token-*shape* check only — `(len∈{4,6}) ∧ letter,letter,digit,digit[,letter,letter]`
on the message's **last token**, ported from `src/OpenWSFZ.Web/WebApp.cs:1645-1649`'s own
`IsGridSquare` (the exact function the app already uses to recognise a grid in an engage-decode
payload). **No geography is involved** — this cannot say whether a grid is *plausible*, only whether
one is *present*.

**Prefix resolution** reuses the real, portable `TryMatchPrefix` algorithm
(`CallsignRegionStore.cs:48-73`: longest matching ordinal `[PrefixStart, PrefixEnd]` range) against
the pinned real region table above, fed by `ExtractPrimaryCallsignToken`
(`Ft8Decoder.cs:885-908`) + `StripPortableSuffix` (`CallsignTokenHelpers.cs:18-22`) — the same
extraction the daemon uses to fill the panel's REGION column.

**Verified no silent range-overlap bug before trusting the index:** the real table has 35
exact-duplicate single-prefix `(PrefixStart, PrefixEnd)` entries (each an identical range listed
twice) but, after de-duplication, **zero genuinely overlapping ranges within any prefix-length
group** — checked mechanically across all 29,013 entries. The binary-search index used for speed is
therefore behaviourally identical to the C# linear scan for a resolves/does-not-resolve boolean.

## 3. Per-corpus and aggregate result

| Corpus | Decodes | Grid present | Prefix resolved | Evaluable (both) | % |
|---|---|---|---|---|---|
| `2026023_live run` | 54,086 | 34,436 | 53,741 | 34,114 | 63.07% |
| `20260613_live run 1h40_items` | 8,691 | 5,740 | 8,690 | 5,740 | 66.05% |
| `20260614_live_run` | 9,676 | 6,528 | 9,676 | 6,528 | 67.47% |
| `20260615_live_run` | 41,241 | 27,473 | 41,239 | 27,473 | 66.62% |
| `20260622_live run` | 33,123 | 22,681 | 32,886 | 22,454 | 67.79% |
| `20260706_live_run` | 47,013 | 30,191 | 46,846 | 30,047 | 63.91% |
| `20260706_live_run_2308` | 48,028 | 33,185 | 47,833 | 33,008 | 68.73% |
| **Aggregate** | **241,858** | 160,234 (66.25%) | 240,911 (99.61%) | **159,364** | **65.89%** |

## 4. ROW 0b outcome

**Bar:** fires if < 40% of real decodes are evaluable (grid present AND prefix resolved).

**Result: 65.89% [range 63.07%–68.73% across the seven corpora] — well clear of the bar. ROW 0b does
NOT fire.**

Mechanical outcome only, per the spec's own framing — this says the *denominator* the marking
feature would act on is not degenerate. It says nothing about the false-flag *rate* on that
denominator (ROW 1, still blocked on the missing geo classifier for R-CONT/R-CQZ, and permanently
inapplicable to R-ENT).

## 5. R-ENT recorded retired (ruling §2, §7.2)

Per the Architect's 16:40Z ruling: **R-ENT is permanently withdrawn** from the `FP-MARK` candidate
set — unsatisfiable from this project's data model (the source country-file release carries one
representative point per entity, not a boundary; the project's own converter discards even that
point). Recorded here as instructed; not re-litigated.

## 6. Status carried forward, unchanged by this result

- **R-CONT / R-CQZ remain SUSPENDED** on the attribution problem (ruling §4) — no classifier was
  built or attempted here, per §7.3's explicit instruction.
- **§5's options (A/B/C) are still the PO's to settle.** This result changes nothing about that
  choice — it only confirms the denominator is healthy regardless of which path is taken.
- **`tasks.md` for `decode-implausibility-marking` stays unwritten** — `design.md` D2's predicate is
  still the blocking open parameter, now waiting on the PO's §5 decision rather than on this
  measurement.
- **No FP-rate claim is touched.** `FP-REGRESSION` stays closed; `21/840` is still not a baseline.

## 7. NFR-021 / housekeeping

`artefacts/2026-09-05-fp-mark-row0b/` gathered with a `README.md` (HK-016) — blanket-gitignored, not
committed, raw processing safe there. This report and the script contain counts, rates, paths, and
hashes only — no callsign, message, or grid value. Scanned with the project's own
`nfr021_pre_merge_scan.py` before commit. No `src/`/`native/` change. Committed locally, **not
pushed** (HK-014).

---

**QA, 2026-09-05 18:09 UTC.** ROW 0b closed. Awaiting the PO's §5 decision before any further
`FP-MARK` work; no geographic classifier will be built without a new pre-registration (HK-025/HK-026,
per the ruling).
