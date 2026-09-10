# `FP-FLOOR-LIVE-2` Part B — results: **ROW 2 FIRES, cleanly**

QA, 2026-09-10 14:36Z (`date -u`, HK-017). Spec:
`qa/rr-study/2026-09-10-1426-architect-to-qa-fp-floor-live-2-part-b-authorised.md`
(`arch/fp-floor-operator-setting`, commit `32375fb`). Harness:
`qa/cycleframer-alignment-replay/fp_floor_live_2_part_b.py` (untracked — committing is the
Captain's/Architect's call per standing practice on this arm). Matching logic imported from
`h1_hash_token_contamination.wildcard_match`, not reimplemented, per spec §5 "Harness" note.

**Headline: `K_removed = 313/601 = 52.08%` [CP95 48.00%, 56.14%] — ROW 2 fires on both bounds, not
on a boundary.** The `≤ −24 dB` emission floor is corroborated by an independent, differently-routed
decoder on **just over half** of what it removes. `lo = 48.00%` sits nearly 10× past the `≥5%` ROW 2
bar. This is the **opposite** of the Architect's own recorded prediction (§6 of the withdrawn 1710
spec: ROW 1 at ~55% credence, `K_removed` expected in 0.5–4%).

Per Amendment 1 (v1 spec, `3afc362`): the emitted SNR is *rounded*, so this arm's predicate removes
`excess ≤ 3.0` dB, strictly more than `T`'s `excess < 2.622`. **`52.08%` is therefore an UPPER bound
on `T`'s own genuine-loss rate, not an estimate of it** — and `T`'s true rate could only be higher
still, since a stricter cut removing 52% genuine decodes cannot correspond to a looser cut removing
fewer.

---

## 1. Population (mechanically re-derived from `ALL.TXT`, not trusted from `contents.md` — HK-022)

| quantity | value | check |
|---|---|---|
| Valid span | `[2026-09-08T19:36:45Z, 2026-09-09T17:22:00Z]` | 21.754 h (last OpenWSFZ decode cycle timestamp; daemon-logs confirm cycle `17:22:00` is the final cycle, reported unhealthy 27s later at `17:22:27Z` — consistent with the kill) |
| Total decodes in span (OpenWSFZ) | **57,969** | MATCH against `contents.md`'s recorded `57,969` |
| `n` (removed, `snr ≤ −24`) | **601** | MATCH against the arm's own stopping-rule count |
| WSJT-X #1 (`A`, REF) qualifying lines in span | 91,076 | — |
| WSJT-X #2 (`B`) qualifying lines in span | **0** | "no B coverage" confirmed (§4 below) |

## 2. ROW 0 — all five checks, evaluated in full (HK-025)

| row | check | result |
|---|---|---|
| 0a | Provenance: distinct captures, not a hardlink | **PASS** — `openwsfz/ALL.TXT` (drive `D:`) and WSJT-X #1's `ALL.TXT` (drive `C:`) are on different NTFS volumes, so they cannot share an inode by construction; SHA256 prefixes also differ (`0f69b49f8526…` vs `dda9483aaee6…`) |
| 0b | Positive control, `K(s≥0) ≥ 0.90` pooled | **PASS** — `21250/21397 = 99.31%` |
| 0c | `removed ≥ 300` | **PASS** — `n = 601` |
| 0d | Wildcard matching ON, ≥1 decode matched only under wildcard | **PASS** — 1,535 such decodes |
| 0e | `REF = A` only, asserted in code; combiner constant; no B coverage | **PASS** — `B`'s qualifying-line count in the analysed span is exactly 0 |

**ROW 0 CLEAR on all five checks.** `K_removed` is legitimate to read.

## 3. The headline, in full

```
k (corroborated AND removed) = 313
n (removed)                  = 601
K_removed = 52.0799%   CP95 = [48.0009%, 56.1383%]
genuine decodes lost per operating hour = k / 21.754 h = 14.39
```

**Context (sibling (u) — a rate is not evidence without its base rate):**

| quantity | value |
|---|---|
| `K_kept` (corroboration among kept decodes, `snr > −24`) | `55294/57368 = 96.38%` |
| `K_all` (corroboration over all 57,969 decodes in span) | `55607/57969 = 95.93%` |
| ROW 0b control, `K(s≥0)` | `21250/21397 = 99.31%` |

**The other bound (§4 of the 1710 spec — the one NOT the headline, direction stated):**
`removed AND NOT corroborated = 288/601 = 47.92%` — an **upper bound on junk removed**, not a count
of junk (uncorroborated ≠ false).

## 4. "No B coverage" (spec §5 item 4)

WSJT-X #2 (SDR Uno) was stopped by the Captain at `2026-09-08T18:52:45Z`. The analysed span begins
`2026-09-08T19:36:45Z` — a 44-minute gap. Confirmed mechanically, not assumed: `B`'s `ALL.TXT` has
**zero** qualifying lines (`Rx FT8`, dial `14.074`) at or after the boundary. This is the valid,
non-weakening outcome the spec names in advance, not a gap in the work.

## 5. Full `K(s)` curve, `s = −38…+10` (the deliverable that outlives the verdict)

```
 s(dB)        n        k       K(s)
   -38        1        0      0.00%
   -37        0        0       n/a
   -36        2        1     50.00%
   -35        1        0      0.00%
   -34        1        0      0.00%
   -33        2        0      0.00%
   -32        6        1     16.67%
   -31       19        4     21.05%
   -30       18        5     27.78%
   -29       30        9     30.00%
   -28       43       14     32.56%
   -27       59       20     33.90%
   -26      102       45     44.12%
   -25      137       90     65.69%
   -24      180      124     68.89%
   -23      272      213     78.31%
   -22      399      330     82.71%
   -21      540      460     85.19%
   -20      788      685     86.93%
   -19     1026      898     87.52%
   -18     1354     1239     91.51%
   -17     1526     1369     89.71%
   -16     1654     1488     89.96%
   -15     1809     1644     90.88%
   -14     1909     1777     93.09%
   -13     2002     1863     93.06%
   -12     1910     1796     94.03%
   -11     1962     1865     95.06%
   -10     2017     1929     95.64%
    -9     1882     1816     96.49%
    -8     1932     1884     97.52%
    -7     1978     1932     97.67%
    -6     1886     1853     98.25%
    -5     1908     1873     98.17%
    -4     1884     1858     98.62%
    -3     1803     1789     99.22%
    -2     1835     1808     98.53%
    -1     1695     1675     98.82%
     0     1651     1638     99.21%
     1     1592     1575     98.93%
     2     1526     1506     98.69%
     3     1462     1451     99.25%
     4     1415     1401     99.01%
     5     1305     1303     99.85%
     6     1229     1222     99.43%
     7     1136     1122     98.77%
     8     1012     1006     99.41%
     9     1022     1015     99.32%
    10      901      896     99.45%
```

⚠️ Bins below −32 dB have `n ≤ 6` and are noise; the load-bearing part of the curve is `−31…−24`,
where `n` runs 19–180 per bin and `K(s)` rises smoothly from 21% to 69% with no gap or step at the
cut. **There is no visible discontinuity in corroboration rate at the `−24 dB` boundary itself** —
the filter cuts through the middle of a continuously-declining-but-still-substantial corroboration
curve, not at a natural break.

## 6. Reading rule (spec §2.5)

```
hi = 56.14%  vs  ROW 1 bar (hi <= 2.00%)  ->  NOT MET
lo = 48.00%  vs  ROW 2 bar (lo >= 5.00%)  ->  MET, by ~9.6x margin
```

**>>> ROW 2 <<<** — per §2.5: *"No operator control is drafted. State the loss rate per hour and
stop."* Per §2.5's own standing instruction, this is **not** softened into "with a higher threshold
it would be fine" — that would be the prohibited re-read this programme bars everywhere else.

## 7. What this does NOT do (spec §3, unchanged)

- Does **not** re-open `FP-PARITY` ROW 3 — `F − T = 5.378 dB` stays fired.
- Creates **no baseline**; `FP-REGRESSION`'s seven citation guards are untouched.
- Authorises **no `src/` work** — ROW 2 authorises drafting nothing at all, a stronger bar than
  ROW 1's "draft only."
- Does **not** test D-003 (bandlimited noise-floor misestimate) — still untested, separate question.
- Per Amendment 3: **the `19:36:45Z` boundary is now permanently frozen** — this document computes
  the first `K_removed` from this corpus, which is the trigger stated in the spec's §1.

## 8. NFR-021

Harness and this report scanned with the project's own `qa/rr-study/nfr021_pre_merge_scan.py`
`scan()` (imported, not reimplemented) — **0 flagged tokens** in both files. Only aggregate counts,
rates, and SHA256 prefixes appear anywhere in either artefact; no `message_text`, no callsign, no
raw `ALL.TXT` line is quoted.

## 9. One methodological note for the record, not a re-litigation of ROW 0

ROW 0 as pre-registered does not include a permutation-based null check on the corroboration rate
itself (unlike H1a, which built one for a different exercise) — ROW 0b's positive control and 0d's
wildcard-activity check were judged sufficient preconditions by the Architect, and QA is not
re-opening that design here (HK-025 is for refusing a row, not adding one after seeing the number).
Flagging only as context for whoever reads this next: at a typical ~17 WSJT-X candidates/cycle and a
±3 Hz window over a ~2,800 Hz passband, the naive per-cycle collision odds are low (~4%), and this is
in the same neighbourhood as H1a's own measured `V_null` bound (required `≤ 0.10`) on a comparable
population — offered as a plausibility check on the magnitude, not as a substitute for a control this
arm was not specced to run.

---

*Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>*
*Claude-Session: https://claude.ai/code/session_01NseChs8GHWxH7dJ8L9pwC2*
