# QA (k) review of the CS-CEIL spec (`arch/cs-model-ceiling` `6d911263`, file `…1931-architect-to-qa-spec-cs-model-ceiling.md`)

**Written:** 2026-11-12, `date -u` read 19:34:19Z. **To:** Architect, then the Captain. **Verdict: ACCEPT WITH FOUR REQUIRED AMENDMENTS (A1 to A4) and three freeze-time checks (F1 to F3).** I do not refuse the spec: the question is well posed, the method is a real ceiling construction, and the outcomes are reachable. Two of the amendments are validity holes in the CLOSE direction (a CLOSE that can be reached by the instrument being stingy), which is exactly where a ceiling study must not leak.

## 1. HK-027: what is on disk (checked 2026-11-12, nothing deleted)

| item | where | state |
|---|---|---|
| O, R2 and R3 buffers, `20260925_2010` | `_qa-scratch\gap-residual\cap\off\buffers` | **1,182 files: 400 O, 400 R2, 382 R3** (the 18 cycles without R3 are the spec's 18). 988 MB |
| their SHA-256 | `…\cap\off\hash` (1,182 files), `capture_index.tsv` (per-cycle hashes) | present |
| batch 1/2 natives | `…\cap\off\native` (per-cycle `.tsv`) | present |
| NR-TAX frozen category table | `…\gap-residual\nrtax_row_tags.jsonl` (Oct 30) and `class_rows.jsonl`; `cuts.json`; committed `qa/rr-study/results/2026-10-29-nr-tax/result_nrtax.json` | present |
| forced-leg code, unchanged | `qa/rr-study/gap-relocate-run/gr_forced.py` (+ `gr_common.py`) | present |
| CS-REFIT buffers (I, R3B, S) | `_qa-scratch\cs-refit\buffers`, 1,200 files | present (not needed by this spec) |
| `_qa-scratch\cs-ceil` | | does not exist yet |

**Nothing needs regenerating. No PC arms are needed.** The `…\cap\on` folder is empty (not needed).

## 2. Amendments required before freeze

**A1. CLOSE is not corrected for the instrument's recall.** V-REL passes at RL(CTRL-HIT) ≥ 0.80, so the method may lose up to 20 % of signals that are decodable in place. CLOSE tests CI_hi(RAW_worst) < 1.0 pp **uncorrected**: a measured 0.9 pp with RL(CTRL-HIT) = 0.80 is a true ceiling of about 1.1 pp, above the bar. The same holds for the unmodelled pessimism the spec does not mention: the fitted envelope (W = 0.32 s) can absorb a neighbour's residue and carry it to the clean slot, which makes the copy as bad as the original. **Required:** CLOSE iff CI_hi(RAW_worst) **÷ RL(CTRL-HIT)** < 1.0 pp, with RL(CTRL-HIT) in the same cycle bootstrap (point value in the denominator, the lower-bound variant reported). CTRL-HIT is band-matched, so it calibrates exactly this loss. This also fixes V-REL's source: 0.80 is GAP-RESIDUAL 0d's bar for the forced legs' recall in place, a different question from relocated recall. State it as such, or set it from the CTRL-HIT result with the correction doing the work.

**A2. Rows without a slot, and the CLOSE direction.** "No slot ⇒ excluded and counted" lets up to 10 % of CS-NR (≈ 70 rows = **0.58 pp of n_ref**, more than half the bar) leave the numerator, so the slot rule can select a CLOSE. **Required:** in RAW_worst, rows with no slot count as rescued, exactly as fit-zero rows do (worst case). In NET-CEIL they count as not rescued and stay out of "with a copy" (conservative for MODEL-STUDY). Each direction takes its adverse assumption; both counts are reported. V-SLOT stays as the coverage guard.

**A3. The slot's own in-window floor is never checked.** The ±1 dB match uses the quiet tail (13.2 to 14.8 s), which says nothing about what sits in the slot **during** the transmissions (weak undecoded signals, QRM, keyclicks). A slot that is clean in the tail and dirty in-window would again bias toward CLOSE. **Required:** a frozen second condition on the slot, its in-window floor (0 to 12.6 s) within X dB of its own tail floor, with X **set at freeze from the empty-band distribution on these same buffers** (a pilot with no relocation, HK-038: the number comes from data on file, not from me), and RL reported with and without that condition as a descriptive.

**A4. The optimism control is on a different population, and its source is thin.** CTRL-HIT is band-matched to CS-NR; CTRL-WEAK (≈ 73 IW rows) is not. The optimism (a fit absorbing noise, so an inflated amplitude) falls with SNR, so IW rows probably over-state it for CS-pure. That errs against MODEL-STUDY, which is the acceptable side, but with n ≈ 73 an RL(CTRL-WEAK) of 0.10 is 7 rows, so the correction (RL × ≈ 530 rows) carries about ±0.3 pp before the bootstrap. **Required:** state the direction of the bias (against MODEL-STUDY) in the spec, report CTRL-WEAK's band mix beside CS-NR's, and add **V-REPRO for CTRL-WEAK in place** (all of them not decodable in place; the spec checks CS-NR and CTRL-HIT only, and an in-place hit among the IW rows would inflate RL).

## 3. Freeze-time checks (I do these; they change no outcome)

- **F1. The quiet-tail window.** FT8 ends at 12.64 s plus dt. WSJT-X dt up to about +1.5 s ends at 14.1 s, inside 13.2 to 14.8 s, and the row's own 60 Hz includes the row. At freeze I measure the dt range in `20260925_2010` (aggregate) and, if late rows reach the window, move its start after the latest end in the neighbourhood, or take the median over the clean part; the tail definition is frozen as code before relocated output exists.
- **F2. Double data-aiding.** The fit is data-aided and the forced legs are data-aided: the test is mostly "is ŝ's fitted amplitude above the forced-leg threshold". That is the generous side by design, and CTRL-WEAK measures it; I will report RL by fitted-amplitude quartile so the Architect can see whether the answer is the row's SNR or its surroundings.
- **F3. Identical-structure property.** RAW_worst ≥ NET-CEIL holds in every bootstrap replicate (pure ⊂ CS-NR, RL(CTRL-WEAK) ≥ 0), so CLOSE and MODEL-STUDY are mutually exclusive as stated. I verify it in the self-test, both branches, and all three outcomes are reachable (RAW < 121 rows, NET-CEIL ≥ 121 above optimism within ≈ 530).

Under A1 the CLOSE bar sits on RAW_worst ÷ RL(CTRL-HIT); NET-CEIL stays uncorrected for recall (conservative for MODEL-STUDY). Both remain pre-registered and mechanical.

## 4. Cost

**Within the 3 h target and 4 h limit.** Machine time stays small (buffers on disk, no replay). The work: a small C# harness for `SubfeasFitSignal` through the friend assembly (the Replay81 route), the Python slot, shift and group code, the self-test with mutation kills, the V-REPRO run, then the run. Effort ≈ 3 to 3.5 h with A3's pilot. Machine time ≤ 45 min as the spec says; the PC is needed only for the forced legs, so I will ask the Captain for the window then.

## 5. Order

1. Architect adopts A1 to A4 (an amendment, or tell me where I am wrong).
2. I write the (k) record, freeze the code, the group lists and the self-test, run V-REPRO (no relocated output), commit, and ask the Captain for the PC window for the fits and forced legs.
3. One run, one reading, a short report.
