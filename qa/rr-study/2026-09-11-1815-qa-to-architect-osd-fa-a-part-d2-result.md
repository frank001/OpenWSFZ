# `OSD-FA-A` Part D, re-run on `FP-FLOOR-LIVE-2` — result: **VOID (ROW 0e fails even corrected)** — reporting and escalating, not refusing

QA, 2026-09-11 18:15Z (`date -u`, HK-017). Per the Architect's Part D ruling
(`2026-09-11-1652-architect-osd-fa-a-part-d-ruling.md`, `arch/osd-fa-a` `4998b2a`, read via
`git show` and verified before acting) — re-running Part D on the corpus Amendment 1 §3 actually
specifies, with ROW 0e as corrected in the ruling's §3.1.

**Headline: `D`'s row is VOID.** ROW 0e, corrected, fails on both readings: `77.1%` full-population,
`78.5%` on the spec's own 200-decode subset — both `< 0.90`. Per base §4/ruling §3.1, this **VOIDs
Part D only**; it does not touch Parts A/B/C. `U` itself is computed (`1.495%`, CI `[1.256%,
1.744%]`) but is **not citable as Part D's result and not a bound on E3** while ROW 0e fails.

🔴 **Per the ruling's own instruction (§3.2): "If fidelity fails and the failures concentrate in
one category, report it and escalate. Do not refuse."** That is exactly what happened — see §3.
This report does not attempt an HK-025 refusal; the ruling already closed that path for the
hash-packing ground, and no other ground is being offered here.

---

## 1. HK-020 — critical config, checked against the AMENDMENT, not the base spec

| config | value used | source |
|---|---|---|
| Corpus | `artefacts/20260908_live_run_1827-fp-floor-live-2/` | Amendment 1 §3, `arch/osd-fa-a` `bb26778` |
| Span | `[260908_193645, 260909_172200)` | Amendment 1 §3 (Amendment 3's own frozen boundary) |
| Decode source | OpenWSFZ's own `openwsfz/ALL.TXT` (production-emitted) | Amendment 1 §3 |
| Extraction offset | reported `dt`, **no** `+0.16s` | Part D ruling §2 (struck base §2.4 item 1 / §4.1 and Amendment 1 §3's own repeat of it) |
| ROW 0e definition | 200 seeded eligible (no `<`) decodes, `-1` counts as fail, `≥0.90` bar | Part D ruling §3.1 |
| Sample size | 1,000 cycles, seeded, sorted at construction | base §2.4 hazard 2 / §4.1 |
| PCM convention | `read_wav` + `normalise_rms(0.20)` | this session's own August-corpus disclosure, carried forward per the ruling §4's instruction to disclose it again here |
| REF for corroboration split | WSJT-X #1 (`FT991A`), same-cycle, `|Δf|≤3Hz`, wildcard matching | `FP-FLOOR-LIVE-2` Part B / Amendment 1 (`fp_floor_live_2_part_b.py`, reused) |

## 2. Population and method

**Population:** 5,221 archived cycle-audio WAVs in-span (`cycle-audio/`, non-`_2` files — the `_2`
duplicate-pipeline defect from `contents.md` occurred 18:28:30–18:31:01, entirely before this span
starts). This matches `F-001` L3's own **5,222**-cycle figure for the identical span almost
exactly (off by one, plausibly a boundary-inclusivity artefact, not chased further). **Sampled
population is every archived cycle, not only the ~4,099 that happen to carry ≥1 live decode** — a
cycle with zero decodes contributes `0/0` to `U` either way, but sampling only from decode-bearing
cycles would under-represent the true cycle population and mismatch `E3`'s own population
definition (caught before sampling, disclosed here rather than found later).

**Decode count check:** `57,947` dial-filtered (`14.074`) decodes in-span, against `FP-FLOOR-LIVE-2`
Part B's own **`57,969`** (`fp_floor_live_2_part_b.load`, re-run directly this session for the
comparison). **Gap: 22 decodes (0.038%).** Part B applies no upper-bound cutoff (reads to the
corpus's natural EOF); this leg's exclusive `< 260909_172200` cutoff (Amendment 1 §3's own literal
span) drops whatever landed in the last few seconds before that instant. Disclosed, not chased —
negligible against a 1,000-cycle sample.

**Method:** identical to the August-corpus run (`part_d.py`, reused — HK-018), parameterised to the
new corpus (`part_d2.py`, new): extract LLRs at `(freq_hz, dt_s)` (no offset), `ft8_ldpc_decode_llrs
(max_iters=50, osd_depth=2)`, record `out_path`. 1,000 cycles sampled (seed
`compute_seed("OSD-FA-A-PART-D2", 0, 0) = 1849361851`), **10,888 decodes**.

## 3. ROW 0e, corrected (ruling §3.1) — FAILS, and the failure still concentrates by category

```
Eligible (no '<' token)        = 10,205 / 10,888
200-decode subset (seeded)     = 200
Pass = converges AND payload == true_codeword(text); -1 counts as fail.

Full-population rate           = 7,864 / 10,205 = 77.06%
200-decode subset rate         =   157 /   200   = 78.5%
Bar                            = 0.90
VERDICT: FAILS both readings -> Part D VOID
```

**Per-category breakdown (structural, no message text printed — same five categories as the
August-corpus report, kept per the ruling's own instruction):**

| category | pass | total | rate |
|---|---:|---:|---:|
| `sign_off` (`RR73`/`73`) | 448 | 1,352 | **33.1%** |
| `other` | 2,854 | 3,480 | 82.0% |
| `CQ` | 2,611 | 3,100 | 84.2% |
| `report_plain` | 1,307 | 1,532 | 85.3% |
| `report_R` | 644 | 741 | 86.9% |

**The concentration persists after removing the hash-packing explanation.** `eligible` already
excludes every decode whose production text carries a `<` token — the August corpus's diagnosed
mechanism cannot apply here by construction (the ruling's own point). `sign_off` still fails at
**33.1%**, against **82–87%** for every other category. **This is now reported as an unexplained
finding, per the ruling's explicit instruction, not investigated further this session** — the
ruling itself names two unconfirmed candidates (pass-2 post-tile-suppression decodes a
waterfall-reading probe would not reproduce; something in how the fidelity comparison itself is
implemented). Escalating rather than diagnosing further: this needs the Architect's own read,
possibly with source access this session doesn't have reason to duplicate.

## 4. Descriptive (never gated, base §3.2/ruling §3.2)

```
U = 140 / 9,362 = 1.4954%
95% CI (cycle-clustered bootstrap, 2,000 resamples): [1.256%, 1.744%]
n_neither (out_path==-1) = 1,526
```

**`U` split by fidelity verdict (ruling §3 table, reproduced on the new corpus):**

| group | n (`bp_or_osd`) | `osd` | `U` |
|---|---:|---:|---:|
| fidelity pass | 7,864 | 79 | **1.005%** |
| fail / unverifiable / `-1` | 1,498 | 61 | **4.072%** |
| **worst case** (every non-pass counted as OSD) | 9,362 | — | **16.84%**, above the 10% bar |

Same direction as the August corpus (failed-fidelity decodes take the OSD path several times more
often than passed ones) — consistent with the ruling's own reading that this is not what a
comparator error on correctly-located extractions would produce.

**`U` by `REF`-corroboration (Amendment 1 §3's own descriptive split, WSJT-X #1, same-cycle,
`|Δf|≤3Hz`, wildcard mandatory — `fp_floor_live_2_part_b`'s `load`/matching logic reused, not
reimplemented):**

| group | n | `osd` | `U` |
|---|---:|---:|---:|
| corroborated by `REF` | 9,192 | 33 | **0.359%** |
| **not** corroborated | 170 | 107 | **62.94%** |

**`U` by reported SNR (Amendment 1 §3's other split):**

| group | n | `osd` | `U` |
|---|---:|---:|---:|
| `snr ≤ −24` | 69 | 23 | **33.33%** |
| `snr > −24` | 9,293 | 117 | **1.259%** |

🔴 **Neither split is gated — both are exactly the kind of signal base §3.2 asks for as description,
not verdict.** The corroboration split in particular is striking (uncorroborated decodes are
~175× more likely to be OSD-path than corroborated ones) and bears directly on the E2 question this
whole arm exists to answer — but it is reported here as description under a VOID Part D, not as a
finding this session is drawing a conclusion from. Flagged for the Architect's own reading.

## 5. ROW 0a / 0d — clear

- **0a:** pin asserted in-run at construction on both legs (`6b2e16a6…4f85c`, shim `20260050`).
- **0d (Part D leg):** two independent processes (`D2a`, `D2b`), identical seeded 1,000-cycle
  sample, **`0/10,888`** per-decode records (path, fidelity, category, corroboration, snr) differ.

## 6. What this means, and what QA is NOT doing

**Part D is VOID.** Per base §4.2/ruling: this affects Part D only. It does **not** license citing
`U` (either corpus's figure) as a bound on `E2`, and it does not by itself block Parts A/B/C from
running — those have their own ROW 0 preconditions (0b, 0c) which this report has not yet reached.
🔴 **Whether a VOID Part D changes how Parts A/B may eventually be CITED (as opposed to whether they
may run) is the Architect's reading, not asserted here** — base §4.2's D1/D2/D3 rows each say
something about citability, and none of them is literally "VOID"; this is flagged as an open
question rather than resolved by assumption.

**Not investigating the sign-off mechanism further this session**, per the ruling's own instruction
to report and escalate rather than diagnose past what a smoke test already surfaces. **Not
proceeding to ROW 0b/0c/Parts A/B/C/E1/E2/E3 in this same report** — this is a second, unplanned
checkpoint (Part D needed a full re-run and produced a second unresolved finding), and stacking
further large legs on top without the Architect's read on §3's escalation risks compounding an
open question rather than resolving it.

## 7. NFR-021

`ALL.TXT` (OpenWSFZ and WSJT-X #1) carries real off-air callsigns. Message text held in memory only
— `true_codeword()` comparison, `wildcard_match()` corroboration matching, structural
categorisation (`.split()`/fixed-literal membership tests) — never printed, logged, or written.
Per-leg JSON (`artefacts/2026-09-11-osd-fa-a-part-d2/`, blanket-gitignored) carries `path`,
`fidelity`, `has_bracket`, `category`, `corroborated` (bool), `snr` (integer) and cycle/decode
indices — no text field. Scanned with `nfr021_pre_merge_scan.py` before commit.
