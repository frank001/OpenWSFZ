# D-001: consolidation and clean slate

**Author:** Architect, 2026-07-26 (00:15). **For:** the Captain and QA.
**Purpose:** re-anchor on D-001, state what is closed, keep one live lead, and discard the rest.

This supersedes the disposition and work plan in
`2026-07-25-2330-architect-to-qa-pr108-disposition-and-workplan.md` §4. Two of my own
recommendations from that document are **withdrawn** below (§5.2, §5.3) — they were written
before I re-anchored on the D-001 number, and they do not survive it.

---

## 1. Where D-001 actually is

All four arms below decode **the same 68 matched cycles** from
`artefacts/20260725_live_run_1806/`. Earlier reports compared unmatched cycle sets, which is
part of how the picture got muddy.

| arm | decodes |
|---|---:|
| our decoder / our audio (live) | 1277 |
| our decoder / our audio (offline) | 1284 |
| our decoder / WSJT-X audio (offline) | 1288 |
| WSJT-X decoder / WSJT-X audio (live) | **2028** |

| contribution | decodes | share of gap |
|---|---:|---:|
| **capture chain** (our audio vs WSJT-X audio, same decoder) | 4 | **0.5 %** |
| **live path** (our live vs our offline, same audio+decoder) | 7 | **0.9 %** |
| **decoder** (our decoder vs WSJT-X decoder, same audio) | **740** | **98.5 %** |
| total D-001 gap | 751 (1.588×) | 100 % |

**D-001 is a decoder problem. The capture chain, the framer, the live path and the window
boundary together account for 11 of 751 missing decodes.**

## 2. Closed — do not reopen

Each of these is closed by direct measurement, not by inference. The point of listing them is
that they should never consume another session.

| avenue | closed by | evidence |
|---|---|---|
| Capture chain loses decodes | tonight's 2×2 | 4 of 751 (0.5 %). 68/68 WAV pairs cross-correlate at 0.933–0.992 |
| Cycle-boundary clock drift | 12:00 signature argument + 23:00 measurement | our framer σ = 59 ms, zero dropped samples, no accumulation; misalignment can only reduce *candidates*, and candidates are pegged at their ceiling |
| Window misalignment generally | 11:10 magnitude + 12:00 signature | recall plateau flat 0.92–0.99 out to ±2 s; ft8_lib searches −1.60…+3.04 s |
| `CycleFramer` correction loop would recover the loss | 12:00 attribution | upper bound **4.3 %**, and the two rates are statistically indistinguishable |
| Audio on zero-decode cycles is degraded | 12:00 probe | median RMS ratio **1.01**; noise floor flat; PCM length exactly 180 000 every cycle |

The 12:00 document (`2026-07-25-1200-architect-second-mechanism-located.md`) already had the
answer. Everything after it in this directory — the parity report, the cross-correlation note,
my own two documents tonight — has been *re-confirming a negative*. That work was worth doing
once, because it converts "probably not the capture" into "0.5 %, measured", and that is what
lets us stop. It should not be extended.

## 3. The one live lead

From `ldpc_stats.py` over the 11 h 51 m session, per decile:

- Sync candidates: median **140** in eight of ten deciles — `K_MAX_CANDIDATES` at
  `src/OpenWSFZ.Ft8/Native/ft8_shim.c:467`. **The candidate list is saturated at its
  compile-time cap.**
- Candidate yield is *identical* on cycles that decode 22 messages and cycles that decode none
  (median 140, p90 140, both populations).
- What varies is **survival**: `failCands` 82 → 136 as decodes collapse, `meanAbsLLR`
  4.075 → 3.83, `prenormVar` 116 → 91.

So the decoder finds the signals and then fails to decode them. Two distinct sub-questions,
and they are separable:

1. **Are we truncating the candidate list?** Pass 0 caps at 140 and is saturated. If the true
   candidate population exceeds 140, we are discarding candidates before LDPC ever sees them —
   and which 140 survive is then an artefact of the scoring order, not of signal quality.
2. **Why is LDPC survival collapsing?** Falling `meanAbsLLR` and `prenormVar` in the collapsed
   deciles points at LLR scaling/normalisation, which is where the OSD parameters we have been
   sweeping (`kMinScorePass2`, `osdCorrThreshold`, `osdNhardMax`) act.

These are the only two things standing between us and the 740.

## 4. Keep

- `2026-07-25-1200-architect-second-mechanism-located.md` — **the anchor document.** Everything
  else in this directory is subordinate to it.
- The §1 table above — it is what closes the capture avenue permanently.
- `ldpc_stats.py`, `rewindow.py`, `run_phase*.py`, `score_recall.py`, `D001ParamSweep` — the
  offline decode harness. This is the instrument for §3 and it works.
- `measure_dt_alignment.py` — the 2×2 capture-vs-decoder separator. Cheap, general, and it
  answered in one run what decode-count comparison could not answer at all.
- The per-cycle `hashTableRejectCount` logging from PR #108 (`Ft8Decoder.cs` +19, tests +141).
  Hash-table rejection is a **decoder** failure mode, so this is on the live path. Salvage it.

## 5. Discard

### 5.1 PR #108 and the whole cycle-boundary thread

Close the PR, drop the branch, and let the `fix-cycle-boundary-clock-drift` OpenSpec change go
with it (it exists only on the branch and was never merged, so there is no archive step). The
six `dev-tasks/2026-07-2[345]-cycleframer-*.md` handoffs die with it. Suggest one paragraph in
the §9.5 closure note recording *why* — three fix rounds defeated by live testing because the
premise was falsified — rather than preserving six documents about a dead mechanism.

### 5.2 Withdrawn: the capture gap/enqueue-latency telemetry salvage

At 23:30 I recommended salvaging `WasapiAudioSource.cs` +49 / `CaptureManager.cs` +48 / tests
+53 as useful observability. **Withdrawn.** It instruments the capture chain, which is now
measured at 0.5 % of the gap. Adding 150 lines of permanent telemetry to the one subsystem we
have just proven innocent is exactly the reflex that produced this sprawl. Drop it with the
rest of the branch; the `hashTableRejectCount` salvage in §4 stands, because that one is
decoder-side.

### 5.3 Withdrawn: the DT-offset delta sweep as a priority

At 23:30 I made "decide whether the +0.735 s DT offset costs decodes" the highest-value next
action. **Withdrawn — it is answerable from code, and the answer is no.**

`decode.c:279` searches `time_offset` over blocks −10…+19 at 0.16 s per block, i.e.
**−1.60 s … +3.04 s, centred at +0.72 s.** Our median reported DT is +0.68…+0.735 — essentially
exactly that centre. So our decoder is reporting the raw `time_offset` in ft8_lib's own frame,
while WSJT-X reports relative to the nominal transmission start. It is a **reporting-convention
difference, not a misalignment**, and the search window it sits in is 4.64 s wide — far too
generous for a 0.735 s reference shift to cost anything. The empirical check agrees: our
decoder scored 1288 on WSJT-X's audio against 1284 on ours despite a genuine 0.133 s window
difference.

The DT value is still **wrong where it is consumed** (ADIF, UI), so it remains a logging
correctness bug worth a small dev-task with a regression test. It is not a D-001 lead and
should not be sequenced ahead of §3. No delta sweep is needed.

### 5.4 Also drop

- The band-limited coherence check floated in the 21:45 note (already recommended against).
- The alignment-replay phase documents (`phase0`, `phase0b`, `phase1a`, `phase1b`,
  `deliverable-5-alignment-bound`) — retain as history, but they are closed work; nothing in
  them is a live lead.

## 6. Next steps

Two experiments, both offline, both deterministic, both using the harness already on `main`.
Neither needs a live run.

**6.1 — Is the candidate cap costing us decodes?** Rebuild the shim with `K_MAX_CANDIDATES`
raised (e.g. 140 → 300 → 600, pass 0 only) and re-decode the fixed corpus at otherwise
production-baseline settings. Report decodes and `failCands` per setting.
- Decodes rise materially ⇒ we have been truncating the candidate list; the cap becomes a
  tuned parameter and this is a direct recovery of part of the 740.
- Decodes flat while `failCands` rises ⇒ the extra candidates are spurious, the cap is not the
  constraint, and the whole of the loss is LDPC survival — which routes everything to 6.2.

Either outcome is decisive, which is why this goes first. It also needs a native rebuild, so
it is a **Developer session** under HK-011, not a QA-only run.

**6.2 — Why is LDPC survival collapsing?** The `meanAbsLLR` 4.075 → 3.83 and `prenormVar`
116 → 91 trends are the thread. This is an LLR scaling/normalisation question, and it is where
the existing parameter sweep already operates. Scope it properly **after** 6.1, because 6.1
changes what population LDPC is being asked to survive.

**6.3 — Structural comparison against WSJT-X, if 6.1 and 6.2 do not close the gap.** We run
two passes (full waterfall, then spectrogram-suppressed at `K_MAX_CANDIDATES_PASS2` = 200).
WSJT-X runs more passes with successive interference cancellation and a-priori decoding. If the
740 survives 6.1 and 6.2, the residue is likely structural to ft8_lib and the question becomes
a product one — how much of WSJT-X's decoder we are willing to reimplement — not a bug hunt.
That is a Captain decision, and I would want 6.1/6.2 results before framing it.

## 7. Honest caveats

- The §1 decomposition is **one 21-minute session on one device and one band**. It is
  internally consistent and the capture share is so small that a factor-of-several error
  would not change the conclusion, but it is a single sample.
- 6.1's outcome is genuinely uncertain. Saturation proves the cap *binds*; it does not prove
  the candidates beyond 140 are decodable. The experiment is designed so that either answer
  advances us, which is the best I can claim for it.
- Nothing here explains the 740 yet. §3 localises it to two mechanisms and §6 tests them. I do
  not want this document read as a solution — it is a clearing of the ground.

---

*Per HK-014 nothing is pushed or merged. Per HK-015 `tasks.md` and `dev-tasks/` remain QA's to
author. Closing PR #108 needs the Captain's explicit sign-off per HK-010.*
