# ARCHITECT → QA — PRE-REGISTRATION `D2`: is the shared +0.650 s offset a CONVENTION or a PHYSICAL displacement?

**2026-08-19 13:05Z · Architect · follows `D1` (12:40Z, ROW 1, locus SHARED)**

**Status: SPEC ONLY, NOT RUN. No `src/` change. No capture run. No Developer session — HK-011 is
not engaged by anything in this document.**

🔴 **This arm needs NO new data.** Everything it consumes is already on disk. §3 discharges HK-018
and HK-004 with counts I measured while drafting.

---

## 0. What `D1` left open, stated precisely

`D1` answered *which file carries the offset*: both do, bit-identically. It was never built to say
*what the offset is*. The board's phrasing of the survivor set — "the shared capture/save path **or**
the `dt` convention" — is a disjunction nobody has separated, and the two halves have opposite
consequences:

| if it is… | then the product defect is… | and the fix is… |
|---|---|---|
| the **`dt` convention** | possibly **nothing** — two programs naming the same instant differently | a harness/labelling correction, no `src/` risk |
| a **physical displacement** | real — our buffer's contents sit ~0.65 s off true | a capture/framing change, `src/`, a type change, a Developer session |

We have spent one withdrawn recommendation on guessing this. `D2` measures it.

---

## 1. The decomposition, written down before any number is looked at

Let `C_w` be **WSJT-X's convention constant**: the amount it subtracts, relative to our definition,
when it turns a signal's position inside its capture buffer into the `DT` it reports. Our own
definition is buffer-relative with nothing subtracted — verified in code, not assumed:
`ft8_shim.c:1432-1434` computes `dt = (cand->time_offset + time_sub/time_osr) * symbol_period`,
measured from the first sample of the buffer handed in. There is no protocol-start term anywhere in
the shim.

Let `P` be any **physical displacement** — the amount by which the audio actually sitting in a
buffer is offset from where its label says it should be.

`AO1`'s `K = +0.650 s` is, by its own construction, `p_ours − dt_wsjtx`: the extra offset needed,
when anchored at the reference's reported `dt`, to land on the signal inside our buffer.

🔴 **The structural point that makes this arm cheap.** If our file and the reference's file are the
same audio — and F1 measured exactly that, median `|lag|` 15.5 ms over 4,956 pairs — then a signal
sits at the *same* position `p` in both. Any physical displacement is therefore **common to both**
and **cancels out of `K` identically**. What survives in `K` is only what the two programs *call*
that position:

> **`K = C_w`, forced, given F1.**

`D1`'s result is the direct corroboration: sweeping either file returns the same argmin, which is
what "the displacement cancels" looks like when you measure it.

⚠️ **I am not asserting the conclusion.** The above says `K` is *structurally* a convention
quantity given F1. It does **not** say `C_w = 0.650`; that is an empirical claim about WSJT-X, and
`AO1`'s Part C measured a **real +0.706 pp recall cost**, which a purely notational difference has
no obvious way to produce. **Those two things are in tension, and naming the tension is the point of
this arm.** See §5 ROW 1 — that branch *escalates* rather than closing.

---

## 2. The statistic

**`Δ` := `reported_dt_s(WSJT-X) − reported_dt_s(OpenWSFZ)`, over matched pairs of the *same
injected signal*, on the R&R synthetic bench.**

Why this is the right instrument, and not merely an available one:

1. **Both decoders hear the identical audio through one chain.** Any capture latency, playback
   offset, or slot-alignment error is **common-mode and cancels exactly** in the difference. `Δ` is
   the convention term and nothing else: `Δ = −C_w`.
2. 🔴 **`Δ` is immune to synth truth-label error by construction.** It never reads `true_dt_s`. If
   our generator mislabels where it put a signal, `Δ` is unaffected — both decoders still heard the
   same waveform. This is the HK-022 property the R&R bench usually *lacks* (round-tripping against
   our own generator tests self-consistency); `Δ` sidesteps it because it is decoder-versus-decoder,
   not decoder-versus-truth.
3. **It is not censored by its own matcher — verified in code.** `matcher.py` pairs on cycle,
   message text, and `FREQ_TOLERANCE_HZ = 4.0` (`:31`, `:125`, `:150-175`). **`dt` is recorded but
   never used as a matching predicate.** Had it been, a ~0.65 s convention difference would have
   pushed the reference's rows *out* of the matched set and hidden the very effect we are measuring.
   🔴 **QA: re-verify this independently before arming. If it is wrong, the arm is void, not
   adjusted.**

**Prediction linkage:** `K = C_w = −Δ`. So `Δ ≈ −0.650 s` means the offset is entirely convention;
`Δ ≈ 0` means it is entirely physical; anything between is a measured split.

---

## 3. HK-018 / HK-004 discharge — the data exists, I counted it

I checked before proposing anything. `qa/artefact_inventory.py --check` reports the inventory **up to
date**, and no capture run has landed since 2026-08-10 — so a *new device* corpus does not exist and
would need a capture run. **`D2` does not need one.**

R&R matched CSVs carry `true_dt_s`, `reported_dt_s`, `appraiser`, and `cycle_utc` in the same row
(`matcher.py:35-36`). Usable matched rows (both `dt` fields present) across 107 matched CSVs:

| scenario | WSJT-X | OpenWSFZ |
|---|---|---|
| **S7** | **3,071** | **2,563** |
| S4 | 410 | 393 |
| S8 | 394 | 360 |
| S1 | 362 | 360 |
| S2 / S3 | 270 each | 270 each |

Best single runs: `2026-08-05-3bd4cd0` (464 / 393), `2026-08-15-8d6e1b1` (461 / 404),
`2026-06-20-d70aad5` (435 / 361).

🛑 **These CSVs contain `message_text` and the `2026-08-15-8d6e1b1` run is the known NFR-021
contamination case** (~203,920 unmatched rows logged with full message text). `D2` reads them and
must emit **counts and seconds only**. Grep every emitted file individually before committing — the
run directory's own cleanliness does not extend to anything derived from it.

---

## 4. ROW 0 — preconditions, all mechanical, all before any `Δ` is computed

Evaluate in order. Any failure STOPS the arm and escalates; none of them is a "note it and carry on".

| row | check | bar |
|---|---|---|
| **0a** | DLL SHA256 for the primary run asserted against that run's own recorded manifest, never inferred from a label or a version integer | exact match; absent manifest ⇒ STOP |
| **0b** | Field provenance, by code read: OpenWSFZ `reported_dt_s` traces to `ft8_shim.c:1432`'s `dt`; WSJT-X `reported_dt_s` traces to `ALL.TXT` field **`[5]`** (0-based) | both confirmed in writing; ⚠️ confusing `[5]`/`[6]` inverts this result exactly |
| **0c** | `matcher.py` does **not** use `dt` in its matching predicate (§2 item 3), re-verified independently | confirmed; else VOID |
| **0d** | Audio path: establish and **state** whether the R&R bench feeds OpenWSFZ **live through `CycleFramer`** or **from file**. Do not guess. | answer recorded; drives §5's interpretation note, not the row |
| **0e** | Matched-pair population | ≥ 250 pairs **and** ≥ 60 `cycle_utc` clusters on the primary run |
| **0f** | **Resolution (HK-021(m)), measured not assumed:** cluster-bootstrap `1.96·SE(Δ)` | **≤ 0.05 s.** Above that the arm cannot separate 0.650 from 0.500 and must NOT report a row — escalate as underpowered |
| **0g** | **Pairing purity null (H1a precedent):** re-pair candidates to truths at random *within* cycle, recompute `Δ_null` | `Δ_null` diffuse and centred near 0; a tight non-zero `Δ_null` means the pairing manufactures the result ⇒ VOID |
| **0h** | **HK-026 — is the instrument flat where the boundary sits?** Confirm the injected `true_dt_s` range lies well inside both decoders' acceptance, and that per-decoder yield does **not** fall off at the range edges | flat across the used range; rolloff at an edge ⇒ restrict the range and re-state, do not average across it |

**Pre-registered contingency for 0e/0f:** if the primary run fails on population, pool **only** runs
sharing an identical asserted DLL SHA, and report that pooling was invoked and which runs entered.
Never pool across differing SHAs; never pool to rescue a failed 0f.

**Primary run:** `2026-08-05-3bd4cd0`. **Descriptive replication, per run, never pooled into the
headline:** `2026-08-15-8d6e1b1` and `2026-06-20-d70aad5`.

---

## 5. ROWS — mutually exclusive, strict order, two-sided

`θ = 0.10 s` throughout (two grid steps of the `AO1` sweep, the same bar `D1` used). All rows are
evaluated on the **signed** `Δ` with its cluster-bootstrap CI95 — 🔴 **never on `|Δ|`** (HK-021(l),
six prior firings, all Architect-authored). Row 2 is an equivalence claim and is therefore written
as a CI containment, which is signed and two-sided by construction (HK-021(n)).

**ROW 1 — PURE CONVENTION.** `Δ ∈ [−0.750, −0.550]`, i.e. `C_w` agrees with `AO1`'s `K = +0.650 s`
to within `θ`.
→ The offset is entirely a difference in what the two programs call `dt`. **No capture or framing
defect is demonstrated, and no `src/` change is justified by the offset alone.**
🔴 **This row does NOT close the question — it ESCALATES it.** `AO1` Part C measured `L = +0.706 pp`,
a real recall cost, and a purely notational difference has no mechanism by which to cost recall.
ROW 1 firing means **either** Part C's effect has a different cause **or** this arm's cancellation
argument is wrong. Report both possibilities, rule neither out, and stop. **Do not let ROW 1 be
written up as "the offset was nothing."**

**ROW 2 — PURE PHYSICAL.** `CI95(Δ) ⊂ [−0.10, +0.10]` (contained, not merely overlapping).
→ The two decoders agree on what `dt` means; the +0.650 s is a physical displacement of captured
audio. **The capture/framing locus is confirmed**, the device axis becomes live, GH #111's
device-axis arm is warranted, and the 12:26Z design envelope (a chunk carrying its own capture
timestamp, stamped on the capture thread) becomes the candidate fix shape — **as a proposal to the
Captain, not as authorised work.**

**ROW 3 — MIXED.** Neither ROW 1 nor ROW 2, and `CI95(Δ)` excludes both 0 and −0.650.
→ Report the split explicitly: `C_w = −Δ`, residual physical `P = 0.650 + Δ`, each with its CI.
Consequence scales with `P`: `|P| ≥ 0.10 s` carries ROW 2's consequences at the size of `P`;
`|P| < 0.10 s` is a measured residue too small to justify a `src/` change on its own.

**ROW 4 — INSTRUMENT FAILURE.** `Δ` is dispersed beyond the model (cluster-bootstrap CI wider than
0.30 s), **or** the regression slope of `Δ` on `true_dt_s` differs from **0** with CI excluding 0.
→ A constant convention is then the wrong model — `Δ` depends on where the signal sits, which no
notational difference can do. Escalate; do not report ROWS 1–3.

**Mandatory alongside every row:** slope of `Δ` on `true_dt_s` with **CI and p**, and `Δ` stratified
by `true_dt_s`. 🔴 **Never a bare `r`.** The matched population is decode-censored (only signals both
decoders read contribute), which biases the *population* but not the *contrast* — unless `C_w`
varies with `dt`, which is exactly what the slope tests.

---

## 6. Predictions — scored

Recorded before any `Δ` is computed. My ranges run under-dispersed and skewed toward whatever I
measured last, so I have widened these deliberately.

| quantity | prediction |
|---|---|
| row | **ROW 1** P≈0.45 · **ROW 3** P≈0.35 · **ROW 2** P≈0.12 · **ROW 4** P≈0.08 |
| `Δ` point | **−0.55 s** |
| `Δ` 80 % interval | **[−0.75, −0.35]** |
| slope of `Δ` on `true_dt_s` | **0**, CI excluding ±0.05 s/s |

🛑 **The reasoning behind the −0.55 s point estimate, disclosed so it can be discounted rather than
inherited:** an FT8 transmission starts 0.5 s into its slot, so a decoder reporting `DT` relative to
the *expected transmission start* rather than the *slot boundary* differs from ours by ≈0.5 s — which
would leave ≈0.15 s of `K` unexplained and land ROW 3. **This is recall and inference, not a
measurement, and it is not licence to skip anything.** ⚠️ **The standing licence policy is binding:
WSJT-X source may be read for method only. A constant read out of its source may NOT be cited as
this arm's result — the measured `Δ` is the result, or there isn't one.**

---

## 7. De-blinding disclosure (X1/X2 precedent)

While drafting I ran, on the R&R CSVs: **row counts, appraiser value counts, and null-rates of
`true_dt_s`/`reported_dt_s`**, plus a code read of `matcher.py` and `ft8_shim.c`. I did **not**
compute `Δ`, any difference of the two `dt` columns, or any stratification of them, at any point.

✅ **The headline is therefore still blind and my §6 predictions are scorable in full.** If QA finds
any evidence to the contrary in my shell history, treat the predictions as void rather than argue
the point.

---

## 8. Scope discipline — what `D2` does not touch

`D2` answers one question: is the shared offset notational or physical? It does **not** revisit,
rehabilitate or reopen: `AO1` (closed), C2 (accepted), the ledger correction, ROW 3, ROW 0f, `D1`,
N1 ROW 2 / limb 1, N5, or any standing closure (error-correction changes, PCM input scaling,
candidate budgets, subtract-and-resynthesise, spectral locality). None of those moves on any branch
of this arm.

**It is also not the device arm.** Even ROW 2 does not by itself justify a capture run; it justifies
*proposing* one, with GH #111's 2×2 decomposition folded in, to the Captain.

**Estimated cost:** re-analysis only, data on disk, no rebuild, no capture, no `src/`. Comparable to
`D1`'s ~3 minutes of measurement plus harness time.

**Next action: QA runs `D2` and stops.** Report the row, the CIs, the slope with its p-value, the
ROW 0 trace in order, and the mandatory disclosures. Escalate on ROW 1 and ROW 4 rather than
concluding.
