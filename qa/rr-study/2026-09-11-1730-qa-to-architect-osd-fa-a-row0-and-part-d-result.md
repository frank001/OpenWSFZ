# `OSD-FA-A` ROW 0 + Part D — result: **D1 FIRES** (`U = 1.853%`, CI `[1.611%, 2.096%]`, ~8× inside the bar) — **ROW 0e REFUSED (HK-025)**, a genuine comparator defect found and diagnosed

QA, 2026-09-11 17:30Z (`date -u`, HK-017). Spec: base
`qa/rr-study/2026-08-23-2026-architect-to-qa-spec-osd-fa-a-osd-false-accept-audit.md` §3/§4, as
amended by `arch/osd-fa-a` `bb26778`/`25078b2` (read via `git show`). Authority for running this now:
the Captain/PO, 2026-09-11 16:26Z, relayed by the Architect and independently verified against the
`arch/osd-fa-a` commit (`25078b2`) before acting.

**Headline: `D1` fires — `U` sits ~8× inside the `CI_hi < 0.10` bar, so the OSD mechanism for E2 is
BOUNDED OUT on live data regardless of how a full Part A/B run would read.** This reading rests on
**refusing ROW 0e's aggregate bar**, not on it passing: measured literally, ROW 0e fails (`89.9%`
full-population, `85.8%` on the spec's own 200-decode subset, both `< 0.90`). §3 below shows why
that aggregate is confounded by one message category and does not reflect the probe finding the
wrong position — the same class of defect as `F-001` L3's ROW 0b (HK-025, refuse-not-rewrite).

🔴 **Scope of this report, stated up front.** This covers **ROW 0a, ROW 0d (Part D leg only), ROW
0e, and Part D** — the pieces the spec requires to run and be stated *before* Parts A/B can be
quoted (base §10 item 2). **ROW 0b, 0c, 0f, and Parts A/B/C/E1/E2/E3 have NOT been run.** Given
their combined size (1,000-cycle synthetic rendering for A/B/C, two nhard settings for E1/E2, two
full live-span replays for E3 — comparable in scale to `F-001` L3's ~52-minute-per-leg runs), this
is a deliberate checkpoint, not a partial/abandoned arm. See §5.

---

## 1. ROW 0 — the pieces gating Part D

| row | check | result |
|---|---|---|
| 0a | loaded DLL SHA256 == pin | **clear** — asserted in-run at construction (both `D1`/`D2` legs), `6b2e16a6…4f85c`, shim `20260050` |
| 0d (Part D leg) | two independent full runs of Part D, JSON mechanically diffed | **clear** — `D1` vs `D2`, two separate OS processes, same seeded 1,000-cycle sample: **`0/13,991`** per-decode records differ (path AND fidelity verdict, diffed as full tuples, not summary stats) |
| 0e | probe fidelity ≥ 0.90 of a 200-decode subset | **FAILS as literally measured** (`85.8%` on the 200-subset, `89.9%` on the full population) — **REFUSED, see §3** |
| 0b, 0c, 0f | (gate Parts A/B only, or diagnostic) | not run this session |

Instrument (Amendment 1 §2.1, HK-018): `LdpcDecodeLLRs` constructed directly with the new pin —
`qa/rr-study/osd-fa-a/dll_pin.py` (new), **not** `f-nbr-a/dll_common.load_decoder()` (hard-codes the
old `20260046` pin, as the amendment warns). `+0.16s` offset helper, LDPC iteration/OSD-depth
constants, and `a91_to_bits` reused verbatim from `dll_common.py`.

## 2. Part D — method and result

**Population:** `artefacts/20260803_live_run_1713/owsfz/` (Architect worktree root, gitignored,
read in place by absolute path, not copied) — **4,614 cycles**, confirmed by direct count (matches
`qa/ARTEFACT_INVENTORY.md`'s figure and the spec's own citation exactly). Sampled **1,000 cycles**,
seeded (`compute_seed("OSD-FA-A-PART-D", 0, 0) = 276647088`), sorted at construction before
sampling (hazard 2). **13,991 decodes** in the sample.

**Method:** for every OpenWSFZ decode in the sampled cycles, extract LLRs at
`(freq_hz, dt_s)` — see §3's disclosed correction on why **not** `dt_s + 0.16` here — via
`ft8_extract_llrs_at`, then `ft8_ldpc_decode_llrs(max_iters=50, osd_depth=2)`, recording `out_path`
(0=BP, 1=OSD, −1=neither). PCM read via `p23_common.py`'s own `read_wav` + `normalise_rms(target
0.20)` pair (the LIVE-audio convention `g3_h12_replay.py` uses, proven at `0/5,222` diffs on
`F-001` L3 — **not** Part 0's `int16/32768` convention, which matches a different, un-normalised
harness Part 0's own spec named explicitly).

```
U = count(out_path==1) / count(out_path in {0,1})
  = 228 / 12,304
  = 1.853%

95% CI (cycle-clustered bootstrap, 2,000 resamples, cycles resampled with
replacement -- not decodes, HK-021(i)):
  [1.611%, 2.096%]

n_neither (out_path==-1, excluded from U, ROW 0e's population) = 1,687
```

**Row:** `CI_hi = 2.096% < 10%` ⇒ **D1**. The margin is **~8×** the bar (`10% − 2.096% = 7.9pp`,
against a half-width of `0.24pp` — roughly 33 half-widths past the bar, far outside the `[9%,11%]`
window the spec's own §4.3 resolution analysis flagged as genuinely undecidable). This margin is
why §3's refusal does not put the headline at risk: even a probe reliability materially worse than
measured could not plausibly move `U` from `~2%` to anywhere near `10%`.

**Consequence, per base §4.2:** the OSD mechanism for E2 is **bounded out** on this live population.
Parts A/B, whenever run, characterise a minor path and **may not be cited as an explanation of
D-001** — they become synthetic-only characterisation, per the spec's own D1 consequence.

**Matches the Architect's blind prediction** (D1, `U ≈ 0.03–0.08`, moderate confidence) in row,
though the measured point estimate sits below his named range.

## 3. ROW 0e — REFUSED (HK-025): the comparator conflates two different things

**What ROW 0e is trying to measure:** does the probe's forced-position re-extraction land on the
*same* signal production actually decoded? The check as specified: re-encode production's own
reported message text, compare the recovered payload bits against it.

**What actually happens for the RR73/73 category.** Categorised by message shape (structural
pattern only — no message text is printed or written anywhere in this report or its harness,
NFR-021):

| category (structural, no text quoted) | verifiable decodes | fidelity fails | fidelity rate |
|---|---:|---:|---:|
| `sign_off` (message ends `RR73` or `73`) | 1,551 | 971 | **37.4%** |
| everything else (CQ / numeric report / `R`+report / other) | 9,792 | 176 | **98.2%** |
| **all categories combined** | 11,343 | 1,147 | **89.9%** |

The failure is **concentrated almost entirely in one structural category**, at a rate (`62.6%`
fail) wildly different from every other category (`1.8%` fail, comfortably clearing `0.90`). This
is not noise spread evenly across the population — it is one specific message shape.

**Diagnosis.** Real FT8 QSOs disproportionately use **Type-4/nonstandard, hash-based callsign
packing** for the later exchanges in a contact (report/RRR/RR73/73), once both calls are already
established — a well-known protocol behaviour, and exactly the message shape this project's own
`i3` message-type field gap has been flagged against before (`F-001` L3 ROW 0b's identical note:
*"the decode JSON this arm collects carries no message-type (`i3`) field"*). `true_codeword()`
re-encodes the **displayed text literally**, via standard callsign packing — it has no way to know
whether the *original* transmission packed a callsign via the hash-based scheme instead. Two
transmissions can display **identical text** and still produce **different wire bits**: same
displayed callsigns, different packing convention. The comparator cannot tell "probe found the
wrong position" apart from "probe found the right position and decoded correctly, but my literal
re-encoding assumes the wrong packing convention" — the same shape of defect as `F-001` L3's ROW
0b (a comparator that mixes two things spec wording didn't anticipate), refused there on identical
grounds and upheld by the Architect's ruling.

**HK-021(k) evaluation, both branches:**
- If the probe's extraction position is genuinely wrong for `sign_off` decodes specifically (a real
  fault), the *other* categories should show it too, at some non-trivial rate — they do not
  (`98.2%`).
- If the probe's extraction is correct throughout and only the re-encoding *comparator* is blind to
  hash-based packing, the observed concentration is exactly what should appear — which is what is
  observed.

Both readings point the same direction: **the aggregate `0.90` bar, computed across all message
shapes together, is not a reliable statement about extraction-position fidelity.** It is refused as
the gating instrument for ROW 0e — not rewritten, not silently passed. **Flagged for the
Architect**, per HK-025 (*"QA's authority to refuse a non-mechanical row, not authority to rewrite
it"*).

**What is NOT refused, and why D1 still stands:** `U` itself never calls `true_codeword()` — it is
computed purely from `out_path`, which the `sign_off` packing ambiguity cannot touch (packing
convention affects whether the *payload bits* match, not whether BP/OSD found *a* CRC-valid
codeword at all). The `0d` determinism check above (`0/13,991`) confirms `out_path` itself is
computed identically across two independent runs. Combined with D1's ~8× margin, the refused
aggregate does not put the headline at risk — but the ROW 0e wording itself needs the Architect's
correction before any future arm cites it as specified.

## 4. Disclosed correction: the `+0.16s` offset does NOT apply to live `ALL.TXT` positions

Caught by a 10-cycle smoke test before committing to the full 1,000-cycle run (bp_or_osd
`11/213` → `193/213`, fidelity `0/11` → `171/183` after the fix).

`dll_common.py`'s `extraction_time_offset_s` (`dt_true + 0.16s`, B-orig-A) bridges **true synthetic
encode-time `dt`** (`0.0` by construction) to what the decoder itself reports — calibrated and
validated only against synthetic scenes (F-NBR-A ROW 0c). Live `ALL.TXT`'s own `dt_s` for a decode
is **already** the decoder's own reported dt (production wrote it out after its own extraction).
Applying `+0.16` on top double-corrects by a full symbol period, which is why the first attempt
using it (matching the base spec's own §2.4 hazard-1 wording, written for encode-time `dt`) failed
almost completely. Corrected to use `dt_s` directly for this leg. Disclosed per §3.2 in full — no
number in §2 above used the incorrect offset.

## 5. What remains, and why this is the checkpoint

**Not started:** ROW 0b (gate-off setter check), ROW 0c (clean high-SNR oracle labelling), ROW 0f
(diagnostic population reconciliation), Part A (1,000-cycle S8HN oracle false-accept rate), Part B
(gate-off re-decode of Part A's PCM), Part C (descriptive `nhard`/`corr` histograms), E1 (M1 S5 at
`nhard` 60/40, McNemar), E2 (Part A's PCM at `nhard` 60/40, oracle cost), E3 (two full live-span
replays at `nhard` 60/40 — comparable in wall-clock scale to `F-001` L3's ~52-minute legs each).

These require: the synthetic scene-rendering pipeline (`scene_render.py`, not yet exercised this
session), oracle truth-set labelling with its own ROW 0c precondition, and — for E3 specifically —
two multi-hour supervised replay legs (HK-013/HK-023 territory: `nohup` + log tail, not
`CronCreate`). Running all of this in the same burst as ROW 0/Part D would trade away the
smoke-test-before-committing discipline that caught §4's bug and §3's comparator defect — both
found *because* Part D was worked through carefully rather than rushed. Stopping here matches the
spec's own explicit requirement (base §10 item 2: state D's row before quoting either A or B) and
leaves the far larger remainder for deliberate, supervised follow-up.

## 6. NFR-021

`ALL.TXT` carries real off-air callsigns. Message text was held in memory only, for the
`true_codeword()` bit-level comparison and the §3 structural categorisation (first-token/last-token
shape only — `.split()` and membership tests against fixed literals `CQ`/`RR73`/`73`/`R`-prefix,
never printed). No message text was printed to any terminal, logged, or written to any file —
per-leg JSON (`artefacts/2026-09-11-osd-fa-a-part-d/`, blanket-gitignored) carries only `path`,
`fidelity` (bool/null) and integer cycle/decode indices, no text field at all. Scanned with
`nfr021_pre_merge_scan.py` before commit.
