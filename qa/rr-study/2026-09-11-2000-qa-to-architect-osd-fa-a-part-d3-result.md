# `OSD-FA-A` Part D, third run — result: **`D1` FIRES** (`U = 1.644%`, CI `[1.414%, 1.876%]`) — `ROW 0e` READABLE at `93.5%`

QA, 2026-09-11 20:00Z (`date -u`, HK-017). Per the Architect's Part D2 ruling
(`2026-09-11-1918-architect-osd-fa-a-part-d2-ruling.md`, `arch/osd-fa-a` `68c6a07`) §3.1/§3.3/§3.4,
following the bit-field diagnostic (`2026-09-11-1935-...-mechanism-2-diagnostic.md`) that decided
sign-off's exclusion.

**Headline: `D1` fires.** `ROW 0e` is **readable** for the first time across three attempts:
`93.5%` on the 200-decode subset (and `93.5%` full-population), clearing the `0.90` bar. `U =
140/8,517 = 1.644%`, cycle-clustered bootstrap CI `[1.414%, 1.876%]` — `CI_hi` sits **~5.3×** inside
the `10%` bar. **The OSD mechanism for `E2` is bounded out on live `FP-FLOOR-LIVE-2` data.** Parts
A/B, whenever run, characterise a minor path and may not be cited as an explanation of D-001.

---

## 1. HK-020 — critical config, per the ruling §3.1/§3.4

| config | value | source |
|---|---|---|
| Corpus/span | `FP-FLOOR-LIVE-2`, `[260908_193645, 260909_172200)` | Amendment 1 §3 (unchanged) |
| Positions | `artefacts/2026-09-10-f001-l3-live-measurement/subject_20260050.json` — SHA re-asserted in-run (`6b2e16a6…4f85c`, matches both the DLL pin and the replay JSON's own recorded `dll_sha256`) | Part D2 ruling §3.1 |
| Matching | same cycle, `wildcard_match`, `\|Δf\| ≤ 3Hz`; closest-frequency tiebreak, disclosed | ruling §3.1 |
| Reproduction bar | `≥ 0.90` (else VOID) | ruling §3.1, "the E3-0 rule reused" |
| `ROW 0e` eligibility | no `<` token **and category ≠ `sign_off`** | ruling §3.3, decided by the bit-field diagnostic |
| `ROW 0e` bar/subset | `200` seeded, `-1` counts as fail, `≥0.90` | Part D ruling §3.1 (unchanged) |
| PCM | `read_wav` + `normalise_rms(0.20)` | unchanged, disclosed again |

## 2. Reproduction (the E3-0 rule, reused)

```
n_live_total (sampled cycles' live decodes) = 11,615
n_matched (found in the replay, same cycle, wildcard + tolerance) = 11,551
reproduction share = 99.45%  >= 0.90  -> NOT VOID on this ground
```

1,000 cycles sampled (fresh seed `compute_seed("OSD-FA-A-PART-D3",0,0) = 1310442853` — a new seed
for a genuinely new method, not the Part D2 sample), from the same 5,221-cycle archived population.

## 3. `ROW 0e`, corrected + sign-off excluded — READABLE

```
Eligible (matched, no '<', category != sign_off) = 9,352
200-decode subset (seeded)                        = 200
Pass = converges (path in {0,1}) AND payload == true_codeword(text); -1 counts as fail.

Full-population rate  = 93.51%
200-subset rate       = 93.5%
Bar                   = 0.90
VERDICT: READABLE -> Part D's row may be stated
```

## 4. `D`'s row

```
U = osd / (bp+osd) = 140 / 8,517 = 1.644%
95% CI (cycle-clustered bootstrap, 2,000 resamples): [1.414%, 1.876%]
n_neither (out_path==-1, among matched decodes) = 419
```

`CI_hi = 1.876% < 10%` ⇒ **`D1`**. Margin: `10% − 1.876% = 8.12pp`, about **5.3×** the bar's own
distance from zero-CI, and no longer resting on a refused or borderline `ROW 0e` — this is a clean
pass at `93.5%`, not a margin argument standing in for an unresolved precondition.

**Consequence, per base §4.2 (`D1`):** the OSD mechanism for E2 is bounded out on this live
population. Parts A/B, whenever run, characterise a minor path and **may not be cited as an
explanation of D-001** — synthetic-only characterisation.

**Prediction scoring suspended** for this leg, per the ruling §4 (the Architect saw this corpus's
own per-decode records while diagnosing Mechanisms 1/2, de-blinding `D`'s prediction).

## 5. ROW 0a/0d — clear

- **0a:** pin asserted in-run (DLL and replay JSON's own recorded SHA both `6b2e16a6…4f85c`).
- **0d:** two independent processes (`D3a`, `D3b`), identical sample, **`0/11,615`** per-decode
  records (matched, path, fidelity, category, corroboration, snr) differ.

## 6. Descriptive (never gated)

**`U` by `REF`-corroboration** (WSJT-X #1, same matcher as Part D2):

| group | n | `osd` | `U` |
|---|---:|---:|---:|
| corroborated | 10,890 | 10 | **0.092%** |
| not corroborated | 242 | 173 | **71.49%** |

Even sharper than Part D2's own void-leg figure (which was `0.36%` vs `62.9%`) — now measured on a
readable leg. **Still not a finding**, per the Architect's own §4 framing: corroboration bounds
genuine loss from below, and only Part A/E2's oracle can separate a genuine weak signal WSJT-X
missed from a false accept. Flagged, not concluded from.

**`U` by SNR:**

| group | n | `osd` | `U` |
|---|---:|---:|---:|
| `snr ≤ −24` | 126 | 43 | **34.13%** |
| `snr > −24` | 11,006 | 140 | **1.272%** |

## 7. NFR-021

Message text held in memory only (`wildcard_match`, `true_codeword`, category checks) — never
printed, logged, or written. Per-leg JSON (`artefacts/2026-09-11-osd-fa-a-part-d3/`,
blanket-gitignored) carries counts/booleans/indices only. Scanned with `nfr021_pre_merge_scan.py`
before commit.

## 8. Next

Per the ruling §5 order: `ROW 0b/0c → Part A → B → C → E1 → E2 → E3`, HK-020 per leg. Given the
size of what remains and the depth this Part D arc already took (three runs, two located
instrument mechanisms), reporting this milestone now rather than continuing directly into Part A
in the same report.
