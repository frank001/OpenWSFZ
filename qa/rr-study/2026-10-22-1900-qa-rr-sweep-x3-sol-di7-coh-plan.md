# QA: plan for a full R&R sweep, three times, on `sol`, with the synced `decoding_improvement` build (series DI7COH)

**Stamped:** 2026-10-22T19:00:45Z by `date -u`. **Status: PREPARED, NOT STARTED.** The Captain's instruction (QA's window, 2026-10-22): *"prepare a full r&r sweep on sol (3x) with the decoding_improvement build after the developer changes are reviewed and accepted. this should count against the new data era."* Nothing runs until the gate in §1 is met and the Captain gives the go (§7). No push, no `src/` change.

## 0. What a "full sweep ×3" is here (existing machinery, nothing new)

- **One sweep** = one supervised battery of the full scenario list `S1,S1b,S2,S3,S4,S5,S7,S8,S3c,S6` through `battery-tp.sh`: S6 at the standard tier, **sequential** (WSJT-X alone, then OpenWSFZ alone), the WSJT-X monitoring M1-M3, the scenario-level retry (3 per scenario, no wall-time limit).
- **×3** = `series-tp.sh 3 DI7COH`: three COMPLETE sweeps in a row; each is renamed `<date>-<sha7>-DI7COH-sweep<n>`; the series halts on any halt (a scenario failing again with its retries used up).
- Results come home with `pull-series.sh DI7COH` (aggregates only; the daemon log never leaves `sol`, NFR-021) into `qa/rr-study/results`, then the root results folder (standing rule).
- **Duration, measured on the last comparable series:** MAINDEEP sweep 1 ran 2026-10-19 17:14:55Z to 20:52:38Z = **3 h 38 min** (10 scenario attempts, 0 failed, 0 replacements). Three sweeps ≈ **11 h** if nothing halts; retries add to that. `sol` is exclusive for the whole series (no replay, no compile, no other job on it: the harness aborts if one is running).

## 1. The gate: what must be true BEFORE the series starts

1. The Developer's DI sync 7 commit exists (task `dev-tasks/2026-10-22-di-sync-7.md`, `c2170d73`), and **QA has reviewed it and committed the HK-039 record** (`Reviewed-commit:` + `Verdict: APPROVED`).
2. **QA's acceptance checks pass on that commit:** the seven (or eight) conflicts resolved as the task says; shim number agreed in the header, the DLL and `libft8.version.txt` (`check_native_version.py` on both binaries); the exports of both lines present; `subfeas_fit.c` and `coherent_fallback.c/.h` byte-identical to `main`; the full unfiltered suites green on Windows and WSL; the **decode-identity check** (`di_sync_identity.py`) against plain `main` with the fallback flag explicit on both sides.
3. The PR into `decoding_improvement` is **merged** on green CI (the Captain's go covers it: "main first and then decoding_improvement"). *Proposal:* the series builds from the **merged tip**, so the pin names a committed state. If the Captain prefers an earlier start, the series can build from the reviewed local commit instead; say which in §7.
4. `sol` is idle and reachable; the audio rig and WSJT-X profile `rr` unchanged since the last series (the PRECHECK appraiser gate verifies this itself).

## 2. The build and the pin

- A new checkout on `sol`, `~/OpenWSFZ-di7`, at the DI tip; published with **`tools/publish_selfcontained.py --rid linux-x64`** (never plain `dotnet publish --self-contained`: that is a Native AOT build with broken audio); `tools/capture_build_provenance.py` run next to it; `TP_REPO=~/OpenWSFZ-di7`, `TP_DAEMON=<its publish>/OpenWSFZ.Daemon`.
- **The pin is the committed `libft8.so` in that tree** (S6 pins the one the daemon loads). If the CI job "Commit rebuilt native binaries" rebuilds the `.so` after the DI merge, the tree's file is CI's; record whichever file is in the tree: its SHA-256 at the start of every sweep and at S6 start and end (the harness already does the latter). **Never reuse an older pin** (the `sol` `.so` `0197f9ce…` is QA's local build of `b8fc732e`, and `main`'s `.so` is CI's since PR #254).
- Tooling: `~/rr-work-b2` stays the tooling checkout (the analyser, M1-M3, S6-V7). It must carry QA's current `qa/refset` tooling at a recorded commit; QA's local commits are not pushed (HK-033), so the sync to `sol` is a bundle copy (as for `b2merge.bundle`), not a push. The tooling commit is logged in the sweep's build line.

## 3. The configuration (explicit, never inherited)

- `~/rr-run/config-di7coh.json` = `config-tp-deep.json` (the MAINDEEP/TPDEEP rig config: `osdNhardMax` 24, subtraction on, 8 sub threads, early decode on, `decodingDepth` **Deep**) **plus `"coherentFallbackEnabled": true`, written explicitly.** Since PR #253 an absent key also reads true, but an explicit value is what the read-back is compared with, and an old config can hold an explicit `false` (the station's does).
- **Validity row V-D (existing, voids the sweep on any mismatch):** the depth read back from `/api/v1/status` at the start and end of every sweep equals Deep (`depth_readback.py`).
- **Validity row V-F (new, for this series): the fallback was running.** `/api/v1/status` has no field for the flag (the Developer left the optional read-back out), so V-F is read from two places and both must agree with the config: (a) `GET /api/v1/config` `decoder.coherentFallbackEnabled` read at the start and end of each sweep and logged, and (b) the daemon's own per-cycle line `Coherent fallback: eligible=…` counted from `daemon.stdout.log` **on `sol`** (counts only): the lines exist only while the fallback is on. A sweep with the config true but no such lines, or lines with the config false, is **VOID**. Where the 95 % bar for "lines present" comes from: in the 20 m live check every scored cycle had a fallback line (483 of 483 in the scored set; a cycle with nothing to do logs `eligible=0`, so the line does not depend on decodes); I will use ≥ 95 % of the cycles in each sweep and record the observed fraction. A harness that stops or restarts the daemon (the S6 passes) can lose a few lines at its edges, which is why the bar is not 100 %.
- Every other config value is the MAINDEEP one, byte for byte (diff against `config-tp-deep.json` is exactly the one added key).

## 4. What the series answers, and what it does not (HK-022, HK-038)

- **It answers:** the R&R rows of the new era on `sol`: the OpenWSFZ decode rate against WSJT-X in each scenario, three complete sweeps, so the between-sweep spread is measured, with the fallback ON and the Deep third pass.
- **The era (the Captain's "count against the new data era"):** a **new row**, labelled **DI7COH** = `decoding_improvement` synced with `main` (`f7e57989` / `74c75792`, 2026-10-22 18:17:34Z), shim 20260070 (to be confirmed by the sync), Deep, fallback ON, `nhard` 24, OSD fix on. **Never pooled** with MAINDEEP (`main` `5229beec`, no fallback), TPDEEP, TPNORMAL, B2CAP, B2BASE, or any sequential-vs-concurrent S6 mix. Comparison with MAINDEEP is descriptive, same rig, and is said to be across a build change (the fallback plus the DI-only work), not a measurement of the fallback alone.
- **It does not answer:** whether the fallback's gain over WSJT-X (+3.82 pp, 40 m replay) appears in the synthetic R&R scenarios; whether the DI-only decoder work helps or hurts (the identity check, not this series, answers whether the sync changed decodes); anything on 20 m live (the R14 run).
- **No pass/fail bar of QA's own is added.** The WSJT-X tripwire stays as ruled (Architect, 2026-10-17-2218): FLAG iff the WAV-clustered 95 % CI of S6's WSJT-X consistency excludes **93.9 %** (mean of the six prior standard sequential blocks; re-derive if the rig, the WSJT-X exe or the WAV list changes). Section 6 of each report is read first (HK-031), and depth and flag read-backs, the pin lines (start and end), the F2 clamp check and the capture counters are quoted before any number is cited.

## 5. Run recipe (for the day; nothing here is executed now)

```
# on sol, after the build is published and the config is in place, nothing else running
export TP_REPO=$HOME/OpenWSFZ-di7 TP_DAEMON=<publish>/OpenWSFZ.Daemon TP_CONFIG=$HOME/rr-run/config-di7coh.json
SCENARIO_RETRIES=3 setsid nohup sh $HOME/series-tp.sh 3 DI7COH > $HOME/rr-run/series-DI7COH.launch 2>&1 < /dev/null &
# detached, no cron (HK-023); on the PC, after 'SERIES DI7COH COMPLETE':  bash qa/rr-study/linux/pull-series.sh DI7COH
```
A pre-flight smoke first (one short scenario, the pins, the depth and flag read-backs, a clean PRECHECK) before the 11 h start, as for TPDEEP.

## 6. Tooling to prepare (QA, no `src/`)

- **V-F row** into the series: a small read-back of `/api/v1/config` at each sweep's start and end, and the count of `Coherent fallback:` lines from `daemon.stdout.log` on `sol`, written into `depth_readback.json`'s neighbour (`flag_readback.json`) and checked by `pull-series.sh`. **Not yet written.** It is QA tooling and is committed before the series starts.
- A `series-di7coh` launcher note in `qa/rr-study/linux/README.md`.
- Sync the tooling commit to `sol` by bundle; record its hash.

## 7. Decisions for the Captain (with their data; nothing is started)

1. **The go**, after §1 is met. *Data:* the series occupies `sol` for about 11 h; the PC stays free for the Developer and the station.
2. **Build source:** the merged DI tip (recommended: the pin names a committed state, and the CI "rebuilt binaries" step has run) versus the reviewed local commit (an earlier start by one PR cycle, about 15 minutes of CI).
3. **S6 tier:** standard, as in every prior series (recommended: keeps the era comparable). Extended costs more time.
4. **After the series:** hibernate `sol` (`sudo -n /usr/sbin/hibernate-ram`) as on 2026-10-21? A hibernated `sol` has to be woken before results can be pulled.
5. **The series ID** `DI7COH` (a label only; it must never repeat).
