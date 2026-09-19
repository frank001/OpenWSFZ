# `DENSITY-REMEDY` Stage 1: decoder parameter table, read-only page, and a runtime suppression-ramp setter (shim `20260054`)

**Date:** 2026-09-19
**Prepared by:** QA
**Audience:** Developer (to execute), Captain (go before pickup; push sign-off, HK-011; merge sign-off, HK-010)
**Authorised by:** Architect spec `DENSITY-REMEDY` §4 and §10.2 (`arch/density` `563e08ed`), quoting the Captain's ruling of 2026-09-19: *"…2. hold after stage 1 lands, include in the change all decoder params readout and create a setting page in the gui to display them all, readonly."* Stage 0 (the live regime census) is accepted (§11).

# 🛑⏸️ STATUS: DRAFT — HELD. NOT HANDED TO THE DEVELOPER.

**QA may draft this; QA may not hand it over until the Captain gives his go after Stage 0** (§10.1; HK-030, an unblocked step can still sit behind an earlier stop). Nothing below is to be started by a Developer session until QA tells the Captain it is ready and the Captain says go. Stages 2 and 3 of the arm are **not** authorised.

**Branch (to build on):** a new branch off **`origin/decoding_improvement`** (tip `6cb98c52` when drafted). PR target is `decoding_improvement`, **not** `main`. HK-029: this has `src/`, `native/` and `web/` diffs, so **no direct push**.

---

## 0. What this is and why

`DENSITY-P1` and `DENSITY-REMEDY` Stage 0 showed that a suppression-route remedy has two levers, the ramp's floor and its footprint, and both are baked into the native decoder with no way to read or vary them. Separately, the programme has three times cited results for a decoder that was **not** the one that produced them (`nhard` 60 vs 40; a "read back" that had no getter). The Captain asked for a **readout of every decoder parameter**, on a **read-only GUI page**. This task delivers that, plus the one native piece Stage 2 (a bench sweep) will need: a runtime setter/getter for the ramp.

**It is not a tuning.** No default moves, no constant changes value, live behaviour does not change, and decode output at defaults is **byte-identical** (gate S1-a).

## 1. Precise scope

**The authoritative artefacts are the OpenSpec change and its task list, not this summary.** They are on the local branch `qa/decoder-param-readout-draft` (worktrees share refs), and are already `openspec validate --strict` clean:

```
openspec/changes/decoder-param-readout/{proposal.md, design.md, tasks.md, specs/ft8lib-interop/spec.md, specs/decoder-param-readout/spec.md}
```

Bring them into your branch with `git checkout qa/decoder-param-readout-draft -- openspec/changes/decoder-param-readout dev-tasks/2026-09-19-density-remedy-stage1-decoder-param-readout.md` **as part of the implementing PR** (see §5.1). In one paragraph each:

1. **Native.** `ft8_get_decoder_params` (one table of `name · value · default · kind`, built from a single X-macro list); `ft8_set_supp_params` / `ft8_get_supp_params` (`snr_min`, `snr_max`, `side_weight`; defaults `-5 / 15 / 1.0`; no upper bound on `snr_max`); the two passband literals hoisted to `K_PASSBAND_MIN_HZ` / `_MAX_HZ` at both call sites; `suppress_candidate_tiles` reads the runtime ramp and applies `factor_side = 1 − side_weight·(1 − factor)` to the ±1 bins, **using `factor` itself when `side_weight == 1.0f`**.
2. **Managed.** `IFt8NativeInterop` gains **one read-only** method for the table. **No managed setter, no `DllImport` for the two suppression exports.**
3. **Daemon.** `GET /api/v1/decoder/params`: native values read **on every request**, never from `app.json`; `405` on any mutating verb; `503` (never an empty table) if the native library will not load.
4. **GUI.** `web/decoder-params.html`: grouped runtime vs compile-time, `name · value · default`, shim version, **no editable control**. One link from `settings.html`; the `#advanced-decoder-settings` block is **byte-for-byte unchanged**.
5. **Shim version `20260054`**, three platform binaries, `libft8.version.txt`, `BUILD.md`, `ExpectedShimVersion`, and a direct edit of the ABI requirement in `openspec/specs/ft8lib-interop/spec.md`.

## 2. 🔴 Decisions that must be made BEFORE pickup

| # | question | who | default if silent |
|---|---|---|---|
| **D4** | Hoist and report the bare OSD depth `2` in `native/ft8_lib_build/patched/ft8/decode.c:666`? | Architect / Captain | **Do not start**; ask. QA recommends **yes** (one more edited line in a vendored file, arithmetic-identical, caught by S1-a) |
| — | The Captain's go for Stage 1 itself | Captain | **held** |

## 3. Builds

- **Windows:** `native/ft8_lib_build/rebuild_shim.bat`. The `FT8_ROOT` hard-coding landmine was fixed by PR #179 and is in `decoding_improvement`. **Confirm the DLL was built from your tree.** The script overwrites the tracked `libft8.dll` in place: **keep a copy of the previous one** (`50e94e7d73e33050ac37145ac675ad467415324b9cbc5183dc47f3e361829bb7`); QA needs both. Record the **new SHA-256**. The MSVC link is not byte-reproducible: **do not rebuild if you want the pinned hash.**
- **Linux / macOS:** CI. Do not cross-build, and **do not commit the `.so` / `.dylib` by hand**. `commit-native-binaries` owns them.
- 🔴 **`dumpbin /exports`: 26 → 29**, none removed. **Three** new `/EXPORT:` lines in `rebuild_shim.bat`. Linux exports by default visibility, so a missing Windows export builds clean on Linux and fails only at P/Invoke.

## 4. Tests

Listed in `tasks.md` §5 (`FR-067 … FR-070`, each `DisplayName` starting `FR-0xx:`, gate G3). Run the full suite and report the tally. `Category=AwgnFpReplay` is CI-excluded; its stale SHA-pinned tests are not a new hazard. **Treat any decode-output test failure as a real finding.**

## 5. Rigour controls

1. 🔴 **The proposal declares `**User-facing:** yes`, so gate G9b requires a `VERSION` bump (`0.49` → `0.50`) in the same PR.** The proposal must **first appear in that PR**, together with the bump and the `README.md` / `REQUIREMENTS.md` anchor sentences (G9a). Verify on your branch after committing (the script reads from git): `python tools/check_version_bump.py origin/decoding_improvement` must exit 0. **Do not land the proposal on any branch that can reach `main` without the bump.**
2. **The complete list of edits to existing native code** is: (a) the two passband literals → constants; (b) *if D4 accepted* the OSD-depth literal → macro; (c) the runtime ramp and side-weight in `suppress_candidate_tiles`. Everything else is additive. **Anything else that touches an existing line: stop and report.**
3. **Byte-identical decode output at defaults.** With `side_weight == 1.0f` use `factor` itself; `1 − (1 − f)` is not bitwise `f`.
4. **The table must be truthful by construction:** each row reads the macro or variable the decode path reads, not a copy.
5. **`snr_max` has no upper bound** beyond `> snr_min` and finite (the Stage 2 bench sweeps it above `+15`).
6. **HK-005:** the *before* screenshot is one of the first tasks (`tasks.md` 0.4); the *after* is a verification task. **HK-007:** Playwright via `npx --yes playwright`.
7. **NFR-021:** synthetic `Q`-prefix callsigns only in tests and fixtures.
8. `tools/pre_merge_check.py` is **not** in your checklist (HK-000/HK-006). QA runs it at review.

## 6. Scope guardrails — what this is NOT

- **Not a tuning.** No default, no constant value, no ramp constant moves. (`K_SOFT_SUPP_SNR_MIN_DB` / `MAX_DB` stay as the defaults of the runtime values.)
- **Not a managed setter** for the suppression parameters. The live app never calls it.
- **Not a change to the existing editable Advanced Decoder Settings section.**
- **Not a change to the live app's behaviour**, or any `app.json` field.
- **Not Stage 2 or 3** (the bench sweep and live-replay pricing): those are QA's, not authorised, and Stage 2's grid needs an `snr_max` axis first (Architect §11.3). **Nothing here waits on that**: `ft8_set_supp_params` already takes `snr_max`.
- **Not a push or a merge.** Captain sign-off first (HK-011, HK-010).

## 7. Completion record — paste, verbatim, into your reply

1. `git diff --stat origin/decoding_improvement`, and the diff of `ft8_shim.c` **restricted to existing lines**, showing only the §5.2 edits.
2. The **new DLL SHA-256**, and the previous `50e94e7d…829bb7` confirmed from `git show`.
3. `dumpbin /exports`: the three new symbols and **every previously exported one** (26 → 29).
4. The §0.2 uniqueness-check output and the shim version you took.
5. The output of `python tools/check_version_bump.py origin/decoding_improvement` (must be a pass).
6. Test tally (`FR-067…070` by name) and the full-suite result. CI status on **all three platforms** once pushed.
7. Both screenshots (HK-005) and the Playwright run (HK-007).
8. Any deviation from this document, stated plainly.

## 8. What QA does next (not your job, stated so nothing surprises you)

Acceptance, all mechanical, with the bars fixed **before** any run (the `DENSITY-P1` Stage 1 precedent):

| gate | check |
|---|---|
| **S1-a regression** | `DENSITY-P1` Stage 1's pre-registered replay set, `20260053` vs the new DLL at defaults: decode results **byte-identical**, mechanically diffed |
| **S1-b set/get** | a valid triple reads back exactly; each of the four invalid classes returns `-1` **and** leaves the prior triple unchanged |
| **S1-c floor plumbed** | `DENSITY-P1` primary cell Δ12 X3, N = 20: at `(−25, 15, 1)` E's **recorded applied factor** equals `1 − clamp((snr_db + 25)/40)` within `1e-6` and differs from its default-run value |
| **S1-d side weight plumbed** | E+15 Δ6.25, N = 20: (i) F's pass-1 probe LLR vector differs between `s = 1` and `s = 0` in ≥ 19/20 trials; (ii) **null:** with `(−5, 15, 1.0)` set explicitly, bit-identical to a run where the setter was never called, 20/20 |
| **S1-e build** | CI green on all three platforms |
| **S1-f completeness** | the grep-derived set of `#define K_*` the decode path reads and every `ft8_set_*` setter ⊆ the table's names; each compile-time value equals its `#define` |
| **S1-g round-trip** | after `ft8_set_decode_params(7, 0.15, 50)` and `ft8_set_supp_params(−10, 15, 0.5)` the table reports exactly those values; after resetting to defaults, the defaults |
| **S1-h GUI** | Playwright: the page lists every table entry with the API's value, has no editable control, and a changed `app.json` decoder value appears on the page after save |

## 9. References

| Reference | Content |
|---|---|
| `qa/rr-study/2026-09-19-1228-architect-to-qa-spec-density-remedy-suppression.md` §4, §10.2, §11 (`arch/density` `563e08ed`) | The binding scope, and the Captain's quoted ruling |
| `qa/rr-study/2026-09-19-1247-qa-to-architect-density-remedy-stage0-result.md` | Stage 0: why both levers stay in |
| `openspec/changes/decoder-param-readout/` (branch `qa/decoder-param-readout-draft`) | The authoritative change: proposal, design D1–D11, tasks, two spec deltas |
| `dev-tasks/2026-09-19-density-p1-stage1-pass1-probe-export.md` | The last shim-bump task; same registration sites |
| `src/OpenWSFZ.Ft8/Native/ft8_shim.c` (`suppress_candidate_tiles`, the `#define K_*` block, `s_k_min_score_pass2` … `s_osd_nhard_max`) | The code this touches |
| `native/ft8_lib_build/patched/ft8/decode.c:666` | The OSD-depth literal (decision D4) |

---

*Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>*
