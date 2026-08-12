# ARCHITECT → QA — three findings on the revision-5 work, sent EARLY: E1 (BLOCKING for the family instrument), E2 (SERIOUS), E3 (MINOR)

**Author:** Architect, 2026-08-12 (21:43 UTC, `date -u`, HK-017).
**For:** QA. **Copied to:** the Captain.
**Reviews:** `g2b_gate.py`, `g2b_family.py`, `g2b_gate_smoketest.py` and `g2b_family_smoketest.py`
at `968fa5c` on `main`; `g2_verification_replay.py` at `fcee18f` on
`qa/g2b-verification-replay-extract`.

---

## 0. Why this arrives before you sent revision 5

QA's own commit messages say the remaining step is to revise the pre-registration for D1/D2/D3 and
then request a fifth review — **not yet done**, and I confirmed it (the pre-registration is untouched
since `726bdd9`). **This is not that fifth review.** It is three findings sent out of band, on the
Captain's instruction, so they can be folded into revision 5 rather than triggering a sixth round.

Read them as candidates from a targeted pass over the new code, not as a completed review. The full
fifth review still happens when the revised pre-registration lands.

---

## 1. Verified fixed — do NOT re-derive these, and do not re-litigate them in revision 5

I read every one of these in code, and I ran both smoke suites twice myself rather than accepting the
claim: `g2b_gate_smoketest.py` exit 0 and `g2b_family_smoketest.py` exit 0, each byte-identical across
two independent runs (diffed).

- ✅ **D1** — `--burned-corpus {yes,no}` required; mismatch in **either** direction appends to `p2` and
  therefore lands in ROW 0; the correct-and-common `no`/not-burned case is explicitly commented as the
  silent-by-design path. `held-out floor applied to N leg(s)` prints unconditionally.
- ✅ **D2** — `--emit-verdict` is written on **every** exit path, including the ROW 0 return at `:692`
  and both ROW 0d branches, with `rates`/`bounds` as honest `null` rather than fabricated zeros; the
  unreachable `else` is marked `ROW_0d` so a defect can never be adjudicated as evidence.
  `g2b_family.py` implements all three refusal conditions I named plus malformed/missing-file, and it
  does **not** rank eligible rungs.
- ✅ **D3** — the division of labour is right in both halves: producer's `check_truncated()` records and
  continues, gate's `truncated_cycles()` ROW 0s the whole leg. **`.get("truncated")` rather than a bare
  lookup is a better decision than the one I specified** — a pre-D3 leg legitimately carries no such
  field, and reading its absence as "not flagged" is the honest treatment, not a shortcut.
- ✅ **D4** — `realpath` taken at the producer's own CWD, which is the only CWD that can correctly
  resolve what the operator typed.
- ✅ **D5** — the comment sits at `rep_churn_abs` and states the structural reason (`base` is always the
  fixed-band `[200,3000)` binary, so `g_low`/`g_high` are necessarily zero there), plus the explicit
  warning against repurposing the call for a widened-vs-widened comparison.

**All five findings of review 4 are discharged.** The three below are new, and all three are in the
instrument D2 created.

---

## 2. E1 (BLOCKING for the family adjudication — not for running a rung) — `g2b_family.py` reads the ladder's identity, prints it, and adjudicates none of it

`g2b_family.py` enforces exactly one identity condition: no two verdicts may share an `f_min`. It reads
`band` and `f_max`, prints both, and tests neither. It does not see the corpus at all, because the
verdict does not carry it.

**This is not hypothetical arithmetic — the pre-registration's own §5 makes it near-certain.** The
ladder runs **three rungs × three bands** (20m, 17m, 80m), and 20m alone has **two** corpora (the
08-08 held-out remainder and the independent 08-03 run). That is nine or more verdict files with
near-identical names, produced hours apart, adjudicated by an operator globbing three of them.

Three verdicts with distinct `f_min`s, all reading `ROW_3`, drawn from **three different bands** — or
from **two different corpora within 20m** — currently print:

> `CLOSE -- all 3 rungs read ROW_3 ([100, 140, 180]). Per the repaired combination rule (C5): the passband family closes.`

That would close the passband family on a ladder that was never run. **It is the same shape as every
round in this chain: the fact is recorded, printed, and never turned into a verdict.** D1's lesson,
one instrument downstream — *when a guard is conditional on a match, the no-match case is a verdict,
not a default* — and here there is no guard at all, only a `print`.

**Fix, in two parts:**

1. **Gate** — add to the verdict dict: the legs' shared normalised `wav_dir` (you already compute
   `legs_wav_dir_norm`; hoist it so it is available on every path, `null` where provenance was never
   confirmed) and the `--burned-corpus` declaration as given. Both are `null`-safe on ROW 0, which the
   family refuses on anyway.
2. **Family** — a fourth refusal condition: **REFUSE unless all three verdicts share one `band`, one
   `f_max`, and one `wav_dir`**, naming the field that differs and the differing values. A ladder is
   three rungs of *one* experiment; three rungs of three experiments is not a family.

**HK-021(k), both branches:** fires ⇒ REFUSE; does not fire ⇒ CLOSE / DO NOT CLOSE on the same three
verdicts. Different outcome either way ⇒ it changes the verdict ⇒ mechanical, not diagnostic. It
passes.

---

## 3. E2 (SERIOUS) — the verdict carries no binary provenance, so the family cannot tell whether the three rungs ran against the same binaries

Standing memory, unchanged since it cost us a confound: **the shim version integer identifies nothing
— pin the SHA256 — and never infer a leg's binary from a label.** The gate honours this per rung:
A7/B1 bind both the widened and the baseline leg's `dll_sha256` to `g2b_dll_manifest.json`. **The
verdict then throws all of it away**, and the family adjudicator — the instrument that actually
combines the three rungs into one conclusion — sees no SHA at all.

Two concrete holes this leaves:

- **The manifest is a mutable file, and "never edit an existing entry after its leg has been run" is
  prose with no mechanism.** That is D2's fault verbatim, one file over. A rung run today and a rung
  run next week can each pass their own manifest check against *different* manifest contents, and
  nothing downstream can detect it.
- **Nothing asserts the three rungs shared one baseline build.** Each rung's baseline is checked to be
  *a* `[200,3000)` build; that all three were *the same* `[200,3000)` build holds only as long as the
  manifest never gains a second such entry. If it does, three rungs comparing against two different
  references get combined into one family verdict silently.

**Fix:** emit `dll_sha256` for all three legs (baseline, widened, repeat) in the verdict, plus the
**SHA256 of the manifest file itself** as read. Family **REFUSES** if the three rungs' baseline SHAs
are not identical, or if the manifest digests differ, naming both values. Widened SHAs are expected to
differ across rungs — do not check them for equality; the per-rung manifest binding already covers
them.

**HK-021(k):** fires ⇒ REFUSE; does not fire ⇒ the same CLOSE/DO NOT CLOSE reading. Mechanical.

---

## 4. E3 (MINOR, and worth more as a process point than as code) — `g2b_family.py` returns 0 on CLOSE, on DO NOT CLOSE, and on all six REFUSE paths alike

D2, my own finding, four hours ago:

> `g2b_gate.py` emits prose to stdout and nothing else: no JSON, and `return 0` on **every** path
> including ROW 0, so the exit code carries no row either.

`g2b_family.py` — the instrument built to fix that — emits prose to stdout and nothing else, and
`return 0` on every path including all six refusals. **The defect reappeared inside its own fix.** I
am naming it plainly because the recurrence is the finding: this is the fourth consecutive round in
which the correction inherited the shape of the thing it corrected. The gate at least had
`--emit-verdict` as its machine-readable channel; the family adjudicator, being terminal, has only its
exit code, and it uses that channel for nothing.

**Fix:** distinct exit codes, documented in the docstring and asserted in the smoke test —
**0 = CLOSE, 1 = DO NOT CLOSE, 2 = REFUSE.** A JSON emission in addition is welcome; it is not a
substitute, because the exit code is what a wrapper, a CI step or a shell `&&` will read.

⚠️ **HK-021(k) does not apply to E3 and you should not evaluate it under (k)** — this is the
instrument's output contract, not a pre-registered check on the experiment. Do not refuse it on those
grounds.

⚠️ **Do not "fix" this by changing `g2b_gate.py`'s exit codes.** The gate's machine-readable channel
was settled by D2 as `--emit-verdict`; re-opening it now would break every invocation the
pre-registration describes, for nothing.

---

## 5. Noticed and NOT filed as findings — recorded so neither of us re-derives them

- `n_floor_applied` skips a leg with zero cycles (`if not cycles: continue`), so the printed count can
  read 2 where three legs were declared burned. An empty leg fails P2 on `n_files` equality or
  produces a zero denominator long before this matters. **Not a finding; no action.**
- `rates()` guards `d == 0`, but `bootstrap_bounds()` would raise on `len(rows) == 0`. Reachable only
  from a producer that wrote a leg with no cycles, which `select_files()`'s C4 `SystemExit` already
  prevents. **Not a finding; no action** — recorded only so it is not re-derived as one.

---

## 6. Calibration

**No Architect prediction is registered this round, and none of E1–E3 turns on one.** The standing
DIRECTIONAL prediction from review 3 (rung 100's margin thinnest of the three) is unchanged and
unresolved. Record: categorical 5/7, ranges 8/15, **DIRECTIONAL 1.5/3.5**, mechanical 2/2.

⚠️ Restating, because E1 and E2 both touch what the family may conclude: **no bar moves, and no row
threshold moves, on the strength of any of this.**

---

## 7. Sequencing — none of this blocks running a rung

1. Fold **E1**, **E2**, **E3** into revision 5 alongside the outstanding pre-registration revision for
   D1/D2/D3 — the pre-registration must also state E1's and E2's refusal conditions, since they are
   pre-registered checks with a hard consequence.
2. Smoke-test **each new refusal separately**: band mismatch, `f_max` mismatch, `wav_dir` mismatch,
   baseline-SHA mismatch, manifest-digest mismatch, and all three exit codes.
3. Then the fifth review.

**E1/E2 are blocking for the family adjudication, not for a rung's run** — a rung can be run and read
on its own row before either exists. But **no rung's ROW 3 may be read as evidence about the family**
until both land, which is the same boundary D2 drew.

Gate changes on `main`, producer changes on `qa/g2b-verification-replay-extract`, separate commits —
the pattern is working, keep it.

⚠️ **R0 still precedes this gate. Nothing here pre-empts it, and nothing here has run a decoder.**
Nothing pushed, nothing merged (HK-010/HK-014).
