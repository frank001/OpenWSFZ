# `SUB-FEAS` Stage 2 (labelled diagnostic): ruling. **The gain survives the replay control: net ≈ +8.9 pp**

**Architect, 2026-09-28 ~11:00Z** (HK-017). Branch `arch/subtraction-feasibility`. Docs only:
`git diff --stat origin/main -- src/ native/` is empty. Rules on QA
`qa/rr-study/2026-09-28-1025-qa-to-architect-sub-feas-stage2-diagnostic-results.md` (`qa/sub-feas`).
Captain, 2026-09-28: *"proceed with stage 2."* Stage 1's FAIL stands and is not revised.

## §1. The control the result was missing

QA's `ΔR` counts a decode as **new** when it is absent from the **live** `ALL.TXT`. GAP-LOCATE's ROW 0e
showed that a DLL replay can decode more than the live path did. Replay-vs-live gain would be credited
to subtraction. QA's ghost check also had no null: with ~24 subtracted signals per cycle, *any* decode
lies close to one of them.

**Architect control** (read-only, QA's own `stage2` functions, counts only per HK-037; script
`replay_control.py` kept in the Architect's scratchpad): 150 split-B cycles (seed 20260928), each decoded
**twice** with the same pinned DLL, text-dedup, "new" rule and corroboration rule:

| leg | new | corroborated | ΔR (pp of 3,668 WSJT-X) | distance to nearest subtracted signal: median, ≤ 5 Hz |
|---|---:|---:|---:|---|
| **ORIG**: original PCM, no subtraction | 43 | 28 | **0.76** | 76.5 Hz, 0.0 % |
| **SUB**: W\* = 0.32 residual | 367 | 354 | **9.65** | 25.0 Hz, 13.0 % |
| **NET (SUB − ORIG), paired per cycle** | | | **+8.89 pp, 95 % CI [8.01, 9.75]** | |

- The replay reproduces the live path closely: 16.0 DLL decodes per cycle vs 15.8 live (2,370 / 150).
  Replay-vs-live accounts for **0.76 pp**, not the gain.
- ORIG's new decodes serve as the missing ghost-check null. They sit a median 76.5 Hz from the nearest
  subtracted signal, with none within 5 Hz. The subtraction-revealed decodes cluster at 25 Hz. **That is
  the signature of neighbours being unmasked**, which fits GAP-LOCATE's LB (interference-limited loss,
  with another transmission dominating the cell).
- The sample's SUB reading (9.65 pp) agrees with QA's full-run 10.07 [9.69, 10.44]. The control's
  sample is 150 of 1,051 cycles.

## §2. Ruling

- **Accepted, with the control attached:** on this corpus, one subtraction pass recovers **≈ 8.9 pp net**
  (of WSJT-X's decode count) of WSJT-X-corroborated decodes the live decoder missed. In these cycles
  OWS decoded 2,370 against WSJT-X's 3,668, so this closes **roughly a quarter** of the gap.
  Uncorroborated additions: 3.66 % of new (QA); 🛑 uncorroborated ≠ false positive.
- **Stage 1 FAIL is not revised.** Its X metric was a weak proxy (§2 of the 00:40Z ruling). Stage 2 measured
  the outcome directly.
- **This is a labelled diagnostic, not a licensed gate.** It carries its limits:
  1. **One corpus:** one 40m night, direct-CODEC, `decoding_improvement` `51e40b55`.
  2. **Offline replay:** the live path adds `IsPlausibleMessage` and a real-time budget. The Python fit
     costs ~3.9 s per signal. Production needs a native implementation that fits all subtractions inside a
     15 s cycle. **Feasibility of that is not measured.**
  3. **One pass only.** Multi-pass is untested, in either direction.
  4. **FP exposure unmeasured** beyond the uncorroborated share.

## §3. What it licenses: nothing by itself. The Captain's decision

🛑 **The subtract-and-resynthesise BUILD prohibition still stands.** Lifting it is the Captain's call.
**Architect recommendation: lift it for ONE scoped build arm**, with its own pre-registration:
(a) a native implementation of *this* method (data-aided fit + drift + W = 0.32 s envelope; not the June
code) behind a config flag, default OFF; (b) an offline acceptance on a **second, independent** corpus,
reproducing ΔR_net ≥ 1.0 pp against the ORIG control, with a runtime bar inside the cycle budget; (c) only
then, a live A/B endurance run. HK-011 applies: `native/` needs a Developer session, via QA handoff.

## §4. Scored (ledger rule 1)

§9 #5 was VOID (conditional on a PASS that never occurred). **No prediction existed for a diagnostic
Stage 2.** The ledger records that the Architect's §5 recommendation expected at best a modest result
("if NONE, close for good"), and that the outcome was a large WIN. **This is the first result in this
programme where the Architect's hypothesised expectation erred in the PESSIMISTIC direction.**
