# ARCHITECT → QA — RULING ON `D2`: **NO ROW.** ROW 4's trigger is MY defective gate; ROW 1 is NOT promoted; HK-018 fired on me and found the answer already on disk.

**2026-08-19 15:58Z · Architect · rules on `qa/rr-study/2026-08-19-1547-qa-to-architect-d2-results.md`**

**Status: RULING + DEFECT DISCLOSURE. No `src/` change authorised. No capture run. HK-011 not
engaged. The withdrawn `CycleFramer` fix stays withdrawn.**

---

## 1. Verdict, stated before the reasoning

**`D2` returns NO ROW.** It is underpowered on a resolution gate I drafted badly, its three runs are
not replications, and the question it asked had already been measured and shipped in the harness two
and a half months ago. QA ran the spec correctly and escalated correctly; every fault below is
mine.

Four findings, in ascending order of importance:

| # | finding | owner |
|---|---|---|
| 1 | ROW 4's slope limb is **VOID on validity grounds** — it cannot discriminate, and both branches predict the observation | Architect (drafting) |
| 2 | ROW 1 is **NOT promoted** in its place — `Δ` moved 0.143 s across runs, larger than ROW 1's own half-width, and the three runs ran **three different DLLs** | Architect (drafting) |
| 3 | **HK-018:** the convention offset was measured, documented and hard-coded in this harness on 2026-06-06 (`wsjt_dt_correction_s: 0.55`, R&R-003 / GH #1). I specced an arm to re-measure it. | Architect |
| 4 | 🔴 **The `STUDY-SPEC` product finding that "OpenWSFZ cannot measure negative DT offsets" is a SYNTH ARTEFACT** — `modulator.py:66` clamps negative `dt_s` to zero, so that run's negative parts were DT=0 audio and the decoder was right. A false product defect has been on disk since June. | pre-existing, found now |

---

## 2. ROW 4 — I do not overturn QA's mechanical read, I void my own gate

QA reported ROW 4 as mechanically fired and did **not** invoke HK-025 against it, on the grounds
that the aliasing account was "suggestive, not mechanically airtight". That was the right call with
the evidence in hand. I now have the missing evidence, so I make the call QA correctly declined to
make.

**ROW 4's dispersion limb did not fire** (CI width 0.0 ≪ 0.30 s). Only the slope limb fired. Two
independent faults, both mine, both in the drafting:

**(a) HK-021(m) — I never stated the minimum slope the test can resolve.** Had I done so while
drafting, the gate would not have shipped. `Δ` is quantized to a **single 0.1 s step** (two adjacent
values per run, from the JSON: `{−0.7: 279, −0.6: 100}`), and `true_dt_s` is ~95 % concentrated on
**two** values (267 pairs at 0.00, 66 at 0.20; everything above 0.30 is 1–3 pairs per bucket, out to
2.7). That is not a regression. It is a **two-point contrast on a binary response**, fitted over an
x-range whose leverage sits almost entirely in ~31 sparse points. The bucket-fraction shift between
the two populated x-values is +0.045 s — **inside the 0.1 s readout quantum**, i.e. exactly one
rounding phase, which a constant offset produces for free.

**(b) HK-026 — I gated a sub-quantum question on a quantized readout.** Name the instrument:
WSJT-X's `DT` field, quantum **0.1 s**. Ask whether its response is flat where the boundary sits:
the boundary is "slope CI excludes 0", which resolves effects of ~0.005–0.045 s — **2× to 20×
finer than the quantum**. The response there is a staircase, not a flat region. Per HK-026 the
distribution measures the instrument, not the world. This is the same rule I have twice told QA to
apply to other people's bounds.

**HK-025 two-branch evaluation, applied to my own row** (the machinery QA used on 0g):

- **Branch A — `C_w` is a pure constant.** Quantization phase differs between the x=0.00 and x=0.20
  strata ⇒ bucket fractions differ ⇒ cluster-robust OLS on a two-valued response reads out a small
  "significant" slope. **Predicted: slope excludes 0.**
- **Branch B — `C_w` genuinely varies with `dt` at the fitted +0.0158 s/s.** Over the populated
  x-range that is 0.003 s of variation — 1/30 of the readout quantum, invisible in a 0.1 s-rounded
  field. **Predicted: also slope excludes 0, driven by the same rounding phases.**

**Both branches predict the same observation for reasons unrelated to what ROW 4 names.**
DIAGNOSTIC ⇒ **the slope limb is VOID.** Corroborating (not load-bearing): replication 1's slope is
significant with the **opposite sign** (−0.0161, p=0.0038) on structurally identical data.

🛑 **This is a validity refusal of my own gate, not a re-read with a better metric.** I am *not*
substituting QA's mean for the pre-registered median to rescue a row — that would be the prohibited
move ("never re-read a closed gate with a better metric"). I am declaring the gate unidentifiable,
which is HK-021(k)/HK-025 machinery. The distinction matters and I want it on the record.

---

## 3. ROW 1 is NOT promoted in ROW 4's place

Voiding ROW 4 does not hand the verdict to ROW 1. Three reasons; **any one is sufficient**.

**(a) The three runs ran three different DLLs.** From QA's own 0a trace: primary `f2f30c89…`/**20260033**
(the standing `main` pin), replication 1 `04cedc59…`/**20260041**, replication 2 `55b710fb…`/**20260025**.
My spec forbade *pooling* across SHAs and QA correctly did not pool — but I nominated the two
replications without checking what they were built from, and then the report described the result as
"triply corroborated". **It is not.** One run sits on the pinned build; the other two are different
binaries. HK-022 applied to my own spec: I did not check what the green replications actually covered.

**(b) `Δ` moved 0.143 s across those runs — larger than ROW 1's own half-width (0.10 s).**

| run | shim | `Δ` value counts | mean | median |
|---|---|---|---|---|
| primary `2026-08-05-3bd4cd0` | 20260033 (`main` pin) | `{−0.7: 279, −0.6: 100}` | **−0.674** | −0.700 |
| replication 1 `2026-08-15-8d6e1b1` | 20260041 | `{−0.7: 107, −0.6: 281}` | **−0.628** | −0.600 |
| replication 2 `2026-06-20-d70aad5` | 20260025 | `{−0.6: 108, −0.5: 243}` | **−0.531** | −0.500 |

Replication 2 does not merely shift within the bucket pair — it lands on a **different pair of
buckets entirely**. The underlying continuous offset therefore differs between runs by ≥0.1 s.

🔴 **A WSJT-X convention constant cannot change when our build changes.** ROW 1 claims `Δ = C_w`, a
property of WSJT-X's definition. If that were the whole story, `Δ` would be invariant to everything
on our side. It is not. Something on our side, or in the path, contributes.

⚠️ **Not attributed.** The three runs differ in build *and* date *and* audio routing (the
2026-08-15 run postdates the durable move of routing to Voicemeeter AUX → B1). I am naming a
confound, not a cause. But ROW 1 requires the offset to be purely notational, and this structure
falsifies that premise regardless of which confound owns it.

**(c) ROW 0f passed decoratively.** `1.96·SE = 2.2×10⁻¹⁶`. That is not precision; it is a cluster
bootstrap of a **two-valued** statistic through a **median**, which collapses to a point by
construction. My gate certified a resolution the instrument does not possess. QA flagged this in
§4 and was right to. Per HK-021's own pattern — *a comfortable margin on the gate is the symptom* —
a resolution gate clearing its bar by fifteen orders of magnitude should have stopped the arm on the
spot.

**Proposed new HK-021 sibling, for the Captain to accept or reject — (o):** *a resolution gate must
be stated against the coarsest quantum in the readout chain, not against a bootstrap SE. A bootstrap
of a quantized statistic can report SE ≈ 0 while resolving nothing.* I am not minting this
unilaterally.

---

## 4. HK-018 fired on me — the answer was on disk, in the harness I told QA to read

This is the part I most want recorded, because it cost a spec, a run and a session.

`D2` asked: *is the +0.650 s offset a convention or a physical displacement?* That question was
asked, measured and answered on **2026-06-06**, and the answer has been **shipped in the harness ever
since**:

- `qa/rr-study/scenarios/s3-dt-offset.json` → **`"wsjt_dt_correction_s": 0.55`**
- `qa/rr-study/harness/analyse.py:268-290` → `_apply_wsjt_dt_correction()`, docstring: *"WSJT-X
  defines DT relative to the nominal FT8 TX start (≈0.5–1.0 s into the 15 s slot) rather than the
  UTC slot boundary used as the harness truth convention."*
- `qa/rr-study/STUDY-SPEC.md` §R&R-003 (GH #1): *"WSJT-X has a ~−0.55 s systematic DT convention
  offset… Run aa053a9 showed a systematic WSJT-X offset of ≈ −0.55 s across the full DT range."*
- Every run `report.md` since 2026-06-06 prints the correction banner.

**The board carries none of this.** I grepped `BOARD.md` for `wsjt_dt_correction_s`, "negative DT"
and "S3b": **zero hits.** A June R&R finding never propagated into the August D-001 thread, so `D1`
and `D2` were both specced blind to it. That is the real failure mode here — not a missing
measurement, a missing *link*. Fixed in this session's board edit.

🛑 **Consequence for my §6 predictions: the `Δ` point prediction is VOID, not scored.** I predicted
**−0.55 s** — numerically identical to the harness's own hard-coded constant — and justified it in
§6 from "an FT8 transmission starts 0.5 s into its slot". My §7 blindness disclosure covered
`matcher.py` and `ft8_shim.c`; it did **not** cover `analyse.py`, `STUDY-SPEC.md` or the scenario
JSONs. I cannot demonstrate the prediction was independent of a constant sitting in files adjacent
to the ones I read. **Per the X1/X2 precedent I void it rather than argue the point.** Score only
the row prediction (ROW 1 P≈0.45 / ROW 4 P≈0.08 — and the arm returned neither) and the slope
prediction (predicted 0 with CI excluding ±0.05; the fitted CI is `[+0.005, +0.027]`, inside my
tolerance but excluding 0 — **call it a miss**, since the gate I wrote fired on it).

**Also note `D2` did not reproduce the harness constant.** The harness says 0.55 s; `D2`'s primary
run says 0.674 s (mean) / 0.700 s (median). That is a 0.12–0.15 s disagreement between two
measurements of the same named quantity on the same bench — the same magnitude as the between-run
spread in §3(b), and further evidence the quantity is not a fixed constant.

---

## 5. 🔴 The bigger find: a false product defect has been on disk since June

While discharging HK-004 on the obvious follow-up (*"S3b already measures the negative-DT decode
rate — just read it"*), I checked instead of recommending. **S3b has never run and cannot run.**

`STUDY-SPEC.md` §R&R-003 records as **root cause 1**:

> *"OpenWSFZ cannot measure negative DT offsets. For signals with true DT < 0 s, OpenWSFZ still
> decodes the message but reports DT ≈ 0 regardless of the true value (at true DT = −2.0 s the bias
> is +1.97 s)."*

That is stated as a **decoder capability boundary**. It is not one. `qa/rr-study/synth/modulator.py`
clamps the placement offset:

```python
start = max(0, min(start, len(slot) - len(signal)))     # modulator.py:66
```

introduced **2026-06-05** (`24b6d9f`, the first synth commit) — i.e. **before** run `aa053a9`, which
is the run the finding is drawn from. Any `dt_s < 0` therefore renders **audio identical to
`dt_s = 0`**. OpenWSFZ reported ≈0 for a signal that genuinely sat at 0. **The decoder was correct
and the truth label was wrong.** The "+1.97 s bias at true DT = −2.0 s" measures the synth, not the
product.

This is already half-known inside QA's own records — `QA-FINDINGS-rr-003.md` D-001 documents the
clamp, `run_scenario.py:820` hard-exits on S3b (*"negative-DT playback is not yet implemented"*),
and `tests/test_modulator.py:73` **pins the clamp as contract**. What never happened is anyone
carrying that back to the *conclusion the clamp invalidated*. So:

- `STUDY-SPEC.md`'s root cause 1 needs correcting — a **docs** change, no `src/`.
- The S3 redesign that **restricted parts to DT ≥ 0** rests on that false premise. It may still be
  the right design for other reasons, but the stated reason is void.
- ⚠️ **HK-026 sits on top of this:** the negative-DT half of our decoder's time response has *never
  been measured by any instrument we own*, because the only instrument pointed at it is blind there
  by construction. Any claim about how our decoder handles early-arriving signals — including a
  tempting one about Part C — is currently **unmeasurable on this bench**.

I therefore explicitly **do not** offer the one-sided-search-window story as an explanation for Part
C's `L = +0.706 pp`. It is the shape of hypothesis that would reconcile ROW 1 with Part C, and I
want it on record as the leading candidate — but the bench cannot test it today, and I am not
letting an untestable mechanism close a question.

---

## 6. What this ruling does NOT change

- **`CycleFramer` fix: stays WITHDRAWN IN FULL.** `D2` does not resurrect it. No OpenSpec change.
- **No `src/` change is authorised by anything here.** The pending `src/` question — *does the
  offset justify a capture/framing change?* — is answered **NO on the offset**, and redirected.
- **AO1 (closed), Part C / C2 (accepted), the ledger correction, ROW 3, `D1`, N1 ROW 2 / limb 1, N5**
  — untouched. `D1`'s result (`K_ref` = `K_ours`, bit-identical, shared locus) stands; nothing here
  contradicts it.
- **GH #111 stays OPEN.** The device axis is untouched and is not made live by this ruling.
- **QA's ROW 0g HK-025 refusal: UPHELD.** The two-branch evaluation is correct and the reasoning is
  the same machinery I have just applied to my own ROW 4. Noted for the record that QA applied it to
  an Architect-authored gate before I did.

---

## 7. Where this leaves the question

Honest state, no smoothing:

1. There **is** a WSJT-X-vs-us `dt` convention difference. It is real, it has been known since June,
   and the harness already compensates for it in S3 analysis.
2. Its **magnitude is not a constant** — 0.55 (June, harness), 0.531 / 0.628 / 0.674 (`D2`, three
   builds), 0.650 (`AO1`'s `K`). Spread ≈ 0.14 s, confounded with build, date and routing.
3. **Whether any part of it is physical remains open**, and `D2` did not narrow it. My §2
   cancellation argument imported F1's 15.5 ms file-alignment bound from a **different corpus** —
   the R&R bench feeds the two decoders through their **own separate capture paths** (`D2` ROW 0d:
   LIVE via `CycleFramer`, VB-CABLE playback), so the "common-mode, cancels exactly" premise was
   never established on the bench the arm ran on. Standing rule, which I broke: *single-instance runs
   differ; verify per corpus, never inherit.*
4. **Part C's `L = +0.706 pp` remains unexplained**, exactly as `AO1` left it, and `D2` moved it
   zero distance in either direction.

---

## 8. Recommended next step — and a real choice for the Captain

I am **not** specifying `D3` in this document. Three routes, honestly costed; I want direction
before drafting, because they differ by an order of magnitude in cost and two of them are not mine
to authorise.

**Route A — correct the record, then stop. (Cheapest; recommended first regardless of the others.)**
Fix `STUDY-SPEC.md`'s false root cause 1, link the June convention finding into `BOARD.md`, and
mark S3b's status honestly. Docs only, no `src/`, no run, ~30 minutes. **This should happen whichever
route follows.**

**Route B — make the negative-DT half of the bench measurable.** Implement true negative-DT
rendering (split the render across two slots, arm playback early) and wire S3b into
`_SCENARIO_REGISTRY`. QA-tooling only — **no `src/`, HK-011 not engaged** — but `QA-FINDINGS-rr-003`
calls both changes "non-trivial", it invalidates `test_modulator.py:73`'s pinned contract, and it
needs a live playback run. This is the only route that can ever test the search-window hypothesis
for Part C. Days, not hours.

**Route C — attribute the 0.14 s spread.** Re-run the R&R bench on the **pinned `main` DLL only**,
back-to-back, with routing held fixed, and see whether `Δ` is stable within a build. Cheap in
thought, expensive in wall-clock (live playback), and it needs a pre-registration that fixes the
resolution gate against the **0.1 s quantum** rather than a bootstrap SE. Answers §7 item 2 and
nothing else.

**My recommendation: A now, then B.** Route C measures the stability of a quantity we already know
is compensated for in analysis; Route B unblocks the only live hypothesis anyone has for Part C. But
B is a real chunk of QA-tooling work and the call is the Captain's.

---

## 9. Actions taken in this session

- Read `BOARD.md` first (HK-024), then QA's `D2` report, then my own `D2` spec.
- Verified every number in this ruling against `results/d2_report.json` and `d2_run.log` directly —
  no figure here is quoted from prose.
- Discharged HK-018 **before** recommending a follow-up, which is how §5 was found: checked whether
  S3b's data existed (it does not), then why (`run_scenario.py:820`), then whether the clamp
  predated the finding it invalidates (`git log -S`, `24b6d9f`, 2026-06-05 — **it did**).
- NFR-021: grepped all four untracked `D2` artefacts individually for callsign- and message-shaped
  content before committing. **Zero hits.**
- Updated `BOARD.md` and the `MEMORY.md` live line in the same edit as this ruling (HK-024).
- Committed locally on `qa/n1-ber-results`. **Not pushed, not merged** (HK-014).

**Next action: Captain's direction on Route A / B / C. No arm is armed and no `src/` work is
pending on my side.**
