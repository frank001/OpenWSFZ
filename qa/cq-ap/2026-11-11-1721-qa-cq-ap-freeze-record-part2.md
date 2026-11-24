# CQ-AP (candidate #2): FREEZE RECORD, PART 2 (analysis code, harness, dry-run), before either arm's output exists

**Author:** QA · **Written:** 2026-11-11T17:2xZ (`date -u` read 17:20:12Z while computing the hashes below) · **Completes:** Part 1 `342d320b` (`qa/rr-study/2026-11-10-2127-qa-cq-ap-freeze-record.md`), per the Architect's Amendment 3 (A3.1).
Part 1 is unchanged. No callsign, message text or per-decode row appears in this record (NFR-021, HK-037).

## 1. No arm output exists
- No OFF, ON, OFF2 or REF run has been started. `arms\` (the output folder) does not exist; `cqap_analysis.py --run` has never been run.
- The only replay output that exists is the **dry run** of section 4, on the OLD night `20260930_1930` (40 cycles), not on a cycle of the live window. Its outputs are discarded and enter no row.

## 2. The analysis code (committed; this commit is the freeze of the code)
Commit **`32a17b0eb11d6b1536f166e573a02bfc3c934eeb`** on `qa/same-chain`. Git blob hashes (`git ls-files -s`):

| file | blob |
|---|---|
| `qa/cq-ap/cqap_analysis.py` | `39f1c14a9ffbf79d54fb0aa7cfea3d934bc5cf1d` |
| `qa/cq-ap/cqap_selftest.py` | `d24b3be1b5ec6bc5fa2614daa4202eec7acea47a` |
| `qa/cq-ap/cqap_arms.sh` | `545e54344299135be5633006123ecd4b59d21d7c` |
| `qa/cq-ap/cqap_make_selection.py` | `15f4d4c3bb93d817934993fc343489dafbe78045` |
| `qa/cq-ap/live-session-cycle-list.txt` (Part 1) | `c12667fe331753b635a4f00ce32c9c4e4460f5c1` |
| `qa/cq-ap-psk/cqapsk_analysis.py` (imported: match rule, spot reader, V-SELF reader) | `29ce29b96683f5785c2871dba2ce481aeff7eb9d` |
| `qa/cq-ap-psk/c28_ghosts.py` (imported by the above) | `8d8813f05c183b9ac421bb755f80aa2f477a6dcf` |
| `qa/rr-study/sub-feas/replay81/Program.cs` | `7b93d4a8009dbee376b6005ca0d1379c68660e7b` |
| `qa/rr-study/sub-feas/replay81/StageProbe.cs` | `6045dfae465c0af40a2dfacf802ca2422018b618` |
| `qa/rr-study/sub-feas/replay81/Replay81.csproj` | `031e5be1f141f2d8047727a00b42d94ea7daf690` |

What the code does (every constant is asserted in the code, not recalled here): seed **20261111**, B = 2000 cycle resamples, 95 % percentile intervals; match = spec §3 (sender exact, rc without the station call, FT8, |t_tx − cycle start| ≤ 1800 s, |f − (dial + audio)| ≤ 50 Hz, or the same text decoded by WSJT-X in the same cycle); hashed-call texts excluded and counted; one AP-only extra per (cycle, text); rows V-NAT, V-SET (all four arms incl. same thread count), V-OFF (first 50 cycles, outcome fields kind/freq/dt/snr/path only, abandon cycles excluded and counted, more than 5 excluded fails), V-FEED, V-SELF (≥ 0.90), G-GAIN (CI_lo K_C > 0), NO-GAIN (A1.1: CI_hi (K_C + K_N)/D_OFF < 0.15 %), U-UB (CI_hi K_N per cycle ≤ 0.021), T-TIME (p95 difference ≤ 1.0 s, abandoned cycles per 100 ≤ OFF + 1); verdict VOID, NO-GAIN, SHIP-CANDIDATE, FP-UNRESOLVED, BETWEEN in that order. **Two stated reading choices, fixed now:** (a) a "cycle abandons" if any of the fallback, residual pass, third pass (abandoned or failed) or late round abandoned (as `kr_analyse.timing`); (b) an AP-only extra whose text does not start with `CQ` cannot be feed-matched, so it counts as uncorroborated unless WSJT-X decoded it (reported on the N-1 line). Descriptive lines as Part 1 §2, plus "extras with an OFF decode within 5 Hz in the same cycle" (descriptive only).

## 3. Self-test
`python qa/cq-ap/cqap_analysis.py --selftest` → **`cqap selftest: ALL PASSED`** at `32a17b0e`. Synthetic Q-prefix data only; runs the same `analyse()` the real run uses end to end (counts, edge values ±50 Hz / ±1800 s, own-receiver and FT4 and other-sender negatives, hashed and non-CQ lines, all five verdicts, V-OFF exclusion logic, V-SELF fail, feed gap, wrong DLL, wrong head, determinism). **Mutation check:** 14 single-line breaks of the analysis (verdict order, hashed exclusion, each bar's `<`/`<=`, NO-GAIN on K_C only, text in the V-OFF key, abandon slack, OFF-text exclusion, WSJT-X corroboration, exclusion limit, seed) were all KILLED. Two of the first nine survived (the U-UB boundary and the A1.1 "uncorroborated only is not no-gain" case); tests were added before this commit.

## 4. Replay81 dry-run repeat (A1.6), on the pinned DLL
- Binaries (built from the committed harness; the freeze's two builds): `_qa-scratch\cq-ap\bin_on` (RepoRoot = clean checkout `cq-ap-src` at `7ca00264`, `-p:HasCqAp=true`) with `libft8.dll` **`bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528`** (= the pin); `_qa-scratch\cq-ap\bin_ref` (RepoRoot = `tree_ref` at `98332f2a`, no `HasCqAp`) with `libft8.dll` **`1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914`** (= the V-OFF reference pin). `Ft8.FitProbe.dll` SHA-256: ON `2a1c3f48…dc21a`, REF `1f4585ae…89bbd`.
- Run: `bash qa/cq-ap/cqap_arms.sh dry` (40 cycles of `20260930_1930`, `--cq-ap 0` then `--cq-ap 1`), 17:11:53Z to 17:19:50Z, both rc 0, preflight ok (pin at start and end, readback tokens incl. `cqap=False` / `cqap=True`, 8 threads), orphan check clean. **WSJT-X was not running** (no `wsjtx.exe` in the process list).
- **Plumbing result only (not a gain, loss or timing):** forwarding works this time: the OFF arm has 0 rows with `apKind = cq` and 0 `cq-ap:` log lines; the ON arm has 40 `apKind = cq` rows and 40 `cq-ap:` lines. (The first dry run, before `b87b63fe`, had ON identical to OFF.)

## 5. The exact invocations (fixed)
- Selections: `python qa/cq-ap/cqap_make_selection.py` → `sel_500.json` SHA-256 `c618a66e24bb0d129aa6f5df0ecdad978a53f4b0e9e991d308557378fef5de7f` (500 cycles, warm-up cycle `261110_184730`, discarded), `sel_50.json` `2ea8029d14821b45755451f37c1c9fb47e0345d08ca6fa58f6ff3ae94ea89bbd` (first 50). The list's SHA-256 `842e6790…c8f9` is asserted by the script.
- Arms, in this order, each detached and logged, PC exclusive, WSJT-X idle: `bash qa/cq-ap/cqap_arms.sh OFF2`, `OFF`, `ON`, then `REF` (OFF2 first because it is the OFF-vs-OFF repeat; OFF and ON follow, as Part 1 §2). Parameters of every CQ-AP arm are the ones in the script header (Deep, nhard 24, 5 / 0.05, multi-set, `Both`, R-F4, L1′, 8 threads); the only difference between OFF and ON is `--cq-ap`.
- Analysis, once: `python qa/cq-ap/cqap_analysis.py --run --arms-dir _qa-scratch\cq-ap\arms --tree-on _qa-scratch\cq-ap-src --tree-ref _qa-scratch\cq-ap\tree_ref --bin-on _qa-scratch\cq-ap\bin_on --bin-ref _qa-scratch\cq-ap\bin_ref --cycle-list qa/cq-ap/live-session-cycle-list.txt --spots _qa-scratch\cq-ap\spots_raw.jsonl --wsjtx-all-txt artefacts\20261110_1817_cq-ap-live\wsjt-x\ALL.TXT --daemon-log artefacts\20261110_1817_cq-ap-live\owsfz\daemon-stdout.log --cap-start 261110_181737 --cap-end 261110_212230 --dial-hz 7074000 --out _qa-scratch\cq-ap\cqap_result.json`.

## 6. Status
**The freeze (Part 1 + Part 2) is complete with this commit.** Arms start only on the Captain's go with the PC free and WSJT-X idle. Any change to the files above after this commit is a dated, signed amendment before any arm output is read.
