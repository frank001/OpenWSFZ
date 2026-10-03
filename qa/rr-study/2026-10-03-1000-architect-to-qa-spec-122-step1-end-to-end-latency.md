# SPEC: #122 STEP 1. When does each program actually show a decode? End-to-end latency, OpenWSFZ against WSJT-X, on one clock

- **To:** QA (owner; QA may assign the Engineer, with one owner recorded on the board). cc Captain. **From:** Architect. **Date:** 2026-10-03 ~10:00Z (HK-017, `date -u`).
- **Branch:** `arch/122-latency` (local). Docs only: `git diff --stat -- src/ native/` is empty.
- **Why now (Captain, 2026-10-03):** *"prepare the specs for gh issue #122"*. The Captain chose a full spec for step 1 and an outline for steps 2–5 (roadmap: `2026-10-03-1005-architect-122-latency-roadmap.md`).
- 🔴 **#122 stays on HOLD (Captain, 2026-09-21).** This spec is **ready to run, but not authorised.** Nothing runs until the Captain says go.
- **Status:** PRE-REGISTERED. QA commits the listener, the parser, the row predicates and the analysis as code **before the live session**. Any change after the session needs a dated amendment that says why.
- **Needs:** about 2.5 h of station time, receive only, real band traffic, WSJT-X running as normal. No build. No `src/` or `native/` change. **One human action**, on the WSJT-X UDP setting (§3.2).

## 1. Question

#122's budget table (2026-08-11) measured one term: the decoder's own `elapsed=` time (p50 518 ms). Three things were never measured:

- **Q1.** On one clock, relative to the end of the slot, **when does each program publish its first and its last decode** of a cycle, OpenWSFZ and WSJT-X, on the same audio?
- **Q2.** **How is WSJT-X's publishing spread through the cycle?** One burst, or several (one per decode pass)? Does it publish **anything before the slot ends**? The Captain has observed that WSJT-X shows decodes progressively. Whether it starts before the slot closes has never been measured, and that answer decides how much step 4 is worth.
- **Q3.** **How long is OpenWSFZ's WebSocket → browser-render leg?** #122 bounded it "by inspection, not by data".

This is a **characterisation**. It has no PASS bar on latency. Its validity rows (§4) decide whether the numbers can be reported at all.

## 2. Instrument

**What the instruments already record (HK-027), and why none of it is enough:**
- Both `ALL.TXT` files stamp the **cycle start** only, never the moment a decode appeared.
- The daemon's line `Cycle {Time}: N decode(s) found, elapsed=… ms` (`src/OpenWSFZ.Ft8/Ft8Decoder.cs`, cited in #122) gives the decoder's own time. The log stamp has **one-second resolution** (`[23:21:15 INF]`, `artefacts/20261002_2115_lateness_edge_run/daemon.stdout.r1.log`), and the line says nothing about delivery.
- WSJT-X logs no decode times at all.

**The instrument: the WSJT-X UDP protocol.** Both programs send a `Decode` datagram (type 2) for every decode:
- **WSJT-X** sends each one as it is produced. This is the feed GridTracker uses. 🔴 *Assumption, not verified:* a datagram is sent when the decode appears in WSJT-X's Band Activity window. §6 states this limit. No row in this spec can test it.
- **OpenWSFZ** sends one `Decode` per visible result from `ExternalReportingService.DecodeLoopAsync`. It sends for **both** batches: `DecodePump.PublishFirstAsync` writes batch 1 to `ExternalReportingChannel` (`src/OpenWSFZ.Daemon/DecodePump.cs:164`), and `PublishSecondAsync` writes batch 2 (`:181`). Encoder: `WsjtxDatagram.EncodeDecode` (`src/OpenWSFZ.Daemon/WsjtxDatagram.cs:173`).

A listener on the same PC stamps every arriving datagram with the PC clock, in milliseconds. That puts both programs on **one clock**, with no change to either program. Each `Decode` carries its cycle's start time (`TimeMsSinceMidnightUtc`), so every datagram is assigned to its cycle by that field, never by its arrival time.

**Reference instant:** `B` = the **nominal** slot start + 15.000 s, on the PC clock (the slot end). The nominal slot start is the datagram's `time` field rounded down to a multiple of 15 s. That makes `B` the same instant for both programs even if OpenWSFZ's framer stamps its window a few ms off the boundary. QA reports the largest difference between the raw field and the rounded one, per program. Every offset in this spec is `arrival − B`, in seconds. A negative offset means the decode was published before the slot ended.

## 3. Set-up

### 3.1 Listener (test-only code under `qa/`, Python stdlib `socket` + `struct`)

- **Two UDP ports**, one per program, e.g. `127.0.0.1:2240` for OpenWSFZ and `:2241` for WSJT-X. Each arrival is stamped with `time.time_ns()` **at receive, before any parsing**.
- **Parse only:** the header (magic, schema, type, id), then for type 2: `new`, `time`, `snr`, `delta time`, `delta frequency`, `mode`, `message`, `low confidence`, `off air`. QA checks the field order against `WsjtxDatagram.cs:173-190` and against WSJT-X's `NetworkMessage.hpp` documentation (FILE:LINE in the report).
- 🔒 **HK-037 / NFR-021:** the message text never leaves the parsing function. The function may compare texts **inside itself**, to match one decode across programs (O4), and returns **only** numbers: offsets, counts, SNR, DT, DF and a per-cycle match index. No text, no callsign and no hash of either is written to disk or to a log. Raw datagrams are **never** saved: the WSJT-X stream carries real third-party callsigns.
- Only `new = true` decodes are counted. WSJT-X re-sends old decodes with `new = false` on a replay request.
- **Relay mode for WSJT-X (required):** after stamping, the listener forwards each WSJT-X datagram **byte-for-byte** to the address WSJT-X sent to before the change (GridTracker), so the station keeps working. OpenWSFZ needs no relay (§3.2).

### 3.2 Pointing both programs at the listener

- **OpenWSFZ:** add **one extra** `externalReporting.targets` entry (`127.0.0.1:2240`, enabled). The existing targets stay as they are. 🔴 **HK-035:** config POST is an overlay on `main` since v0.53, **but** check whether a list field such as `targets` is merged or replaced. Send the complete list (existing entries + the new one), read it back, and confirm that the existing targets are unchanged. Remove the entry afterwards and read back again.
- **WSJT-X (the one human action, HK-027):**
  1. QA first **reads** the current UDP server address and port from WSJT-X's `.ini` (a file read, nothing changed) and records them.
  2. The Captain sets WSJT-X *Settings → Reporting → UDP Server* to the listener's port.
  3. Afterwards he restores the recorded value, and QA confirms the restore by reading the `.ini` again.

  QA may propose an `.ini` edit with WSJT-X closed as a mechanical alternative. The Captain decides, because it is his station.
- **Browser leg (Q3):** a Playwright-driven browser (HK-007; a test tool, not added to the product) opens the OpenWSFZ web UI. An injected script stamps:
  - (a) the arrival of every decode-carrying WebSocket message, using `performance.timeOrigin + performance.now()`;
  - (b) the moment after it is rendered: the first `requestAnimationFrame` callback after the table has changed, then a second one (a double-rAF).

  QA names the WebSocket message type and the render function (FILE:LINE, e.g. `web/js/main.js:1820`, per #122). The script records **counts and times only** (HK-037).

### 3.3 Session

- **Build:** current `main` (record the SHA). `libft8.dll` SHA-256 pinned at start and at end. Shim `20260056`. `nhard` 40. **`decoder.subtractionEnabled` as shipped (ON)**, confirmed by reading it back from the running daemon. Record `decodeNoiseSuppression` exactly as it is (do not change it; O1 and U3 account for it).
- **Band and time:** 40 m, **≥ 2 h**, including at least 1 h with a median of ≥ 15 WSJT-X decodes per cycle (a busy period). This needs real traffic: a synthetic scene cannot show WSJT-X's own pass behaviour on a real band. Receive only, `tx.autoAnswer` false.
- 🔴 **CPU rule:** no test suites, builds, other runs or extra daemons on the PC during the session. The latency being measured is itself CPU-sensitive. The station is one resource: QA and the Engineer never overlap live runs.
- **Piggy-backing** on another receive-only run is allowed **only with the Captain's go** and only if that run's goal is not disturbed (HK-020). A dedicated daytime session is recommended.
- **HK-019:** listener and browser stopped by explicit teardown, orphan check empty. **HK-016:** gather into `artefacts/<UTC>_122_latency_run/`.
- **Clock record (descriptive):** run `w32tm /stripchart /computer:<NTP server> /samples:5 /dataonly` at the start and at the end. Both programs read the same PC clock, so an offset does not affect Q1–Q3. It only matters for how either program sits relative to **other stations'** slots.

## 4. Pre-registered rows

**Validity (if any row FAILS, no latency figure is reported; the report names the row and stops).** All predicates are code, committed before the session (HK-021).

| Row | Predicate |
|---|---|
| U0 config | Build SHA recorded. DLL SHA-256 at start = at end = pin. `subtractionEnabled` read back ON. OpenWSFZ targets read back as (original list + listener), and as the original list after removal. WSJT-X `.ini` UDP value after restore = the value recorded before the change |
| U1 listener positive control (HK-026), before the session, on the station PC with the session's processes idle | A test sender emits **200** synthetic `Decode` datagrams (Q-prefix calls only, NFR-021) to each port at scheduled, logged send times, including bursts of 30 within 50 ms. **PASS iff** ≥ 99 % of the recorded arrival stamps are within **2 ms** of their send stamp, none is lost, and every parsed field equals the sent field |
| U2 relay transparency | During U1, every datagram the WSJT-X port forwards is **byte-identical** to the one it received (compared in code), and the forwarding delay is ≤ 2 ms at p99 |
| U3 completeness | Per program, per cycle with ≥ 1 decode: the number of `new = true` datagrams against that cycle's `ALL.TXT` lines. **WSJT-X:** equal in ≥ 98 % of cycles. **OpenWSFZ:** if `decodeNoiseSuppression` is off, equal in ≥ 98 % of cycles; if it is on, datagrams ≤ `ALL.TXT` lines in 100 % of cycles (the ratio is reported). A FAIL means the UDP feed does not stand for what the program decoded |
| U4 causality (OpenWSFZ) | In **100 %** of cycles, OpenWSFZ's first-datagram offset ≥ the cycle's logged batch-1 `elapsed` ÷ 1000 − 0.010 s. (The decode starts after the window closes, and the window closes at or after `B`.) A FAIL means the cycle assignment or the clock reading is wrong |
| U5 cycle assignment | 0 datagrams whose offset falls outside [−15.0, +20.0] s of their own cycle's `B`, for either program |
| U6 browser coverage | The browser recorded a WebSocket arrival for ≥ 98 % of the OpenWSFZ batches the UDP listener recorded in the same window |
| U7 busy period | ≥ 240 cycles with a median of ≥ 15 WSJT-X decodes (the §3.3 condition). If this FAILS, the run is reported as **thin-band only** and Q2's pass-structure output is labelled descriptive |

**Outputs (exact definitions, no bar).** Each one is reported for all cycles **and** for busy cycles (≥ 20 WSJT-X decodes) separately. Quantiles are p5, p50, p90, p99 and max, each with `n`.

- **O1 first and last decode, per program:** `F` = the offset of the earliest datagram of the cycle, `Z` = the offset of the latest. For OpenWSFZ, also batch 1 and batch 2 separately (the batch is identified as each burst of datagrams that one `DecodeBatch` produces; QA states the rule in code, e.g. a gap of > 200 ms between datagrams of one cycle), and the gap between them.
- **O2 WSJT-X pass structure:** a histogram of every WSJT-X datagram's offset in 50 ms bins, pooled over cycles. Per cycle, the number of bursts (gap > 300 ms) and each burst's start offset. **The fraction of WSJT-X decodes published before `B`** (offset < 0), and the fraction of cycles with at least one such decode.
- **O3 like-for-like delay:** decodes that **both** programs reported in one cycle (exact text, same cycle, matched one-to-one inside the parsing function). `Δ` = OpenWSFZ offset − WSJT-X offset, per matched decode. Report its quantiles, the fraction with `Δ` < 0 (ours earlier), and `ΔF` = `F`(OpenWSFZ) − `F`(WSJT-X) per cycle.
- **O4 browser leg:** WebSocket arrival − UDP arrival of the same batch (expected ≈ 0, both sent from one publish), and render − WebSocket arrival. Quantiles of each.
- **O5 the budget, refreshed:** #122's table rebuilt from O1/O4 (median and p99): slot end → first OpenWSFZ decode on screen → time left before the 17.36 s TX deadline. WSJT-X's first decode goes beside it.

## 5. What the result feeds (stated in advance, so it cannot be fitted afterwards)

These are **readings for the roadmap**, not verdicts. The Architect rules on them with the report.
- If WSJT-X publishes a material share of its decodes **before `B`** (O2), then decoding before the slot closes (**step 4**) is **parity with WSJT-X**, not a gamble, and step 4's offline gate moves up the order.
- If `ΔF` (O3) is about the size of the decoder's own time (≈ 0.5 s), the decode itself is our gap: **steps 3 and 5** close it.
- If the browser leg (O4) is above 100 ms at p99, a web-side fix comes first, because it is the cheapest.
- **Batch 2** (O1, OpenWSFZ) replaces the Q2 night's derived `T2` with a measured publish time. It does **not** reopen the parked batch-2 → auto-QSO choice by itself (lateness ruling `2026-10-02-2225` §3: reopening needs a median `T2` below about 2.9 s, measured on a full night).

## 6. Limits (carried with every figure)

- **UDP publish ≠ screen, for WSJT-X:** the instrument assumes WSJT-X sends each `Decode` when it displays it. It is not verified, and no row tests it. For OpenWSFZ, O4 measures the screen directly.
- One PC (Ryzen 7 7800X3D), one band, one session, one build of each program. Real traffic, so the scene is not controlled.
- The flag is ON, as shipped. Batch 1 comes from the ordinary decode, which the flag does not change. Batch 2 timing belongs to this CPU and this worker count.
- Offsets are relative to the **PC clock's** slot end. The WSJT-X UDP feed shows when a decode was published, never when the signal was sent.

## 7. Predictions (blind; scored at ruling time in the ledger)

| # | Prediction | P | Class |
|---|---|---:|:---:|
| EL1 | WSJT-X publishes ≥ 1 decode **before `B`** in ≥ 50 % of cycles that have decodes. My basis is a recollection that WSJT-X runs an early FT8 decode on a partial window. **I have not read that in its source.** The ledger's LT2 lesson applies: weight this as a guess about a mechanism | 0.50 | H-mech |
| EL2 | OpenWSFZ `F` p50 (all cycles) ∈ [0.45, 0.80] s | 0.70 | H |
| EL3 | O3: matched `Δ` p50 > 0 (OpenWSFZ publishes later than WSJT-X) | 0.80 | H |
| EL4 | O4: render − WebSocket arrival, p99 ≤ 50 ms | 0.75 | H |
| EL5 | U0–U7 all pass the first time | 0.60 | H |
