# Architect → QA — execution pack, 2026-09-04 13:22Z

**Occasioned by:** the Developer session that landed `ac6150d` (`F-001` L3 export, shim
`20260049`→`20260050`) and the PO's S1–S8 sweep `1241679`, both of which post-dated the board's own
last write.

**Binding documents, all already committed — read them, do not re-derive them (HK-018):**

| Document | What it carries |
|---|---|
| `2026-09-02-1906-…-spec-awgn-fp-offline-replay.md` **Amendment 3** (`cdf3bf1`, `ece7790`) | A3.0.1 the CI incompatibility · A3.1 the pin ruling · A3.2 ROW 0r · A3.3 it refires |
| `2026-09-03-1616-…-spec-fp-parity-and-inchain-floor.md` **Amendment 1** (`cdf3bf1`) | A1.1 frozen S1b population · A1.2 forced upper bound · A1.3 the knife edge · A1.4 prediction retracted |
| `2026-09-03-1616-…-spec-fp-parity-and-inchain-floor.md` **§5** | the arm's own declared order — **P4 below clarifies it, and does not reorder it** |

**Both PO rulings behind A3.1 and A3.2 were taken 2026-09-04 on the Architect's recommendation.**
This pack is the execution order for them plus the rows they unblock. **Nothing here re-opens a
closed gate or re-drafts a pre-registered threshold.**

---

## 0. Hard bars, before anything

- 🛑 **No `src/` or `native/` change is licensed anywhere in this pack.** Every item is `tests/`,
  CI-config, or analysis. **Run `git diff --stat -- src/ native/` before each commit and state the
  result in the report** — not "verified", the actual output.
- 🛑 **`PinnedShaWinX64` is NOT re-pinned.** `ce02c7ba…153e` stays the `20260049` identity of every
  already-landed row. Changing it silently reattributes M1–M4 / ROW 0q / ROW 0m to a binary they
  never ran on.
- 🛑 **The "additive export, never called in the decode path" argument may not be substituted for
  ROW 0r** anywhere, in any report, at any priority.
- 🛑 **HK-025 stands.** QA may refuse any row here on HK-021(k) grounds without the Architect's
  agreement: classify (validity vs precision), evaluate both branches, and if the same row fires
  either way it is diagnostic ⇒ refuse it and say why.
- 🔴 **Step 0, before touching anything else:** read `qa/ARTEFACT_INVENTORY.md` (standing rule,
  violated 4×) and confirm on-disk presence of `_work/m1m4_s5/`, `_work/m3_s1/`, and the five
  frozen S1b sweeps. **Report what is missing before rendering or capturing anything.**
  `python qa/artefact_inventory.py --check` fails if the inventory is stale — run it.

---

## 1. The order, and why it is this order

```
P1  A3.1 filter ─────────────► HARD STOP ─► Captain pushes (PR + CI)
     (blocks the push)              │
                                    │  P2 and P4 do not wait for the push
     ┌──────────────────────────────┴───────────────────────┐
     │                                                      │
P2  ROW 0r  ──► P3  ROW 0o, 0p, then 0n ──┐        P4a  ROW 1  (no binary,
     (binary carry-forward)   (need a binary)  │              no dependency)
                                              └──► P4b  ROW 2 / ROW 3
```

**The one dependency that is easy to get wrong:** ROW 1 needs **no binary at all** — it reconstructs
`excess` from integer SNRs already sitting in five sweeps' `owsfz-all.txt`. It therefore does **not**
wait on ROW 0r or on the push. But **ROW 2/ROW 3 do wait on ROW 0n/0o**, because `T = C + 1.0` and
`C` is measured *offline*; §3's two repairs are what make an offline absolute quantity
production-valid. ⇒ **Compute ROW 1 early, hold ROW 2/3 until 0n/0o close.** This is a
**clarification of FP-PARITY §5 steps 4–5, not a reordering of them** — the sequence is unchanged.

---

## P1 — A3.1: make the unpushed range pushable. **Do this first, it blocks everything.**

### Why it is P1

`AwgnFpReplayTests.cs` was added in `84d69e9`, **inside the never-pushed range ⇒ CI has never run
it once**, and it fails there for **two independent** reasons (A3.0.1): the `20260050` pin mismatch,
and — the one nobody had noticed — every corpus-dependent fact **asserts** its corpus exists rather
than skipping (`AwgnFpReplayTests.cs:459`) against `qa/rr-study/awgn-fp-replay/_work/`, which is
`.gitignore:222` with **zero tracked files**. A runner can never hold it. CI runs `dotnet test`
**unfiltered** (`ci.yml:325`, gate G1) on all three matrix legs.

⇒ **This class would have red-lined G1 on the next push with or without a shim bump.** P1 is the
only thing that makes the range pushable.

### The edits

1. **`.github/workflows/ci.yml`, the `Test (Release)` step (line ~325)** — add the category
   exclusion to the existing invocation:
   ```
   dotnet test -c Release --no-build
     --filter "Category!=AwgnFpReplay"
     --logger trx
     --collect:"XPlat Code Coverage"
     --results-directory TestResults/
   ```
   Add a comment above it, in the style of the existing G1/G6 block, saying **why**: the class is a
   local measurement harness bound to an untracked corpus and a pinned binary, it is not a
   repository invariant, and it is run explicitly by the arm.
2. **`TESTING_STRATEGY.md`** — record the convention in one short subsection: `Category=AwgnFpReplay`
   is **measurement-arm-only**, excluded from the default and CI suites, run explicitly by the arm
   with its own binary pin. State that any future measurement-arm test class does the same rather
   than landing in the default suite.
3. **Nothing else.** Do not edit `AwgnFpReplayTests.cs`.

### Mechanical verification — all four, all reported

| # | Check | Threshold |
|---|---|---|
| P1.1 | `dotnet test -c Release --filter "Category!=AwgnFpReplay"` | **0 failures** |
| P1.2 | Executed-test count **with** the filter vs **without** it | delta **exactly 9** |
| P1.3 | `grep -rn 'Category", *"AwgnFpReplay"' --include=*.cs tests/` | **exactly 1 file**, `AwgnFpReplayTests.cs:47` |
| P1.4 | `git diff --stat -- src/ native/` | **empty**, output pasted into the report |

🔴 **P1.2 and P1.3 exist because of HK-022's drafting question — what error could this change NOT
detect?** A filter can silently over-exclude. The delta is 9 because the class holds exactly 9
`[Fact]`s (counted 2026-09-04); if the delta is not 9, or a second file carries the trait, **STOP**
— the filter is excluding something it was not authorised to exclude.

### 🔴 The mitigation A3.1 makes mandatory, and it is not optional

**A filtered-out suite is silent, not green.** After P1, `main` being green says nothing about
whether the arm ever ran. ⇒ **From now on, every `AWGN-FP` / `FP-PARITY` result report must quote
(a) the exact `--filter` command line used, and (b) ROW 0a's own printed `actual` / `pinned` SHA
pair from that run's stdout. A report carrying neither is not a result and may not be cited.**
Put this sentence in the report template, not only in this pack.

### 🛑 HARD STOP at the end of P1

**QA commits and stops.** QA does **not** push, branch, open the PR, or merge.

Hand back to the Captain with: the P1.1–P1.4 outputs, and the statement that `main`'s unpushed range
carries a `src/`+`native/` diff (7 files, +141/−3 from `ac6150d`) ⇒ **HK-029's direct-push exception
does not apply** ⇒ this needs the Captain's diff review and a PR, not a direct push to `main`
(HK-010, HK-011, HK-014).

✅ **Two things already checked and cleared — do not re-flag either as a defect, and do not spend
time on them:** ROW 0a is **not** Windows-only (`OpenWSFZ.Ft8.csproj:23-25` copies all three natives
to the output directory on every platform, so its file hash is platform-independent); and the stale
`osx-arm64` dylib does **not** block, because CI's *"Check committed macOS dylib is current"* step is
`continue-on-error: true` (`ci.yml:74`) and the `macos-latest` leg rebuilds it.

---

## P2 — ROW 0r: does the arm's landed evidence survive the shim bump?

Full pre-registration is **AWGN-FP A3.2**. Restated here only as the operational checklist.

1. **Obtain the `20260049` binary as a real artefact, never a rebuild:**
   ```
   git show 3b52608:src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll > <work>/libft8-20260049.dll
   ```
2. **Assert its SHA256 equals `PinnedShaWinX64` before using it.** 🛑 **Mismatch ⇒ STOP.** You do
   not hold the pinned binary and no carry-forward claim of any kind may be made.
3. **Population:** every M1 S5 slot under `_work/m1m4_s5/`. No sampling, no truncation.
   ⚠️ Do not reach for any population helper taking a `limit=` — `compute_matched_hit_control`
   **truncates in file order**, it does not sample (off ≈3.8× in past use).
4. **Method:** decode every slot twice, once per binary, same process configuration and same decode
   params, and diff the **decode set per slot** — message text, frequency, SNR, DT. **Not** per-slot
   counts, **not** the aggregate event total.
5. **FIRES iff any slot's decode set differs.**
   - **Does not fire** ⇒ M1–M4, ROW 0q and ROW 0m **carry forward to `20260050` as DISCLOSED
     carry-forwards**. Report both SHAs, the slot count, and "decode-identical"; every future
     citation of those rows carries the disclosure. **Landed, not silently — exactly as `S5-LEVEL`
     Option 2 landed.**
   - **Fires** ⇒ those rows are **void on `20260050`**. Report which slots differ and how many, then
     **re-run them on `20260050` before P3 proceeds**. 🛑 Do **not** investigate *why* they differ —
     that is a new pre-registration, not a patch to this one.
   - The two branches are **exact complements**; exactly one fires.
6. 🔴 **Scope, from A3.2's own HK-022 note:** the M1 corpus is **noise-only**, so ROW 0r cannot see a
   difference that appears only on genuine signals. **The carry-forward is scoped to the
   false-accept rows. ROW 0d / M3's genuine population is NOT carried by this row.** If P3 or P4
   needs M3, **add `_work/m3_s1/` to ROW 0r's population and say that you did.**

---

## P3 — ROW 0o, ROW 0p, then ROW 0n

Unchanged from FP-PARITY §4 and §5 step 4. Two notes only:

- **These need a binary ⇒ they run after P2**, on whichever binary ROW 0r leaves valid. State which
  one, with its SHA, in the report.
- **ROW 0n is the paired re-decode** — supervised per HK-013/HK-023 if it runs long. A
  `Monitor`-owned process dies at session end; use `nohup … & disown` (PID-verified) plus a
  disposable `tail -f` Monitor for notification only.
- 🛑 §6's bar holds: **`NormalisePcm` parity is matching production, not scaling input.** It may not
  be varied as a lever. Input scaling stays closed.

---

## P4a — ROW 1. **No binary. No dependency. Can start immediately, in parallel with P1.**

### The population is frozen (A1.1) — five sweeps, verified on disk 2026-09-04

`2026-08-27-22b749c` · `2026-08-29-872ba65` · **`2026-08-30-2e60949`** · `2026-09-02-3b52608` ·
`2026-09-03-35378b9` — 12 S1b truth rows each ⇒ **60 slots**, all with `owsfz-all.txt` + `truth.csv`
present, all post-`c3a9ea8` (checked, not assumed).

⚠️ **`2e60949` is the `2026-08-30` directory.** `2026-08-31-2e60949` is an S7-only rerun sharing the
short SHA and holds **no** S1b data — the identical trap ROW 0m already hit.
🛑 **No sweep may be added to or removed from this list after ROW 1 is read.** A sweep run later is a
**new** pre-registration.

### Method

Per §4 ROW 1, corrected by ROW 0q's settled rule (**round-half-away-from-zero**, `ft8_shim.c:1732`,
so the ±0.5 dB is symmetric and **not** one-sided). Take truth-matching OpenWSFZ decodes on the S1b
population, reconstruct `excess = Snr + 26.5` (§2.2, quantum 1 dB), apply ROW 0q's correction in the
**conservative** direction (whichever makes `F` smaller), and report `F`, p01, p05, `n`, the weakest
injected rung producing any truth-matching decode, and the decode rate at that rung.

🔴 **Use `harness/common.py`'s parser against raw `owsfz-all.txt` + `truth.csv`. Never `matcher.py`**
— HK-026, and its FP column is still unscoped.

### A1.2 is known in advance and is not negotiable

2026-09-03's S1b, OpenWSFZ: `0/3 @ −24` · **`0/3 @ −21`** · `3/3 @ −18` · `3/3 @ −15`.
⇒ bottom rung producing truth-matching decodes is **−18 dB at 100%** ⇒ ROW 1's own >50% rule
**forces `F` to be reported as an UPPER BOUND on the true floor**, never as the floor. WSJT-X took
**2/3** at −21, so a genuine population demonstrably exists **≥3 dB below anything this ladder can
see** — HK-026 in its plainest form.

🛑 **`F` is never quoted without `n`, the 1 dB quantum, and the truncation statement.**

---

## P4b — ROW 2 / ROW 3. **Hold until P3 closes.**

`T = C + 1.0`. As of 2026-09-04, `C = +1.622 dB` and **the 2026-09-03 sweep does not move it**: its
two in-chain false accepts (−26 dB @ 341 Hz, −27 dB @ 2878 Hz) reconstruct to `excess` **+0.5** and
**−0.5 dB**, so they raise `n` on the in-chain false-accept population and leave the ceiling alone
⇒ **`T = 2.622 dB`**. ROW 2 fires iff **`F ≥ 8.622 dB`**.

### 🔴 A1.3 — this will be decided by one decode's readout quantum, and the report must show it

| Weakest truth-matching reported SNR | `excess` | after −0.5 | Verdict |
|---|---|---|---|
| −18 dB | 8.5 | **8.0** | **ROW 3** (margin 5.38) |
| −17 dB | 9.5 | **9.0** | **ROW 2** (margin 6.38) |

S1 bias is **+0.82 dB**, so a −17 reading on a −18 dB injection is expected, not exotic.

🛑 **The gate stands exactly as written and is not re-drafted now that its landing zone is visible** —
that would be reading a closed gate with a better metric, which is barred. The 6.0 dB is a declared
policy margin and the PO has seen it.

🔴 **But a verdict resting on n≈1 must show that it does.** In the same section as the verdict,
report:

1. the **lowest 5** reconstructed `excess` values, sorted, each with its **injected rung**, its
   **reported SNR**, and its **sweep ID**;
2. **how many distinct decodes sit within ±1 dB of the 8.622 dB fire line**;
3. `n`, the quantum, and the A1.2 truncation statement.

**If ROW 3 fires, that is the arm working, not the route failing** — PARKED, not closed, and
**not** softened into "needs more data", and **not** re-run with a smaller margin.

---

## 5. Housekeeping — small, do not let it grow

1. **`qa/rr-study/run_s1s8_2026-09-03.log`** is untracked from the PO's sweep. Architect scanned it
   2026-09-04: **clean**, no callsign-shaped tokens, only timestamp fragments. Per HK-016 it belongs
   under a dated `artefacts/` directory with the run's other artefacts, not in `qa/`. QA's call
   where exactly; **do not commit it to `qa/` by default.**
2. **Still unclaimed, unchanged in priority, do not start without a fresh decision:**
   `nfr021_pre_merge_scan.py` directory mode; `matcher.py` FP-window scoping (this sweep needed the
   manual `cycle_utc`↔`truth.csv` join **again**, and found S8-window rows inside `S5_matched.csv`
   **again**); `resume_study.py`'s R&R-009 part-restriction gap.
3. **The shim-renumber dev-task** (`20260051`/`20260052`) is unchanged and is the **Captain's** to
   open as a Developer session. `20260050` is L3's and is **not** a renumber target. When it runs,
   **A3.3 applies: ROW 0r re-runs for that bump too.**

---

## 6. What the report must carry (HK-001, plus this pack's own additions)

- Per priority: what ran, on which binary **with its SHA**, and the row's verdict in its own
  pre-registered words.
- **The `--filter` command line and ROW 0a's printed actual/pinned SHA pair** for every arm run
  (A3.1's mandatory mitigation).
- `git diff --stat -- src/ native/` **output**, per commit.
- NFR-021: any new decode CSV redacted **before** the report is written, guarded against the injected
  truth text first, byte-level rewrite (UTF-8 BOM + CRLF), re-scanned to 0/0. 🔴 The shipped scanner
  **cannot scan an uncommitted directory** — import its `scan()`/`classify()` over a directory walk
  (HK-022 false green).
- Headline carries FP-PARITY §0's two bars: **this arm proposes no capture run and builds no filter.**
- Anything QA refuses under HK-025, with the classification and both branches shown.

## 7. Standing disclosure

🛑 The Architect remains **de-blinded** on the excess distributions (AWGN-FP A1.0). Prediction
scoring stays **suspended** for ROW 2 / ROW 3. Recorded in FP-PARITY A1.4: the §7 prediction's
*reasoning* is already falsified — it expected truth-matching decodes near −24 dB and there are
none at −24 or −21, so if ROW 3 fires it fires because the ladder truncates **high**, not low.
