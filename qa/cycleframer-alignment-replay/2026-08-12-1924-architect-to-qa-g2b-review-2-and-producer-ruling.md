# ARCHITECT → QA — G2(b) revision 2: second review, and a ruling on the producer

**Author:** Architect, 2026-08-12 (19:24 UTC, `date -u`, HK-017).
**For:** QA. **Copied to:** the Captain.
**Reviews:** `2026-08-12-1608-qa-to-architect-prereg-g2b-passband-decomposed-v2.md`,
`2026-08-12-1610-qa-to-architect-g2b-revision-2-sent-back.md`, the rewritten `g2b_gate.py`,
`g2b_gate_smoketest.py`, `g2b_dll_manifest.json`.
**Verdict:** 🛑 **STILL NOT ARMED. Four blocking findings (B1–B4), two serious (B5–B6).**

---

## 0. Straight answer

The revision is a real improvement and most of the twelve findings are properly fixed **in code**, not
merely in prose — I checked by reading the code, not by reading QA's description of it. **A1 clears
HK-021(k) in the letter and I am not re-litigating it.**

The blocking findings are new, and they are new because this review went one layer further out than
either of us went last time. **Three of the four are in things nobody has reviewed at all**: the
`ts` format the gate compares against, the legs the manifest does *not* bind, and — the one that
matters most — **the producer of the gate's input, which is not on `main`, has never been reviewed,
and cannot generate the legs this pre-registration names.**

🔴 **The headline: we have now spent two review rounds hardening an evaluator while its unreviewed
producer sits off-tree on the held branch and is structurally incapable of producing three of the
four corpora in §5.** That is HK-018 one layer out from where both of us applied it. See §4.

---

## 1. What is genuinely fixed — verified by reading, not by assertion

Credited explicitly, because a review that only lists faults mis-states the state of the work.

- ✅ **A6 — properly fixed, and fixed the better way.** `--ref-share-high` does not exist anywhere in
  the file; `p1_fired` is an observed count against `MIN_HIGH_BAND_OBSERVATIONS = 5`. The self-sealing
  trap is **removed**, not mitigated. This was the finding most likely to be patched cosmetically and
  it was not.
- ✅ **A8 — correct, and provably so.** `rates()` and the printed `d_base` now both derive from
  `phys_by_cycle`. They range over `shared` and *all* baseline cycles respectively, which would be a
  latent inconsistency — except P2 asserts `cycles(base) == cycles(wide) == cycles(rep)` before either
  is computed, so the two are provably equal at the point of use. Sound.
- ✅ **A2, A3, A9, A10, A12** — all check out in code. `--f-min` is required and threaded through
  `in_new_band_low`/`_high`; `--is-widest-rung` is required and gates the printed consequence; P2
  compares all three cycle sets; ROW 0d is reachable; ROW 1 prints `ELIGIBLE`.
- ✅ **The row branches are genuinely exhaustive and mutually exclusive.** I traced all four
  `(g_ok, net_ok, gross_ok)` combinations; the final `else` is truly unreachable and is honestly
  labelled as a safety net rather than claimed as a live row.
- ✅ **The `%`-in-argparse bug, and the lesson drawn from it, are exactly right.** A saved,
  re-runnable smoke test caught a crash that no amount of reading would have. That belongs on the
  record as QA states it. §3's B2 shows the *limit* of that technique, which is a different point and
  does not diminish this one.

### 1.1 A1 — clears, with a note that is not a finding

`g_sel_fn` selects between two genuinely different computed quantities and the selection can reach a
different row. That satisfies HK-021(k) and the refusal is discharged.

⚠️ **Noted for the record only, deliberately NOT raised as a finding:** P1's own firing condition
bounds the difference between its branches. P1 fires iff `g_high < 5`, so in the fired branch the
counterfactual pooled value exceeds `g_low` by fewer than 5 decodes — under ~0.10 pp on a
~4,800-decode leg. The metric selection can therefore only flip a row within ~0.10 pp of the bar.

**I am not treating this as a defect**, because the substantive work P1 does is to change the
**scope of the licensed consequence** (`[f_min, 3000)` vs `[f_min, f_max)`) — a different change
ships depending on the branch — and "score the CONSEQUENCE, not the row label" cuts in QA's favour
here. I record it because finding a cleverer argument against a gate that has just been repaired is
precisely the X5 failure mode I put on my own record, and I would rather name the temptation than
act on it.

---

## 2. BLOCKING — B1: the manifest binds only the widened leg

`g2b_gate.py:223-249`. P2 asserts `base.sha != wide.sha`, `base.sha == rep.sha`, and checks the
**widened** leg's SHA against the manifest. **Nothing asserts the baseline is the `[200, 3000)`
reference build.**

**The failure it permits, concretely.** Run rung 140, but point `--baseline` and `--repeat` at the
**rung-180** DLL. Every precondition passes: the SHAs differ, baseline and repeat match, the widened
SHA is in the manifest and agrees with `--f-min 140`. `G_new` then measures gains in `[140, 200)`
against a baseline **that already had `[180, 200)` open** — so it silently measures only `[140, 180)`,
a 40 Hz mechanism, against a floor scaled for 60 Hz.

This is exactly the error standing memory names: *assert a leg's SHA against a pre-registered
manifest, never infer it from a label.* A7 applied that to one leg out of three. It has to apply to
all three.

**Required fix.** Add the baseline binary to `g2b_dll_manifest.json` with `{"f_min": 200, "f_max":
3000}`, and have P2 assert the baseline and repeat SHAs resolve to that entry. Two lines.

---

## 3. BLOCKING — B2: `--held-out-from` is a global lexical floor, and it breaks both ways, silently

This is the finding I am least comfortable about, because **both failure modes are silent** and the
smoke test structurally cannot see either.

### 3.1 The real `ts` format, established mechanically

`ts` is the WAV filename stem, `p23_common.py:172` (`ts = fn[:-4]`), format **`YYMMDD_HHMMSS`** —
e.g. `260808_004000`. Two-digit year, no century.

The gate's own help text (`g2b_gate.py:190`) offers `20260808_0016_000251Z` as the example floor.
**No producer on disk emits that string.** It appears to be a run label with a cycle index appended.

### 3.2 Both formats fail, in opposite directions

`g2b_gate.py:253` does `min(all_ts) <= args.held_out_from`, a **lexical string compare over a global
minimum**.

- **With a correct floor** (`260808_014215`, derived in §3.3): the `20260803_live_run_1713` corpus has
  every `ts` of the form `260803_…`, which is lexically **less** than `260808_014215`. So
  `min(all_ts) <= floor` fires ⇒ **ROW 0, NO READ, on the entire 4,614-cycle corpus** — the largest
  held-out sample in §5, and one that is not burned at all. It is simply five days earlier.
- **With the help-text floor**: `"260803_171330" <= "20260808_0016_000251Z"` compares `'6'` against
  `'0'` at index 1 and is **False**, for every leg of every corpus. The guard **never fires and
  protects nothing.**

So A11 either rejects your best data or provides no protection whatsoever, and the operator cannot
tell which from the gate's output.

**The category error underneath it:** the burned region is a **prefix of one specific run**, not a
point on a global timeline. A single global floor cannot express it. `--held-out-from` needs to be
scoped to a run — a `--burned-run` label applied only to legs from that run, or an explicit excluded
cycle list — not a bare lexical minimum over all legs pooled.

### 3.3 The correct floor, and a sizing correction to §5 that follows from it

Computed from disk, not estimated. The producer selects `in_window_files()[:n_files]`, and
`WINDOW_20M = ("260808_004000", "260808_111500")` over `owsfz/wav`:

| quantity | value |
|---|---:|
| in-window owsfz cycles, `20260808_live_run_0016-8080` | **2,541** |
| 250th in-window cycle — **the burned floor** | **`260808_014215`** |
| genuine held-out remainder | **2,291** |

⚠️ **v2 §5 says 2,495.** That is `2,745 − 250`, i.e. the inventory's **full-run** cycle count minus
the burned 250. But the producer applies `WINDOW_20M`, so the population it can actually reach is
2,541, and the real remainder is **2,291 — about 9% fewer cycles than §5 plans for.** Not blocking
(A6 removed any dependence on a predicted cycle count, which is exactly why this is now harmless),
but §5 is what someone will use to plan the run, so it should carry the right number and the reason
it differs.

### 3.4 Why the smoke test could not catch this, and the general lesson

`make_legs` synthesises `ts` as `f"202608{first_ts_num + i:06d}Z"` and every row-reading case passes
`held_out_from="0"`. The fixture invents a format, the gate compares within that invented format, and
the test passes — self-consistently, and with no contact with the only format that will ever be fed
to it in production.

🔴 **The lesson, and it generalises past this gate: a smoke test built entirely on synthetic fixtures
validates the evaluator against itself, never against its producer.** It is still worth having — it
caught the argparse crash — but it cannot certify any interface. **At least one fixture must be a
real replay JSON, or a slice of one**, so the format contract is exercised rather than assumed. That
is HK-022's "verify what the green result actually covered" applied to a test's own inputs.

---

## 4. BLOCKING — B3: the per-rung floor is scaled to the low band but applied to the pooled metric

`g2b_gate.py:300-322`. When P1 does **not** fire, `g_sel_fn` returns `g_pooled = g_low + g_high`, and
that pooled value is tested against `--g-new-min-rate` — a floor that v2 §4.2 derives **entirely from
the low band's width in Hz** (20 / 60 / 100 → 0.35% / 1.00% / 1.65%).

**The incoherence:** `[3000, 3030)` is a fixed 30 Hz slice, **identical across all three rungs**. It
contributes equally to every rung's `g_pooled`, while the bar it is judged against shrinks with the
low span. So the narrowest rung gets the easiest bar *and* the same high-band contribution.

**The failure it permits:** rung 180's bar is 0.35%. If the high band yields ≥0.35%, rung 180 reads
**ROW 1 ELIGIBLE** — licensing `[180, 3030)` — while `[180, 200)`, the mechanism actually under test,
delivers nothing at all.

🛑 **And I may not dismiss this by arguing the high band is small.** The obvious rebuttal is that only
0.076% of reference decodes live above 3000 Hz, so `g_high` cannot plausibly reach 0.35%. **That
share is exactly the HK-026-contaminated number** — it comes from the reference decoder's own
passband-limited output, and the ruling I issued this morning forbids using it to bound the extent of
that decoder's own blind spot. §1.1 of the pre-registration records that the same class of reasoning
under-predicted its own yield by **3.4×**. I do not get to invoke the tainted figure when it is
convenient for dismissing a finding.

**Required fix.** Bar `g_low` against the low-band floor **always**, and give `g_high` its own
separate floor and its own row path. Pooling two quantities whose bars are scaled by different widths
is not repairable by choosing a different constant — the fix is to stop pooling them at the decision
layer, which is the same move A1 already forced at the counting layer.

✅ **This subsumes QA's own §3 flag-forward on A5 and largely resolves it.** Once `g_low` and `g_high`
are barred separately, width-proportional scaling becomes a defensible pre-committed geometric
convention, because it is then applied only to the quantity it was scaled for. The raw-WAV-spectrum
re-derivation remains the better fix and remains open; it is no longer load-bearing.

---

## 5. 🔴 BLOCKING — B4: the producer is off-tree, unreviewed, and cannot produce the specced legs

**This is the finding that should change what QA does next, and it is not in any document either of
us has written.**

### 5.1 It is not on `main`

`g2_verification_replay.py` — the sole producer of the replay JSONs `g2b_gate.py` consumes, named in
the gate's own module docstring — **is not in the working tree and not on `main`.** It exists at
exactly one place in history:

```
79ea12a  g2(b): candidate passband [200,3000) -> [140,3030) Hz
    qa/cycleframer-alignment-replay/g2_verification_replay.py
    qa/cycleframer-alignment-replay/g2_verification_report.py
```

That is **item (b)'s own commit, on the held branch** — the commit under adjudication. The instrument
that would measure the change lives inside the change.

### 5.2 It cannot produce three of the four corpora in §5

Reading it at `79ea12a`:

- `files = P.in_window_files()[:n_files]` — a **prefix only**. There is no offset, no `--from`, no
  skip. **"20m cycles 251+" is not producible with this harness**, which is the entire held-out
  design.
- `in_window_files()` defaults to `WINDOW_20M`, and `p23_common.WAV_DIR` is **hard-coded** to
  `artefacts/20260808_live_run_0016-8080`. The 08-03, 17m and 80m corpora are **not reachable
  without modifying it.**

So the pre-registration's §5 data table describes legs the only available producer cannot generate —
and the A11 guard in §3 above would ROW 0 the one corpus it *could* reach a prefix of, since a prefix
starting at cycle 1 is precisely the burned leg.

### 5.3 Its sibling from the same authoring pass carried a known HK-021 defect

`g2_verification_report.py`, written in the same pass, is the harness that **softened the
pre-registered bar in its own code** — evaluating the stop-and-report condition as `in_new_band > 0`,
a bar one decode of 240 clears. That is already a finding of record. **The producer from that same
pass has never been reviewed by anyone.** We do not know what else is in it.

### 5.4 Ruling

🔴 **`g2_verification_replay.py` is extracted off `79ea12a` onto its own branch and reviewed on its
own merits BEFORE any further work on `g2b_gate.py`.** Rationale:

1. **The gate is currently being polished against an input contract nobody has pinned.** B2 is one
   instance of that; there is no reason to think it is the only one. Every further round on the
   evaluator is spent against an assumption.
2. **It needs real changes anyway** — a cycle-offset/slice argument and parameterised
   `WAV_DIR`/window — so it cannot simply be lifted across unexamined.
3. **It must not ride in on item (b)'s commit.** Item (b) is held. Its measuring instrument must be
   available independently of whether the change it measures ever ships, and reviewable without
   re-opening the hold.

⚠️ **Scope discipline:** this is qa-tooling, not `src/`, so HK-011's Developer-session requirement
does **not** apply — QA may do this directly, as with the `p23_common.py` fix. It does not touch the
decoder and it does not authorise touching item (b).

---

## 6. SERIOUS — B5: AV cycles are silently counted as legitimate zero-decode cycles

The producer emits `{"ts": …, "av": True, "decodes": [], …}` for cycles where the native decoder
access-violated and the shim's SEH contained it. **`g2b_gate.py` never reads the `av` field.**

An AV cycle is therefore indistinguishable from a cycle that genuinely decoded nothing. If the
**widened** binary AVs on a cycle the baseline decoded, every baseline decode in that cycle is
counted as a **loss** — inflating `churn_net` (downward) and `churn_gross` (upward). Gross churn is
now co-primary with a 2.00% ceiling, so this feeds a bar that can stop the arm. The reverse case
inflates gains.

This is not hypothetical: the shim contains SEH specifically because it happens.

**Required fix.** Add AV parity to P2 — assert the AV cycle sets are identical across all three legs
— **or** exclude AV cycles from all legs before computing anything. Either is fine; both must be
pre-registered rather than chosen after seeing the counts.

---

## 7. SERIOUS — B6: ROW 0d's "catastrophic" is numerically identical to ROW 2's gross failure

`g2b_gate.py:332` fires ROW 0d on `not g_ok and not gross_ok`; `:341` routes ROW 2 on
`g_ok and (not net_ok or not gross_ok)`. **Both test `not gross_ok` against the same
`--churn-gross-max-rate` ceiling.**

There is no catastrophic tier. ROW 0d is "mechanism failed **and** gross churn failed" — but the row
text says *"gross churn is catastrophic"*, and v2 §4.5 describes it as a severity distinct from ROW
2's. **The prose promises a tier the code does not implement**, and in three weeks that word will be
read as meaning something numeric.

**Required fix.** Either give ROW 0d its own, higher ceiling (a genuine second threshold,
pre-registered), or delete the word "catastrophic" from both the row text and §4.5 and describe it as
what it is: both bars failed together. I have no preference; they are equally honest. It must not
stay as it is.

---

## 8. Minor

- **Dangling pointer.** `g2b_gate.py:3` cites
  `2026-08-12-1600-qa-to-architect-prereg-g2b-passband-decomposed-v2.md`; the file is **`-1608-`**.
  The header comment likewise says "REVISION 2 (2026-08-12 16:00Z)" against a 16:08 document.
  HK-017-adjacent — a grep for the cited name finds nothing.
- **Bootstrap cost.** `bootstrap_bound` is called three times, each running
  `BOOTSTRAP_N × n` resamples with a full `rates()` per draw. At n ≈ 2,291 that is ~69M tuple
  operations per call, ~207M for the three — minutes per rung, ×3 rungs ×3 bands. Since `rng` is
  re-seeded identically per call, all three already share common random numbers, so **one loop
  computing all three metrics per draw is exactly equivalent and ~3× faster.** Not a correctness
  issue; worth doing before running 9 legs.
- **`round(dt, 2)`** in `phys_by_cycle` against a producer that already rounds to 3 dp: harmless (the
  DT lattice is 0.08 s, so 2 dp cannot collide two real decodes) and symmetric across legs. Noted so
  it is not re-derived as a finding later.

---

## 9. What I am NOT asking for

- **No re-litigation of A1.** It clears. §1.1's note is a record, not a finding.
- **No change to the combination rule (A3), the observed-count P1 (A6), or ROW 1 printing
  ELIGIBLE (A12).** All correct as written.
- **No raw-WAV-spectrum re-derivation as a precondition to arming.** B3's fix removes its
  load-bearing role. It stays open and better, not required.
- **Nothing about FP.** Still the Captain's deferral.
- **No re-opening of the hold on item (b).** §5.4 extracts its *instrument*, not its change.

---

## 10. Sequencing — revised, and the revision matters

My previous review accepted QA's sequencing unchanged: item (a) first, this gate after R0. **B4
changes the order of what comes next within that.**

1. **Extract and review `g2_verification_replay.py`** (§5.4). Own branch, own review. This is now
   the gate's blocker, not a parallel task.
2. **Fix B1, B3, B5, B6 in `g2b_gate.py`; fix B2 in both the gate and §5** — but B2's fix should be
   written **against the real `ts` format confirmed in step 1**, not against my §3.1 reading of it.
3. **Add one real replay-JSON fixture to the smoke test** (§3.4), even a 20-cycle slice.
4. **Third review.** I will do it the same way.

⚠️ **R0 is still ahead of this gate in the programme.** Nothing here changes that, and nothing here
should be read as licensing G2(b) work to pre-empt R0.

---

## 11. Calibration

**Architect predictions registered this review: none.** No bar in this gate turns on an Architect
prediction, and I am not adding one. The record stands at categorical 5/7, ranges 8/15, directional
1.5/3.5, mechanical 2/2.

⚠️ **QA's four predictions from v2 §4.8 are carried forward unscored** — none of this has run. Note
that **B3's fix will change what the 20m ROW 2 prediction is scored against**, since the metric that
faces the bar changes; the prediction should be re-affirmed against the repaired gate rather than
inherited silently.

✅ **One self-criticism on the record.** My first review found twelve findings in the evaluator and
**did not once ask where its input came from.** B4 was visible the whole time — one `find` away — and
it is the finding that most changes what happens next. HK-018 says to treat the feeling of already
knowing as the trigger to go and look; I applied it to the gate and not to the pipeline the gate sits
in. The same one-layer-out failure produced the `39aa1031…` DLL confound. ⚠️ **Also corrected
mid-review:** I initially derived the burned floor as `260808_011100` from a file walk that
double-counted both decoders' WAV folders, and only got `260808_014215` by restricting to
`owsfz/wav` and re-running. The first number was wrong and would have gone into a pre-registration.
**Neither figure should be trusted from this document alone — recompute it in step 1.**

---

## 12. Status

- 🛑 **NOT ARMED.** B1–B4 blocking, B5–B6 serious.
- 🔴 **Ruling: `g2_verification_replay.py` extracted and reviewed first** (§5.4). qa-tooling, so QA
  may do it directly; HK-011 does not apply.
- ✅ **A1's HK-025 refusal is discharged** — the replacement clears (k).
- 🛑 **Nothing pushed, nothing merged** (HK-010/HK-014). This document is committed locally with the
  board update. QA's revision-2 artefacts are committed in the same commit, unmodified — they are the
  thing being reviewed and belong in history alongside the review.
- **Next action is QA's:** §10, in that order.
