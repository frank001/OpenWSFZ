# `DENSITY-MECH` — pre-registration: is the near-neighbour loss in EXTRACTION, or upstream of it?

**Architect, 2026-09-18T13:56Z** (`date -u`, HK-017). Branch `arch/density` (the density workstream's
branch: `DENSITY-LIVE`'s spec, its ruling and this arm are one line of work). Docs-only;
`git diff --stat origin/main...HEAD -- src/ native/` is empty.

**Status: cleared to run.** Captain, 2026-09-18, on `DENSITY-LIVE` ROW 1 (spec
`2026-09-18-1339-…-density-live-concentration.md` §10): *"1. go"* ⇒ the M1/M2 mechanism arm.

**Offline, synthetic, Q-prefix only. No station time, no live corpus, no `src/`/`native/` change, no
Developer.** Every entry point it needs is **already exported by the shipped shim** (§1.2).

---

## §0. Why this arm, and why it is NOT `NBR-A` again

`DENSITY-LIVE` established that, live, **we decode 5.2% of the rows WSJT-X decodes under an
equal-or-stronger neighbour within 18.75 Hz**, at a cost of **≈ 4.30 pp** (C2). The fix route depends
entirely on **where** in our pipeline the victim is lost:

| | the victim's bits at its true position are… | the loss is… | route |
|---|---|---|---|
| **M1** | **corrupted.** The neighbour's tones land in the victim's 8 tone bins; magnitude-only single-symbol max-log can't tell them apart. | in **extraction** | extraction work = **D-001 limb 2**. **Not closed.** |
| **M2** | **intact.** Offered at the right spot, production's own extraction + LDPC would decode them. | **upstream**: candidate search, sync or tile suppression never offers that spot | candidate stage. 🛑 **The candidate-budget family is CLOSED ×2**, so this authorises nothing directly (new pre-registration, FP primary, and a Captain ruling to reopen). |

🛑 **Neither outcome reopens subtract-and-resynthesise (DEAD: three builds, three reverts),** even though
that is how WSJT-X handles this geometry.

**Why `NBR-A` failed, and why this design does not repeat it.** `NBR-A` tried to read the mechanism from
the **shape** of `R(Δ)`, looking for 6.25 Hz periodicity. `R` is a knife-edge (C3), so `R(Δ)` is a step
function and the shape can't carry the signal whatever the truth is. Its ROW 0c′ closed it (2026-08-30).
**This arm does not read a shape.** It asks a **direct counterfactual at fixed geometry**: *bypass the
candidate stage, extract at the victim's true position, and decode with production's own LDPC. Does it
come back?* That is a yes/no that **differs between M1 and M2 at every single cell**, and it needs no
periodicity. The continuous metric the `NBR-A` closure asked for (bit-error count against truth) is
carried alongside as supporting evidence and for ROW 0.

---

## §1. Instrument

### 1.1 Scene

`F-NBR-A`'s scene and machinery, **verbatim**: `qa/rr-study/f-nbr-a/scene_render.py` and
`qa/rr-study/scenarios/s8hn-band-scene-highn.json` (committed, Q-prefix synthetic). **E** is the
interferer at `SR.E_FREQ_HZ`, −5 dB. **F** is the victim, placed at `E_FREQ_HZ + Δ` exactly as
`part_c.run_c2()` does. **F's level via `SR.set_station_snr()`**, E's removal via `SR.remove_station()`,
both as `part_c` uses them. **Same seed discipline as `part_c`**, with one new `part_index` per cell,
declared in the results JSON before the run.

### 1.2 Entry points — all in the shipped shim, all from existing harnesses

| call | what it does | harness it comes from |
|---|---|---|
| `ft8_decode_all` | **production**, end to end | `f-nbr-a/dll_common.py` |
| `ft8_extract_llrs_at(pcm, f, t, out174)` | production's **own** `ft8_extract_likelihood()` at a **caller-supplied** position, snapped to the production lattice; raw pre-normalisation LLRs | `n1-extract-llrs-at-position/extract_llrs_ctypes.py` |
| `ft8_ldpc_decode_llrs(llr174, …)` | production's **own** BP → OSD → CRC-14 path on a supplied LLR vector | `r2-coherent-llr-instrument/ldpc_decode_ctypes.py` (as `nbr_rerun_driver.py` already imports it) |
| truth bits | F's message → 174 codeword bits | `extract_llrs_ctypes.py`'s existing bit helper; BER via its `hard_decision_ber()` (sign convention documented there) |

`max_iters` and `osd_depth` passed to `ft8_ldpc_decode_llrs` **must equal the running build's own**,
read from the build and recorded (as `NBR-RERUN` ROW 0b did). An oracle decode on weaker LDPC settings
than production's would bias toward M1.

🔒 **Binary:** `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`, SHA-256
**`91997e38038d9328edcb49cd1e8661706d0092ed2c73e808094c96c3980ad2c6`** (shim `20260051`), hashed from
the file actually loaded.

### 1.3 Per trial, three measurements on the SAME rendered noise

1. **`prod`**: `ft8_decode_all` on the full scene (E present). Hit = F's message recovered, using
   `part_c._f_recovered()` verbatim.
2. **`orc_E`**: `ft8_extract_llrs_at` at **F's true (freq, time offset)** on the full scene → BER vs truth
   → `ft8_ldpc_decode_llrs` → hit iff `crc_ok` **and** the payload equals F's.
3. **`orc_0`**: the same as 2 on the **same seed with E removed** (`SR.remove_station`). This is the paired
   control, and it absorbs any lattice-snap or origin-convention loss, because that loss is identical in both.

**F's "true position"** is the position `scene_render` placed it at. 🔴 **QA must state, in the results
JSON, exactly which frequency (tone-0 vs centre) and which time origin that is, and how it maps onto
`ft8_extract_llrs_at`'s arguments.** This programme has lost days to DT-convention and origin defects
(`modulator.py` clamp; the B-ORIG/B-POS work under `r2-coherent-llr-instrument/`). **ROW 0c is the
mechanical check that it is right.**

### 1.4 Cells

**Primary grid — E fixed at −5 dB (the bench's level), F set by the neighbour excess:** Δ ∈ **{6.25,
12.0, 18.75} Hz** (the complete-exclusion zone, C2's own points) × **`X` = snr_E − snr_F ∈ {+1, +3, +6}
dB**, i.e. F at −6 / −8 / −11 dB. `X` = +3 is the bench's own geometry (F −8 dB), and `X` = +1 sits on the
live knife-edge (`DENSITY-LIVE` §10.4: `rel` ≥ 1 ⇒ 3.9% live).

**Strong-victim cells — reporting only:** Δ ∈ {6.25, 12.0, 18.75}, F at **+5 dB**, E at +8 dB (`X` = +3).
Live showed strong victims excluded as completely as weak ones (per-band `D` 0.67 → 0.84).

**N = 100 trials per cell.** Nine primary + three reporting = 12 cells × 100 × (1 decode + 2 extractions
+ 2 LDPC + 2 renders). **Minutes, not hours.**

---

## §2. ROW 0 — preconditions (any fires ⇒ 🛑 STOP, no primary reading)

🔴 **HK-025 applies: QA may refuse any row on HK-021(k) grounds without Architect agreement.**

| row | check | fires when | why it changes the verdict |
|---|---|---|---|
| **0a — binary** | SHA-256 of the loaded DLL = §1.2's pin; shim version read back = 20260051; `max_iters`/`osd_depth` recorded from the build | any mismatch | unidentified binary ⇒ nothing below is attributable |
| **0b — determinism** | two full runs ⇒ byte-identical results JSON, **mechanically diffed** | differ | a non-deterministic harness makes every rate unreadable |
| **0c — the oracle can say YES** | `orc_0` hit rate **≥ 0.90** in **every** primary cell (E removed, F at its cell level) | any cell < 0.90 | if the oracle path can't decode an **unobstructed** victim at its "true" position, the position mapping (§1.3) or the path is wrong. **A low `orc_E` would then be read as M1 when it is an instrument defect: the exact false-M1 this row exists to stop.** |
| **0d — the oracle can say NO** | F **alone** (E removed) at **−30 dB**, Δ = 12, 100 trials: `orc_0` hit rate **≤ 0.20** | > 0.20 | if the oracle "decodes" a victim far below threshold, it is leaking truth (wrong payload check, stale buffer, CRC mis-read) ⇒ a high `orc_E` would be a false M2 |
| **0e — the bench reproduces** | `prod` hit rate **≤ 0.20** in **≥ 6 of the 9** primary cells | < 6 cells | the exclusion isn't reproduced in the geometry this arm is built on (it was 0/100 at Δ ≤ 18.75, `X` = +3 in `F-NBR-A` and `NBR-RERUN`). With too few excluded cells there is nothing to attribute. |

**Null in independent units (HK-021(z)).** 0c and 0d are the two nulls. "The oracle is a faithful
production decode at the right spot" ⇒ an unobstructed victim at −11…−6 dB decodes ≈ 100% (C1: 100/100
with E removed), and a −30 dB victim ≈ 0%: several dB below any FT8 decoder's threshold, and we already
score 0/24 at −21 dB (S1b). **At a true rate of 0.99, falling below 0.90 in 100 trials has probability
< 10⁻⁴; at a true 0.00, exceeding 0.20 is impossible without leakage.** Both rows pass where the null holds.
A position-mapping or leakage defect moves the rate by far more than the tolerance, so they fail on one.
The level sits well below threshold on purpose: an oracle with the exact position and OSD may legitimately beat
production's threshold, and 0d must not false-STOP on that.

---

## §3. Reading rows

### 3.1 Per cell (only cells with `prod` ≤ 0.20 — "excluded" — are read)

Let `o = orc_E` hit rate in the cell.

| cell reads | predicate | meaning |
|---|---|---|
| **M1** | `o ≤ 0.20` | offered at the right spot, production's own extraction + LDPC **still can't decode it**: the bits are corrupted |
| **M2** | `o ≥ 0.80` | offered at the right spot it **decodes**: the bits are intact, and the loss is upstream |
| **MIXED** | `0.20 < o < 0.80` | partly both |

### 3.2 Overall (only if ROW 0 is silent)

| row | predicate | reading |
|---|---|---|
| **ROW 1 — M1** | **every** excluded primary cell reads M1 | **Extraction.** The loss is in bit formation, and this defect and D-001 limb 2 are the same work item. ⇒ Captain: whether to reopen limb 2 with **≈ 4.30 pp** as its business case. `coherent_llr.c`'s ROW 0g is still uncleared, so it is not a ready remedy. |
| **ROW 2 — M2** | **every** excluded primary cell reads M2 | **Upstream.** The bits survive, and production never offers the spot. ⇒ The candidate-budget family is **CLOSED ×2**. Report and stop; reopening needs the Captain's ruling and a new pre-registration naming the specific stage and parameter, **FP primary**. |
| **ROW 3 — MIXED / SPLIT** | otherwise | **Report the cell map** (Δ × `X`, with `o`, `prod`, BER). Back to the Architect and the Captain. 🛑 **No averaging across cells, and no choosing the "majority" mechanism.** A split by Δ or by `X` is itself the finding. |

```python
excluded = [c for c in primary if c.prod <= 0.20]
if row0_fires:                               verdict = "ROW 0 STOP"
elif all(c.orc_E <= 0.20 for c in excluded): verdict = "ROW 1 M1"
elif all(c.orc_E >= 0.80 for c in excluded): verdict = "ROW 2 M2"
else:                                        verdict = "ROW 3 MIXED"
```

**Can every row be returned?** `o` ranges over [0, 1], and ROW 0c/0d prove the oracle can land at either
end. **ROW 1** needs every excluded cell ≤ 0.20, **ROW 2** every one ≥ 0.80, and **ROW 3** anything else.
All three are reachable and mutually exclusive (a cell can't be both ≤ 0.20 and ≥ 0.80). ✅

**Readout quantum.** N = 100 ⇒ 0.01 per trial. The binomial SE is ≈ 0.02 at `o` ≈ 0.05 or 0.95 and
≈ 0.04 at the bars. **A clean M1 cell (`o` ≈ 0.05) crosses 0.20 only on a ~7σ excursion, and a clean M2
cell (≈ 0.95) crosses 0.80 the same way.** Cells truly near a bar will land in MIXED, and that is the
honest reading for them. **Nothing here sits near its quantum.**

⚠️ **Why "every cell" and not a majority:** a majority rule would let one mechanism outvote a real split
by geometry. That is the outcome-chosen reading HK-021(y) forbids. Strict unanimity pushes every
disagreement to ROW 3, where the map is reported whole.

---

## §4. Reporting only — gates nothing, can change no row

1. **Per cell:** `prod`, `orc_E`, `orc_0` hit rates, with n.
2. **BER (continuous, 0–174 bits), paired per trial:** median and IQR of `BER(orc_E) − BER(orc_0)`
   per cell. **M1 predicts a large positive shift; M2 predicts ≈ 0.** This is the dynamic-range metric the
   `NBR-A` closure asked for. It **supports** the row and must not **override** it.
3. **Strong-victim cells** (F +5 dB, `X` = +3): the same per-cell table.
4. **Where the corrupted bits sit** (only if any cell reads M1 or MIXED): BER split by codeword position
   class (payload vs parity, as `hard_decision_ber` indexes them). Descriptive.
5. 🛑 **Not in scope, even as reporting:** `ft8_coherent_llr_at` at the oracle position. Whether a
   coherent extractor **fixes** an M1 is a **remedy** question for the next arm, and its own ROW 0g is still
   uncleared. Adding it here would turn a mechanism arm into an untested remedy trial.

---

## §5. What this can't see — named now

1. **One scene, one interferer, synthetic AWGN.** Live pairs vary in drift, fading and timing, and ROW 1/2
   is a statement about **this** geometry.
2. **The oracle is given the true position exactly** (to the lattice). **An M2 means "production never
   offers the spot"**. It does not say whether that is candidate ranking, sync-peak capture by E, tile
   suppression or a post-decode filter. **That split is the next pre-registration's job**, if the Captain
   reopens the family.
3. **An M1 does not mean every extraction change would help.** It means the magnitude-only single-symbol
   metric is corrupted at the true position, which is the premise of limb 2, not proof of its remedy.
4. **No live data is read.** `DENSITY-LIVE`'s clearance was for one live test and is **not** used here.

---

## §6. Deliverables (QA)

1. `qa/rr-study/density-mech/density_mech.py`, importing `f-nbr-a`, `n1-…`, `r2-…` modules **verbatim**.
   §1.3's position mapping is written out in the script's header **and** in the results JSON.
2. `results/density_mech_result.json` (both determinism runs), ROW 0a–0e values and verdicts, per-cell
   table, verdict, §4 items. **Q-prefix synthetic only**; run the NFR-021 scanner on the output **and**
   the report prose anyway.
3. QA report in `qa/rr-study/`, usual `qa-to-architect` form.
4. 🛑 **No `src/`/`native/` change.** If any entry point turns out not to be callable from the shipped
   DLL, **STOP and report**. Don't route around it with a different binary. Commit by path; push waits on
   the Captain (HK-033).

---

## §7. Sequence after the verdict — pre-registered

| verdict | next |
|---|---|
| **ROW 1 (M1)** | Architect → Captain: reopen D-001 limb 2 with ≈ 4.30 pp as its business case? The first question would be clearing `coherent_llr.c`'s ROW 0g. **No fix is specced from this arm.** |
| **ROW 2 (M2)** | Architect → Captain: the candidate-budget family is CLOSED ×2. Reopen it for a narrowly named stage, or accept the gap. **Nothing is specced without that ruling.** |
| **ROW 3** | Cell map to the Architect and Captain. No averaging, no re-cut. |
| **ROW 0** | Report and stop. No re-cut of bars, cells or levels. |

---

## §8. Predictions — written before any trial of this arm is run

🔴 **Weight these accordingly. Per the ledger my MECHANISM calls have been wrong, including this very defect:
the 2026-08-27 `NBR-A` spec put ROW 1 (M1) at 55%, and the 2026-09-16 assessment leaned M2 at 0.60.** I
have now held both positions on it.

| # | prediction | P | class |
|---|---|---:|:---:|
| — | **Mechanism reads M2** — carried from the density assessment §8 #2 (2026-09-16), **the scored one** | 0.60 | H-mech |
| 1 | ROW 0 silent | 0.75 | H |
| 2 | Verdict **ROW 1 (M1)**, given ROW 0 silent | 0.35 | H-mech |
| 3 | Verdict **ROW 2 (M2)**, given ROW 0 silent | 0.25 | H-mech |
| 4 | Verdict **ROW 3 (MIXED)**, given ROW 0 silent | 0.40 | H-mech |
| 5 | Paired BER shift at Δ = 6.25, `X` = +3 has median **≥ 20 bits** | 0.65 | H |

⚠️ **#2–#4 contradict the carried 0.60 on M2, and I'm saying so rather than hiding it.** The 0.60 was
read off C2's recovery at 31.25 Hz. Thinking about the physics since, E's tones at Δ = 6.25–12 Hz land
**directly** in 6–7 of F's 8 tone bins at 3 dB more power, which is hard to square with intact bits. The
carried 0.60 **stays the scored one**; the new numbers are recorded as informed.

**Resolved while drafting — assessment §8 #3** ("LLR extraction is not callable from the shipped shim
without a Developer change", 0.65, C): 🔴 **MISS.** `rebuild_shim.bat` on `main` exports
`ft8_extract_llrs_at`, `ft8_coherent_llr_at` and `ft8_ldpc_decode_llrs`, and the names are present in the
built DLL. **I asserted a feasibility gap I could have checked in one grep**, for the third time in this
programme. ROW 0a is the binding check.

---

## §9. Status

- ➡️ **DISPATCHED to QA** on Captain authority (*"1. go"*).
- 🔴 **Bars fixed:** ROW 0c ≥ 0.90 · 0d ≤ 0.20 at −30 dB · 0e ≥ 6/9 excluded · per cell M1 ≤ 0.20 / M2 ≥ 0.80 ·
  unanimity for ROW 1/2. They do not move after the result.
- 🛑 **Subtract-resynthesise DEAD · candidate-budget CLOSED ×2 · no remedy trial in this arm.**

---

## §10. ACCEPTANCE RULING — 🛑 VOID. The oracle is not production, and the data prove it

**Architect, 2026-09-18T14:36Z.** QA report `2026-09-18-1433-qa-to-architect-density-mech-result.md`,
commit `10045691` (`qa/e4-bench`, not pushed). QA ran the spec exactly as written, ROW 0 was silent, and
the rows mechanically return **ROW 1 (M1)**. **I am not accepting it, and the fault is in the spec, not the
run.**

### 10.1 The contradiction

| cell | `prod` (production, E present) | `orc_E` (oracle at F's true position, E present) |
|---|---:|---:|
| primary Δ 18.75, `X` +1 | **94/100** | **0/100** |
| strong Δ 12.0, `X` +3 | **100/100** | **0/100** |
| strong Δ 18.75, `X` +3 | **100/100** | **0/100** |
| primary Δ 6.25 / 12.0, `X` +1 | 35 / 15 | 0 / 0 |

`orc_E` is **0/100 in all 12 cells**, with a paired BER shift of **0.30–0.44 (53–77 of 174 bits)**,
including cells where **production decodes F from the same audio every time.** The arm's whole premise
(§0, §1.2) was that the oracle is *"production's own extraction + LDPC, at the right spot"*. **If it were,
it could not fail 100/100 where production succeeds 100/100.** So `orc_E` = 0 is **not** evidence that
the bits are corrupted *for production*, and an M1 reading drawn from it is **void**.

### 10.2 Why — two things production does that the oracle does not (checked in `ft8_shim.c` on `main`)

1. **Production is TWO-PASS** (`K_MAX_PASSES` = 2). After pass 0 it **attenuates each decoded signal's
   waterfall tiles** (active tone bin ±1) by a **soft SNR-scaled factor**: none at ≤ −5 dB, full at
   ≥ +15 dB (`K_SOFT_SUPP_SNR_MIN/MAX_DB`). It then re-runs candidate search with a wider net. The oracle
   extracts from the **unsuppressed pass-0 waterfall**. ⚠️ Suggestive, **not established:** E at +8 dB
   (strong cells) gets ≈ 65% attenuation and production recovers F at 12 and 18.75 Hz. E at −5 dB (primary)
   gets **none**, and production mostly fails.
2. **Production extracts where its own search puts the candidate**, which need not be F's *true*
   position. At primary Δ 18.75 / `X` +1, E is unsuppressed (−5 dB), yet production decodes F 94/100 while
   the oracle at the true position reads BER ≈ 0.30. **That cell is unexplained by (1) alone.** A candidate
   at a lattice point displaced away from E is one candidate explanation. **I am not asserting it.**

### 10.3 🔴 My design failure, logged

**ROW 0 proved the oracle can say YES (E removed) and NO (−30 dB). It never checked that the oracle
agrees with production where production succeeds WITH E present, which is the only condition the arm
reads.** That check was free: `prod` was measured in the same cells. **HK-022's question, "what error
could this ROW 0 NOT detect?", has the answer "exactly this one."** It is the fourth predicate-design
failure in two days (`E4-STAGE2` ×3), and it is the same shape: a precondition validated off the axis the
verdict reads on.

### 10.4 What the run DOES establish — descriptive, not a verdict

- ✅ **Single-pass magnitude extraction at the victim's true position is completely corrupted by a
  neighbour ≥ 1 dB stronger within 18.75 Hz**: 0/100 in every cell, BER 0.30–0.44, against 100/100 with
  E removed on the same noise. That is a true fact about `ft8_extract_likelihood()` on an unsuppressed
  waterfall.
- ✅ **Production's recovery of such victims, where it happens, therefore runs through something the
  oracle omitted**: pass 1, a displaced candidate, or both.
- ✅ The instrument itself is sound for what it measured: 0a–0d all clean, position mapping confirmed
  (`orc_0` 100/100 everywhere), byte-identical reruns.

🛑 **Not established: M1, M2, or which production stage loses F in the cells where it is lost.**

### 10.5 Amendment A1 — the diagnostic that decides between §10.2's explanations (dispatched)

Same harness, same seeds, same binary. **Cells:** the five with `prod` > 0 (primary Δ 6.25/12/18.75 at
`X` +1; strong Δ 12/18.75) **plus** primary Δ 12 / `X` +3 (bench geometry, `prod` 0) as the excluded
reference. N = 100.

| measurement | how |
|---|---|
| **`prod_p0`**: production with pass 1 disabled | `ft8_set_decode_params(k_min_score_pass2 = 1 000 000, <production's own osd_corr_threshold>, <production's own osd_nhard_max>)`, which leaves pass 0 untouched and admits no pass-1 candidate. Confirm via `ft8_get_last_candidate_counts` that pass 1 had **0** candidates. **Restore production's values afterwards and assert them.** |
| **production's F position** | for every `prod` hit, F's reported `(freq_hz, dt)` from `ft8_decode_all`, and its offset from the true position |
| **`orc_P`**: oracle at production's position | `ft8_extract_llrs_at` at production's reported position (same §1.3 time-origin mapping) → `ft8_ldpc_decode_llrs`, E present |

**Readings, per cell with `prod` ≥ 0.80** (primary 18.75/+1; strong 12, 18.75):

| reads | predicate | meaning |
|---|---|---|
| **A1-POS** | `prod_p0` ≥ 0.80 **and** `orc_P` ≥ 0.80 | production gets F **in pass 0 at a displaced position**. The oracle looked in the wrong place. |
| **A1-PASS1** | `prod_p0` ≤ 0.20 | production gets F **only via pass 1** (suppression and/or the wider net) |
| **A1-OTHER** | anything else | report |

🛑 **A1 carries no M1/M2 verdict.** It says which production route recovers F where F is recovered, which
is what a valid re-spec of this arm has to model. **A1-PASS1 would mean the oracle needs pass-1's
suppressed waterfall, which no export provides.** That is a `native/` change (HK-011) and a Captain
decision. **A1-POS would mean the oracle must search a neighbourhood, not a point**, which needs no
Developer.

### 10.6 Ledger

**All `DENSITY-MECH` §8 predictions: UNSCORED, arm void** (the ledger's precedent for ROW E4). The carried
assessment §8 #2 (M2 @ 0.60) **stays open.** 🛑 **QA's note that "#2 (M1 @ 0.35) called it right" is
withdrawn with the verdict.** Design failure logged (§10.3).

### 10.7 Status

- 🛑 **VOID. No M1, no M2. Do not cite "the loss is in extraction".**
- ✅ Descriptive fact (§10.4): pass-0 extraction at the true position is fully corrupted by a ≥ 1 dB-stronger
  neighbour ≤ 18.75 Hz.
- ➡️ **A1 dispatched to QA** (diagnostic, minutes, no `src/`/`native/`).
- ✅ **`DENSITY-LIVE`'s ≈ 4.30 pp is unaffected.** This arm is about where the loss happens, not whether.
