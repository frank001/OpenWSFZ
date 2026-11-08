# Developer task: COH-FALLBACK (A' step 4) - the fallback runs after the last ordinary batch, in parallel, and publishes in a batch of its own (flag-gated, default OFF)

To: Developer. From: QA. Stamped 2026-10-21 by `date -u` (QA's writing time ~17:0xZ). Captain's go: 2026-10-21, Architect's window: *"go with the timing-only redesign"* (spec §14). **This authorises a build and a replay. Merge (HK-010) and default ON stay the Captain's. `src/`/`native/` work needs your separate session (HK-011).**
Base: **`feat/coh-fallback-stage1` at `1405ada4`** (your Stage 2 build; shim version as built there). Continue on that branch or a branch off it (say which). No push (HK-033).

## Read first (the design is the Architect's; this file is the handoff)
`git show arch/coherent-limb2:qa/rr-study/2026-10-07-1330-architect-to-qa-spec-coh-fallback-step3-build.md`: **§14 (Amendment 4) as changed by §15 (Amendment 5)**. §13 explains why the Stage 2 design failed A3' (the fallback contended with batches 2 and 3; the both-published batch-2 delay p95 was 496 ms against a 50 ms bar; see §13 and A13.8). The method (R1, R2', R3, R4', R5, R6'', R8, R9, R10, R11, R12', R13) is unchanged; `ft8_coherent_fallback_at` and the F1b code are not to be touched (QA's A2 results depend on them).

## What changes, against 1405ada4

1. **R6''' / R7''' (replaces R6' / R7'): start and publish.** Today the fallback starts once batch 1 is out, on one thread (`Ft8Decoder.cs:875-892`, `RunCoherentFallback`), and its decodes are held for the last supplementary batch.
   - **Start only after the cycle's last ordinary batch has been handed off:** batch 3 on Deep (after the third pass, whether or not batch 3 had any decodes), batch 2 on Normal. **Nothing of the fallback may run concurrently with pass 0, the residual pass or the third pass.**
   - **Publish as a batch of its own after every ordinary batch:** batch 4 on Deep, batch 3 on Normal, delivered only if non-empty. The same per-cycle `seen` dedup, `IsPlausibleMessage`, noise-suppression filter and R6'' apply. A fallback text already published in ANY earlier batch of the cycle is not published again.
   - With the flag OFF nothing changes (R13): same native calls, outputs, order and batch numbers.
   - Deadline: the fallback shares the 13 s `SubtractionCycleBudget` (`Ft8Decoder.cs:108`). Unfinished work is abandoned, never queued, counted (R12'). Re-derive `CoherentFallbackPublishReserve` (`:217`) for the new position and say what you chose and why (FILE:LINE).
2. **R14 (new): the extra batch must reach the QSO services and the panel.**
   - `LateBatch` and the QSO channels (`Program.cs:345-348`: "up to 3 batches per cycle", capacity 8; `LateBatch.cs:55`, "3 batches x 2 cycles + 2 spare") must carry **up to 4 batches per cycle** with the flag ON.
   - **Record the capacity arithmetic with FILE:LINE** and update the comments that say 3. **With the flag OFF, the capacity and the behaviour are unchanged** (R13): say how you keep that, and test it.
   - Unit tests for the 4-batch case: no drop, order kept, and the reply-deferral logic (the latest-whole-signal guard) applied to batch 4 exactly as to any late batch. `LateBatchQsoTests` / `LateBatchReplayTests` / `QsoLateBatchRigs` are the existing rigs.
   - The panel's batch handling must accept batch number 4 (check every place that assumes 2 or 3, and list them).
3. **R15 (new): parallel over candidates.**
   - The cycle loop splits the eligible candidates across `EffectiveSubtractionThreads` worker threads (`Ft8Decoder.cs:93`; 8 on the station).
   - The per-candidate native code has no mutable global state (`coherent_fallback.c:31`); **verify that claim for the thread-local candidate list and decoded-payload snapshot** (`Ft8Decoder.cs:616-619`, which is thread-local to the thread that called `ft8_decode_all`): the workers must not read thread-local state of another thread. Say how you hand them the snapshot.
   - **Determinism is required.** Results are gathered **in candidate order** before F1b, dedup and R6'', so the published set and its order do not depend on scheduling. A new or changed native export is allowed if you need a per-candidate or deadline/cancel entry point: bump the shim, keep `ft8_coherent_fallback_at` and the F1b code byte-identical, and say what you changed.
   - The hash table: the fallback must not write it from several threads (it writes only through the ordinary message decode, after the gather, in candidate order, as now).
   - Abandonment at the deadline: workers stop between candidates; what was finished and is in candidate order before the first unfinished candidate is published or counted as the spec of R12' says. State your rule (FILE:LINE) and test it. No queuing of leftover work.
4. **Counters and the cycle log line (R12').** Keep the Stage 2 line, one per cycle, aggregates only, no text, and **add**: `workers=...`, `fbWallMs=...` (fallback wall time from its start), and `batch4PublishMs=...` (publish time of the fallback batch from decode start; `-1` when no fallback batch was published). Make the same fields reachable from `Replay81` (the existing `--cohfb-out` path). Do not use `-1` as a time anywhere QA would average it (the §13 error): use an explicit `published` flag next to it.
5. **R11 provenance tag** unchanged (`Path = 2` for fallback decodes, `:765`); add the **batch number** to the replay harness result so QA reads batch 4 without guessing.
6. **Replay harness access** unchanged (`SetCoherentFallbackEnabled` / `CoherentFallbackEnabled`).

## Tests and hand-back
- Unit tests: flag default/overlay (carried); the fallback does not start before the last ordinary batch is handed off (a recorded-order test, not a timing test; **no fixed delays**: wait on a positive condition, `OpenWSFZ.TestSupport.Poll.*`, `TESTING_STRATEGY.md` §11); batch 4 on Deep and batch 3 on Normal, only if non-empty; dedup against earlier batches; R6''; **gather-in-candidate-order determinism** (the same input with 1, 2 and 8 workers gives the same published list and order, with a scheduling perturbation); abandon-never-queue; R12' line content including the new fields; flag-OFF identity; batches 1-3 unchanged; the R14 4-batch tests. Synthetic callsigns only (NFR-021).
- State: the unfiltered `dotnet test OpenWSFZ.slnx` command and result; the native self-test and ASan/UBSan **after** your last native edit; Windows `libft8.dll` / Linux `libft8.so` SHA-256 values if the native changed; `git diff --stat` against `1405ada4`; FILE:LINE for each design choice above; confirmation that `ft8_coherent_fallback_at` and the F1b code are unchanged (or exactly what changed). **No timing conclusions: QA measures.**
- **Flaky-test watch:** QA pushes the branch early to get the macOS result (about 6 minutes); thread-count and ordering tests must not depend on the machine's core count.

## Acceptance (QA; mechanical; you do not run these)
All against the Captain's chosen fresh 40 m night, Deep, `selection.json` frozen with its SHA before any decode, arms OFF, ON, ON-repeat, a pin at the start AND the end of every arm (V1, fail-closed re-hash).
- **A2(e) 100/100** on the parallel build (QA runs it first).
- **A3'' (a):** batches 1-3 identical ON vs OFF, N/N. The only exception is a cycle where an ordinary pass hit `SubtractionCycleBudget` in exactly one arm (from the ordinary-pass counters, counted and listed by slot). Any other difference fails the row.
- **A3'' (b):** median of the signed (ON - OFF) publish time, batch 2 and batch 3 separately, read only on cycles where both arms published that batch; block-40 bootstrap, B 10,000, seed 20261007. FAIL if CI_lo > 50 ms for either batch; PASS if CI_hi <= 50 ms for both; OPEN otherwise (goes to the Captain). The p95 and its CI are descriptive.
- **S4-T:** batch-4 publish time and fallback wall time (median, p95, max), descriptive and mandatory. **SG2 predicts median wall <= 0.5 s.**
- **D-GO':** CI_lo(NET) >= 1.0 pp. **U':** set by the Captain after the OFF arm, from QA's dated U' note (U'0 split into tested-and-absent and untestable, U'_max = 0.30 x U'0, half-width, and the line "U'_max is / is not <= 0.042").
- **R14 live check before default ON** (not a merge gate): one live session on the station with the flag ON shows batch 4 reaching the panel and both QSO services with no channel drops (daemon log); QA specifies it after the replay.
- Merge needs A1 (flag OFF identical), A2, A3'', the unit tests and the Captain's sign-off. Default ON needs D-GO', U'-OK, the R14 live check and the Captain's decision.
