# First-pass latency profile: where do the ~500 ms go? (Test A, report)

| Field | Value |
|---|---|
| Run | 2026-09-30, 17:16Z to 17:19Z, single decode at a time, one thread |
| Tool | `feat/first-pass-latency-profile` @`6fd9fe3e` (Developer; `tests/Ft8.FirstPassProbe`, test-only; it times a generated **copy** of `ft8_shim.c`, nothing shipped changed) |
| Shipped `libft8.dll` | `ee00d118523ee2160750736225c67d8a056193908d168ed9a6ec3375ff990e4c` (unchanged; the only `src/` line the branch adds is one `InternalsVisibleTo` test hook) |
| Timed test DLL | `e619a9acd72f6a045f322041e74adecbee6c2ace81e70c628290ce9e57eeb37e` (scratch, never shipped; built by `build_timed_dll.py`; script fails if any anchor in the shipped text is missing) |
| Cycles | the **161 E1 cycles** (`e1_selection.json`, SHA `f58c0c7bd3ed34855f5db24277b941202813831b0f088a34944f5ba97c6879e2`), real recorded audio, each WAV asserted 12 kHz mono 16-bit, 180 000 samples |
| Machine | Ryzen 7 7800X3D; **WSJT-X closed; a browser was open** (low CPU); the Engineer and the Developer were idle; not a bit-perfect quiet machine |
| Commands | `profile --dll <shipped> …`, `profile --dll <timed> …`, `compare`, `overhead`, `summary` per the Developer's recipe; `--selection e1_selection.json --artefacts-root artefacts` |

> **Bottom line.** **97.5 % of the first-pass decode is the two per-candidate decode loops** (pass 0: 34.2 %, pass 1: 63.3 %). Everything else together,
> spectrogram, both candidate searches, noise floor, normalisation, marshalling and the managed bookkeeping, is **about 2.5 %** (~12 ms of ~492 ms).
> **Descriptive only: no decode-rate claim, no change to what ships.**

## Per-stage timing (161 cycles; milliseconds unless a count)

| Stage | median | p95 | max | share of whole call |
|---|---:|---:|---:|---:|
| **WHOLE CALL (`DecodeAsync`)** | 492.387 | 542.320 | 564.511 | 100.0 % |
| managed before native (normalise) | 0.916 | 1.088 | 1.275 | 0.2 % |
| marshalling + P/Invoke (derived) | 0.033 | 0.065 | 0.076 | 0.0 % |
| native: waterfall build (spectrogram) | 4.446 | 4.882 | 7.322 | 0.9 % |
| native: noise floor | 0.074 | 0.090 | 0.189 | 0.0 % |
| native: pass 0 find candidates | 2.149 | 2.445 | 4.111 | 0.4 % |
| **native: pass 0 candidate decode loop** | **168.289** | 196.901 | 204.631 | **34.2 %** |
| native: pass 1 suppression | 0.057 | 0.074 | 0.219 | 0.0 % |
| native: pass 1 find candidates | 2.102 | 2.308 | 3.782 | 0.4 % |
| **native: pass 1 candidate decode loop** | **311.477** | 339.914 | 366.864 | **63.3 %** |
| native: cleanup | 0.004 | 0.028 | 0.041 | 0.0 % |
| native: unattributed (total − stages) | 0.004 | 0.005 | 0.006 | 0.0 % |
| native TOTAL (`ft8_decode_all`) | 491.061 | 540.968 | 563.099 | 99.7 % |
| managed after native + scheduling (derived) | 0.477 | 0.832 | 1.168 | 0.1 % |

**Candidate counts (medians):** pass 0: **140 candidates, 24 decoded**; pass 1: **200 candidates, 2 decoded**.

## Instrument validity

- **Equivalence: PASS.** Shipped vs timed DLL on all 161 cycles: pass-0 count, total count and outcome hash **identical** (`compare`: "EQUIVALENT").
- **In-situ overhead:** whole-call median shipped 497.413 ms vs timed 492.387 ms (difference −5.026 ms, −1.01 %, i.e. the timed copy was not slower; noise-level). Timer cost: 15.6 ns per native read, 18 reads per decode, **about 0.3 µs per decode**.
- **Stage sum:** native stages sum to the native total with **0.00 %** unattributed (the managed-after figure is derived, so the stages sum to the whole by construction; the check that can fail is the native stage sum).

## What it says, and what it does not

1. **The per-candidate decode step is the bulk**, which is the thing that is independent per candidate and so the natural thing to split across threads. The spectrogram and the candidate searches (the parts that are not obviously splittable) are **about 1.7 %**. So, on this evidence, threading the per-candidate decode loops is the only change that could move the ~500 ms materially; nothing else matters.
2. **Pass 1 is the expensive pass and the unproductive one.** Its decode loop is 311 ms (63 % of the call) for a median of **2 decoded candidates out of 200**, against pass 0's 168 ms for 24 of 140. The per-candidate cost is roughly 1.6 ms in pass 1 (mostly failures) against 1.2 ms in pass 0; pass 1 tries more candidates and most fail after the error-correction iterations run. **This suggests a second, cheaper latency lever that needs no threading: publish batch 1 after pass 0 (about 170 ms after the audio ends) and pass 1's few decodes afterwards.** That is an idea, unverified: it depends on what share of the decodes an operator could answer comes from pass 1 (a median of 2 per cycle), and on the two-stage publish machinery, and it changes when decodes appear, not which decodes.
3. **Not shown:** that the candidates are independent in the shipped code (the decode loop shares the callsign hash table and per-thread priority-bits state, see the #122 comment), how well the loop would scale across cores, or what splitting costs. The profile says where the time is, not how much a split would save. A speed-up of the decode loops from N threads is bounded by the loop share (97.5 %), so at most a few-fold reduction of the ~492 ms; a realistic figure needs a prototype.
4. **Blind spot (HK-026):** busy real 40m cycles (the E1 selection: ≥ 20 first-pass decodes each), one machine, single-threaded measurement; the medians will differ on quiet cycles (fewer decodes, cheaper loops). It is not a decode-rate measurement and says nothing about decode rate.

## Decision inputs (for the Captain and the Architect; nothing is authorised by this report)

- Threading the per-candidate decode (idea in #122, "not yet"): the profile supports the premise (97.5 % of the time is that step). Scoping, design and the Captain's go come **before** any `src/`/`native/` change.
- Splitting the first pass into two publishes (after pass 0, then after pass 1) is a cheaper candidate that the profile suggests; same rule.
- Hygiene: integers and stamps only; no message text anywhere. Artefacts committed: this report, `summary.txt`, `compare.txt`.
