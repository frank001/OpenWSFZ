# `F-001` L3 — Amendment 2: corpus substitution granted, and ROW 0d withdrawn as unevaluable

**Author:** Architect, 2026-09-08 (20:31 UTC, `date -u`, per HK-017).
**For:** QA, answering three questions raised before building anything.
**Amends:** `2026-09-02-1631-architect-to-qa-spec-f001-l3-own-hash-compare-sizing.md` + Amendment 1.
**Status:** docs-only, committed locally, **not pushed** (HK-014). Base `origin/main`@`cf21ac5`.

🔴 **Written before any L3 datum has been read on any corpus.** No `ft8_get_h12_unresolved_by_code`
output exists anywhere on disk. This is pre-registration, not post-hoc widening, and the corpus
choice below is therefore **not outcome-chosen** (HK-021(y)).

---

## 0. Headline

| QA's question | Ruling |
|---|---|
| 1. Substitute tonight's `FP-FLOOR-LIVE-2` archive for the `s17m` replay leg? | ✅ **GRANTED**, with two bars (§1.2, §1.3). QA's reading — nothing in the predicates is band-specific — is **correct**. |
| 2. Is a `20260049` binary on disk for ROW 0e? | ✅ **YES, no rebuild.** `artefacts/2026-09-03-f001-l3-shim-rebuild/libft8-20260049-prechange.dll`, SHA256 verified this session. **And ROW 0e has already passed once** (§2.2) — re-run it anyway, on the analysed leg. |
| 3. Write the `g3` extension + a §5 gate-evaluation script? | ✅ **AUTHORISED** — §7 step 3 anticipated exactly this. Conditions in §3. |

🔴 **And a fourth thing QA did not ask, found while checking question 3: ROW 0d cannot be evaluated
on the shipped `20260050` ABI, and the natural implementation makes it tautologically green.** That
is my drafting fault, it is the exact HK-022 failure the spec lectures about, and §4 withdraws the
row and says what is now uncovered. **Read §4 before writing the gate-evaluation script** — it is
the only part of this amendment that changes a verdict path.

---

## 1. Question 1 — corpus substitution: GRANTED

### 1.1 QA's reading is right, and here is the check rather than the assurance

I re-read every predicate against the substitution. ROW 0a (binary identity), 0b (`U_total` vs
`<...>` renderings **from the same leg**), 0c (`out_of_range`), 0e (byte-identity across binaries),
0f (`n12 == 149`), 0g (`U_clean` floor), ROW 1/2/3 (`U149`, `E_uniform`, occupancy): **not one names
a band, a frequency, or `s17m`.** §4's `s17m` pin was a choice of *the largest corpus available on
2026-09-02*, not a property the measurement requires. Tonight's archive is larger and fresher.

✅ **It also honours §4's actual bar — "No capture run. No live transmission. Replay only."** That
bar exists so L3 sizing does not commission RF work. `FP-FLOOR-LIVE-2` is capturing for its own
pre-registered reasons and would run identically if L3 did not exist. Reading its archive afterwards
is replay. **The bar is not lifted; it is unbroken.**

✅ **One substantive improvement over `s17m`, worth stating because it is why I am not merely
tolerating the substitution:** `s17m` predates `c3a9ea8` (the negative-`time_offset` SNR collapse
fix, shim `20260046`). I verified `c3a9ea8` **is** an ancestor of `ac6150d`, so the `20260050` L3
binary already contains that fix — meaning an `s17m` reading would size L3 on decode behaviour the
shipped binary no longer produces. **Tonight's post-fix corpus is the better-matched population, not
just the more convenient one.** This is the same defect that forced `FP-FLOOR-LIVE`'s withdrawal
(`2026-09-08-1745-…WITHDRAWAL…`); it applies here for identical reasons and I had not spotted it.

### 1.2 🛑 BAR 1 — do not put replay load on the capture machine while the capture is live

`FP-FLOOR-LIVE-2` is a **live-capture** arm whose validity depends on the daemon not missing cycles,
and whose corpus was already restarted once tonight (Amendment 3, clean start `19:36:45Z`) over a
*suspicion* of disturbance that investigation could not confirm. A dual-binary replay decode over
thousands of cycles is a heavy, sustained CPU load.

🔴 **Run the L3 replay only after `FP-FLOOR-LIVE-2` has hit its stopping rule (`n ≥ 600` or 24 h from
`19:36:45Z`) and the daemon is stopped** — or on a machine that shares nothing with the capture.
**If the replay runs concurrently and `FP-FLOOR-LIVE-2` later shows any cycle-loss anomaly, the two
arms become mutually confounded and both are damaged.** L3 is not time-critical; the capture is
in flight. The capture wins.

⚠️ **Sharpening added 2026-09-08 ~20:5xZ, after QA correctly pushed back that the machine has ample
CPU headroom (~6% utilisation, observed by the Captain).** That observation is fair and the
performance reasoning behind it was **incomplete, not wrong** — and idle-state utilisation is not
evidence of headroom *under* the load in question, nor is mean utilisation the quantity a capture
daemon is sensitive to (scheduling-latency spikes on the audio path are, and I do not know that
daemon's tolerance). But the load question is **not the load-bearing one**, and the argument's real
form is stronger than "two arms might interfere":

🔴 **L3's corpus IS `FP-FLOOR-LIVE-2`'s output.** If the replay perturbs the capture, it corrupts the
very audio L3 then reads — **a self-inflicted loop, not a collision between two independent arms.**
And the damage is **unattributable after the fact**: any cycle-loss anomaly in `FP-FLOOR-LIVE-2`
could no longer be separated from the replay, so **both** arms lose — the capture on validity, L3 on
provenance. ⇒ The causal risk runs one way (replay → capture); the *mutual* damage is in
**attribution**. Either way the bar stands unchanged, and it stands **regardless of measured CPU
headroom**, because it is not a performance claim.

### 1.3 ⚠️ BAR 2 — `U_clean ≥ 500` is a real risk on a short corpus, and it is checkable, not
assumable

ROW 0g (as re-expressed by A1.3 item 2) stops the arm if `U_clean = U_total − U[0] < 500`. The
`s17m` figure the spec sized against (`U_total ≈ 2,640`) came from a **four-day** corpus.
`FP-FLOOR-LIVE-2` is a single contiguous span of ~7–14 h.

🛑 **I am not predicting either way, and I am specifically not asserting the corpus is big enough.**
Cycle count favours it (a 13.6 h run is ~3,264 cycles against the 60-cycle leg the Developer's
identity check used); but unresolved lookups are **not** proportional to cycles — the callsign hash
table **saturates** as the run proceeds, so a station heard with a full callsign at hour 1 stops
generating unresolved lookups for the remaining 12 hours. The unresolved population is therefore
front-loaded and its size is genuinely uncertain.

⇒ **Evaluate ROW 0g mechanically and accept its answer.** If it fires, that is **instrument failure,
not a null** — the spec already says so, and it must not be softened into "L3 exposure is small".
The remedy would be extending the corpus, not lowering the floor.

### 1.4 ⚠️ What the substitution genuinely costs, stated so it is not discovered in the report

The primary reading is the **occupancy distribution over 4,096 codes**, whose null is uniformity. A
single-band, single-QTH, single-contiguous-span corpus has a different code-generating process from
a four-day multi-band one: fewer distinct stations, more repeats per station, and the saturation
effect above. **Uniformity may hold less well.**

🔴 **This is not a reason to refuse the substitution — it is the reason the occupancy check exists,
and that check was verified discriminating before the spec shipped (§4's z-table).** If
`|occ_obs − occ_exp| > 3·occ_sd`, the honest consequence is already pre-registered: **ROW 3,
escalate.** 🛑 **Do not average, do not pick the nearer row, do not re-cut the threshold, and do not
re-run on a different corpus to get a cleaner occupancy** — that last one would be exactly the
outcome-chosen corpus selection this amendment's timing exists to avoid.

### 1.5 Substitution, stated as the operative text

> **§4's corpus is replaced by:** the `FP-FLOOR-LIVE-2` cycle-audio archive, **the same contiguous
> span the `FP-FLOOR-LIVE-2` corpus itself analyses** (from `2026-09-08T19:36:45Z` to that arm's own
> stopping point, per its Amendment 3). Record the archive path and the exact cycle range in the
> report. **"Extend to `s20m`/`s80m` only if ROW 1 fires" is unchanged** and now reads as "extend to
> a second corpus only if ROW 1 fires".

⚠️ **Pin the span mechanically and once, before reading any count.** Using `FP-FLOOR-LIVE-2`'s own
already-pinned boundary is deliberate: it is a timestamp fixed for reasons unrelated to L3, which is
the strongest available guarantee that L3's corpus edges were not chosen by an L3 outcome.

---

## 2. Question 2 — the `20260049` binary: already on disk, already hash-verified

### 2.1 No rebuild. Both binaries exist and I verified both SHAs this session

| Leg | Path | SHA256 (`sha256sum`, verified 2026-09-08 20:2xZ) | Matches pin? |
|---|---|---|---|
| ROW 0e control, shim `20260049` | `artefacts/2026-09-03-f001-l3-shim-rebuild/libft8-20260049-prechange.dll` | `ce02c7ba10e216349c3cc6d2460a6106379a4593bb730c807dbe8128ecca153e` | ✅ = the README's pin, = the SHA QA quoted |
| ROW 0a subject, shim `20260050` | `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` on `origin/main`@`cf21ac5` | `6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c` | ✅ = the Developer manifest's pin |

✅ **`main` today still ships the exact `20260050` binary ROW 0a pins.** Nothing has rebuilt it in
the five days since. ROW 0a is satisfiable with no build step at all.

🔴 **Assert both SHAs in-run and print them (HK-021(p)); do not infer either from
`ft8_lib_version_check()`.** A version integer identifies nothing — that is a standing project rule,
and it bites hardest here because the two legs are *meant* to differ only by an additive branch.

⚠️ **Rebuilding would have been the wrong answer, and it is worth saying why in case the artefact
ever goes missing.** A `20260049` rebuilt from today's tree would not be the `20260049` the pin
names. ROW 0e's claim is differential — *"the added `else if` does not perturb decoding"* — so the
control must be the export commit's **parent** (`ac6150d^`), not a binary that merely carries the
label `20260049`. The on-disk artefact is exactly that, preserved by the Developer for this purpose.

### 2.2 🔴 ROW 0e has already passed once — and you should still re-run it

The Developer session discharged the ROW 0e-equivalent check at build time
(`artefacts/2026-09-03-f001-l3-shim-rebuild/README.md`, task 6.1):

```
cycles=60 decodes_pre=647 decodes_post=647 diffs=0
RESULT: BYTE-IDENTICAL -- ROW 0e-equivalent PASSES
```

on corpus `artefacts/20260808_live_run_1154-8080-17m/owsfz/wav`.

**That does not discharge ROW 0e for this arm** (HK-022 — a green result answers what it was pointed
at): it was a different corpus, and the script is self-described as *"ad hoc … not a permanent QA
instrument"*. ROW 0e is the row the spec singles out as the only one that catches the error the
others cannot. **Re-run it on the analysed leg.** It costs one extra replay pass over WAVs you are
already replaying.

✅ **Reuse `l3_row0e_identity_check.py`'s mechanics** (it exists, it worked, it mirrors
`g4_h12_suppression_replay.py`'s comparison). 🔴 **Byte-identity must be MECHANICALLY DIFFED and the
diff count printed — never asserted** (standing rule).

⚠️ **And note what a FAIL would now mean.** With a prior clean pass on 647 decodes, a ROW 0e failure
on the new corpus would not read as "the export perturbs decoding"; it would read as **corpus- or
environment-dependent non-determinism**, which is a far more serious finding than a STOP. Report it
as such rather than filing it as a routine ROW 0 stop.

---

## 3. Question 3 — tooling: AUTHORISED, with four conditions

QA is right that no HK-011 gate applies: `qa/` Python driving the native library by `ctypes` is QA's
own instrument, and §7 step 3 explicitly anticipated the `g3` extension. Build both.

1. 🛑 **Do not touch `g4_h12_suppression_replay.py`.** Unchanged from §7 step 3. It is the Option A
   instrument and other arms read it.
2. 🔴 **The `g3` extension must be additive and conditional, on the pattern of its existing
   `h12_by_code` bind — and that must be MECHANICALLY DIFFED, not asserted.** Run `g3` on a fixed
   corpus before and after the extension and show the outputs are byte-identical. `g3` has existing
   callers; an extension that silently changes its output would confound them, and "it's only an
   added bind" is precisely the assumption ROW 0e exists to refuse to make.
3. **The gate-evaluation script ships the predicates as code and prints every row's evaluation,
   then the first firing verdict** (§5, HK-021(r)). Print `U_total`, `U[0]`, `U_clean`, `U149`,
   `E_uniform`, `occ_obs`, `occ_exp`, `occ_sd`, and `out_of_range` **always**, on every path,
   including a ROW 0 stop.
4. 🔴 **The gate-evaluation script must not be validated by the code that generates its inputs**
   (HK-022's drafting question). See §4 — one row already fails this test, and it is the one I
   wrote.

---

## 4. 🔴 ROW 0d is WITHDRAWN — unevaluable on the shipped ABI

### 4.1 The defect

**ROW 0d as written:** `sum(unresolved_by_code) ≠ U_total` ⇒ STOP.

I read the shipped export and the counters behind it. `ft8_get_h12_unresolved_by_code` returns
**only the 4,096-row table** (its `int` return is `H12_CODE_SPACE`/`-1`, a status, not a total), and
there is **no `g_h12_unresolved` scalar** — the shim's scalar counters are `g_h12_displaying`,
`g_h12_ambiguous`, `g_h12_divergent`, `g_h12_suppressed`, all of which belong to the **resolved**
branch.

⇒ **`U_total` has no independent source. Its only possible definition is `sum(table)`** — at which
point ROW 0d reads `sum(table) ≠ sum(table)` and is **green by construction**. Generator and
consumer are the same code. It would have passed on every run, forever, while detecting nothing.

🔴 **This is my drafting fault, not QA's, not the Developer's, and not the PO ruling's.** §5 asks
"what error could this row NOT detect?" of ROW 0 rows and I did not ask it of my own ROW 0d.

### 4.2 The ruling

> **ROW 0d is withdrawn.** It is not renumbered and not replaced in place; ROW 0a/0b/0c/0e/0f/0g are
> unchanged and keep their identifiers. **`U_total` is hereby DEFINED as `sum(unresolved_by_code)`**
> and must be reported as such — never described as an independently measured total.

**Two mechanical checks that ARE available take over part of its job.** Both were verified against
`ft8_shim.c` this session, not assumed:

- **0d′ — `sum(by_code_displaying) == ft8_get_h12_displaying_count()`.** A genuine table-vs-scalar
  reconciliation on the **sibling** table, built at the same emission site (`ft8_shim.c:1690-1704`)
  with the same defensive mask and the same shared `out_of_range` counter. It proves the shared
  emission machinery reconciles. **It does not prove the L3 table's own accumulation.**
- **0d″ — `sum(by_code_ambiguous) == ft8_get_h12_suppressed_count()`.** Exact by construction:
  `tls_h12_suppressed = (tls_h12_multiplicity >= 2)` (`:821`) and both counters increment on that
  identical predicate on adjacent lines (`:1680`, `:1691`). **This discharges A1.3 item 4's intent**
  — confirming the suppressed subset lands in the *other* branch and is excluded from L3's
  population by construction.

**Either fails ⇒ STOP**, same consequence ROW 0d carried.

### 4.3 🛑 What is now uncovered — stated plainly, not dressed up

**A mis-accumulation confined to `g_h12_unresolved_by_code` itself is caught by 0d′ and 0d″ not at
all.** They exercise the sibling table and the sibling predicate. The only remaining check that
touches the L3 table from an **independent direction** is:

> **ROW 0b** — `U_total <` (count of `<...>` renderings parsed from the same leg's emitted lines)
> ⇒ STOP.

ROW 0b compares a native counter against a quantity derived from **decode text**, by a path sharing
no code with the counter. **It is now the load-bearing reconciliation for this arm and should be
reported as such.** ⚠️ It is one-sided by design: `U_total >` renderings is expected and correct
(lookups exceed renderings), so 0b catches an **under**-count and is blind to an over-count. That
blindness is real and I am not closing it.

### 4.4 A1.3 item 4 is likewise unevaluable as written, and is superseded by 0d″

A1.3 item 4 requires *"the difference between the ungated unresolved count and the gated one"*.
**No ungated unresolved count exists** — per A1.1's own ruling the emission-site `else if` **is** the
gate, so the export exposes the gated population only and the difference is not computable. §6.1
item 3's original form (compare against the historical `847`) was already replaced by A1.3 item 4;
**A1.3 item 4 is now itself replaced by 0d″ above**, which is same-run, mechanical, and evaluable.
A1.3 item 4's own caveat still stands verbatim: the equality is near-tautological, catches a
mis-wired branch and nothing else, and is **blind to padding contamination** — which is why A1.3
item 2's `U_clean = U_total − U[0]` remains separate and non-redundant.

### 4.5 One decision that is the PO's, stated once

The alternative to withdrawing ROW 0d is **adding an `ft8_get_h12_unresolved_count()` scalar** so the
reconciliation becomes real. **My recommendation is not to build it,** and I will not raise it
again: it costs a shim bump to `20260051` (breaking ROW 0a's pin), a second Developer session and
Captain diff review, and a repeat of the `AwgnFpReplayTests` pinned-SHA fallout the last bump caused
— all to harden a validity row on an arm whose result is **COST-ONLY and cannot license shipping L3
either way**. Disproportionate. 🛑 **The ruling is the PO's; if they want the scalar, this arm waits.**

### 4.6 ✅ PO RULING, 2026-09-08 ~21:0xZ — NO SCALAR. Binding on this arm.

> **PO:** *"no scalar, skip it. we'll evaluate later"*

**The scalar is not built. ROW 0d stays withdrawn, `20260050` stays pinned in ROW 0a, and the arm
proceeds exactly as §6 sets out** — nothing is waiting on a build, and QA is unblocked on everything
except §1.2's capture bar.

⚠️ **"We'll evaluate later" is recorded literally: DECLINED FOR NOW, not closed.** This is **not** a
standing prohibition and re-proposing the scalar later is legitimate — unlike the genuinely closed
arms in `closed-arms-prohibitions.md`. **Do not harden this into "the scalar was ruled out."**

🔴 **What must travel with any later evaluation, so it is not re-derived from scratch:** the scalar's
only job was to make ROW 0d a real reconciliation. Skipping it means **§4.3's uncovered gap is now a
PERMANENT property of this arm's result** — a mis-accumulation confined to
`g_h12_unresolved_by_code` is caught only partially, by one-sided ROW 0b. 🛑 **That limitation must
appear in the report's own statement of validity, not only here.** A reader who sees ROW 0b pass
must not be able to infer a table-level reconciliation that was never performed.

---

## 5. What this amendment does NOT change

- 🛑 **COST-ONLY (§0.3, §8) is untouched.** Efficacy remains structurally unmeasurable — every
  corpus we hold, tonight's included, has **zero `Tx` lines**, so no station has ever called us.
  **A cost-only result is still not a verdict on L3**, and the report's headline must carry that
  constraint verbatim. Substituting a fresher corpus does **not** weaken this bar; it does not touch
  it.
- 🛑 A1.1's gate — `tls_h12_lookup_performed && !tls_h12_resolved` — PO-ratified, unchanged.
- 🛑 A1.3's `U_clean = U_total − U[0]` padding rule, and ROW 0g's floor read on `U_clean`, unchanged.
- 🛑 `20260050` stays pinned in ROW 0a, now with its SHA re-verified against `main` (§2.1).
- 🛑 "row 149 = 0" from `ft8_get_h12_by_code` remains **out of scope for L3 forever** (§0.1, HK-026).
- 🛑 `847` remains uncitable as a user-facing ambiguity figure (user-facing is `250`).
- 🛑 §7's blind predictions stand for ROW 1–3. The `U_total ≈ 2,600–3,600` expectation was already
  withdrawn-or-restated by A1.4 and is **further void on a substituted corpus — do not score it.**
- 🛑 This arm still licenses **no** `src/` behaviour change (HK-011). Nothing here needs a build.

---

## 6. What QA does, in order — replacing §7

1. **Wait for `FP-FLOOR-LIVE-2` to stop and its daemon to be down** (§1.2). Do not start before.
2. Pin the archive path and cycle span from `FP-FLOOR-LIVE-2`'s own Amendment 3 boundary (§1.5).
3. Extend `g3_h12_replay.py`; **byte-diff `g3`'s output before/after the extension** (§3 cond. 2).
4. Write the §5 gate-evaluation script, predicates as code, all rows printed (§3 cond. 3).
5. Replay the leg on **both** pinned binaries (§2.1) for ROW 0e; print the diff count (§2.2).
6. Evaluate ROW 0a, 0b, 0c, **0d′, 0d″**, 0e, 0f, 0g — **0d is withdrawn** (§4) — then ROW 1/2/3.
7. Report per HK-001. **Headline carries §0.3's COST-ONLY constraint verbatim**, and states that
   ROW 0b is this arm's load-bearing reconciliation and what it is blind to (§4.3).

🛑 **HK-025 remains available in full.** If QA judges any row here non-mechanical — including the
ones I have just written — it may **refuse to run** and say which row and why. No Architect
agreement needed. Given that I have just withdrawn one of my own rows for being decorative, that
invitation is meant literally.
