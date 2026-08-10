# ARCHITECT → QA — spec X3: does sub-lattice placement error cost more in a CROWDED cycle?

**Author:** Architect, 2026-08-10 (18:08 UTC, `date -u`, HK-017).
**For:** QA. **Authorised by:** the Captain, 2026-08-10, in answer to the X2 route memo (ruling 1 of 3).
**Depends on:** P3 (`2026-08-09-0129-…-spec-p2-pcm-scale-and-p3-sublattice-shift-union.md`, harness
`p3_shift_union.py`) and X2 (`2026-08-10-1731-qa-to-architect-x2-…-results.md`).
**Costs:** decoder replay only. **No `src/` change, no rebuild, no capture, no Developer session.**

---

## 0. The question, in one line

P3 measured that sub-lattice placement costs **`S_all` = 4.27 pp** of real `REF` decodes, pooled.
X2 measured that crowding costs **`F_std` = 17.22 pp**, at matched SNR. **X3 asks whether they are
the same effect** — i.e. whether the recall the lattice costs us is concentrated in crowded cycles.

### 0.1 Why this is the arm worth spending decoder time on

`ft8_extract_symbol` is a max-log over 8 **magnitude** bins at the candidate's *quantised* grid
position — non-coherent, single-symbol. Two mechanisms plausibly compound:

1. a neighbour's energy adds into your tone bins, and with no phase information nothing separates
   "my tone" from "my tone + somebody else's";
2. an extraction window mis-placed by up to ±1.5625 Hz / ±0.04 s **straddles** — collecting less of
   your own signal and more of the neighbour's.

If (2) is material, refined placement attacks the crowding term *and* the lattice term with one
change, and it does so **without characterising the interference at all** — which matters, because
the direct mechanism route is X4's problem, not this arm's.

🛑 **This compounding is an Architect INFERENCE and it is DIRECTIONAL. My directional calls are
0 for 2** (`S_freq` vs `S_time` reversed; the P2 scale curve's shape). Per the standing rule the
gate below is a **magnitude bound in both directions** and turns on no directional prediction of
mine. A result in either direction is readable.

### 0.2 What I ruled out before writing this, so QA does not re-derive it

🛑 **The cheap observational version of this question — T1's `G` stratified by density — is
UNDERPOWERED BY CONSTRUCTION and must not be proposed.** Computed, not estimated: 20m `G` carries a
frequency-clustered SE of **1.22 pp**, so splitting it in half gives ~1.73 pp per half and ~2.44 pp
on the difference ⇒ a **>7.3 pp** interaction would be needed to fire at 3σ, against a base `G` of
only **3.16 pp**. The observational route cannot answer this at any runtime (T2a's structural
ceiling binds it further). **That is the entire justification for spending decoder replay instead.**

P3's interventional design is ~15× tighter (`SE(S_all)` = **0.080 pp**) because it is a *paired*
within-file comparison rather than a between-decode contrast. That is what makes X3 answerable.

---

## 1. Design

Re-run P3's five-leg shift-union (base, ±1.0417 Hz, ±0.0267 s) **unchanged**, then partition the
outcome by **X2's density regimes, fixed globally and identically** (HK-021(g)):

```
FLOOR   density <= 5
MID     density 6-13
OVERLAP density 14-26
```

Density is per-cycle `REF` decode count, defined exactly as X2 defines it. Reuse
`x2_density_floor.py`'s regime assignment; do not re-derive it.

**Primary metric**

```
I_20m = S_all(OVERLAP, 20m) - S_all(MID, 20m)
```

**Replication metric** (the true floor regime, reachable only on 80m)

```
I_80m = S_all(OVERLAP, 80m) - S_all(FLOOR, 80m)
```

`S_all` keeps P3's definition exactly: `REF` decodes the union recovers that the base leg misses,
as a percentage of `REF` **within that regime**. Frequency-clustered bootstrap, 1 000 draws, fixed
seed `20260810`, paired (resample clusters once per draw, recompute both `S_all` on the same
clusters — P1a's lesson).

### 1.1 Why 20m is primary and 80m is replication — the reverse of X2

X2's headline came from 80m because only 80m reaches the FLOOR. **X3 inverts that**, because X3's
precision is set by *frequency clusters*, not by rows, and 80m has only ~907 of them against 20m's
30 513. Scoping from P3's published cluster structure (1/√clusters):

| leg | contrast | scoped SE | 3σ detectable |
|---|---|---:|---:|
| **20m (primary)** | MID − OVERLAP | ~0.18 pp | **~0.6 pp** |
| 80m (replication) | FLOOR − OVERLAP | ~0.92 pp | ~2.8 pp |

⚠️ **These are SCOPING figures, not measurements** — they scale P3's pooled SE by assumed cluster
fractions. They are why ROW 0e below computes the real thing **before** any decoder time is spent.

---

## 2. ROW 0 — void conditions, in strict order

Evaluate in order; the first that fires ends the arm.

| row | check | bar | consequence |
|---|---|---|---|
| **0a** | DLL identity pinned to P3's | SHA256 == `39aa1031ad63fd7c882ae9093a3d6c4d681f1c45e2a4f3b4336ff6c3f45e0aba` | VOID — a different binary is not a comparison with P3 |
| **0b** | shim version asserted at startup | `ft8_lib_version_check()` recorded in the result JSON | VOID |
| **0c** | `REF` reproduces | 20m `REF` == **69 222** exactly, through the shared T1 loader | VOID — the denominator drifted |
| **0d** | regime populations | every regime used carries ≥ 300 `REF` rows **and** ≥ 250 distinct frequency clusters | that leg is **UNDERPOWERED**, reported as an instrument limitation, **never as a null** |
| **0e** | 🔴 **pre-flight power, computed BEFORE the decoder runs** | scoped `SE(I)` ≤ 0.75 pp on the primary leg | if `SE(I)` > 0.75 pp the primary leg is **declared underpowered and NOT RUN** |
| **0f** | shift control, per P3 §ROW 0d | reported Δf within 0.25 Hz of applied 1.0417 Hz over ≥ 200 matched messages | VOID |
| **0g** | `native_av_count` == 0 | no access violations | VOID |

**ROW 0e is the point of this section and it is deliberately cheap.** Compute the clustered
`SE(I)` from the **base leg alone** (which P3 already establishes, and which costs one pass rather
than five) plus the real per-regime cluster counts. If it fails, we have spent minutes rather than
hours, and the honest answer is "this corpus cannot resolve it" — an instrument failure, not a null.

🛑 **Do not proceed to the four shifted legs until ROW 0e passes.** HK-021(i): check the structural
ceiling on effective n *before* asking for more data.

### 2.1 A discrepancy QA must resolve mechanically at ROW 0a/0b, not by reasoning

`src/OpenWSFZ.Ft8/Native/ft8_shim.h:297` on `main` reads `FT8_SHIM_VERSION 20260033`, and
`Ft8LibInterop.cs:224` reads `ExpectedShimVersion = 20260033` — but P2/P3/P1a all asserted shim
**20260035** against DLL SHA `39aa1031…`. Those cannot both describe `main`'s source tree.

**The SHA is the authority, not the version integer** (the board records that
`FT8_SHIM_VERSION` collides twice across five unmerged branches, so the integer identifies nothing).
Pin the SHA, record whatever version the DLL actually reports, and **flag the mismatch upward
rather than resolving it in session.** If the pinned DLL cannot be located, that is ROW 0a — stop.

---

## 3. The gate — mechanical, rows mutually exclusive, evaluated in order

```python
# I = S_all(OVERLAP) - S_all(MID or FLOOR);  lo/hi = paired clustered 95% CI on I
if se_I > 0.75:                      return "ROW 0e"   # underpowered, not a null
if I >= 2.0 and lo > 0:              return "ROW 1"    # lattice cost CONCENTRATES in crowded cycles
if abs(I) < 1.0 and se_I <= 0.40:    return "ROW 2"    # lattice cost is INDEPENDENT of crowding
if I <= -2.0 and hi < 0:             return "ROW 3"    # REVERSED - lattice costs MORE at the floor
return "ROW 4"                                          # inconclusive
```

**Consequences, pre-committed now, before any number exists:**

- **ROW 1** ⇒ placement error and crowding compound. **Sync refinement inside the decoder becomes
  the leading D-001 treatment candidate**, and is escalated to the Captain as a Developer-session
  recommendation with X3's number attached. It does **not** license a specific implementation
  (OSR 2→4 remains separately unproven — P3's guard, restated at §5 below).
- **ROW 2** ⇒ the two terms are **independent**. The lattice costs a flat ~4 pp everywhere and
  crowding's 17 pp is carried by something else. **Sync refinement is demoted to a modest,
  standalone recall improvement**, and X4 (spectral locality) becomes the live mechanism route.
- **ROW 3** ⇒ genuinely surprising and I have no mechanism for it. **Report and stop**; it earns a
  fresh pre-registration, not an in-session interpretation.
- **ROW 4** ⇒ no reading. Do not editorialise on the point estimate.

🛑 **No row licenses an `src/` change, a parameter value, or a capture run.** ROW 1's consequence is
a *recommendation to the Captain*, which is a different object (HK-011).

---

## 4. Secondary quantities — reported, never gating

1. **`X_guard` by regime.** P3's union manufactured 89.7% junk pooled. Whether that junk
   concentrates in crowded cycles is directly relevant to the open FP question and costs nothing
   extra to compute. **Report it; no row turns on it.**
2. **`S_freq` and `S_time` by regime.** P3 found `S_time` (3.01) > `S_freq` (2.41) pooled. Whether
   that ordering holds within regime is descriptive. 🛑 **Do not gate on which is larger** — that is
   exactly the directional call I got wrong.
3. Per-regime `n`, cluster counts, and raw base/union decode counts, so the arm can be re-read
   later without re-running it.

---

## 5. Citation limits, pre-committed

- 🔴 **`I` is a within-band, within-corpus contrast.** It does not license comparing `S_all` across
  bands — 80m and 20m differ in cluster structure by ~34×.
- 🛑 **No row re-reads P3.** P3 stays ROW 3, `X_guard` = 0.897, and the union still manufactures
  decodes. X3 partitions P3's effect; it does not revise it.
- 🛑 **ROW 1 does NOT license `K_FREQ_OSR`/`K_TIME_OSR` 2→4.** P3's guard stands verbatim: finer OSR
  keeps one scoring/CRC pass, the union runs the decoder five times and unions outputs, so neither
  P3's nor X3's false-positive behaviour is evidence about OSR in either direction. **Sizing an OSR
  change earns its own pre-registration with FP as the primary metric.**
- ⚠️ Density regimes are `REF`-based, so `I` is conditional on the reference in exactly the way
  X2's `F_std` is. It is not a claim about signals on the air.

## 6. Architect predictions, recorded blind

Per HK-021, and quoting the standing calibration (**categorical ROW calls 5/7, ranges 7/10,
DIRECTIONAL/SHAPE calls 0/2** — read the ranges as symmetric and simply wide):

| # | prediction | type |
|---|---|---|
| 1 | ROW 1 or ROW 2; **not** ROW 3 | categorical |
| 2 | `I_20m` ∈ **[0.5, 4.0] pp** | magnitude |
| 3 | measured `SE(I_20m)` ∈ [0.10, 0.35] pp — i.e. ROW 0e passes on the primary leg | magnitude |
| 4 | 80m replication is **UNDERPOWERED** at ROW 0d or fails to reach the 2.8 pp bar | categorical |
| 5 | `X_guard` is **higher** in OVERLAP than in MID/FLOOR | 🛑 **directional — recorded for scoring only, NOTHING turns on it** |

I am on record that I expect ROW 1. **The gate is built so that ROW 2 fires cleanly against me** —
that is the bound running against my own prediction, per HK-021.

---

## 7. Boundaries

- **No `src/`, no rebuild** (HK-011). **No push, no merge** (HK-014/HK-010). **No
  `pre_merge_check.py`** (HK-006).
- Per HK-015 this is Architect → QA; `dev-tasks/*.md` are QA's to author, and nothing here needs one.
- **NFR-021:** counts, rates and cycle timestamps only. No callsign or message text in the harness
  output or the report.
- Harness output to `x3_result.json`; determinism required (two runs, byte-identical stdout).
