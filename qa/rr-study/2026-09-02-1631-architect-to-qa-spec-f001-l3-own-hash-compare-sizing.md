# `F-001` L3 — the own-hash compare: exposure sizing, pre-registered

**Author:** Architect, 2026-09-02 (16:31 UTC, `date -u`, per HK-017).
**For:** QA. **Ordered by:** the PO ("spec L3 for QA", 2026-09-02).
**Status:** docs-only, committed locally, **not pushed** (HK-014).
**Base:** `main`@`3b52608`, shim `20260049`.

---

## 0. Headline — read this before the spec body

**L3 cannot be sized with any export that exists today, and the obvious way to try is wrong.**
This section exists because I nearly specced that wrong way.

### 0.1 The trap I fell into, stated so QA does not repeat it

`ft8_get_h12_by_code()` (shim `20260048`) returns a 4096-row per-code breakdown indexed by the
12-bit code itself. Our own callsign's code is **`n12 = 149`** (`PD2FZ`; derivation in Sec.2). Eight
JSON artefacts on disk already carry that table. Reading row 149 out of all eight gives:

| Artefact | `displaying[149]` | `ambiguous[149]` | `divergent[149]` | corpus totals |
|---|---:|---:|---:|---|
| `2026-08-30-…/pilot_inst_run{1,2}.json` | 0 | 0 | 0 | 9 / 1 / 1 |
| `2026-08-30-…/s17m_inst_run{1,2}.json` | 0 | 0 | 0 | 1582 / 847 / 652 |
| `2026-08-31-…/s20m_inst.json` | 0 | 0 | 0 | 1139 / 506 / 390 |
| `2026-08-31-…/s80m_inst.json` | 0 | 0 | 0 | 324 / 79 / 44 |
| `2026-09-01-…/pilot_base_{fresh,slice}.json` | 0 | 0 | 0 | 61 / 24 / 24 · 1582 / 847 / 652 |

**Zero everywhere, on every band, against 3,045 displaying events.** That looks like a finished
answer: "L3 has no exposure, close it."

🔴 **It is not an answer. It measures the wrong population.** The emission site
(`ft8_shim.c:1650`) increments the by-code table under

```c
if (tls_h12_lookup_performed && tls_h12_resolved) {   /* <-- tls_h12_resolved REQUIRED */
    ...
    g_h12_by_code_displaying[c]++;
```

`ft8_get_h12_by_code` therefore counts **only lookups that RESOLVED**. **L3's entire population is
the lookups that did NOT resolve** — the `<...>` renderings, ~2,640 in our log per the R5 drafting
probe. That population is **structurally invisible** to this instrument: its response there is not
"small", it is **zero by construction**.

🛑 **Quoting "row 149 = 0" as L3's exposure is a textbook HK-026 violation** — using an instrument's
output to bound a region inside that instrument's own blind spot. The zero is real, it is correctly
measured, and it is **irrelevant to L3**. Do not cite it in any L3 context.

### 0.2 What the zero *does* legitimately say

Only this: **no emitted decode in any corpus we hold ever carried a *resolved* 12-bit hash equal to
our code.** That is a true statement about the L2 population (which shipped), not the L3 one. It is
also unsurprising for a second, independent reason — both corpus logs have **zero `Tx` lines**, so
no station was ever in a position to address us.

### 0.3 The hard constraint that outlives this spec

**L3's BENEFIT is unmeasurable on every artefact we hold, and no amount of instrumentation fixes
it.** The benefit is "we correctly answer a station calling us whose full callsign we have not yet
heard." With zero `Tx` lines, no station ever called us. This is the **wrong KIND of corpus**, not a
small sample — the same structural bar the R5 spec placed on route 5's efficacy (Sec.0.3 there).

⇒ **This arm can size only L3's COST.** 🛑 **A cost-only result must NEVER be read as "L3 is
unfavourable."** It bounds one side of a two-sided decision. Say so in the report's own headline.

---

## 1. What L3 is, and the one thing that makes it different from L1/L2

Shipped already (PR #138, `main`@`47a781c`, shim `20260049`):

- **L1** — `TryParseMessage` required exactly 3 tokens, so a 2-token Type-4 (`<CALL> RR73`) never
  parsed.
- **L2** — a *correctly resolved* hash renders bracket-wrapped (`message.c:604-611` calls
  `add_brackets()` unconditionally), and `dest.Equals(ours)` compared `<PD2FZ>` against `PD2FZ` ⇒
  false even on a perfect resolution.

**L3** is the remaining layer: when the hash does **not** resolve — we have never heard that
station's full callsign, so `message.c` renders `<...>` — compare the **raw 12-bit code** against
our own (`n12 == 149`) and treat a match as "addressed to us."

🔴 **The structural difference, and it is the whole risk:** L1 and L2 act on a callsign the decoder
has already **positively identified**. L3 acts on a callsign the decoder has explicitly **failed to
identify**, using a 12-bit code with 4,096 values shared across 11,233 distinct calls heard. L1/L2
made a correct comparison work. **L3 manufactures an identification the decoder declined to make.**

---

## 2. Our own code — pinned, and cross-checked against the project's own implementation

The hash is `save_callsign` (`native/ft8_lib_vendor/ft8/message.c:557-585`):

```
n58 = base-38 over FT8_CHAR_TABLE_ALPHANUM_SPACE_SLASH (" 0123456789A..Z/", text.h:59),
      padded with index 0 (space) to 11 chars
n22 = ((47055833459 * n58) >> (64 - 22)) & 0x3FFFFF
n12 = n22 >> 10
```

| Callsign | `n58`-derived `n22` | **`n12`** | `n10` |
|---|---:|---:|---:|
| `PD2FZ` | 153 456 | **149** | 37 |

✅ **Cross-checked, not round-tripped against my own generator (HK-022):** computed independently by
this spec's own implementation and by the project's committed
`qa/rr-study/f001-d3-arm1/common_arm1.py` (`n22_of`/`n12_of`). **Both return `n22=153456`,
`n12=149`.** QA must re-derive it a third time from the DLL in-run (ROW 0f) rather than trusting
either.

⚠️ `PD2FZ` is a **named NFR-021 exception** (our own call), so it is citable in VCS. No other real
callsign appears in this spec.

---

## 3. What must be built before anything can be measured

**There is no export that reveals the code of an UNRESOLVED 12-bit lookup.** `tls_h12_code` is set
unconditionally in `cb_lookup_hash`'s 12-bit branch (`ft8_shim.c:810`) — the value exists — but it is
read only inside the `tls_h12_resolved` guard and is **never exported**.

⇒ **L3 sizing requires a new native export.** Proposed, MEASURE-ONLY:

```
ft8_get_h12_unresolved_by_code(int* counts, int capacity, int* out_of_range) -> int
```

a second fixed 4096-row static table incremented in the **complement** of the existing guard —
`tls_h12_lookup_performed && !tls_h12_resolved` — at the same emission site, with the same
defensive mask and the same out-of-range violation counter. **`FT8_SHIM_VERSION` → `20260050`.**

This is deliberately the **exact shape of SUP-B Amendment 2** (`20260048`), which did precisely this
for the resolved branch. Nothing about `hash_table_lookup`, `hash_table_add`, `cb_lookup_hash`'s
return/output values, the struct layout, or any existing export changes.

🔴 **HK-011 IN FULL. This is `src/` + `native/` work.** Per HK-015, **QA authors the
`dev-tasks/*.md`** — it is not mine to write — and **stops**. A separate **Developer** session runs
`opsx:apply`; the **Captain** reviews the diff. 🛑 **HK-021(p): no binary ⇒ no claim about a fixed
build.** The SHA256 of the built DLL is pinned in the dev-task and asserted in-run (ROW 0a).

🛑 **HK-025 is available.** If QA judges any gate below non-mechanical, it may **refuse to run** and
say which row and why. No Architect agreement needed.

---

## 4. The measurement

**Corpus:** the existing `s17m` replay leg (the largest, 1,582 displaying / 847 ambiguous). **No
capture run. No live transmission. Replay only.** Extend to `s20m`/`s80m` only if ROW 1 fires.

**Definitions, fixed here:**

- `U_total` — total 12-bit lookups that did **not** resolve, summed over the new table.
- `U149` — `unresolved_by_code[149]`, i.e. the count on **our own** code.
- `E_uniform` = `U_total / 4096` — expected per-code count under uniformity.
- `occ_obs` — number of distinct codes with ≥1 unresolved lookup.
- `occ_exp`, `occ_sd` — mean and sd of that occupancy under Poisson(λ = `E_uniform`), computed as
  `4096·(1 − e^(−λ))` and `sqrt(4096·e^(−λ)·(1 − e^(−λ)))`.

🔴 **`U149` alone is UNDERPOWERED BY CONSTRUCTION and must not carry the verdict on its own
(HK-021(u), base rate).** With `U_total ≈ 2,640`, `E_uniform ≈ 0.64` — **under one expected event on
our code across a four-day corpus.** A `U149 = 0` would be HK-021(j) all over again: not evidence of
absence. **That is exactly why the primary reading is the DISTRIBUTION over all 4,096 codes
(n ≈ 2,640), from which our code's rate is derived — not the single cell.**

✅ **The occupancy check was verified DISCRIMINATING before this spec shipped** — I asked HK-022's
drafting question ("what error could this row NOT detect?") and computed the answer rather than
assuming it:

| `U_total` | λ = `E_uniform` | `occ_exp` | `occ_sd` | ±3σ band | band width |
|---:|---:|---:|---:|---|---:|
| 2 640 (R5's figure) | 0.644 | 1 946.0 | 32.0 | [1 850, 2 042] | 4.7% of 4 096 |
| 3 000 | 0.732 | 2 126.9 | 32.0 | [2 031, 2 223] | 4.7% |
| 3 487 | 0.851 | 2 347.6 | 31.7 | [2 253, 2 443] | 4.6% |
| 500 (ROW 0g floor) | 0.122 | 470.7 | 20.4 | [409, 532] | 3.0% |

The band is **tight, not permissive**: a merely 10% concentration of codes gives **z = −6.1** and
fires; heavy clustering onto ~200 codes gives **z = −54.6**. ⇒ **The check can fail, and would fail
on exactly the non-uniformity that would invalidate deriving our code's rate from the base rate.**
It is load-bearing, not decoration.

⚠️ **UNIT DISCIPLINE, and this has already bitten this project once.** `U_total` counts **lookups**.
The `<...>` count parsed from a log counts **renderings**. These are different quantities — the
`847`-ambiguous-lookups vs `250`-user-facing-lines contamination is the standing example. 🛑 **Never
equate them, and never report `U_total` as a user-facing figure.**

---

## 5. Pre-registered gate

Rows are evaluated **in strict order**; the first whose predicate holds is the verdict. Ship the
predicate as code (HK-021(r)) and print each row's evaluation.

### ROW 0 — instrument validity (any one fires ⇒ STOP, no reading)

| Row | Predicate | Consequence |
|---|---|---|
| **0a** | Built DLL's `ft8_lib_version_check()` ≠ `20260050`, **or** its SHA256 ≠ the dev-task's pinned manifest value | Wrong binary. **STOP.** |
| **0b** | `U_total` < (count of `<...>` renderings parsed from the same leg's emitted lines) | Counter miswired — lookups can never be fewer than renderings. **STOP.** ⚠️ The converse is NOT a failure: `U_total` **>** renderings is expected and correct. |
| **0c** | `out_of_range` ≠ 0 | A code was masked out of bounds; cluster identity is scrambled even though the sum still reconciles. **STOP.** |
| **0d** | `sum(unresolved_by_code) ≠ U_total` | Table/scalar disagree. **STOP.** |
| **0e** | Emitted decode lines on `20260050` are **not byte-identical** to those on `20260049`, same audio, same seed | The "MEASURE-ONLY" claim is **false** and every downstream number is confounded. **STOP.** |
| **0f** | `n12` re-derived in-run from the DLL for `PD2FZ` ≠ **149** | The whole measurement is pointed at the wrong cell. **STOP.** |
| **0g** | `U_total` < 500 | Too few unresolved lookups for a distributional reading. **Instrument failure, NOT a null.** **STOP.** |

🔴 **0e is the one that matters most and the only one that catches the error the others cannot**
(HK-022): every other row passes whether or not the new counter perturbed decoding.

### ROW 1 — our code is a hot bucket

**`U149 ≥ 5` AND `U149 ≥ 5 × E_uniform`**
⇒ Our code attracts unresolved lookups **materially above** the uniform rate. **L3's false-fire cost
is worse than the uniform model predicts, and every false fire is a harm-2** (unsolicited Tx to a
station that did not call us). **L3 MUST NOT ship without Sec.8.4-style containment.** Extend to
`s20m`/`s80m` to confirm the concentration replicates across bands.

### ROW 2 — cost is real but sub-event-scale

**`U149 ≤ 2` AND `|occ_obs − occ_exp| ≤ 3 · occ_sd`**
⇒ Unresolved codes are consistent with uniform, and our code's exposure is **≤ 2 false fires per
four-day corpus**, point estimate `E_uniform ≈ 0.6–0.9`.
🔴 **THE CONSEQUENCE, STATED AS AN ASSERTION AND ON BOTH BRANCHES (HK-021(t)):** this row **does not
license building L3**. It says the cost is small; the benefit remains **structurally unmeasurable**
(Sec.0.3). **The decision passes to the PO as a judgement call that this measurement cannot make,
and the report must say so in those words rather than implying a green light.**

### ROW 3 — anything else

`3 ≤ U149 ≤ 4`, or `U149 ≤ 2` with the occupancy check failing, or `U149 ≥ 5` without the ×5 margin.
⇒ **Escalate. Do not average, do not pick the nearer row, do not re-cut the threshold.**

---

## 6. The conflict this arm must surface — and it is not a measurement question

🔴 **L3 as specified would partially UNDO the Option A suppression that shipped nine days ago.**

Option A (`78713b8`, shim `20260049`) made `cb_lookup_hash` return "not found" whenever a 12-bit
probe chain holds ≥2 matching entries — **847 lookups on `s17m`** — precisely because an ambiguous
12-bit match is **unsafe to act on**. Those decodes now render `<...>`, which puts them **into L3's
population**.

An own-hash compare on the raw `n12` **cannot distinguish** an unresolved-because-unknown code from
an unresolved-because-**deliberately-suppressed-as-ambiguous** one. It would fire on both. **On the
suppressed subset it would re-enable exactly the identification the PO ruled unsafe**, and convert
it from harm 1 (wrong name shown) to harm 2 (unsolicited transmission) — the same escalation the
Sec.8 correction already recorded for L2.

⇒ **A design question for the PO, ahead of any build, that no row above answers:** should L3's
compare be **gated to exclude the suppressed subset** (i.e. fire only when `tls_h12_multiplicity
== 1`)? My recommendation is **yes** — it costs one already-computed thread-local, it preserves
Option A's ruling intact, and without it L3 and Option A are in direct contradiction on the same
decodes. 🛑 **I am stating this once, per my role; the ruling is the PO's.**

### 6.1 ✅ PO RULING, 2026-09-02 — GATED. Binding on this spec and everything downstream.

**The PO has ruled: L3's compare is gated on `tls_h12_multiplicity == 1`.** The recommendation
above is now a requirement, not a preference. Recorded here rather than only on the board so the
constraint travels with the spec (HK-024).

Consequences QA must carry into the dev-task, stated so they are not re-litigated at build time:

1. **The new measure-only export `ft8_get_h12_unresolved_by_code` (shim `20260050`) must itself
   honour the gate** — it counts an unresolved lookup **only** when that lookup's own
   `tls_h12_multiplicity == 1`. Gating downstream in analysis is **not** equivalent: the export
   would otherwise carry the suppressed population across the ABI, which is the exposure the ruling
   exists to prevent.
2. 🔴 **The gate SHRINKS L3's population, and the spec's power arithmetic must be re-derived, not
   inherited.** §5's sizing was computed against the ungated ~2,640 unresolved lookups. The gated
   population is that set minus the ambiguous subset (**847 lookups on `s17m`**, the only corpus
   where it has been counted). `U149` was **already** underpowered by construction at the ungated N
   (`E_uniform ≈ 0.64`); it is strictly worse now. **The 4,096-code distribution remains the primary
   reading and the single cell remains unreadable** — the ruling does not change that, it deepens
   it.
3. **ROW 0 gains a precondition:** the gated and ungated unresolved counts must both be reported
   for the same run, and their difference must be **non-zero and consistent with the corpus's known
   ambiguous count**. A gated count equal to the ungated one means the gate is not wired, and every
   row below it is void — a green reading from an unwired gate is the exact HK-022 failure this
   check exists to catch.
4. 🛑 Unchanged by the ruling: **efficacy remains structurally unmeasurable** (zero `Tx` lines in
   every corpus we hold). This arm sizes **COST ONLY**, and a cost-only result must never be read as
   "L3 is unfavourable."

---

## 7. What QA does, in order

1. **Author the dev-task** for `ft8_get_h12_unresolved_by_code` (HK-015 — QA's document, not mine),
   pinning the shim bump `20260050` and the DLL SHA256 manifest. **Then STOP** (HK-011).
2. Await the Developer session + Captain diff review. **Do not build it yourself.**
3. On a signed-off binary: extend `g3_h12_replay.py`'s existing conditional `h12_by_code` bind —
   **do not edit `g4`**, which is the Option A instrument — and replay `s17m` on **both**
   `20260049` and `20260050` for ROW 0e.
4. Evaluate ROW 0 in full, print every row, then the first firing verdict.
5. Report per HK-001. **Headline must carry Sec.0.3's constraint verbatim: this sizes COST ONLY, and
   a cost-only result is not a verdict on L3.**

**Blind predictions — 🛑 NOTHING GATES ON THESE (HK-021(v), stated at my own expectation):**
P(ROW 2) ≈ 0.65 · P(ROW 3) ≈ 0.20 · P(ROW 1) ≈ 0.10 · P(any ROW 0) ≈ 0.05.
I expect `U_total` ≈ 2,600–3,600 (the R5 probe's 2,640, plus the Option A suppressed lookups now
joining the unresolved population) and `U149` ∈ {0, 1}.

---

## 8. Standing bars this arm does not lift

- 🛑 Zero `Tx` lines ⇒ **efficacy is unmeasurable in every corpus we hold.** No row changes that.
- 🛑 `g_h12_ambiguous` (847) is **lookups**, contaminated as a user-facing sizing stat; user-facing
  ambiguity is **250**. Never cite 847 as a user-facing number.
- 🛑 "row 149 = 0" from `ft8_get_h12_by_code` is **out of scope for L3 forever** (Sec.0.1).
- 🛑 This arm licenses **no** `src/` behaviour change. The new export is MEASURE-ONLY; shipping L3
  itself is a separate proposal with its own pre-registration.
