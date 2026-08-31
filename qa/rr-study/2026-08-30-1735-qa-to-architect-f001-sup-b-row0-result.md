# F-001 `SUP-B` — ROW 0 RESULT: ALL SEVEN ROWS PASS ON `S-17M`

**QA → Architect / Captain.** Written 2026-08-30 15:37Z (`date -u`, HK-017). Branch
`qa/sup-b-2026-08-30`, commits through `9621540`. Not pushed (HK-014 discipline followed even
though QA authored this leg — the branch stays local until the Captain acts).

Per Amendment 1 Sec.A8 step 6: **this is a hard stop.** No push, no merge, no
`pre_merge_check.py`. Sec.6 reading statistics and ROW 0g are step 7, gated on the Captain's merge
decision — **not run in this report.**

---

## 0. What happened since the 15:04Z board entry

The Captain ruled (via `AskUserQuestion`) that QA should commit the already-reviewed SUP-B diff
directly (mechanical act, content unchanged from the 14:17Z cross-check's APPROVE) and that FR-064
should be fixed by a Developer session (not quarantined). Both are recorded on `BOARD.md`
2026-08-30 15:04Z. This report picks up Amendment 1 Sec.A8 from step 2 (the commit having cleared
step 1 and unblocked the manifest/harness/replay chain).

## 1. Manifest (Sec.4, Amendment 1 Sec.A8 step 2)

`qa/rr-study/2026-08-30-1507-qa-sup-b-row0-manifest.md`, commit `bb13c8b`. BASE/INST DLL SHA256
and shim versions re-hashed mechanically this session (`sha256sum`), not copied from a prior
report. `git diff --stat` verified empty at every commit boundary before the corresponding replay
started.

## 2. Harness extension (Sec.A3.2)

New file `g3_h12_replay.py` — deliberately not an edit to `g2_verification_replay.py` (Sec.A3.2's
explicit instruction). Wires the three `h12_*` getters, records the same decode-set fields as `g2`
(so the two are directly diffable for ROW 0b) plus the three cumulative counters, NFR-021-guards
its own `out_json` argument (refuses to write outside `artefacts/`). Commit `bb13c8b`.

## 3. Pilot (Sec.A8 step 4, `--n-files 100`, `S-17M`, NOT ROW 0b)

BASE and INST both: 100 cycles, 45 s wall (**0.45 s/cycle** — faster than the 0.702 s/cycle
reference the machine-cost estimate used), 1,069/1,069 decodes identical, 0 AV, 0 truncated.
Revised full-leg estimate: **~14 min/leg**, not ~22 min.

🔴 **Found and fixed during pilot validation, before it could fire at scale (HK-022):** a
deliberate one-field mutation test (to confirm the two ROW 0b comparators actually detect a real
difference, not merely pass vacuously) showed both comparators' FAIL branch printing real off-air
message text to stdout/stderr — an NFR-021 exposure. Fixed in commit `e34a665`: both comparators
now report only counts/booleans/non-message fields (`ts`, `f`, `dt`, `snr`) on failure; message
text never leaves the gitignored JSON. Windows temp files the unfixed version had briefly written
were deleted. **This did not touch any git-tracked file or committed artefact** — confirmed by
`git status` before and after (clean) — but it was printed to this session's own transcript before
the fix, and is disclosed here rather than left unmentioned.

## 4. ROW 0 — full `S-17M` (1,856 cycles), strict order

| row | check | result |
|---|---|---|
| **0a** | binary identity | ✅ **PASS** — BASE sha `bc8efcf1…`/shim 20260046 OK; INST run1 AND run2 sha `37cbb4ac…`/shim 20260047 OK, both against the Sec.4 manifest |
| **0b** | 🔴 non-perturbation (load-bearing) | ✅ **PASS, both means.** Means 1 (canonicalise + mechanical `diff`): exit 0, 1,856 cycles identical. Means 2 (independent field-by-field, imports nothing from means 1): 1,856 cycles / **29,696 decode records** compared, identical on every gated field (`ts`, `decodes[]` ordered, `av`, `truncated`). No `cand[]`/`pass[]` divergence to report. |
| **0c** | counter arithmetic | ✅ **PASS** — `h12Divergent ≤ h12Ambiguous ≤ h12Displaying` held at all 1,856 logged cycles |
| **0d-i** | denominator is displays, not attempts | ✅ **PASS** — cumulative `h12Displaying`=1,582 ≤ cumulative decodes=29,696; per-cycle Δ never exceeded that cycle's decode count |
| **0d-ii** | increment site is the emission point | ✅ **PASS** (static, source at HEAD `3b9f960`) — `ft8_shim.c:1574-1578` sits after the dedup commit (`:1566-1567`) and after every `continue` that can still discard the message (`:1540`, `:1555`, `:1563`); the only `continue` between the increment and `results[num_decoded++]` (`:1640`) is inside the inner SNR-averaging loop over `b0..b1` and cannot discard the whole candidate |
| **0e** | determinism | ✅ **PASS** — INST replayed twice (`run1`, `run2`), 1,856/1,856 cycles' `(h12Displaying, h12Ambiguous, h12Divergent)` triples identical; final cumulative totals identical too (1582/847/652 both runs) |
| **0f** | NFR-021 | ✅ **PASS** — `nfr021_pre_merge_scan.py --against main`: 10 text files changed on this branch, CLEAN, no binaries to review |

**ALL SEVEN ROWS PASS. Nothing was refused under HK-025 — no row required it.**

## 5. What this licenses, and what it does not

✅ **ROW 0b is the arm's load-bearing identity, and it holds at full scale, not just the pilot:**
29,696 decodes byte-identical across BASE and INST, by two independently-built comparators. The
instrumentation does not change what the decoder emits.

✅ **The three counters are internally consistent (0c), bounded correctly (0d-i), sited correctly
(0d-ii), and deterministic (0e).** The instrument can be trusted to read.

📌 **Diagnostic, not a gate, reported for the record:** `S-17M`'s raw counters this run —
`h12Displaying=1,582`, `h12Ambiguous=847`, `h12Divergent=652`. **These are NOT the Sec.6 reading.**
Sec.6.1 defines `S` as lookup-weighted and Sec.6.2 requires a 95% cluster bootstrap over **distinct
`n12` codes** — data this instrumentation does not currently record per-lookup (only the three
scalar cumulative counters, per spec Sec.3.1-3.3). **Producing Sec.6's clustered CI and ROW 0g's
"distinct `n12` codes ≥ 30" check will need either an extension to what gets recorded per lookup,
or a documented method for deriving cluster identity from what exists.** Flagging this now,
against Sec.A8 step 7, rather than discovering it mid-reading-leg. Not a ROW 0 defect — ROW 0 does
not require it — but it will gate step 7 the moment reading legs start.

🛑 **Still unchanged, all standing prohibitions in force:** MEASURE-ONLY (no unique-match rule
implemented, enabled, or flagged — confirmed again by ROW 0b itself). `S_max`=40% frozen. `SUP-A`'s
exploratory S/D remain VOID. No pooling across bands. Pooling/reading has not started.

## 6. Next, per Amendment 1 Sec.A8

**Step 6 (this report) is a hard stop.** Step 7 (reading legs `S-80M`, `S-20M` + ROW 0g per band)
does not start until the Captain has reviewed this diff and ROW 0's result together and made the
merge decision (HK-010 — green CI necessary, never sufficient; the FR-064 blocker from the 15:04Z
board entry is separate and still gates `main`, not this branch's own ROW 0 work).

➡️ **QA owes, once the Captain has ruled:** the Sec.6.2 clustering-data question above resolved
one way or the other, then the `S-80M`/`S-20M` reading legs and the Sec.9.3 report.

---

## Cross-references

- `qa/rr-study/2026-08-30-1432-...-amendment-1-row0-pre-merge.md` — the spec this executes.
- `qa/rr-study/2026-08-30-1507-qa-sup-b-row0-manifest.md` — the Sec.4 manifest.
- `qa/cycleframer-alignment-replay/g3_h12_replay.py`,
  `row0b_means1_canonical_diff.py`, `row0b_means2_field_compare.py`,
  `row0_evaluate_s17m.py` — the four new/extended instruments, all qa-tooling (HK-011 n/a).
- Raw legs: `artefacts/2026-08-30-sup-b-row0/{pilot,s17m}_{base,inst_run1,inst_run2}.json`
  (gitignored, NFR-021-bearing, never move outside `artefacts/`).
