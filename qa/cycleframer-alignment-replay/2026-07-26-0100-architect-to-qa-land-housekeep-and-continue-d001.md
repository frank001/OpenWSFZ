# Architect → QA: land to `main`, housekeep, and continue D-001

**Author:** Architect, 2026-07-26 (01:00). **For:** QA. **Status:** operative — this is the
entry point for the D-001 thread; everything else in this directory is evidence or history.

Per HK-015 I have authored no `tasks.md` or `dev-tasks/*.md` entries. Part C specifies the work
in enough detail for QA to author both. Per HK-014 nothing is pushed; all four commits below are
local. Per HK-010 the push and the PR #108 close both need the Captain's explicit sign-off.

---

## 0. Reading order

The directory has grown to thirteen documents in one day. To pick the thread up cold:

1. **`2026-07-26-0015-d001-consolidation-and-clean-slate.md`** — the anchor. Where D-001 is, what
   is closed, what is live. **If you read one document, read this.**
2. **`2026-07-25-1200-architect-second-mechanism-located.md`** — the live lead (candidate
   saturation, LDPC survival). Predates the capture detour and was right all along.
3. **`2026-07-25-2300-alignment-root-cause.md`** — the measurements behind the decomposition.

Everything else is superseded or historical. Part B.5 asks you to mark it as such.

## 1. Where D-001 stands (one table)

68 matched cycles, `artefacts/20260725_live_run_1806/`:

| contribution | decodes | share |
|---|---:|---:|
| capture chain | 4 | 0.5 % |
| live path | 7 | 0.9 % |
| **decoder** | **740** | **98.5 %** |
| total gap | 751 (1.588×) | |

D-001 is a decoder problem. The live lead is **sync-candidate saturation at
`K_MAX_CANDIDATES` = 140** (`src/OpenWSFZ.Ft8/Native/ft8_shim.c:467`), saturated in 8 of 10
deciles with *identical* candidate yield on cycles decoding 22 messages and cycles decoding
none — while LDPC survival collapses (`failCands` 82 → 136, `meanAbsLLR` 4.075 → 3.83).

---

# Part A — Land to `main`

## A.1 What is unpushed

`main` is **4 commits ahead of `origin/main`**, 993 insertions, **zero `src/` files**:

| commit | author | contents |
|---|---|---|
| `7a04928` | QA | 21:45 cross-correlation note + `cycle-audio-archive` tasks.md §9 addendum |
| `e584082` | Architect | root-cause analysis; `measure_capture_alignment.py`, `measure_dt_alignment.py` |
| `63b0c33` | Architect | PR #108 disposition + work plan (**§4 withdrawn** — see B.5) |
| `37bcb11` | Architect | consolidation and clean slate (the anchor) |

## A.2 Decision still open on `7a04928` — it has *not* reached the remote

I previously described the 21:45 note as "on `main` at `7a04928`". That was wrong: it is
**local and unpushed**, so its incorrect content need never reach the remote. That window closes
the moment you push, so decide first.

Its §2–§4, and the tasks.md §9 addendum it carries, state:
- "11/68 pairs lock" → actually **68/68** once the ±50 ms search window is widened
- "lag ≡ 4 (mod 12), a fixed 0.333 ms residual" → actually **≡ 76 (mod 120)**, a 10 ms grid
- "the remaining 57/68 are inconclusive; most 15 s windows are noise-dominated" → they were a
  **truncated search**, not a physical result
- "a band-limited coherence refinement could sharpen those 57" → unnecessary; drop it

**My recommendation: land it, with a superseded-by banner, and rewrite the tasks.md addendum
(A.3).** Preserving the note documents a failure mode worth remembering — a truncated search
read as a physical result, which then attracted a plausible mechanism to explain it. The 23:00
document's §2 critique references it directly and reads oddly without it. But amending or
dropping the commit is entirely defensible while it is still local, and it is your commit and
your call.

## A.3 The tasks.md §9 addendum must be corrected regardless

Whatever you decide in A.2, `openspec/changes/cycle-audio-archive/tasks.md` currently carries 14
lines of §9 addendum repeating the incorrect claims. That file is an **OpenSpec artefact that
will be archived**, so the error would become permanent record. HK-002's content-drift check
applies directly.

Replace it with the corrected finding: 68/68 pairs lock at corr 0.933–0.992, all at lag ≡ 76
(mod 120) — a 10 ms grid matching the WASAPI device period; the ±500 ms sawtooth belongs to
WSJT-X's arm, not ours; capture-chain parity confirmed. Point at
`2026-07-25-2300-alignment-root-cause.md`.

## A.4 Gates

`python3 tools/pre_merge_check.py` — all gates PASS except **WSL Debian compile + test**, which
is one of the three catalogued local transient false-FAILs (HK-006). Zero `src/` files are
touched by any of the four commits, so it cannot be causal. Re-run before declaring ready and
confirm the failure is the known one.

## A.5 How to land

Docs and QA tooling only, no `src/`. HK-000 permits trivial zero-risk changes straight to
`main`, but **I recommend a single branch + PR** — the commits carry a significant analytical
claim that reverses a months-old working assumption, and they modify a `tasks.md` destined for
archive. That deserves a reviewable diff. One PR for all four commits is fine; they are one
thread.

---

# Part B — Housekeeping

## B.1 Close PR #108 unfixed — needs Captain sign-off (HK-010)

Draft, base `main`, branch `docs/propose-fix-cycle-boundary-clock-drift`, merge-base `9369900`.
Rationale in the anchor document §5.1; evidence in `2026-07-25-2300-alignment-root-cause.md`.

Mechanics already verified:
- `openspec/changes/fix-cycle-boundary-clock-drift/` exists **only on the branch** and was never
  merged, so there is **no OpenSpec archive step** — closing removes it wholesale, and HK-002
  does not apply to a close.
- **#108 is the only open PR** and targets `main` directly, so HK-008's
  retarget-before-delete hazard does not arise. Branch deletion is safe once closed.
- Verify `delete_branch_on_merge` behaviour individually before any manual delete (HK-003).

The six `dev-tasks/2026-07-2[345]-cycleframer-*.md` handoffs die with the branch. Record *why*
in one paragraph on the §9.5 closure — three fix rounds defeated by live testing because the
premise was falsified — rather than preserving six documents about a dead mechanism.

## B.2 Salvage before closing — one small PR, Developer session (HK-011)

Cherry-pick **only** these two files from the branch, raised **before** #108 is closed:

| file | lines |
|---|---:|
| `src/OpenWSFZ.Ft8/Ft8Decoder.cs` | +19 — per-cycle `hashTableRejectCount` logging |
| `tests/OpenWSFZ.Ft8.Tests/HashTableRejectCountLoggingTests.cs` | +141 |

Hash-table rejection is a **decoder** failure mode, so this is directly on the D-001 path and
will be wanted for Part C. It touches `src/`, so: Developer session runs `opsx:apply`, Captain
reviews the diff before push (HK-011).

**Do not salvage** the capture gap/enqueue-latency telemetry (`WasapiAudioSource.cs` +49,
`CaptureManager.cs` +48, tests +53). I recommended it at 23:30 and **withdrew it** at 00:15:
it instruments the subsystem now measured at 0.5 % of the gap.

## B.3 Close `cycle-audio-archive` §9.5 and archive the change

§9.5 — *"Decide, with the Captain, what happens to the paused PR #108"* — is the **last open box**
in the change. On sign-off, tick it with a one-line disposition pointing at the anchor document.

Then archive via `opsx:archive`. Unlike B.1 this **is** an archive, so HK-002 applies in full:
manually check task-completion-on-archive, delta-spec sync, and content drift — the last of
which is exactly what A.3 fixes.

## B.4 Artefacts (HK-016)

`artefacts/20260725_live_run_1806/README.md` exists but was backfilled after the fact, and the
README says so. Nothing outstanding for this run; noted only so the next live run gathers
artefacts automatically at close-out rather than on request.

## B.5 Mark superseded documents

Add a one-line superseded-by banner to the top of each; do not delete or rewrite the bodies:

| document | banner |
|---|---|
| `2026-07-25-2145-raw-audio-crosscorrelation-check.md` | §2–§4 corrected by the 23:00 root-cause doc |
| `2026-07-25-2330-…-pr108-disposition-and-workplan.md` | §4 work plan withdrawn; superseded by the 00:15 anchor. §2 (PR #108 mechanics) still current |
| `phase0`, `phase0b`, `phase1a`, `phase1b`, `deliverable-5-alignment-bound` | closed alignment work; retained as history, no live leads |

## B.6 `SPEC.md`

Add `measure_dt_alignment.py` to the tooling section. The 2×2 decoder-vs-audio design is a
**general instrument for separating a capture fault from a decoder fault** — it resolved in one
run what decode-count comparison could not resolve at all. Worth finding next time instead of
rebuilding ad hoc.

---

# Part C — Continue D-001

This is the actual objective. Everything above is clearing the ground.

## C.1 — Is the candidate cap costing us decodes? **Do this first**

**Why first.** Pass 0 caps candidates at 140 and is saturated in 8 of 10 deciles. If the true
candidate population exceeds 140, we discard candidates before LDPC ever sees them, and *which*
140 survive is an artefact of scoring order rather than signal quality. Both outcomes are
decisive, which is what makes it the right opening move.

**Method.** Rebuild the native shim with `K_MAX_CANDIDATES` raised — 140 → 300 → 600, **pass 0
only**, leaving `K_MAX_CANDIDATES_PASS2` (200) alone — and re-decode the fixed corpus at
otherwise production-baseline settings (`kMinScorePass2=10`, `osdCorrThreshold=0.10`,
`osdNhardMax=60`). Use the existing offline harness unmodified. Report per setting: total
decodes, `failCands`, `meanAbsLLR`, and decode elapsed time.

**Interpretation.**
- Decodes rise materially ⇒ we have been truncating. The cap becomes a tuned parameter and part
  of the 740 is directly recoverable.
- Decodes flat while `failCands` rises ⇒ the extra candidates are spurious, the cap is not the
  constraint, and the entire loss is LDPC survival → everything routes to C.2.

**Watch for:** decode time scales with candidate count against a 15 s per-cycle budget (current
median 373–653 ms, so there is headroom, but 600 candidates is 4× pass 0's work). If a setting
wins on decodes but breaches the budget, that is a real finding, not a failed experiment —
record it.

**Ownership.** Needs a native rebuild, so **Developer session under HK-011**, not a QA-only run.
QA drafts the dev-task and owns the analysis; Captain reviews the diff before any push.

## C.2 — Why is LDPC survival collapsing?

`meanAbsLLR` 4.075 → 3.83 and `prenormVar` 116 → 91 across the collapse is the thread — an LLR
scaling/normalisation question, and where the existing OSD parameters already act. **Scope this
after C.1 reports**, because C.1 changes the candidate population LDPC is asked to survive, and
scoping it now would be scoping against a moving target.

## C.3 — Structural comparison against WSJT-X — only if the gap survives C.1 and C.2

We run two passes (full waterfall, then spectrogram-suppressed at 200 candidates). WSJT-X runs
more passes with successive interference cancellation and a-priori decoding. If the 740 survives
C.1 and C.2, the residue is likely structural to `ft8_lib`, and the question becomes a product
one — how much of WSJT-X's decoder we are willing to reimplement — not a bug hunt. **That is a
Captain decision, and I would want C.1/C.2 results before framing it.**

## C.4 — Replication (issue #111)

The 98.5 %/0.5 % decomposition rests on one device, one band, one 21-minute session. **Do not
schedule a run for this** — fold the 2×2 into the next live run that happens for other reasons;
the marginal cost is the analysis, not the session. Acceptance: capture share stays in single
digits and framer σ stays well under one FT8 symbol (160 ms). Non-blocking; C.1 proceeds now.

## C.5 — DT reporting offset — low priority, not a D-001 lead

`Ft8Decoder` reports DT ~0.735 s high vs WSJT-X. This is a **reporting-convention difference,
not a misalignment**: `decode.c:279` searches −1.60…+3.04 s, centred at +0.72 s, and our median
DT is +0.68…+0.735 — the centre. In a 4.64 s search window a 0.735 s reference shift costs
nothing, which the data confirms (1288 decodes on WSJT-X's audio vs 1284 on ours, despite a real
0.133 s window difference).

It is still wrong where consumed — **ADIF and the UI** — so it warrants a small dev-task with a
regression test pinning median DT on a fixed corpus. The absence of such a test is why a 0.735 s
offset survived this long. **Sequence it behind C.1 and C.2.**

---

## D — Ownership and gates at a glance

| item | owner | gate |
|---|---|---|
| A.2 decide on `7a04928` | QA | — |
| A.3 correct tasks.md §9 addendum | QA | required before B.3 |
| A.5 push to `main` | QA | Captain sign-off (HK-010), gates (HK-006) |
| B.1 close #108 + branch | QA | Captain sign-off (HK-010, HK-003) |
| B.2 salvage PR | Developer | Captain reviews diff (HK-011) |
| B.3 tick §9.5, archive | QA | HK-002 manual audit |
| B.5, B.6 banners + SPEC.md | QA | — |
| C.1 candidate-cap sweep | QA drafts → Developer | HK-011 (native rebuild) |
| C.2, C.3, C.5 | scope after C.1 | — |
| C.4 replication | QA, opportunistic | issue #111 |

**Escalation is Dev → QA → Architect (HK-015).** If C.1 contradicts the anchor document's §1
decomposition, escalate rather than absorbing it — that table is what closed the capture avenue,
and it should not be quietly revised.
