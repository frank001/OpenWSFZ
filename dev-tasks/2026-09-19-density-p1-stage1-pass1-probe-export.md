# `DENSITY-P1` Stage 1: a pass-1 probe TAP inside `ft8_decode_all` (four diagnostic-only exports, shim `20260053`)

**Date:** 2026-09-19 (authored 10:14Z, `date -u`)
**Prepared by:** QA
**Audience:** Developer (to execute), Captain (pre-push sign-off, HK-011; merge sign-off, HK-010)
**Authorised by:** Architect pre-registration `DENSITY-P1` §1, on `origin/arch/density` at `ea69d8a3`
(`qa/rr-study/2026-09-18-1758-architect-to-qa-spec-density-pass1-probe.md`), and the **Captain's go of
2026-09-19: "proceed with DENSITY-P1"**. 🛑 QA reads that go as **Stage 1 only** (this task). The spec asks
for two separate go-aheads; **Stage 2 (the DIRTY/CLEAN diagnostic) needs its own**, and cannot run before
QA has accepted this build in any case.
**Status:** Proposed. Cleared for pickup. The Developer session does not push or merge on its own
initiative; the Captain signs off the push (HK-011) and the merge (HK-010).
**Branch:** a new branch off **`origin/decoding_improvement`** (tip `e5c79aa4` when QA checked; its
`src/` and `native/` are **identical to `main`'s**, verified with `git diff --stat` empty). PR target is
`decoding_improvement`, **not** `main`. HK-029: this has a `src/`/`native/` diff, so no direct push.

---

## 0. What this is and why

`DENSITY-LIVE` priced the crowded-victim loss at ≈ 4.30 pp. `DENSITY-MECH` A1 then showed production
recovers a crowded victim **only in pass 1**, so the loss lives inside pass 1. The next question is whether,
**after production's own pass-1 soft suppression of the stronger neighbour**, the victim's bits at its
position are CLEAN (pass 1's search misses a decodable signal) or still DIRTY (suppression leaves too much
of the neighbour, or damages the victim).

Answering it needs the waterfall **as production holds it at that instant**. `DENSITY-MECH` was voided
because its oracle was a separate code path that differed from production. So this task builds a **tap
inside the real `ft8_decode_all`**, not a re-implementation of anything. The tap reads; it does not act.

## 1. Precise scope

### 1.1 Four new diagnostic-only exports (`ft8_shim.c` / `ft8_shim.h`)

Names and types are QA's concrete resolution of the spec's "indicative" contract. Adjust names if you must,
**never the semantics**.

| export | semantics |
|---|---|
| `void ft8_set_probe(float freq_hz, float time_offset_s)` | **Arms** a thread-local probe for the **next** `ft8_decode_all` call on this thread. Position convention **identical** to `ft8_extract_llrs_at`: `freq_hz` is the tone-0 frequency, `time_offset_s` is the `dt + 0.16 s` origin, snapped to the same `K_FREQ_OSR`/`K_TIME_OSR` lattice. |
| `void ft8_clear_probe(void)` | Disarms, and also invalidates any captured data. |
| `int ft8_get_probe_llrs(int pass, float* out174)` | Copies the raw, **pre-normalisation** 174 LLRs captured at the probe position for `pass` (0 or 1). Returns `0` on success, and leaves `out174` untouched on any error. Distinct **non-zero codes** for: bad `pass` or NULL `out174`; the last call was **not armed** (never stale data); the pass **did not run** (the `num_decoded >= max_results` early `continue`); the resolved frequency bin fell **outside `[0, num_bins)`** (use `-3`, matching `ft8_extract_llrs_at`). |
| `int ft8_get_last_suppression(Ft8SuppressionRecord* out, int capacity)` | Copies up to `capacity` records for the last **armed** call and returns the **total** count (`n_all_supp`), following the `ft8_get_last_pass_counts` capacity convention. Returns `0` if the last call was not armed or pass 1 did not run. |

```c
typedef struct {
    int32_t freq_offset;   /* cand->freq_offset of the suppressed pass-0 decode */
    int32_t time_offset;   /* cand->time_offset */
    int32_t freq_sub;      /* cand->freq_sub   */
    int32_t time_sub;      /* cand->time_sub   */
    float   snr_db;        /* all_supp_snrs[i]: the UNROUNDED float `snr` (ft8_shim.c:1756), NOT r->snr */
    float   factor;        /* the attenuation factor suppress_candidate_tiles ACTUALLY APPLIED */
} Ft8SuppressionRecord;    /* 24 bytes, all 4-byte members, no padding */
```

🔴 **`factor` must be what was applied, not a re-derivation.** Change `suppress_candidate_tiles` from
`static void` to `static float` and `return factor;` at the end. Its **only** call site is
`ft8_shim.c:1594`, and production ignores the value. The tap records it. No other line of that function
changes. (This is the one deliberate edit to an existing production function; S1-a/S1-b prove it neutral.)

### 1.2 Placement — the tap, inside `ft8_decode_all`

Existing structure (verified by QA against `origin/main`, `ft8_shim.c:1583–1606`):

```
for pass in 0..K_MAX_PASSES-1:
    if (num_decoded >= max_results) { ...; continue; }          // early exit
    if (pass == 1) for i in supp: suppress_candidate_tiles(...)  // :1592-1594
    ...
    ncands = ftx_find_candidates(&mon.wf, ...)                   // :1604
```

1. **At entry**, after the `pcm_len != FT8_EXPECTED_SAMPLES` early return: consume the arm
   (`bool probe_active = tls_probe_armed; tls_probe_armed = false;`) and **reset every probe TLS field**
   (`valid[]`, statuses, suppression count) **on every call, armed or not**. A disarmed call must leave the
   probe reading as "not armed", never as stale data from an earlier armed call. These are writes to
   probe-own TLS only.
2. **In the pass loop, immediately after the `if (pass == 1) …suppress…` block and before
   `ftx_find_candidates`:** `if (probe_active) { capture(pass) }`. It runs for **both** passes, so pass 0
   sees the unsuppressed waterfall and pass 1 the suppressed one.
3. **`capture(pass)`** snaps the probe position with **the same arithmetic as `ft8_extract_llrs_at`**
   (`ft8_shim.c:1885–1898`, including the negative-`sub` normalisation), applies the same
   `freq_offset ∈ [0, num_bins)` guard, then calls `ftx_extract_likelihood_at(&mon.wf, …)` **into the
   probe's own TLS buffer**, and **only after the copy completes** sets `valid[pass]`. No
   `ftx_normalize_logl`.
   ⚠️ **Do not refactor `ft8_extract_llrs_at` to share this code.** The two are deliberately independent
   copies, so that acceptance check S1-c tests their agreement instead of assuming it.
4. **The suppression record:** inside the existing `pass == 1` loop, when `probe_active`, store
   `{freq_offset, time_offset, freq_sub, time_sub, all_supp_snrs[i], <returned factor>}` for each
   `i < n_all_supp`.
5. **SEH:** a fault mid-capture returns `-2` as today. Because `valid[]` is set only after the copy, a
   half-written buffer can never read as valid.

### 1.3 Registration sites (all of them; QA enumerated these, do not rely on a grep of your own)

| site | change |
|---|---|
| `src/OpenWSFZ.Ft8/Native/ft8_shim.h` | prototypes + `Ft8SuppressionRecord`; `#define FT8_SHIM_VERSION 20260053`; a changelog entry in the file's existing style |
| `native/ft8_lib_build/rebuild_shim.bat` | four new `/EXPORT:` lines, next to `ft8_ldpc_decode_llrs` (`:171`) |
| `src/OpenWSFZ.Ft8/Native/BUILD.md` | mirror the `/EXPORT:` list (`:169`) and the export note |
| `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt` | a new `=== CURRENT: … (FT8_SHIM_VERSION 20260053) ===` entry **with the new DLL's SHA-256** |
| `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs` | `ExpectedShimVersion` `20260051` → `20260053` (`:444`); add a `<remarks>` entry stating these exports are diagnostic-only with **no `IFt8NativeInterop` binding**, mirroring the B4 entry at `:352` |
| `openspec/specs/ft8lib-interop/spec.md:49` | the `SHALL be` constant → `20260053`, plus one history entry (as PB140-ship did) |
| Linux (`build_linux.sh`) | **nothing.** `gcc -shared` has default visibility and no export list; CI prints `nm -D … \| grep ft8_` |
| macOS | **nothing.** `macos-latest` CI owns it; the `[WARN]` is expected and permanent |

🔴 **No `DllImport` for any of these four symbols anywhere in `src/OpenWSFZ.Ft8`.** Not reachable from the
managed product layer. Test-local P/Invoke in `tests/` is fine (see §3).

### 1.4 `FT8_SHIM_VERSION` = **`20260053`**, deliberately **not** `20260052`

The spec says "next unused". QA verified the full history, and **the obvious answer is a trap**:

- **No ref defines anything above `20260051`**, and `20260053` appears in **zero commits** (`git log --all -S`).
- **`20260052` is reserved on paper:** `dev-tasks/2026-09-03-shim-version-renumber-rc1rc2-and-rc4-branches.md`
  assigns it to `d001-rc4-decode-depth` (`20260035 → 20260052`). That renumber is **queued and unexecuted**.
  Using `20260052` here would recreate the very collision that task exists to remove. Skipping a slot has
  precedent in this file (`20260003`, `20260007` were skipped).
- Re-run the check **at pickup**, because history may have moved:
  ```
  for r in $(git for-each-ref --format='%(refname)' refs/heads refs/remotes); do
    git show "$r:src/OpenWSFZ.Ft8/Native/ft8_shim.h" 2>/dev/null | grep -E '^#define FT8_SHIM_VERSION' | awk -v r=$r '{print $3, r}'; done | sort | tail
  git log --all --oneline -S20260053
  ```
  If `20260053` has been taken, take the next value that is unused **and** unreserved, and say so.
- `FT8_SHIM_VERSION` identifies nothing on its own (MEMORY): the **SHA-256 of the built DLL** is the pin.

## 2. Build

- **Windows:** `native/ft8_lib_build/rebuild_shim.bat`. The `FT8_ROOT` hardcoding landmine was fixed by
  PR #179, which is in `decoding_improvement`'s tip. Even so, **confirm the DLL was built from *your*
  tree** (hash the source in use, or check the timestamp of `obj\ft8_shim.obj`). The script overwrites the
  tracked `src/…/win-x64/libft8.dll` in place. Record the **new SHA-256** and keep a copy of the old
  binary, `91997e38038d9328edcb49cd1e8661706d0092ed2c73e808094c96c3980ad2c6` (`git show
  origin/decoding_improvement:src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`). QA's acceptance needs both.
- **Linux / macOS:** CI. Do not cross-build. After the PR lands, the automated `commit-native-binaries`
  follow-up PR carries the `.so`/`.dylib`.

## 3. Tests (C#, `tests/OpenWSFZ.Ft8.Tests/`, test-local P/Invoke, following `CoherentLlrAtTests.cs`)

Deterministic synthetic scenes only. **No real callsigns** (NFR-021: `Q`-prefix synthetic calls only).

| # | asserts |
|---|---|
| T1 | **Non-perturbation:** for a two-signal scene, `ft8_decode_all` results **and** every `ft8_get_last_*` diagnostic (`pass_counts`, `candidate_counts`, `llr_stats`, `snr_terms`, `noise_floor`) are **identical armed vs disarmed** |
| T2 | **Pass-0 equivalence:** `ft8_get_probe_llrs(0,…)` equals `ft8_extract_llrs_at` at the same PCM/position **bit-for-bit** (compare as `int` bit patterns, never `==` on floats) |
| T3 | **Self-disarm, and never stale:** a second `ft8_decode_all` with no re-arm makes `ft8_get_probe_llrs` return the *not armed* code |
| T4 | **Out-of-band position:** `-3` for that pass; decode results unchanged |
| T5 | **Suppression record:** for a scene with a strong pass-0 decode, `count ≥ 1`; `factor` equals `1 − clamp((snr_db − (−5)) / 20, 0, 1)` within `1e-6`, **and** `factor` lies in `[0,1]`. (Constants `K_SOFT_SUPP_SNR_MIN_DB` = −5, `_MAX_DB` = +15, `ft8_shim.c:537–538`; write the literals in the test as assertions, don't import them.) |
| T6 | **Early exit:** with `max_results` small enough to trigger the pass-1 skip, `ft8_get_probe_llrs(1,…)` returns the *pass did not run* code |

Run the **full** suite and treat any decode-output test failure as a real finding.
`Category=AwgnFpReplay` is CI-excluded (`ci.yml:336`); its SHA-pinned tests were **already stale** at
`20260051`, so they are not a new hazard. Leave them alone.

## 4. Rigour controls

1. 🔴 **The complete list of edits allowed to existing code:** (a) `suppress_candidate_tiles` returns
   `factor` (§1.1); (b) the entry-time consume-and-reset (§1.2.1); (c) the one `if (probe_active)` capture
   call after the suppression block (§1.2.2); (d) the record store inside the pass-1 suppress loop
   (§1.2.4). **Anything else in `ft8_shim.c` that touches an existing line: STOP and report.** Everything
   else is additive.
2. **`decode.c` and the vendored `native/` tree: zero edits.** `ftx_extract_likelihood_at` already exists.
3. **Read-only tap.** No write to `mon.wf`, no change to any counter, candidate, decode, SNR, ordering or
   TLS diagnostic that exists today. Extraction goes into the probe's own buffer.
4. **`FT8Result` stays 48 bytes.** No struct-layout change to anything that exists.
5. **Disarmed cost:** one `bool` test per pass plus a handful of TLS stores per call. Say so in the
   changelog.
6. Toolchain and flags **unchanged**: same script, same machine.
7. `tools/pre_merge_check.py` is **not** in your checklist (HK-000/HK-006); QA runs it at review.

## 5. Scope guardrails — what this is NOT

- **Not Stage 2.** No DIRTY/CLEAN measurement. That is QA's, after acceptance and a separate Captain go.
- **Not a remedy.** No change to the soft-suppression ramp (−5…+15 dB), the ±1-bin footprint, the
  candidate caps (140/200), `K_MAX_PASSES`, or any decode parameter. The H5 rejection (June, 0 dB
  over-suppression) stands as a known failure.
- **Not managed-reachable.** No `DllImport`, no `IFt8NativeInterop` member, no daemon wiring.
- **Not a change to `ft8_extract_llrs_at`** (§1.2.3).
- **Not a push or merge.** Captain sign-off first (HK-011, HK-010).
- **Not a re-opening** of PCM subtract-and-resynthesise (DEAD) or the candidate-budget family (CLOSED ×2).

## 6. Deliverables and completion record

Paste, verbatim, into your reply:

1. `git diff --stat origin/decoding_improvement` (files touched), and `git diff` of `ft8_shim.c` restricted
   to **existing lines**, showing only the four §4.1 edits.
2. New DLL **SHA-256**, plus the old `91997e38…ad2c6` confirmed from `git show`.
3. `dumpbin /exports` (or equivalent) showing the four new symbols **and** every previously exported one.
4. Output of the §1.4 uniqueness check, and the version you took.
5. Test results (T1–T6 by name) and the full-suite tally. CI status on **all three platforms** once pushed.
6. Any deviation from this document, stated plainly.

## 7. What QA does next (not your job, stated so nothing surprises you)

Acceptance **S1-a…d** (spec §1.3): **S1-a** old (`91997e38…`) vs new DLL, probe **disarmed**, results
byte-identical, mechanically diffed; **S1-b** probe **armed** at arbitrary positions, byte-identical to
disarmed; **S1-c** pass-0 tap bit-for-bit vs `ft8_extract_llrs_at` on `DENSITY-MECH`'s cells; **S1-d** CI
green ×3. The spec says "the fixed replay set used for the last shim bump", but the last bump's regression
net was the live S1–S8 battery, which is not an offline diff set. **QA will therefore pre-register S1-a's
concrete replay set before running it** and say so in the acceptance report. That is QA's to define, and
needs nothing from you.

## 8. References

| Reference | Content |
|---|---|
| `origin/arch/density:qa/rr-study/2026-09-18-1758-architect-to-qa-spec-density-pass1-probe.md` §1 | The binding Stage 1 contract |
| `src/OpenWSFZ.Ft8/Native/ft8_shim.c:1583–1606, 1592–1594` | Pass loop; suppression block; insertion point |
| `src/OpenWSFZ.Ft8/Native/ft8_shim.c:857–905` | `suppress_candidate_tiles` (the ramp, `−5…+15 dB`) |
| `src/OpenWSFZ.Ft8/Native/ft8_shim.c:1856–1937` | `ft8_extract_llrs_at` (the reference snapping arithmetic; do not modify) |
| `src/OpenWSFZ.Ft8/Native/ft8_shim.c:1706–1783` | Where `snr` and `all_supp_*` are computed and filled |
| `native/ft8_lib_build/patched/ft8/decode.c:817–848` | `ftx_extract_likelihood_at`, read-only w.r.t. the waterfall |
| `dev-tasks/2026-09-14-passband-140-ship.md` | The most recent shim-bump task; same registration sites |
| `dev-tasks/2026-09-03-shim-version-renumber-rc1rc2-and-rc4-branches.md` | Why `20260052` is reserved |

---

*Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>*
