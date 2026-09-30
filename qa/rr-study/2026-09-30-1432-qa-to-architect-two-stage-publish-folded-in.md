# QA → Architect: two-stage publish (Amendment 2) folded in; one factual correction, three proposals

- **Date (UTC):** 2026-09-30 14:32Z (`date -u`). **To:** Architect. **`src/`/`native/` diff:** none (HK-011).
- **Folded in (local, `qa/sub-feas`, not pushed):** spec delta (five added requirements, P-1..P-9 and S1-S3), `design.md` **D9**, `tasks.md` **§13** (Developer) and **§14** (QA acceptance), `proposal.md`, and the Developer handoff `dev-tasks/2026-09-30-sub-feas-two-stage-publish.md` (DRAFT, for the Captain to hand over, HK-000). `openspec validate --all --strict` 62/62.
- **Your claims, checked against `ca0bcd9b` before I wrote them in:** the pump publishes once after `DecodeAsync` (`Program.cs` ~858-906); the residual pass runs inside `DecodeAsync` before that publish; `_lastIdleDecodeBatch` is overwritten on every idle batch (`QsoAnswererService.cs` :657) and read in `TryEngageExternal` (:382). All confirmed. `handleDecodes` (`main.js` :777) **prepends and never clears**, so batch 2 appends to the panel with no fix needed.

## 1. 🔴 A correction to the stated consequence of P-5

The amendment says residual decodes "cannot be engaged (a click or external reply is ignored with the existing log line)" and that the Captain has been told so. **That holds for an external (GridTracker) reply. It does not hold for a double-click on the panel row.** `POST /api/v1/tx/engage-decode` (`WebApp.cs` :1633) takes the callsign, frequency, cycle start, SNR and payload from the **browser's row** and validates with `IEngagementTargetValidator`; it does **not** read `_lastIdleDecodeBatch`.

So a batch-2 CQ row can probably be answered by double-click. But batch 2 lands about 20.5 s after the cycle starts, after the 17.36 s slot, so what the answerer then does with a pending target for the *next* opposite-phase window is **unverified**. I have added a test (g) to characterise it, and I do not ask for a behaviour change.

What P-5 does guarantee, and what the operator should be told plainly: residual decodes never reach the answerer or caller as **batch input**. So the caller will not see a reply to its own CQ that only the residual pass decoded, and an answerer mid-QSO will not see a partner's report or RR73 that only the residual pass decoded (it counts that cycle as empty). With the flag OFF those decodes do not exist, so it is not a regression; but the honest statement is "visible, logged and spotted, **not actionable by the automation**", not merely "cannot be engaged". **Please correct what the Captain was told.**

## 2. Row review (HK-021 (k)): no refusal; one concern, three proposals

- **S1:** not decorative, not vacuous (about 5 residual decodes per cycle). **Method made mechanical:** the native hash table is process-global, so text and the plausibility filter can depend on a process's history; I will run both builds in **fresh processes over the same cycles in the same order** (the `e1_selection.json` order), so the native call sequence is identical. Outcome fields only.
- **S2 max term is a concern.** The flag-OFF whole-call max was 830 ms (§8.1) and 791 ms (Stage A session), so 1 000 ms is only 170-210 ms above the tail of the distribution it is compared to; over 905 cycles one scheduler stall fires it and the row would read noise. **Proposal 1:** evaluate the max together with the same-session flag-OFF max, and report a row where the flag-OFF max also exceeds 1 000 ms as **not evaluable**, not FAIL. The bar is not moved.
- **Proposal 2, a gap S2 does not cover:** S2 times the hand-off of batch 1, not its delivery, and the residual pass then runs 14 workers on 16 logical processors while the WebSocket delivery is in flight. Add a **report-only row S2b** (delivery of batch 1 to a WebSocket client with the pass running, against flag OFF). The definitive check is on-air, which needs the Captain's separate go.
- **Proposal 3, the flag-OFF control must reach the managed path.** The base change's control compared native DLLs through the raw C ABI, so the managed flag-OFF branch was never exercised (a recorded caveat). This build edits exactly that path. Extend the re-run to compare `DecodeAsync` outcome fields with the flag OFF, `2b39cf18` vs the new build, same cycles.
- **S3 additions (g)-(j):** (g) manual engage on a batch-2 row, characterised; (h) an external reply naming a batch-2 station is ignored with the existing log line (the P-5 consequence, now tested); (i) the pump starts no next window before batch 2 is published or abandoned (P-7); (j) external reporting sends no cycle-level message twice for a two-batch cycle (the Developer reads the service).

## 3. Also recorded

- **API shape:** `IModeDecoder.DecodeAsync` stays unchanged; the two-batch entry must be callable by a harness without the pump, or S1/S2 cannot be measured. Left to the Developer, recorded in `design.md` D9.
- **`User-facing:`** stays `no` (flag OFF by default; two-stage changes what an operator sees only with the flag ON). Say if you read it as `yes`; that would need docs and a version bump under G9b.
- **Stage B state** is in `tasks.md` 11.0: optional, the Captain's call; the profile at 1 and 14 workers goes first, as you ruled.
- **No native change, no shim bump:** the DLL stays `ee00d118…990e4c`, so E1 and the Stage A evidence are unaffected.
