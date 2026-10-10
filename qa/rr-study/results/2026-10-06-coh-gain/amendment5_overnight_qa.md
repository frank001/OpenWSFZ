# COH-GAIN Amendment 5 (QA-authored, UNRULED) — further fresh samples, run overnight

**Authority.** The Captain, in QA's window, 2026-10-06 ~20:40Z (`date -u`): *"do an overnight run as you see fit. end time is 7:00 tomorrow, local time. expand the samples as you see fit. minimal monitoring, only engage at the expected end time."* Local time is UTC+2, so the run ends **05:00Z**; the orchestrator starts no step it cannot finish by **04:45Z**. The Architect's session was unreachable when this was written, so the amendment is **QA's, dated, committed BEFORE any extraction, and awaits the Architect's ruling**; it changes **no threshold, no row and no arm**.

## What it adds
- **Samples.** Six further FRESH samples of the NHARD-REP frozen ordered list, positions `i mod 10 ∈ {1, 2, 4, 6, 8, 9}`: the only residues no outcome has touched (0 was NHARD-REP's sample, 3 the first sample, 5 the Amendment-4 extension, 7 hosted the discarded pilot rows). Each row list is frozen and pinned by LF SHA-256 in `cg_common.SAMPLE_PINS`; disjointness from every other list and from the pilot is asserted in code and tests.
- **Per sample (the Amendment-4 recipe, unchanged):** its own batch-labelled V4′ replay (bar 0.90) with its manifest committed BEFORE its extraction; the extraction with all arms (G, C1, C3, C3\*, GO, C3O); V1, V3 and V5 (first 300 rows, fresh process); V2 carried.
- **Primary (unchanged form): `NET_C3` POOLED** over the first sample and every VALID fresh sample (the Amendment-4 extension included): block 8 within each sample, then pooled; same B (10 000) and seed (20261006); **COH-GO iff `CI_lo` ≥ `BAR_G`, COH-STOP iff `CI_hi` < `BAR_G`, else COH-OPEN, `BAR_G` = 1.0 pp (HK-038: ratified by the Captain as the gain that justifies a native build; a decision value; FROZEN).**
- **Validity is per sample and outcome-independent.** A fresh sample that fails ANY of its own V1 / V3 / V4′ / V5 is EXCLUDED from pooling and NAMED; the others pool (HK-021 (ab): the rule is scoped to the sample it guards, not blanket). A first-sample failure withholds the pooled verdict as before. A sample that did not run (deadline) is excluded as "not run", never counted as a pass.
- **Secondary (U row), over the valid FRESH samples only** (the first sample produced the idea): U = G, and C3 only where G fails; a C3 CRC-valid wrong payload is a false decode, never a success; U-GO iff `CI_lo(NET_U)` ≥ 1.0, U-STOP iff `CI_hi` < 1.0, else U-OPEN. Per Amendment 4's ruling this is a REPLICATION check (the union cannot lose a row); **the fallback's false decodes are the decision** and are reported per row and per correct recovery.
- **Descriptive:** per-sample NET_C3 and NET_U, so heterogeneity between samples is visible rather than hidden by the pool.

## Supervision (HK-013 / HK-019 / HK-023)
Detached orchestrator `cg_overnight.py`, the existing generic watchdog (`onoff_replay_watchdog.py`), a 60-second heartbeat, idempotent steps (a done marker per step; the extraction itself resumes by cycle), a deadline guard, WSJT-X / jt9 / the daemon closed, teardown and an orphan check at the end. Manifests are committed by path by the orchestrator before each extraction. Nothing is pushed.

## Not done / limits
Same night, same chain: more samples tighten the interval but do not add a second band or night. Everything else in the first report's limits stands.
