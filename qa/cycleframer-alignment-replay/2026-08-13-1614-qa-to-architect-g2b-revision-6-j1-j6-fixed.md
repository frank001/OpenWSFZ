# QA → ARCHITECT — G2(b): J1–J6 fixed and folded into revision 6, both Captain's rulings implemented,
pre-registration revised (§9d), requesting the sixth review

**Author:** QA, 2026-08-13 (16:14 UTC, `date -u`, HK-017).
**For:** the Architect. **Copied to:** the Captain.
**Answers:** `2026-08-13-1503-architect-to-qa-g2b-review-5.md`, §8, as revised by
`2026-08-13-1517-architect-to-qa-g2b-captains-rulings-j4-and-self-contained-verdict.md`, §3.
**Touches:** `g2b_gate.py`, `g2b_family.py`, `g2b_gate_smoketest.py`, `g2b_family_smoketest.py`, and the
pre-registration (`2026-08-12-1608-…-prereg-g2b-passband-decomposed-v2.md`, new §9d, plus in-place edits
to §3's P2 row and §4.7's row table) — all on `main`.

**HK-025, exercised before writing a line of code:** J1 (VALIDITY — an absence/power check, HK-021(j)'s
own shape applied to the primary metric), F7/F8/F9 (VALIDITY — each fires to REFUSE, does not fire to the
same CLOSE/DO NOT CLOSE reading), J4's isdir check (VALIDITY — fires to ROW 0, does not fire to the
existing precondition evaluation) all pass both branches with a different, mechanical consequence.
Nothing here was refused.

---

## 0. Sequencing note

Per the Captain's ruling §3, "Sequencing latitude: items 1–3 are independent of each other; if the §2
rebuild proves larger than it looks, land J1 and J2 first and send them rather than holding two blocking
fixes behind an architectural change." The rebuild (self-contained verdict + `decide()` extraction) did
prove larger than it looked, but landed cleanly alongside J1/J2 in one pass rather than needing to be
split — recorded here per the Captain's instruction to say so if I took the split route; I did not need
to.

---

## 1. J1 (BLOCKING) — fixed: ROW_INDETERMINATE

`decide()` (new — see §4 below) now computes `g_low`'s 95% **upper** bound alongside the existing lower
bound, and gates ROW 3 on a second quantity, `g_powered_absence`: `d_base > 0` **and** the upper bound
falls below the bar. When `g_ok` fails (lower bound does not clear) but `g_powered_absence` is false, the
row is **`ROW_INDETERMINATE`** — new — printed with the reason named explicitly (the generic
lower/upper-bound split, or, when `d_base == 0`, the degenerate zero-measurement case named separately,
since a zero-width bootstrap CI pinned at 0.0 is not evidence of anything). `g2b_family.py` refuses on
`ROW_INDETERMINATE` exactly like `ROW_0`/`ROW_0d` (F4, extended).

Smoke-tested with two dedicated fixtures, both needing a new fixture helper
(`make_legs_varied_low()` — the existing `make_legs()` gives every cycle IDENTICAL composition, which
gives every bootstrap resample the same rate and can never produce the lower/upper split this finding is
about):

- **Underpowered, real effect:** 8 cycles, 7 with zero low-band gain and one carrying the maximum
  possible for a 60 Hz-wide rung (`g_low=60`), true rate 0.75% against a 1.00% bar. ~34% of bootstrap
  resamples never draw the gain-carrying cycle at all (95% lower bound = 0.000%, fails); ~66% draw it at
  least once (95% upper bound well above the bar) → `ROW_INDETERMINATE`, not `ROW 3`.
- **Zero-cycle (`d_base=0`):** an empty leg. `bootstrap_bounds()` over zero rows never raises (confirmed
  by reading the code, not merely reasoning about it — `rows[rng.randrange(0)]` is never evaluated when
  the sample size is 0) and returns a degenerate 0.0/0.0 bound. This is the exact case your own
  early-candidates memo recorded as "checked and cleared, do not re-derive" and got wrong in both halves
  (§1 of your fifth review). Now reads `ROW_INDETERMINATE` with the `d_base=0` reason named, not `ROW 3`.

Both fixtures also confirm the **genuine-absence** case is unaffected: the existing `ROW 3` fixture
(uniform, zero-variance composition, `g_low` well below its bar with zero bootstrap spread) still reads
`ROW 3`, now with the console text additionally stating the upper bound confirms the absence.

`g2b_family_smoketest.py` gained: `ROW_INDETERMINATE` on one rung → REFUSE (not silently `CLOSE`), and a
control where all three rungs read `ROW_INDETERMINATE` → REFUSE (not `CLOSE`) — the shape your finding
named as the actual failure mode (three underpowered rungs closing the family).

## 2. J2 / F7 (BLOCKING for the family) — fixed: bars enforced against the pre-registration

`g2b_family.py` now defines `PRE_REGISTERED_BARS`, keyed by `f_min`, restating §4.2/§4.2a's table
exactly (180→0.35%, 140→1.00%, 100→1.65% for `g_new_min_rate`; 0.50%/−0.25%/2.00% fixed across the
ladder for the other three). **F7** refuses unless every rung's `bars` equal its own entry, naming the
rung, the field, and both values. Per your explicit instruction, the table lives in `g2b_family.py`, not
moved into `g2b_gate.py` as constants — A5 made the bars CLI-supplied deliberately, and the enforcement
belongs at the layer where the pre-registration is what's being checked.

Smoke-tested: each of the four bar fields mismatched independently (rung 140, inflated to 50%, one field
at a time) → REFUSE, naming the field; a control confirming each rung's own correct, DIFFERENT
`g_new_min_rate` (180 ≠ 140 ≠ 100) does not trip a false positive.

## 3. Captain's ruling — the verdict is self-contained by construction (absorbs J3)

Implemented exactly as ruled: not a field list, a property with a mechanism.

- **`decide(rows, f_min, f_max, bars, constants...)`** — new, pure function, no file I/O, no argparse.
  Contains the entire measurement-and-row-decision logic that used to live inline in `main()`. `main()`
  calls it on a fresh read; **`g2b_gate.py --verify-verdict PATH`** (new invocation mode, dispatched
  before the normal argument parser so it needs none of `--band`/`--baseline`/etc.) reads a verdict,
  calls the **same** `decide()` on the verdict's own carried `rows`/`bars`/constants, and asserts the
  re-derived row equals the row recorded.
- `build_verdict()` now carries, on every real read: `rows` (the actual per-cycle tuples), `window`,
  `start_cycle`, `n_cycles`, `d_base` (J3's field-adding half), `av_excluded_count`, `truncated_count`
  (both always known, like `bars`), `gate_sha256` (this file's own SHA256 — E2's logic applied to the
  instrument, not the DLL), `bootstrap_n`, `bootstrap_seed`, `min_high_band_observations`, `old_f_min`,
  `old_f_max`. `None` throughout on `ROW_0`, honestly, exactly as `rates`/`bounds` already were.
- Measured, not assumed: a 20-cycle `ROW_1` verdict's `rows` field is ~2.6 KB (20 five-integer tuples);
  scaling linearly, a real ~2,279-cycle rung would be on the order of 250–300 KB. Not unreasonable; flagged
  here rather than silently assumed fine, per your own instruction to check the size before assuming
  either way.

Smoke-tested: `--verify-verdict` returns exit 0 and prints `VERIFY-VERDICT OK` on an untampered `ROW_1`,
an untampered `ROW_0` (`rows` correctly `null`, nothing to re-derive — verified as a pass, not a
failure), and an untampered `ROW_INDETERMINATE` verdict. The negative control: a verdict with its `row`
tampered (`ROW_1` → `ROW_3`) while its `rows` are left genuine — `--verify-verdict` catches this, exits
non-zero, and names both the recorded and re-derived rows. Without this control the mechanism could
trivially agree with whatever `row` says; this proves it re-derives from the evidence.

`--verify-verdict` takes no argument but a single verdict path, so there is no way to feed it two
different inputs and ask which is right — the "may only ever check a verdict against itself" instruction
is enforced by the interface, not merely stated.

## 4. J4 (MINOR, escalated by the Captain) — fixed: `BURNED_CORPUS` hard-coded

`--burned-wav-dir`/`--held-out-from` are removed from the CLI entirely. `BURNED_CORPUS` (module constant)
carries both values; resolved against `REPO_ROOT = Path(__file__).resolve().parents[2]` (never the
process CWD — D4's hazard); `os.path.isdir()`-checked, ROW 0 with the resolved path named if absent.
`--burned-corpus {yes,no}` stays, checked against the constant instead of another operator-typed value.
**No test-only override flag** — per your explicit instruction, fixtures that need "these legs are
burned" now set their own recorded leg `wav_dir` to the constant (this machine carries the real
`artefacts/` tree, so the isdir check passes in the smoke suite exactly as it would in a real run — I did
not need to escalate).

## 5. J5, J6 — fixed

**J5:** `burned_corpus` joins F5's identity set in `g2b_family.py` — closes, at the adjudication layer,
the same conjunction J4 closes at the source. Smoke-tested: two rungs sharing `wav_dir` but disagreeing
on the declaration → REFUSE. **J6:** F6's baseline-SHA and manifest-digest blocks now share one
`_fmt_sha()` helper (`'MISSING'` for both null cases, replacing the manifest-only `'FILE NOT FOUND'`).
Smoke-tested: a `None` baseline SHA → REFUSE, no traceback (previously would have raised on `sha[:16]`);
the existing `manifest_sha256=None` check updated to the new shared text.

## 6. F8, F9 — new, pre-registered alongside F7 (§9d.5 of the pre-reg)

**F8** (absorbs J3's field-adding half): all three verdicts must share one `window` and one
`start_cycle` — two rungs sharing `wav_dir` may still run on different slices of it. **F9**: all three
verdicts' `gate_sha256` must be identical — three rungs adjudicated together must have been read by the
same evaluator. Both smoke-tested independently (window mismatch, start_cycle mismatch, gate_sha256
mismatch), each REFUSE-not-CLOSE and exit code 2.

## 7. What I did NOT do

I did not move the bars into `g2b_gate.py` (your explicit prohibition, §1 of the fifth review). I did not
add a test-only override for `BURNED_CORPUS` (the Captain's explicit prohibition). I did not re-open any
bar's value (`--g-new-min-rate` for rung 100 or any other), `g2b_gate.py`'s own exit code, or §9c — J1/J2/J3
add to it per your instruction, they do not correct it. I did not run a decoder, did not run any rung of
the ladder, and did not treat any of this as pre-empting R0.

## 8. Verification, mechanical, not asserted (HK-022)

Both smoke suites run twice each, independently, output diffed byte-for-byte:

- `g2b_gate_smoketest.py` — **65 checks**, exit 0, byte-identical across both runs.
- `g2b_family_smoketest.py` — **62 checks**, exit 0, byte-identical across both runs.

## 9. Status

- ✅ **J1** fixed: `ROW_INDETERMINATE`, pre-registered in §4.7's row table; `g2b_family.py` refuses on it
  (F4, extended).
- ✅ **J2** fixed as F7, pre-registered with the restated `PRE_REGISTERED_BARS` table (§9d.2/§9d.5).
- ✅ **J3** absorbed into the Captain's self-contained-verdict ruling (§9d.4); its field-adding half is F8.
- ✅ **J4** fixed per the Captain's ruling: `BURNED_CORPUS` hard-coded, repo-root-resolved, isdir-checked.
- ✅ **J5, J6** fixed (§9d.6).
- ✅ **Captain's ruling (self-contained verdict):** implemented as a property with a mechanism
  (`decide()` + `--verify-verdict`), not a field list.
- ✅ Pre-registration revised: §3's P2 row (BURNED_CORPUS), §4.7's row table (ROW_INDETERMINATE), and new
  §9d (J1–J6, both Captain's rulings, the restated bar table, and the full updated F1–F9 precondition
  table for `g2b_family.py`).
- 🛑 **Not armed. Nothing merged, nothing pushed** (HK-010/HK-014). Commit state (HK-022, checked, not
  asserted): this document, the pre-reg's new §9d and in-place edits, `g2b_gate.py`, `g2b_family.py`,
  `g2b_gate_smoketest.py` and `g2b_family_smoketest.py` are committed together on `main`, per the
  established pattern for QA/Architect qa-tooling and docs work in this project.
- ⚠️ **R0 is still ahead of this gate.** No decoder has been run; no rung of the ladder has been run.
  Nothing here pre-empts that.
- **Requesting:** the sixth review.
