# RULING: #122 gate 4a, V2 FAILED on corpus P. Verdict, scope and the diagnostic

- **From:** Architect. **To:** Engineer (owner). cc QA, Captain. **Date:** 2026-10-03 ~14:20Z (HK-017, `date -u` read 14:18Z).
- **Spec:** `qa/rr-study/2026-10-03-1015-architect-to-qa-spec-122-gate4a-truncation-replay.md` with Amendment 1 (`45c1d016`).
- **Run:** Engineer, harness `9dd89f3f`, analyser `7690689d` (`eng/122-gate4a`, local). 11:39:10Z to before 14:17Z. Outputs: `artefacts/20261003_1139_122_gate4a_truncation_replay`.
- `git diff --stat -- src/ native/`: empty. Aggregates only (HK-037).

## 1. Verdict (as registered; not rewritten)

**Gate 4a: V2 FAIL on corpus P (1 074 of 1 075 cycles identical).** R 720/720, X17 464/464, X80 497/497 PASS. V0, V1 and V3 PASS (all eight arms exited 0, DLL pinned at the start and end of every arm, no orphan).

**Scope of the stop:** spec §5 says that if any validity row fails, *"no catch figure is reported; the report names the row and stops"*. That sentence covers the **whole report**, not only P. **The Engineer's reading is correct: no catch figure for any corpus.** V4′ was not evaluated, which is also correct, because V0–V3 stop first. Nothing here releases a catch figure. §4 says what could.

## 2. What the failure is

- One cycle (stamp `261001_112700`, list position 956). Arm F's final decode has 16 decodes. Arm T's final decode has 15. The difference is exactly one decode, at **1 731 Hz, DT 0.9, SNR −11**, which is present in F and absent in T. T has nothing that F lacks. Numeric fields only.
- **Two readings, and the data cannot separate them:**
  1. **Shared state:** the early decodes of this cycle, or of earlier ones, changed the final decode. This is the claim V2 exists to test. Leads for the mechanism, **not hypotheses I am pricing** (ledger LT2 lesson):
     - The managed path drops a decode whose rendered text repeats an earlier one in the same call (`Ft8Decoder.cs:510/528`, a per-call `seen` set). It also drops any text that fails `IsPlausibleMessage` (`:534`).
     - The rendered text depends on the process-global callsign hash table, and arm T fills that table from the early decodes first.
     - So a hash resolved earlier can make two texts identical (one is then de-duplicated away), or can change plausibility.
  2. **Run-to-run nondeterminism** in the decode, unrelated to the early decodes. That would be its own finding: the flag-OFF ordinary decode has so far been bit-identical wherever it was tested (Stage A E1; the 10-01 replay's V4, 4 298/4 298).

## 3. Diagnostic: APPROVED, labelled post-registration, and it does not change §1

| # | What | Output (counts and booleans only; HK-037) |
|---|---|---|
| D1 | Re-run **arm F on P**, fresh process, same child list and order | per cycle, numeric multiset identical to the original F: N/N. **If F does not reproduce itself, the V2 failure is nondeterminism, and that becomes the finding** |
| D2 | Re-run **arm T on P**, fresh process | per cycle, T's final multiset against the original T, and its early multisets against the originals: N/N |
| D3 | Inside D1 and D2, for stamp `261001_112700` only, computed **inside the matching function**: the number of decodes whose text contains an unresolved hash placeholder; whether the 1 731 Hz decode's text (in F) equals the text of any other decode in that same call (in T); whether it passes `IsPlausibleMessage` in each arm | booleans and counts. **No text, no hash of text** |

- **Order:** D1 first (≈ 10 min). Then D2 (≈ 65 min) and D3 within them.
- **Exclusive PC, as in the main run** (CPU rule). D1–D3 are code committed before they run.
- 🔴 **When it runs is the Captain's decision.** He said he would decide the PC order at 14:40Z: the B2 build, QA's T2′ replays, the keying-latency test, and #122 step 1 are all waiting. My recommendation is **D1 first, because it is short**: it says at once whether we have a determinism problem, which would matter to every replay-based acceptance in the programme, Stage B's included.

## 4. What happens after the diagnostic (decided now, so the result cannot steer it)

- **If D1 shows F is not reproducible:** gate 4a's V2 is void as a test of shared state. I write it up as a determinism finding. Whether catch figures may then be reported, labelled descriptive, is a **new ruling**.
- **If F and T each reproduce, and D3 shows a text collision or a plausibility change:** the shared-state effect is real, and the claim *"an early decode loses nothing by construction"* is **false**. The rate here is 1 decode in 1 cycle of 1 075, on one corpus. Step 4's build spec would then have to protect the final decode: for example, the final decode runs with the hash table as it was before the early decode, or de-duplication across batches is defined differently. Catch figures, if the Captain wants them, are then reported as *"descriptive, from a run whose V2 failed on P (1/1 075)"*, never as a gate result.
- **If F and T each reproduce and D3 shows neither:** the mechanism is unexplained. I rule again then, and do not guess.

## 5. Predictions

**TR5 (V0–V4 all pass the first time, 0.65): ❌ MISS** (V2 on P). Scored now, ledger updated in the same edit. TR1–TR4 and TR6 stay **unscored** until a catch figure exists, if one ever does.
