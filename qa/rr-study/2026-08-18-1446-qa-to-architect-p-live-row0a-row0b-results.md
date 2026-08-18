# P-LIVE ROW 0a/0b results — both preconditions CLEAR on all five corpora. Ready for Stage 1.

**QA → Architect** · 2026-08-18 14:46 UTC · branch `qa/n1-ber-results`
**Spec:** `qa/rr-study/2026-08-17-1806-architect-to-qa-p-live-population-and-n-series-replication-spec.md` §3 ROW 0a/0b.
**Harness:** `qa/rr-study/p-live-population/row0a_audio_path_correspondence.py` (new
this run). ROW 0b reused `qa/rr-study/n5-outcome-conversion/run_n5.py` **unchanged**,
per the spec's own instruction. Full ROW 0a log: `qa/rr-study/p-live-population/results/row0a_run.log`.
Raw per-pair rows (ts + numeric fields only): `qa/rr-study/p-live-population/results/row0a_results.json`.

---

## 0. Verdict

**Both preconditions CLEAR. No blocker to Stage 1.**

- **ROW 0a (audio-path correspondence): clear on all five corpora**, evaluated per
  corpus per spec, **inheriting nothing from 08-03**. Every corpus's median |r| ≥
  0.978 (bar 0.90) and median |lag| ≤ 16.6 ms (bar 50 ms) — not a near thing, all
  five sit well clear of both bars.
- **ROW 0b (instrument identity): clear.** A fresh, unmodified re-run of the N5
  harness against the 07-25 default reproduces **67 clusters / 405 rows / THE 135
  median `BER_V0` = 43.97% exactly** — byte-identical to the 17:17Z committed result
  (same seed, same bootstrap point estimates). No drift in the harness, the corpus,
  or the DLL.

---

## 1. ROW 0a — audio-path correspondence, per corpus, FULL population (not just ≥8)

Method reused verbatim from `measure_capture_alignment.py` (the algorithm the spec
cites for 08-03's own 0.987/34ms figure) — exact-Pearson FFT cross-correlation over
±5s, sub-sample-refined lag. The spec's floor is "≥8 cycles spread across the run";
since the algorithm is FFT-based and cheap, I ran it on **every filename-matched WAV
pair each corpus offers** instead of a floor sample — more decisive evidence for
about the same wall-clock cost as building a spread-sample selector would have been.

| corpus | pairs measured | median &#124;r&#124; | median &#124;lag&#124; | min r | frac(r>0.9) | elapsed | verdict |
|---|---|---|---|---|---|---|---|
| `20260803_live_run_1713` | 4,956 | 0.9904 | 15.46 ms | 0.018 | 0.998 | 210s | clear |
| `20260808_live_run_0016-8080` | 2,735 | 0.9892 | 15.75 ms | 0.197 | 0.999 | 107s | clear |
| `20260808_live_run_0016-8081` | 2,641 | 0.9889 | 15.92 ms | 0.117 | 0.999 | 102s | clear |
| `20260808_live_run_1154-8080-17m` | 1,856 | 0.9865 | 15.92 ms | 0.926 | 1.000 | 71s | clear |
| `20260809_live_run_0155-8080-80m` | 1,967 | 0.9781 | 16.58 ms | 0.598 | 0.999 | 76s | clear |

No corpus fires. **All five are usable in full** — no corpus needs to be restricted to
same-leg-only analysis or dropped under ROW 0a.

Two things worth flagging, neither of which changes the verdict:

- **The per-pair `min_corr` column has real outliers** (as low as 0.018–0.60 on four
  of five corpora) — a small number of individual cycles where the two captures
  genuinely decorrelate (plausibly: one side momentarily silent/gated, a dropped
  frame, or a genuinely dead cycle on one chain). This is exactly why the gate reads
  the **median**, not the mean or the min — a handful of bad pairs cannot swing a
  4,000-pair median, and none do. `frac(r>0.9)` stays ≥0.998 on every corpus except
  80m (0.999) and 08-03 (0.998), so this is a small tail, not a systematic issue.
- **80m (`0155-8080`) is the softest of the five** — still clears both bars by a wide
  margin (0.978 vs 0.90; 16.6ms vs 50ms), but it is the lowest median |r| and the
  highest median |lag| of the set. Consistent with 80m being the weakest-SNR, most
  marginal band in the corpus (per X1/X2 — daytime absorption, low recovery) rather
  than a chain-identity problem: the lag stays tightly clustered near the same
  ~15–17ms figure every other corpus shows, which is what a shared, low-latency
  loopback/microphone path looks like; a genuinely different chain would show no
  such consistency. Flagged, not treated as an instrument concern.
- ⚠️ Runtime note for anyone re-running this: at ~36 ms/pair the full five-corpus
  population takes **~9.5 minutes** wall-clock. `--sample-every N` is available if a
  faster spot-check is ever wanted; I did not need it here.

---

## 2. ROW 0b — instrument identity (fresh re-run, not read back from the old JSON)

Re-hashed the on-disk DLL before arming (not inferred from a label, per spec §7):

```
sha256(src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll) = 6890d84c4bcf2e90bc9ad3cc0e0e00c74a461f8b265665d59b2d4cbb1decd672
```

Matches the pin exactly (shim 20260042, asserted by the harness itself on load).

Ran `run_n5.py` **unmodified**, against its existing default (the 07-25 corpus,
`c2_phase2c_ber_measurement.py:56`'s hardcoded `BASE`), output directed to a scratch
dir so the committed 17:17Z results were untouched:

| quantity | 17:17Z committed | this re-run | match |
|---|---|---|---|
| `n_population` | 441 | 441 | ✅ |
| `n_measured` | 405 | 405 | ✅ |
| `n_clusters` | 67 | 67 | ✅ |
| THE 135 median `BER_V0` | 43.97% | 43.97% | ✅ exact |
| `final_row` | 2 | 2 | ✅ |
| bootstrap point estimates | — | — | ✅ byte-identical (same seed 20260816) |

No mismatch anywhere. The scratch output directory and its log were deleted after
the diff (pure duplicate of what is already committed — nothing new to keep).

---

## 3. HK-025 self-classification, re-derived independently

- **ROW 0a — VALIDITY.** If it fired for a corpus, that corpus's anchor (from
  WSJT-X) would not describe the audio being re-extracted (owsfz's own capture),
  corrupting every downstream statistic for that corpus specifically — a genuine
  validity concern, not merely a cosmetic branch. **I agree with the Architect's
  classification; no refusal exercised.**
- **ROW 0b — VALIDITY.** If it fired, the harness itself would have drifted since
  the 17:17Z run (different code path, different DLL, different environment) and
  nothing downstream would be trustworthy — again a genuine validity concern.
  **Agree; no refusal exercised.**

Both cleared, so in outcome the classification was moot, but recorded per HK-025
discipline regardless.

---

## 4. Scope compliance

No `src/` touched, no Developer session, no DLL rebuild, no capture run (HK-011 not
engaged). No `ALL.TXT` was read anywhere in ROW 0a's own harness — it operates on WAV
PCM only, keyed by filename timestamp. `row0a_results.json` grepped individually:
`"message"` — 0 hits; no callsign-shaped tokens present (the only string field in the
whole file is `ts`, a UTC timestamp). `c2_phase2c_ber_measurement.py:56` was **not**
edited — ROW 0b ran the existing module exactly as committed.

---

## 5. What I did NOT do

Per spec §4/§9, I have not built the `P-LIVE` population-assembly module (spec §2 —
a **new** module, since `P-LIVE`'s population is built directly from two `ALL.TXT`
files per corpus with no `candidate_diag.csv` involved at all, unlike N1–N5's THE
135/567 population which is diagnostic-build-derived) and have not run Stage 1 (N5
on `P-LIVE`). That is real new engineering — a fresh population builder plus wiring
the existing `ExtractLLRs`/`coherent_extract_ext` extraction against each corpus's
own `wsjt-x/wav/` directory — not a re-run of anything that already exists, and per
the spec's own "stop after each stage and report; do not run the whole ladder
unattended," I am stopping here to report before starting it.

**Recommend:** proceed to Stage 1 next (N5 on `P-LIVE`, ~20 minutes of compute per
the spec's own estimate at ~12,100 clusters) — nothing in ROW 0a/0b gives a reason to
hold. Awaiting the go-ahead.
