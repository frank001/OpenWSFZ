# CQ-AP-PSK: FREEZE RECORD (before any rate is computed)

**Author:** QA · **Written:** 2026-11-10T15:38Z (`date -u` read 15:38:35Z) · **Spec:** `arch/cq-ap-psk-check` `qa/rr-study/2026-11-10-1153-architect-to-qa-spec-cq-ap-psk-check.md` with Amendment 1 (`42084a11`, §7) and Amendment 2 (`8202d245`, §8).
No callsign, message text or per-decode row appears in this record (NFR-021, HK-037).

## 1. What is frozen
| item | value |
|---|---|
| **Analysis code** | commit **`39f40ea454210e70c8aa957309de6bfe0c4aa028`** on `qa/same-chain` (local): `qa/cq-ap-psk/cqapsk_analysis.py` (blob `29ce29b96683f5785c2871dba2ce481aeff7eb9d`), `c28_ghosts.py`, `cqapsk_selftest.py`, `PlausibleGate/Program.cs` + `.csproj`. Synthetic self-test passes (`python -I cqapsk_analysis.py --selftest` → `SELFTEST OK`). |
| **Capture** | start **2026-11-10T11:56:28Z** (`date -u`, written at the recorder launch; the recorder logged `connect` at 11:56:28.57Z), end **2026-11-10T15:30:48Z** (`date -u` at the stop of both). One recorder run, no restart. |
| **Spot file** | `D:\Projects\claude\_qa-scratch\cq-ap-psk\spots_raw.jsonl`: **6,922,228 lines** (1 connect line + 6,922,227 messages), SHA-256 **`43cdf5af57822dcae2222aee9e5100932b0f3782faf9c88df86b332d78091f49`**. Stays in scratch; deleted at job close. |
| **Decode source** | OpenWSFZ's own `ALL.TXT` (station config `decodeLog.path`, repo-root `ALL.TXT`, gitignored), cycles from the daemon start 11:35:28Z to the capture end. WSJT-X's `ALL.TXT`: **absent** (`%LOCALAPPDATA%\WSJT-X\ALL.TXT` does not exist; no wsjtx process during the session). |
| **Daemon** | `_run-main` `98332f2a` (v0.69), `libft8.dll` SHA-256 `1ba8dc3d6a7d0327…db914` (= pin); up 11:35:28Z to 15:30:48Z; PSK Reporter upload ON the whole time. |
| **Ghost seed** | **20261110**, `numpy.random.Generator(PCG64(20261110))`; one block of **400,000** `n28` draws (int64, uniform on [6,257,896, 268,435,455]) then one block of **400,000** donor indices (uniform over P_R in window), then the shuffle partners from the same generator. Consumed in order until 10,000 ghosts are accepted. |
| **`rx_call` exclusion** | any spot whose `rc` contains `PD2FZ` never matches; counted for V-SELF. |

## 2. Fixed rules (restating the spec; one script, run once)
- **Window:** decode cycle start in [capture start + 1800 s, capture end − 1800 s] = **[12:26:28Z, 15:00:48Z]**; any feed gap > 120 s (V-FEED), widened by 1800 s each side, is excluded and counted.
- **Match (CORROBORATED), A1.1:** a spot with `sc` equal to the sender (exact), `rc` not containing `PD2FZ`, `md` = FT8, |`t_tx` − cycle start| ≤ 1800 s (`t` only if `t_tx` is missing; counted), |`f` − (dial + audio offset)| ≤ 50 Hz.
- **Truth population, A1.3/A1.4:** WSJT-X is absent, so **V-REF fails and P_R gates** (verdict labelled "(P_R)"). P_R = our CQ decodes (one per cycle and sender) whose sender we decoded as a CQ in **at least 2 other cycles within ±600 s, each within ±10 Hz of the decode's audio offset**. Bins on OUR SNR (`ALL.TXT` field [4]): **≥ −10 / −11…−15 / −16…−18 / ≤ −19**; weak bin ≤ −19, next bin −16…−18.
- **Ghosts, A2.0–A2.2:** `n28` → 6-character field by the mixed-radix inverse (constants asserted in the code: NTOKENS 2,063,592, MAX22 4,194,304, 262,177,560 standard values), trimmed. A candidate is dropped if it is empty or has an internal space, then dropped unless **`IsPlausibleMessage("CQ <ghost> <donor grid>", live grammar)` is true**; the donor grid is the donor message's last token if it is a 4-character grid, else the message is `CQ <ghost>`. The first **10,000** accepted are kept; the rejected share is reported. A ghost takes its donor's cycle time and absolute frequency; matched as above (exact trimmed `sc`).
- **Plausibility call: THROUGH THE PRODUCT ASSEMBLY (not a port):** `qa/cq-ap-psk/PlausibleGate` loads `OpenWSFZ.Ft8.dll` and `OpenWSFZ.Daemon.dll` from `_run-main\src\OpenWSFZ.Daemon\bin\Release\net10.0\win-x64\publish` (`98332f2a`) and invokes `Ft8Decoder.IsPlausibleMessage(text, store)` by reflection with a `CallsignGrammarStore` loaded from a **copy** of the station's `callsign-grammar.json` (SHA-256 starts `7b581f31b7f0f651`, identical to the station file). Smoke test (synthetic Q calls): `CQ Q1ABC FN42` accepted, `CQ DX Q1ABC` accepted, `CQ  Q1ABC` rejected, `Q1ABC Q2XYZ -10` accepted, `CQ Q1ABC ZZ99` rejected.
- **Shuffle P_S:** each P_R member's sender re-paired with another P_R member at least 7,200 s and 200 Hz away (random among the eligible); members with none are dropped and counted. Descriptive.
- **Rows and bars (unchanged from the spec):** G-COVER Wilson-95 lower bound of C_weak ≥ 0.40; G-SLOPE C(next) − C_weak ≤ 0.20; G-GHOST Wilson-95 upper bound of the ghost share ≤ 0.02; V-SELF ≥ 0.90 (spots with `rc` containing `PD2FZ` ÷ the sum of `{Reported}` in the daemon's "PSK Reporter: N decodes seen, M reported" lines whose send fell inside the capture; log stamps are local, offset +3600 s asserted against the "Cycle HH:MM:SS" UTC stamps); N-INSUFF: fewer than 30 P_R decodes in the weak bin. Verdict order: INSUFFICIENT, NOT-USABLE (C_weak upper < 0.40 or ghost point > 0.05), USABLE, BETWEEN. G-GHOST is a guard, not a discriminating row (A2.3).

## 3. QA choices where the spec was silent (fixed now, before any rate; the Architect may object before the run)
1. **P_R recurrence counts CQ decodes of the same sender only** (the sender of a non-CQ message cannot be told apart from the other party). Recurrences are counted over the whole daemon-up period, not only inside the window; membership is tested only for decodes inside the window.
2. **G-SLOPE when the −16…−18 bin is empty:** undefined ⇒ the row **fails** (and the report says "undefined").
3. **V-FEED gaps** only exclude time (they do not change the verdict); V-FEED itself is reported as the count of gaps > 120 s.
4. **V-SELF** compares feed spots whose `rc` contains `PD2FZ` over the capture with the log's reported-record sum; the denominator window is "send inside the capture" by the log's time of day on 2026-11-10.
5. **Descriptive call+band-only line:** `sc` match with |`t_tx` − cycle start| ≤ 1800 s and no frequency limit.

## 4. What was done before this freeze (disclosure)
- **Raw feed:** one print of the first 700 bytes of the spot file (keys), and the key statistics on a 22,270-row prefix: `t` − `t_tx` min 0, median 0, max 20 s; 94.6 % of `t_tx` on 15-s boundaries. No call, no rate, no match.
- **ALL.TXT:** the line count (129,094 lines in the whole file) and the last two lines with callsigns masked (to confirm the field layout). No CQ count and no repeat count was computed.
- **Ghost proof (A2.0):** `c28_ghosts.roundtrip` against **ft8_lib** through `libft8.dll` `ft8_encode_message` (text → 79 tones → payload bits → c28): seed 20261111 (not the freeze seed): **20,000 draws, 18,619 unpack to a packable trimmed call, 18,619 of 18,619 read back to the identical `n28` (0 mismatches)**; a throwaway seed 1 run: 18,648 of 18,648. About 7 % of uniform draws are not a space-free call (internal space), which is why the rejection step exists.
- **Not yet run:** the real analysis (`--run`). The §3 first-live-session report (`959d15c6`) used the daemon log only and computed nothing CQ-AP-PSK uses.

## 5. The run (one invocation, after this record is committed)
`python -I qa/cq-ap-psk/cqapsk_analysis.py --run --all-txt D:\Projects\claude\OpenWSFZ\ALL.TXT --spots …\spots_raw.jsonl --daemon-log …\live-rf4on\daemon_final.out --cap-start 261110_115628 --cap-end 261110_153048 --daemon-start 261110_113528 --gate-dll …\gate-bin\PlausibleGate.dll --pub-dir <publish dir above> --grammar …\callsign-grammar.copy.json --out …\cq-ap-psk\result.json`. Aggregates only; the report quotes `result.json`.
