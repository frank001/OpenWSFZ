# `DENSITY-P1` — pre-registration: after pass-1 suppression, are the crowded victim's bits clean or still dirty?

**Architect, 2026-09-18T17:58Z** (`date -u`, HK-017). Branch `arch/density`. This document is docs-only;
`git diff --stat origin/main...HEAD -- src/ native/` is empty. **Stage 1 below specifies a `native/` change,
which is NOT made here** (HK-011).

# 🛑 STATUS: HELD. QA DOES NOT START ANY PART OF THIS UNTIL THE CAPTAIN'S GO-AHEAD.

Captain, 2026-09-18: *"option a, prepare it but don't let QA start on it yet, hold until my go-ahead."*
**Prepared, not dispatched.** No dev-task, no harness, no Developer contact, no build. This is a hard stop
in the HK-030 sense: nothing downstream of it may start, even a step that looks unblocked.

**What option (a) is** (`DENSITY-MECH` §11.4): reopen **pass-1 co-channel handling** as the density line,
starting with a diagnostic export, then a remedy arm priced live. **This document covers the first two
steps only: the export (Stage 1) and the diagnostic that reads it (Stage 2).** A remedy arm is **not**
specified here and needs its own pre-registration and its own go-ahead.

---

## §0. Where we are, in one paragraph

`DENSITY-LIVE` priced the crowded-victim loss at **≈ 4.30 pp** (C2). `DENSITY-MECH` A1 showed that our
decoder recovers a crowded victim **only in pass 1**: with pass 1 disabled it is 0/100 in every cell,
including cells where full production is 94–100/100. Pass 0's extraction at the victim's true position is
fully corrupted (BER 0.30–0.44). **So in the geometries where we lose the victim, we are losing it inside
pass 1**, and the question that decides the fix route is:

> **After production's own pass-1 suppression of the stronger neighbour, are the victim's bits at its
> position CLEAN, so that pass 1's search or ranking misses a decodable signal, or still DIRTY, so that
> suppression removes too little of the neighbour or damages the victim?**

| reading | route | status |
|---|---|---|
| **DIRTY** | the suppression step itself: how much, where and when it attenuates | **soft-ramp tuning is not prohibited.** One variant (H5, 20260011) was rejected in June for over-suppression. |
| **CLEAN** | pass-1 candidate search / ranking / budget | 🛑 **candidate-budget family CLOSED ×2**; extra passes CLOSED. Nothing is authorised without a Captain ruling. |

🛑 **PCM subtract-and-resynthesise stays DEAD under either reading.**

**Production facts this rests on** (`src/OpenWSFZ.Ft8/Native/ft8_shim.c` on `main`, read while drafting):
- `K_MAX_PASSES` = 2. Pass 0 and pass 1 share `min_score` 10 and LDPC 50 iterations. Pass 1's candidate cap
  is **200 vs 140**.
- Before pass 1, `suppress_candidate_tiles()` attenuates **each pass-0 decode's** tone bin ±1, over all 79
  symbols and every time/freq sub-bin. The factor is `1 − clamp((snr − (−5)) / 20, 0, 1)`: **no change at
  reported SNR ≤ −5 dB, full at ≥ +15 dB.** The SNR is the **decoder's reported** SNR for that signal,
  not a scene level.

---

## §1. Stage 1 — the diagnostic export (Developer; QA authors the dev-task)

### 1.1 Design principle: a TAP inside production, not a copy of it

🔴 **`DENSITY-MECH` went void because its oracle was a separate code path that differed from production.**
The export must therefore **not** re-implement pass 0, suppression or pass 1. It must **capture state from
inside the real `ft8_decode_all` call**, at the exact point production uses it.

**Contract (names indicative; the Developer may adjust them, but not the semantics):**

| export | semantics |
|---|---|
| `ft8_set_probe(float freq_hz, float time_offset_s)` | **arms** a thread-local probe for the **next** `ft8_decode_all` call on this thread. Same position convention as `ft8_extract_llrs_at` (tone-0 frequency; `dt + 0.16 s` time origin, B-orig-A), snapped to the same lattice. |
| `ft8_clear_probe(void)` | disarms it. The probe also **disarms itself** after one `ft8_decode_all` call. |
| `ft8_get_probe_llrs(int pass, float* out174)` | raw pre-normalisation LLRs at the probe position, extracted with production's own `ft8_extract_likelihood` path **from `mon.wf` as it stands at the start of that pass's candidate search** (pass 0 = unsuppressed; pass 1 = **after** `suppress_candidate_tiles`). Returns an error code if the probe wasn't armed, or the pass didn't run (e.g. the early exit). |
| `ft8_get_last_suppression(…)` | for the last call: the number of pass-0 decodes suppressed, and **per entry** its lattice `(freq_offset, time_offset)`, **reported SNR** and **applied factor**. Numeric only. |

**Placement:** inside `ft8_decode_all`'s pass loop, **immediately after** the `if (pass == 1)
suppress_candidate_tiles(…)` block and **before** `ftx_find_candidates`. It is guarded by a thread-local
`armed` flag that **defaults to false** and is never set by the managed layer.

### 1.2 🛑 Non-negotiables for Stage 1

1. **Production behaviour byte-identical with the probe disarmed.** No change to the waterfall, candidates,
   decodes, SNR, ordering or TLS diagnostics that exist today. The tap only **reads** `mon.wf`, into its
   own TLS buffer.
2. **The probe must not perturb the call it observes, even when armed.** Extraction into a separate buffer,
   no write to `mon.wf`, no change to any counter. **Stage 2's ROW 0b tests this mechanically.**
3. **Not reachable from the managed layer.** No `DllImport` in `src/OpenWSFZ.Ft8` for these symbols. This is
   diagnostic-only, like `ft8_extract_llrs_at`.
4. **Shim version bump.** Use the next unused `FT8_SHIM_VERSION`. ⚠️ **Two real collisions are on record and
   the renumbers are unexecuted** (MEMORY). The Developer/QA must verify uniqueness against the full history,
   not the last value. Update `ExpectedShimVersion` (`Ft8LibInterop.cs`) and any SHA pins in tests. **Pin
   the new DLL's SHA-256**, because the version number identifies nothing.
5. **Branch: `decoding_improvement`** (the Captain's long-lived decode-rate branch). **HK-011:** a separate
   Developer session with pre-push sign-off. **HK-029:** this has a `src/`/`native/` diff, so **no direct push**.
   **HK-010:** the merge needs the Captain.
6. Windows `rebuild_shim.bat` export list, and the Linux/macOS builds (CI owns macOS).

### 1.3 Stage 1 acceptance — QA, before Stage 2 may run

| gate | check | fail ⇒ |
|---|---|---|
| **S1-a regression** | the fixed replay set used for the last shim bump, decoded by the **old** (`91997e38…`) and **new** DLL with the probe **disarmed**: decode results **byte-identical**, mechanically diffed | 🛑 reject the build |
| **S1-b perturbation** | the same set with the probe **armed** at an arbitrary position: decode results **byte-identical** to disarmed | 🛑 reject the build |
| **S1-c pass-0 equivalence** | on `DENSITY-MECH`'s cells, `ft8_get_probe_llrs(0, …)` at F's true position equals `ft8_extract_llrs_at`'s output for the same PCM/position **bit-for-bit** | 🛑 reject: the tap is not reading what production reads |
| **S1-d build** | CI green on all three platforms | 🛑 |

---

## §2. Stage 2 — `DENSITY-P1`, the diagnostic (QA, only after Stage 1 is accepted AND a separate Captain go)

### 2.1 Instrument

`DENSITY-MECH`'s harness and scene, **verbatim**: the `f-nbr-a` scene, E at `E_FREQ_HZ`, F at `E_FREQ_HZ + Δ`,
the same `part_index` seeds, the same §1.3 position mapping. **Binary: the Stage 1 DLL, SHA-pinned.**
🔴 **Decode params set explicitly to the LIVE app's** (`k_min_score_pass2` 10, `osd_corr_threshold` 0.10,
**`osd_nhard_max` 40**) via `ft8_set_decode_params`, and read back and recorded. **Not** the shim default 60
(`DENSITY-MECH` §11.2).

**Per trial, ONE production call:** arm the probe at F's true position → `ft8_decode_all` (E present) →
record:
- `prod`: F recovered, full production (`part_c._f_recovered` verbatim).
- `pass_F`: the pass that decoded F, if any, attributed from `ft8_get_last_pass_counts` together with the
  result order or pass tag. **QA states the attribution method** and falls back to A1's pass-1-off rerun if
  it can't be made exact.
- `P0`, `P1`: probe LLRs for pass 0 and pass 1 → BER vs truth → `ft8_ldpc_decode_llrs` (production's
  `max_iters`/`osd_depth`; `nhard` 40) → hit iff CRC OK **and** payload = F's.
- the suppression record (§1.1): **E's reported SNR and applied factor**.

**Paired control, same seed with E removed:** `P1_0` (pass-1 probe, no E).

### 2.2 Cells

`DENSITY-MECH`'s nine primary cells (Δ {6.25, 12, 18.75} × `X` {+1, +3, +6} dB, E −5 dB) **plus** its three
strong-victim cells (F +5, E +8) **as gated cells**, since they carry the most suppression (factor ≈ 0.35 at
+8 dB). **Plus** two cells with E at **+15 dB** (full suppression), F at +12 (`X` +3), Δ {6.25, 12}: the
"suppression maxed out" end. **N = 100.** 14 cells.

### 2.3 ROW 0 — any fires ⇒ 🛑 STOP

🔴 **This ROW 0 is built on `DENSITY-MECH` §10.3's lesson: the probe must be shown to agree with production
IN THE EXACT CONDITION THE VERDICT READS**, which is pass 1 with E present.

| row | check | fires when |
|---|---|---|
| **0a — binary & params** | SHA pin; shim version; decode params read back = live app's | mismatch |
| **0b — determinism & non-perturbation** | two full runs byte-identical; **and** `prod` with the probe armed = `prod` with it disarmed, per trial, in every cell | any difference |
| **0c — AGREEMENT WITH PRODUCTION, on the verdict axis** | in every trial where production decoded F **in pass 1** (`pass_F` = 1), the **`P1` oracle also decodes F**. Required: **agreement ≥ 0.95 of those trials**, pooled over cells, **with ≥ 50 such trials** (A1 gives ~294 across three cells) | < 0.95, or < 50 trials |
| **0d — the oracle can say NO** | F alone at −30 dB: `P1_0` hit rate ≤ 0.20 | > 0.20 |
| ~~**0e — the oracle can say YES**~~ | ~~`P1_0` (E removed) ≥ 0.90 in every gated cell~~ 🔴 **SUPERSEDED by §7 A1 (2026-09-19): infeasible as written — F decodes in pass 0 of the control and pass 1 suppresses F's own tiles, so `P1_0` reads F's ruins wherever F's factor < 1 (pilot: 0.00 in the strong and E+15 cells).** | ~~any cell < 0.90~~ → see §7 |
| **0f — the geometry is excluded** | `prod` ≤ 0.20 in ≥ 6 gated cells (so there is something to read) | < 6 |

**Why 0c is the load-bearing row.** If the `P1` oracle fails where production **succeeded** in pass 1, it is
not reading what production reads, and a DIRTY reading would be the same false verdict `DENSITY-MECH`
produced. **0c is exactly the check that arm was missing.** It uses cells where the answer is known (production
succeeded), and it is mechanical.

⚠️ **0c tests agreement in one direction only** (production-yes ⇒ oracle-yes). Oracle-yes where
production-no is **not** a disagreement. It **is** the CLEAN reading. That asymmetry is the design, not an
oversight.

### 2.4 Reading rows — per excluded gated cell (`prod` ≤ 0.20), with `o1` = `P1` hit rate

| cell reads | predicate | meaning |
|---|---|---|
| **DIRTY** | `o1` ≤ 0.20 | after production's suppression, F's bits **still can't be decoded at its position**. Suppression leaves too much of E, or damages F. |
| **CLEAN** | `o1` ≥ 0.80 | after suppression, F's bits **decode at its position**, but production never did. Pass 1's search or ranking misses a decodable signal. |
| **MIXED** | otherwise | |

| overall | predicate | next (pre-registered, §2.6) |
|---|---|---|
| **ROW 1 — DIRTY** | every excluded gated cell DIRTY | suppression route |
| **ROW 2 — CLEAN** | every excluded gated cell CLEAN | candidate-stage route (CLOSED ×2) ⇒ Captain |
| **ROW 3 — SPLIT** | otherwise | full cell map (Δ × `X` × E level, with E's applied factor) to the Architect and Captain. 🛑 No averaging, no majority. |

```python
excl = [c for c in gated if c.prod <= 0.20]
if row0_fires:                        verdict = "ROW 0 STOP"
elif all(c.o1 <= 0.20 for c in excl): verdict = "ROW 1 DIRTY"
elif all(c.o1 >= 0.80 for c in excl): verdict = "ROW 2 CLEAN"
else:                                 verdict = "ROW 3 SPLIT"
```

**Every row is reachable:** 0d/0e prove `o1` can land at either end, and 0c proves it tracks production where
production succeeds. The rows are mutually exclusive. **Readout quantum:** N = 100, so the SE is ≤ 0.05 and the bars
sit 0.60 apart. A cell truly near a bar goes to SPLIT, and that is honest. ✅

**Null in independent units (HK-021(z)).** "The probe is production's own pass-1 state" ⇒ 0c ≈ 1.00
(identical code path, identical waterfall) ~~and `P1_0` ≈ `orc_0` ≈ 1.00 (A1/`DENSITY-MECH`: 100/100)~~ 🔴 **struck
2026-09-19 (§7): false wherever F's own applied factor < 1 — `orc_0` was a pass-0-equivalent read, `P1_0` is
read AFTER F's own pass-0 decode has suppressed it. I carried a number across a pass boundary without checking
what the pass does to F.** The 0.95 ~~and 0.90 bars pass~~ bar passes where that holds, and fails on a tap at the wrong point or a perturbing tap.

### 2.5 Reporting only — gates nothing

1. Per cell: `prod`, `P0`, `P1`, `P1_0` hit rates; paired BER `P1 − P1_0` and `P0 − P1` (how much suppression
   bought).
2. **E's reported SNR and applied factor**, per cell (median, IQR). ⚠️ The E −5 dB cells may carry a factor
   of ≈ 1.0 (**no** suppression) if E is reported at ≤ −5 dB. **That alone would make DIRTY near-automatic
   there.** It is reported so nobody reads a DIRTY at factor 1.0 as "suppression is too weak". **No
   suppression was applied at all.**
3. If DIRTY or SPLIT: **collateral vs residual.** BER on F's symbols where E's attenuated bins (tone ±1)
   **overlap** F's tone bin, vs symbols where they don't. Residual E predicts errors where E's energy
   **wasn't** removed; collateral predicts errors where F's **own** bins were attenuated. Descriptive.
4. `pass_F` distribution in the non-excluded cells.

### 2.6 Sequence after the verdict — pre-registered

| verdict | next |
|---|---|
| **ROW 1 DIRTY** | Architect → Captain: a **suppression-route remedy arm** (factor ramp, ±1-bin footprint, SNR input), pre-registered with **FP primary**, priced live with `DENSITY-LIVE`'s classifier before anything ships. **Reported factor at E's level decides the arm's shape.** If E was unsuppressed (factor ≈ 1) the question is the ramp's floor. If fully suppressed and still dirty, the question is the footprint. H5's June rejection (over-suppression at 0 dB) is the known failure to design around. |
| **ROW 2 CLEAN** | Architect → Captain: the candidate-budget family is **CLOSED ×2**. Reopen it narrowly for pass-1 ranking in this geometry, or accept the gap. |
| **ROW 3 SPLIT** | the map to the Captain. **No averaging.** |
| **ROW 0** | report and stop. No re-cut. |

---

## §3. What this can't see

1. **One synthetic scene, AWGN, one interferer.** Live pairs vary.
2. **The probe reads at F's true position.** A1 showed production's candidate sits within 0–1 Hz of it,
   so this is not the `DENSITY-MECH` failure. Still, **CLEAN means decodable at the true position**, not
   that pass 1 would rank that exact lattice point.
3. **It does not test a remedy.** It locates the loss within pass 1; nothing more.
4. `nhard` 40 here vs 60 in `DENSITY-MECH`/A1. `prod` rates are **not** comparable across the two, by design.

---

## §4. Cost, stated for the Captain before he says go

| step | who | cost |
|---|---|---|
| Stage 1 export | QA dev-task → Developer session → QA acceptance S1-a…d | one Developer session, one shim bump, CI on 3 platforms. **The probe is ~40–60 lines of `native/` plus the export list.** |
| Stage 2 diagnostic | QA | minutes of compute (14 cells × 100 trials × one decode + LDPC probes) |
| merge of Stage 1 to `main` | Captain (HK-010) | **not required for Stage 2.** Stage 2 runs from `decoding_improvement`. |

**Two separate go-aheads are asked for:** Stage 1 (build the export), then Stage 2 (run it). Nothing merges
to `main` without a third.

---

## §5. Predictions — written before anything is built

🔴 **My mechanism calls on this defect: `NBR-A` M1 @55% (never scored), assessment M2 @0.60 (open),
`DENSITY-MECH` VOID.** Weight these as close to uninformative.

| # | prediction | P | class |
|---|---|---:|:---:|
| 1 | Stage 1 passes S1-a…d first time | 0.70 | C |
| 2 | Stage 2 ROW 0 silent (**0c in particular**) | 0.70 | H |
| 3 | ROW 1 DIRTY, given ROW 0 silent | 0.40 | H-mech |
| 4 | ROW 2 CLEAN, given ROW 0 silent | 0.20 | H-mech |
| 5 | ROW 3 SPLIT, given ROW 0 silent, split by E's applied factor | 0.40 | H-mech |
| 6 | E at −5 dB is reported at an SNR giving factor ≥ 0.90 (≈ no suppression) | 0.60 | C |

---

## §6. Status

- ~~🛑 **HELD. Not dispatched. QA does not start: no dev-task, no harness, no Developer contact.**~~
- ~~➡️ **With the Captain:** go / no-go on **Stage 1** (export build). Stage 2 needs a **second**, separate go.~~
  🟢 **2026-09-19: Stage 1 GO given and Stage 1 ACCEPTED (S1-a…e); Stage 2 GO given. Stage 2 runs under §7's amendments.**
- 🔴 **Bars fixed now:** S1-a/b byte-identical · S1-c bit-for-bit · 0c ≥ 0.95 over ≥ 50 pass-1 trials ·
  0d ≤ 0.20 · ~~0e ≥ 0.90~~ **0e-i / 0e-ii per §7** · 0f ≥ 6 · per cell DIRTY ≤ 0.20 / CLEAN ≥ 0.80 (on `o1` per §7 A2) · unanimity for ROW 1/2.
- 🛑 **PCM subtract-resynthesise DEAD · candidate-budget CLOSED ×2 · no remedy in this document.**

---

## §7. Amendment 1 — ROW 0e infeasible as written; ruling on QA's A1–A4 (2026-09-19T11:48Z, `date -u`)

**Raised by QA under HK-025 before any Stage 2 data was collected.** QA's feasibility pilot ran control legs
only (N = 20, no verdict quantity computed; `artefacts/density-p1-stage2/pilot_row0e_feasibility.txt`,
gitignored): primary cells F reported ≈ −6.5 dB, factor 1.000, `P1_0` = 1.00 · strong-victim cells factor
0.43, `P1_0` = 0.00 · E+15 cells factor 0.10, `P1_0` = 0.00 · `P0_0` = 1.00 in every cell.

**The defect is mine.** With E removed, F decodes in **pass 0**, and pass 1 then suppresses **F's own** tiles
before the pass-1 tap reads. §2.3's 0e would have fired with certainty in 5 cells whether or not the probe
was sound: a row that cannot pass, so a STOP that says nothing. Same shape as `DENSITY-MECH` §10.3: a
precondition checked in a condition different from the one it had to hold in. Struck at §2.3 and §2.4 (HK-022).

### 7.1 Ruling

| item | ruling |
|---|---|
| **A1 — split 0e** | ✅ **ACCEPTED WITH ONE EDIT** (below) |
| **A2 — `o1` over trials with `pass_F ≠ 0`** | ✅ **ACCEPTED.** The gating `o1` in §2.4 is the `P1` hit rate over trials where F was **not** decoded in pass 0 (`pass_F` ∈ {1, none}). The unconditional rate is reported. Denominator is ≥ 80 by construction in any excluded cell (`prod` ≤ 0.20); QA reports it per cell anyway. |
| **A3 — params read-back** | ✅ **ACCEPTED.** No getter exists (QA verified all 26 exports). 0a becomes: SHA pin + shim version + the values **SET** (10 / 0.10 / 40) recorded, with a statement that read-back is impossible. 🔴 **I wrote "read back" without grepping the export list. That is the fourth feasibility claim in this programme made without a one-line grep** (ledger, `DENSITY` #3). |
| **A4 — "gated cells"** | ✅ **All 14 are gated.** The 12-cell variant without E+15 is reporting only. |

### 7.2 The edit to A1 — 0e-i must be gated on the control's F factor, not on `prod`

As QA proposed it, 0e-i applies to every **excluded** cell. Excluded status comes from `prod` in this run,
and this run uses **nhard 40**, not `DENSITY-MECH`'s 60 (§3.4: `prod` is not comparable across them). **If a
strong-victim or E+15 cell turns out excluded at nhard 40, 0e-i would fire there with certainty:** its
control reads `P1_0` = 0.00 from self-suppression. That is the same fault this amendment exists to remove.

And in such a cell `P1_0` is not the right YES test anyway. The reading (`o1`, per A2) uses trials where F was
**not** decoded in pass 0, so F's own tiles were **not** suppressed. The control, by contrast, always
suppresses them.

| row | check | fires when |
|---|---|---|
| **0e-i — pass-1 YES, where the control is valid** | over excluded cells whose control-leg **median F factor ≥ 0.90**: `P1_0` ≥ 0.90 in each | any such cell < 0.90, **or no excluded cell qualifies** (the row may not go decorative) |
| **0e-ii — tap + LDPC YES on an unsuppressed waterfall** | `P0_0` ≥ 0.90 in every gated cell | any cell < 0.90 |

- An excluded cell whose control F factor is < 0.90 is **still read**, flagged in the cell map, and its YES
  evidence is 0e-ii plus 0c (the pass-1 tap agreeing with production **with E present**, which is the
  verdict axis itself). It is not gated by 0e-i.
- **Why the split is not outcome-chosen (HK-021(y)).** The control's F factor comes from F's reported SNR
  with E **absent**, fixed by the cell's geometry. It does not depend on `o1` or `prod`. The pilot says the
  nine primary cells qualify (factor 1.000), so 0e-i covers them.
- **Both rows can fire:** 0e-i if the pass-1 tap misreads an unsuppressed F, 0e-ii if the tap or LDPC path is
  broken. Both pass under the null (pilot 1.00 / 1.00).

§2.4's `excl` and verdict code are unchanged except `o1` → the A2 conditional rate. 0a–0d and 0f are unchanged.

### 7.3 Predictions

- **§5 #2 ("ROW 0 silent", 0.70, H) is scored a MISS against the spec as written.** The pilot shows 0e would
  have fired with certainty. A prediction on a row I designed to be unpassable is a design failure, and it is
  scored as one, not withdrawn.
- **No new blind prediction is written for the amended ROW 0.** I have seen the pilot's control rates, so any
  number would be informed.
- **#3–#6 stand as written.** They are on the reading rows and on E's factor, which nobody has seen.

🟢 **QA may pre-register the harness under §7 and run.**
