# F-001 `SUP-B` AMENDMENT 2 — ROW 0 RESULT: ALL NINE ROWS PASS ON `S-17M`

**QA → Architect / Captain.** Written 2026-08-30 18:21Z (`date -u`, HK-017). Branch
`qa/sup-b-2026-08-30`, commits through `a6075c8`. Not pushed (HK-014).

Per execution pack Sec.C7.1 step 6: **this is a hard stop.** No push, no merge, no
`pre_merge_check.py`. Step 7 (`S-17M`'s own reading + ROW 0g, `S-80M`, `S-20M` legs, Sec.6.4
verdict) does not start until the Captain reviews this diff and this result together and rules
on the merge (HK-010) — **not run in this report.**

---

## 0. What happened since the 17:43Z code review

Picked up execution pack Sec.C7.1 from step 3 (Developer diff `47447e3` already committed and
QA-reviewed APPROVED, per `BOARD.md` 2026-08-30 17:43Z). This report covers steps 3-6.

## 1. Manifest re-pin (Sec.4 / Sec.C7.1 step 3)

`qa/rr-study/2026-08-30-1507-qa-sup-b-row0-manifest.md`, commit `1ad2f8b`. `git diff --stat`
verified empty against HEAD before this commit and again before every leg started. INST
re-pinned to shim `20260048` (win `e22524e8…`, linux `4686a4f7…`), **re-hashed mechanically this
session** (`sha256sum` against the committed working-tree binaries, not copied from
`libft8.version.txt` unchecked — both matched). `BASE` unchanged (`bc8efcf1…`/`20260046`).

⚠️ **Found and not used, flagged for the record:** a stray, gitignored `baseline_libft8.dll` at
the repo root hashes to `6f151bc9…` — **neither** the BASE nor INST pin, provenance unknown (not
tracked, no history). Not used for anything in this run; `BASE`'s leg used a freshly-extracted
`git show main:src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`, independently re-hashed and confirmed
`bc8efcf1…` before use.

## 2. Harness + evaluator extension (Sec.C3/C4 / Sec.C7.1 step 4)

Same commit `1ad2f8b`. `g3_h12_replay.py`: binds `ft8_get_h12_by_code` only when
`shim_version >= 20260048` (no bare `try/except`, per Sec.C3.2); reads the 4,096-row table ONCE
at end of run into `h12_by_code`/`h12_code_out_of_range`. `row0_evaluate_s17m.py`: adds
`row_0c_ii`/`row_0c_iii` in that strict order (Sec.C4.1 — masking preserves the sum, so 0c-iii
alone cannot see a mismasked code); widens `row_0e` to diff the full table elementwise across the
two INST replays, not just the three per-cycle scalars.

## 3. Pilot (20 cycles, `S-17M`, NOT ROW 0b) + mutation test (HK-022)

BASE (via unmodified `g2_verification_replay.py`, shim `20260046` — confirmed this session that
`g3_h12_replay.py` correctly raises `AttributeError` against BASE, since even the ORIGINAL three
`h12_*` getters don't exist below shim `20260047`, exactly as that script's own docstring already
documents) and INST ×2 (via the extended `g3_h12_replay.py`, shim `20260048`): 204 decodes each,
0 AV, 0 truncated, table sums reconciled exactly with the scalars (9/1/1), `out_of_range=0`.

🔴 **Before trusting the pilot's green result, confirmed by mutation test that the new/widened
rows actually detect what they claim (HK-022 — a green result answers whatever it was pointed
at):**
- `0c-ii` correctly VOIDs on an injected `out_of_range=1`.
- `0c-iii` correctly VOIDs on a table cell bumped without an offsetting change (sum no longer
  reconciles).
- `0e` correctly VOIDs on a single cell perturbed between the two INST runs.
- **The documented blind spot itself confirmed, not just asserted:** a sum-preserving move
  between two buckets (one cell −1, another +1, `out_of_range` untouched) leaves `0c-iii` PASSing
  — reproducing exactly the Sec.C4.1 scenario `0c-ii` exists to catch, and confirming the
  evaluation order (0c-ii before 0c-iii) is load-bearing, not decorative.

## 4. ROW 0 — full `S-17M` (1,856 cycles), strict order, nine rows

| order | row | result |
|---|---|---|
| 1 | **0a** | ✅ **PASS** — BASE sha `bc8efcf1…`/shim `20260046` OK; INST run1 AND run2 sha `e22524e8…`/shim `20260048` OK, both against the Amendment 2 manifest |
| 2 | **0b** | ✅ **PASS, both means.** Means 1 (canonicalise + mechanical `diff`): exit 0, 1,856 cycles identical. Means 2 (independent field compare): 1,856 cycles / **29,696 decode records** identical on every gated field. |
| 3 | **0c** | ✅ **PASS** — `h12Divergent ≤ h12Ambiguous ≤ h12Displaying` held at all 1,856 cycles |
| 4 | **0c-ii** 🆕 | ✅ **PASS** — `h12_code_out_of_range == 0` |
| 5 | **0c-iii** 🆕 | ✅ **PASS** — `sum(displaying)=1582`, `sum(ambiguous)=847`, `sum(divergent)=652`, all three exactly equal to the corresponding scalar finals |
| 6 | **0d-i** | ✅ **PASS** — cumulative `h12Displaying`=1,582 ≤ cumulative decodes=29,696; no per-cycle Δ exceeded that cycle's decode count |
| 7 | **0d-ii** | ✅ **PASS** — re-verified **against the NEW commit (`47447e3`) and NEW line numbers** (the block moved to `ft8_shim.c:1611-1632`, per Sec.C4 row 7's explicit instruction): sits after the dedup commit (`:1607-1609`) and after every discarding `continue` (`:1582`, `:1597`, `:1605`); the only `continue` downstream (`:1677`) is inside the inner SNR-averaging loop and cannot discard the candidate |
| 8 | **0e** 🆕widened | ✅ **PASS** — per-cycle triples identical 1,856/1,856 cycles, **and** the full `4,096×3` table plus `out_of_range` identical elementwise across both INST replays |
| 9 | **0f** | ✅ **PASS (after a fix — see §5)** — `nfr021_pre_merge_scan.py --against main`: 20 text files changed, CLEAN |

**ALL NINE ROWS PASS. Nothing was refused under HK-025 — no row required it.**

Raw counters this run (both INST replays, identical): `h12Displaying=1,582`,
`h12Ambiguous=847`, `h12Divergent=652`, `hash_table_reject_count=13,359` — all four identical to
the 15:39Z Amendment-1 run's own totals, corroborating (not substituting for — Sec.C4.3) the prior
that instrumenting at this site does not perturb decode behaviour.

## 5. ROW 0f fired once, fixed in-session, then re-ran CLEAN

First run: `🔴 NON-COMPLIANT TOKENS FOUND` — 2 occurrences, 1 distinct token (`CS-2a3646`), across
`openspec/changes/f001-sup-b-instrumented-suppression-sizing/tasks.md` and
`src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt`.

**Diagnosed without ever printing the raw token to this session's own transcript** (the same
discipline the ROW 0b comparators already follow): wrote a one-off script that prints only the
match's **fingerprint and masked context** (`m.start()`/`m.end()` replaced with `#`). Context:
`"...OpenWSFZ.###.Tests 7/7..."` — the flagged token is **`E2E`**, the End-to-End test project's
own name, matching `CALL_RE`'s shape (`E`, `2`, `E`) coincidentally. Confirmed non-callsign.

Fixed in commit `a6075c8`: added `E2E` to `nfr021_pre_merge_scan.py`'s
`KNOWN_SHAPE_FALSE_POSITIVES`, same class and citation style as the existing `S8HN` entry.
Re-ran on the re-committed tree (`git status` clean first, per Sec.C7.2): **CLEAN, 20 text files,
exit 0.**

This is a shared qa-tooling fix, not part of the pre-registered 8-file SUP-B diff (qa-tooling —
HK-011 does not apply), analogous to the harness/evaluator extensions in §2.

## 6. What this licenses, and what it does not

✅ **ROW 0b holds at full scale on the new binary too:** 29,696 decodes byte-identical, BASE vs
INST, two independently-built comparators.

✅ **The per-code table is internally consistent (0c-iii), bounded correctly (0c-ii shows no
masking occurred), sited correctly (0d-ii, re-verified against the new line numbers), and
deterministic down to every one of its 12,288 cells (0e, widened).** The instrument can be
trusted to read at cluster granularity, not just in aggregate.

📌 **`S-17M`'s raw counters and its now-complete per-code table are STILL NOT the Sec.6 reading.**
Per Sec.C6, the table falls out of this run and needs no fourth leg — but computing `N`
(participating-code count), evaluating ROW 0g, running the bootstrap, and the Sec.6.4 verdict are
all **step 7**, gated on the Captain's merge decision (Sec.C7.1). Not run in this report, exactly
as the 15:39Z report deferred the same computation for the same reason.

🛑 **Still unchanged, all standing prohibitions in force:** MEASURE-ONLY. `S_max`=40% frozen.
`SUP-A`'s exploratory S/D remain VOID. No pooling across bands. `S-17M`'s counters remain a
**diagnostic** until step 7 computes an actual interval — do not divide them into a verdict.

## 7. Next, per Sec.C7.1

**Step 6 (this report) is a hard stop.** Step 7 — `S-17M`'s own reading + ROW 0g, then `S-80M` /
`S-20M` legs, ROW 0g per band, Sec.6.4 verdict per band with `MARGINAL` evaluated first — does not
start until the Captain has reviewed this diff and this result together and ruled on the merge
(HK-010). The FR-064 blocker remains separate, on its own branch (Sec.C1), and still gates `main`
independently of this branch's own ROW 0 work.

---

## Cross-references

- Execution pack: `qa/rr-study/2026-08-30-1617-architect-to-qa-spec-f001-sup-b-amendment-2-execution-pack.md`
- Amendment 2 spec: `qa/rr-study/2026-08-30-1608-architect-to-qa-spec-f001-sup-b-amendment-2-cluster-instrumentation.md`
- Manifest (Amendment 2 re-pin): `qa/rr-study/2026-08-30-1507-qa-sup-b-row0-manifest.md`
- Prior (Amendment 1) ROW 0 result: `qa/rr-study/2026-08-30-1735-qa-to-architect-f001-sup-b-row0-result.md`
- Harness/evaluator/scanner commits: `1ad2f8b` (manifest re-pin + harness + evaluator), `a6075c8`
  (NFR-021 `E2E` false-positive fix)
- Raw legs: `artefacts/2026-08-30-sup-b-row0-amend2/{base,inst_run1,inst_run2}_*.json`,
  `pilot_*.json` (gitignored, NFR-021-bearing, never move outside `artefacts/`)
