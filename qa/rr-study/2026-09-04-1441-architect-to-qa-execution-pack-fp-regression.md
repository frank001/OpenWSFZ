# `FP-REGRESSION` — Architect → QA execution pack

**Architect, 2026-09-04 14:41Z** (`date -u`, HK-017). Spec:
`2026-09-04-1432-architect-to-qa-spec-fp-regression-bisect.md`. **This pack orders and instruments
that spec. It does not change a single pre-registered row.** Where this pack and the spec disagree,
**the spec wins** — report the discrepancy rather than resolving it yourself.

---

## 🛑 HOW TO READ THIS PACK — read this before anything else

**HK-030 exists because the last pack was overrun.** That pack said "QA commits and stops", and elsewhere noted that a later block
"does not wait for the push". QA read the second note as licence to keep going. It was not.

Binding rules for this pack:

1. **A HARD STOP means: commit, write the report, hand back to the Captain, and STOP THE SESSION.**
   Not "don't push". Not "carry on with the next independent block."
2. 🔴 **This pack deliberately contains NO dependency-ordering notes.** There is no statement
   anywhere in it that any block is "independent", "unblocked", or "does not wait". If you find
   yourself reasoning *"block N doesn't depend on block M, so I can continue"* — **that reasoning is
   the HK-030 failure itself.** Dependency is a fact about data. Permission is a fact about who
   said go. They are different questions and only the Captain answers the second.
3. **Blocks run in the order E0 → E1 → E2 → E3 → E4, one per session**, unless the Captain says
   otherwise in writing.
4. If a block's STOP branch fires, **that is the end of the session** — do not "just check" the
   next block to see what it would have said.

---

## E0 — Preflight (no decode, no binary)

1. **Corpus.** Verify the frozen population at `qa/rr-study/awgn-fp-replay/_work/m1m4_s5/`.
   🔴 **Open `qa/ARTEFACT_INVENTORY.md` BEFORE concluding anything is missing** (HK-018, violated
   4×). Report any gap; **do not re-render silently.**
2. **Working tree.** `git diff --stat -- src/ native/` ⇒ must be **empty**. Say so in the report.
3. **Scratch dir for extracted binaries.** Anywhere under `artefacts/` (blanket-gitignored).
   🛑 **Never copy an extracted DLL over `src/OpenWSFZ.Ft8/Native/`.** If a candidate cannot be
   tested without a rebuild, that is an **HK-011 Developer session** — stop and say so.

---

## E1 — ROW 0b, and the pre-registered binary manifest

### E1.1 The manifest — pre-registered here, verified independently by you (HK-021(p))

`git show <sha>:src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll | sha256sum`:

| # | Date | Commit | win-x64 `libft8.dll` SHA256 | Note |
|---|---|---|---|---|
| B1 | 2026-08-05 | `3bd4cd0` | `f2f30c890b253eb6b69aa1a89c26d2991ee70aa2a202c68361130344bb7d4015` | last **0/120** sweep |
| B2 | 2026-08-12 | `9500e03` | `c559a049d103c1f350f1a87b319033d5f8d1a2f91b74d9756d8d7cf03d2e6112` | `HASH_TABLE_SIZE` 256→4096 |
| B3 | 2026-08-14 | `3bc2b9d` | `fa87bd9779c4dba831b792f5bc2608f29db875d7ce8d6c535f93e094b485e6b8` | vendored rebuild, all 11 objects |
| B4 | 2026-08-14 | `af2f466` | `fe0b7d534e06fd4d1f79575739af650f78a524861cb195178a1c1c9036139cdc` | r1 sync refiner |
| B5 | 2026-08-14/15 | `aa434cb` = `8d6e1b1` | `04cedc598593e89569b7212deef66efaa413322994216108841525ca2ebc45bf` | r1b; **first 1/120** sweep |
| B6 | 2026-08-21 | `7d36038` | `1889408787a2c7ea545dbe8477691b090417a74fc81116cbf1ea52413bfbdb3a` | 1/120 sweep |
| B7 | 2026-08-22 | `7ed8b0c` | `a3d32b7839a0fd73dcc8d35bd514d60f962f3267179fd77cbd8a1ebd6ecc8d45` | Phase B / fusion normalisation |
| B8 | 2026-08-22 | `c3a9ea8` = `f5dec23` | `bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f` | neg. `time_offset` fix; **4/120** sweep |

**Window A = B1→B5 (4 adjacent pairs). Window B = B6→B8 (2 adjacent pairs). Six pairs total.**

🛑 **Recompute every SHA yourself and assert it against this table before that binary decodes
anything. Any mismatch is STOP, not a note.** A `FT8_SHIM_VERSION` label identifies nothing.

### E1.2 ROW 0b

Per spec §4: **FIRES iff** the win-x64 DLL SHA256 is **unchanged across an entire window in which
the in-chain rate moved.** On the manifest above, B1≠B5 and B6≠B8, so the expected verdict is
**does not fire** — **confirm it mechanically, do not assume it.** If your recomputed SHAs
contradict the table, the table is wrong and that is the finding.

### E1.3 🔴 An established fact you must carry into every later block

**B8 (`bc8efcf1`) served BOTH the `f5dec23` sweep (4/120) and the `22b749c` sweep (0/60).** Same
binary, consecutive sweeps, rates 3.33% and 0.00%. Fisher one-sided **p = 0.194** — i.e. at these
sample sizes **the in-chain series cannot distinguish a binary effect from sweep-to-sweep variation.**

⚠️ **This is a power statement, not a null result.** It does not show within-binary variance is zero;
it shows n=60/120 cannot resolve it. Two consequences, both binding:

- It is **why the offline paired design is the right instrument** — same WAVs through both binaries
  removes exactly this noise.
- 🛑 **No block in this pack may attribute an in-chain rate difference to a specific commit.** The
  in-chain series located the *windows*; only the paired offline replay can attribute within them.

**For the record, the headline contrast was stress-tested before this pack was written:** dropping
`f5dec23` (the largest single contributor) leaves **9/360 = 2.50% vs 2/360 = 0.556%, 4.50×,
Fisher p = 0.0317.** The regression survives leave-one-out.

### 🛑 HARD STOP 1 — after E1

Commit. Write the report. **Hand back to the Captain and stop the session.**

---

## E2 — ROW 0a, the instrument-sensitivity gate

Decode the full frozen 4,000-slot corpus through **B1** (pre-regression) and through **B8**
(post-step), paired — the same WAVs through both.

**FIRES iff** the paired difference (B8 − B1) in offline false-accept rate is **≤ 0**.

- **Does not fire** ⇒ the offline seam is responsive; ROW 1 becomes runnable **by the Captain's
  instruction, not automatically.**
- 🛑 **Fires ⇒ STOP. The bisect is VOID and must not be run.** The offline seam is blind to whatever
  moved in-chain; the arm re-scopes to an in-chain instrument, which is a **new pre-registration**.
  🛑 Do **not** respond by widening the corpus, changing the metric, or "checking one more binary."

**Report the signed difference and its paired CI. Never `|Δ|`** (HK-021(l)).

⚠️ **What ROW 0a cannot detect** (HK-022, carried from spec §4): that the offline and in-chain
effects share a *mechanism*. Same direction is necessary, not sufficient. Say so in the report.

### 🛑 HARD STOP 2 — after E2, on either branch

---

## E3 — ROW 1, the bisect

Decode the frozen corpus through **all eight** binaries B1…B8, oldest first, paired throughout.

**FIRES iff** any adjacent pair shows a paired difference in offline false-accept rate whose 95% CI
**excludes zero**. The **set** of firing adjacent pairs is the located change set.

🔴 **Three instructions that exist because of how this arm was drafted:**

1. **Test all six adjacent pairs. Do not stop at the first fire.** ROW 2b exists precisely for the
   two-step case the in-chain series predicts.
2. **Do not test B2 (`9500e03`, `HASH_TABLE_SIZE`) first.** It is the Architect's post-hoc
   hypothesis, recorded in spec §7 **so that it cannot steer the arm**. Run oldest-first.
3. **If B3 (`3bc2b9d`, the vendored whole-toolchain rebuild) is implicated**, that is a **more
   serious finding than a parameter change**, not a null one — it would bear on every binary-identity
   claim this project holds. Report it as such; do not rationalise it as "just a rebuild".

### 🛑 HARD STOP 3 — after E3

---

## E4 — ROW 2 / ROW 3 / ROW 4

Per spec §4, evaluated in order, mutually exclusive:

- **ROW 2a** exactly one adjacent pair fires · **ROW 2b** two or more ⇒ **report all of them**
- **ROW 3** ROW 0a passed but ROW 1 fires nowhere ⇒ the offline seam is the wrong instrument;
  re-scope (new pre-registration). 🛑 Do not re-read ROW 1 with a better metric.
- **ROW 4** anything else ⇒ report and stop.

### 🛑 HARD STOP 4 — after E4

---

## Reporting requirements (every block)

1. **The recomputed SHA of every binary used, next to its manifest value.**
2. `git diff --stat -- src/ native/` output, quoted, and confirmed empty.
3. Every row printed — inputs, threshold, verdict — then the first firing verdict.
4. Signed differences, never absolute values. `n` and the readout quantum wherever a rate is quoted.
5. 🔴 **Never cite `3.333%` as a baseline here.** It is post-regression (`FP-PARITY` A2.4). The
   pre-regression in-chain figure is **`2/360 = 0.556%`**.
6. **NFR-021 before every commit.** The corpus is noise-only ⇒ decoder output is hallucinated
   callsign-shaped tokens **by construction**. Import the shipped scanner's own `scan()`/`classify()`
   (HK-022); it **cannot scan an uncommitted directory** and prints a false-green "CLEAN". Use a
   placeholder infix distinct from `<RDCTnn>` / `<RDCTMnn>` / `<RDCTRnn>` and commit a redaction map.

## Standing bars this pack does not lift

- **No capture run.** Everything is offline replay of WAVs already on disk.
- **The candidate-budget family stays closed** (`s_k_min_score_pass2`, `K_MAX_CANDIDATES*`, the pass
  table). If a row implicates them, that is a finding to *report*.
- **No fix, no revert, no tuning** under this arm. It locates; a repair is a separate
  pre-registration.
- `jt9 -d 3` offline is not a valid reference decoder.
- **QA does not push, branch, open a PR, or merge** (HK-014/HK-011). `main` is 21 ahead with a real
  `src/`+`native/` diff ⇒ **HK-029's direct-push exception does not apply.**
