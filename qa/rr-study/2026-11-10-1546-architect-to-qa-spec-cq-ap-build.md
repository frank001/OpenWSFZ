# `CQ-AP` build spec: a CQ a-priori decode attempt behind a default-OFF flag, measured by an OFF/ON replay of one live session against PSK Reporter

**From:** Architect · **To:** QA (Developer task via QA, HK-015) · **Date:** 2026-11-10 15:45:58Z (`date -u`) · **Branch:** `arch/cq-ap`
**Authority:** the Captain, 2026-11-10, on the CQ-AP-PSK ruling's §3 proposal: "spec it". Candidate #2 of the decode programme.
**Base:** `origin/main` `98332f2a` (v0.69). **This spec asks for a `src/` + `native/` change: a separate Developer session (HK-011), QA review before any replay (HK-039), `pre_merge_check` before any push (HK-006).** This document is docs only.
**Prior ruling:** `qa/rr-study/2026-11-10-1541-architect-cq-ap-psk-ruling.md` (`af7389bd`): PSK Reporter corroboration is a **one-sided** instrument. A corroborated extra is real (ghosts 0 / 10,000); a missing spot proves nothing.
🟢 **Size rule.** One build, one live session (shared with candidate #3), two replay arms. Anything more needs the Captain's word.

---

## §0. Why, in one paragraph

- WSJT-X's AP type 1 assumes a message starts with `CQ`. It fixes those bits before LDPC, so weak CQ calls can decode that otherwise would not.
- We have the mechanism already. `ftx_decode_candidate_ap` (`native/ft8_lib_build/patched/ft8/decode.c:1083`) overwrites chosen LLRs with ±40 (`FT8_AP_LLR_HARD`, `src/OpenWSFZ.Ft8/Native/ft8_shim.c:648`) before normalisation. Today it is used only for **QSO context** (my call / his call bits, `ft8_set_ap_bits`, `ft8_shim.c:1644`).
- **The risk:** AP is WSJT-X's main source of false decodes. Our reference WSJT-X runs AP OFF, so it cannot confirm AP-only decodes. The PSK Reporter feed can, from one side only.
- **So the build is measured as two bounds.** Corroborated AP-only extras are a lower bound on the real gain; uncorroborated ones are an upper bound on false decodes.

## §1. The build (D-rows; QA turns these into the Developer task and reviews against them)

| row | requirement (mechanical) | why |
|---|---|---|
| **D1 Bits** | CQ-AP overrides **payload bits 0–28** (`n29a` = `c28`("CQ") `<< 1` \| `ipa` 0) and **bits 74–76** (`i3` = 1), with the existing sign convention (bit 1 → +`FT8_AP_LLR_HARD`, `ft8_shim.c:1773`, applied at `:1786`). **A unit test encodes `CQ Q1ABC JO22` with ft8_lib's own encoder and asserts that every overridden position equals the encoded bit.** No other bit is overridden | the positions come from the 77-bit layout as `ft8_shim.c:1790–1800` describes it; the test, not this table, is the authority. E151 and E152 are why this is a test and not a reading |
| **D2 Flag** | new decoder key **`cqApEnabled`**, **default `false`**, read like the other decoder keys and passed to the native layer. With the flag OFF, decode outcomes on a fixed WAV set are **identical** to `98332f2a` (mechanical diff of outcome fields, never rendered text) | OFF must be today's decoder. The station is unchanged until the Captain says otherwise |
| **D3 Extra, never instead** | the CQ-AP attempt runs **only on a candidate whose normal attempt failed** (the normal attempt includes QSO-AP when that is active), in every pass of `ft8_decode_all` on every buffer it is called on (original and residual). It never replaces a normal attempt. The coherent fallback is out of scope | an AP attempt that replaced the normal one would lose every non-CQ decode on that candidate (see §5, observation O1) |
| **D4 BP only** | the CQ-AP attempt runs **belief propagation only; OSD is not run on it**. A counter of OSD calls from the CQ-AP path reads 0 | with 32 bits forced the OSD gate's `nhard` never sees disagreement on them, so the gate is effectively looser. OSD-on-AP can be a later arm on the Captain's word |
| **D5 Filter unchanged** | CQ-AP decodes pass the same CRC, `IsPlausibleMessage` (`Ft8Decoder.cs:1461`, applied at `:803`) and text dedup as any decode | no new acceptance path |
| **D6 Tag** | every decode carries an `apKind` (`none` / `cq`) from the native result to the managed decode record. The replay harness writes it. The daemon logs one Information line per cycle: `cq-ap: attempts=N decodes=M` (counts only, never a callsign) | the measurement needs to know which decodes came from CQ-AP |
| **D7 Not uploaded** | decodes with `apKind = cq` are **not uploaded to PSK Reporter** (`PskReporterEngine`, a new counted exclusion reason `ap=`) | an unconfirmed AP decode must not become a public spot, and our uploads must never be able to corroborate our own AP decodes (§3 excludes our `rc` anyway) |
| **D8 Harness** | Replay81 gets `--cq-ap on\|off` and logs the effective value with the other parameters (V-SET) | as KMIN-OSD-RECAL A1 |
| **D9 Provenance** | shim version bumped; the new DLL's SHA-256 is the arms' pin | `FT8_SHIM_VERSION` identifies nothing; the SHA does |
| **D10 Synthetic** | on synthetic `Q`-prefix audio: (a) a `CQ Q1ABC JO22` at an SNR where the OFF build fails is decoded by ON with `apKind = cq`; (b) a non-CQ `Q1ABC Q2DEF JO22` is never decoded with `apKind = cq`; (c) noise-only audio gives 0 `cq` decodes over ≥ 200 cycles | proves the direction of the bits and the filter before any real audio |

QA reviews the Developer commit against D1–D10 and commits the `Reviewed-commit:` record before any replay (HK-039).

## §2. The corpus: the next live session, set up for both candidates

🔴 **Today's PSK capture is gone.** My CQ-AP-PSK ruling ordered its deletion at job close in the same document that proposed this build (E155). The feed has no history, so the corpus is a **new live session**. It does **not** need the build: the build is replayed against its audio afterwards, and the station never runs CQ-AP live in this test.

**The session (the Captain starts it; QA sets up and stamps it):**
- our daemon on `main` as deployed (era "RF4+L1′ ON"), **`cycleAudioArchive` ON from the start** (read back before the stamp; today's first 32 min were lost to it, QA Q47);
- **WSJT-X running alongside** on the same audio, **with its PSK Reporter spotting OFF** (one uploader per call: `openspec/changes/psk-reporter-upload/design.md`, risks);
- **QA's MQTT recorder running from before the daemon start to after its stop** (`record.py`, as for CQ-AP-PSK), raw file in `_qa-scratch\cq-ap\` only;
- **at least 3 h**, so that about 2 h of window remains after the ±1800 s trims.

**This one session also serves candidate #3** (a live WSJT-X reference for the default-ON era). It is one session, not two.

🔴 **HK-037 and retention:** the raw spot file and the per-callsign working files stay in `_qa-scratch\cq-ap\` **until the Architect's ruling on THIS build closes the job**, and not one step earlier.

## §3. The arms and the match

**Arms (PC, station daemon stopped, PC exclusive because timings are compared):**

| arm | build | `cqApEnabled` |
|---|---|---|
| **OFF** | the reviewed CQ-AP build | false |
| **ON** | the same build, same DLL | true |

Both arms use the session's live configuration (Deep, `nhard` 24, 5 / 0.05, multi-set, `Both`, R-F4 and L1′ ON), the same thread count, and **every archived cycle inside the window** (the window as in the CQ-AP-PSK spec §2: capture start + 1800 s to capture end − 1800 s, minus feed gaps).

**AP-only extra:** a decode in the ON arm with `apKind = cq` whose message does not appear in the OFF arm's output for the same cycle. Messages with hashed calls are excluded and counted. The comparison is made inside one function (HK-037).

**Corroborated:** the CQ-AP-PSK §2 match rule exactly, as amended. The sender equals `sc` (exact), `rc` does not contain `PD2FZ`, FT8, |`t_tx` − cycle start| ≤ 1800 s, |f − (dial + audio)| ≤ 50 Hz. **Or** WSJT-X decoded the same message in the same cycle. An AP-only extra that is neither is **uncorroborated**.

## §4. Rows and verdict

**Freeze** before either arm's output exists: build commit, DLL SHA-256, capture start and end with the spot file's SHA-256 and row count, the window, the cycle list, the analysis code, the seed **20261111**, and each arm's parameters.

| row | predicate (mechanical) | where its bar comes from |
|---|---|---|
| **V-NAT / V-SET** | the DLL matches the pin; each arm logs exactly its parameter set, including `cqApEnabled` | mechanical, as every replay since 2026-11-08 |
| **V-OFF** | D2 holds on the build under test: the OFF arm's outcome fields equal a `98332f2a` replay on the first 50 window cycles, **counting only cycles in which neither run abandoned any stage** (abandons depend on wall-clock time; excluded cycles are counted, and V-OFF also fails if more than 5 of the 50 are excluded) | the OFF arm must be today's decoder, or ON − OFF is not CQ-AP's effect. Abandon exclusion: on file, 0 abandons in both KMIN-OSD-RECAL arms and live (`959d15c6`), so it should rarely bite |
| **V-FEED / V-SELF** | as CQ-AP-PSK (no gap > 120 s; own spots ÷ `{Reported}` ≥ 0.90 over windows when the daemon was up) | the CQ-AP-PSK spec, where both passed (V-SELF 1.028) |
| **G-GAIN** | `CI_lo(K_C)` > 0, where K_C = corroborated AP-only extras per 100 cycles (cycle bootstrap, B = 2000) | any real gain at all; the instrument's lower bound |
| **NO-GAIN** | `CI_hi(K_C ÷ D_OFF)` < **0.15 %**, where D_OFF = the OFF arm's decodes | 0.15 % ≈ the smallest gain the programme has kept: KMIN-OSD-RECAL NET +0.146 pp (2026-11-09). That figure is pp of WSJT-X decodes, not % of ours; the denominators differ, so the bar is a scale marker, not a like-for-like |
| **U-UB** | `CI_hi(K_N)` ≤ **0.021** per cycle, where K_N = uncorroborated AP-only extras per cycle | U_bar_G 0.021 per cycle (ratified COH-GATE-G 2026-10-28; reused for LATE-SUB, L1′, COH-RES-CAND, KMIN-OSD-RECAL). **K_N is an upper bound on false decodes**, so passing is strong and failing is not proof of harm |
| **T-TIME** | ON's latest-batch p95 − OFF's ≤ **1.0 s**, and ON's deadline abandons per 100 cycles ≤ OFF's + 1 | design choice. Live headroom today: latest batch max 5.1 s of 13 s (QA §3 report `959d15c6`). The +1 per 100 is DO-3's form |

**Verdict (exclusive, evaluated in this order):**
1. **VOID**: V-NAT, V-SET, V-OFF or V-FEED fails.
2. **NO-GAIN**: NO-GAIN fires. CQ-AP closes for this configuration.
3. **SHIP-CANDIDATE**: G-GAIN, U-UB and T-TIME pass, and V-SELF passes. The Captain decides whether to set `cqApEnabled` on his station (one explicit POST, HK-035) or make it the code default.
4. **FP-UNRESOLVED**: G-GAIN passes and U-UB fails. The upper bound on false decodes is above the bar, but that is not proof of harm. **The station stays OFF.** The Captain gets both bounds and decides whether a further measurement is worth it.
5. **BETWEEN**: anything else (including a T-TIME or V-SELF fail with G-GAIN passing).

**Descriptive (no gate):** K_C and K_N per our-SNR bin; the share of AP-only extras corroborated by WSJT-X versus by the feed; total AP-only extras per 100 cycles; `cq-ap` attempts per cycle; NET and ΔU′_ta of ON versus OFF against WSJT-X **if** QA's harness can freeze classes for this session (otherwise not computed). Expect AP extras to land in the unconfirmed column there: WSJT-X cannot see them.

## §5. Not measured, not in scope, and one observation

- **OSD on AP attempts** (D4), **AP types beyond CQ** (`CQ DX`, `CQ nnn` modifiers, MyCall-AP outside a QSO), and the coherent fallback: later arms, on the Captain's word.
- **A real false-decode rate.** Only an upper bound (K_N). The ghost model behind "corroborated ⇒ real" is a model (CQ-AP-PSK §5).
- **Live behaviour with the flag ON** (QSO engine, UI, external reporting). Only after a SHIP-CANDIDATE and the Captain's word.
- 🔎 **Observation O1 (from code, not measured; not in scope):** with QSO-context AP active, pass 0 runs **only** the AP-constrained attempt (`ft8_shim.c:1875–1879`: `if (pass == 0 && ap_active) decoded = ftx_decode_candidate_ap(...) else decoded = ftx_decode_candidate(...)`), and the subtraction passes set the same bits (`SubtractionPass.cs:439`). While a QSO is in progress, a candidate that is not a message between the two calls therefore cannot decode in pass 0 and has only pass 1 and later. I have not checked whether this is known or measured. It touches only cycles during a QSO. I raise it for the Captain as a possible separate small question, not as a defect.

## §6. Order and cost

1. QA's (k) review of this spec, rows only (in particular D1's test, D3's placement in the pass loop, and whether Replay81 can carry D8).
2. QA writes the Developer task; the Developer builds (a separate session, HK-011); QA reviews D1–D10 (HK-039).
3. **The live session (§2)** can happen **before or after** the build: it does not need it. It is the Captain's: radio on, WSJT-X alongside with PSK spotting off, about 3 h.
4. Freeze, OFF arm, ON arm: ~~about 600–800~~ **about 480–500 (a 3 h capture leaves a ~2 h window = ~480 cycles; the actual window is 500; E158, A3.2)** window cycles each at about 7 s per cycle, so about 1.5 h per arm, PC exclusive.
5. QA's report; my ruling; the programme page's top updated in the same edit.

**Cost:** one native + C# change of moderate size, one review, one 3 h live session that also serves candidate #3, about 3 h of PC replay.

## §7. Predictions (Architect; scored at the ruling)

| # | prediction | P | class |
|---|---|---:|:---:|
| CB-1 | D1–D10 pass on the Developer's first submission | 0.55 | C |
| CB-2 | K_C ÷ D_OFF ≥ 0.5 % (point) | 0.35 | H |
| CB-3 | U-UB passes | 0.35 | H |
| CB-4 | verdict SHIP-CANDIDATE | 0.25 | H |
| CB-5 | T-TIME passes | 0.80 | C |

**Reasoning:**
- BP-only CQ-AP is the conservative half of what WSJT-X does, and subtraction, the third pass and the coherent fallback already reach many weak CQs. So the corroborated gain is plausibly well under 1 %.
- The upper bound K_N counts every real one-off CQ the feed missed as well as every false decode, and the bar allows about one per 48 cycles. It is more likely to fail than pass.
- Timing has large headroom: one BP attempt per failed candidate, no OSD.
- 🔴 **Bias check:** HYPOTHESISED calls lean toward "a findable gain"; SHIP-CANDIDATE is held at 0.25.

## §8. Amendment 1 (2026-11-10 15:50:38Z, `date -u`): QA (k) review adopted in full; before the Developer task and any build

QA confirmed the D1 positions (`[0,29)` call 1, `[29,58)` call 2, `[58,74)` ir + grid, `[74,77)` `i3`; ft8_lib `message.c`), the BP sign convention (positive = bit 1, `ldpc.c:68`) and observation O1. It required two changes and made five notes, all adopted.

- **A1.1 NO-GAIN on all extras (QA required change 1; E156).** A lower bound cannot show that there is no gain: real one-off CQs that the feed never heard would make NO-GAIN fire although AP helps. **NO-GAIN now reads `CI_hi((K_C + K_N) ÷ D_OFF)` < 0.15 %**: even with every AP-only extra counted as real, the gain is below the bar. G-GAIN stays on K_C (a lower bound is the right side there).
- **A1.2 Inject after normalisation (QA required change 2a; E157).** The QSO-AP mechanism overrides at ±40 **before** `ftx_normalize_logl` (`decode.c:1100–1106`). The normaliser's variance (`decode.c:406–417`) then includes the forced values, so 32 entries at ±40 inflate it and scale the other 142 LLRs down before BP, which is not scale-invariant. **D1 now injects the CQ bits AFTER normalisation, at magnitude 1.01 × the largest |LLR| of the normalised non-forced entries.** That is WSJT-X's form as QA recalls it (`ft8b`, `apmag`), **not verified here**. The D10 sweep (A1.3), not the recollection, is the authority on whether it works. **The QSO-AP path stays exactly as it is** (D2); its own pre-normalisation scaling is recorded as observation **O2** (§5 style: from code, not measured, not in scope).
- **A1.3 D10(a) becomes a positive control (QA required change 2b).** Synthetic `CQ Q…` messages (Q-prefix calls only), SNR in **1 dB steps from 4 dB below to 1 dB above OFF's 50 %-decode SNR**, **≥ 200 cycles per step**, both builds. **Bar:** at one or more steps, ON's decode rate exceeds OFF's by **≥ 10 percentage points** with ON's Wilson-95 lower bound above OFF's Wilson-95 upper bound. **Source:** a design choice, with no data on file. A mechanism that cannot add 10 pp anywhere within 3 dB of threshold on clean synthetic audio would not move live numbers, and closing CQ-AP on such a build would be closing it for an implementation reason. **If D10(a) fails, the build goes back to the Developer; no replay arm runs.** (The synthetic generator must avoid the known `modulator.py` DT clamp defect; QA knows it.)
- **A1.4 D1b sign test (QA note).** On a clean encoded `CQ Q1ABC JO22`, the right-sign override decodes and the opposite-sign override does not.
- **A1.5 D3 placement and D4 (QA note).** The CQ-AP attempt is part of the `decoded` determination **before** the `if (!decoded) { …; continue; }` branch. A CQ-AP decode then goes through cross-pass dedup, `ftx_message_decode` and the hash handling, sets `tls_cf_cands[].decoded` and stores its payload, so the coherent fallback does not retry that candidate. `ftx_decode_candidate_ap` falls back to OSD internally (`decode.c:1118`), so **D4 needs a BP-only variant or parameter, with a real OSD-call counter that a test reads as 0**, and the QSO-AP path unchanged.
- **A1.6 D8 adds:** the harness writes `apKind` per decode. QA dry-runs the harness on the Developer's build before the freeze.
- **A1.7 Two descriptive lines (QA note).** An AP decode is subtracted, so ON changes the residual. Report **ON-only decodes with `apKind = none`** (gains via the residual) and **OFF-only decodes** (losses), per 100 cycles. K_C and K_N are unchanged by this.
- **A1.8 Scope.** `i3 = 1` only: CQs from `/P` callers (`i3 = 2`) are out of reach in this build.
- **Predictions:** CB-1 is **restated before any build** from 0.55 to **0.45** (the build now has a new injection point, a BP-only variant and a sweep to pass). CB-2 to CB-5 are unchanged.

## §9. Amendment 2 (2026-11-10 18:12:14Z, `date -u`): the live daemon runs the CQ-AP build, CQ-AP OFF (Captain's direction)

At 18:09:33Z QA started the live session on `main` `98332f2a` from `_run-main`, as §2 said. At about 18:11Z the Captain stopped it because he wants the **latest build** on the station. The 2 minutes of data are discarded. §2's "our daemon on `main` as deployed" is replaced by the following.

- **A2.1 Build.** The live daemon runs **`7ca00264`** (`feat/cq-ap`, v0.70, shim 20260072).
  - It is `main` `98332f2a` plus one commit (`git log main..feat/cq-ap` = `7ca00264` alone), so "CQ-AP merged onto main" is the same tree. No merge is needed or authorised.
  - It is HK-039 APPROVED and passed the A1.3 sweep.
- **A2.2 Publish location.** Publish to a **new folder `D:\Projects\claude\_qa-scratch\run-cq-ap\`**. `_run-main` stays pinned to `main` and is not overwritten. Before the start:
  - assert that the published `libft8.dll` SHA-256 equals the freeze pin `bbde6eb6…6528`;
  - run the **full test suite** on a clean checkout of `7ca00264`. If it fails, report it and do not start.
- **A2.3 Flag.** `decoder.cqApEnabled` is **absent or false**, i.e. **OFF**, read back before the stamp.
  - §3 Risk and the CQ-AP-PSK ruling said the station runs CQ-AP only after the measured upper bound is acceptable to the Captain.
  - The arms replay the archived audio, so the live flag does not affect them.
  - Turning it ON live is the Captain's choice. If he makes it: stamp a new era "CQ-AP ON live", never pool it, and note that the station's own `ALL.TXT` then contains AP decodes (they are not uploaded, D7).
- **A2.4 Era.** With the flag OFF, D2 makes outcomes identical to `98332f2a`, which the arms check by replay (V-OFF). The live era stays **"RF4+L1′ ON"**, and the stamp records the build `7ca00264`/v0.70.
- **A2.5 Freeze.** Unchanged: build `7ca00264`, DLL `bbde6eb6…6528`, seed 20261111. The live daemon and the arms now run the same DLL.
- Not an Architect error: §2 named `main` explicitly. This records a change of direction.
- **A2.6 The Captain's decision (received after 18:12:14Z): CQ-AP is ON for this run** ("we will do off later. on for this run."). This replaces A2.3's OFF.
  - Set `decoder.cqApEnabled = true` and read it back before the stamp.
  - The live era is **"CQ-AP ON live"**, stamped with the build `7ca00264`/v0.70. Never pool it with "RF4+L1′ ON".
  - The station's own `ALL.TXT` and decode panel contain CQ-AP decodes for this run.
  - They are not uploaded (D7). The PSK accounting line shows them as `ap=N`, and V-SELF stays against `{Reported}`.
  - The arms are **unchanged**: OFF and ON are both replays of the archived audio, and the freeze is the same.
  - Any live figure from this run (the station's `ALL.TXT` against WSJT-X) is ON-era only. Cite it only as descriptive, never as the arm result.
  - At session end, return the flag to absent/false along with the config backup. An OFF live run is a later session.

## §10. Amendment 3 (2026-11-10 21:30:24Z, `date -u`): the freeze in two parts; cycle-count estimate corrected

- **A3.1 The freeze is accepted in two parts.** QA's Part 1 (`342d320b`, `qa/same-chain`) holds every §4 item except the analysis code. A Part 2 addendum completes it. A freeze exists to fix every choice before any arm output is seen, and that purpose survives a split in time. These conditions hold:
  - **Part 1 stays as committed.** Any change to it means redoing the whole freeze as one record.
  - **Part 2** gives the commit and hash of the analysis code (match, bootstrap, arm driver, V-OFF diff). It records the passing self-test and the Replay81 dry-run repeat on DLL `bbde6eb6…6528`. It states that no arm output exists yet.
  - **The freeze is complete only when Part 2 is committed.** No arm runs before then.
  - **The disclosure stands:** QA saw the live per-cycle `cq-ap:` counts (739 cycles) and the spot and cycle counts. These are live ON-era operational counts, not arm outputs. The registered rows are computed on replay outcomes and the feed match only, so these counts cannot steer them.
- **A3.2 Cycle count (E158).** §6 step 4 estimated 600–800 window cycles. §2's own 3 h capture with ±1800 s trims gives about 2 h, about 480 cycles; the actual window is 500. No row depends on this number. Arm time is about 1 h each.
