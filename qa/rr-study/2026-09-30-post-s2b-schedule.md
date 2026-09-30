# Scheduled after S2b: (1) the first-pass "where do the 500 ms go" profile, (2) the WSJT-X corroboration scan of the endurance corpora

- **Date (UTC):** 2026-09-30. **Author:** QA. **Instruction:** the Captain, 2026-09-30: *"when S2b has completed I want you schedule both tests, the 500ms question and the scan of the endurance corpora."*
- **Status: SCHEDULED, NOT STARTED.** Neither test begins until S2b has completed. `src/`/`native/` diff of this note: none (HK-011).

## 0. Where these sit in the queue

| Order | Item | Machine | Who | Depends on |
|---|---|---|---|---|
| 1 | Two-stage acceptance S1/S2 (running) | busy until ~17:20Z 2026-09-30 | QA | (in flight) |
| 2 | Engineer's T8 loop + full slnx, then L1 | quiet machine, station for L1 | Engineer | S2 DONE, QA's green light |
| 3 | **Overnight flag-ON on-air run**, receive only | the station and the machine, until **14:00Z 2026-10-01 at the latest** | QA arms on the Captain's word | Captain's start command |
| 4 | Gather, HK-036 Section 4, orphan check, release the station | | QA | 3 |
| 5 | **S2b** (batch-1 delivery under load; report only) | quiet machine, ~45-60 min run after a harness is written | QA | 4 |
| 6 | **Test A: first-pass profile** | quiet machine, timing | Developer builds the test-only tool, QA runs and reads | 5 |
| 7 | **Test B: WSJT-X corroboration scan of the endurance corpora** | light CPU, offline, no station | QA | 5 (the Captain's order; it has no machine dependency of its own) |

The S2b harness can be **written** earlier (no machine needed); only its run waits for step 4.

## 1. Test A: the first-pass profile ("where do the ~500 ms go")

**Question.** The flag-OFF decode takes about 480 ms median (473-528 ms in recent replays; max 830 ms) and #122's series says p50 518 ms. Only the total is known. The window that matters is the ~2.36 s guard after the audio ends (TX must start by 17.36 s); pass 0 uses about a fifth of it. Whether the first pass could be made faster, and by threading which step, depends on the split.

**What is measured.** Wall-clock milliseconds per stage of one first-pass decode on real recorded cycles, single decode at a time, no change to decoder behaviour:
1. managed side before native: PCM normalisation and marshalling;
2. spectrogram / waterfall build;
3. candidate search, pass 0;
4. per-candidate decode loop, pass 0 (likelihood extraction, LDPC, CRC, message unpack; report the candidate count and the success count as integers);
5. spectrogram suppression and candidate search, pass 1, and its decode loop;
6. noise floor, SNR terms, and the managed side after native: mapping, logging.

**Method.** Test-only, in the style of `tests/Ft8.FitProbe` and its `native/phase_timing.c`: a timing-instrumented **copy** of the pipeline compiled for the test, never shipped, so the product decoder is untouched. Output is **integers and stamps only** (HK-037). Cycles: the 161 E1 cycles (`e1_selection.json`, SHA `f58c0c7b…`) so the result is comparable with the other work. Report median, p95 and max per stage, and the stage shares of the total.

**Acceptance is a report, not a bar.** Read it for one decision: is the per-candidate decode step (independent per candidate, the natural thing to split across threads) the bulk of the time, or is it the spectrogram and search? **It is descriptive: it is not a decode-rate measurement and makes no claim about decode rate.**

**Who and what.** A test-only tool is Developer work (HK-011); QA writes the handoff (draft `dev-tasks/2026-09-30-first-pass-latency-profile.md`), runs it on a quiet machine and reads it. The Architect scopes any follow-on (#122 comment: `issuecomment-5914822230`, "not yet"). If the profile shows a worthwhile split, a design and a spec come **after** and need the Captain's go.

## 2. Test B: WSJT-X corroboration scan of the endurance corpora

**Question.** In the flag-ON replay of busy real cycles, the residual pass found on average **+4.53 more decodes per cycle** than flag OFF (Stage A R7, descriptive, 905 cycles). **How many of those extra decodes does WSJT-X also decode in the same cycle?** That converts a count into a corroborated count and gives a first plausibility check on false positives.

**Corpora.** The three endurance runs used for §8.1 and Stage A: `20260922_2056` (Voicemeeter B1), `20260923_1730` and `20260925_2010` (direct CODEC), each with OpenWSFZ's `ALL.TXT`, WSJT-X's `ALL.TXT` for the same window, and the cycle WAVs. Selection: the frozen §8.1 strata (H and M, 905 cycles, `selection.json` SHA `730d6ea6…`) or the 161 E1 cycles, decided when the test is designed.

**Method (to be finalised at design time).** Outcome comparison at the **text-hash** level, inside one process, so no message text leaves the function that reads it (HK-037):
- the replay harness already writes, per decode, numeric fields plus an 8-hex-digit hash of the message text (`--outcomes`); flag-ON minus flag-OFF gives the extra decodes of each cycle (batch 2 of the two-stage build is exactly the residual decodes);
- WSJT-X's decodes for the same cycle stamp are read from its `ALL.TXT` and hashed with the **same** normalisation, and compared with a frequency/time tolerance;
- reuse the Stage 2 matching logic (`qa/rr-study/sub-feas/stage2.py`) rather than inventing a new one (HK-034), including its treatment of the RR73 encoding difference.
- Report: extra decodes, corroborated, not corroborated, and the not-corroborated share; per run; per SNR band; **with the interval and the block count** (busy cycles cluster, so the effective N is the block count).

**Limits, stated up front (HK-026).**
- The corpora are **not independent** of the SUB-FEAS research corpus's neighbourhood (same station, same bands, same period), so this is a **plausibility check, not the base change's §8.2 result**. §8.2 needs an independent corpus; the overnight run is that candidate.
- "Not corroborated" is **not** "false": WSJT-X can miss a real weak signal, so the not-corroborated share is an **upper bound** on false positives, and only that.
- Busy cycles only (≥ 20 first-pass decodes); no quiet cycles are in these strata.
- **No decode-rate claim** from this test on its own. Cite the SUB-FEAS Stage 2 **net** figure (+8.89 pp [8.01, 9.75]) for the research result, never a raw one.

**Machine.** Offline, CPU-light after the replay (the replay itself is about 15-30 min for the 161 cycles, or about 90 min for all 905), no station. It has no quiet-machine need beyond the replay, but it is scheduled after S2b as instructed.

## 3. Checkpoints
1. S2b complete and reported → QA messages the Architect and the Developer.
2. The Developer is handed the profile draft; QA runs it on the quiet machine; the report goes to the Captain.
3. Test B is designed (selection, tolerance, matching) and **pre-registered** (harness and predicates committed before any result is read), then run and reported with the limits above.
4. Neither test changes what ships. Outcomes are inputs to decisions the Captain makes.
