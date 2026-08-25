# QA -- corrected-predicate re-derivation (WITHDRAWAL Sec.6 item 2)

**Author:** QA, 2026-08-25 17:56Z (`date -u`, HK-017). Repo `main` at `9a2845b`.
**Answers:** `qa/rr-study/2026-08-25-1735-architect-WITHDRAWAL-part-a-metric-was-blind-to-the-treatment.md`
Sec.6 item 2 -- *"re-derive `rate_unresolved` and bucket B1 on the corrected predicate, from the
dumps already on disk, with cycle-clustered CIs -- QA's numbers, not mine."*
**Harness:** `qa/rr-study/g2a-remeasure-a/rederive_corrected_predicate.py` (new),
`common_g2a.has_unresolved_hash_marker()` / `rows_from_dump_corrected()` (new). No rebuild, no
replay -- reuses the L1/L2_run1/L2_run2 decode dumps already on disk
(`artefacts/2026-08-25-g2a-remeasure-a/`) and `part_a.py`/`partition.py` unmodified (HK-018).
**Result:** `qa/rr-study/g2a-remeasure-a/results/2026-08-25-9a2845b-corrected-predicate/`.
**Status:** docs+qa-tooling only. No `src/`, no `native/`, no rebuild, no push, no merge
(HK-011/014). NFR-021: counts and rates only, no message text.

---

## 1. The corrected predicate

`gap-census-a/common.py`'s `has_hash_marker()` is `re.compile(r"<[^>]*>")` -- matches any
bracketed token. Checked directly against `ft8_lib_vendor/ft8/message.c`: `lookup_callsign()`
(`:594-614`) emits the literal string `"<...>"` on a failed hash lookup, or `add_brackets(c11)`
-- an actual resolved callsign, never empty, never containing `.` -- on success (`:549-554`,
`:610`). Grepped the tree for any other `<...>`-producing call site: **none found**; this is the
only one.

New predicate, `common_g2a.has_unresolved_hash_marker()`:

```python
_UNRESOLVED_HASH_RE = re.compile(r"<\.*>")
```

Matches `<...>` (the only string this codebase emits), and, defensively, `<>`/`<.>` in case a
different hash width ever emits a shorter placeholder -- still excludes any actual callsign.
Reproduces the Architect's hand-derived table in `2026-08-25-1735` Sec.2 exactly (verified before
building the harness): L1 6,409/71,583 = 8.9532%, L2 3,566/71,600 = 4.9804%, resolved-only
501/71,583 and 3,347/71,600.

## 2. Part A, re-run through the real harness (cycle-clustered bootstrap, not a hand count)

The Architect's Sec.2 table was point counts only. Feeding the corrected rows through the
existing `part_a.py` (unmodified -- it only ever reads the boolean `has_hash` field) gives the
same point estimate plus the pre-registered clustered CI the gate actually requires:

| | L1 (pre-G2a) | L2 (post-G2a) |
|---|---:|---:|
| unresolved decodes | 6,409 / 71,583 = 8.9532% | 3,566 / 71,600 = 4.9804% |

**H = 3.9728pp, 95% CI [3.8331pp, 4.1133pp] (cycle-clustered bootstrap, n_boot=2,000,
n_cycles=4,627).** `CI_lo` = 3.83pp, far above the 0.02pp (2pp\*) bar -- **ROW A1 fires**,
matching the withdrawal's finding and confirming it was not an artefact of hand-counting.
Determinism check under the corrected predicate: L2 run1 and run2 agree exactly (3,566 = 3,566)
-- ROW 0d's finding was never about the old predicate specifically.

*(bar is stated in the spec as an absolute proportion, 0.02 = 2pp; matches part_a.py's `bar = 0.02`.)*

## 3. Bucket B1, corrected, per leg -- L2 is the citable basis (Sec.4.1)

Descriptive population re-sizing only (a cycle-clustered bootstrap CI on the per-leg B1 **count**,
not a null-based excess -- that is `B1-COVERAGE-A`'s job once the Architect's spec lands per
Sec.4.3). `theirs_only` population size is recomputed per leg because `Population` is built from
that leg's own `ours_rows` against the fixed reference; a resolved decode's text can now exact-match
the reference and leave `theirs_only` entirely, which is why the two legs' denominators differ:

| leg | n_theirs_only | B1 (corrected) | 95% CI | B1 % of D-001 | 95% CI |
|---|---:|---:|---:|---:|---:|
| L1 (pre-G2a) | 18,617 | 985 | [959, 1,011] | 2.2684% | [2.2085%, 2.3283%] |
| **L2 (post-G2a, CITABLE)** | 18,508 | **470** | **[458, 483]** | **1.0824%** | **[1.0547%, 1.1123%]** |

🔴 **The citable B1 figure going forward is L2's: 470 decodes, 1.08pp of D-001 (95% CI
[1.05pp, 1.11pp]), cycle-clustered.** This replaces the withdrawn "~1.55pp" figure, which was
computed on the broken any-bracket predicate and is no longer to be quoted.

⚠️ **This is NOT a re-issue of `ΔB1`.** The L1-vs-L2 gap in this table (985 → 470) is a
description of each leg's own population, not a causal estimate -- it inherits the same
11-commit confound flagged in the 17:25Z ruling Sec.2 (STANDS) and remains a contrast, not a
share. `ΔB1` stays uncitable for exactly the reasons already on record; nothing here changes that
ruling. What this table *does* settle is what "B1" means and how big it is **today, on `main`**,
which is the population `B1-COVERAGE-A` needs to partition.

## 4. Per-cycle hash-table freeze polling (Sec.4.2) -- launched, not blocking this report

Per the withdrawal: *"`ft8_get_hash_table_reject_count()` is exported and monotonic, so the first
cycle it goes non-zero IS the freeze moment -- pollable per cycle in a replay, no rebuild."* New
script `qa/rr-study/g2a-remeasure-a/find_hash_table_freeze_cycle.py` reuses `decode_corpus.py`'s
own `Decoder` class verbatim, polls the reject counter after every WAV, and **stops as soon as it
turns non-zero** (plus a 20-cycle confirmation tail) rather than replaying the full ~58-minute
corpus per leg the way `decode_corpus.py`'s Part A/B runs did -- the freeze cycle index is the
entire measurement.

Launched in background against both pinned DLLs (L1 `f2f30c89.../20260033`, L2
`bc8efcf1.../20260046`), detached (`nohup ... & disown`, PID-verified per HK-023), logging to
`artefacts/2026-08-25-g2a-remeasure-a/{L1,L2}_freeze_cycle.log`, output to
`artefacts/2026-08-25-g2a-remeasure-a/{L1,L2}_freeze_cycle.json`. **Both complete, results below.**

Cycle interval on this corpus is 15s (filename timestamps), so cycle count converts to
session-elapsed time directly:

| leg | table size | freeze cycle | freeze time-into-session | remaining session frozen |
|---|---:|---:|---:|---:|
| **L1 (pre-G2a)** | 256 | **25 / 4,971** | 6.25 min | 20.6h / 20.7h (99.5%) |
| **L2 (post-G2a)** | 4,096 | **767 / 4,971** | 3.20h | 17.5h / 20.7h (84.6%) |

🔴 **G2(a)'s 16x table-size increase pushed the freeze point from cycle 25 to cycle 767 -- roughly
30.7x later in cycle count, not 16x.** Unlike `ΔB1`, this comparison is NOT confounded by the
other 10 commits in the L1→L2 delta: freeze cycle is a pure function of table capacity and the
rate of distinct new hashes, and nothing else in the delta touches hash-table sizing (same
argument the 17:25Z ruling made for the reject-count fall). **Both tables still saturate well
inside the corpus** -- the withdrawal's "63,956 rejects prove 4096 still saturates" is now dated
precisely: for the majority of *any* session on this traffic pattern, both the old and the
current table are frozen. This is the population `B1-cap` (§4.3's third bucket) draws from, and
it is the direct empirical case for why eviction (F-001 D3) remains *plausible* -- while still,
per the withdrawal, **NOT authorised**.

## 5. Summary for the queue

- Item 2 (this report): **done.** Corrected `rate_unresolved`/Part A re-confirmed with a proper
  clustered CI (ROW A1, CI floor 3.83pp); bucket B1 re-derived, **L2's 470/1.08pp is now the
  citable figure**, L1's 985/2.27pp reported for context only.
- Item 3 (`B1-COVERAGE-A`): spec still owed by the Architect (per Sec.4.3); the population it
  should partition is now the corrected 470-decode L2 B1 set above.
- Item 4 (`OSD-FA-A`): unchanged, still open, not started this session.
- Sec.4.2 (freeze-cycle polling): **done.** L1 (256-slot) freezes at cycle 25/4,971 (6.25 min into
  the session); L2 (4,096-slot) freezes at cycle 767/4,971 (3.20h in). Both tables spend the large
  majority of any session frozen (99.5% / 84.6%). Cleanly attributable to G2(a) (unconfounded,
  unlike `ΔB1`) since nothing else in the L1→L2 delta touches table sizing.
- Item 1 (Developer session, `BASE`+`WIDE`): outside QA's remit (HK-011) -- needs the Captain to
  hand this to a Developer session; not actioned here.
