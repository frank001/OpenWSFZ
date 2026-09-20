# `DENSITY-REMEDY` Stage 1 acceptance — **S1-a / b / c / d / f(i) / g / h PASS; S1-f(ii) mechanical PASS with ONE item for the Architect; S1-e (CI ×3) NOT RUN** — the build is a faithful read-only readout; the table's one visible gap is a judgment call

QA, 2026-09-20 12:15Z (`date -u`, HK-017). Build under test: Developer commit `257070d8` (`feat/decoder-param-readout`, shim `20260054`, **UNPUSHED**), change `decoder-param-readout`, per dev-task `dev-tasks/2026-09-19-density-remedy-stage1-decoder-param-readout.md` §8 and Architect spec `DENSITY-REMEDY` §4/§10.2/§12. Acceptance harness `qa/rr-study/density-remedy/stage1_accept_readout.py`, committed **before any verdict run** as `93acbf84` with every bar in its docstring. 🛑 **Stage 2 has NOT started and needs its own Captain go.** 🛑 **Nothing is pushed or merged** (HK-011, HK-033, HK-010).

**Headline: on the pre-registered replay set (DENSITY-P1 Stage 1's, unchanged: 500 calls) the new DLL's decode output is byte-identical to `20260053` at the live `nhard` 40, at the shim's default `nhard` 60, and with the setter called explicitly at its defaults.** ROW 0 is silent, including a control (0d2) proving the set *can* tell a changed side weight or floor from the default. The setter/getter, the floor and the side weight are each plumbed; the table has 30 rows that equal their `#define`s evaluated from source; the page lists every row and can change nothing. **One open item:** the noise-floor median (`cum * 2 >= total`) is a literal the audit's own lister saw and neither the table nor the page mentions. Whether it is a *tuning* literal is the Architect's call (D12).

---

## 1. HK-020 — critical config, and HK-022 — what was pinned and what was NOT filtered

| item | value |
|---|---|
| Binary pin, **OLD** | `50e94e7d73e33050ac37145ac675ad467415324b9cbc5183dc47f3e361829bb7`, shim `20260053`, `git show 6cb98c52d7f0c8b150e32c254f9740a97c909d00:…/libft8.dll` (= `origin/decoding_improvement`), SHA-checked in every run (ROW 0a) |
| Binary pin, **NEW** | `38a21f840b00af146348c166786cb54e178cd2201c5ed4dba3016a4c589a1cba`, shim `20260054`, `git show 257070d8707e4aa4e3a95362b5b8a674d862262a:…/libft8.dll`, SHA-checked in every run; the scratch daemon's own `libft8.dll` was `sha256sum`-checked to the same value |
| Working-tree DLL | **never used** |
| Test filter (Python harness) | **none**: nothing can be filtered out silently |
| Test filter (`dotnet test`) | Ft8: `FullyQualifiedName~DecoderParamReadoutTests\|FullyQualifiedName~DensityP1ProbeTapTests` → **56 passed / 0 failed / 0 skipped**. Web: `FullyQualifiedName~DecoderParams` → **19 passed / 0 failed / 0 skipped**. Both projects built with **0 Warning(s)**. 🛑 This is **not** the full-suite tally (the Developer's 1,537 / 0 is theirs; QA did not re-run it — CI is the gate, HK-006) |
| Params | `ft8_set_decode_params(10, 0.10, 40)` explicit in every run (live `nhard`); the `nh60` runs set `(10, 0.10, 60)` |
| Isolation | one **process** per (DLL, tag, leg); 22 jobs, 8 at a time |
| Replay set | **SYNTH** 300 calls (`DENSITY-MECH` 12 cells × 25 trials, E present); **REAL** 200 live cycles (`20260908_live_run_1827-fp-floor-live-2/cycle-audio`, sorted, every 27th) |

## 2. ROW 0 — all silent

| row | check | result |
|---|---|---|
| **0a** | both SHA pins and both `ft8_lib_version_check` values, every run | ✅ |
| **0b** | determinism: NEW `nh40` run #1 vs #2, byte-identical, both legs | ✅ |
| **0c** | non-vacuity: REAL decodes ≥ 1000; armed REAL ≥ 50 % cycles with ≥ 1 suppression record and ≥ 10 pass-1 decodes | ✅ **2,329** decodes; **157/200** cycles with records; **70** pass-1 decodes |
| **0d** | instrument can say NO (a): `k_min_score_pass2` 30 changes the stream | ✅ differs (first differing line index 1, 0-based) |
| **0d2** | instrument can say NO (b), **on the regressed region itself**: `(−5,15,0.0)` and `(−25,15,1.0)` each change the stream | ✅ **145/200** and **157/200** REAL calls differ (first differing line index 1) |
| **0e** | coverage: SYNTH 300, REAL ≥ 190 in every run | ✅ |
| **c-Q** | S1-c: ≥ 15 trials with E recorded in both runs; E's pass-0 SNR bit-identical between them | ✅ 20/20 |
| **d-E** | S1-d: E really suppressed (≥ 15/20 records, median factor ≤ 0.05) | ✅ 20/20, median **0.0** |

## 3. Verdicts

| gate | predicate | result |
|---|---|---|
| **S1-a** | canon(OLD) = canon(NEW), byte-identical | ✅ **PASS**, all four sub-gates, both legs. **.1** `nh40`: SYNTH `33d5640188851009`, REAL `1bf6deb97821aec5`. **.2** `ft8_extract_llrs_at` bits (the *second* passband site): SYNTH `addc8f01264e8dff`, REAL `0a6c5a1d1cb1cf19`. **.3** `nh60`: SYNTH `861345032e4efcee`, REAL `d27bc18c1a7a67f9`. **.4** setter called explicitly at `(−5,15,1)`: same digests as .1 |
| **S1-b** | 5 valid triples read back bit-exact (incl. `snr_max` `3.0e38`); 17 invalid calls (9 non-finite, 4 `min ≥ max`, 2 `side < 0`, 2 `side > 1`) each `-1` **and** prior triple unchanged; `get(NULL)` `-1` | ✅ **PASS** |
| **S1-c** | floor plumbed: primary Δ12 X+3, N = 20, `(−25,15,1)` | ✅ **PASS**. `|factor − (1−clamp((snr+25)/40))|` max **2.4e-8** (bar 1e-6); factor differs from the default run by **≥ 0.463** (min 0.4636) in 20/20 (e.g. E at −4.20 dB: default **0.960**, floor **0.480**) |
| **S1-d** | side weight plumbed: E+15 Δ6.25, N = 20 | ✅ **PASS**. (i) F's pass-1 LLR differs `s=1` vs `s=0` **20/20** (bar ≥ 19); (ii) null: explicit `(−5,15,1)` ≡ never-called **20/20** (canon, P0, P1, records); (iii, QA-added) P0 unchanged by the setter **20/20** |
| **S1-f(i)** | all 17 `#define K_*` + `FT8_AP_LLR_HARD` + `HASH_TABLE_SIZE` + 5 `decode.c` constants are table rows and equal the `#define` **evaluated from source text** | ✅ **PASS**. Setters: `ft8_set_decode_params`, `ft8_set_supp_params` mapped to the 6 runtime rows; `ft8_set_ap_bits`, `ft8_set_probe` classed non-parameters |
| **S1-f(ii)** | bare literals, **mechanical part**: every `file:line` the page cites contains its literal; no `3.125` literal anywhere | ✅ **PASS**, **24** cites checked. **Judgment part: §5.1, for the Architect** |
| **S1-g** | 30 rows (6 + 24); sizing / short-capacity / canary; round-trip `(7, 0.15, 50)`, `(−10,15,0.5)`; reset; table read leaves decode unchanged | ✅ **PASS**. The last check runs in **two fresh processes** (the canonical line carries cumulative counters), `[decode]×3` vs `[decode, read×3]×3`: identical |
| **S1-h** | Playwright, isolated daemon (port 18761, throwaway config, built from `257070d8`) | ✅ **11/11**: 30/30 rows equal the API; **0** form controls / contenteditable / inline handlers; **0** non-GET requests, exactly one GET of the route; an `osdNhardMax` change through the existing config API shows on the page as `43` (default 60, "differs") and returns to `40` after restore; 0 console errors |
| **S1-e** | CI green on all three platforms | ⏳ **NOT RUN**: nothing is pushed |

**Cross-session corroboration:** the OLD `20260053` digests (`33d5640188851009`, `1bf6deb97821aec5`) are **identical** to those recorded at DENSITY-P1 Stage 1 on the same set, so the replay reproduces across sessions.

**Other mechanical checks (independent of the Developer's):** export table parsed from both PE files: **26 → 29, none removed, added = `ft8_get_decoder_params`, `ft8_get_supp_params`, `ft8_set_supp_params`**. No `DllImport`/`GetProcAddress` for the two suppression exports anywhere in `src/` (comments only). `check_version_bump.py origin/decoding_improvement` **exit 0** (proposal newly introduced, `0.49 → 0.50`, README and REQUIREMENTS anchors). `openspec validate decoder-param-readout --strict` **valid**. Native diff read in full: every edit to an existing line is a same-value macro substitution (or, in `suppress_candidate_tiles`, the runtime ramp with `factor` itself at `side_weight == 1.0f`), as the Developer's list states; S1-a is the proof.

## 4. What this acceptance could NOT have detected (HK-022 / HK-026)

1. 🔴 **Windows DLL only.** Linux/macOS are S1-e. The new C (`_Static_assert` inside a `do{}while(0)`, `isfinite`, `extern const` defined in `decode.c`, an X-macro table) has been compiled only by MSVC.
2. **A replay set is evidence, not proof.** 500 calls, 2,329 real decodes, 70 pass-1 decodes. The default path would have to differ on a call none of these 500 exercise. 0d2 shows the set is sensitive to the region, which is the strongest thing it can offer.
3. **One thread.** `_Thread_local` isolation and a concurrent set-during-decode were not tested (the header documents that contract).
4. **The 140-record cap is unexercised** (busiest cycle 27 pass-0 decodes), inherited from Stage 1.
5. **S1-f(ii) cannot decide what a *tuning* literal is**, and cannot see a design choice that has no numeric literal (§5.2).
6. **The table's truthfulness for the five `decode.c` constants** is checked **by value** (against the `#define`s), not by construction: the shim reads `const` mirrors that `decode.c` initialises from its own macros.
7. **S1-h ran on Chromium only**, one viewport, and does not test a `503` (that is the Developer's FR-069).
8. **Not re-run by me:** the full `dotnet test` (Developer's 1,537 / 0), the Developer's screenshots (HK-005), `pre_merge_check.py` (Captain's initiative only, HK-006).

## 5. Findings

### 5.1 🟡 For the Architect (D12): the noise-floor **median** is a literal the audit saw and the page omits

`ft8_shim.c:1146` (`compute_noise_floor`) and `:1392` (`compute_local_noise_floor_db`): `if (cum * 2 >= (uint32_t)total) { med = v; break; }`. The literal `2` **is the percentile** (50th). It is not on the page's "Not included" note, not in the table, and not in the Developer's ledger. The Developer's own lister shows both lines (`audit/lit_shim.txt` lines 50 and 63), so it was seen and not classified. It matters: the global median is `noise_raw`, **the value the suppression writes back**, and the local median is the SNR that both the report and the pass-1 ramp read (`all_supp_snrs`). Changing `2` to `3` changes decode results without changing the protocol, which is D12's definition.

**My reading, not a ruling (D12 reserves that to you):** it could be filed as the definition of "median" (structural), but the page already lists `0.5f`/`120.0f` from these very lines as *"Not included, with a doubt"*, so consistency says list this too. **If you rule it tuning-or-doubtful:** one more `<li data-literal="noise-floor-median">` on the page plus the count `6 → 7` in the FR-070 tests, **HTML and test only, no native rebuild, so every pin in this report survives**. **If you rule it structural:** the Developer records it as such in the audit report and nothing changes.

### 5.2 ℹ️ Scope note (no action required unless the Captain wants it)

The literal audit sees numbers. It cannot see **non-numeric design choices that move decode results**: the **Hann window** (`monitor.c`, `hann_i`; `WIN-A`/Hann is a standing prohibition), the **median** as the noise estimator, the sync-score metric's shape (the page does cover its neighbourhood), the `#if 1` `max4` symbol-LLR branch in `ft8_extract_symbol`, and the BP algorithm. The page's hint says "Every parameter of the native FT8 decoder"; "every *numeric* parameter" would be exact. Also outside the native library entirely: the managed post-decode layer (`IsPlausibleMessage`, text dedup), which `ALL.TXT` sits behind.

### 5.3 Ruling on the Developer's deviation: **T0a — CONFIRMED**

`DensityP1ProbeTapTests` T0a `== 20260053` → `>= 20260053`. I wrote the density-p1 dev-task; its registration list has **no T0a and no identity pin**, so the Developer's account of the provenance (it came from `3ad5504e`) is correct. The restatement is sound: a `==` pin on the build a test *was written for* cannot survive the next bump. What it guards, that the tap exists, is stated as that. The exact version is enforced where it belongs: `Ft8LibInterop`'s load-time ABI self-test (`ExpectedShimVersion`), and FR-067 has the same `>=` shape. **One caveat, minor:** these test classes P/Invoke `libft8.dll` directly rather than through `Ft8LibInterop`, so their own guard is the capability check; that is adequate, since FR-067 fails on a stale binary.

### 5.4 Minor notes (none blocks)

- `NormaliseFloatValue`'s doc says it "can never change a value's meaning, only its spelling". It changes the double by ~1.5e-9 (`0.10000000149011612 → 0.1`). Display-correct; **any programmatic comparison against the native table must use a tolerance** (as the Developer noted). One word in a comment.
- The page's audit-locations note is `file:line` at `257070d8`. All 24 verified here; any future edit to those files will move them.
- `ft8_set_supp_params` accepts `side_weight = -0.0f` (`-0.0 < 0.0f` is false). Harmless (behaves as 0), and not a spec violation.

## 6. Answers to the Developer's five questions

1. **S1-f(ii):** I grepped **without filtering 0 and 1** (own lister, committed as `qalit.py`) over `ft8_shim.c`, `decode.c`, `monitor.c`, `ldpc.c`. Every `0`/`1` site was read; the suppression footprint is the only tuning one, and it is now `K_SUPP_FOOTPRINT_HALF_BINS`. The `GFSK_*`, `monitor_resynth`, `db_power_sum` and `ft8_decode_multi_symbols` literals are **off the decode path** (`FT8_UNUSED_STATIC` / never called). `sync_refiner`/`coherent_llr` are linked but **not called from `ft8_decode_all`**. Your listing of `monitor.c` and `ldpc.c` is right and I agree with it. **One gap: §5.1.**
2. **T0a:** confirmed (§5.3).
3. **Extra hoists:** all verified token-identical in the diff (two OSD-depth sites, search limit, LLR target, time window, SNR offset, footprint, `DEFAULT_*`). Accepted; S1-a corroborates.
4. **Float widening:** handled; my harness compares float32-widened values exactly.
5. **Own replay set:** run (§3).

## 7. Status and what is needed

- ✅ **The native build is technically accepted** on S1-a, b, c, d, f(i), g, h.
- 🟡 **S1-f(ii) needs the Architect's ruling on §5.1.** Either outcome leaves the DLL and every pin here untouched.
- ⏳ **S1-e needs a push, which needs the Captain (HK-011).** Base and PR target: `decoding_improvement`, **not** `main`. 🔴 **G9b:** the proposal is `User-facing: yes`; this branch carries `0.49 → 0.50`, so it passes. **Never merge the draft branch `qa/decoder-param-readout-draft` on its own.**
- 🛑 **Merge needs the Captain's separate sign-off** (HK-010). QA has **not** run `pre_merge_check.py` (HK-006).
- 🛑 **Stage 2 is held** and needs its own Captain go. Nothing of Stage 2 was computed.
- **QA's own commits are LOCAL ONLY** (HK-033): `93acbf84`, `fd38d441`, `2e9fed6a` and this report, on `qa/density-remedy`. Two of them are harness fixes (§8).
- Artefacts: `artefacts/density-remedy-stage1-accept/` (gitignored). Committed: the harness, `qalit.py`, and `results/stage1_readout_{verdict,unit,s1h_playwright}.json` (counts and hashes only; NFR-021 scan: 0 callsign-shaped tokens).

## 8. Disclosures (things that went wrong on my side, HK-034: not hidden inside the deliverable)

- **`unit` failed twice on my own counter**, not on the build. The first failure (`Not included <li> count 7 != 6`) was the page's HTML *comment* quoting `data-status="not-included"`; my "fix" then wrote a literal backspace character into the regex (`\b` in a non-raw string) and read 0. Corrected and committed as `fd38d441` and `2e9fed6a`. **No bar, threshold or predicate changed**; the first-run output is kept as `unit_run1_pre_counter_fix.json`.
- I made a scratch checkout (`D:\qv`) and a scratch daemon on port 18761 for S1-h. The daemon's path and command line were verified before stopping it; the checkout and config dir are removed; `git worktree list` shows three again.

---

*Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>*
