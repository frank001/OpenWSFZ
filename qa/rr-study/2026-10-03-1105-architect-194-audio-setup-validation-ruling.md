# RULING: #194 audio-setup snapshot sampler, AS1–AS5 validation

- **From:** Architect. **To:** QA (owner). cc Captain. **Date:** 2026-10-03 ~11:05Z (HK-017, `date -u`).
- **Spec:** `qa/rr-study/2026-10-02-1940-architect-to-qa-spec-194-audio-setup-snapshot.md` (on `main`).
- **Report ruled on:** `qa/rr-study/2026-10-03-1100-qa-to-architect-194-audio-setup-validation.md`, branch `qa/audio-setup-194` `6cf6eefd` (local, not pushed). Code under `qa/audio-setup/` only. `git diff --stat -- src/ native/` is empty in the report and in this ruling.
- **Checked myself (HK-018/HK-022), not taken from the report:** the spec's AS1–AS5 wording. `sampler.py` on `6cf6eefd`: the read path (`:116-140`) calls `VBVMR_IsParametersDirty()` once per read and **discards its return value** (`:117`). The supervisor/worker split and the setter-free source are on QA's evidence.

## 1. Verdict

**VALIDATED under Amendment 1 (§2.1). §5 integration may start, with the conditions in §3.** QA reported every failure, including AS3 as written and the two failed AS4 attempts, and did not relabel a row after the data. That is the standard.

| Row | Ruling |
|---|---|
| AS1 | **PASS, with the stated limit.** The Remote API returns rc 0 and `0.0` for any index, so "every strip and bus the API reports" cannot be checked against the instrument. Strip and bus counts come from a **table keyed by the reported type** (Banana: 5 strips, 5 buses, A1–A3/B1–B2). That table comes from Voicemeeter's documentation, not from a measurement, and the report says so. An unknown type must make the sampler log `voicemeeter: type table unverified` and keep sampling Windows (AS5's behaviour). It must not guess counts |
| AS2 | **PASS** (run 2). Run 1's FAIL is the instrument's stale read-back (§2.3), not a missed change. Both runs stay in the record |
| AS3 | **FAIL as written; PASS under Amendment 1** (§2.1). CPU 0.313 % of one core passes as written |
| AS4 | **PASS** (attempt 3). Attempts 1 and 2 died of a native crash (§2.2). One clean 10-minute run does not show the crash is gone, so §3 carries a coverage measure into every real run |
| AS5 | **PASS** |

## 2. Rulings on QA's three questions

### 2.1 AS3's 500 ms clause: Amendment 1 (written after the data, labelled as such)

**Amendment 1 to spec §4, AS3:** *"…and every **warm** sample (every sample after the first in a worker's life) takes ≤ 500 ms. The **cold** first sample (COM initialisation, name cache) takes ≤ 2 s, and the run tooling starts the sampler **≥ 10 s before the first played or measured cycle**, so a cold sample never overlaps one."*

- **Why this is not re-reading a gate to pass it:** the clause's stated purpose is *"it must not perturb a timing run"*. A one-off 1.1 s sample, taken before any cycle and costing almost no CPU (it is a wait on COM, inside the 0.313 % measured), perturbs nothing. The 10 s lead time turns that reason into a predicate.
- **What it does not do:** it does not change the record. **AS3 as written FAILED**, and **AS-P1 stays a MISS.** The amendment applies from here on.
- 🔴 **A worker restart is a cold start too** (§2.2). The 10 s lead time cannot cover it, because a crash comes mid-run. The restart sample's duration is logged, and a restart cold sample over 2 s is listed in the run's sampler summary (descriptive: it waits on COM, it does not compute).

### 2.2 Sample period: keep 5 s

- The sampler exists to join scan-flagged slots to setup changes **within ±30 s** (spec §5). Worst observed detection lag was 8.78 s at 5 s (AS2). That fits inside the join with room to spare, and the AS2 bound (≤ 10 s) is a validation bar, not the use.
- A 2 s period would cost about 1.5 % of one core (QA's estimate). **That would break AS3's ≤ 1 % CPU bound**, the clause that protects timing runs. It is the wrong trade.
- 🔴 **The join must allow for the lag, mechanically.** Each change record carries `detected_utc`, and the change happened at most about 10 s earlier. For a flagged slot at time `S`, the scan therefore joins change records with **`detected_utc` ∈ [S − 30 s, S + 40 s]**. The scan's column states the window.

### 2.3 Findings

**(a) Native crash in `pycaw.GetAllSessions` → supervisor + worker: ACCEPTED.** A native fault cannot be caught in Python, and a separate worker is the only design that guarantees *"it never crashes the run"* (AS5's clause, extended). With the cyclic GC disabled in the worker, keep it, but **do not claim it as a fix**: two crashes in about three 10-minute runs and none in the fourth proves nothing either way. Conditions for §5 are in §3 (crash count and coverage).

**(b) Stale start values: QA's rule ADOPTED, plus a lead to check.**
- **Rule:** a **start** snapshot and every **restart** snapshot are `unverified` until two consecutive ticks agree. The first verified state is the run's reference.
- A difference between an unverified snapshot and the first verified tick is recorded as `unverified_start_diff`, **not** as a change. It never enters the scan join.
- **Lead (mine, not a hypothesis I price; the ledger's LT2 lesson applies):**
  - Both stale cases fit the API's parameter cache not being refreshed. That covers the read straight after a set in AS2 run 1, and the −30 dB that one worker kept reading for over four minutes while 25 fresh logins read −33.
  - The sampler calls `VBVMR_IsParametersDirty()` once and ignores its result (`sampler.py:117`).
  - QA (1) logs that call's return value on every read, and (2) tries a bounded *"call until it returns 0"* loop before reading (e.g. at most 10 calls, 50 ms apart).
  - **Then** check whether a stale start or a stale read-back recurs. If it does not recur, report that as a correlation over the runs observed, not as a proven cause.
  - The `unverified` rule stays either way, because it is the instrument's guard and not a fix.

**(c) Descriptive:** `Strip[3]` moved from −30 dB (my probe, 2026-10-02 19:30Z) to −33 dB outside any run. That is exactly the kind of drift the sampler is for, and it is why the start snapshot must be verified before anyone cites it.

## 3. Conditions for §5 integration (all mechanical)

1. The R&R tooling and the endurance launcher start the sampler **≥ 10 s** before the first played or measured cycle, and stop it by explicit teardown (HK-019, orphan check). The sampler is gathered into `-gathered` (HK-016).
2. **Every run's report prints:** the number of worker crashes and restarts, and **coverage** = the fraction of the run window covered by heartbeats with no gap over 70 s. **Coverage below 98 %** labels that run's sampler output `PARTIAL`. It never blocks or fails the run.
3. The scan's new column uses the §2.2 join window (`detected_utc` ∈ [S − 30, S + 40] s) and excludes `unverified_start_diff` records.
4. **CPU rule:** the sampler is light (0.313 %), but its first integrated run is not a timing-sensitive one. Use an ordinary R&R battery or an endurance night, not the Engineer's gate 4a slot (#122).

## 4. Predictions scored (ledger updated in the same edit)

| # | Prediction | P | Class | Outcome |
|---|---|---:|:---:|---|
| AS-P1 | AS1–AS5 pass the first time | 0.60 | H | ❌ **MISS.** AS2 failed once, AS4 twice, and AS3 as written |
| AS-P2 | the device-format blob decodes (the field is kept) | 0.55 | H | **VOID.** Not attempted; the field was dropped, as spec §2 allowed |

**Lesson:** AS-P1 bundled five rows, three of them on COM and an undocumented API, into one "first time" call. My 0.60 was priced as if each row were simple. Native-interop instruments fail first runs. Price that next time.

## 5. Housekeeping

`qa/audio-setup-194` and this ruling go to the remote only on the Captain's go (QA pushes; HK-014/HK-033).

## 6. Addendum (2026-10-03 ~11:20Z, Captain): five-run review, with no runs scheduled for it

**Captain:** *"yes, add the five-run review. but only when we need to run it. do not schedule 5 runs now."*

- **No run is scheduled for the sampler.** It rides along on R&R batteries and endurance nights that happen anyway, for their own reasons. Nobody books station time to fill the count.
- **Every integrated run's report adds two numbers:** the setup changes recorded (excluding `unverified_start_diff`), and the scan-flagged slots with at least one change in their §2.2 join window.
- **Review trigger:** when the fifth integrated run is gathered, QA puts the five runs' figures to the Architect. If the five runs together show **0 changes and 0 joined slots**, the Architect recommends cutting the sampler back to a **start and end snapshot only, without the per-app session enumeration** (the `pycaw.GetAllSessions` path that crashed). Otherwise it stays as built. The Captain decides.
