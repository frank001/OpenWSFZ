# F-001 `SUP-B` — AMENDMENT 1: ROW 0 RUNS PRE-MERGE, ROW 0d IS REPLACED, AND THE INSTRUMENT ALREADY EXISTS

**Architect → QA.** Amends
`qa/rr-study/2026-08-30-1149-architect-to-qa-spec-f001-sup-b-instrumented-suppression-sizing.md`
(hereafter "the spec"). Branch `qa/sup-b-2026-08-30`. Committed locally, **not pushed** (HK-014).

**Author:** Architect · **Written:** 2026-08-30 14:32Z (mechanically derived, HK-017)

---

## Sec.A0 — What this amendment changes, and what it does not

| # | spec section | change |
|---|---|---|
| **A1** | Sec.9.2 steps 3/4 | 🔴 **ROW 0a–0e run BEFORE the merge decision, not after.** My ordering error. |
| **A2** | Sec.4 | 🔴 **BLOCKER: the implementation is UNCOMMITTED.** Sec.4's "`git diff --stat` empty" cannot be satisfied today. |
| **A3** | Sec.3.3 / Sec.5 | ✅ **The replay instrument already exists** — named, with its one required extension and three traps. No new plumbing. |
| **A4** | Sec.2.1 | 🔴 **Sec.2.1's replay rationale is FACTUALLY WRONG for `S-20M`** (three process starts). Corrected, with a corrected window. |
| **A5** | Sec.5 ROW 0b | ✅ Predicate made executable — the field scope, and what "two independent means" actually buys. |
| **A6** | Sec.5 ROW 0d | 🔴 **ROW 0d AS WRITTEN IS CIRCULAR AND QA COULD REFUSE IT UNDER HK-025. REPLACED** by two mechanical rows plus a diagnostic. My error. |
| **A7** | Sec.2.1 | ✅ **Preconditions DISCHARGED with numbers** — inventory current, all three corpora have full WAV coverage. |

🛑 **UNCHANGED AND NOT REOPENED BY THIS AMENDMENT:** `S_max` = **40%**, frozen, immovable in either
direction (spec Sec.2.2). `SUP-A`'s exploratory `S`/`D` values remain **VOID and uncitable**.
**MEASURE-ONLY** — the unique-match rule is not implemented, enabled, or flagged (spec Sec.3.4).
**Pooling across bands remains FORBIDDEN.** The Sec.6 reading, the Sec.6.4 verdict table, the Sec.7
predictions and the Sec.7.1 power disclosure are untouched. **This amendment changes ORDER,
PLUMBING and TWO PREDICATES. It changes no bar and no number.**

---

## Sec.A1 — ROW 0a–0e run pre-merge, and the ordering error is mine

Spec Sec.9.2 has the Captain merging at step 3 and QA running ROW 0 at step 4. **That is the wrong
way round and it is my spec, so it is my error.**

🔴 **ROW 0b is not a post-merge verification. It is this diff's acceptance test.** It asks whether
the instrument changed the thing it measures. A build that fails it must never reach `main` — and
backing native binaries out of `main` is expensive in a way that backing them out of an unmerged
branch is not.

Nothing about ROW 0a–0e requires the merge. Verified this session, not assumed:

| leg | source | SHA256 | reachable now? |
|---|---|---|---|
| `BASE` | `git show main:src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` | `bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f` | ✅ **matches spec Sec.4's `bc8efcf1…` pin** |
| `INST` | working tree, branch `qa/sup-b-2026-08-30` | `37cbb4acb93c0006d65c40defb0da21366160d3a6b07e283660eed358bd6ac26` | ✅ matches the board's 14:17Z entry |

Both legs' binaries are identifiable and extractable today. **Sec.9.2 is amended to:**

1. **QA** proposes the `src/`/`native/` diff and STOPS (HK-011). — *done*
2. **Developer** applies, builds, tests. **never** `pre_merge_check.py` (HK-006). — *done, but see Sec.A2*
3. 🔴 **Developer commits the diff on the branch** (Sec.A2 blocker).
4. 🔴 **QA pins the manifest, verifies `git diff --stat` empty, and runs ROW 0a–0e.**
5. **Captain** reviews the diff **with ROW 0's result in hand**, and decides the merge (HK-010 — green
   CI necessary, never sufficient).
6. **QA** replays the reading legs and reports (spec Sec.9.3).
7. **Architect** commits locally and stops (HK-014).

⚠️ **This does not license QA to merge, push, or run `pre_merge_check.py`.** Step 5 is still the
Captain's alone. The only thing that moved is *when QA measures*.

---

## Sec.A2 — 🔴 BLOCKER: the implementation is uncommitted

Verified this session:

- `8faa141` ("Developer handoff") contains **one file** — the 593-line dev-task. **No code.**
- `git diff --stat HEAD` = **23 files changed, 514 insertions(+), 6 deletions(-)**, unstaged.
- One further file staged: `tests/OpenWSFZ.Ft8.Tests/H12InstrumentationLoggingTests.cs` (+154).

**Three consequences, all load-bearing:**

1. 🛑 **Spec Sec.4 requires `git diff --stat` to be EMPTY when the first replay starts.** It is
   currently 23 files. **ROW 0 cannot be run to spec until the Developer commits.** This is the
   pre-registration hygiene `NBR-A` Amendment 2 used, and it worked; it is not ceremony.
2. **There is no diff object for the Captain to review** at step 5, and no commit the manifest can
   name.
3. ⚠️ **Both hand-built binaries exist only in the working tree.** Neither is reproducible
   bit-for-bit from any commit. A stray `git checkout` or `git stash` loses `37cbb4ac…` and
   `4970ec5f…`, and a rebuild will not necessarily reproduce them.

➡️ **QA owes nothing here — this is the Developer's action, and QA should say so and wait rather
than commit `src/` itself (HK-011).** QA's ROW 0 begins at the commit.

---

## Sec.A3 — The instrument exists. Do not build a second one.

**HK-004/HK-018.** I looked before specifying, and the harness this arm needs was extracted, reviewed
and hardened on 2026-08-12.

### A3.1 The harness

**`qa/cycleframer-alignment-replay/g2_verification_replay.py`** — drives a **named** `libft8.dll`
in-process via `ctypes` over a WAV corpus:

```
python qa/cycleframer-alignment-replay/g2_verification_replay.py \
    <dll_path> <label> <out_json> \
    --wav-dir <dir> --window-lo <ts> --window-hi <ts> \
    [--start-cycle N] [--n-files N] [--allow-short]
```

Why it is the right instrument, and not merely an available one:

- ✅ **It takes the DLL as an argument and records `dll_sha256` + `shim_version` into its output
  JSON.** ROW 0a becomes a field comparison against the Sec.4 manifest, not a promise.
- ✅ **`--start-cycle`/`--n-files` are a genuine SLICE**, not a prefix (its B4 fix) — the corrected
  `S-20M` window in Sec.A4 is expressible.
- ✅ **`--allow-short` fails CLOSED by default** (its C4 fix): a corpus shorter than asked for
  aborts rather than silently producing a narrower leg.
- ✅ **Per cycle it already records** `ts`, `av`, `truncated`, `wall_s`, `decodes[{f, dt, snr, m}]`,
  `cand[]`, `pass[]`, written atomically (tmp + `os.replace`).

✅ **AND — the decisive fact — no daemon and no capture are needed.** Verified in the diff: the three
counters accumulate **in C**, at `ft8_shim.c:1574-1578`, immediately after the cross-pass dedup slot
is committed at `:1566-1567` and after the last `continue` that can still discard the message
(`:1555`, `:1563`). A headless `ctypes` replay therefore sees them. The C# delta is a version
constant, three `DllImport` declarations and one log line — **none of which can alter a decode.**

### A3.2 The one extension QA must make

`build_decoder()` wires `ft8_get_last_candidate_counts`, `ft8_get_hash_table_reject_count` and
`ft8_get_last_pass_counts`. **It does not know about the three new getters.** QA adds:

| export | restype |
|---|---|
| `ft8_get_h12_displaying_count` | `c_int` |
| `ft8_get_h12_ambiguous_count` | `c_int` |
| `ft8_get_h12_divergent_count` | `c_int` |

and records all three **per cycle, after `dec.decode(pcm)`**, into the per-file record. They are
process-lifetime cumulative (spec Sec.3.3), so the per-cycle **Δ** is derived downstream — **record
the cumulative value, never the delta**, so a dropped cycle is visible as a jump rather than lost.

✅ **This is qa-tooling, so HK-011 does not apply** — the same basis on which this file was extracted
in the first place, stated in its own extraction notice. **QA may do this directly.** ⚠️ Do it as a
**new script or a flagged addition**, not an edit that changes the behaviour of the existing G2(b)
call path — that pre-registration is not ours to perturb.

### A3.3 🔴 NFR-021 — the output JSON carries message text

**`"m": r["message"]` — every decode's full text, including real off-air callsigns.** The harness's
own docstring says callers **MUST** keep the output outside the repo.

🛑 **`out_json` goes under `artefacts/` (blanket-gitignored) — NEVER under `qa/`.** This class has now
fired **three** times: the `*_matched.csv` contamination, the `NBR-A` report that named three
callsigns *inside the sentence asserting no exposure*, and it is the standing ROW 0f. ⚠️ **The
gitignore is not the whole surface — scan the PROSE of anything derived from these files too.**

➡️ **Ship the scan as CODE (HK-021(r)), not as a remembered grep.** The `NBR-A` pre-merge TODO
already asks QA for a durable scanner; **if it exists by the time this runs, use it here and say so.**

### A3.4 Three traps inside `p23_common.py`

| # | trap | instruction |
|---|---|---|
| 1 | 🔴 `p23_common.DLL_SHA256 = 39aa1031…` is **neither `BASE` nor `INST`** — standing memory flags it as an unmerged rc4-decode-depth three-pass build | `g2_verification_replay` bypasses it (`verify=False`) **deliberately**. ROW 0a asserts against **Sec.4's manifest only**. Never re-enable that pin, never quote it. |
| 2 | ⚠️ `WAV_DIR` defaults to the 08-08 20m corpus | **Always pass `--wav-dir` explicitly.** A forgotten flag silently replays the wrong band. |
| 3 | ⚠️ `P.normalise_rms(..., P.PROD_TARGET_RMS)`, `PROD_TARGET_RMS = 0.20` (`Ft8Decoder.cs:52`) | **Input scaling is a STANDING PROHIBITION.** This is production-matched and applied **identically to both legs**, so it cannot manufacture or mask a ROW 0b difference. 🛑 **It may not be varied, tuned, or made a variable of this arm.** |

✅ **Checked and now discharged (HK-022):** standing memory records `p23_common.py`'s `load_ref()`
sort fix as **UNCOMMITTED**. It is committed and present (`ref = {k: a[k] for k in sorted(...)}`), and
`p23_common.py` is clean in `git status`. ⚠️ The underlying hazard stands for any **new** code:
`set(a) & set(b)` over string keys iterates per-process-randomly. **Sort at construction in every
comparison this arm writes.**

---

## Sec.A4 — 🔴 Sec.2.1's replay rationale is wrong for `S-20M`

Spec Sec.2.1 claims replay "reproduces the same table evolution the live session had
(`g_session_hash_table` is process-static and never re-initialised)". **That claim holds only if the
live session was ONE process.** Checked on disk:

| corpus | `openswfz-*.log` files | process starts |
|---|---|---|
| `S-17M` | `openswfz-20260808T115445Z.log` | **1** ✅ |
| `S-80M` | `openswfz-20260809T015438Z.log` | **1** ✅ |
| `S-20M` | `…T000842Z`, `…T001357Z`, `…T001605Z` | 🔴 **3** |

**The live `S-20M` table was reset twice.** A single-process replay of all 2,745 cycles builds a
table that never resets — **more residents than the session ever held, which biases `S` UP.**

✅ **All three restarts are in the first ~16 minutes**; the load-bearing process starts at
**`260808_001605`** and runs to `260808_113745`. This is also the log `SUP-A` itself used (2,728
cycles). **Corrected `S-20M` window:**

| corpus | `--wav-dir` | `--window-lo` | `--window-hi` |
|---|---|---|---|
| `S-17M` | `artefacts/20260808_live_run_1154-8080-17m/owsfz/wav` | `260808_115445` | `260808_193830` |
| `S-80M` | `artefacts/20260809_live_run_0155-8080-80m/owsfz/wav` | `260809_015445` | `260809_101100` |
| `S-20M` | `artefacts/20260808_live_run_0016-8080/owsfz/wav` | 🔴 **`260808_001605`** | 🔴 **`260808_081605`** (= lo + 8 h, the 1–8 h prefix) |

Use the **`owsfz`** leg's WAVs, not `wsjt-x`: the counters measure OpenWSFZ's own table under its own
decodes, and `owsfz/ALL.TXT` is how `SUP-A` defined these corpora.

📌 **I am NOT re-cutting `S-17M` (7.73 h) or `S-80M` (8.27 h).** Both sit at or inside the 1–8 h band
and their spans are `SUP-A`'s. **`S-80M`'s 0.27 h overrun is disclosed in the report, not trimmed** —
trimming a corpus after an arm has begun is the shape of a prohibited re-read, even when the motive
is tidiness. `S-20M`'s change is a **correctness fix to a wrong process boundary**, not a re-cut.

⚠️ **Corrected rationale, which QA should quote instead of Sec.2.1's:** the replay is continuous
**by design, because continuous 1–8 h operation is the product scenario the PO asked about** — not
because it reproduces the capture campaign. A capture-campaign restart is not a product event.
⚠️ **Consequence, stated so nobody trips on it later:** the h12 counters therefore cannot be
cross-checked against a live log's own per-cycle counters for `S-20M`. **That is not a gate.**

---

## Sec.A5 — ROW 0b as an executable predicate (HK-021(r))

ROW 0b's consequence is unchanged: **VOID THE ARM.** What follows is only how it is decided.

**Scope the comparison to the emitted decode set. Explicitly:**

| field | in the diff? | why |
|---|---|---|
| `ts` | ✅ | the cycle set must match exactly |
| `decodes[]` — **ordered** list of `(f, dt, snr, m)` | ✅ | this is the emitted set; the shim's iteration order is unchanged, so **ordered** comparison is available and strictly stronger |
| `av` | ✅ | a contained native AV on one leg only is a real perturbation |
| `truncated` | ✅ | a leg hitting `MAX_RESULTS = 200` on one side only is a real difference |
| `wall_s` | 🛑 **NO** | timing jitter; including it fails ROW 0b trivially and tells you nothing |
| `cand[]`, `pass[]` | ⚠️ **report, do not gate** | a genuine multiplicity walk should not move these; **if they move while `decodes[]` does not, report it — do not silently pass** |
| `label`, `dll_path`, `dll_sha256`, `shim_version` | 🛑 **NO** | differ between legs **by construction** |

**"Two independent means" — what it actually buys, and therefore what it must be.** Ask HK-022's
question: *what error could this row NOT detect?* **A buggy canonicaliser that normalises the
difference away.** Running the same canonicaliser twice detects nothing. Therefore:

- **Means 1:** canonicalise each leg to one line per decode (sorted deterministically at
  construction), `diff` the two files, **require exit 0**.
- **Means 2:** 🔴 **must NOT import or reuse means 1's canonicaliser.** Load both JSONs
  independently and compare field-by-field in memory, reporting counts compared. A shared helper
  between the two makes ROW 0b decorative.

⚠️ **A bounded pilot is encouraged and is NOT the gate.** Run `--n-files 100` on `S-17M` first to
catch a gross perturbation in minutes rather than hours, and to read `wall_s` for a real cost
estimate before committing to the full legs. 🛑 **A passing pilot may never be reported as ROW 0b.**
**ROW 0b is decided on the full pinned corpus (`S-17M`, 1,856 cycles) or not at all.**

✅ **Fold the work:** `INST`'s ROW 0b leg **is** `S-17M`'s reading leg. The marginal cost of ROW 0b
is **one extra `BASE` replay of one corpus**, not four.

---

## Sec.A6 — 🔴 ROW 0d is circular as written. It is replaced.

**ROW 0d said:** *per cycle, Δ`h12Displaying` == the number of emitted decodes in that cycle whose
display came through a resolved 12-bit lookup.*

🔴 **The right-hand side is not computable from any artefact.** Spec Sec.2.3 records that
`message.c:594-613` renders a resolved 12-bit slot and a resolved 22-bit slot **identically** — that
is *why* the instrument exists. So the only available source for the RHS is the counter itself.

**Apply HK-025's own procedure to it. CLASSIFY:** validity. **EVALUATE BOTH BRANCHES:** fires ⇒ same
row; does not fire ⇒ same row, because both sides come from one counter. ⇒ **DIAGNOSTIC ⇒ QA would
be right to REFUSE it.** I am pre-empting a legitimate refusal, and the defect is mine.

**ROW 0d is struck and replaced by 0d-i and 0d-ii, both mechanical, both from artefacts or source:**

| row | check | predicate | consequence if it fires |
|---|---|---|---|
| **0d-i** | denominator is displays, not attempts (Trap 3) | per cycle, Δ`h12Displaying` **≤** `len(decodes)`; and over the leg, Σ Δ`h12Displaying` **≤** Σ `len(decodes)` | **VOID** — the counter is counting decode **attempts**, which is not the PO's quantity |
| **0d-ii** | increment site is the emission point | in the **reviewed commit**, the increment block sits **after** the dedup commit (`decoded_ht[walk] = …`) and after every `continue` that can still discard the message; asserted against pinned line numbers **and the commit SHA**, not a floating file | **VOID** — same defect, caught at source |

✅ **0d-i is a real falsifier, not decoration:** counting at the lookup site includes messages later
deduplicated or discarded (spec Sec.3.2 Trap 3), so the count **exceeds** emissions and the bound
breaks. That is precisely the error the row exists to catch.

📌 **DIAGNOSTIC, explicitly NOT a gate:** Δ`h12Displaying` against the count of emitted
**nonstandard-shaped** messages via `ARM 1B`'s `slot()` heuristic. **Report it; never gate on it.**
`ARM 1B`'s heuristic is a **disclosed lower bound**, and this spec retired it as an identifier
(Sec.2.3). It is a sanity read, and a spread is not a failure.

✅ **ROWS 0a, 0b, 0c, 0e, 0f, 0g are UNCHANGED**, as is their strict order — 0d-i and 0d-ii occupy
0d's position. ✅ Sec.5's "do the counters move?" remains **deliberately not a gate**: `S` = 0 is a
legitimate and highly decision-relevant reading, not an instrument failure.

**ROW 0a, restated mechanically:** each leg's recorded `dll_sha256` **==** Sec.4's manifest entry
**AND** `shim_version` == **20260046** (`BASE`) / **20260047** (`INST`). Both, not either.

---

## Sec.A7 — Preconditions, discharged with numbers

Spec Sec.2.1 flagged two things that could kill the arm. **Both are now measured, not assumed:**

✅ **`python qa/artefact_inventory.py --check` → "ARTEFACT_INVENTORY.md up to date", exit 0.** The
spec's "STALE since 2026-08-10" warning is **discharged** — the content is current; the `Scanned:`
line is excluded from the comparison, which is why the date alone was misleading.

✅ **All three primary corpora have full replayable WAV coverage**, and all three `owsfz/wav/`
directories were opened and their first/last files confirmed to span the run:

| corpus | band | cycles (`owsfz`) | **WAVs (`owsfz`)** | verdict |
|---|---|---|---|---|
| `S-17M` | 17m | 1,856 | **1,856** | ✅ replayable |
| `S-80M` | 80m | 1,210 | **1,988** | ✅ replayable |
| `S-20M` | 20m | 2,745 | **2,747** | ✅ replayable |

🔴 **Three bands survive ⇒ Sec.2.1's "if fewer than two bands survive, STOP and escalate" does NOT
fire.** No corpus is dropped and none is substituted.

✅ **Bonus, closing a `SUP-A` open item (HK-018):** `SUP-A` recorded `S-80M`'s log as *"not located
under the expected name — QA to locate"*. **It is
`artefacts/20260809_live_run_0155-8080-80m/owsfz/openswfz-20260809T015438Z.log`** (`…T015438Z`, not
`…T015445Z` — a 7-second offset from the first cycle stamp is what defeated the name match).
⚠️ **This does not resurrect anything from `SUP-A`. Its numbers stay VOID.**

---

## Sec.A8 — Order of work

| step | what | owner |
|---|---|---|
| 1 | **Commit the 24-file diff on `qa/sup-b-2026-08-30`** | 🔴 **Developer** (Sec.A2) |
| 2 | Pin `BASE`/`INST` SHA256 + shim versions into spec Sec.4's manifest, commit, verify `git diff --stat` **empty** | QA |
| 3 | Extend the harness with the three getters (Sec.A3.2); `out_json` under `artefacts/` (Sec.A3.3) | QA |
| 4 | Pilot: `--n-files 100`, `S-17M`, both legs — gross perturbation + `wall_s` cost read. **Not ROW 0b.** | QA |
| 5 | **ROW 0a → 0b → 0c → 0d-i → 0d-ii → 0e → 0f**, strict order, on `S-17M` full | QA |
| 6 | 🔴 **STOP. Report ROW 0 to the Captain.** Merge decision (HK-010). | **Captain** |
| 7 | Reading legs: `S-80M`, `S-20M` (corrected window), + ROW 0g per band | QA |
| 8 | Report per spec Sec.9.3 | QA |

🛑 **Step 6 is a hard stop.** No push, no merge, **no `pre_merge_check.py`** (HK-006 — Captain's
initiative only). ⚠️ **HK-025 is undiminished: QA may refuse any row on HK-021(k) grounds, naming the
row and its evaluation, and stop — no partial run, no Architect agreement needed.** ⚠️ **If this
amendment diverges from the shipped source, the shipped code wins and this document is the defect.**

---

## Sec.A9 — What the Architect owes

Nothing further before ROW 0's result. **Three errors in the parent spec are mine and are recorded as
mine: the merge/measure ordering (Sec.A1), the `S-20M` single-process assumption (Sec.A4), and ROW
0d's circular predicate (Sec.A6).** They join the `SUP-A` bracket defect already recorded in the
parent spec's Sec.1.2.

---

## Cross-references

- `qa/rr-study/2026-08-30-1149-architect-to-qa-spec-f001-sup-b-instrumented-suppression-sizing.md` — the spec this amends.
- `dev-tasks/2026-08-30-sup-b-h12-instrumentation.md` — the Developer handoff (`8faa141`).
- `qa/cycleframer-alignment-replay/g2_verification_replay.py` — the replay instrument, and its own extraction notice on why qa-tooling edits sit outside HK-011.
- `qa/cycleframer-alignment-replay/p23_common.py` — `Decoder`/`read_wav`/`normalise_rms`; carries the `DLL_SHA256` trap of Sec.A3.4.
- `qa/ARTEFACT_INVENTORY.md` — corpus/WAV coverage; regenerate with `python qa/artefact_inventory.py`.
- `qa/rr-study/2026-08-30-1129-qa-to-architect-f001-sup-a-result.md` — the `SUP-A` ROW 0b failure this arm answers.
