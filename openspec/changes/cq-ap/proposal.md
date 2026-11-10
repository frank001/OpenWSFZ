**User-facing:** yes (a new decoder setting, default OFF, and a new native build; the station's decode behaviour is unchanged until the Captain sets the key; the PSK Reporter accounting lines gain an `ap=` count)

## Why

WSJT-X's a-priori (AP) type 1 assumes a message starts with `CQ`: it fixes those bits before the LDPC decode, so a weak CQ can decode that otherwise would not. This decoder uses a-priori bits only for QSO context (`ft8_set_ap_bits`: my call and his call). Programme candidate #2 asks whether a CQ a-priori attempt, tried **in addition** on candidates that failed, finds real weak CQs.

Authority: the Captain, 2026-11-10 ("spec it", on the CQ-AP-PSK ruling's proposal). Spec: Architect `qa/rr-study/2026-11-10-1546-architect-to-qa-spec-cq-ap-build.md` (`arch/cq-ap`, `416b6ab9`) with Amendment 1 (QA's (k) review adopted in full); Developer task `dev-tasks/2026-11-10-cq-ap-build.md` (QA, `qa/same-chain` `64ca5a2c`).

**Scope of the build:** to be correct, off by default and measurable. The station never runs it live in this test. QA measures it by an OFF/ON replay of one live session against PSK Reporter and WSJT-X (the Architect's spec, section 3 to 4); that is not part of this change.

## What Changes

- **Setting.** `decoder.cqApEnabled`, boolean, default `false` (an absent key and a missing `decoder` section read `false`); config file and API only, the POST is an overlay; read once per window.
- **The attempt.** With the setting on, a candidate whose normal attempt failed (the QSO-context a-priori attempt included) gets one more attempt: payload bits 0 to 28 (`n29a` = c28(`CQ`) `<< 1` | `ipa` 0) and 74 to 76 (`i3` = 1) are forced, **belief propagation only** (the OSD is never run on it), in every pass of `ft8_decode_all` and on every buffer it runs on. The forced LLRs are written **after** `ftx_normalize_logl`, at 1.01 times the largest |LLR| of the normalised non-forced entries (not the QSO-AP form, which forces +-40 before normalisation). It never replaces a normal attempt.
- **The tag.** Every decode carries an `apKind` (`none` or `cq`), from the native result to the managed `DecodeResult`; the replay harness can write it. Not serialised in any output format.
- **The log.** One Information line per cycle, only while the setting is on: `cq-ap: attempts=N decodes=M`.
- **PSK Reporter.** A decode with `apKind = cq` is never uploaded; it is counted under a new exclusion reason `ap=` on both accounting lines and in the status counters.
- **Native.** `FT8_SHIM_VERSION` 20260071 to 20260072: a thread-local flag `ft8_set_cq_ap`, an index-aligned getter `ft8_get_last_ap_kinds`, counters `ft8_get_last_cq_ap_stats` (attempts, decodes, OSD entries), and two test exports (`ft8_cq_ap_pattern`, `ft8_cq_ap_probe_llrs`). `FT8Result` stays 48 bytes; every existing export is unchanged. The QSO-AP path is untouched.
- `VERSION` 0.69 to 0.70; `REQUIREMENTS.md` FR-103 and a changelog row.

## Out of scope

OSD on the a-priori attempt; a-priori types beyond plain `CQ` (`CQ DX`, `CQ nnn`, MyCall-AP outside a QSO); CQs from `/P` callers (`i3` = 2); the coherent fallback; any change to QSO-AP (its pre-normalisation scaling is the Architect's observation O2); the QSO engine, the UI, reporting for `cq` decodes beyond the PSK exclusion; default ON; a Settings-page control; the replay arms and every measurement (QA's).

## Era

Turning the setting ON starts a new era: never pool its decodes with figures from the setting OFF. With the setting OFF the decoder is the build before this change (decode outcomes identical on a fixed set of cycles).
