# `CQ-AP-PSK` ruling: USABLE (P_R) stands, but as a one-sided instrument. Feed corroboration proves an extra is real; a missing spot does not prove it false

**From:** Architect · **To:** QA, the Captain · **Date:** 2026-11-10 15:41:19Z (`date -u`) · **Branch:** `arch/cq-ap-psk-check`
**Spec:** `qa/rr-study/2026-11-10-1153-architect-to-qa-spec-cq-ap-psk-check.md` with Amendments 1–2 (`42084a11`, `8202d245`).
**Freeze:** `22b854c5` (code `39f40ea4`). **Report:** `qa/rr-study/2026-11-10-1541-qa-cq-ap-psk-report.md` (`3d49d107`, `qa/same-chain`, local). Analysis run once, 15:39:16Z.
**Data:** live, era "RF4+L1′ ON", 20 m; capture 11:56:28Z–15:30:48Z; window 12:26:28Z–15:00:48Z. WSJT-X was not running, so V-REF failed and **P_R gated** (A1.4).

---

## §1. The registered verdict: USABLE (P_R)

| row | value | bar | result |
|---|---|---|---|
| V-REF | no WSJT-X `ALL.TXT` | — | FAIL ⇒ P_R gates |
| V-FEED | 0 gaps > 120 s | — | pass |
| V-SELF | 1,294 / 1,259 = 1.028 | ≥ 0.90 | pass |
| N-INSUFF | weak bin n = 609 | < 30 fires | no |
| G-COVER | C_weak 607/609 = 0.997, Wilson-lo 0.988 | ≥ 0.40 | pass |
| G-SLOPE | +0.0018 | ≤ 0.20 | pass |
| G-GHOST (guard) | 0 / 10,000, Wilson-hi 0.00038 | ≤ 0.02 | pass |

The verdict follows the registered order (§3 of the spec, A1.4). **It stands.**

## §2. What it means: QA's limit is right, and there is a second property

**QA's limit (HK-026), adopted.**
- P_R holds only steady repeat callers, so C is flat at about 1.0 from −10 dB down to ≤ −19 dB.
- A flat response cannot bound its own blind spot.
- The weak-bin coverage of **one-off** CQs, and of stations that few others hear, is **unmeasured**.
- So "C ≈ 1" may **not** be carried over to the decodes CQ-AP would add.

**The property that does not depend on that limit.** The rule separates real callsigns from random ones by a factor of about 700:
- **Ghosts:** 0 of 10,000 publishable random callsigns are corroborated (Wilson-hi 0.00038).
- **Real callsigns:** P_R in the window is about 1.0. Even real callsigns placed **at the wrong time and frequency** are corroborated 27.7 % of the time (P_S).

A false AP decode is a random `c28` (the model behind the ghosts; §5 of the spec names this as a model). Its chance of being corroborated is therefore ≤ 0.0004. Hence:

> **Corroborated ⇒ real (to ≤ 0.04 % per decode). Not corroborated ⇒ unknown.**

**Consequence for any CQ-AP test.** Classify the AP-only extras by the feed:
- **the corroborated share is a lower bound on the real gain**, and this holds whatever the coverage of one-off weak CQs turns out to be;
- **the uncorroborated share is an upper bound on false decodes.**

Coverage only decides how far apart the two bounds sit. That is a usable instrument for a build decision. It is **not** a point estimate of AP's false-decode rate, and nobody may cite it as one.

**Further limits (stated, not gating):**
- **The time-and-frequency rule is loose:** P_S at 0.277 shows that a corroboration means "this callsign was real and on the band near this time", not "this transmission was heard". That suffices against random false decodes. It does not catch a false decode that happens to equal a real active callsign; that case is rare by the ghost model, but not measured.
- **V-SELF = 1.028 is not explained.** Possible causes are send windows at the capture edges, or duplicates in the feed. It does not indicate loss, and it passes.
- One session, 20 m, daytime.

## §3. What follows (a proposal for the Captain, not a decision)

**A CQ-AP build is now measurable.**
- **What it is:** a Developer session (HK-011) adds a CQ a-priori pass (WSJT-X AP type 1, the CQ bits fixed) using the existing `ap_overrides` mechanism (`native/ft8_lib_build/patched/ft8/decode.c:121`), behind a flag that is **default OFF**, with every AP-only decode tagged.
- **How it is measured:** one live session with **WSJT-X running alongside** (its PSK spotting OFF) plus the MQTT capture.
  - That gives the lower-bound gain (corroborated AP-only extras), the upper-bound false share (uncorroborated), and the usual NET and U′ against WSJT-X.
  - The same session gives candidate #3 its live reference, so one session serves both.
- **Cost:** a native and C# change with QA review (HK-039) and the pre-merge gates. Then about a 3 h live session.
- **Risk:** AP is WSJT-X's main source of false decodes. The flag stays OFF on the station until the measured upper bound is acceptable to the Captain.
- **The Captain decides** whether to build it. If he says no, CQ-AP stays demoted, and the reason on file is that the instrument now exists but the build was not wanted.

## §4. Predictions scored (spec §6; scored on P_R, as A1 recorded)

| # | prediction | P | outcome |
|---|---|---:|---|
| CA-1 | V-SELF passes | 0.65 | ✅ HIT (1.028) |
| CA-2 | C(≥ −10) ≥ 0.80 | 0.65 | ✅ HIT (1.000) |
| CA-3 | USABLE | 0.45 | ✅ HIT (on P_R; would P_T agree? unmeasured) |
| CA-4 | G-SLOPE fails | 0.35 | ❌ did not fail (+0.0018) |
| CA-5 | INSUFFICIENT | 0.15 | ❌ did not fire (n = 609) |

**Brier 0.139 over 5.** CA-3 was held below even odds, and P_R's construction made it easier than P_T would have been. It is a hit on a softer population than the one I priced.

## §5. Housekeeping

- **HK-037:** the job is closed by this ruling, so QA deletes the raw spot file and any per-callsign working files in `_qa-scratch\cq-ap-psk\`. Keep only `result.json` (aggregates) and the hashes already in the freeze.
- Architect errors on this spec: E152, E153, E154 (ledger, 2026-11-10).
- `git diff --stat -- src/ native/`: empty. Docs only.
