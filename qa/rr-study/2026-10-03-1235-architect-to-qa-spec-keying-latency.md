# SPEC: KEYING LATENCY k. From "decide to transmit" to the first FT8 sample leaving the PC, and as far as the radio as can be measured

- **To:** QA (owner; QA may assign the Engineer, with one owner recorded on the board). cc Captain. **From:** Architect. **Date:** 2026-10-03 ~12:35Z (HK-017, `date -u`).
- **Branch:** `arch/sub-feas-stage-b` (local). Docs only: `git diff --stat -- src/ native/` is empty.
- **Why (Captain, 2026-10-03, "yes, proceed"):** companion to SUB-FEAS speed spec Amendment 5 (§5h, Stage B re-aimed at batch 2's arrival time). The lateness ruling's Q2 used k ∈ {0, 0.5, 1.0} s **because k had never been measured** (`2026-10-02-2225` §3: *"k is unmeasured"*). The same-slot reply condition is **median T2 ≤ 2.95 s − k**. Stage B's bar (2.50 s) assumes k ≲ 0.45 s. This spec replaces that assumption with a number.
- **Status:** PRE-REGISTERED. Harness, row predicates and analysis are committed as code before the first measurement.
- **Needs:** K1 needs nothing (data already on disk). K2 needs about 1 h of PC time, **no RF, the radio not keyed**, no build, test-only code under `qa/`. K3 (RF) is **optional** and needs the Captain (§3.3). Not during the Engineer's #122 gate 4a run or any other timing run (CPU rule).

## 1. What k is, in parts

For a same-slot reply, **k** is the time from the moment the software decides to transmit to the moment the first FT8 symbol is on the air. The path is in the code (`src/OpenWSFZ.Daemon/CatPttController.cs:130-160`):

| Part | From → to | Where it comes from |
|---|---|---|
| `k_dec` | batch published → TX decision | **does not exist yet.** The automation is fenced from batch 2 (P-5). Measured here only through its nearest existing path, the immediate engagement (`POST /api/v1/tx/engage-decode`, `WebApp.cs:1529`), which keys at once (decision record §5e of the speed spec) |
| `k_ptt` | `KeyDownAsync` → CAT PTT asserted | `_pttGate.SetPttAsync(true)` (`CatPttController.cs:147`), logged at `:150` |
| `k_lead` | PTT asserted → playback called | `ptt.LeadTimeMs` (`PttConfig.cs:45`, default **50 ms**). QA reads the station's actual value |
| `k_audio` | playback called → first sample rendered at the TX audio endpoint | WASAPI buffering, plus Voicemeeter if the TX path goes through it |
| `k_rig` | sample at the endpoint / PTT command → RF out | the FT-991A's USB audio path and its TX switching. **Not measurable without RF** (K3) |

**What the instrument already records (HK-027).** The daemon's **file log** stamps lines to the millisecond (e.g. `2026-06-22 21:04:45.611 +02:00 [INF] TX KeyDown — starting playback …`, `artefacts/2026023_live run/openswfz-20260622T185757Z.log`). The console log (`[HH:mm:ss]`) does not. So `k_ptt` and `k_lead` can be read from past runs, without any new run.

## 2. Parts of the measurement

### K1: from logs already on disk (HK-018; run first)

- List every daemon **file** log under `artefacts/` that contains TX lines (`KeyDown`/`PTT asserted`). Count them by PTT controller (CAT, audio-only, serial).
- Per TX event, from the ms stamps: `KeyDown` decision line (QA names the line logged at TX entry in `TransmitAsync`, with FILE:LINE) → `PTT asserted` → `starting playback` (where logged) → `playback completed`. Report each interval's distribution.
- Report the playback duration against the nominal 79 × 0.16 = 12.64 s plus the buffer. A consistent excess is a lower bound on `k_audio`'s tail.
- **Engage path:** for events started by `engage-decode` (if the logs show it), the request line → `PTT asserted`. That is the nearest existing measure of `k_dec` + `k_ptt`.
- Read the station's current `ptt` config (method, `LeadTimeMs`) and `AudioOutputDeviceId` from `GET /api/v1/config`, or from the config file if the daemon is down. Read only.

### K2: no-RF bench measurement of `k_audio` (test-only harness)

- 🔴 **No RF, ever.** The radio is not keyed. The harness calls the daemon's **player** class (the one `CatPttController` uses, `_player.PlayAsync`) directly from a test program, **without** any PTT controller. Nothing asserts PTT.
- **Endpoint:** the same TX render endpoint the station uses (K1's `AudioOutputDeviceId`).
  - 🛑 **If that endpoint feeds the radio**, its VOX or data-VOX could key the transmitter. QA confirms with the Captain that **VOX is off** before K2. If that cannot be confirmed, K2 runs on a Voicemeeter virtual input with the **same sample format and buffer settings and no route to the radio**, and the report labels `k_audio` *"bench endpoint, not the station's TX endpoint"*.
  - **Answered 2026-10-03 (Captain, photo of the FT-991A screen, radio clock 13:01Z, relayed by QA):** VOX key **OFF**, MOX OFF; menu 142 VOX SELECT = **DATA**, 146 = 50, 147 = 100 ms. ⇒ K2 **may** use the station's TX endpoint. **No re-check before playback (Captain, ~13:1xZ: *"My word that no settings have been changed is enough."*).** The K2 report quotes his word and the 13:01Z photo reading as the VOX basis. If he ever says a setting has changed, K2 stops and uses the labelled bench endpoint. With VOX SELECT = DATA, a VOX switched on would let PC audio key the transmitter. That is why this basis is quoted, not assumed.
- **Signal:** a 12.64 s FT8-length buffer whose first sample is a sharp onset, a full-scale 1 ms tone burst after exact digital silence. **n = 200 playbacks**, started at seeded random offsets within the second.
- **Timing:** a WASAPI **loopback** capture of the same endpoint, using the capture API's **device position / QPC timestamp** for each buffer, not the time the buffer arrived. QA names the library (permissive licence only) and the field used. The playback-call instant is stamped with the same QPC clock immediately before `PlayAsync`. `k_audio` = QPC(first captured sample of the onset) − QPC(call).
  - If the library cannot expose QPC positions, use arrival times. The report then labels `k_audio` as an **upper bound**, inflated by up to one capture buffer (stated in ms).
- **Positive control (HK-026):** in half the trials, chosen by the seed, the harness waits an **extra 200 ms** before `PlayAsync`, **inside** the timed interval. The two halves' medians must differ by **200 ± 5 ms** (row K2-PC). If they do not, the instrument cannot see a known delay, and no `k_audio` is reported.

### K3 (optional, RF; the Captain decides): `k_rig`

- Only with the Captain's go and his set-up: the radio into a **dummy load** at minimum power, and an RF-onset detector that he chooses (e.g. the SDR, idle since 2026-09-21, connected through a sampler, or a second receiver), timestamped on the PC clock.
- Measures `KeyDown`'s `PTT asserted` stamp → RF onset, and audio onset → modulated RF.
- Until K3 runs, `k_rig` is reported as **unmeasured**, and every total says *"k without the radio"*.

## 3. Rows

**Validity (if a row FAILS, the part it guards is not reported):**

| Row | Predicate |
|---|---|
| K0 | Station config read (method, `LeadTimeMs`, output endpoint) and recorded. K2's harness reads back the endpoint it opened and asserts it equals the recorded one, or that it is the labelled bench endpoint |
| K1-n | ≥ 20 TX events with ms stamps found, for the PTT method the station uses now. If fewer, K1 is reported as *"thin"*, with its n |
| K2-PC | positive control: |median(delayed) − median(plain) − 200 ms| ≤ 5 ms |
| K2-n | 200 playbacks recorded; 0 with no detected onset |
| K2-safe | PTT never asserted during K2: the harness constructs no PTT controller (asserted in code), and the daemon is not running, or runs with TX disabled. Read back |

**Outputs (no bar; this is a characterisation):**
- `k_ptt`, `k_lead` and the engage-path interval (K1): median, p95, max, n.
- `k_audio` (K2): median, p95, max, n, labelled exact (QPC) or upper bound.
- **`k_PC` = `k_ptt` + `k_lead` + `k_audio`** (medians, and a p95 sum labelled conservative), and the implied same-slot condition **median T2 ≤ 2.95 − k_PC** (and − `k_rig` if K3 ran). This is the number Stage B's T2′ margin (0.45 s) is checked against at its ruling.

## 4. Limits

- `k_dec` for the automation's batch-2 path cannot be measured, because that path does not exist. The engage path is a proxy and is labelled so.
- K2 measures the PC side on this PC. Without K3, the radio's share is unknown.
- The partner's tolerance is WSJT-X's (lateness edge +2.75 s, a cliff, synthetic AWGN), as in Q2.

## 5. Predictions (blind; scored at ruling time)

| # | Prediction | P | Class |
|---|---|---:|:---:|
| KL1 | `k_PC` median (K1 + K2) ≤ 250 ms | 0.65 | H |
| KL2 | `k_audio` median ≤ 120 ms | 0.55 | H |
| KL3 | K1 finds ≥ 20 CAT-method TX events with ms stamps | 0.70 | H |
| KL4 | K2-PC passes the first time | 0.70 | H |
