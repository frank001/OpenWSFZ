# `D003-LIVE` — result: **ROW 2 FIRES, cleanly — D-003 is active and attributable to OpenWSFZ**

QA, 2026-09-10 15:50Z (`date -u`, HK-017). Spec:
`qa/rr-study/2026-09-10-1536-architect-to-qa-s1-ladder-reply-and-d003-live-spec.md` §3
(`arch/d003-live`, commit `bd337f2`). `R_STAR` ratified and the HOLD lifted by commit `2c439b5`
("0.17% is approved", PO, 2026-09-10 15:44Z). Harness: `qa/cycleframer-alignment-replay/d003_live.py`,
committed alongside this file. Join reused **by import** from Part B's harness
(`fp_floor_live_2_part_b.py`: `clopper_pearson`, `ts_to_dt`) and `h1_hash_token_contamination.wildcard_match`,
per spec §3.1 "Do not write a new implementation." Only the candidate-selection logic
(`ASSIGN_EXCL` / `ASSIGN_NEAR`) is new — Part B never needed to pick a single candidate, only ask
whether ≥1 existed.

*(Correction to the harness, not this report, per the Architect's acceptance ruling §4: the opening
docstring of `d003_live.py` states that Part B's `load()` loader is imported. It is not — only
`wildcard_match`, `clopper_pearson`, and `ts_to_dt` are imported, as stated correctly above. The
loader and the candidate-enumeration logic are new code in this harness, and ROW 0a below — exact
reproduction of Part B's population figures — is exactly the check that validates that new code.)*

**Headline: `R_u = 4.8524%`, combined CI `[4.1823%, 5.5111%]`, `p_sign = 2.29×10⁻¹³` — ROW 2 fires by
~25–32× the `R_STAR = 0.17%` bar, on both bounds, with a sign test as decisive as this programme has
ever produced.** `ASSIGN_EXCL` and `ASSIGN_NEAR` give **identical** figures, because in this corpus no
OpenWSFZ decode ever has more than one candidate match under the join (0a/0b below). D-003 (OpenWSFZ
misreads SNR on live audio, by ≥10 dB, one-sided against its own mirror) is **real, active on the
current binary (shim ≥`20260046`), and heavily concentrated below 600 Hz** — 34.67% there vs 1.23%
above it, ~~both still well past `R_STAR`~~ ⛔ **STRUCK 2026-09-10 16:03Z, per the Architect's
acceptance ruling §2 (`2026-09-10-1556-architect-d003-live-acceptance-ruling.md`, `arch/d003-live`
`1d09325`): my own spec §3.6 item 3 asked for a slice's `R_u` without its `R_o` — an HK-021(u)
violation, now struck at the spec too. With the mirror added, the one-sidedness sits entirely below
600 Hz; the ≥600 Hz slice does NOT clear `R_STAR` as a D-003 finding. See the corrected §3 table
below.** ~~This **reverses** the Architect's own June-era hope in the S1-ladder reply (§2.1) that
D-003 might be confined to a retired mechanism, and~~ ⛔ **CORRECTED, same ruling §4: §2.1 expresses
no such hope — it says the June figures are not a baseline and that D-003 was untested on shims
≥`20260046`. What this result contradicts is his §4 prediction, cited next.** This result lands well
outside even his own stated prediction range (§4 of the spec: central 0.5%, range 0.05–3%, discounted
in advance as ~1-in-3 calibrated).

---

## 1. Population (mechanically re-derived from `ALL.TXT`, not trusted from prose — HK-022)

| quantity | value | check |
|---|---|---|
| Corpus | `artefacts/20260908_live_run_1827-fp-floor-live-2`, span `[2026-09-08T19:36:45Z, close)` | Amendment 3, frozen |
| REF | WSJT-X #1, read from **the snapshot** `wsjtx-1-ft991a/ALL.TXT`, never AppData | sha256 `dda9483aaee6…` matches the spec's pinned `REF_SHA256` exactly — **PASS** |
| Clamp model | `min(REF SNR in span) = −24`, 0 readings below it | **PASS** (over all 91,076 REF lines in span, not just corroborated pairs) |
| Total OpenWSFZ decodes in span | 57,969 | matches Part B's own population |
| Corroborated (`ASSIGN_NEAR`) | 55,607 | matches Part B's `K_all` denominator exactly |

## 2. ROW 0 — all three checks, evaluated in full (HK-025)

| row | check | result |
|---|---|---|
| 0a | `ASSIGN_NEAR` reproduces Part B exactly: 57,969 total; 55,607 corroborated; 313 corroborated at `snr_ow ≤ −24`; 6 at `≤ −31`, bins `{−36:1, −32:1, −31:4}` | **PASS** — every figure matches to the integer |
| 0b | Same row under `ASSIGN_EXCL` and `ASSIGN_NEAR` | **PASS** — both give ROW 2, and are in fact numerically **identical** (see below) |
| 0c | `delta[uncensored]` takes ≥5 distinct values | **PASS** — 50 distinct values under both assignments |

**ROW 0 CLEAR on all three checks.** `R_u` is legitimate to read.

**Why EXCL and NEAR are identical, checked, not assumed:** of the 57,969 OpenWSFZ decodes, exactly
55,607 have **precisely one** join candidate and 2,362 have **zero** — none has two or more. There is
no assignment ambiguity anywhere in this corpus, so `ASSIGN_EXCL`'s exactness requirement and
`ASSIGN_NEAR`'s nearest-candidate tie-break select the same partner every time. 0b holds cleanly; it
was not stress-tested against real ambiguity here because there wasn't any to stress-test against.

## 3. The headline, in full

```
n_u (uncensored pairs)       = 54,942   (665 censored pairs excluded, REF = −24)
c (median delta, uncensored) = −2.0 dB
k_u (under-reads, ≥10dB, signed) = 2,666   k_o (over-reads, the mirror) = 906
R_u = 4.8524%   R_o = 1.6490%   (same sentence, sibling (u))
CP95(R_u)              = [4.6742%, 5.0354%]
cluster bootstrap(R_u) = [4.1823%, 5.5111%]  (2,000 draws, seed 20260910, 3,283 clusters,
                                               sorted at construction)
combined CI(R_u)       = [4.1823%, 5.5111%]
sign test: U = 591  O = 367  p_sign = 2.28769×10⁻¹³
```

`lo` clears `R_STAR` by **~25×**, `hi` by **~32×**, and the point estimate `R_u` sits at **~28.5×**
`R_STAR`. The sign test is not a formality here — 591 clusters have more under-reads than over-reads
against 367 the other way, at `p ≈ 2×10⁻¹³`: this is one-sided, attributable to OpenWSFZ, not
reference noise.

**Context (sibling (u) — descriptive frequency split, spec §3.6 item 3):**

| population | `R_u` |
|---|---|
| `freq_ow < 600 Hz` | `2,062/5,947 = 34.6729%` |
| `freq_ow ≥ 600 Hz` | `604/48,995 = 1.2328%` |

The 600 Hz boundary is taken from June mechanism 1's report (low-frequency sideband contamination
from DC/hum), not chosen from this data. ~~**Both halves clear `R_STAR` independently** — even the
"clean" ≥600 Hz population sits at ~7.25× the bar — but the low-frequency mechanism dominates by
almost 30×, consistent with mechanism 1 persisting on the current shim.~~

⛔ **STRUCK 2026-09-10 16:03Z, per the Architect's acceptance ruling §2.** The paragraph above cited
`R_u` per slice without its mirror `R_o` (spec §3.6 item 3's own error, HK-021(u): the base rate
belongs in the same sentence). Without `R_o`, a slice's `R_u` shows only how much the two programs
disagree there, not which one is misreading. **Corrected split, with the mirror, computed by the
Architect from these same committed functions** (`d003_live.load`, `build_records`, `assign_pairs`,
`compute`, `cluster_key`, imported not reimplemented), `ASSIGN_NEAR`, global `c = −2.0`:

| slice | `n_u` | local median `delta` | `k_u` / `R_u` | `k_o` / `R_o` | clusters `U` / `O` |
|---|---:|---:|---:|---:|---:|
| `freq_ow < 600 Hz` | 5,947 | −10.0 | 2,062 / 34.67% | 6 / 0.10% | 296 / 0 |
| `freq_ow ≥ 600 Hz` | 48,995 | −1.0 | 604 / 1.23% | 900 / 1.84% | 295 / 367 |

**All of the one-sidedness sits below 600 Hz**: 296 clusters under-read-dominant, none the other
way. That band holds 10.8% of `n_u` and 77.3% of `k_u`. It is a band-wide level shift, not scattered
misreads — local median `delta` −10 dB against −2 dB overall, i.e. a typical low-band signal reads
about 8 dB lower relative to WSJT-X than the same kind of signal elsewhere, on the same samples.
Consistent with June mechanism 1 (DC/hum contaminating the local noise floor below ~600 Hz,
`qa/endurance/2026-06-14-582bd69/report.md`) — that report is still not a baseline.

**Above 600 Hz, under-reads are FEWER than their mirror** (604 vs 900) — there is no one-sided
OpenWSFZ under-read there, so **"the ≥600 Hz slice clears `R_STAR`" is not a D-003 finding.** Part of
the apparent over-read excess is that the global `c = −2` sits 1 dB below that band's own local
median (−1), shifting its cut-offs; this was not tested and is not a finding either. Disagreement of
≥10 dB is still material in **both** directions there (`R_u = 1.23%`, `R_o = 1.84%`, ~7–11× `R_STAR`)
— the ROW-3 "material, not attributable" pattern — so the synth-into-real block (§8 below) holds in
both bands regardless of this split.

**Exploratory only, not citable as a boundary** (a 1000 Hz sub-cut, chosen after the spec, HK-021(y)):
600–1000 Hz remains under-read-dominant (`n_u = 10,041`, local median −3, `k_u = 215` vs `k_o = 66`,
clusters 86/28); ≥1000 Hz reverses (389 vs 834, clusters 209/339). Reads as the low-band mechanism
tapering rather than stopping sharply at 600 Hz — a hypothesis for whoever investigates the
mechanism, not a result.

## 4. Histogram of `(delta − c)`, uncensored, integer bins (spec §3.6 item 2)

Identical under both assignments (§2 above). Full curve in the harness's own stdout
(`qa/cycleframer-alignment-replay/d003_live.py` run, `2026-09-10`); the load-bearing tail:

```
  -29 :      1        -13 :    313 #       +10 :    363 #
  -27 :      1        -12 :    378 #       +11 :    223
  -26 :      3        -11 :    524 #       +12 :    135
  -25 :      3        -10 :    663 ##      +13 :     87
  -24 :      3         -9 :    842 ###     +14 :     35
  -23 :      7         -8 :   1107 ####    +15 :     30
  -22 :     12         -7 :   1491 #####   +16 :     17
  -21 :     30         -6 :   1854 ######  +17 :      6
  -20 :     37         -5 :   2452 ########+18 :      4
  -19 :     50         -4 :   2901 ##########+19:  4
  -18 :     65         -3 :   3348 ############+20:  1
  -17 :     87         -2 :   3729 #############+21:  1
  -16 :    115         -1 :   4274 ###############
  -15 :    161         +0 :   4451 ################
  -14 :    213         +1 :   4521 ################  (mode)
                        +2 :   4452 ################
                        +3 :   4157 ###############
                        +4 :   3615 #############
                        +5 :   2972 ##########
                        +6 :   2206 ########
                        +7 :   1439 #####
                        +8 :    932 ###
                        +9 :    627 ##
```

Roughly symmetric mound centred near 0 (by construction — `c` is the median), but with a visibly
heavier and longer left tail past `−10`: `k_u = 2,666` in `(−∞,−10]` against `k_o = 906` in
`[+10,+∞)`, the asymmetry the sign test formalises at the cluster level.

*(Correction, per the Architect's acceptance ruling §4: the "(mode)" label above originally sat on
bin `+0` (4,451); bin `+1` (4,521) is the actual mode. Fixed above — no figure changes, both counts
were already printed correctly.)*

## 5. Descriptive: the 313 corroborated-removed (`snr_ow ≤ −24`, `ASSIGN_NEAR`) split (spec §3.6 item 4)

**Does NOT reopen Part B ROW 2 (accepted `3e997e0`)** — this bears on *why* `T` costs genuine
decodes, not on *whether* it does.

| class | count |
|---|---|
| (a) REF `= −24`, censored | 109 |
| (b) uncensored AND `under` (the misread class) | 60 |
| (c) uncensored, not `under` | 144 |
| **total** | **313** (matches 0a) |

## 6. openspec scenario (spec §3.6 item 5)

`openspec/specs/ft8-decoder/spec.md:104-107`: *"No SNR values below −30 dB when WSJT-X reports normal
SNR for the same message."* `V` = corroborated pairs (`ASSIGN_NEAR`) with `snr_ow ≤ −31`:

```
V = 6  (matches 0a)   V_cens = 3   V_uncens = 3
```

**`V_uncens = 3 ≥ 1`: a violation with an uncensored reference.** Three decodes report `snr_ow ≤ −31`
while WSJT-X — not itself clamped — reads them well above that. This is a real (small-`n`) instance of
the scenario, not one of the vacuous "every WSJT-X decode satisfies `≥ −24`" cases the spec's §2.2
flagged as a scoping defect. Per §3.6 item 5, QA is deciding whether to raise a defect: **yes, folded
into the D-003 record this result authorises below (HK-015)** rather than filed separately — `V` is a
small-`n` corroborating instance of the same mechanism ROW 2 already establishes at scale, not an
independent finding.

## 7. Reading rule (spec §3.4, strict order — ROW 0b already confirms `EXCL == NEAR`)

```
hi = 5.5111%  vs  ROW 1 bar (hi <= R_STAR = 0.1700%)                -> NOT MET
lo = 4.1823%  vs  ROW 2 bar (lo >= R_STAR = 0.1700% AND p_sign<0.05) -> MET, ~25x margin, p=2.3e-13
```

**>>> ROW 2 <<<** — *"D-003 active and attributable to OpenWSFZ. No operator control is drafted. QA
may author a D-003 defect record or dev-task carrying the rate and frequency split (HK-015); any
`src/` work goes through HK-011."*

## 8. What this does NOT do (spec §3.5/§6, unchanged)

- Does **not** reopen `FP-FLOOR-LIVE-2` Part B (ROW 2 accepted `3e997e0`), `FP-PARITY` ROW 3
  (`F−T=5.378dB` stays fired), or any `FP-REGRESSION` guard. Creates **no baseline**.
- Authorises **no `src/` work** in any row.
- **Blocks synth-into-real for any SNR-reading deliverable** (spec §1.1/§3.5) — an S1 bias/R&R study
  on a real substrate, or any `F`-type minimum statistic where one misread sets the answer, cannot be
  built while OpenWSFZ under-reads live SNR at ~5% one-sided. §1.2's wideband-AWGN rung extension
  (the PO's call, no D-003 exposure) is **unaffected**.
- No capture run. Everything on disk, per spec.

## 9. NFR-021

Harness scanned with the project's own `qa/rr-study/nfr021_pre_merge_scan.py` `scan()` (imported, not
reimplemented) — **0 flagged tokens**. This report scanned the same way before commit. Only
aggregate counts, rates, SHA256 prefixes, and dB figures appear anywhere in either artefact; no
`message_text`, no callsign, no raw `ALL.TXT` line is quoted. Message text is held only transiently
inside `d003_live.py`'s `build_records()`/`assign_pairs()` locals for the exact-vs-wildcard tie-break,
never returned, never printed.

## 10. Proposed next step, for the Captain/Architect, not decided here

This result is a QA measurement, not a defect record or a dev-task. Per HK-015, QA may author either;
neither is written yet, pending the Captain's direction on whether to proceed straight to a D-003
defect record (carrying §3's rate/frequency split and §6's openspec-violation instances) or hold for
Architect review first.

**Superseded 2026-09-10 16:03Z:** the Architect's acceptance ruling (§3 of
`2026-09-10-1556-architect-d003-live-acceptance-ruling.md`) clears QA to author the D-003 defect
record now, without further review, on the ruling's terms. Written as
`DEFECT-d003-live-audio-low-frequency-snr-underread.md` (repo root), same commit as this correction.

---

*Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>*
*Claude-Session: https://claude.ai/code/session_01NseChs8GHWxH7dJ8L9pwC2*
