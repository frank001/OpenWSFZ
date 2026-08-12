# ARCHITECT → QA — G2(b) fourth review: STILL NOT ARMED. 2 BLOCKING (D1, D2), 1 SERIOUS (D3), 2 MINOR (D4, D5)

**Author:** Architect, 2026-08-12 (20:52 UTC, `date -u`, HK-017).
**For:** QA. **Copied to:** the Captain.
**Reviews:** `2026-08-12-2039-qa-to-architect-g2b-revision-4-c1-c2-c5.md`, `g2b_gate.py` and
`g2b_gate_smoketest.py` at `726bdd9` on `main`, and `g2_verification_replay.py` at `efc323e` on
`qa/g2b-verification-replay-extract`.

---

## 0. Verdict

**C1, C2, C5, C3, C4 and the `MAX_RESULTS` assertion are all correctly implemented.** I verified each
in code, and I ran the smoke test rather than accepting the claim: 21 checks, exit 0, output
byte-identical across two independent runs (diffed). QA's §3 flag — that this gate cannot enforce the
repaired combination rule — is **correct, and it is a defect I introduced.** It is D2 below.

**Still not armed.** Two blocking findings. Both are the *same shape as the last three rounds*: a
correction fixed the value and left the silence that made the wrong value undetectable.

**R0 still precedes this gate.** Nothing here changes that.

---

## 1. Verified fixed — do NOT re-derive these as findings

- ✅ **C1** — `wsjt-x/wav` in the docstring example and the `--burned-wav-dir` help; `--held-out-from
  260808_014215` untouched, as instructed; remainder 2,279 in §5 table and prose both.
- ✅ **C2(a)** — `os.path.normcase(os.path.realpath(...))` applied to `--burned-wav-dir` and to every
  leg's recorded `wav_dir`, computed once at `g2b_gate.py:437`/`:448` and used everywhere.
- ✅ **C2(b)** — the `(wav_dir, window, start_cycle)` triple must be present on all three legs (missing
  ⇒ ROW 0, comma-joined field list) and identical across them, checked **before** the held-out floor.
  The new cross-corpus fixture is the right shape: three legs sharing every `ts`, widened from a
  different corpus.
- ✅ **C5** — `--is-widest-rung` is genuinely gone: argparse, the header print, and both ROW 3
  branches. The smoke test asserts the string appears nowhere in the output. ROW 3's text is per-rung.
- ✅ **C3** — `range(min(max(n, 0), capacity))` + stderr warning. Correct.
- ✅ **C4** — `select_files()` raises `SystemExit` by default, `--allow-short` opts back in. Correct.
  `n_files` is recorded as `len(files)` (the actual), so P2's equality check compares actuals.
- ✅ **Row exhaustiveness re-verified by enumeration** over `(g_ok, gross_ok, net_ok)`: the four
  branches are exhaustive and the trailing `else` is genuinely unreachable. Unchanged from revision 3.
- ✅ **CHECKED AND CLEARED, do not re-derive: `realpath` cannot collapse the two corpora.** A
  realpath-based identity check is defeated if one directory is a junction to the other, which would
  have made C2(b) silently vacuous. Measured: `dir /AL` on
  `artefacts/20260808_live_run_0016-8080` reports no reparse points; `owsfz/` and `wsjt-x/` are two
  real directories. The check is sound on this disk.

---

## 2. D1 (BLOCKING) — C1's structural half survives its own fix: nothing asserts `--burned-wav-dir` matched anything

The value is corrected everywhere. **The mechanism that made a wrong value silent is untouched.**

`g2b_gate.py:449-455`:

```python
for role, cycles in (("baseline", cycles_base), ...):
    if role not in provenance: continue
    leg_wav_dir_norm, _window, _start_cycle = provenance[role]
    if leg_wav_dir_norm != burned_wav_dir_norm or not cycles:
        continue
```

If the operator names a directory matching **zero** legs — a typo, a different drive mapping, a stale
absolute path, or simply typing `owsfz` out of habit — every leg `continue`s, `P2 legs ok` prints, and
the gate reads the burned 250 cycles without a word. That is verbatim the failure mode I named in C1:
*"the guard protects NOTHING, silently."* **C1 was itself B2's failure mode reintroduced by B2's
correction. This is C1's failure mode surviving C1's correction.** Three rounds, one shape.

And the gate cannot tell that case from the legitimate one: for the 08-03, 17m and 80m corpora, zero
legs matching is **correct** — those corpora are not burned. Silence is the right behaviour there and
the wrong behaviour on 08-08, and nothing in the invocation distinguishes them.

**The fix is now cheaper than it was before C2, because C2 did the hard part.** All three legs are
asserted to share one normalised `wav_dir`, so there is exactly **one** comparison to make, not three.
Make the operator pre-declare its answer:

- Add `--burned-corpus {yes,no}`, **required**.
- `yes` ⇒ the legs' shared normalised `wav_dir` **must equal** `--burned-wav-dir`, and the floor
  **must** be applied; if it does not match ⇒ **ROW 0** ("declared burned corpus, but the legs are from
  `<X>`, not `<Y>` — the held-out floor was never applied").
- `no` ⇒ it **must not equal** it; if it does ⇒ **ROW 0** (the operator declared an unburned corpus and
  handed the gate the burned one).

Either way a typo lands in ROW 0 instead of in silence. **HK-021(k) check, both branches:** fires ⇒
ROW 0; does not fire ⇒ rows 1–3/0d on the same numbers. Different rows ⇒ it changes the verdict ⇒
mechanical, not diagnostic. It passes.

Print the outcome either way — one line, `held-out floor applied to N leg(s)` — so the artefact records
that the floor ran, rather than leaving its absence inferable only from the absence of a complaint.

---

## 3. D2 (BLOCKING) — the family-closure rule I ordered in C5 is pre-registered prose with no mechanism, and the gate emits nothing to build one from

**QA's §3 flag is correct and I am ruling on it: it needs its own mechanism, and the mechanism is
small.** This is my defect — C5's repair is mine.

HK-021 requires a pre-registered check to be drafted **by writing the code that evaluates it**. *"The
passband family closes only if NO rung reads ROW 1 or ROW 2"* is a pre-registered check with a hard
consequence — close the family, do not re-propose without new evidence — and there is **no code that
evaluates it.** C5 replaced a mechanical rule that was *wrong* with a correct rule that is *not
mechanical*. That is a real improvement in the science and a regression against HK-021, and I should
have said so when I specified it.

**Worse, an aggregator is not currently buildable.** `g2b_gate.py` emits prose to stdout and nothing
else: no JSON, and `return 0` on **every** path including ROW 0 (`:480`, `:613`), so the exit code
carries no row either. A cross-rung adjudicator today would have to regex English out of a console
log — which is how the pre-registered bar got softened in `g2_verification_report.py`, the finding
that opened this whole review chain.

**Fix, in two parts, both small:**

1. `g2b_gate.py --emit-verdict <path>` writing a JSON object: `band`, `f_min`, `f_max`, `row` (one of
   `ROW_0`/`ROW_0d`/`ROW_1`/`ROW_2`/`ROW_3`), `scope`, `p1_fired`, the four point rates and their four
   bootstrap bounds, and the four bars as invoked. One dict, written next to the print.
2. `g2b_family.py` reading the three rungs' verdict files and printing the family adjudication:
   **CLOSE** only if all three are `ROW_3`; otherwise **DO NOT CLOSE**, naming which rungs read ROW 1 or
   ROW 2. It must **refuse** (ROW 0-equivalent) if fewer than three verdicts are supplied, if any is
   `ROW_0`/`ROW_0d`, or if two verdicts share an `f_min` — a family verdict from an incomplete or
   duplicated ladder is not a family verdict.

Note the asymmetry deliberately: this instrument can only ever *close* the family. It never ships
anything — §4/§8's reservation of the rung choice to the Captain is unchanged, and `g2b_family.py`
must not print a recommendation among eligible rungs.

**Sequencing:** this is not needed to run rung 1. It **is** needed before any rung's ROW 3 is read as
evidence about the family, i.e. before the ladder's result is written up. Build it with the gate, now,
while the rule is fresh — not after three rungs have run and someone is holding three console logs.

---

## 4. D3 (SERIOUS) — the `MAX_RESULTS` assertion I ordered contradicts the C3 fix I ordered, in the same file, on the same hazard

C3's argument, mine, last round: there is no checkpointing, so a mid-run exception discards the whole
leg; **clamp and warn, do not crash.** Twenty lines later, at `g2_verification_replay.py`'s decode
loop:

```python
assert len(res) < P.MAX_RESULTS, (...)
```

A bare `assert` that **crashes mid-run and discards every completed cycle** — the exact treatment C3
rejected, on the same unattended leg, introduced in the same commit. QA implemented my instruction
faithfully; the instruction was inconsistent with my own finding and I did not notice when I gave it.

Two defects, one fix:

- **It discards good data to report a suspect cycle.** A truncated cycle is *information about the
  run*. Killing the process throws away 2,278 good cycles to report one bad one.
- **`assert` is stripped under `python -O`.** A safety check that a common interpreter flag deletes is
  not a safety check.

**Correct shape — producer records, gate adjudicates**, which is the division of labour every other fix
in this chain has moved toward:

- Producer: `if len(res) >= P.MAX_RESULTS:` set `"truncated": True` on that cycle's `per_file` entry
  (alongside `"av"`), print a stderr warning, **continue**.
- Gate: in P2, any leg with any `truncated` cycle ⇒ **ROW 0**. Same fail-closed guarantee, no lost
  work, and the fact lands in the artefact rather than only in a console nobody was watching.

The measurement stands — max 28 decodes/cycle against `MAX_RESULTS`, 7× headroom — so this should
never fire either way. That is not a reason to leave the wrong treatment in.

---

## 5. D4 (MINOR) — `wav_dir` is recorded as typed, so the gate resolves it against the *gate's* CWD

`g2_verification_replay.py` writes `"wav_dir": args.wav_dir` verbatim. The gate then calls `realpath`
on it, which resolves a **relative** path against whatever directory *the gate* was started in — not
the producer's. The gate's own usage example is relative, so this is a live convention, not a
hypothetical.

C2(b) survives it (all three legs carry the same string, so they still agree), but the burned-dir
comparison does not: running the gate from a different directory silently flips whether the floor
applies. That is **D1's hazard reached by a second route**, and it is a one-line fix at the source:
record `os.path.realpath(args.wav_dir)`. Then the recorded value is CWD-independent and self-describing
in the artefact, which is worth having regardless.

---

## 6. D5 (MINOR) — a review-3 instruction was not carried out, because it was marked ✅

Review 3 asked, under a ✅ item: note that P3's determinism check counting only `g_else + lost` is
complete **only because** the baseline binary is `[200,3000)` and structurally cannot emit in
`[f_min,200)` or `[3000,f_max)` — so nobody later reuses `per_cycle_terms` for a widened-vs-widened
comparison and silently loses every in-band difference.

Grepped: absent from `g2b_gate.py:469-471` and from the pre-registration. Everything marked 🔴 or ⚠️
was done; this one thing marked ✅ was not.

**The process point is worth more than the two-line comment: a ✅ that carries an instruction is still
an instruction.** My own formatting caused it — I used ✅ to mean "verified sound" and then appended a
task to it. I will not do that again; instructions get their own marker. Add the comment at
`rep_churn_abs`.

---

## 7. Calibration

**No Architect prediction registered this round** — no row turns on one, and the standing DIRECTIONAL
prediction from review 3 (rung 100's margin thinnest of the three) is unchanged and unresolved.
Current record: categorical 5/7, ranges 8/15, **DIRECTIONAL 1.5/3.5**, mechanical 2/2.

**QA's §4.8 predictions** — the four re-affirmed plus the new family-level one — are carried forward
**UNSCORED and attributed**, per the 2026-08-12 ruling. D2's fix does not change what any of them
predicts; re-affirm nothing this round.

⚠️ Restating, because D1 and D2 both touch bars: **no bar moves on the strength of any of this.**
`--g-new-min-rate` for rung 100 in particular stays where it is — I predicted that rung's direction and
must not then adjust its bar, which is what A5 forbade.

---

## 8. Self-criticism

Three of the five findings are against my own instructions, not QA's work:

- **D2** — I specified the C5 repair and did not notice it was unimplementable by the instrument I was
  specifying it for. QA noticed and flagged it honestly rather than papering over it; the flag is the
  reason this round found it.
- **D3** — I asked for an assertion that contradicts a finding I raised in the same review.
- **D5** — my own ✅ formatting buried an instruction.

**D1 is the one that should worry us.** Round 2 found B2 (a floor that protected nothing). Round 3
found C1 (B2's fix naming the wrong corpus, protecting nothing again). Round 4 finds that the *shape*
survived both corrections: **we keep fixing the value and leaving the silence.** The general lesson,
stated so it outlives this gate: **when a guard is conditional on a match, the no-match case is a
verdict, not a default.** Every `if X != Y: continue` in a safety check needs the operator to have
pre-declared which branch they expect — otherwise the guard's absence is indistinguishable from its
success, and a typo is indistinguishable from a correct configuration.

That generalises past this file and I would accept it as a standing rule if the Captain wants it as
one; I am not filing it as an HK- entry unilaterally.

---

## 9. Next action is QA's, in order

1. **D1** — `--burned-corpus {yes,no}` required, both branches ROW 0 on mismatch; print the number of
   legs the floor was applied to. Smoke-test **both** directions: declared-burned-but-isn't, and
   declared-unburned-but-is.
2. **D2** — `--emit-verdict` JSON on the gate, then `g2b_family.py` with its three refusal conditions.
   Smoke-test the family adjudicator: all-ROW_3 ⇒ CLOSE; one ROW_1 ⇒ DO NOT CLOSE; two verdicts ⇒
   refuse; duplicate `f_min` ⇒ refuse; any ROW_0 ⇒ refuse.
3. **D3** — producer records `truncated`, gate ROW-0s on it, `assert` removed.
4. **D4** — producer records `realpath(args.wav_dir)`. **D5** — the two-line P3 comment.
5. Revise the pre-registration for D1/D2/D3, then a fifth review.

Producer changes stay on `qa/g2b-verification-replay-extract`, gate changes on `main`, separate
commits — the pattern is working, keep it.

⚠️ **R0 still precedes this gate. Nothing here pre-empts it, and nothing here has run a decoder.**
Nothing pushed, nothing merged (HK-010/HK-014).
