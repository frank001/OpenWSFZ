# `THRESH-A` — acceptance ruling: **`T2` ACCEPTED**, two descriptive corrections, and the §3.6 decision note for the Captain

**Architect, 2026-09-13 11:17Z** (`date -u`, HK-017). Branch `arch/thresh-a`.
Docs-only; `git diff --stat origin/main -- src/ native/` empty.

Accepts: QA's `qa/rr-study/2026-09-12-1756-qa-to-architect-thresh-a-result.md` (QA branch
`qa/thresh-a-result`, `79cc9187`, zero `src/`/`native/` diff), against the spec
`2026-09-12-1724-architect-to-qa-spec-thresh-a-isolated-threshold-locus.md` (`32e44313`).

---

## 1. Verdict

**`T2` fires, and I accept it.** At the isolated weak-signal threshold, the loss is in bit
formation. Handing production the exact true cell recovers essentially none of its misses.

I recomputed it independently from QA's per-cycle JSON
(`artefacts/thresh-a/_out/thresh_a.json`, in QA's worktree), with my own tally rather than QA's
`analyse.py`:

| check | result |
|---|---|
| `\|M\|` / `\|H\|` (production misses / hits in `R*`) | **546 / 704**, as reported and as the spec predicted from NT's table |
| `F_BP` on `M` | **1 / 546**; CP95 `[0.005%, 1.016%]` (scipy `beta.ppf`, exact). `CP95_hi < 0.20` ⇒ **T2** |
| `F_BP` on `H` (ROW 0d) | **704 / 704**; `CP95_lo = 99.48% ≥ 0.90`. PASS |
| `(path, crc_ok, success)` on `M` | `(-1, 0, F)` 529 · `(1, 1, F)` 16 · `(0, 1, T)` 1 |
| `(path, crc_ok, success)` on `H` | `(0, 1, T)` 704 |

**The forced leg is not an echo of production.** ROW 0d's `704/704` alone could not tell "an
independent forced read that works" from "a forced read that reproduces whatever production did".
The miss population can. On 17 of the 546 cycles where production had no genuine decode, the forced
read produced a CRC-valid codeword: 1 correct and 16 wrong. An echo would give 0 on both. So the
`T2` reading measures what the true cell's LLRs can support, not a copy of production.

ROW 0a/0b/0c/0e/0f are accepted as reported. 0b reproduces NT's committed 21-rung table exactly.
0c was re-derived from the shim's own constants, not from the spec's algebra, which is the better
check.

## 2. Two descriptive corrections to QA's report §5 (HK-022). Neither touches the gate.

**(a) `ldpc_errors` is unsatisfied parity checks, not bit errors.** QA's report reads it as
*"hard-decision errors against a 174-bit codeword"*. It is `bp_decode`'s `*ok` out-parameter
(`native/ft8_lib_vendor/ft8/ldpc.c:130`ff, `min_errors` over `ldpc_check`), handed out unchanged
by `ftx_ldpc_decode_llrs` (`native/ft8_lib_build/patched/ft8/decode.c:967`). It counts the
**unsatisfied parity checks out of 83** at BP's best iteration. QA's *"mean 7.35"* also averages in
the 16 `path = 1` cycles, whose count `decode.c:1001` resets to 0. **Over the 529 `path = −1`
cycles alone: mean 7.57, median 7, range 1–20 unsatisfied checks of 83.**

**(b) The 16 `path = 1` cycles are wrong-payload decodes, not CRC failures.** QA's report reads
them as *"OSD engaged, CRC/payload still failed"* and says OSD was engaged on 16 cycles. Both are
wrong:

- OSD runs on **every** BP non-convergence (`decode.c:969-979`), which is all 545 failing cycles.
- `path = 1` is set only when OSD returns a CRC-valid codeword **that also passes the nhard/corr
  gate** (`decode.c:978-1000`).
- **All 16 have `crc_ok = 1`.** The payload is what fails.

⇒ **At the true cell, OSD at depth 2 recovered 0 of 546 threshold misses and produced 16
CRC-valid, gate-passing wrong decodes** (2.93%, CP95 `[1.68%, 4.72%]`). The gate is untouched,
because `T2` is BP-only and `k_any = k_BP = 1` either way. It is recorded because it is the
threshold-population face of `OSD-FA-A`: OSD adds only false accepts here.

**Minor, not a correction.** §5 calls the single BP recovery *"almost certainly"* a candidate-stage
pass-over. Production could equally have read a different lattice cell for that signal. It is
`1/546` either way; cite it as "not established".

**Action for QA:** fix both in place in §5 of the report, where they are stated, before
`qa/thresh-a-result` is pushed. Do not add a note at the top instead (HK-022). Pushing still
needs the Captain's go (HK-033).

## 3. Prediction scorecard (on the record, spec §5)

| | predicted | outcome |
|---|---|---|
| Row | T3 0.45 · T1 0.30 · **T2 0.25** | **T2** |
| `Δ50` | `[0.3, 1.5]` dB | **0.000 dB**, outside my interval |
| ROW 0d | PASS, 0.85 | PASS, `704/704` |

My §5 reasoning for down-weighting T2 was *"the cell is clean, which argues against T2."* That was
wrong: a clean cell at threshold is exactly where LLR quality binds. My categorical calls stay
poorly calibrated.

## 4. Comparator note: WSJT-X's S1b margin is not AP-assisted (Architect, outside the arm)

`THRESH-A` makes no WSJT-X claim (spec §4, HK-026), and this section does not change that. It
checks one assumption behind the spec's §0 *"existence proof"*: that WSJT-X's `13/24` at the S1b
−21 dB rung is not a priori (AP) decoding.

- `%LOCALAPPDATA%\WSJT-X - FT991A\WSJT-X - FT991A.ini:45` reads `NDepth=3`. That is Deep, and the
  AP flag is not set. WSJT-X stores "Enable AP" as bit 16 of `NDepth`; that is my reading of its
  settings convention and was not verified against WSJT-X source this session.
- **Zero AP-marked decodes (`a1`…`a7`) in all 30 R&R `wsjt-all.txt` files** in QA's worktree,
  including all six `4584900d` sweeps.

⇒ WSJT-X's threshold margin comes from non-AP decoding: its bit metrics and/or OSD depth. That is
the same locus `T2` points to for us.

## 5. Consequence (spec §3.6)

- **No candidate-stage work may be described as a threshold treatment.** No candidate-stage
  follow-up arm is licensed.
- C-GAP-D's ruling stands untouched: the coherent-LLR limb may not be described as a D-001
  treatment.
- The decision note below goes to the Captain.

---

## 6. Decision note for the Captain (spec §3.6, one page)

**What we learned.** When a single weak signal sits alone in noise, our decoder usually finds it.
What fails is reading its bits. Pointing the decoder at the exact right spot recovers 1 of 546
misses and buys **0.0 dB** of sensitivity. The loss is in how the 174 bit likelihoods are formed
from the audio: single-symbol, magnitude-only, non-coherent. It is not in finding the signal.

**What that rules out.** Tuning candidate search (sync thresholds, ranking, extra passes) will not
lower our weak-signal threshold.

**What is on the shelf.** One remedy has been built: the coherent bit-likelihood extractor (Route B2
limb 2, `native/ft8_lib_vendor/refine/coherent_llr.c`). It is **not shippable**. Its own
pre-registered check, ROW 0g-2, still fires: after the Phase B fix its bits are still worse than
production's, by a median of 3 bit errors (CI95 `[−5, −2]`). The board's rule is that it may be
neither advanced nor called dead while that row fires.

**How much it could matter for live decode rate.** Not much, on the evidence we have:

- C-GAP-D sized the whole "better bit extraction" lever against the live 20m gap at **≈7 pp of the
  ~42 pp gap** (`G(3)` = 6.995 pp, CI95 `[6.897, 7.172]`). That is the "16% ceiling".
- Most live misses sit far beyond the correction threshold. In W1's 135-miss live sample the
  median bit-error rate was 44.0%, against 11.3% that BP+OSD can correct, and about 97% were never
  correctable by any error-correction change. A threshold improvement buys only the fringe.

**The fork (your call):**

| option | what it means | cost |
|---|---|---|
| **A. Reopen Route B2 on sensitivity grounds** | Treat weak-signal sensitivity as a goal of its own, with its own acceptance test and no D-001 claim. The first job is closing ROW 0g-2's residual 3-bit gap. | A research-and-build programme with a failed precondition on record, `src/`/`native/` work (HK-011), and a live payoff bounded at ≈7 pp. |
| **B. Park the isolated threshold** | Accept the weak-signal gap to WSJT-X for now and point decode-rate effort elsewhere. | Nothing now. It can be reopened if weak-signal DX becomes a priority. |

**Architect recommendation: B.** The only remedy has failed its own precondition, and the ceiling
on live decode rate is small. Choose A only if you value decoding at the noise floor for its own
sake, as opposed to raising the live decode rate.
