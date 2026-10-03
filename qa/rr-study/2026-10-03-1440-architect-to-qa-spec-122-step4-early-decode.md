# SPEC: #122 STEP 4. An extra early decode at 13.0 s, shown on the panel before the slot ends (phase 4a: panel only)

- **To:** QA (owner: the OpenSpec change, `tasks.md`, the Developer handoff; HK-015/HK-000). cc Captain. **From:** Architect. **Date:** 2026-10-03, written from 14:33Z by `date -u` (HK-017).
- **Branch:** `arch/122-latency` (local). Docs only: `git diff --stat -- src/ native/` is empty. **The build is `src/`** (and `native/` only if R4's option (ii) is chosen), so it needs a separate Developer session (HK-011).
- **Authorised:** the Captain, 2026-10-03 (Architect's window, about 14:31Z): *"1. agreed"*. That answered the Architect's recommendation to write the step-4 build spec with these defaults: the automation ignores early decodes the final decode does not confirm; the panel shows them marked; cut point x = 2.0 s; panel-only first, automation after step 2. **#122 is no longer only "on hold" for this step.** The Developer starts when the global hold lifts (after the Engineer's D1, Captain).
- **Evidence:** gate 4a, accepted (`2026-10-03-1435-architect-122-gate4a-report-ruling.md`; report `eng/122-gate4a` `df4ec892`). Every figure is **descriptive** (V2 failed on P by one decode; the figures were released by the Captain).
  - At **x = 2.0 s**, an early decode had **C ≈ 0.98** of the full-window decodes on four corpora (P 0.984, R 0.983, X17 0.988, X80 0.987).
  - It took about as long as the full decode (`t(2.0)` ≈ 527 ms on P against `t(0)` ≈ 534 ms), so those decodes appear **≈ 2 s earlier**.
  - It also produced early-only decodes: `S_unc` (uncorroborated) 0.22–0.47 per 100, and `S_corr` (corroborated by the live WSJT-X) 0.26–0.96 per 100.
  - One final decode in 20 175 was lost on P when early decodes ran first (cause under diagnosis, D1–D3).

## 1. What changes, in one paragraph

When a cycle's window holds **13.0 s of audio** (156 000 of 180 000 samples), the daemon decodes a **copy** of that partial window, zero-filled to full length, exactly as gate 4a did. It publishes the result to the **decode panel only**, as an **early batch**, with each row marked *early*. At the slot end, the **ordinary decode runs exactly as today** and publishes batch 1 (and batch 2 with the flag ON) to every consumer, as today. On the panel, a final row that matches an early row **confirms** it: the mark is removed, with no duplicate row. An early row that no final row confirms stays visible, marked *unconfirmed*. **ALL.TXT, external reporting (UDP), the QSO automation and the cycle-audio archive see nothing of the early batch.** Their behaviour stays as today, byte for byte.

## 2. Requirements

| # | Requirement |
|---|---|
| **R1 trigger** | The early decode starts when the window being filled reaches `180 000 − 12 000 × earlyDecodeCutSeconds` samples. It uses a **copy**; capture continues into the original window, untouched. QA locates the hook in `src/OpenWSFZ.Ft8/CycleFramer.cs` (the window producer, `:54` onwards) or the pump, with FILE:LINE |
| **R2 never in the way** | If the decoder is still busy when the trigger fires (e.g. the previous cycle's residual pass, flag ON), the early decode is **skipped** for that cycle, never queued and never delaying anything. Skips are counted and logged per cycle. The ordinary decode at the slot end is never delayed by an early decode. If an early decode is still running when the window closes, the ordinary decode waits for it (at most one early decode's time, ≈ 0.6 s). That wait is measured (A3) |
| **R3 the early batch reaches the panel only** | A new panel event (or a field on the existing one) marks the rows *early*. Not ALL.TXT, not the external-reporting channel, not the answerer or caller channels, not the archive (`DecodePump.PublishFirstAsync`/`PublishSecondAsync`, `DecodePump.cs:134-182`, unchanged). Decode-filter admission (`AdmitNewValues`) is **not** run on early rows: the final batch admits as today |
| **R4 the final decode is unaffected by the early decode** | 🔴 For every cycle, the final decode's outcome must be what it would be without the early decode. Gate 4a showed the early decode can change it through process-global state (one in 20 175). The build guarantees this by one of: **(i)** running the early decode with callsign-hash-table **writes suppressed** (it reads, it never adds), if the shim already allows that; or **(ii)** a native snapshot/restore of the hash table around the early decode (new shim number). QA and the Developer pick, with FILE:LINE. **Acceptance A2 tests the guarantee, not the mechanism** |
| **R5 confirm and mark on the panel** | Match final rows to early rows inside the cycle by **same message text and \|Δf\| ≤ 10 Hz**, one-to-one (the Test B rule). Matched: the early row is replaced by the final row (no duplicate, no flicker into two rows). Unmatched final rows are added as today. Unmatched early rows stay, marked *unconfirmed*. The marks are visual and accessible (text or `aria` label, not colour alone) |
| **R6 config** | `decoder.earlyDecodeEnabled`, **default `false`** for this change (the Captain sets the default after A3). `decoder.earlyDecodeCutSeconds`, default **2.0**, accepted range 0.5–3.0. Read once per window, as the subtraction flag is. Config POST is an overlay on `main` (HK-035): tests cover a partial update that leaves both fields as they were |
| **R7 log line** | One per cycle, in the file log (ms stamps): `Early decode: n=…, elapsedMs=…, skipped=…`. Aggregates only, no message text |
| **R8 flag OFF ⇒ nothing changes** | With `earlyDecodeEnabled = false`, the pump, the panel events, ALL.TXT, UDP and the QSO services behave exactly as before: same calls, same order (characterisation tests, as two-stage publish's P-9) |

**Phase 4b (NOT in this change; outline only).** The QSO automation acts on early decodes after step 2 (progressive batches). Per the Captain's default, an early decode that the final decode does not confirm is **dropped from the automation's state** when the final batch arrives. Its own spec comes after step 2.

## 3. Acceptance (mechanical, pre-registered; HK-021, with each stop scoped to the outputs it guards, sibling (ab))

| Row | Predicate | Guards |
|---|---|---|
| **A1 flag OFF identity** | Existing suite green. New characterisation tests: with the flag OFF, the panel events, ALL.TXT lines, UDP datagrams and QSO-channel batches for a fixed set of recorded cycles are **identical** to the pre-change build (outcome fields) | the merge |
| **A2 final decode unaffected (R4)** | Replay of gate 4a's corpus **P** list (`selection_p.json`, its SHA asserted), flag ON: per cycle, the final decode's numeric multiset (freq, dt, snr) = the same build with the flag **OFF**, in a separate fresh process. **PASS iff N/N.** If D1 has shown that the flag-OFF decode does not reproduce itself, A2's reference becomes "within D1's measured run-to-run difference", stated before A2 runs | R4 only |
| **A3 live timing (station, receive only, ≥ 2 h on 40 m, flag ON for both features, as shipped otherwise)** | From the R7 log line and the existing `Cycle` line: (a) the early batch is published at **median ≤ 13.7 s** into the slot (13.0 + about 0.55 s decode + margin); (b) early decodes skipped (R2) in **≤ 5 %** of cycles; (c) the final batch 1's median publish time is no more than **+0.10 s** later than the same session's cycles in which the early decode was skipped or disabled. QA designs (c) mechanically, e.g. alternating the flag per hour, read back each time | timing claims only |
| **A4 consistency with gate 4a** | On A2's replay, the early batch's catch against the final decode `C(2.0)` is within **±0.01** of gate 4a's 0.984 (P). A miss means the product's early path is not the path gate 4a measured | the gate 4a figures' transfer |
| **A5 panel behaviour** | Playwright (HK-007): early rows appear marked; a confirming final row replaces its early row (one row, not two); an unconfirmed early row keeps its mark; keyboard and screen-reader text carry the mark. Plus `live_verify_9_axes.py` (decode-panel filtering policy: this change touches the panel's decode rows) | the UI |

**Stops are scoped:** A2 failing blocks the merge (R4 is a requirement). A3 failing blocks the **default-ON** decision, not the merge (the flag ships OFF). A4 failing labels the figures; it blocks nothing by itself, and comes back to the Architect.

## 4. Limits and what is not claimed

- 🛑 **No decode-rate claim.** Early-only decodes corroborated by WSJT-X (`S_corr`) are shown on the panel, but they reach no log. Whether they should reach ALL.TXT is a separate decision for the Captain, after A3.
- Replay-based figures (A2, A4) are not the live path. A3 is the live check.
- CPU: one extra ordinary decode (≈ 0.5 s of one core) per cycle, inside the capture window, while a residual pass may be running. R2's skip rule and A3(b)/(c) measure that.
- The partner's view is not changed. This is about **our** screen. Step 1 (the WSJT-X comparison) is still the Engineer's, queued.

## 5. Predictions (blind; scored at the acceptance ruling)

| # | Prediction | P | Class |
|---|---|---:|:---:|
| SD1 | A2 passes N/N on the first build | 0.65 | H |
| SD2 | A3(a): the early batch's median publish ≤ 13.7 s | 0.75 | H |
| SD3 | A3(b): skips ≤ 5 % of cycles on a 40 m evening with the flag ON | 0.70 | H |
| SD4 | A4: C(2.0) within ±0.01 of 0.984 | 0.70 | H |
