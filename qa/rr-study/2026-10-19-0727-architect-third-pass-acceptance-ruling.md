# Third pass (#240): acceptance ruling after the sol R&R (TPNORMAL + TPDEEP) and the partial station run

- **From:** Architect · **To:** QA (copy: the Captain) · **Written:** 2026-10-19 07:27Z (`date -u`)
- **Spec:** `2026-10-18-1205-architect-to-qa-spec-third-pass-yield.md` + Amendment 1 (`arch/third-pass` `4c7568bc`).
  Interim ruling + Addendum 1: `2026-10-18-1408-architect-third-pass-y40-tref-ruling.md` (`e179a643`).
- **Data:** QA's message and board entry of 2026-10-19 ~07:40Z (QA's stamp). The sweep folders
  `2026-10-18-b0e23bb-TPNORMAL-sweep1` / `…-TPDEEP-sweep1` in the root results folder. **The Architect read
  `f2_record.json` and `f2_per_play.csv` of both sweeps directly** (§3 rests on them). All other figures are as QA
  reported them, not recomputed.
- **Build:** `feat/third-pass-deep` `a329cea9`, sol `libft8.so` `f7888f6d…`, rig config pin `661de047…`.
- `git diff --stat -- src/ native/` for this document: empty.

## 1. Verdict

| item | ruling |
|---|---|
| TPNORMAL (Normal, sol, full battery) | **VALID.** Exit 0, 0 failed attempts, config pin OK, depth read-back VALID (9,975 polls), S6 V1–V5/V7 + onset PASS, 0 residual abandons, FP 0/480 |
| TPDEEP (Deep, sol, full battery) | **VALID.** Same rows, depth read-back VALID (9,985 polls). 0 of 111 third passes abandoned or failed |
| TPNORMAL continues the B2CAP era | **CONFIRMED.** OWS own 88.0 % [84.9, 91.0], inside the band 87.3–88.3 %. The build difference is cleared as a cause |
| TPDEEP | **First row of a new era (Deep, sol).** Never pooled with the B2CAP era |
| Station endurance (Deep, 40 m), cut off after 4 h 14 m | **Read as a partial (the Captain's ruling): for capture and timing counters only.** Not a decode or yield figure: HK-036 Section 4 was never produced, so nothing from it is cited as yield |
| **#240 step 1 (Deep as an opt-in setting, default Normal)** | ✅ **ACCEPTED as measured.** Every validity row passed on every corpus. The cost and the risk on the slowest machine are known (§2–§3). **No ship bar was set (HK-038), so "accepted" means the measurement is complete and the build does what the spec says. Whether to ship and merge is the Captain's call (§5)** |

## 2. What the whole arm shows (the figures to cite)

| question (spec §4) | answer | where from |
|---|---|---|
| Extra confirmed decodes | **+0.514 pp of WSJT-X decodes [0.384, 0.658]** on one 40 m night (Y-40, offline). A second band agrees: +0.482 pp [0.293, 0.679] (Y-2, 17 m, descriptive, reference settings unknown). 82 of 84 batch-3 decodes were matched to WSJT-X | interim ruling §3, Addendum 1 |
| Time per cycle | Third pass median **0.79 s on the PC** (Y-40), **0.88 s on the station PC** (live partial, 1,012 runs), **1.5–1.6 s on sol** (T-REF 1.61 s; TPDEEP 1.51 s, p90 2.02, max 3.29) | interim ruling, QA |
| Budget misses on the slowest machine | **0 abandoned of 111 started** (TPDEEP), 0 of 41 (T-REF), 0 of 1,012 (station). On TPDEEP alone, 0 of 111 bounds the abandon share below about 2.7 % (one-sided 95 %) | QA |
| Live capture with Deep ON (F2) | sol: one clamp episode, **not material** to the figure (§3). Station: **0 clamped windows**, 0 drops, overruns or restarts in 15,265 polls | §3, QA |

**Citation guards (unchanged and added):**
- 🛑 Cite NET_3 only with its corpus and CI. Never add it to SUB-FEAS's +8.89 pp or the offline +11.73 pp.
- 🛑 **TPDEEP's 90.7 % vs TPNORMAL's 88.0 % is a consistency figure (S6 own-universe), NOT a yield gain.** It is
  descriptive (CIs overlap, one sweep each). Never cite the +2.7 pp as "Deep decodes 2.7 % more". Part of the gap may be
  F2 noise in TPNORMAL (§3: up to 0.8 pp). Why Deep would raise run-to-run consistency was not examined, and does not
  bear on this ruling.
- 🛑 sol timings are sol's; station timings are the station PC's.

**Ledger:** TP-1..3 were scored at the interim ruling (all HIT). No prediction was registered for the sol sweeps, so
nothing is scored here. TPDEEP's 0/111 is consistent with TP-3, but it is not TP-3's population (T-REF), so TP-3 is not re-scored.

## 3. The Amendment-1 clamp check: the open F2 item, now ruled

Read from the per-play files by the Architect.

**TPNORMAL: FLAG, one episode, upper bound +0.82 pp.**
- One clamped play: **play 59**, after a 5.4 s residual pass (play 58). Play 59's window also holds the sweep's one channel drop.
- Without that WAV: 88.02 → 88.83 %, against a 1-WAV placebo of [87.73, 88.49]. Flagged by 0.34 pp.
- This is **Normal**: there is no third pass, so it is the known F2 mechanism of the B2CAP era, not Deep.
- It joins the record: B2CAPR sweep 1 (+0.49 pp), sweep 2 (+1.61 pp), TPNORMAL (+0.82 pp), all upper bounds.
- **The era band stands as it is**, with its F2 caveat. The caveat now reads: "three of four sweeps carry an F2
  episode worth up to +0.5 / +1.6 / +0.8 pp".

**TPDEEP: not flagged, and the cause is the stall WAV with a longer stall.**
- Five clamped plays, 175–179 (6 windows), all **directly after play 174**.
- Play 174 is the known stall WAV (the B2CAPR §9 "play-35 slot", repeated at plays 119 and 174).
  Here it took a **7.04 s residual pass plus a 2.17 s third pass: about 9.2 s of decode work, the longest of the sweep.**
- Play 175's window carries 9 of the sweep's poll drops.
- Its figure effect: 90.71 → 90.84 % (+0.13 pp), inside the 5-WAV placebo [90.18, 91.38].
- The same WAV's other trial (play 119: 6.4 s + 2.2 s) did not clamp. That matches the B2CAPR finding that this stall
  leads to a clamp in some runs only.

**Reading:**
1. **On sol, Deep makes the known stall longer** by about 2 s on the WAV that already causes it. In this sweep that was
   followed by a clamp episode.
2. **One sweep cannot show whether Deep makes F2 episodes more frequent.** Clamped windows per sweep: B2CAP era 4 / 2 / 12 / 2; TPDEEP 6. That is inside the era's range.
3. **The figure effect was not material** (inside the placebo).
4. **On the station PC, Deep produced no clamps at all** in 4 h 14 m live (0 of 15,265 polls), with third passes of
   median 0.88 s, max 1.37 s.

F2 stays parked (the Captain's earlier choice). This ruling adds one fact to the reopen question: **Deep lengthens the
trigger stall by about 2 s on sol.** That matters if Deep is ever proposed as the default for slow machines. It does
not block Deep as an opt-in setting.

## 4. Housekeeping for QA (not choices, and none blocks this ruling)

1. **Station partial: 777 batch-3 decodes in the log vs 717 in the status counter.** Explain this before any live
   batch-3 count from the station is cited. B6 (counters in status) is a build requirement: if the counter undercounts,
   that is a build defect for a Developer. If the log double-counts (for example, a line per rendering), it is a parser
   matter. Aggregates only (HK-037).
2. TPDEEP S7: WSJT-X 1, OWS 0, unexplained. S7 movement is instrument-suspect by standing rule. Record it, don't chase it.
3. sol test folders (`…TPH*/TPT*/TPSMOKE*/TPDRY-1`) can go, once the Captain gives the go (the sweeps are pulled).

## 5. For the Captain: the decision this arm was built to inform

**The question:** do we ship `decoder.decodingDepth = Deep` as an **opt-in** setting (default stays Normal), and where
does `feat/third-pass-deep` merge?

**The data:**
- **Gain:** about +0.5 pp of WSJT-X's decodes, on two bands. About 0.1–0.13 extra confirmed decodes per cycle (22/232 on Y-2, 60/455 on Y-40).
- **False-decode exposure:** 2 OWS-only of 84 batch-3 decodes. That is an upper bound on false decodes, not proof.
- **Cost:** about 0.8–0.9 s more decode time per cycle on the PCs, and about 1.5 s on sol.
- **Budget:** 0 misses anywhere: 1,700 started third passes in all (Y-40 363, Y-2 173, T-REF 41, TPDEEP 111, station 1,012).
- **Risk:** on sol it lengthens the known F2 stall. It has not done so on the station.
- **Normal is bit-for-bit today's output** (V1, two corpora), so shipping it changes nothing for anyone who doesn't switch it on.

| option | what it leads to | matters or housekeeping |
|---|---|---|
| **A. Merge to `main` as opt-in, default Normal** | A PR from `feat/third-pass-deep` (main-based, CI was run; QA re-checks the CI result before the PR). Zero change for users who leave it on Normal. DI picks it up at its next `merge origin/main`, but that merge conflicts in `WebApp.cs`: `src/` work, a Developer session (HK-011) | **Matters:** it is the ship decision. Low risk, by V1 |
| B. Merge to `decoding_improvement` first | The station could run Deep in standard endurance runs (a new decode era on the station, never pooled). Needs the same `WebApp.cs` conflict resolved by a Developer first | Matters: it trades a station era change for live data |
| C. Don't merge yet | The branch stays as it is. Nothing changes. The +0.5 pp is not delivered | Matters: the cost is only the gain forgone |
| (any) Settings-page UI (#240, B10, out of step 1) | A follow-up spec, if you want users to be able to find the setting | Housekeeping, after A or B |

**Architect's view:** A. The gain is small but real and corroborated, and Normal is provably inert. The only risk seen
is on the slowest machine, and it is opt-in there. **What A does not settle:** whether Deep should ever be the
default. That would need a bar set from this data, and a decision on F2 for slow machines.

**Also waiting on you:** the push of QA's local commits (HK-033), and the sol cleanup go (§4.3).

## Addendum 1: §4.1 closed (2026-10-19, after QA's reply)

- **777 vs 717 is not a defect.** QA traced it, and the Architect checked the same lines in `a329cea9`.
- **The log line counts raw results.** `SubtractionPass.RunThirdPassAsync` logs `result.Length`, the raw native results.
- **The status counter counts delivered decodes.** `Ft8Decoder` adds `batch3.Count` only after `MapNative`, the same
  per-cycle text de-duplication that batch 2 goes through. The B5 requirement (batch 3 mapped exactly like batch 2) holds.
- **So 60 of 777 raw results (7.7 %) were text duplicates of decodes already in that cycle.** They were not delivered.
- **Rule:** cite the delivered (status) count for any live batch-3 figure, never the log sum.
- **Caveat:** this comes from the code path, not a per-cycle measurement, because no per-cycle counter exists.
- This changes nothing in §1–§5 (but see Addendum 2). The offline figures (NET_3, M2) come from Replay81's per-batch outcome files (A4), not from this log line.

## Addendum 2: the Captain's decision, Deep is the DEFAULT (2026-10-19 08:42Z, `date -u`)

**Decision (the Captain's, via QA; checked by the Architect on `origin/main`):**
- #240 step 1 merged to `main` as PR #248, `0c7124db`, 08:23:41Z.
- Commit `21d8fac4` makes **`decoder.decodingDepth` default to `Deep`.**
  - In `DecoderConfig.cs`, an absent key reads as Deep, and an explicit `"Normal"` stays Normal.
  - This goes beyond option A in §5, which assumed Normal as the default.

**The Architect's concern, stated once:**
- §5 said a Deep default needed a bar set from this data, plus an F2 decision for slow machines.
- The one risk seen was on sol: Deep lengthened the known trigger stall by about 2 s (§3). That rests on one sweep.
- With Deep as the default, that risk reaches every slow-machine install that has no explicit key.
- The station PC showed no clamps. The measured gain is about +0.5 pp, and 0 of 1,700 third passes ran out of the budget.
- The decision is the Captain's, and it stands. F2 stays parked.

**What it changes in this ruling:**
1. §5's "Normal is bit-for-bit today's output, so nothing changes for anyone who doesn't switch it on" **no longer
   describes the shipped default.** V1 still holds for an explicit `"Normal"`.
2. 🔴 **Eras.** A build from `main` at or after `0c7124db`, with no `decodingDepth` key, is a **Deep-era** instrument
   (a new timing and decode era).
   - **The B2CAP era (OWS 87.3–88.3 %) continues only with an explicit `"Normal"`** in the config, read back as Normal from
     `/api/v1/status`.
   - Never pool a key-absent post-`0c7124db` run with a pre-merge run or an explicit-Normal run.
3. QA's follow-ups are accepted as listed:
   - pin an explicit depth in the sol rig config before the next sol run (and refresh the config pin);
   - set the depth explicitly in the endurance configs;
   - record the station's first Deep cycle as its era start when the Captain redeploys.
   - **Every run note from now on states the depth it ran with, as read back from status, not only as written in the config** (HK-020: the one critical config).
4. The citation guards in §2 are unchanged.
5. **Not established:** Deep's capture behaviour on any machine slower than the station PC, beyond sol's one sweep.
   - **Suggestion only, not a test bar:** if a user on slow hardware reports lost cycles, the first thing to try is
     `decodingDepth: "Normal"`.
