# QA → Architect: P-LIVE Stage 1R results — ROW A, ANCHOR CONFIRMED BROKEN, corrected offset +0.65s

**Author:** QA
**Date:** 2026-08-18 18:24:57Z (mechanically derived via `date -u`, HK-017)
**Runs:** `qa/rr-study/2026-08-18-1616-architect-to-qa-p-live-stage1-ruling-anchor-provenance-defect.md`
Sec.5 (Stage 1R corrective spec)
**Harness (new):** `qa/rr-study/p-live-population/run_stage1r.py`, plus
`plive_population.build_p_hit_population()` (new function, same module)
**Status:** 🔴 **ROW A FIRES. Stage 1 is confirmed VOID, not null. QA STOPS here per
the ruling's own instruction — no re-run of Stage 1, no Stage 2.**

---

## 0. Headline

**ROW A fires cleanly, not on a boundary.** The P-HIT positive control (600
rows / 551 clusters sampled from PRIMARY's 25,411-row / 4,371-cluster P-HIT
population — cycles both decoders decoded) reads **median BER_V0 = 49.43%**
at WSJT-X's raw reported DT — chance level, identical to Stage 1's own
headline number on the *miss* population. **On rows we ourselves demonstrably
decoded, V0 extraction at the raw anchor is indistinguishable from noise.**
The ruling's prediction (P(ROW A)≈80%) is confirmed.

The 49-point `dt_offset` sweep (M3's own grid, reused verbatim) finds a sharp,
clean trough: **swept optimum at `dt_offset = +0.65s`, median BER_V0 = 5.75%**
— close to W1's matched-hit-control floor of 2.9%. This is a **second,
independent measurement of the anchor-convention offset**, through a
different code path (`ft8_extract_llrs_at` directly) than M3's +0.45s
(through the sync refiner).

---

## 1. Gate trace, strict order

| Row | Condition | Measured | Result |
|---|---|---|---|
| 0a' | DLL SHA256 re-hashed, asserted before arming | `6890d84c...`, shim 20260042 | **clear**, matches pin |
| 0b' | P-HIT control n≥500 rows / ≥200 clusters | n_measured=556/600, n_clusters_measured=515/551 (drop: 44 `no_true_codeword`) | **clear** |
| 0f' | median BER_V0(raw) outside [0%,35%], two-sided | 49.43% | **FIRES** (high side; low side structurally unreachable, BER∈[0,1]) |
| **A** | median BER_V0(raw) ≥ 35% | **49.43%** | **FIRES** |

**HK-025:** independently re-derived before arming (`run_stage1r.py:hk025_check()`),
concurs with the ruling's own Sec.5.2 classification on all three rows —
each routes to a genuinely different action (DLL-mismatch→refuse-to-arm vs
proceed; underpowered→escalate vs proceed; anchor-broken→VOID+STOP vs
proceed to B/C). No refusal.

DLL re-hashed from disk immediately before arming, not inferred from a label —
matches the pin exactly (`6890d84c4bcf2e90bc9ad3cc0e0e00c74a461f8b265665d59b2d4cbb1decd672`),
same DLL Stage 1 used.

---

## 2. Sample construction

`build_p_hit_population()` (new, `plive_population.py`) inverts Stage 1's own
membership test: a row is a WSJT-X decode whose normalised message **does**
appear in our own `ALL.TXT` for the same `ts` (same `normalize_hash_tokens`
key). Anchor is still WSJT-X's own reported (freq, dt), unchanged by the
inversion — same convention Stage 1 used, per the ruling's Sec.5.1(a).

PRIMARY (`20260803_live_run_1713`) full P-HIT population: **25,411 rows /
4,371 clusters**. Sampled 600 rows by seeded (`20260818`, Stage 1R's own,
distinct from M1/M2/M3's) sort-stabilised RNG — the population list is sorted
at construction (`(ts, freq, dt, message)`) before shuffling, so the sample is
reproducible independent of any hash-set iteration order (standing rule,
`MEMORY.md`). **600/600 sampled → 551 distinct clusters**, comfortably clearing
both Sec.5.2 bars before a single extraction ran (sample size chosen from a
dry count run in advance, not fitted to the outcome — see the harness's own
`DEFAULT_SAMPLE_ROWS` comment).

44 rows dropped at `no_true_codeword` (encoder round-trip failure on WSJT-X's
own message text — same drop class Stage 1 saw, ~1.4–5.7% there; here 7.3%,
consistent). Zero `no_wav` drops. **n_measured = 556, n_clusters_measured =
515** — both bars cleared with wide margin (556≥500, 515≥200).

---

## 3. The sweep

49 points, `m3_common.TIME_ANCHOR_OFFSETS_S` (−1.20…+1.20s, 0.05s step),
**reused verbatim, not redesigned**, per the ruling's explicit instruction.
V0 arm only (`ft8_extract_llrs_at`) — no V3 extraction, since the gate turns
on median BER_V0 alone. 49 × 556 = 27,244 extractions, 147.2s total.

Full table in `p_live_stage1r_report.json["dt_offset_sweep"]`. Shape:

- **−1.20s … +0.55s:** flat, chance-level (45–50%) throughout — no
  informative signal on this side of the grid at all.
- **+0.60s:** 13.22% — the trough begins.
- **+0.65s:** **5.75% — the minimum.**
- **+0.70s:** 6.90%.
- **+0.75s:** 39.94% — sharply back up.
- **+0.80s … +1.20s:** back to chance-level.

**A single sharp trough spanning three points (+0.60/+0.65/+0.70), width
≈0.15s — not a plateau, not multiple candidate offsets.** n_ok = 556/556 at
every single one of the 49 offsets (no edge-of-buffer extraction failures
anywhere on this grid for this population) — the trough shape is real signal,
not a sampling artefact from a shrinking denominator near the grid edges.

**Cross-check against M3, unplanned but worth recording:** M3 measured
+0.45s through the sync refiner (`ft8_extract_llrs_at`'s companion coarse
search); Stage 1R measures **+0.65s directly at `ft8_extract_llrs_at`'s own
entry point**, no refiner involved. The two are **not the same quantity** —
M4 (2026-08-15) already flagged that M3's correction "may still be slightly
short" (a coherent residual bias in `coarse_dt_samp` on both HIT and MISS,
absent in NULL) — and a 0.20s difference between a refiner-mediated estimate
and a raw-entry-point estimate is consistent with that flagged residual, not
a contradiction of it. **Both numbers point to the same underlying
phenomenon (a real, positive, multi-symbol anchor-convention offset) through
two different code paths.** Per the ruling's own Sec.7, this is *not yet* a
finding in its own right and P-LIVE must not be retro-fitted into one — flagged
here as the ruling anticipated, not adjudicated.

---

## 4. What this does and does not license

✅ **Confirms the withdrawal was correct**, independently of M3, through the
exact code path Stage 1 actually used. The ruling's diagnosis (Sec.1, row 5)
is now doubly verified.

🛑 **Does NOT license re-reading Stage 1's numbers with a +0.65s correction
applied.** Per the ruling's own gate: ROW A's consequence is "report the swept
offset from (b) and STOP — do not re-run Stage 1 in the same session." QA is
following that instruction to the letter. A corrected-anchor Stage 1 (or
Stage 2) run is a **new pre-registration**, not an automatic next step from
this result.

🛑 **Does NOT re-open N5's HELD status or D-001's limb 2.** Nothing here
touches N5's own `THE 135`/`THE 567` result (anchored from our own candidate
positions, convention-clean) — N5 stays HELD on its 4.37% bound, exactly as
it has been since 17:44Z on 2026-08-17.

⚠️ **One genuine finding, flagged not adjudicated (per ruling Sec.7):** a
second, independent, different-code-path confirmation that WSJT-X's reported
DT and our buffer-relative convention disagree by roughly half a second —
now measured twice, at +0.45s (refiner) and +0.65s (direct entry point). That
is not a P-LIVE finding; it is a finding about the anchor-conversion boundary
itself, and would need its own pre-registration if pursued.

---

## 5. Housekeeping executed this round (ruling Sec.5.3.1)

The Stage 1 withdrawal's own housekeeping instruction had not yet been
executed (only the ruling document's §5.3.1 text had been drafted/revised
across three prior commits) — done now, same round as Stage 1R:

- `p_live_stage1_rows.json` (29.6MB) moved to
  `artefacts/2026-08-18-p-live-stage1-withdrawn/`, with a `README.md`
  explaining what it is, why it's withdrawn, and how to regenerate it.
  Deletion at the old path **staged** (`git add -u`), not merely moved on
  disk.
- `.gitignore` gained `qa/rr-study/p-live-population/results/*_rows.json`
  (future-round pattern, per the ruling's own judgement call) — verified
  with `git check-ignore -v` against both the new artefacts location and a
  simulated future path.
- `WITHDRAWN.md` added to `qa/rr-study/p-live-population/results/`, naming
  the ruling, the one-line reason, and the new location of the moved file —
  and noting that `p_live_stage1r_*` and `row0a_*` in that same directory are
  **live, not withdrawn**.
- **Stage 1R itself writes no per-row dump** — the 49-point sweep table in
  `p_live_stage1r_report.json` is the complete per-offset output; there is
  no per-row identity information to strip in the first place, so this
  round doesn't recreate the problem the gitignore pattern exists for.

Verified mechanically before this report (HK-022): `git status` shows the
old-path deletion staged, the new file present at 29,599,725 bytes,
`git check-ignore -v` names a rule for both locations. Every emitted file
(`README.md`, `WITHDRAWN.md`, `p_live_stage1r_report.json`,
`p_live_stage1r_run.log`, both new `.py`/`.gitignore` diffs) grepped
individually for "message" — zero hits beyond code/doc references to the
field name itself (NFR-021).

---

## 6. Scope

No `src/`, no Developer session, no DLL rebuild, no capture run — HK-011 not
engaged. DLL re-hashed from disk before arming, not inferred from a label.

---

## 7. Next

Per the ruling's Sec.10: **QA stops here.** Stage 2 (and Stages 3/4) remain
blocked — ROW A did not return ROW B, so the ruling's Sec.6 sequencing
condition is not met. GitHub issue #3 update (ruling Sec.8) to follow in this
same round, folding in this result. **Awaiting the Architect's ruling on
whether/how to pursue the anchor-offset finding (§4 above) as its own
pre-registration, and on Stage 2's status now that ROW A has fired rather
than ROW B.**
