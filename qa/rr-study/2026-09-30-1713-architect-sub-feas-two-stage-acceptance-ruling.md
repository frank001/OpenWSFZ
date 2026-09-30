# RULING — SUB-FEAS two-stage publish, acceptance S1–S3

- **Date (UTC):** 2026-09-30 17:13Z (mechanically derived, `date -u`, HK-017)
- **Author:** Architect. **Reads:** QA's report `qa/rr-study/results/2026-09-30-sub-feas-two-stage-acceptance/report.md`
  (`qa/sub-feas`, latest commit after `990348a7`, local), against spec §5b/§5c (Amendments 2–3).
- **Build under test:** `feat/sub-feas-two-stage-publish` `247ac391`, `libft8.dll` `ee00d118…990e4c` (actual = pinned,
  unchanged from Stage A).

## Verdict: PASS on S1, S2 and S3

| Row | Bar | Result | Ruling |
|---|---|---|---|
| S1 | union(batch 1, batch 2) == Stage A single-batch output, and batch 1 == flag-OFF output of the same build; 161 cycles; fresh processes, same order | 161/161 on numeric multisets (3 842 + 692 = 4 534 decodes) | **PASS** |
| S2 median | time to batch 1 ≤ 1.05 × same-session flag-OFF, per run | 1.005 / 1.003 / 0.995 | **PASS** |
| S2 max | per cycle ≤ 1 000 ms; > 1 % excluded ⇒ not evaluable | max 720.4 ms, 0 of 905 excluded | **PASS** |
| S3 | consumer tests (a)–(f), plus (g)–(j) | each letter mapped to a named test; all ran in the unfiltered `dotnet test OpenWSFZ.slnx` on `247ac391` (1 646 / 0). Names confirmed by `--list-tests`; a supplementary `DisplayName~S3` run is reported as such, not as the result | **PASS** |

Also recorded, no bar: 0 AV / 0 contained / 0 abandons over 605 heavy cycles; whole call including batch 2, max
9 463 ms. Under the Engineer's unrelated CPU load, the residual pass maxed at 10 795 ms (quiet: 8 968 ms), still
inside the deadline. The interim managed flag-OFF comparison (`2b39cf18` vs `247ac391`, 161/161 identical) is
**not** the merge control.

S1's text-level (b) differences in 10 cycles are numerically identical (callsign-hash-table history differs by
process). Informational, accepted. HK-037: the hash-bearing `s1/*.outcomes.txt` files (12) are deleted, and the
harness is numeric-only by default (`70c01fc9`).

## Still open (unchanged)

- **S2b** (WebSocket delivery under load, report only): after the overnight run.
- **Flag-OFF control, native + managed:** merge gate, on the final combined head.
- **Linux/macOS** CI; VERSION 0.53 + docs; the FR for the flag; the speed-redesign OpenSpec change onto the branch.
- The first on-air flag-ON run (RX only) happens on the Captain's word; §7 memory check there.
- `src/`/`native/` diff of this commit: none (HK-011).
