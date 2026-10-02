# RULING — #194 captured-audio scan, PC1 failures and the event log (Amendments A7–A9)

- **To:** Engineer — cc QA, Captain  **From:** Architect  **Date:** 2026-10-02 ~19:25Z (HK-017)
- **Branch:** `arch/194-rr-improvements`. Docs only: `git diff --stat -- src/ native/` empty.
- **On:** `eng/194-scan` `316b66b1`, `qa/rr-study/results/2026-09-23-5f17b43/captured-audio-scan/PC1-AND-EVENTLOG-2026-10-02.md`; freeze `3953ac35` (`thresholds.json` `a3b19753…`, `scan_core.py` `07e8d116…`, LF-normalised; `766eb7a4` superseded before any 09-29 audio was read: accepted).
- **The stop was correct.** PC1 FAIL ⇒ stop is what step 3 says. Nothing below turns a fail into a pass: each amendment either removes a metric's power to flag (and says so), or repeats a control under a draw rule fixed now. The 09-29 pair is still unread, so this is still design, not a re-reading of a closed gate.

## 1. Rulings

**A7 (question 1): a threshold above the representable range ⇒ `DESCRIPTIVE-ABOVE-RANGE`. ACCEPTED, mechanically.** A (side, group, metric) cell is `DESCRIPTIVE-ABOVE-RANGE` iff the 2× injection is not representable in a 16-bit file for **any** of its drawn copies. That applies to the 8 `NOT-INJECTABLE` cells and to `wsjtx:multi:tile_excess_db` and `wsjtx:noise:click_max`. It is not a stop. 🔴 **It is a hole, and the report's headline must say so in plain words:** *with these thresholds, the scan cannot detect a short added sound (a Windows notification, a beep) or a click in the groups listed.* That is one of the Captain's own most likely causes (#194 table), so the gap goes to him, not just into a table (§3).

**A8 (question 2, and `owsfz:single:hiccup`): draw rule.** For the **lag family** (`tau_ms`, `dtau_ms`, `drift_ppm`, and the `hiccup` injection), PC1 copies are drawn only from slots that are **not** `lag_ambiguous`. Those slots are already BLIND for these metrics under A3, so testing there measures nothing. Procedure, fixed now:
1. Name the missed copy in each of the three 9/10 cells.
2. If it is `lag_ambiguous`, replace it with the next slot of the same seeded sequence (20261002) that is unflagged and not ambiguous, and rerun **only those cells**.
3. If the missed copy is **not** `lag_ambiguous`, it is a **real miss: STOP** and report. Do not redraw.

**A9 (question 3): `resid_db` gets an injection.** Add seeded white Gaussian noise (seed 20261002 + copy index) over the support, with power chosen so that the slot's **expected** `resid_db` equals `median + m·(T − median)` for m ∈ {0.5, 1, 2} (the group's frozen values). This is a chain that adds noise, the most generic fault there is. PC1 applies as for any metric. If the 2× noise is not representable, A7 applies.

**Question 4: the order stays, and 09-29 may be read only when all four steps below are done.**
1. Apply A7 (a list change only; no threshold value changes) and **re-freeze**: new commit, new SHA-256 of `thresholds.json`. The superseded freeze stays in the history.
2. Rerun PC1 for the A8 cells and the new `resid_db` cells **only**.
3. All PASS ⇒ read the 09-29 pair (V1–V3). Any FAIL ⇒ stop and report.
4. The report to the Architect, before the scan is wired in (unchanged).

## 2. Event log (§7): accepted as reported

- The logs reach the run, so the absence of audio, PnP and device events in 10:33–12:24Z is real **for those logs**. Voicemeeter's and WSJT-X's own logs are not covered.
- **11:08:45Z: no event within ±30 s.** The log does not explain it, and that is not "nothing happened". The open question is still the Captain's recollection.
- 3 of the 12 shared lag steps fall within ±30 s of a routine Software Protection or Group Policy event, against 1.05 expected (P ≈ 0.075). **Descriptive only.** It is a hint worth one cheap look later (does a scheduled task's CPU burst slip the playback stream?), not a finding. No claim of cause.
- The local-time filter mistake was caught and redone. Good. That is HK-017 working.

## 3. For the Captain (plain words)

The scan works for level changes, dropouts, timing slips and clipping: 71 of its checks passed. **It cannot see a short added sound, such as a Windows notification or a click, in most scene types.** The busy synthetic scenes vary so much on their own that the "unusual" mark ended up above anything a WAV file can contain. Fixing that means redesigning those two measurements, comparing each tile against the same tile of the reference rather than against the slot's own median. That is a separate, small piece of work, **to be decided by you after the validation report**. The rest of the scan does not wait for it.

## 4. Predictions

| # | Prediction | P | Outcome |
|---|---|---:|---|
| CA4 | PC1 passes first time | 0.65 | 🔴 **MISS**: 5 FAIL, 8 not injectable. The cause is again a threshold I did not check against the instrument's range (HK-026), in the direction opposite to CA2. |
