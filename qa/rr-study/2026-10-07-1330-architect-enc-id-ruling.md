# RULING — `ENC-ID` (Amendment 9): **NO READING** (Y4 failed). The mechanism is verified from source; the statistic is withheld

- **To:** QA (cc Captain)  **From:** Architect  **Date:** 2026-10-07 13:30Z (`date -u`, HK-017)
- **Branch:** `arch/coherent-limb2`. Docs only: `git diff --stat -- src/ native/` empty.
- **Reviewed:** QA report `report_encid.md` @ `37141a6f` (`qa/coh-gain`, local, not pushed); row lists `6f2aa866` (committed before re-extraction).
- **Against:** spec §18 + note 1 (`2c43bd8d`).

## 1. Verdict: NO READING, accepted

Y1 PASS (814 / 814; reach pass 76,886 / 76,886), Y2 PASS (0 / 19), Y3 PASS in amended form (QA's amendment accepted; see §2). **Y4 FAIL: 167 / 795 = 21.0 % against ≤ 2 %.** Per the rule, the reading is withheld. QA was right not to retune the 2 %. Raw P = 788 / 795 = 99.1 % is **not citable as a reading.**

**Cause of Y4's failure: my control design (HK-038 fired again).** 793 of the 795 rows are CQs (`icq` = 1), so `hash_eq` is vacuous and the match rests on the single call. A station that calls CQ for more than 30 minutes recurs across the derangement. I set the tolerance without looking at the population's message mix, which was on file (`field_rows.csv`). A within-cycle derangement would have been immune, because a station transmits once per cycle. Ledger: recorded.

## 2. What is established without the statistic

- **Mechanism, verified from source by the Architect (HK-018):** `native/ft8_lib_vendor/ft8/message.c`. `ftx_message_encode` tries `ftx_message_encode_std` first (`:143-145`). Its call packer packs any non-standard call of 3–11 characters as a **22-bit hash inside a standard message** (`:713-726`, `return NTOKENS + n22`), so the std path succeeds and `ftx_message_encode_nonstd` (`:146-147`) is **never reached** for such calls. WSJT-X transmits these messages as type 4 (`i3` = 4). ⇒ **Our re-encoded truth can never equal the on-air payload of a type-4 transmission.** This is a code fact, not a statistic.
- **Descriptive, not citable as a reading:** 99.1 % same-row call match against 21 % shuffled; type-4 outputs are never scored RIGHT, and they make up 815 / 1,567 of the fallback's wrongs and 283 / 645 of G's.
- **Consequences (forward only; no closed ruling is re-read):**
  1. Any offline arm that scores against the vendored encoder's re-packing of WSJT-X text mis-scores type-4 transmissions as wrong. Future arms of that kind must compare type-4 rows by call and hash (§18's method), or exclude them by `i3`.
  2. **Test B and the product replay match by TEXT and are not affected.** The step-3 replay (next spec) is therefore immune.
  3. **Product TX defect (backlog, not this programme):** OpenWSFZ transmits with the same encoder. A user with a non-standard or compound call sends `CQ <hash>` where WSJT-X would send the full call, so other stations see `CQ <...>`. It does not affect the PD2FZ station (a standard call). To the backlog for the Captain.

## 3. Predictions

CE-1 (Y3) ✅ HIT (amended form); CE-2 ENC-CONFIRMED 0.55: ⏸️ **NOT SCORABLE** (no reading); CE-3 (Y2) ✅ HIT.
