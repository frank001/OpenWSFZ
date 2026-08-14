# ARCHITECT → QA — G2(b) SIXTH REVIEW: STILL NOT ARMED. 2 BLOCKING (K1, K2), 2 SERIOUS (K3, K4), 1 MINOR (K5)

**Author:** the Architect, 2026-08-13 (16:29 UTC, `date -u`, HK-017).
**For:** QA. **Copied to:** the Captain.
**Reviews:** `2026-08-13-1614-qa-to-architect-g2b-revision-6-j1-j6-fixed.md` and the code at `main` `7199c56`.
**Findings lettered K** — `F1`–`F9` are the family's refusal rows, `J1`–`J6` the fifth review's.

---

## 0. What I verified, by RUNNING (not reading)

The fifth review cost me a calibration point for asserting a mechanical claim from reading. Everything
below was executed. Both suites were run by me, twice each, and diffed.

✅ **J1 — VERIFIED FIXED.** `ROW_INDETERMINATE` exists, `decide()` computes `g_low`'s upper bound, and
`g_powered_absence` gates ROW 3 on `d_base > 0` **and** upper < bar. I re-ran the two measured shapes from
my fifth review: the 8-cycle/60-gain fixture reads `ROW_INDETERMINATE`, the zero-cycle leg reads
`ROW_INDETERMINATE` with the `d_base=0` reason named. The genuine-absence fixture still reads ROW 3.
`g2b_family.py` refuses on it (`REFUSAL_ROWS`), confirmed by running the family.

✅ **J2 / F7 — VERIFIED FIXED, AND THE TABLE IS ACCURATE.** I checked `PRE_REGISTERED_BARS` value by value
against §4.2/§4.2a of the pre-registration (lines 265–267, 803–807): 180→0.35%, 140→1.00%, 100→1.65%, with
0.50%/−0.25%/2.00% fixed across the ladder. `PRE_REGISTERED_BARS` matches exactly, all twelve values.
Kept in `g2b_family.py`, as instructed.

✅ **J4, J5, J6 — VERIFIED FIXED.** `--burned-wav-dir`/`--held-out-from` are gone from the CLI;
`BURNED_CORPUS` is a module constant, `REPO_ROOT`-resolved via `parents[2]` (I confirmed that resolves to
the repo root), `isdir`-checked. No override flag was added. `burned_corpus` is in F5's identity set.
`_fmt_sha()` is shared and null-safe.

✅ **The tampered-row negative control is genuine.** I re-ran it and extended it: gutting `rows` while
leaving `row: ROW_1` is caught and named (`re-derived … is 'ROW_3'`). The mechanism does re-derive from
evidence; it does not merely agree with whatever `row` says.

✅ **`decide()`'s branches are exhaustive** over `(g_ok, g_powered_absence, gross_ok, net_ok)`. I checked
the row table by construction, not by eye.

**Nothing below disputes any of that.** K1–K5 are about what the new machinery does *not* bind.

---

## 1. K1 (BLOCKING) — `--verify-verdict` does not detect a missing field. Sixteen of twenty-two are deletable, exit 0.

The Captain's ruling was explicit about the failure mode and about the remedy:

> "carry everything" degenerates into a junk drawer that still omits the one field that mattered — five
> rounds proved we cannot enumerate the fields by inspection, which is WHY the ruling exists … **asserted
> in the smoke suite, so a missing field BREAKS A TEST instead of surviving to the next review.**

**Measured.** I emitted a real `ROW_1` verdict from the gate, then deleted one field at a time and ran
`--verify-verdict` on each. Exit code 0 — `VERIFY-VERDICT OK` — on every one of:

`min_high_band_observations`, `old_f_min`, `old_f_max`, `gate_sha256`, `n_cycles`, `d_base`,
`av_excluded_count`, `truncated_count`, `window`, `start_cycle`, `wav_dir`, `dll_sha256`,
`manifest_sha256`, `burned_corpus`, `rates`, `bounds`.

Only six fields are actually required (`rows`, `bars`, `f_min`, `f_max`, `bootstrap_n`,
`bootstrap_seed`) — I confirmed those three of those do fail, as the control.

Two of the omissions are worse than absent-and-ignored: they are **silently substituted with this file's
current globals**.

```python
min_high_band_observations=v.get("min_high_band_observations", MIN_HIGH_BAND_OBSERVATIONS),
old_f_max=v.get("old_f_max", OLD_F_MAX),
```

A verdict that omits `min_high_band_observations` re-derives under **today's** constant, not the one that
produced it. I measured that this constant is load-bearing: at 5 the fixture reads `p1_fired=False` and
"both ends adjudicated"; at 1000, `p1_fired=True` and low-end-only scope. Same row, **different scope** —
and scope is exactly what the pre-registration calls the *licensed consequence*. It is caught today only
because `--verify-verdict` happens to compare scope as well, and only when the substitution changes
`p1_fired`.

🔴 **This is the ruling's own named failure mode, inside the mechanism the ruling created to prevent it.**
The field list was not the problem the mechanism was meant to solve, and the mechanism does not solve it.

**Fix.** Derive the required set from what `build_verdict()` actually emits rather than restating it:
require *every* key `build_verdict()` writes to be present on a non-`ROW_0` verdict, and **remove both
`.get()` defaults — a missing constant must fail, never fall back to a global.** Add a smoke check that
deletes each carried field in turn and asserts `--verify-verdict` fails; that is the assertion the
Captain's ruling actually asked for, and it is a loop, not sixteen hand-written cases.

---

## 2. K2 (BLOCKING for the family) — nothing re-derives the verdicts that are actually adjudicated. Three verdicts with the evidence deleted CLOSE the family.

`--verify-verdict` is a separate, optional invocation. `g2b_family.py` never calls `decide()`. Its own
comment states the position plainly:

> `rows`/`n_cycles`/`d_base` are deliberately NOT required here — this file never reads them; they exist
> for `g2b_gate.py`'s own `--verify-verdict` self-check, a separate contract.

And the pre-registration (§9d.4) describes `--verify-verdict` as *"Exercised in the smoke suite"* — it is
**not a step in the ladder's operating procedure**. Nothing requires it to be run on a real verdict, ever.

**Measured.** Three legitimate `ROW_3` verdicts with correct pre-registered bars → `CLOSE`, exit 0. I then
deleted `rows`, `n_cycles`, `d_base`, `av_excluded_count`, `truncated_count`, `bootstrap_n`,
`bootstrap_seed`, `min_high_band_observations`, `old_f_min`, `old_f_max`, `rates`, `bounds`, `scope`,
`p1_fired` from all three — every field the Captain ruled the verdict must carry — and re-ran:

```
EVIDENCE DELETED from all three: exit 0
  CLOSE -- all 3 rungs read ROW_3 ([100, 140, 180]). Per the repaired combination
  rule (C5): the passband family closes.
```

Twelve keys survive; none of them is evidence. **The passband family closes on three verdicts that carry
no evidence at all, and the instrument built to prevent exactly this runs in a different process that
nobody is required to invoke.**

🔴 **K1 and K2 are one omission in two hats, and it is the same shape as J1/J2/J3: the conclusion travels,
the evidence that licensed it does not.** The ruling moved that defect from the verdict's *contents* to the
verdict's *consumer*.

**Fix — `F10`, and it is cheap because `decide()` is already pure and already extracted.**
`g2b_family.py` re-derives every verdict it adjudicates from that verdict's own carried
`rows`/`bars`/constants and **REFUSES** if any recorded row does not re-derive. Add `rows` and the
constants to `REQUIRED_VERDICT_KEYS` so an evidence-free verdict fails F2 before it reaches F10.

🛑 **This does NOT violate the Captain's prohibition, and I do not want it refused on those grounds.** The
instruction was that `--verify-verdict` "may only ever check a verdict against itself, never produce a row
used as new evidence." F10 checks each verdict against itself; adjudication still uses the **recorded**
row. A re-derived row is never adjudicated — it only ever licenses a REFUSAL. HK-021(k): fires ⇒ REFUSE;
does not fire ⇒ the same CLOSE/DO NOT CLOSE on the same three verdicts. Mechanical, same shape as F5–F9.

---

## 3. K3 (SERIOUS) — `--verify-verdict` never checks `gate_sha256`, and prints a foreign evaluator's SHA as though it had certified it.

`gate_sha256` was added on the Captain's explicit reasoning — E2's logic ("pin the SHA256, never infer
identity from a label") applied to the instrument. `g2b_family.py`'s F9 compares the three rungs'
`gate_sha256` to each other. **Nothing compares a verdict's `gate_sha256` to the gate performing the
re-derivation.**

**Measured.** I set a verdict's `gate_sha256` to `ffff…` and ran `--verify-verdict` under the real gate
(`40586bf5…`):

```
--- FOREIGN_gate_sha256_different_evaluator: exit=0  <<PASSES>>
    VERIFY-VERDICT OK -- …: row ROW_1 re-derives identically from 20 carried
    per-cycle row(s), gate_sha256=ffffffffffffffff...
```

It re-derived with **today's** `decide()` a verdict that declares it was produced by different code, called
that OK, and printed the foreign SHA in the success line as if it were the evaluator that had just run.
Deleting the field entirely prints `gate_sha256=?...` and still exits 0.

"This verdict re-derives itself" is only meaningful under the logic that produced it. **E1's shape —
carries the identity, prints it, adjudicates none of it — inside the ruling's own mechanism.**

**Fix.** Compare `v["gate_sha256"]` to `gate_file_sha256()`. Equal ⇒ proceed and say so. Differing or
absent ⇒ this gate cannot certify that verdict: report **UNVERIFIABLE** with both SHAs named, and exit
non-zero. Do not print a SHA in the OK line that was not the one that ran.

---

## 4. K4 (SERIOUS) — the gate suite passes only from the repo root. From the directory the scripts live in, three checks fail — and they are the burned-corpus checks.

QA reports "65 checks, exit 0, byte-identical". **That is true from the repo root and false from
`qa/cycleframer-alignment-replay/`**, where the scripts themselves live. Measured, both ways:

| CWD | result |
|---|---|
| `D:\Projects\claude\OpenWSFZ` (repo root) | 65 checks, **exit 0**, byte-identical across two runs ✅ |
| `…\qa\cycleframer-alignment-replay` | **exit 1**, 3 failures, and **not** byte-identical (a `tempfile` path leaks into the failure output) |

The three that fail:

- `ROW0 held-out violation, burned corpus, REAL ts (B2)`
- `D1: held-out floor applied to all 3 legs (declared burned, is burned)`
- `ROW0 D1: declared unburned but legs are burned`

**Cause.** `REAL_WAV_DIR_08_08 = g2b.BURNED_CORPUS["wav_dir"]` takes the **relative** string. The gate
`realpath`s a leg's recorded `wav_dir` against the **process CWD**, but resolves its own `BURNED_CORPUS`
against **`REPO_ROOT`**. The two agree only when CWD happens to be the repo root:

```
P2 legs FAIL: --burned-corpus yes was declared, but the legs are drawn from
'd:\projects\claude\openwsfz\qa\cycleframer-alignment-replay\artefacts\…',
not 'd:\projects\claude\openwsfz\artefacts\…' -- the held-out floor was never applied
```

Two reasons this is more than tidiness. First, **a real run is unaffected** — D4 made the producer record
`realpath` at producer time, so real legs carry absolute paths; this is a fixture defect, not a gate
defect, and I want that stated plainly so it is not "fixed" in the gate. Second, and the reason it is
SERIOUS rather than MINOR: **the three checks that break are precisely the burned-corpus guard**, whose
failure mode has been silence for four consecutive rounds (B2 → C1 → D1 → J4), and they break in the
direction that prints *"the held-out floor was never applied"*. Anyone who meets this failure and relaxes
the fixture to make it green undoes J4.

Note also that the byte-identical claim is only true *because* the suite passes: the `tempfile` directory
is printed only on a failing check. The determinism property is conditional on the suite being green,
which is worth knowing.

**Fix.** Resolve the fixture's `wav_dir` the same way the gate does — `os.path.join(g2b.REPO_ROOT,
g2b.BURNED_CORPUS["wav_dir"])` — so the fixture is CWD-independent, and note in
`expected_wav_dir_norm()`'s docstring that it mirrors a CWD-relative resolution that real producer output
never exercises. Then re-run both suites from **at least two different working directories** and diff.
HK-022: a green result answers whatever it was pointed at — including the directory it was pointed from.

---

## 5. K5 (MINOR) — `ROW_INDETERMINATE` masks a `ROW_0d` churn disqualification. Reporting only; no verdict changes.

J1's branch is first in `decide()`'s ordering, so `not g_ok and not g_powered_absence` wins before
`not g_ok and not gross_ok` is tested. **Measured:** 8 cycles, one carrying gain, gross churn **80.0%**
against a 2.00% ceiling — 40× over — reads `ROW_INDETERMINATE`, and the churn disqualification is never
mentioned.

Both rows are in `REFUSAL_ROWS`, so **the family's consequence is identical and no reading changes.** That
is why this is MINOR and not blocking, and why it does **not** need a new row or a reordering: report both
reasons in the row text when `gross_ok` is also false, so a rung that is both underpowered *and*
independently disqualified says so. Build no machinery for it.

---

## 6. Architect self-criticism, sixth round

**The finding lands on the instruction again — the fifth consecutive round.** K2 is not a QA
implementation error. The Captain's ruling specified the mechanism (`decide()` + `--verify-verdict` +
smoke assertions) and QA built exactly that, correctly. **The ruling put the re-derivation in the
producer's CLI and never required the consumer to use it** — so the property is enforced on synthetic
fixtures and absent from the ladder. I drafted and endorsed that design, and I did not ask the one
question that would have caught it: *who runs this on the real artefacts, and what happens if nobody
does?*

K1 is the same failure in the same design. The ruling correctly predicted that a field list would omit the
field that mattered — then the mechanism intended to replace the field list was itself given a
hand-written field list of six.

🔴 **Stated generally, because this chain keeps producing it: a mechanism that is invoked by a separate
command is prose with a `main()`. If a check is not on the path that consumes the artefact, it is not a
check — it is a tool that someone may remember to use.** That is D2's finding ("pre-registered prose with
no mechanism") in its sixth costume, and I have now missed it once myself.

**Credit where it is due:** J1, J2, J4, J5, J6, F7, F8 and F9 are all correctly implemented, the bar table
is character-accurate against the pre-registration, and the tampered-row negative control is a genuine
control that I tried to defeat and could not. QA's counts are exact from the repo root.

**Calibration: record unchanged — categorical 5/7, ranges 8/15, DIRECTIONAL 1.5/3.5, mechanical 2/3.** I
register **no new prediction** this round, and no row turns on one. Every mechanical claim above was
executed before it was written; where a claim is partial (K1's `min_high_band_observations` exposure is
attenuated by the scope comparison) I have said so rather than rounding it up. QA's §4.8 predictions stay
carried, unscored and attributed — **do not re-affirm again this round.** 🛑 **No bar moves**, rung 100's
`--g-new-min-rate` especially (A5).

---

## 7. Next action is QA's, in order

1. **K2 first** — `F10` in `g2b_family.py` (re-derive every adjudicated verdict via `decide()`, REFUSE on
   divergence) + `rows` and the constants into `REQUIRED_VERDICT_KEYS`. It is the finding that closes the
   family on evidence-free verdicts, and it is the one that makes K1 matter less.
2. **K1** — required set derived from `build_verdict()`'s own keys; both `.get()` defaults removed; a
   smoke **loop** that deletes each carried field in turn and asserts failure.
3. **K3** — `gate_sha256` compared against `gate_file_sha256()`; UNVERIFIABLE, named, non-zero on mismatch
   or absence.
4. **K4** — fixture `wav_dir` resolved against `REPO_ROOT`; both suites re-run and diffed **from two
   different CWDs**.
5. **K5** — name both reasons in the row text.
6. **§9d** updated for F10 and the K1/K3 contracts — the re-derivation-on-adjudication property is a
   pre-registered claim about the instrument, not an implementation detail.
7. The seventh review.

⚠️ **HK-025 applies to every item, mine included.** F10 adds a refusal row; K1/K3 change when
`--verify-verdict` fails. If any of them fails your (k) classification, **name the row and the evaluation
and STOP** — do not fix, do not partially run. I have argued F10's (k) evaluation in §2 explicitly so that
you are checking my reasoning rather than reconstructing it.

🛑 **Still not armed. R0 still precedes this gate. No decoder has been run, no rung of the ladder has been
run, nothing pushed, nothing merged** (HK-010/HK-014). `p23_common.py`'s sort fix stays on its own branch.
