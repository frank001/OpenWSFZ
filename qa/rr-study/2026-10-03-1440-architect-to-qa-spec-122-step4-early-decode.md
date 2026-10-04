# SPEC: #122 STEP 4. An extra early decode at 13.0 s, shown on the panel before the slot ends (phase 4a: panel only)

- **To:** QA (owner: the OpenSpec change, `tasks.md`, the Developer handoff; HK-015/HK-000). cc Captain. **From:** Architect. **Date:** 2026-10-03, written from 14:33Z by `date -u` (HK-017).
- **Branch:** `arch/122-latency` (local). Docs only: `git diff --stat -- src/ native/` is empty. **The build is `src/`** (and `native/` only if R4's option (ii) is chosen), so it needs a separate Developer session (HK-011).
- **Authorised:** the Captain, 2026-10-03 (Architect's window, about 14:31Z): *"1. agreed"*. That answered the Architect's recommendation to write the step-4 build spec with these defaults: the automation ignores early decodes the final decode does not confirm; the panel shows them marked; cut point x = 2.0 s; panel-only first, automation after step 2. **#122 is no longer only "on hold" for this step.** The Developer starts when the global hold lifts (after the Engineer's D1, Captain).
- **Evidence:** gate 4a, accepted (`2026-10-03-1435-architect-122-gate4a-report-ruling.md`; report `eng/122-gate4a` `df4ec892`). Every figure is **descriptive** (V2 failed on P by one decode; the figures were released by the Captain).
  - At **x = 2.0 s**, an early decode had **C ≈ 0.98** of the full-window decodes on four corpora (P 0.984, R 0.983, X17 0.988, X80 0.987).
  - It took about as long as the full decode (`t(2.0)` ≈ 527 ms on P against `t(0)` ≈ 534 ms), so those decodes appear **≈ 2 s earlier**.
  - It also produced early-only decodes: `S_unc` (uncorroborated) 0.22–0.47 per 100, and `S_corr` (corroborated by the live WSJT-X) 0.26–0.96 per 100.
  - One final decode in 20 175 was lost on P when early decodes ran first (cause under diagnosis, D1–D3).

## 0. Amendment 1 (2026-10-03 14:56Z by `date -u`, before any build): QA's code reading, all nine points accepted

QA's findings (`qa/122-step4-docs` `f941dae9`, design D1–D10). The Architect checked the two load-bearing ones in the code himself.

1. **R9 (new): the early decode is the ordinary decode ONLY, never the residual pass.** Verified: `Ft8Decoder.DecodeCoreAsync` reads the flag (`Ft8Decoder.cs:370`), and with the flag ON and no first-batch callback it runs `SubtractionPass` inside the same call (`:489-501`). Subtraction is default ON, so an early decode through `DecodeAsync` would take ≈ 5 s, and A3(a) could never hold. ⇒ The early decode uses a pass-0-only entry that does not read the flag. Gate 4a measured exactly that (flag OFF).
2. **R4: snapshot/restore is required, and it is `native/` (new shim number).** Verified: `cb_save_hash` adds unconditionally (`ft8_shim.c:839-841`), so "suppressed writes" does not exist either. The shared state is wider than the table: `g_session_hash_table` (`:795`), `g_hash_table_reject_count` (`:711`), `g_h12_announce_clock` (`:722`) and the `g_h12_*` counters and arrays (`:726-747`). **Snapshot/restore of ALL of them around the early decode** is chosen over suppressed writes. Suppressed writes would lose hash resolution within the call (the early text would read `<...>` where the final reads the call, so R5 could not confirm the row), and would still pollute the h12 counters. The Developer records the exact list in design.md, with FILE:LINE.
3. **R10 (new):** the dial-frequency guard (`DecodePump.cs:79-89`) applies to the early decode. A band change while the window fills discards the early batch too.
4. **R11 (new):** early rows pass the same `DecodeNoiseSuppressionFilter` as batch 1, so a row the operator has hidden is never shown early.
5. **A1b (new; my gap):** with the flag **ON**, ALL.TXT, UDP datagrams, the QSO channels and the archive are **identical** to flag OFF over a fixed set of recorded cycles (outcome fields). Without it, a build could leak early rows to ALL.TXT and pass every row.
6. **A2: positive control and power (HK-026, HK-021 (k) precision branch).** At 1 miss in 1 075 cycles, a build that kept the defect would pass N/N on P with probability ≈ 0.37. ⇒
   - **A2 runs on P and R** (≈ 0.19 to miss it);
   - **A2-PC:** the same replay on the build with R4 disabled must reproduce the known loss at stamp `261001_112700` (the 1 731 Hz decode). If it does not, A2 is **blind** to this defect;
   - **A2b (new, deterministic, the main guarantee):** a test that captures **every global listed in point 2** before the early decode, runs the early decode, restores, and asserts the state is **byte-identical** to the captured one. A rare-event replay alone cannot carry R4.
   - **Merge needs A2b PASS and A2 N/N on P and R.** If A2-PC is blind, A2 is reported as *"not evaluable for this defect"*, and the merge rests on A2b.
7. **A3(c):** the control is **flag-OFF hours**, alternated by partial config POST and read back each time. Cycles where the early decode was skipped are not a control: skips happen when the decoder is busy, so those are the heavy cycles.
8. **A4:** ±0.01 is ≈ 10 standard errors over ≈ 20 000 decodes. That is deliberate: **A4 detects only a gross path difference**, and the report says so.
9. **Panel wire format:** the existing WebSocket `decode` frame stays **byte-identical** when there are no early rows (part of A1). Early rows use a **new `decode-early` frame type**. Batch 1's message gains an **optional `resolves` list** (which early rows it confirms), so confirmation and the final rows arrive in one frame.

**Shim numbers:** B2 (Stage B) and step 4 each take the next free number. Whichever merges second takes the one after.

## 0b. Ruling on A2 / A2-PC (2026-10-03 17:36Z by `date -u`; QA's review of the Developer's `feat/122-step4-early-decode-panel` `fee81a2b`, shim 20260058)

- **Reported:**
  - A2b PASS (17/17), with native mutations that each remove one global from the restore and are each caught, plus a stray-static mutation caught by completeness test 2.4a.
  - A2 N/N on P (1 075/1 075) and R (720/720).
  - **A2-PC NOT reproduced:** the restore-removed build was also 1 075/1 075, so this replay cannot see the defect. That is likely because gate 4a ran six early decodes per cycle and the product runs one.
  - Per the pre-set merge rule (§0 point 6), **A2 is "not evaluable for this defect", and R4 rests on A2b.**
- **The stronger control** (replaying P with all six gate-4a cuts on the restore-removed build and on the real build; ≈ 80 min per build) is **NOT required.** A2b tests the guarantee mechanically and is mutation-proven. A replay can only show a rare event, never its absence. The original loss's mechanism is unknown, so even a reproduced loss would only show that this pattern of use triggers it.
- **Required instead, because A2b covers only what the image holds (HK-026):** extend completeness test 2.4a from `ft8_shim.c` to **every native source compiled into `libft8.dll`**: the vendored `ft8_lib` (`native/ft8_lib_vendor/**`, `native/ft8_lib_build/patched/**`), `common/`, `fft/`, `refine/` and `subfeas/`. Every mutable file-scope or thread-local static is listed as *"in the image"*, *"reset per call (FILE:LINE)"* or *"not written on the pass-0 path (FILE:LINE)"*. A quick scan by the Architect found no mutable static in the ft8 core files and only the `subfeas_fit.c` pool statics (`:596-612`), which pass 0 does not touch. The test makes that mechanical. **Merge needs A2b PASS with the extended 2.4a.**
- **Blind spot, stated:** A2 ran the final decode with subtraction OFF (the product default is ON). A2b is independent of the flag. A3 (live, flag ON) does not check identity. This is accepted and stated in the report.
- **Next:** A1b, then A5 (Playwright + `live_verify_9_axes.py`), A4, and then A3 (live; needs the Captain's go and a slot).

## 0c. Ruling on A3 (live) and the acceptance as a whole (2026-10-04 11:08Z by `date -u`)

- **QA's A3 (build `ca8e3118`, receive only, 40 m, radio on Voicemeeter B2, subtraction ON as shipped, cut 2.0 s; HK-020 arm checks passed):**
  - **Run 1** (02:24:58–06:25:00Z, 4 h, flag alternating hourly, 3 flips read back; 473 ON and 474 OFF cycles after a 45 s settle window): **(b) skips 0/473 = 0 %** (bar ≤ 5 %): PASS. **(c) batch-1 publish:** OFF median 15.566 s, ON 15.562 s, Δ −0.004 s, 95 % CI [−0.015, +0.002] (bar ≤ +0.10): PASS.
  - **Run 2** (10:06:43–11:06:53Z, 1 h, flag ON, a real WebSocket client logging frame arrival): **(a) the early batch arrives at a median 13.509 s into the slot** (p95 13.603, max 13.680; 100 % ≤ 13.7 s): PASS. Batch 1 median 15.546 s, so **the early batch leads by ≈ 2.04 s.** 240/240 cycles produced an early frame.
  - I checked `ws_rows.json` myself (HK-018): it matches.
- **Instrument defect, found and handled (HK-026):** the R7 `Early decode:` log line is written at the **final** decode's start (≈ 15.03 s), not at the early publish, so (a) could not be read from the log, and the reading sat flat at 15.03 s. QA moved (a) to a direct WebSocket measurement (run 2). **D8's design text is corrected at merge.** Moving the log write to the early publish point is optional and low priority; it is not a merge item.
- **Verdict: step 4 phase 4a is ACCEPTED in full.** A1, A1b, A2b (with the extended 2.4a), A2 (not evaluable for the defect, as ruled), A3 (a)(b)(c), A4, A5 browser and `live_verify_9_axes.py` 10/10 all pass. The merge ships with the flag OFF, as specified. QA merges under the Captain's session delegation; **the DEFAULT-ON decision is the Captain's alone** (spec §3).
- **What it does to the operator's window (live, one night):** decodes on screen at ≈ 13.5 s instead of ≈ 15.55 s, so about **3.85 s** to answer before the 17.36 s TX deadline, instead of about 1.8 s. That holds for ≈ 98 % of decodes (gate 4a). The rest arrive at the usual time.
- **Limits:** one night (02–06Z, 10–11Z), 40 m, receive only. Batch 2 is not analysed beyond its arrival (median 5.10 s into the next slot on this `main`-based build without B2). No claim about how the panel feels to use.
- **DEFAULT-ON DECIDED (Captain, 2026-10-04 11:10Z by `date -u`, Architect's window: "default on").** R6's default becomes `earlyDecodeEnabled = true`. The field is new, so no migration is expected. QA verifies that no station or test config holds an explicit false from this branch's builds, and reads the station config after the merge (HK-035). The flag-OFF tests (A1) set false explicitly.
- **Predictions scored (ledger updated in the same edit):** SD1 (A2 N/N on the first build, 0.65) ✅ HIT, with the label that A2 is blind to the defect. SD2 (early median ≤ 13.7 s, 0.75) ✅ HIT, 13.509. SD3 (skips ≤ 5 %, 0.70) ✅ HIT, 0 %. SD4 (C(2.0) ± 0.01 of 0.984, 0.70) ✅ HIT, 0.9838.

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
