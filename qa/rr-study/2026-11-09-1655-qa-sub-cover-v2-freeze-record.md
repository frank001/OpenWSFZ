# SUB-COVER v2 (#273): FREEZE RECORD (2026-11-09T16:54:15Z `date -u`), written BEFORE any O*v2 output exists

Spec: `arch/sub-coverage` `50149101` (v2 spec `f68f4ce9`: §0 to §5; Amendment 1 §6: QA's four (k) points adopted; v1's spec, Amendments 1-2 and ruling stand unless replaced by name). Authority: the Captain, 2026-11-09, "lets try a 2nd version". Size rule: the same 400 stored cycles of `20260925_2010`, no replay, no station, no second night, no pilot. `qa/same-chain` is local; the branch of `50149101` is the Architect's and not pushed yet.

## Frozen inputs and code

| item | value |
|---|---|
| Code (predicates are the code) | `sc_build2.py`, `sc_force2.py`, `sc_analyse2.py` in `qa/rr-study/gap-residual-run/`, QA commit `4e7e7297ba48c41fb6c4e4393a650b0a15d87265`. v1's `sc_build.py`, `sc_force.py`, `sc_analyse.py` are not changed (commit `aa8ceda5`) and are imported, not copied |
| Corpus | unchanged from v1: `selection400.json` `42e09239…`, `population.json` `c54b98b7…`, n_ref 12,124 (9,931 hits, 1,589 NR); stored buffers and natives as v1's freeze record |
| O*v1 result file (base of the incremental readout) | `_qa-scratch\sub-cover\forced_OSTAR.jsonl` SHA-256 `769e9038d97dde1ed8d1f0cdde0ab75ea010d8f6d1254bc40f1f78aa26204bd3` (11,520 records); `ostar.json` `1a207076717ce8b86ad0e72568366a46de7279063369e6d788798c8a67ad1415`; `sc_result.json` `810a972bde39050c2cbae58fba2d316a7c2e930b4b550dc88e3e8729cb927934` |
| DLL | `libft8.dll` SHA-256 `1ba8dc3d6a7d032764b3eaf65e7e5ef850c56b35569ad880b53d6708524db914` = pin (asserted by `gr_forced.load_dec` in every worker) |
| Bootstrap | B = 2000 cycle resamples, seed 20261109 (the spec's), paired indices |
| Frank-path check | `grep 'Users\\Frank'` over the three new files: 0 matches each |
| Hash state | `ft8_hash_state_save` / `restore` around every route-2 consistency check; route 1 is as v1 (not bracketed), so O-V1 holds |

## The matcher's tolerances (spec §1.2, from this night's own text-equal pairs; HK-038), `v2/calib.json` SHA-256 `4ba6996af790eeec56233c0130aa76837e3529699b2ac29998a26a96f5bde02e`

- **N = 9,931 pairs** (every decode v1's text matching paired: batch 1: 7,239; batch 2: 1,339; batch 3: 126; batch 4: 1,227). Our side uses its **native** freq/dt where stored (8,704 pairs); batch 4 has no stored natives and uses its published value (as v1's placement).
- **c = -0.640 s** (median of t_W - t). **tau_f = 2.0 Hz** and **tau_t = 0.080 s** (99th percentiles of |f_W - f| and |(t_W - c) - t|); medians 1.0 Hz and 0.040 s; maxima 4.0 Hz and 0.140 s.
- **STOP row: not fired** (tau_f 2.0 <= 6.25 Hz and tau_t 0.080 <= 0.16 s).

## A1.4: the true ceiling (`v2/ceiling.json`, SHA-256 `ccaec5363736b12b8764c389ceb0067c4853c80884b42508391d77f724440d28`)

Of the 112 rows of the #273-proper stratum, **77 have at least one route-1-rejected neighbour** (our text does not encode, no pre-filter): **0.635 pp of n_ref** (the spec's 0.92 pp counted all 112). It is **>= 0.40 pp, so BUILD-WORTH can fire.** No bar moves.

## Freeze-time results (before any O*v2 output)

- **Selftest PASS:** four synthetic Q-call texts round-trip encode -> payload (my port of `ExtractPayload77`, packed MSB-first into 10 bytes) -> `ft8_coherent_fallback_unpack`; a bracketed text does not encode (as the spec's reading of `message.c`).
- **O-V1: PASS, 400 of 400 cycles bit-identical** (route 2 OFF, pre-filter ON, against the stored O*v1 buffers). Counts equal v1's exactly (own 9,596, unencodable 537, fit-zero 251; by batch 6,876 / 1,342 / 128 / 1,250). **Disclosure:** the first run of `ov1` reported 0 of 400, because my comparison loaded the stored O*v1 buffer from the capture folder (`B.CAP`) instead of `sub-cover\cap\buffers`, where it lives (the old buffer read as missing). Found at once from the equal counts; fixed in the code (the same commit) and the comparison rerun by the new `ov1cmp` command on the buffers already written: 400 of 400. **No O*v2 output exists**: `v2\buffers` holds only the 400 `_OSTAR1V.f32` files. QA ledger Q43.
- **O-BUILD, O-REPRO:** unchanged from v1's freeze (both PASS on file, `freeze_figures.json` `049bb8ae…`).

## Registered rows and decision (as in `sc_analyse2.py`)

O-REPRO, O-BUILD, O-V1 (done), **O-CTRL** (v1's, +2.0 pp, paired), **O-ORC fails only if CI_lo > 5.44 %** among route-2 decodes (reported with its CI otherwise; if route 2 subtracts fewer than 50 decodes, reported, not gated), **O-ENC report-only** (figures read ">="). The row's "still decodes" uses the forced legs with the row's target text = the candidate's text with `<` `>` stripped (the text route 2 verified as the same transmission), substituted in memory in the worker for those rows only (`sc_force2.py orc`). Readout: G*v2, G273v2, strata, route counts, wrong payloads, and **delta-273p** = NR rows of the 112-row stratum decodable on O*v2 and NOT on O*v1 u R2 u R3, in pp of n_ref. **Decision on delta-273p:** BUILD-WORTH if CI_lo >= 0.40 pp; CLOSE if CI_hi < 0.25 pp; BETWEEN otherwise. Valid only if O-V1, O-CTRL, O-REPRO, O-BUILD pass and O-ORC does not fail. Candidate pool excludes any WSJT-X row text-matched to a DIFFERENT decode of ours (A1.3).

## Order from here

`sc_build2.py ostar2` (about 8 min) -> `sc_force2.py ostar2` (about 5 min) -> `sc_force2.py orc` (a few rows) -> `sc_analyse2.py main` -> a short report -> the Architect's ruling.
