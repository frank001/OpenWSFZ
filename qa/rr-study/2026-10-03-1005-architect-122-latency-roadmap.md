# ROADMAP: #122 decode latency, steps 2–5 (outline specs, gates and order)

- **To:** QA (owner of whatever is authorised; the `src/`/`native/` steps go to a Developer through QA, HK-015/HK-011). cc Captain. **From:** Architect. **Date:** 2026-10-03 ~10:05Z (HK-017).
- **Branch:** `arch/122-latency` (local). Docs only: `git diff --stat -- src/ native/` is empty.
- **Companion:** step 1 is a full pre-registered spec, `2026-10-03-1000-architect-to-qa-spec-122-step1-end-to-end-latency.md`.
- 🔴 **#122 stays on HOLD (Captain, 2026-09-21). Nothing in this file is authorised.** Each step becomes a full spec (pre-registered rows, predictions) only when the step before it has reported and the Captain says go.
- **Basis:** #122's body and comments (the 2026-09-30 profile, Test A; the Architect's 2026-09-30 assessment); the lateness ruling `2026-10-02-2225`; `DecodePump.cs` as on `main` `bdd11a34`.

## 0. Words used here (two "pass-0"s have already been confused once)

| Term | Meaning | Today's time (p50, busy 40 m cycles) |
|---|---|---|
| **native pass A** | the first pass inside `ft8_decode_all()` (140 candidates) | loop ≈ 168 ms, median 24 decodes |
| **native pass B** | the second native pass (decoded signals attenuated, 200 candidates) | loop ≈ 312 ms, median 2 decodes |
| **ordinary decode** | A + B, one native call; published as **batch 1** | whole call ≈ 492 ms |
| **residual pass** | SUB-FEAS subtraction + re-decode (flag ON, default since v0.54); published as **batch 2** | ≈ 5.0 s |

Profile: `qa/rr-study/results/2026-09-30-first-pass-latency-profile/report.md`. A and B loops are 97.5 % of the ordinary decode.

## 1. The Captain's aim, and what each step can and cannot do for it

**Captain, 2026-10-03:** *"I'm hoping to speed up the first pass so that the available window for the reply… so it is still open."* So the batch-2 → auto-QSO choice **stays open, not decided** (parked 2026-10-02). Every step below is built so that the batch-2 policy can be added later without rework. Until the Captain chooses, the default stays **fenced** (the automation does not act on batch 2, as today).

🔴 **The arithmetic, stated once:** the Q2 night measured batch 2 at **T2 p50 5.71 s** into the reply slot. That is the decode start (0.03 s) + the ordinary decode (≈ 0.53 s) + the residual pass (≈ 5.0 s). The lateness ruling (`2026-10-02-2225` §3) set the condition for replying to a batch-2 decode in the same slot: **a median T2 below about 2.95 s**, i.e. about 2.8 s faster.

| Step | What it saves in batch 1 (the ordinary decode, which carries most decodes) | What it saves in T2 (batch 2) |
|---|---|---|
| 1 measure | nothing (an instrument) | nothing, but it **measures** T2 on `main` |
| 2 progressive batches | nothing by itself; it makes 3 and 4 usable by the automation | nothing |
| 3 native pass A first | ≈ 0.32 s (A's decodes appear at ≈ 0.18 s, not ≈ 0.49 s) | ≈ 0 (the residual pass still waits for A + B) |
| 4 extra early decode | **≈ x s** for the stations already complete at `15 − x` (§2.3) | ≈ 0 unless the residual pass also starts early (a decode-rate question) |
| 5 thread the native passes | up to ≈ 0.3–0.4 s, unproven | ≈ the same 0.3–0.4 s |

⇒ **#122's steps make batch 1, which carries most of each cycle's decodes, much faster.** Batch 2 stays out of reach of a same-slot reply, because about 5 s of its 5.7 s is the residual pass itself. Making batch 2 answerable is a **residual-pass speed** question (SUB-FEAS Stage B, optional since 2026-09-30), not a #122 question. I say it once and do not repeat it. The Captain decides.

## 2. The steps

### 2.1 Step 2: progressive batches as the decode model (`src/`, Developer, via an OpenSpec change)

**Problem:** every consumer assumes **one batch = one cycle**. SUB-FEAS had to fence the answerer and caller off from batch 2 (`DecodePump.cs:46-50`). `QsoAnswererService._lastIdleDecodeBatch` (`:104`, set at `:657`, read at `:382`) and `ExternalReportingService._lastDecodeBatch` (`:176`, set `:485`) each keep only the **last** batch. The second is replaced by batch 2 today (diagnostic only, `:1115-1121`).

**Requirements (outline):**
- **P2-R1** `DecodeBatch` (`DecodeBatch.cs:11`) gains `Sequence` (0, 1, …) and `IsFinal`. One cycle publishes ≥ 1 batch, and exactly one of them has `IsFinal`.
- **P2-R2** Consumers see two events, **decodes-added** and **cycle-complete**. Per-cycle bookkeeping moves to cycle-complete: retry counts, "no reply this cycle", watchdog resets (`QsoAnswererService.cs:1272-1302`, `QsoCallerService.cs:1039`). A second batch can then never look like a new cycle.
- **P2-R3** "This cycle's decodes" means **every batch so far in the cycle** (accumulated), in the answerer's external-reply path and in external reporting's diagnostic.
- **P2-R4** Batch-2 policy is an explicit setting, **default `fenced`** (today's behaviour). The Captain's parked choice later becomes a value of that setting, not a redesign.
- **P2-R5** Flag OFF: one batch, `Sequence` 0, `IsFinal`. Everything outward (panel, `ALL.TXT`, UDP, QSO behaviour) stays byte-identical. The cycle-audio archive stays once per cycle.

**Gate to start:** the step-1 report has been ruled on, and the Captain says go. **Gate to accept:**
- characterisation tests that pin today's answerer and caller behaviour, written and green **before** the refactor;
- the same tests green after it;
- `live_verify_9_axes.py` (the decode-filter policy);
- one supervised on-air QSO session.

The QSO state machines key the transmitter, which makes them the most delicate code in the project. That is why this step is first among the code steps and not folded into another.

**A cheaper order, for the Captain to weigh after step 1:** step 3 done **panel-only** (A's decodes reach the panel early, and the automation keeps one batch at the end, as SUB-FEAS's fence does) needs no step 2. It gives the operator the 0.32 s. The automation does not get it. Step 2 is what lets the **automation** use steps 3 and 4.

### 2.2 Step 3: native pass A first (`native/` + `src/`, Developer)

- **P3-R1** The shim hands over pass A's results before pass B runs. Either split it into two calls **on the same thread** (the decoder's state is thread-local: `tls_pass_counts[]`, the AP bits), or use a callback. The shim version gets a new number.
- **P3-R2** 🔴 **Outcome identity:** for every cycle, A's batch ∪ B's batch = today's single-call result. That means outcome fields, compared across processes, never rendered text (the hash table is process-global). It is checked on the 161 profile cycles and on one full recorded night, with the flag OFF and ON.
- **P3-R3** With step 2, A's batch goes to every consumer as `Sequence` 0. Without step 2, panel only (the cheaper order above).
- **Gate to start:** step 1 ruled. If the Captain wants the automation to benefit, step 2 accepted first.

### 2.3 Step 4: an extra early decode before the slot closes (`src/`, maybe `native/`)

🔴 **I am revising my 2026-09-30 assessment here.** I framed step 4 as *moving* the decode earlier, which trades recall for time, and I made the DT-convention offset a prerequisite. A better shape is to **add** an early decode and keep the final one. That is what the Captain saw WSJT-X do (progressive display), and possibly how WSJT-X does it (EL1 in the step-1 spec tests that).
- At `15 − x` s, decode the partial window and publish what decodes as an early batch. The **final decode at 15 s is unchanged**, so it loses nothing **by construction**. Its results are de-duplicated against the early batch by outcome fields.
- **What it costs instead:**
  - CPU: one more ordinary decode inside the capture window, while the previous cycle's residual pass may still be running with the flag ON;
  - duplicates to handle;
  - the automation acting on an early decode whose final version differs (it should not happen; it gets a row).
- **Which stations an early decode can catch (indicative, from the lateness ruling):** a transmission occupies `L + 0.5 … L + 13.14` s of the slot. In the edge run, a signal still decoded with **≈ 0.89 s of its tail cut** (`L` 2.75 ⇒ cut 0.89 s) and failed at 1.14 s. That is synthetic AWGN at −8/−16 dB, a cliff, both decoders. So an early decode at `15 − x` might catch stations with `L` ≲ `2.75 − x`: at x = 1 s, every station up to `L` ≈ 1.75. This is a rough guide, not a design value.
- **Gate 4a (offline, test-only, no station, no build; can run when the PC is quiet, independent of steps 1–3):** a **truncation replay** on recorded real windows (the cycle-audio archive). For each window, zero everything after `15 − x` for x ∈ {0.5, 1.0, 1.5, 2.0, 2.5} and decode it with the shipped DLL. Report, per x: the fraction of the full-window decodes that the early decode already finds, the early decodes that the full window does **not** find (spurious; there must be ~0), and the decode time. Recordings measure real stations' real timing directly, so the DT-convention item (≈ 0.65 s, 0.2 s of it unexplained) becomes an **explanation**, not a blocker. My full spec for 4a comes when the Captain asks for it.
- **Gate to build:** 4a reported and ruled. Step 2 accepted if the automation is to use the early batch. The CPU interaction with the residual pass measured on the station.

### 2.4 Step 5: thread the native passes (`native/`, Developer; prototype first)

- **Shape to prototype (unverified):**
  - a **parallel phase** per candidate, up to the 77-bit payload (sync, LLRs, LDPC, CRC);
  - then a **serial phase in candidate order** for de-duplication, unpacking and the callsign hash table.

  The order-dependent shared state (the hash table) is then touched only serially, in today's order. That is the part that could change **results**, not just timing, if done in parallel. Pass B still starts after pass A (it depends on A's attenuation).
- **P5-R1** Outcome-identical to the single-thread build for 1, 2, 4 and 8 threads, over repeated runs (determinism, not a lucky ordering). Checked on the 161 profile cycles and one full night.
- **P5-R2** Bounded, heap-only, stress-tested (the project has two production crashes in native subtraction work). It must not oversubscribe the CPU with the residual pass's 8 workers (measured, not assumed).
- **Value:** the lowest of the four. If step 4 lands, the urgency drops further. It is the only step that also shortens T2 a little.

## 3. Order and gates

```
step 1 (station, ~2.5 h) ──ruled──► Captain ──► step 2 (QSO refactor) ──► step 3 (A first, automation too)
        │                                   └──► or: step 3 panel-only (no step 2)
        │
gate 4a (offline, PC quiet; can run before, after or instead of step 1's slot; never overlapping it)
        └──ruled──► step 4 build (after step 2 if the automation should use it)
step 5: prototype only after 3 or 4 has landed and step 1's numbers say there is still a gap
```

## 4. What the Captain decides now

1. **Whether and when step 1 runs** (#122 stays on HOLD until he says go). It needs one WSJT-X UDP setting changed and then restored by him (step 1 §3.2).
2. **Whether I write gate 4a as a full spec now.** It needs no station, it is cheap, and it answers the largest unknown (how much an early decode would catch on real traffic).
3. Nothing else. Steps 2, 3 and 5 wait for step 1's report.
