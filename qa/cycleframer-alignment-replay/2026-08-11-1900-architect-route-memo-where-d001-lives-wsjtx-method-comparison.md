# Architect route memo — where D-001 actually lives, read against WSJT-X's method

**Author:** Architect
**Date:** 2026-08-11 19:00:25Z (mechanically derived, HK-017)
**Status:** 🔴 **MEMO ONLY — NOT A SPEC.** No gate is drafted. No `src/` change is recommended.
No pre-registration follows from this document. It exists to be ruled on.
**Prompted by:** Captain's question "look at the WSJT-X source code, look for the method, not
copying code from it — how can we resolve D-001?", plus the mid-turn correction below.

---

## 0. What this document is, and what it is not

It is a **route memo**: the D-001 pipeline laid out end to end, with every stage tagged by what
the programme has actually measured about it, read against how WSJT-X solves the same problem.

It is **not**:

- a spec, a gate, or a pre-registration (HK-021 does not apply because nothing here is gated);
- a `src/` recommendation in any direction (HK-011);
- a licence to reopen anything on the standing prohibition list (see §8).

🛑 **No number in this memo is new.** Everything cited is already on the board or in a committed
report, or is a code fact re-verified today against the current tree. Where I am reasoning rather
than citing, it is labelled **HYPOTHESIS**.

---

## 1. The correction that prompted this memo, and why it matters

I opened this line of work with the framing "D-001 sits in the decode stage, sub-stage
demodulation". The Captain's correction, mid-turn:

> *"remember the issue is before the decoder, not the decoder itself"*
> *"all the studies that have been done indicated that the decoder is not the issue, it even
> seems to be better?"*

**That is substantially right, and I had let a loose word do too much work.** "Decoder" has been
used across this programme to mean three different things. Separating them dissolves most of the
apparent contradiction:

| sense of "decoder" | what it covers | verdict | evidence |
|---|---|---|---|
| **(a) Error correction** | BP + OSD + CRC | 🛑 **RULED OUT, and it is genuinely strong** | `E` = 4.28 of 135 (W1, cross-validated by B.2's 5.69/4.45). Corrects to `B50` = **11.3% BER**. The missed population arrives at **median 44.0% BER** — ~4× the correction threshold, out where P(decode) ≈ 2%. D-009 swept 45 OSD grid points for **+0.109 pp**. |
| **(b) Demodulation** | candidate → symbol likelihoods | ⚠️ **where the failure is VISIBLE** | RC1/RC4 ROW 2: 87.9% of misses have a candidate present and still fail. 3.1% out-of-band / 8.9% no-candidate / 87.9% candidate-present-and-failed. |
| **(c) The whole native library** | `ft8_decode_all` end to end | ⚠️ ambiguous — this is the word that caused the confusion | — |

**So "the decoder is not the issue, it even seems to be better" is a defensible reading in sense
(a), and I should have said so plainly.** Our error-correction stage is not the weak link — it is
doing real work, correcting up to 11.3% BER, and no measurement anywhere in the programme shows it
inferior to WSJT-X's. The bits arriving at it are the problem.

🔴 **And that is the load-bearing observation, which I under-weighted until the correction.**
**44% BER is not "a weak signal". It is indistinguishable from noise** (50% is pure chance). A
signal that is genuinely present, genuinely spotted as a candidate, and demodulates to ~random
bits is the signature of **reading at the wrong place**, not of reading a faint thing at the right
place. Whatever is wrong is wrong *before* the bits exist.

⚠️ **One honest qualifier that cuts against the "better" reading:** every recovery figure is
measured against WSJT-X at `NDepth = 3` (Deep, top of range) while we run `K_MAX_PASSES = 2`,
candidate caps 140/200, and a hardcoded 200–3000 Hz passband. Part of the raw gap is depth/budget
asymmetry rather than capability. But that part has been **swept and measured small**: C.1 (cap
140→300→600) **+0.93%**, RC4 (`K_MAX_PASSES` 2→3) **+0.70 pp**, D-009 **+0.109 pp**. It does not
account for the gap.

---

## 2. The pipeline, end to end, with evidence status per stage

This is the useful artefact of this memo. Stages are in execution order. **Status is assigned from
measurements already on disk**, not from argument.

```
 [1] WASAPI capture ──► [2] CycleFramer ──► [3] PCM normalise ──► [4] FFT → uint8_t waterfall
                                                                          │
                                                                          ▼
 [8] CRC ◄── [7] BP + OSD ◄── [6] extract → LLR ◄── [5] find_candidates (3.125 Hz / 0.08 s lattice)
```

| # | stage | code | status | basis |
|---|---|---|---|---|
| 1 | Audio capture (WASAPI shared, 48.0 ppm device) | `WasapiAudioSource.cs` | ⚠️ **PARTIALLY TESTED** | Drift fix shipped and holds (+0.0 ppm vs a 48.0 ppm chain, `be5960a`). But **no zero-drift control exists in any corpus.** |
| 2 | Cycle framing to UTC grid | `CycleFramer.cs` | ⚠️ **RULED IN as a mechanism, UNQUANTIFIED live** | See §5 — this is the live thread. |
| 3 | PCM normalise to RMS 0.20 | `Ft8Decoder.cs:52` | 🛑 **RULED OUT, PERMANENTLY** | P2 ROW 2: `P` = **0.007 pp** across **±18 dB**. Not mispriced. |
| 4 | **FFT → magnitude waterfall** | `ft8_shim.c:1185-1189`, `decode.h:21-30` | 🔴 **NEVER TESTED BY ANY ARM** | See §3, §4. |
| 5 | Candidate search | `decode.c:264-285` | ⚠️ mostly RULED OUT as a *budget* issue | C.1 +0.93%, RC2 dead twice, RC1: candidates ARE generated in 87.9% of misses. |
| 6 | Symbol extraction → LLR | `decode.c` `ft8_extract_symbol` | ⚠️ failure visible here, **cause upstream** | 44% BER on misses. |
| 7 | BP + OSD | `decode.c`, `ldpc.c` | 🛑 **RULED OUT** | `E` = 4.28; D-009 +0.109 pp over 45 points. |
| 8 | CRC / message decode | `message.c` | 🛑 **RULED OUT as a loss path** | Hashed callsigns resolve to `<...>` and are **never discarded** — costs message TEXT only. |

🔴 **Read the table as a whole and one thing jumps out: stage 4 is the only stage in the entire
pipeline that no D-001 arm has ever touched.** Every arm — C.1, C.2, RC1–RC4, D-009, P1a, P2, P3,
T1, T2, S.1, S.1r, X1–X5, W1 — has operated on stages 3, 5, 6, 7 or on observational `ALL.TXT`
statistics. **Stage 4 has been treated as a fixed given for the whole programme.**

---

## 3. What WSJT-X does — the method, not the code

**Sourcing, stated honestly:** WSJT-X source is **not on this machine**. `D:\WSJT\wsjtx` is a
binary install (`bin/`, `plugins/`, `share/`). The only Fortran locally is
`C:\Temp\ft8_lib_headers\ft4_ft8_public\`, which is the *message-packing* half (callsign→c28,
CRC14, hashcodes) — encode side only, nothing about demodulation. `ft8b.f90` and `sync8.f90` were
read from the SourceForge master tree.

🛑 **Licence constraint: WSJT-X is GPLv3; ft8_lib is MIT. Method only, never code.**

> 🔴 **CORRECTION added 2026-08-11 after this memo was written — do not reason from the original
> wording, which claimed copying "relicenses our decoder" and was "the only legally available
> route."** The premise was wrong: **OpenWSFZ itself is AGPL-3.0** (repo-root `LICENSE`), not MIT,
> and AGPL/GPL are compatible — so the bar was never a *legal* one. **The prohibition now rests on
> the Captain's explicit policy ruling (2026-08-11): only MIT-compliant/permissive third-party code
> may be incorporated; no GPL-derived code, from WSJT-X or anywhere.** The conclusion is unchanged
> and absolute; only its basis was wrong. Full statement in the programme document §2.1.

### 3.1 Where the two pipelines agree

Both start with a coarse search over a **magnitude** time-frequency grid, and the search windows
are comparable:

- WSJT-X `sync8`: **±2.5 s of lag** (`JZ=62`, ~0.04 s steps), 3.125 Hz bins (`df=12000.0/NFFT1`),
  metric = max over three Costas 7×7 arrays (`icos7 = 3,1,4,0,6,5,2`).
- ft8_lib `ftx_find_candidates` (`decode.c:279`): `time_offset = -10 … +19` blocks ≈ **−1.6 s to
  +3.0 s**, 3.125 Hz effective bins at `freq_osr = 2`.

✅ **The coarse search is NOT the gap.** I checked this specifically because "we don't look far
enough in time" was my first instinct, and it is wrong.

### 3.2 Where they diverge — and it is one architectural decision

For **each surviving candidate**, WSJT-X **goes back to the original audio and builds a second,
private, per-candidate front end**:

| step | WSJT-X (`ft8b.f90`) | OpenWSFZ |
|---|---|---|
| per-candidate downconvert | `ft8_downsample(dd0,newdat,f1,cd0)` → **complex baseband** `cd0(0:3199)`, phase retained | **nothing** — re-reads the one shared magnitude waterfall |
| coarse time | `idt = i0-10 … i0+10` | candidate's grid index, as found |
| fine frequency | `ifr = -5 … +5`, `delf = ifr*0.5` Hz, then **re-downsamples at the refined frequency** | none |
| fine time | `idt = -4 … +4` at 1/200 s = **5 ms** | none |
| refinement metric | `sync8d` — **coherent** correlation against the Costas arrays | n/a |
| bit metrics | 1-, 2-, 3-symbol **coherent** sums — `abs(cs(g(i2),ks) + cs(g(i3),ks+1))` — → `bmeta/bmetb/bmetc`, normalised by σ (`normalizebmet`), scaled `scalefac = 2.83` | single-symbol max-log over 8 magnitude bins |
| passes | `ipass = 1..4` over `llra..llrd`, then AP passes (`apmag = maxval(abs(llra))*1.01`) | 2 passes, one metric |

**Final achieved resolution: WSJT-X ≈ 0.5 Hz / 5 ms. OpenWSFZ 3.125 Hz / 0.08 s.**
**≈6× coarser in frequency, ≈16× coarser in time.**

🔴 **The keystone is the per-candidate complex downconversion.** Fine refinement and coherent
multi-symbol metrics are both *consequences* of holding complex baseband. Neither can be bolted
onto a `uint8_t` magnitude waterfall — there is no phase to refine against and nothing to sum
coherently. **We have no equivalent of this stage at all.**

---

## 4. Three cheap options that look available and are not

Each of these was checked today against the current tree specifically because it would have been a
small, fast win. **All three are dead.** Recording them so nobody re-derives them.

**(a) 🛑 `WATERFALL_USE_PHASE` is a dead switch, not a disabled feature.**
`decode.h:21` has `// #define WATERFALL_USE_PHASE`, and flipping it swaps `WF_ELEM_T` from
`uint8_t` to `waterfall_cpx_t`. It looks like a one-line unlock. **`grep USE_PHASE decode.c`
returns zero hits — there is not one `#ifdef` branch in the decoder body.** Enabling it yields a
struct with a `.phase` field that **no code ever reads**, at 4× the memory. The coherent path is
not switched off upstream; it was never written.

**(b) 🛑 `ft8_decode_multi_symbols()` is not the coherent metric it resembles.**
It is dead code — declared (`decode.c:124`), defined (`decode.c:1059`), **no call site in either
tree** (re-verified today). And even wired up it computes
`WF_ELEM_MAG(a) + WF_ELEM_MAG(b)` — **it adds dB magnitudes**. WSJT-X sums the *complex* values and
then takes the magnitude. These are different operations; ft8_lib's is a non-coherent
approximation. Wiring it up does **not** buy WSJT-X's multi-symbol gain.

**(c) 🛑 Framing offset alone cannot be a ~42 pp effect — we already have the number.**
`CycleFramer.cs:184` records the measured cost of grid misalignment: **−3.8% of decodes at 1 s of
offset, −29.8% at 2 s.** The 48 ppm drift defect is fixed and the framer re-anchors every cycle.
A residual of tens of milliseconds is worth a fraction of a percent on that curve. ⚠️ **But see
§5 — that figure was measured on replay, where both legs share framing, and there is a live
observation it does not comfortably explain.**

---

## 5. The one genuinely live upstream thread — and a tension worth naming

This is the part of the Captain's steer I cannot close from existing data, and it is the strongest
argument for *not* jumping straight to a front-end rebuild.

**The observation (2026-08-08, exploratory, no ROW — must not be cited as a result):**

| control | 20m | 17m |
|---|---|---|
| WSJT-X vs WSJT-X (self-consistency) | **99.6%** | 97.7% |
| **OpenWSFZ vs OpenWSFZ** (same build, same antenna, same device) | **94.2–94.4%** | **99.6%** |

**Two OpenWSFZ instances running the identical build on the identical antenna disagreed with each
other 5.6% of the time on 20m — and 0.4% on 17m.** Two explanations were tested and **both ruled
out**: it is not density (flat 93.0–94.7% across all five 20m quintiles) and not run-length drift
(flat 93.3–95.4% across all 11 hours). The remaining candidates are **band/signal-population** vs
**capture start alignment** — the 20m pair started **21 minutes apart**, the 17m pair started **in
the same second**. The cheap decisive test was run (`qa/endurance/2026-08-08-capture-phase-selfconsistency-test.py`)
and landed **ROW C, INCONCLUSIVE** — self-consistency 99.65% → 97.58%, delta −2.07 pts, inside the
pre-declared 97.0–99.0 dead band. Direction favours the start-phase hypothesis; **it does not clear
the bar and must not be reported as implicated.**

**The tension, stated plainly:** §4(c) says 1 s of framing offset costs 3.8%. Yet two instances
that should both be UTC-grid-anchored disagreed by 5.6%. Those do not sit comfortably together.
A candidate reconciliation exists in our own code: `CycleFramer.cs:190` documents that the clock
read at resync runs ahead of the sample being placed by **up to 2048 samples (171 ms)** of
unconsumed chunk, plus any host scheduling lag, and the correction is *"a monotone improvement at
every lag"* — i.e. reduced, **not eliminated**. Two processes with different scheduling luck can
therefore sit persistently tens to ~100+ ms apart.

🔴 **HYPOTHESIS (labelled as such, not a finding) — framing phase and lattice coarseness may be
ONE defect, not two.** Our time lattice is **0.08 s**. A persistent inter-process framing
difference of ~100 ms is **more than one full lattice cell.** With no sync refinement, that moves
a signal into a different cell, and P3 measured that moving by **⅓ of a cell** recovers
**`S_all` = 4.27 pp** — the largest single-arm effect in the programme. On this reading:

- the framing error is upstream (the Captain's steer), **and**
- it only *costs* anything because stage 4/5 has no refinement to absorb it (my framing),
- and WSJT-X is immune to the same error because it refines to **5 ms** — a 171 ms framing bias is
  ~34 refinement steps, trivially absorbed, and **invisible** to it.

**This is a hypothesis with a plausible mechanism and one inconclusive test behind it. It is not
established. It is the single best-motivated untested thing on the board.**

---

## 6. Routes, with trade-offs

Presented for a ruling. **I recommend the order below, and the reason is that route A is cheap and
could make route B unnecessary or re-scope it — not that A is more likely to be the answer.**

**Route A — settle the upstream framing question first. Observational/replay, no `src/`.**
Determine whether live framing phase differs between processes and by how much, and whether that
difference tracks decode disagreement. The instrumentation question ("can we even see our own
framing phase per cycle?") must be answered before a design. **Cheapest by a distance; the only
route that does not commit engineering effort; and it directly tests the Captain's steer.**
⚠️ HK-021(i) applies — the 08-08 test was already inconclusive once, so an underpowered repeat is
an instrument failure, not a null, and the power question must be settled *before* arming.

**Route B — per-candidate complex-baseband refinement (the WSJT-X method, reimplemented).**
A new stage between `ftx_find_candidates()` and `ftx_decode_candidate()` (`ft8_shim.c:1314-1335`):
retain the cycle PCM, mix/decimate per candidate, coherent Costas correlation over a fine (Δf, Δt)
grid, feed the refined position downstream. **B1** = refine position only, reuse existing magnitude
extraction. **B2** = full coherent multi-symbol LLRs off the baseband.
✅ **In its favour:** it is the only route that addresses stage 4, the one stage never tested; it is
P3's own stated conclusion (*"refine inside the decoder, not by a union bolted outside it"*); and
it does not carry P3's false-positive problem — `X_guard` = 0.897 is an artefact of running five
decoders and unioning outputs, whereas refinement runs **one** candidate through **one** scoring
and CRC pass.
🛑 **Against:** it is the largest piece of engineering the programme has contemplated; it is native
C; it depends on `C:\Temp\ft8_lib_headers`, which is **outside version control** (verified intact
today, but a `C:\Temp` clear makes the library unbuildable and no commit records why); and it
should not be started before Route A, because if framing phase is a first-order term then B's
sizing changes.

**Route C — `K_FREQ_OSR`/`K_TIME_OSR` 2→4.** Halves the lattice to 1.5625 Hz / 0.04 s. Still no
refinement, still no phase, 4× waterfall cost, and lands nowhere near 0.5 Hz / 5 ms.
🛑 **Explicitly barred on P3's evidence** — an OSR change earns its own pre-registration with **FP
as the primary metric**. Listed for completeness as the blunt fallback, **not recommended**.

---

## 7. What binds any route

- 🛑 **`subtractft8` — subtract-and-resynthesise — terminates the WSJT-X pipeline, and that limb is
  DEAD for us.** Three builds, three reverts, **−17 pp at worst.** Recorded here explicitly because
  anyone reading WSJT-X's decoder end to end will find it and try to "complete the method". **Do
  not.**
- 🛑 Input scaling/normalisation/AGC/equalisation — CLOSED (P2).
- 🛑 The candidate-budget family — closed twice (RC2; C.1 bounded at +0.93%).
- 🛑 Spectral locality — RETIRED PERMANENTLY (X5, 2026-08-11).
- 🔴 **HK-011** — any `src/` route: QA proposes and stops, a separate Developer session runs
  `opsx:apply`, the Captain reviews the diff.
- 🔴 **HK-021(k)** — any gate that follows must evaluate the row under **both** outcomes of every
  pre-gate check; if the row is unchanged either way it is a **diagnostic**, not a gate.
- 🔴 **Binary identity** — pin `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`, SHA
  `f2f30c89…`, shim `20260033`. First free shim integer is **20260038** (G2's).

---

## 8. Architect calibration note (required, per `MEMORY.md`)

🛑 **I have deliberately put no magnitude prediction on any route in this memo.** My record is
DIRECTIONAL **1/3**, ranges **8/15**, and the last four magnitude calls all missed with the
**interval right and the actionable implication wrong**. A recovery figure from me here would be
decoration and would risk anchoring a future gate. Any arm must derive its own bar mechanically.

⚠️ **I also want one drafting error on the record before it propagates.** I opened this session
asserting "D-001 is in the decode stage, sub-stage demodulation" as though that settled the
locality, and began designing toward a decoder-internal fix. **The Captain's correction — that the
studies say the decoder is not the issue — was right, and the pipeline table in §2 is what I should
have produced first.** X3→X4→X5 was three consecutive arms with zero readings, all from Architect
gate-drafting; **this is the same failure one stage earlier — reasoning from a remembered framing
instead of going and laying the evidence out.** HK-018 exists for exactly this and I did not run it
until prompted.

---

## 9. For the Captain — the questions this memo exists to get answered

1. **Route A before Route B?** Or is the framing question sufficiently settled by the 08-08
   inconclusive test that you would rather spend the effort on the front end directly?
2. **Is Route B in scope at all?** It is materially larger than anything the programme has built.
   If the answer is no, that is a legitimate and clarifying outcome — the honest reading of §2
   would then be that D-001 has an identified architectural cause we are choosing not to pay for,
   which is a very different project posture from "still investigating".
3. **Does the open FP surge (4.24–4.90%) gate any of this?** Route B changes what reaches the CRC.
   You deferred FP on G2 ("we will look at FP later"); this route may not be able to defer it.
