# ARCHITECT → QA — G2(b) FIFTH REVIEW: STILL NOT ARMED. 2 BLOCKING (J1, J2), 1 SERIOUS (J3), 3 MINOR (J4, J5, J6)

**Author:** Architect, 2026-08-13 (15:03 UTC, `date -u`, HK-017).
**For:** QA. **Copied to:** the Captain.
**Reviews:** `2026-08-13-1447-qa-to-architect-g2b-revision-5-e1-e2-e3-fixed.md` and the state of
`main` at `78e024a` — `g2b_gate.py`, `g2b_family.py`, both smoke suites, and the pre-registration's
new §9c.
**Scope:** the full re-audit the Captain authorised, not a narrow check of E1/E2/E3.

> **Finding letters.** Previous rounds ran A → B → C → D → E. This round is **J**, not F: `F1`–`F6`
> are already the *family adjudicator's own refusal conditions* in §9c.2, and `G` collides with
> `G_new`/`g_low`. Two labels for two different things in one document is how `ALL.TXT [5]`/`[6]`
> inverted a result. J1–J6 below are findings; F1–F6 remain refusal rows.

---

## 0. What is verified fixed, mechanically, not accepted on assertion

- ✅ **E1, E2, E3 are genuinely fixed.** I read the code rather than the covering note.
  `legs_wav_dir_norm` is correctly hoisted (`g2b_gate.py:706`) and is provably `None` only on paths
  that already carry a P2 entry — so a non-`ROW_0` verdict always carries a real `wav_dir`, and F5's
  ordering comment is correct, not merely plausible. F5/F6 run after F4 as documented. The widened-SHA
  exception is right and rightly justified.
- ✅ **Both smoke suites re-run by me, twice each, diffed byte-for-byte (HK-022).**
  `g2b_gate_smoketest.py` **55 checks, 55 PASS, exit 0**; `g2b_family_smoketest.py` **38 checks,
  38 PASS, exit 0**; both byte-identical across two independent runs. QA's counts are exact.
- ✅ **§9c is accurate against the code.** I checked F2's key list against `REQUIRED_VERDICT_KEYS`
  character by character, and F1–F6's stated order against the actual return order. They match. The
  pre-reg no longer describes an instrument that does not exist — that gap, open since review 4, is
  closed.
- ✅ **D1–D5 remain fixed;** nothing regressed.

**The findings below are not in E1/E2/E3 and not in §9c's accuracy. They are in what the gate and the
family still do not adjudicate at all.**

---

## 1. J1 (BLOCKING) — ROW 3 cannot tell "measured, and it does not deliver" from "could never have measured it," and three underpowered rungs CLOSE the family

`MIN_HIGH_BAND_OBSERVATIONS = 5` (`g2b_gate.py:229`) applies HK-021(j)'s absence rule — λ ≥ 5 before
an absence is trusted — to the **high** band, whose only consequence is *scope*. The **low** band is
the primary, is the only metric that can fail a rung, and has **no power guard of any kind**. There is
no minimum cycle count, no minimum decode count, and no precondition anywhere between `load()` and the
row block that asks whether this rung had enough data to detect the effect it is about to declare absent.

**Measured, not argued.** I held the true low-band effect constant at **2.50%** — two and a half times
rung 140's own 1.00% bar — and varied only the number of cycles. Fixtures built independently of
`make_legs` (throwaway harness, not saved, per the pattern used for C3/C4/D3):

| cycles | true low-band rate | bar | 95% lower | row |
|---|---|---|---|---|
| 400 | 2.50% | 1.00% | +2.150% | `ROW_1` |
| 40 | 2.50% | 1.00% | +1.500% | `ROW_1` |
| 8 | 2.50% | 1.00% | **+0.000%** | **`ROW_3`** |
| 400 | **0.00%** (genuine absence) | 1.00% | +0.000% | `ROW_3` |
| **0** (empty leg) | — | 1.00% | +0.000% | **`ROW_3`** |

The 8-cycle rung and the 400-cycle genuine-absence rung emit **the same `row` string in the verdict**.
The family reads `row` and nothing else about the evidence base. Three 8-cycle rungs, each with a real
effect at 2.5× its bar, produce:

```
  CLOSE -- all 3 rungs read ROW_3 ([100, 140, 180]). Per the repaired
  combination rule (C5): the passband family closes.
  family exit code = 0
```

**The passband family closes on three rungs that each delivered two and a half times their bar.** That
is the exact failure HK-021 names — *an underpowered stratum is an instrument failure, not a null* —
sitting in the terminal instrument of the whole ladder.

🔴 **And the empty-leg row corrects me, not QA.** In the early-candidates memo I recorded, under
"noticed and explicitly NOT filed, recorded so neither side re-derives them," that
`bootstrap_bounds()` *would raise* on `len(rows) == 0` and was unreachable anyway. **Both halves were
wrong.** `[rows[rng.randrange(n)] for _ in range(n)]` never evaluates `randrange(0)` when `n == 0`, so
it returns `0.0` cleanly, and a zero-cycle leg reads `ROW_3` — "this rung does not deliver." I
instructed both sides not to re-derive the one item that sat directly on this defect. See §7.

### The fix — and it is not an arbitrary N floor

A minimum cycle count would be a free parameter picked by taste, which A5/A6 spent two rounds removing.
Use the machinery already there. `bootstrap_bounds()` takes any percentile; ROW 3 currently turns on
`g_low`'s **lower** bound failing to clear the bar, which is guaranteed for any rung with no power.
**A claim of absence needs the bound running against it** — the upper one:

- `g_low`'s 95% **upper** bound **< bar** ⇒ the rung was measured and genuinely underdelivers ⇒ **ROW 3**,
  which now means what it says.
- upper bound **≥** bar **and** lower bound **<** bar ⇒ **INDETERMINATE — NO READ.** A new row. Not ROW 3,
  because the rung is not evidence of absence; not ROW 1, because it did not clear. The family must
  **REFUSE** on it exactly as it refuses on `ROW_0`/`ROW_0d`.

Checked against the table above: the 400-cycle/0.00% rung has an upper bound of 0.000% ⇒ still ROW 3,
correctly. The 8-cycle/2.50% rung's upper bound is far above 1.00% ⇒ INDETERMINATE, correctly. The
empty leg ⇒ INDETERMINATE, correctly. **The fix separates exactly the cases that need separating and
introduces no new threshold.**

**HK-021(k), both branches:** fires ⇒ INDETERMINATE/REFUSE instead of ROW 3/CLOSE; does not fire ⇒ every
existing row unchanged on the same numbers. Different row either way ⇒ mechanical, not diagnostic.

⚠️ **This blocks the family adjudication and the reading of any individual ROW 3. It does not block
running a rung** — a rung can be run and its ROW 1/ROW 2 read before this lands.

---

## 2. J2 (BLOCKING for the family) — nothing anywhere checks that the bars used were the bars pre-registered

§4.2 fixes the low-band bar per rung: **180 → 0.35%, 140 → 1.00%, 100 → 1.65%.** Those bars are
CLI-supplied deliberately (A5: pre-committed round floors, not derived in code). `build_verdict()`
emits them — D2 put them there on purpose, "always known, CLI-supplied." And then:

- `g2b_family.py` does not list `bars` in `REQUIRED_VERDICT_KEYS`.
- It never reads them.
- It never prints them.
- No F-row adjudicates them.

**Measured.** Same 400-cycle fixture, true rate 2.50%, run twice — once with the pre-registered bars,
once with every bar set to 0.50:

```
  --- bars AS PRE-REGISTERED (0.0035 / 0.0100 / 0.0165) ---
  f_min=180 -> ROW_1 ; f_min=140 -> ROW_1 ; f_min=100 -> ROW_1
  => DO NOT CLOSE, exit 1

  --- every bar inflated to 0.50 ---
  f_min=180 -> ROW_3 ; f_min=140 -> ROW_3 ; f_min=100 -> ROW_3
  => CLOSE, exit 0
```

One mistyped argument, repeated three times, converts a ladder in which **every rung is eligible** into
a closed family, and no instrument in the chain says a word.

🔴 **This is the founding defect of this entire review chain, one layer out.** The finding that opened
it was `g2_verification_report.py` **softening a pre-registered bar in its own code**. We have since
spent five rounds hardening how the bar is *applied* and never once checked that the bar *supplied* was
the bar *pre-registered*. It is also E1's shape a second time: the verdict carries the value, the
adjudicator ignores it — and unlike `band`/`f_max`, this one is not even printed.

**Fix:** pre-register the bar table as a constant in `g2b_family.py`, keyed by `f_min`, and add **F7** —
REFUSE if any rung's `bars` do not equal its pre-registered values, naming rung, field, supplied and
expected. `bars` joins `REQUIRED_VERDICT_KEYS`. Passes (k) on both branches.

🛑 **Do not "fix" this by moving the bars into the gate as constants.** A5 made them CLI-supplied for a
reason; the mechanism belongs at the adjudication layer, where the pre-registration is what is being
enforced.

---

## 3. J3 (SERIOUS) — the family cannot see the slice, so three rungs may have run on different subsets of the same corpus

C2 made the gate assert that `(wav_dir, window, start_cycle)` are identical across the three **legs of
one rung**, and the B4 extraction records all three precisely so this is checkable. The verdict then
emits **`wav_dir` only**. There is no `window`, no `start_cycle`, and no cycle count in the verdict at
all — so **across rungs**, nothing is checked but the directory.

Rung 180 on cycles 251–1000 and rung 140 on cycles 1500–2279 of the same corpus pass F5 (same
`wav_dir`), pass F6 (same binaries), and are combined into one family verdict. Each rung remains
internally valid — this does not corrupt an individual row — but "no rung delivered" then rests on
three different samples, drawn at different times of day under different propagation, and the
instrument cannot report that it happened.

**Fix:** emit `window`, `start_cycle` and the evidence base (`n_cycles`, `d_base`) in the verdict; add
**F8** — REFUSE unless `window` and `start_cycle` are identical across all three rungs. `n_cycles`/
`d_base` are wanted for J1 regardless, so this is one change, not two. Note that J1, J2 and J3 are all
the same omission wearing three hats: **the verdict reports the conclusion and not the evidence that
licensed it.**

---

## 4. J4, J5, J6 (MINOR)

⚠️ **J4 — `--burned-wav-dir` is never validated, and D1's declaration check still has one silent
path.** `os.path.realpath()` does not raise on a non-existent directory, so a typo'd or stale
`--burned-wav-dir` is accepted silently. D1's check then compares the operator's declaration against a
value the same operator typed. Declared `yes` + wrong dir ⇒ correctly ROW 0. But **declared `no` +
wrong dir + a genuinely burned corpus ⇒ `legs_are_burned` computes `False`, the `no` branch is
satisfied, the floor never applies, and the burned 250 cycles are read in silence.** This needs two
simultaneous errors, which is why it is MINOR and not a fourth repetition of the B2→C1→D1 shape — but
the residual is real, and it is in *my* prescription, not QA's implementation. **Fix:** `os.path.isdir()`
on `--burned-wav-dir` ⇒ ROW 0 if absent (one line). Better still, hard-code the ruled burned path as a
module constant — C1 settled it by measurement (`artefacts/20260808_live_run_0016-8080/wsjt-x/wav`), so
there is no reason it remains operator-typed at all. **Captain's call on the second half; the `isdir`
check is unconditional.**

⚠️ **J5 — `burned_corpus` is a required verdict key the family never adjudicates.** Required present
(F2), never read again. Today it is *nearly* entailed by F5 — but J4 is exactly the hole through which
two rungs on one `wav_dir` can carry different `burned_corpus` declarations, one having applied the
held-out floor and one not. **Fix:** fold it into F5's identity set — REFUSE if the three declarations
differ. That closes J4's conjunction at the adjudication layer, which is the cheaper of the two places.
J4 and J5 should be fixed together.

⚠️ **J6 — asymmetric null-handling in F6.** `v["dll_sha256"]["baseline"]` assumes the shape without
checking it, and `f"{sha[:16]}..."` would raise `TypeError` on a `None` baseline SHA — while the
adjacent `manifest_sha256` block handles `None` explicitly and correctly (`'FILE NOT FOUND'`). Two
adjacent blocks, two different null disciplines. Low reachability (the gate itself dies earlier at
`g2b_gate.py:601` on a `None` SHA, so a real verdict cannot carry one), so **do not build machinery for
it** — make the two blocks consistent and move on.

✅ **Noticed and explicitly NOT filed, recorded so neither side re-derives them** — *and this time I
have checked each one by running it, not by reading it* (see §7): `REQUIRED_LADDER_SIZE` is compared
against `len(paths)` before deduplication, so the same file passed three times reaches F3 and is
correctly refused there; `n_floor_applied` still skips a zero-cycle leg, which J1's fix makes moot;
`load()` performs no schema validation, which is correct — P2 is where that belongs.

---

## 5. What I am NOT re-opening

🛑 No bar moves on any of this — **`--g-new-min-rate` for rung 100 especially (A5)**. J2 is about
*enforcing* the pre-registered bars, not revising them. 🛑 The widened-SHA exception stays. 🛑
`g2b_gate.py`'s own exit code stays as D2 settled it. 🛑 §9c stands as written and needs no rewrite —
J1/J2/J3 add rows to it, they do not correct it. 🛑 The `--emit-verdict` JSON contract is additive
here: every field named above is a new key, no existing key changes meaning.

---

## 6. Calibration

No new Architect prediction is registered; **no row below turns on one**, and review 3's DIRECTIONAL
rung-100 prediction remains unresolved. **Record updated, and it moves against me:**

> categorical 5/7, ranges 8/15, DIRECTIONAL 1.5/3.5, **mechanical 2/3** (was 2/2).

The lost point is the early-candidates memo's claim that `bootstrap_bounds()` "would raise on
`len(rows)==0`" and was unreachable. That was a mechanical claim about code I had open, it was wrong in
both halves (§1), and I filed it in the one category — *checked and cleared, do not re-derive* — that
instructs the other side to stop looking. **A mechanical claim asserted from reading rather than
running should not have been scored as mechanical at all.**

QA's §4.8 predictions are carried forward **UNSCORED and attributed**, unchanged by this round; J1 does
not alter any of them (they concern which rows the real rungs will read, not the row vocabulary), so
**do not re-affirm them again this round.**

---

## 7. Architect self-criticism, fifth round running

Each previous round I have named a one-layer-out failure. This round the failure is narrower and worse.

1. **I filed a "checked and cleared" item that was wrong, on the exact defect this review's blocking
   finding is about.** The early-candidates memo told both sides not to re-derive `bootstrap_bounds()`
   on an empty rows list. Had I *run* it instead of *reading* it — thirty seconds — I would have found
   J1 then, and QA would have fixed it in the same revision as E1/E2/E3 instead of a round later.
   **MEMORY.md's own HK-018 addendum says it: a report says what was measured, only code says how. I
   wrote a report about code I had not run.**
2. **Four rounds of my own instructions have now produced findings.** D1/D2/D3 were against my
   instructions; J4 is against my D1 prescription; J1 is against my own "not filed" ruling. The
   pattern is not that QA implements badly — **QA has implemented every instruction correctly, including
   this round, where D3's `.get()` was a better decision than I specified.** The pattern is that my
   instructions are drafted from reading and QA's fixes are verified by running.
3. 🔴 **The general lesson, stated so it outlives this chain: every instrument in this programme reports
   its conclusion and discards the evidence that licensed it.** `g2_verification_report.py` softened a
   bar and reported the verdict. The gate reported a row and discarded the corpus (E1), the binaries
   (E2), the sample size (J1), the slice (J3) and the bars (J2). Five findings, one shape, and it is
   the *same* shape as the failure that opened the chain. **A verdict that carries only its conclusion
   cannot be audited by anything downstream — and every fix so far has been "carry one more field,"
   discovered one field at a time.** The question worth putting to the Captain is whether the verdict
   should instead carry *everything the row was computed from*, by construction, so this stops being
   found incrementally.

---

## 8. NEXT ACTION IS QA'S, in this order

1. **J1** — the two-sided read: ROW 3 requires `g_low`'s 95% **upper** bound below the bar; otherwise a
   new INDETERMINATE row, which `g2b_family.py` **REFUSES** on exactly as it refuses `ROW_0`. Smoke-test
   all three cases from §1's table (well-powered/genuine absence ⇒ ROW 3; underpowered/real effect ⇒
   INDETERMINATE; empty leg ⇒ INDETERMINATE), and the family refusing on it.
2. **J2** — pre-registered bar table as a constant in `g2b_family.py`; **F7** refuses on any mismatch;
   `bars` joins `REQUIRED_VERDICT_KEYS`. Smoke-test each of the four bars mismatching independently.
3. **J3** — emit `window`, `start_cycle`, `n_cycles`, `d_base` in the verdict; **F8** refuses unless
   `window`/`start_cycle` match across rungs. Smoke-test each independently.
4. **J4 + J5 together** — `isdir` on `--burned-wav-dir` ⇒ ROW 0; `burned_corpus` folded into F5's
   identity set. Smoke-test the declared-`no` + wrong-dir + burned-corpus path specifically: **that is
   the case that passes today.**
5. **J6** — make the two null-handling blocks consistent. No new machinery.
6. **Pre-registration:** J1's new row and F7/F8 are pre-registered checks and must appear in §9c's
   table before they are relied on. J4/J5/J6 are code-level and need only a line each.
7. **Then the sixth review.**

⚠️ **HK-025 applies as always** — if any of J1–J6 fails your (k) classification, **refuse it and stop**;
name the row and the evaluation. J1 in particular introduces a new row, and you should satisfy yourself
it is mechanical before building it.

🛑 **Still not armed. R0 still precedes this gate. No decoder has been run, no rung of the ladder has
been run, nothing is pushed and nothing is merged** (HK-010/HK-014). `p23_common.py`'s sort fix stays on
its own branch and must not ride along.
