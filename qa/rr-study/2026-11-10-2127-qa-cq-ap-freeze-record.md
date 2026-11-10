# CQ-AP (candidate #2): FREEZE RECORD, PART 1 (inputs), before either arm's output exists

**Author:** QA · **Written:** 2026-11-10T21:27Z (`date -u` read 21:26:49Z while computing the inputs below) · **Spec:** `arch/cq-ap` `qa/rr-study/2026-11-10-1546-architect-to-qa-spec-cq-ap-build.md` with Amendment 1 (A1.1 to A1.8), Amendment 2 (§9, A2.1 to A2.6).
No callsign, message text or per-decode row appears in this record (NFR-021, HK-037).

🔴 **This record is PART 1. It is NOT complete.** The spec's freeze list includes "the analysis code" (the match, the cycle bootstrap, the arm driver and the V-OFF check). **That code does not exist yet.** Part 2, an addendum giving its commit hash, is committed BEFORE any arm output exists. Until Part 2 is committed, no arm may run. Nothing in Part 1 can change once written, except by a dated, signed amendment.

## 1. What is frozen
| item | value |
|---|---|
| **Build under test** | `feat/cq-ap` **`7ca00264a5a8d1af7a0f5ab4c8f97f60243572b1`** (v0.70, shim 20260072; main `98332f2a` plus that one commit), HK-039 APPROVED (`a6255625`). Clean checkout in `_qa-scratch\cq-ap-src`; full suite on it green (exit 0; Ft8 706/706). |
| **DLL pin** | `libft8.dll` SHA-256 **`bbde6eb66af4cd429ffc46f67291ba718c1ae36ae39665faac24629bcb6e6528`** (the self-contained non-AOT publish in `_qa-scratch\run-cq-ap\`, asserted before the live start; the arms use this DLL). |
| **V-OFF reference** | `98332f2a` (v0.69), `libft8.dll` SHA-256 `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914` (the `_run-main` publish). |
| **Live session** | era **"CQ-AP ON live"** (Captain, A2.6). Recorder start **18:17:37Z** (connect logged 18:17:37.607Z; `date -u` 18:17:38Z), daemon start **18:17:43Z**, daemon `taskkill /F` **21:22:21Z**, recorder killed **21:22:30Z** (one `date -u` for the recorder; the last feed message arrived 21:22:26.586Z). One recorder run, no restart. Final `/status`: Capturing, 0 restarts, 0 overruns, 0 dropped chunks, 0 dropped archive cycles. |
| **Spot file** | `D:\Projects\claude\_qa-scratch\cq-ap\spots_raw.jsonl`: **4,061,374 lines** (1 connect line + 4,061,373 messages), SHA-256 **`74dabe81912d01ce2b24e2b8f65c5272968d04a375d9df14a38b62bc393fd952`**; first message 18:17:37.779Z, last 21:22:26.586Z. **Feed gaps > 120 s: 0** (V-FEED). Stays in scratch until the Architect's ruling on THIS build (HK-037). The ~2 min wrong-build file beside it is not part of the window. |
| **Window** | decode cycle start in **[capture start + 1800 s, capture end − 1800 s] = [18:47:37Z, 20:52:30Z]** (capture start 18:17:37Z, end 21:22:30Z). No feed gap, so nothing is widened. |
| **Cycle list** | `qa/cq-ap/live-session-cycle-list.txt` (committed with this record): **500 cycles**, `261110_184745` to `261110_205230`, every window cycle in the archive manifest with its WAV present (0 missing, 0 with `dropped_before` > 0). SHA-256 **`842e67909378a0d1dbf387b27d2e080b4f1e8c1dec3e9bd9770e2e3bac76c8f9`**. Both arms replay exactly these 500 cycles. (The spec's "600 to 800" was an estimate; 2 h 5 min is 500 cycles.) |
| **Archive** | `artefacts\20261110_1817_cq-ap-live\`. `owsfz\cycle-archive.csv` SHA-256 `0adb7e191aa5cd93b485d7716ab4fb1ee905008641432539e3057aceec4dedec`; `owsfz\ALL.TXT` (18,445 lines) `1d906f8b2a5da3afcf09d471774338430ddec9e02919f13bf393ed0cd974b679`; `wsjt-x\ALL.TXT` (21,193 lines) `8bb8d8dd8796b3018d8a33e223e517bc23fef34ce5204aeb4ec7eb862db7549e`. |
| **Seed** | **20261111** for every random step in the analysis (the cycle bootstrap, B = 2000). |
| **Live config (read back at stop, `config_at_stop.json`)** | `decodingDepth` Deep; `osdNhardMax` 24; `kMinScorePass2` 5; `osdCorrThreshold` 0.05; `subtractionEnabled` true; `lateSubtractionRound` true; `coherentFallbackEnabled` true, `coherentFallbackMultiSet` true, `coherentFallbackAudio` Both, `coherentFallbackResidualUngated` true; `earlyDecodeEnabled` true (cut 3 s); `subtractionMaxThreads` 0; **`cqApEnabled` true (live only)**. CAT off, dial 7.074 MHz, receive-only, `cycleAudioArchive` all, direct USB CODEC. |
| **WSJT-X reference** | present this time: the `frans` profile `WSJT-X - FT991A`, `NDepth=3` (Deep), `FT8AP=false`, PSK spotting OFF, SaveAll true. 500 of 500 window cycles have a WSJT-X WAV and an OpenWSFZ WAV. A WSJT-X decode of the same message in the same cycle counts as corroboration (spec §3). |

## 2. Arms (spec §3, restated; fixed now)
| arm | build | `cqApEnabled` | harness |
|---|---|---|---|
| **OFF** | `7ca00264`, DLL pin above | false | Replay81 `--cq-ap 0` |
| **ON** | same build, same DLL | true | Replay81 `--cq-ap 1` |

- Both arms: the live configuration above except `cqApEnabled`, one fixed thread count (the same in both, logged by each run; V-SET), the 500 cycles of the list, **PC exclusive and WSJT-X idle** (T-TIME compares timings), station daemon stopped.
- **V-OFF:** the OFF arm's outcome fields against a `98332f2a` replay on the **first 50 cycles of the list**, counting only cycles in which neither run abandoned any stage (excluded cycles counted; V-OFF fails if more than 5 of the 50 are excluded). Outcome fields only, never rendered text.
- **Rows, bars and verdict order: exactly the spec §4 as amended** (V-NAT, V-SET, V-OFF, V-FEED, V-SELF, G-GAIN, NO-GAIN on `(K_C + K_N) ÷ D_OFF` < 0.15 % per A1.1, U-UB at 0.021 per cycle, T-TIME at 1.0 s and +1 abort per 100 cycles). No bar is changed or added here.
- **Descriptive lines (no gate):** K_C and K_N per our-SNR bin; share corroborated by WSJT-X versus by the feed; AP-only extras per 100 cycles; `cq-ap` attempts per cycle; **A1.7** ON-only decodes with `apKind = none` and OFF-only decodes, per 100 cycles; the **N-1 line** (decodes tagged `cq` whose message does not begin with `CQ`, flagged if more than 10 % of the AP-only extras); the **OFF-vs-OFF repeat line** (a second OFF run on the same cycles, to size run-to-run variation).
- **Corroboration match:** the spec §3 rule: the sender equals `sc` (exact), `rc` does not contain the station call, FT8, |`t_tx` − cycle start| ≤ 1800 s, |f − (dial + audio)| ≤ 50 Hz; or WSJT-X decoded the same message in the same cycle. Messages with hashed calls are excluded and counted. All comparisons inside one function (HK-037).
- **Citation limits:** the sweep result (`53d63d71`) and the dry-run numbers are NOT a gain, loss or timing. The live-era `ALL.TXT` figures (CQ-AP ON live) are descriptive only and never pooled with "RF4+L1′ ON".

## 3. Disclosure: what was looked at before this freeze
- **Counts only, no rates of interest:** the spot file's line count, SHA-256, first and last arrival and the number of gaps over 120 s; the manifest row and WAV counts; the live daemon's final `/status` counters; the number of cycles with a `cq-ap:` line in the daemon log (739) and how many had at least one CQ-AP decode in the first hour (128 of the first 251). These are raw per-cycle log counts with no callsign. They are NOT a result and are not used in any row.
- **Captain's display check** ("looking fine from here"): a footnote only.
- **Not computed:** no `apKind` split, no match, no K_C or K_N, no V-OFF, no replay of any arm.
- **Disclosed deviation to the record:** the first live start (18:09:33Z) ran the wrong build (`98332f2a`); about 2 min of data were discarded and the session was restarted 18:17Z (QA ledger Q51; Amendment 2 records the change of direction).

## 4. Part 2 (owed before any arm runs)
- Commit the analysis code (match, bootstrap, arm driver, V-OFF diff, descriptive lines), with a synthetic self-test that passes, and an addendum to this record giving its commit hash, its blob hashes and the exact invocation.
- Dry-run the Replay81 harness on the CQ-AP build (A1.6: done for `--cq-ap` and `apKind` in `344da888`/`b87b63fe`; the 40-cycle dry-run with real forwarding is to be repeated on this DLL).
