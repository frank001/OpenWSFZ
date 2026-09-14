# `PASSBAND-140` — result: **ROW 0 ALL PASS; `D(C2) = +1.41pp` [0.42, 2.78] pp CI, `D(C1') = +0.60pp` same sign; GATE = G1 (ship-eligible)**

QA, 2026-09-14 17:07Z (`date -u`, HK-017). Per spec
`2026-09-14-1542-architect-to-qa-spec-g2b-140-passband-rearm.md`, as amended by Amendment 1
(`arch/g2b-passband-140` `4b7b9044`: `WIDE`'s `f_max` also moves 3000→3075, not just `f_min`).
Cleared by the Captain's "proceed" (2026-09-14 ~15:3xZ). **The Architect's session ended mid-arm**
(unreachable after the six legs finished) — this report goes to the Captain directly rather than
via the Architect relay the spec's §7 running order otherwise assumed.

**Headline.** Opening the candidate passband from `[200,3000)` to `[140,3075)` Hz recovers real,
WSJT-X-confirmed signal on C2 (today's live corpus, today's shipped binary): `D(C2) = +1.4136pp`
(`R_wild` 61.24%→62.65%), CI (wider of two cluster schemes) `[+0.42, +2.78]pp`, with **no material
in-band cost** (`D_in(C2) = -0.0022pp`, CI `[-0.02, +0.02]pp`). C1′ replicates in sign
(`D(C1′) = +0.60pp`). All eight ROW 0 checks pass — nothing VOID, nothing STOPs. Under the
Architect-set bars (`BAR_G = BAR_H = 0.25pp`), the gate reads **G1 — ship-eligible**.

🔴 **On Q1 (may the bars still move): NO, and this is not a judgement call — it is the spec's own
pre-registered rule.** §5 states verbatim: *"Movable before QA produces any `D`; frozen after. A
move proposed once `D` is known is refused and VOIDs the arm."* `D` now exists (this report). The
bars are frozen at `0.25pp`/`0.25pp` by the arm's own pre-registration, not by anyone's discretion,
mine included. G1 is not provisional on Q1 — there is nothing left for Q1 to decide.

🟡 **Q2 (is the "ship after R2 reports" condition discharged) genuinely IS still open, and per
spec §3.7 it gates the ship dev-task directly: *"G1 ⇒ ship recommended. Once the Captain confirms
§0.4, QA authors the ship dev-task."*** The Architect's own reading was "discharged" (§0.4: R2
reported 2026-08-22, its successor route parked 2026-09-14) — I have not independently re-derived
that chain and am not the authority on it either way; it is explicitly the Captain's to confirm.
**I have not authored a ship dev-task.** Q3 (retire revision 6's bars) is already implemented
throughout this report per the Architect's own §0.3 reasoning (legacy terms reported descriptively
only, A4 below, not computed this pass — see §8).

---

## 1. HK-020 — critical config (checked against spec §1/§2, not inherited from a header)

| config | value |
|---|---|
| `BASE` | `db31d351484046e9f2430e2536d68850c13adba9c7e74f6c911f96345a85627a`, shim `20260050`. **Not** byte-identical to the shipped pin (`6b2e16a6...`) — non-reproducible link (no `/Brepro`), confirmed behaviourally identical via the ROW 0b fallback (500/500 cycles, 8782 tuples each, 0 differing). Recorded as `BASE` per the Architect's own instruction. |
| `WIDE` | `ae0c7c213da7c80d47a01b38f3a538ba279cb52bd48c150153b66c33918c00aa`, shim `20260050` (unchanged). `.f_min=140.0f, .f_max=3075.0f` at `ft8_shim.c:1472`/`:1872` only — independently re-verified (diff cross-checked against `origin/main`'s live content; file re-hashed after loading). |
| C2 | `artefacts/20260908_live_run_1827-fp-floor-live-2/`, `cycle-audio/`, REF = `wsjtx-1-ft991a/ALL.TXT` A-only, window `2026-09-08T19:36:45Z..`. **5,222 cycles** (5 `*_2.wav` excluded, 0 inside window). `\|REF\|` restricted to the decoded cycle set: **91,046** (raw file had 91,076 in window). |
| C1′ | `artefacts/20260808_live_run_0016-8080/`, `owsfz/wav/` (our own capture), REF = `wsjt-x/ALL.TXT` A-only. Window `[260808_011045, 260808_111500]` — lower bound is the ROW 0h burned-cycle cut (251st sorted `wsjt-x/wav/*.wav`), mechanically re-derived, not hardcoded. **2,418 cycles.** `\|REF\|` restricted to decoded set: **64,771** (raw file had 76,967 in window). |
| Legs | **B40** `(10,0.10,40)`, **W40** `(10,0.10,40)` — both corpora. **B60** `(10,0.10,60)` — C2 only, seam check. **B40r** `(10,0.10,40)` — C2 first 300 cycles, determinism. **K60** not run as a full leg — already served its only purpose via the ROW 0b fallback. One process per (leg, corpus), per spec §2.2 — zero hash-table cross-corpus leakage by construction. |
| Managed chain | C# tool (`qa/rr-study/passband-140/PassbandChain/`), `TrimEnd()` → dedup → **production** `Ft8Decoder.IsPlausibleMessage` called by reflection (internal, no `InternalsVisibleTo` added), `CallsignGrammarStore` built exactly as `Program.cs:115-123`, from the station's own `callsign-grammar.json` (sha256 `7b581f31b7f0f65191da247eda6568e2f919d96c1414f9b268c39f4943bba37e`). No Python port. |
| Matcher / bootstrap | `live-gap-now/matcher.py` `recovery()` reused verbatim. `bootstrap.py` extended (this arm's own, `qa/rr-study/passband-140/bootstrap.py`) to a generic key→cluster mapping so the same routine serves both frequency clusters (as LIVE-GAP-NOW) and cycle clusters (this arm's addition, revision 6's own unit). `N_BOOT=2000`, seed `20260914`. |
| Wall time | ~1h10m, all six legs run concurrently (one process each); rates show visible CPU contention (each leg's throughput dips mid-run as the others compete, recovers as shorter legs finish) — **A5's isolated per-leg cost figure is therefore not cleanly measurable from this run** (flagged, §8). |

New code: `qa/rr-study/passband-140/{corpus.py,dll_pin.py,decode_leg.py,bootstrap.py,measure.py,row0b_fallback.py,row0d_seam.py,row0e_determinism.py,row0f_treatment_moves.py,a3_unmatched_density.py,PassbandChain/}`. Reused verbatim (HK-018): `live-gap-now/{matcher.py,seam.py,corpus.py (C2 only, via importlib to avoid a module-name collision)}`, `cycleframer-alignment-replay/{p23_common.py,h1_hash_token_contamination.py}`.

## 2. ROW 0 (strict order) — all eight PASS

| row | check | result |
|---|---|---|
| **0a** | Build diff = exactly two lines (`.f_min`+`.f_max` per Amendment 1); both SHA-256s in manifest before any leg ran; `WIDE` independently re-verified (SHA + `ft8_lib_version_check()=20260050`) | **PASS** |
| **0b** | `SHA(BASE) == 6b2e16a6...` **OR** K60/B60 identical tuples, C2 first 500 cycles | **FAIL on the direct SHA check** (`db31d351...` ≠ pin — non-reproducible link, independently confirmed). **PASS via fallback**: 500/500 cycles, 8,782 tuples each side, **0 differing.** |
| **0c** | Chain applied to C2's live `ALL.TXT`, grouped per cycle, rejects `<=0.1%` | **PASS.** `57,969` rows (exact match to the spec's own drafted-in count), `3` rejected (`0.0052%`, threshold `<=58`). |
| **0d** | B60 through the chain vs C2 live `ALL.TXT`, `F_live >= 0.97` | **PASS.** `F_live=0.9843` (57,061/57,969). `F_rep=0.9841` (reported only, not gated). 0 live cycles with no WAV. Close to LIVE-GAP-NOW's own `F_live=0.9832` on the same corpus/binary/`nhard` — a useful independent cross-check. |
| **0e** | B40r's tuples == B40's, C2 first 300 cycles, mechanically diffed | **PASS.** 5,287 tuples each side, 0 differing. |
| **0f** | (Amendment 1, both edges) W40 emits `>=1` decode `<200Hz` **and** `>=1` `>2959Hz` on C2; B40 emits 0 of either; outputs differ | **PASS.** B40: 0 outside `[200,2959]`. W40: 1,232 below 200Hz, 104 above 2959Hz. Exhibits: low `ts=260908_193715 freq_hz=175 snr=-12`; high `ts=260909_061645 freq_hz=3016 snr=0` (no message text, NFR-021). |
| **0g** | No cycle hits `MAX_RESULTS=200`, any leg | **PASS.** 0 truncated, all six legs. |
| **0h** | 251st sorted `wsjt-x/wav/*.wav` == `260808_011045.wav` | **PASS**, exact match. |

**Nothing VOID, nothing STOPs.** The arm proceeds to §3.3–3.7 in full.

## 3. `R`, `D`, and bands (spec §3.1/§3.3)

```
C2:  B40  R_base=60.0389%  R_wild=61.2361%  M=1.1972pp  (n_ambiguous=10, 0.92%)
     W40  R_base=61.4096%  R_wild=62.6496%  M=1.2400pp  (n_ambiguous=10, 0.89%)
     D(C2) = +1.4136pp

C1': B40  R_base=57.6168%  R_wild=58.4629%  M=0.8461pp  (n_ambiguous=6, 1.09%)
     W40  R_base=58.2128%  R_wild=59.0588%  M=0.8461pp  (n_ambiguous=6, 1.09%)
     D(C1') = +0.5959pp
```

**Bands (Amendment 1, five terms), C2:**

| band | REF rows | D_band |
|---|---:|---:|
| `sub` (≤137Hz) | 17 | +0.0000pp |
| `low` (138–199Hz) | 1,731 | +1.3037pp |
| `in` (200–2959Hz) | 89,119 | **-0.0022pp** |
| `hi` (2960–3034Hz) | 155 | +0.1120pp |
| `beyond` (≥3035Hz) | 24 | +0.0000pp |

Sum of bands = `1.413571162`, `D` = `1.413571162`, `\|diff\|` = `0.00e+00` — additive identity holds
exactly. **`beyond` reading 0 is expected, not a defect**: `WIDE`'s true top base tone (8-tone span)
is ≈3034Hz, so nothing ≥3035Hz can be recovered by construction, same logic as the low edge.

**C1′ bands:** `sub` +0.0031pp (6 rows) · `low` +0.5357pp (703) · `in` +0.0124pp (63,955) · `hi`
+0.0448pp (56) · `beyond` +0.0000pp (51). Sum matches `D(C1')` to `3.33e-16`.

**Yield:** `D_low(C2) ÷ (low REF share)` = `1.3037 ÷ 1.9012%` = **68.6%** of the low-band ceiling
actually recovered (spec's own predicted range was `[35%, 65%]` — slightly above, a genuinely
strong result, not a red flag: the ceiling itself (§0.2) was computed from raw counts, not from
what a real decoder could plausibly reach).

## 4. Confidence intervals (spec §3.1 — two cluster schemes, wider governs)

```
D(C2):     freq clusters (n=2,734): [+0.4209, +2.7779]pp  SE=0.6180pp
           cycle clusters (n=4,112): [+1.3453, +1.4786]pp  SE=0.0344pp
           WIDER GOVERNS: [+0.4209, +2.7779]pp

D_in(C2):  freq clusters (n=2,662): [-0.0203, +0.0160]pp  SE=0.0092pp
           cycle clusters (n=4,112): [-0.0190, +0.0146]pp  SE=0.0086pp
           WIDER GOVERNS: [-0.0203, +0.0160]pp
```

**Disclosure (HK-021(m)/(o), reported against the spec's own pre-drafted power table):** the
spec's own §3.3 predicted frequency-cluster `SE(D)` at `0.10–0.20pp`; the realised value is
`0.618pp`, roughly 3–6× wider than anticipated. This does not change today's reading — `D`'s point
estimate (`1.41pp`) is large enough that `CI_lo` still clears `BAR_G` comfortably even under the
wider-than-predicted interval — but it means this arm's power was lower than the spec's own table
implied, worth carrying into any future arm of this shape that plans its sample size against a
predicted SE. Cycle-cluster SE (`0.034pp`) landed close to the spec's own `≈0.05pp` estimate.

## 5. A3 — what the operator would see in the new band (spec §3.5, load-bearing before any ship
recommendation)

```
W40, C2, post-chain, freq in [137.5, 200)Hz: 1,232 decodes
  matched (exact or wildcard-gained against REF): 1,208 (98.05%)
  unmatched: 24 (1.95%)

new-band unmatched density:  0.0460 / bin / 100 cycles  (10 bins)
in-band  unmatched density:  0.0255 / bin / 100 cycles  (441 bins, B40's own [200,2959) baseline)
ratio = 1.80  (flag threshold: > 3)
```

**No flag.** The new band's unmatched-decode density is under 2× the decoder's own established
in-band rate, and 98% of what it emits there is REF-confirmed. This is a materially clean result —
not spray, not a false-accept surface, real signal recovery.

## 6. Gate (spec §3.6, `BAR_G = BAR_H = 0.25pp`, frozen — see the Q1 note in the headline)

```
G1: CI_lo(D(C2)) >= +BAR_G   AND   CI_lo(D_in(C2)) >= -BAR_H   AND   D(C1') > 0 (point)
    0.4209 >= 0.25 ✓          -0.0203 >= -0.25 ✓                0.5959 > 0 ✓

GATE: G1 — ship-eligible
```

G1 and G2 are mutually exclusive by construction (split on `D_in`'s sign relative to `-BAR_H`); G3
cannot hold alongside G1 (`CI_lo>=0.25` vs `CI_hi<0.25`, `lo<=hi`); this is not G4 — all three G1
conjuncts hold cleanly, none marginally.

## 7. NFR-021

C2/C1′ `ALL.TXT` and WAVs carry real third-party callsigns. This report, `row_status.md`, and every
`.py` file in `qa/rr-study/passband-140/` carry counts, rates, frequencies, and SNRs only — no
message text anywhere. ROW 0f's exhibits are `(ts, freq_hz, snr)` only, per spec's own instruction.

## 8. What this report does NOT cover (disclosed, not silently skipped)

- **A4 (legacy readout, revision 6's `g_low`/`churn_net`/`churn_gross`)** — not computed this pass.
  Purely descriptive per spec (§0.3: revision 6's bars retired, no row reads this), so it does not
  block the gate reading above; a follow-up if the Captain wants continuity with the revision-6
  numbers specifically.
- **A5 (isolated per-cycle wall-time cost, `BASE` vs `WIDE`)** — not cleanly measurable from this
  run: all six legs ran concurrently and visibly contended for CPU (rates dip and recover as other
  legs finish), so `B40` vs `W40`'s raw per-cycle timings from this run are not an isolated cost
  comparison. A clean A5 would need `B40`/`W40` run back-to-back, single-process, on an otherwise
  idle machine — a cheap follow-up if wanted, not required to read the gate.
- **The ship dev-task** — not authored. Gated on the Captain's confirmation of §0.4 (Q2), per spec
  §3.7's own instruction, explicitly not mine to presume.

## 9. Artefacts

`artefacts/passband-140/{bin/,_out/*.jsonl}` (gitignored, ~4h of decode output for both corpora,
both legs, plus B60/B40r). Committed: `qa/rr-study/passband-140/*.py`,
`qa/rr-study/passband-140/PassbandChain/`, `dll_manifest.json`, `row_status.md`, this report. All
on `qa/base`, latest `3408291` plus this file. **Not pushed** (HK-033) — Captain's go needed for
push/PR.
