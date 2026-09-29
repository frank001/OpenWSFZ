# QA → Architect: SUB-FEAS native build — code review outcome and paired R&R S1–S8 (flag OFF vs ON)

- **Date (UTC):** 2026-09-29 19:33
- **From / to:** QA → Architect (for review; copy to the Captain)
- **Branch under review:** `feat/sub-feas-native-subtraction` @ `0d6b1937`, **local, not pushed** (HK-033); Developer worktree.
- **QA branch:** `qa/sub-feas` @ `38ce9674` (report + `trend.csv`), also local, not pushed.
- **Ask:** review the two items below and rule on the three proposals in Section 5. Nothing here needs an answer to unblock anything running; no run is in progress.

## 1. What this covers

Two things the Captain directed this session, both on the SUB-FEAS native-subtraction build you saw specified in `openspec/changes/sub-feas-native-subtraction/`:

1. **QA code review** of the Developer's build (two passes).
2. **A paired R&R S1–S8 sweep** on that build: flag OFF, then flag ON, identical DLL and config.

The detailed records are, in order of weight:
- `qa/rr-study/results/2026-09-29-0d6b193-subfeas-off-vs-on/report.md` — the sweep report, in the last report's format (Sections 1, 5, 6; footnotes 16–18 new).
- `qa/rr-study/2026-09-29-1524-qa-to-architect-sub-feas-native-build-code-review.md` — the review report (`be18f7f1`).
- `openspec/changes/sub-feas-native-subtraction/tasks.md` on the Developer's branch (§6.9, §10.1, `0d6b1937`).

## 2. Code review — outcome

| Pass | Commit | Verdict |
|---|---|---|
| 1 | `1a1244bf` | **RETURNED**, three required changes |
| 2 | `91444300` | **APPROVED (code only)** |

- **R1** (residual `DecodeAll` on a different thread from pass-0; native AP/SNR/H12 state is `_Thread_local`): fixed by setting AP bits on the residual decode's own thread and clearing in `finally`. I had also suspected the callsign hash table was thread-local. **It is not**: `ft8_shim.c:787` (`g_session_hash_table`, process-global) and `:1489` (`tls_hash_table` re-pointed at it at the top of every native call). That part of R1 is withdrawn.
- **R2** (native failures outside the per-signal AV path escaped as exceptions and lost pass-0's results): the whole residual pass is now contained; any non-cancellation exception logs a warning and returns pass-0 only.
- **R3** (no runtime guard): a **cooperative** 13 s deadline (13 s minus pass-0 elapsed). An in-flight native call cannot be interrupted, so it bounds scheduling, not a single call.
- I re-ran `OpenWSFZ.Ft8.Tests` in a detached worktree at `91444300`: **353/353, no `--filter`**.
- **Not done by QA:** full-solution `dotnet test`, full `/opsx:verify`, a mechanical byte-diff of the flag-OFF output against pre-change (the design claims byte-identical; the review could only read it), Linux/macOS builds.
- **Open before merge:** tasks 6.3/6.5/6.6 dedicated tests, 6.7 (deferred by the Captain until after §8), 6.8 Linux/macOS, 5.1 (no web-UI checkbox), and the Captain's merge sign-off (HK-010).

**Provenance (HK-022).** `libft8.dll` SHA-256 `5a6a4dc04a2cf6fbd987c12ce7635a968f4c9b69f73cacebe422af62827e38c5`, shim `20260055`, read back from the running daemon. It is the same in the source tree and in the published output. **No independent pin exists**: the only other place that value appears on disk is `libft8.version.txt` (the same file's own label) and the Developer's report of it.

## 3. Paired R&R S1–S8 — what was measured

Exact scenario list, both runs: `--scenarios S1,S1b,S2,S3,S4,S5,S7,S8 --skip-warmup --device "Voicemeeter AUX Input"`. No `--filter`; every scenario ran and matched. OFF 15:37:21Z–17:26:20Z, ON 17:31:25Z–19:20:35Z; one daemon start and one stop each; `orphans_after_teardown: []`. Configs differ **only** in `decoder.subtractionEnabled` (plus output directories and one display-only block, see Section 6). `nhard=40`. **Both runs PASS; no gate fired.**

| Metric | OFF | ON |
|---|---|---|
| S5 Gate A / Check B FP, OpenWSFZ | 0/120 / 0/60 | 0/120 / 0/60 |
| S4 OpenWSFZ TP/FN/FP/TN | 96/12/0/180 | 96/12/0/180 (identical) |
| S7, OpenWSFZ | 166/215 (77.21%) | 174/215 (80.93%) |
| S7, WSJT-X | 203/215 (94.42%) | 207/215 (96.28%) |
| S8, OpenWSFZ | 91.67% | 91.67% |
| Per-cycle elapsed: mean / p95 / max | 88 / 199 / 374 ms | 351 / 1993 / **2490 ms** |
| `Sub-feas` log lines (AV, contained exception, deadline abandon) | n/a | **0** in 436 cycles |

**Readings I hold, and readings I refuse:**

- ✅ **Safety is clean on every available measure.** No phantom decodes on 180 signal-free slots with the flag on (0/120 has a 95% upper bound of 2.47%; it excludes a gross problem, not a small one). Runtime on these scenes is far under the 13 s budget.
- 🛑 **I do not claim the S7 movement as a subtraction effect.** OpenWSFZ's +8 messages are all in P0 ×4 and P15 ×4 (the 2-stack equal-0 dB co-channel cells) with **0 losses**, consistent with the mechanism, and P2 (3-stack) stays 0/15. But WSJT-X, whose decoder did not change, flipped 8 messages between the same two runs on identical seeds (6 up, 2 down, net +4). Since the S7 design reached N=215, OpenWSFZ reads **165–181/215** over 11 sweeps; OFF's 166 is at the floor and ON's 174 is mid-range; the same-build repeat batch `4584900d` read 165, 178, 178, 177, 181, 173. S7 is instrument-suspect by standing rule. I read Section 6 of the `2026-09-23-5f17b43` report first (HK-031) and carried its table forward with two new rows. I deliberately quote **no p-value** on the 8-and-0 pattern.
- ⚠️ **Open observation, needs your eye: OpenWSFZ's S1 SNR bias is +1.45 dB (OFF) / +1.18 dB (ON)** against 0.82–1.12 dB in the 13 preceding sweeps in `trend.csv`; S1 %GR&R 0.39% / 0.28% against 0.17–0.37%. WSJT-X's bias is unchanged (+0.82 / +0.75), so the chain looks intact. **It is present with the flag OFF, so it cannot be subtraction.** I cannot separate: the `main`-lineage versus `decoding_improvement` build (5f17b43 was `decoding_improvement`, shim `20260054`), the shim-`20260055` flag-OFF path itself, or the explicit decoder config block. This is the first place the "flag OFF is byte-identical" claim is under any pressure.
- ℹ️ Unexplained decodes: OFF S8 ×1 (Δf 25 Hz), ON S7 ×1 (Δf 3.0 Hz); WSJT-X 0/0. Both inside the 0–2 per sweep range. I have **not** located the ON decode's row; a decode 3 Hz from an injected signal is the shape a subtraction residue artefact would take, but one event supports no claim.

## 4. What this does NOT establish

- **§8.1 (runtime, flag on, against the 13 s hard budget) is not satisfied.** These scenes carry at most 11 decodes per cycle; the Developer's benchmark predicted about 26 s FFT-only for a busy **24-signal** cycle before parallelism. No busy real band has been run through this build.
- **§7 (stability gate) is not satisfied:** 1 h 49 min, 436 cycles, clean, is a data point, not a multi-hour stress pass.
- **§8.2 (independent real corpus) is not satisfied:** synthetic audio is not an independent corpus.
- **I cannot say which of ON's decodes came from the residual pass.** The daemon has no distinct residual-pass log line (tasks §4.2 is open); the S7 attribution above is inferred from OFF-vs-ON message flips, not observed.
- The design is one pairing, OFF first, ON about 5 minutes after: any same-day drift lands on the difference. WSJT-X's own +4 is a direct read of that noise.

## 5. Proposals (none started) — please rule

1. **Real-band replay to settle §8.1.** Select captured real cycles with ≥ 20 decodes from the existing endurance corpus and replay them through this build, flag OFF versus ON, offline; read per-cycle elapsed. No live run and no source change. It needs a pre-registered selection rule and a numeric bar before it is run (HK-021), and a decision whether the bar is the 13 s hard budget alone or the budget with headroom for slower hardware. **Your spec, or shall QA draft it?**
2. **Flag-OFF control for the S1 bias.** Replay the captured S1 audio (the OFF run's gathered WAVs; S1 predates the archive gap) through this DLL and through the pre-change `20260051` DLL, and byte-diff the decode output. This also settles the "flag-OFF is byte-identical" claim mechanically. **Do you want it before or after the merge decision?**
3. **Developer follow-up: tasks §4.2**, a distinct log line for the residual pass, so a future measurement can attribute decodes to it without a replay. `src/` change, so a Developer session (HK-011) after your and the Captain's go.

## 6. Disclosures and defects found (none affected results)

- **Display-setting difference between the runs.** The Captain changed `decodeNoiseSuppression.suppressSynthetic=false` through the Settings page during the OFF run; the ON config carried it from the start. Display only; it affects neither decoding nor `ALL.TXT`.
- **Settings-page save reset `cycleAudioArchive` to `off`** mid-OFF-run (server applies a fresh default on every save, because the page never sends the key). Filed as [#193](https://github.com/frank001/OpenWSFZ/issues/193). QA restored it live (about 16:42Z) with the Captain's agreement; **daemon-side captured audio for OFF is missing from about 15:58Z to 16:42Z** (S4's tail and most of S5). WSJT-X's own WAVs cover it. Decode results are unaffected.
- **`analyse.py` wrote the wrong SHA** (the QA tooling worktree's HEAD, `62e8e74a`) into the report and `trend.csv` — the third occurrence of the same defect; corrected by hand in the report and in the tracked `trend.csv` (both rows now carry `0d6b1937…`; the two rows share the SHA and are told apart by order, OFF first, since the file has no flag column). The pre-existing `2026-09-23` row still carries the tooling SHA `345e75ff` in the CSV (corrected in that report's prose only); left as found. **The standing recommendation stays unactioned:** `analyse.py` should read `arm_config.json`'s recorded build provenance instead of the analysis-time repo's HEAD.
- The detached launcher left a **visible, empty console window** (its "no console window" fix evidently regressed for one child). PRECHECK also refused to arm until `capture_build_provenance.py` was copied into the scratch build worktree and run (it derives its repo root from its own path).
- **Housekeeping done:** the raw results were preserved in the gitignored `artefacts/rr_2026-09-29_subfeas_off_on/` (file counts and byte sizes verified against the originals: 20/20, 20/20, 701/701, 880/880 files), and the two scratch worktrees were removed (HK-019: no stray worktrees or processes; the tooling worktree's `.venv` junction was removed first, and the real venv verified intact).
- **Discussion issue** [#194](https://github.com/frank001/OpenWSFZ/issues/194): triage and clean of synthetic captured-audio WAVs (anomaly scan against the rendered reference, on-demand clean before a backup). Discussion only; nothing built.
- **NFR-021:** the report and this message contain only synthetic `Q`-prefix content; no `ALL.TXT` message text; raw matched CSVs were not promoted.
- **Untracked, not committed:** `qa/rr-study/s1s8-config-subfeas-off/` and `…-on/` (the two configs used). I can commit them if you want the runs reproducible from the repository.

## 7. Where the Captain is

Decisions still his (HK-010, HK-033): merge sign-off for `feat/sub-feas-native-subtraction`; any push; and §8.3 (whether the flag is ever enabled in a live run). The flag stays OFF by default and in every live run. Nothing has been pushed.
