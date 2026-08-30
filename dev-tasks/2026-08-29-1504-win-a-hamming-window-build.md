# Developer handoff: `WIN-A` Rung 1 — Hamming analysis-window build

**Authored by:** QA (per HK-000/HK-015), transcribing
`qa/rr-study/2026-08-29-1400-architect-to-qa-spec-win-a-analysis-window-sidelobe-ladder.md`
(commit `fb25010`) and the Captain's build authorisation recorded at its top (commit `29e45e2`:
"Developer build session APPROVED — §7 may proceed; QA drafts the dev-task").

🔴 **Per HK-011, this document authorises a BUILD, not a merge.** The arm has not run yet — nothing
in this task may be read as "ship Hamming." §7 of the spec is explicit that the sequence is
QA drafts → **Developer builds** → Captain reviews the diff → **QA arms the gate** — only a
**ROW 1 (BENEFIT)** verdict, reached after arming, licenses a merge recommendation (spec §6.2).
Until then this is an **experimental artefact for QA to test against**, not a candidate for `main`.

**Behaviour change: ONE, INTENDED.** Unlike R0 (a pure reproducibility fix), this task's whole
point is to change decode behaviour — the analysis window. That change is exactly and only the
one described in §1 below; nothing else may move.

---

## 0. Current state, verified this session (HK-018 — not re-stated from the spec unchecked)

- Baseline pin confirmed exactly as the spec states: `main` @ `2ae939c`, shim **20260046**,
  `libft8.dll` SHA256 **`bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f`**,
  verified identical at both `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` and
  `native/ft8_lib_build/libft8.dll` this session.
- `FT8_SHIM_VERSION` is `#define`d at `src/OpenWSFZ.Ft8/Native/ft8_shim.h:626`.
  `ExpectedShimVersion` (the C# side of the ABI sentinel) is at
  `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:371`. Both currently read `20260046` and must move
  to `20260047` **together** (same pattern every prior shim bump has used — grep either file for
  `20260046` to confirm no other reference is missed).
- 🔴 **Finding beyond the spec's own §1.5 excerpt — read before touching the file.** The spec's
  code excerpt shows only the *assignment* line commented out for Hamming/Blackman:
  ```c
  me->window[i] = me->fft_norm * hann_i(i, me->nfft);
  // me->window[i] = blackman_i(i, me->nfft);
  // me->window[i] = hamming_i(i, me->nfft);
  ```
  What it does not show, and what I confirmed by reading
  `native/ft8_lib_build/patched/common/monitor.c:21-47` directly: **the `hamming_i` FUNCTION
  DEFINITION ITSELF is also commented out** (8 lines, 27-34), same as `blackman_i`'s (36-47). The
  spec's §1.5 "MUST be `me->fft_norm * hamming_i(i, me->nfft);`, character for character" cannot be
  satisfied without first uncommenting that function — you cannot call a function whose definition
  is inside a comment. See §1.2 below for exactly what to do about this and why it also affects
  ROW 0c's gate text; **this is flagged for the Architect, not silently resolved by picking an
  interpretation.**
- 🔴 **Second finding, affecting the spec's "rebuilds of all three platform binaries" instruction
  (§7 step 1):** `.github/workflows/ci.yml`'s macOS and Linux legs (lines ~84-95 and ~204-215 in
  the current file) do **not** compile `native/ft8_lib_build/patched/common/monitor.c` at all —
  they `git clone --depth 1 --branch msvc-compat https://github.com/frank001/ft8_lib.git` **fresh
  from the external fork repo** and only overlay this repo's `decode.c` on top of that clone. A
  Hamming change committed only to this repo's `monitor.c` would **not** reach the Linux/macOS CI
  binaries at all — they would keep compiling Hann from the external repo's `msvc-compat` branch,
  silently, with no build error, because that branch is untouched. Making Linux/macOS match would
  require a **separate push to a different GitHub repository** the Captain owns, which is outside
  what a `dev-tasks/*.md` in this repo can authorise. See §3 — **this task's blocking deliverable
  is Windows-only**; Linux/macOS is explicitly deferred, not silently done or silently skipped.

### 0.1 What this means for scope, decided here so the Developer isn't stuck on it

Because the WIN-A gate (spec §3 pins) runs the S7/S5 battery against the **Windows** DLL only
(the daemon + WSJT-X comparison happens on this Windows machine), **the blocking deliverable is
the Windows build alone.** Linux/macOS are moved to a flagged, non-blocking item (§5) that a
merge decision (only reachable via a ROW 1 verdict) would need to resolve later — do not spend
time on them now.

---

## 1. D1 — The one substantive change (Windows only, blocking)

File: `native/ft8_lib_build/patched/common/monitor.c`.

### 1.1 Uncomment `hamming_i`, character for character

Lines 27-34 currently read (each line prefixed `// `):
```c
// static float hamming_i(int i, int N)
// {
//     const float a0 = (float)25 / 46;
//     const float a1 = 1 - a0;

//     float x1 = cosf(2 * (float)M_PI * i / N);
//     return a0 - a1 * x1;
// }
```
Strip exactly the `// ` from each of those **7 commented lines** — line 31 (the blank line between
`const float a1 = 1 - a0;` and `float x1 = ...`) is byte-verified (`od -c`, Architect's ruling §0)
to be a **true empty line, no `//`, no trailing whitespace**. It is not part of the comment and
carries nothing to strip. 🔴 **Leave it completely untouched — do not delete it, collapse it, or
"tidy" the spacing.** It is deliberately load-bearing: it is what makes the corrected ROW 0c
predicate's line-count check (9 removed + 9 added) land exactly right, and removing or altering it
will VOID ROW 0c on a build that is otherwise substantively correct — which is the intended,
correct behaviour of that check, not a false negative to work around. Every other line (7 of the
8) gets `// ` stripped and nothing else — no reformatting, no reflow, no changed constants. Result
must be byte-identical to the commented form with only those 7 comment markers removed. This is
the upstream Kārlis Goba MIT-licensed function, untouched in substance (§1.6 of the spec — no
WSJT-X source consulted, none needed).

### 1.2 Swap the active window line, keep the file's own convention

Lines 81-85 currently read:
```c
        // window[i] = 1;
        me->window[i] = me->fft_norm * hann_i(i, me->nfft);
        // me->window[i] = blackman_i(i, me->nfft);
        // me->window[i] = hamming_i(i, me->nfft);
        // me->window[i] = (i < len_window) ? hann_i(i, len_window) : 0;
```
Change to:
```c
        // window[i] = 1;
        // me->window[i] = me->fft_norm * hann_i(i, me->nfft);
        me->window[i] = me->fft_norm * hamming_i(i, me->nfft);
        // me->window[i] = blackman_i(i, me->nfft);
        // me->window[i] = (i < len_window) ? hann_i(i, len_window) : 0;
```
i.e. **swap which line is active, keep every other alternative commented** — matching the file's
existing convention (all non-chosen windows stay visible as comments) rather than deleting the
Hann line. 🛑 **`me->fft_norm *` MUST appear on the active line, unchanged** — this is the spec's
single most important line (§1.5's trap): the commented alternatives do not carry `fft_norm`, and
uncommenting one of them as originally written would silently drop FFT normalisation, which is a
standing-prohibited input-scaling change. Do not copy the commented line verbatim; write the
`fft_norm`-preserving form above.

### 1.3a ✅ RULED, 2026-08-29 15:13Z — read this before §1.3 below

The Architect has ruled on this (`qa/rr-study/2026-08-29-1513-architect-to-qa-ruling-win-a-row-0c-wording.md`,
commit `3edca62`): the "exactly one changed line" text was the Architect's own drafting error, not
a QA misreading — confirmed independently against `monitor.c` this session. ROW 0c is replaced,
**in effect**, by the `row_0c_ok(diff_files, monitor_diff_lines)` predicate in that ruling's §2 —
spec `fb25010` itself is left untouched, per this project's convention (same as `dee9d90`). It
checks four things mechanically: file scope (only `monitor.c`), exact per-line content including
whitespace, exact line count (9 removed + 9 added = 18, catching a duplicate/reorder a bare
set-equality check would miss), and the `fft_norm` trap (the removed/added sets are keyed so a
build that uncomments the line verbatim without inserting `fft_norm *` fails automatically). **The
edit prescribed in §1.1/§1.2 below already produces exactly this diff — nothing to change in what
you build**, only in what QA checks it against when arming. §1.3 immediately below is kept for
context (why the original wording was wrong) but is now superseded by the ruling for the actual
check QA will run.

### 1.3 🔴 Report to the Architect, don't resolve unilaterally: ROW 0c's literal wording (SUPERSEDED — see §1.3a)

With §1.1+§1.2 applied, `git diff` of this file against `main`@`2ae939c` will show the 8
uncommented `hamming_i` lines **plus** the window-line swap — more than the "exactly one changed
line" ROW 0c literally asks for, even though this is the minimal, correct, spec-mandated change
(§1.5 requires calling `hamming_i(...)` by name, which requires it to exist outside a comment).
**Do not try to satisfy ROW 0c's literal text by inlining the Hamming formula directly into the
assignment line instead of uncommenting the function** — that would contradict §1.5's explicit
"MUST be `me->fft_norm * hamming_i(i, me->nfft);`" instruction to avoid a wording mismatch in a
different section, which is the wrong trade. **Make the change as specified in §1.1/§1.2, report
the true `git diff` in full, and let the Architect amend ROW 0c's check** (something like: "the
diff consists of exactly the uncommented `hamming_i` block, unmodified apart from removed comment
markers, plus the single assignment-line swap, and nothing else" is mechanically checkable and
matches what ROW 0c is actually trying to guard against). This is an escalation, not a decision
for this document to make.

### 1.4 Shim version bump — both sides, together

- `src/OpenWSFZ.Ft8/Native/ft8_shim.h:626`: `#define FT8_SHIM_VERSION 20260046` →
  `#define FT8_SHIM_VERSION 20260047`. Add a changelog comment block above it in the same style as
  the existing entries (see the `fix-negative-time-offset-snr-collapse (FT8_SHIM_VERSION 20260046)`
  block immediately above it for the format) recording: `win-a-hamming-rung1`, the one-line window
  change, the `fft_norm`-preservation note, and this task's file as the source spec.
- `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:371`: `ExpectedShimVersion = 20260046;` →
  `ExpectedShimVersion = 20260047;`.
- Grep both files for any other `20260046` reference before considering this done (R0's task hit
  exactly this kind of miss once already — check rather than assume there are only these two).

### 1.5 Rebuild (Windows only)

Use `native/ft8_lib_build/rebuild_shim.bat` unchanged — no export list change, no new source file,
no changed compile flags. Per `BUILD.md`, this recompiles every translation unit including
`monitor.c` from the tracked patched source, so the change from §1.1/1.2 is picked up automatically.
Copy the result to `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` as the script already does.

### 1.6 Do NOT commit to `main` or open a PR yet

Per the boundary stated at the top of this document: this build has not been armed against the
gate yet, so there is nothing to merge. Work on a scratch/experiment branch (e.g.
`experiment/win-a-hamming-rung1`) or as an uncommitted local change with a WIP commit you can
`git reset --soft` later — either is fine, but **do not push, do not open a PR** (HK-014 applies
to Developer sessions too in spirit: nothing here is Captain-reviewed yet). Hand QA: the branch
name or diff, the new DLL's SHA256, and the exact `git diff` of the three touched files
(`monitor.c`, `ft8_shim.h`, `Ft8LibInterop.cs`).

---

## 2. D2 — ROW 0d's coefficient dump: a standalone diagnostic, NOT a shim/DLL change

ROW 0d requires dumping `me->window[0..7]` on **both** legs (baseline Hann, treatment Hamming) to
catch a wired-but-inert change. Do this **without touching `ft8_shim.c` or the DLL's exported
surface at all** — `monitor_init`/`monitor_t` are plain C with no dependency on the rest of the
decode pipeline for this purpose, so a tiny standalone program is simpler and safer than adding a
new export or an env-var-gated print inside the shipped shim.

### 2.1 Write `native/ft8_lib_build/dump_window.c` (new, throwaway-diagnostic, not linked into the DLL)

```c
#include <stdio.h>
#include <common/monitor.h>
#include <ft8/constants.h>

int main(void)
{
    monitor_config_t cfg = {
        .f_min = 200.0f, .f_max = 3000.0f, .sample_rate = 12000,
        .time_osr = 2, .freq_osr = 2, .protocol = FTX_PROTOCOL_FT8
    }; /* identical to BUILD.md's documented Monitor Configuration */
    monitor_t mon;
    monitor_init(&mon, &cfg);
    printf("nfft=%d\n", mon.nfft);
    for (int i = 0; i < 8; ++i)
        printf("window[%d]=%.9f\n", i, mon.window[i]);
    double sum = 0.0;
    for (int i = 0; i < mon.nfft; ++i)
        sum += mon.window[i];
    printf("sum=%.9f\n", sum);
    monitor_free(&mon);
    return 0;
}
```
ASCII-only output (HK-009 — this prints via a native console, not Python, but keep it ASCII
regardless since QA will be piping it through a Windows console). `sum` is included because ROW 0d
requires `sum(window)` to differ between legs, not just the first 8 values.

### 2.2 Compile it twice — once per leg, against that leg's `monitor.c` only

**Baseline leg** (unmodified `main`@`2ae939c` `monitor.c` — check it out to a scratch copy, or
build from a clean clone of that commit; do **not** use the treatment working tree for this):
```batch
cl /I native\ft8_lib_vendor\common /I native\ft8_lib_vendor /std:c11 /O2 /W3 ^
   native\ft8_lib_build\dump_window.c native\ft8_lib_build\patched\common\monitor.c ^
   native\ft8_lib_vendor\fft\kiss_fft.c native\ft8_lib_vendor\fft\kiss_fftr.c ^
   /Fe:dump_window_baseline.exe
dump_window_baseline.exe > baseline_window.txt
```
**Treatment leg** (after §1's edit is applied):
```batch
cl /I native\ft8_lib_vendor\common /I native\ft8_lib_vendor /std:c11 /O2 /W3 ^
   native\ft8_lib_build\dump_window.c native\ft8_lib_build\patched\common\monitor.c ^
   native\ft8_lib_vendor\fft\kiss_fft.c native\ft8_lib_vendor\fft\kiss_fftr.c ^
   /Fe:dump_window_treatment.exe
dump_window_treatment.exe > treatment_window.txt
```
(`kiss_fft`/`kiss_fftr` are linked because `monitor_init` calls `kiss_fftr_alloc` after the window
loop; without them the link fails. `ft8/constants.h` needs no `.c` — it's header-only for the
protocol enum used here.)

### 2.3 What to hand QA

Both `.txt` outputs, plus the two `.exe`/`.obj` build artefacts are **not** to be committed —
delete them after copying the printed values into your report (this is a throwaway diagnostic
tool per §0.1, not a shipped artefact; do not add it to `rebuild_shim.bat`'s inputs or the DLL
export list).

---

## 3. Acceptance criteria (maps to the spec's ROW 0c/0d, which QA evaluates after arming)

These are what QA will check when arming the gate — reproduce them yourself before handing back,
so a problem is caught here rather than during arming:

- **AC-1** — `row_0c_ok(diff_files, monitor_diff_lines)` from the ruling doc
  (`qa/rr-study/2026-08-29-1513-architect-to-qa-ruling-win-a-row-0c-wording.md` §2) returns
  `True` against your diff: only `monitor.c` touched, the 7 uncommented `hamming_i` lines
  (comment markers only removed, blank line 31 untouched) + the window-line swap in §1.2 (`fft_norm`
  preserved character-for-character on the active line), exactly 9 lines removed and 9 added, no
  other line in the file differs from `main`@`2ae939c`. Run it yourself before handing back rather
  than leaving it for QA to discover a mismatch at arming time.
- **AC-2** — `FT8_SHIM_VERSION` (ft8_shim.h) and `ExpectedShimVersion` (Ft8LibInterop.cs) both read
  `20260047`; no other file references the old `20260046` in a way that now mismatches.
- **AC-3** — `dump_window_baseline.exe` and `dump_window_treatment.exe` (§2) both run and print 8
  coefficients + `nfft` + `sum`; the two `window[0..7]` value sets differ (they must — Hamming ≠
  Hann), and `nfft` is identical between legs (only the window shape should change, not the FFT
  size).
- **AC-4** — new DLL SHA256 recorded; loads and passes the existing `OpenWSFZ.Ft8.Tests` suite
  with no new failures (build + tests only, per HK-011/HK-006 — **do not run
  `tools/pre_merge_check.py`**, that gate is the Captain's initiative alone).
- **AC-5** — the two findings in §0 (the `hamming_i` comment-body issue, the CI external-repo
  monitor.c sourcing) are carried into your report verbatim, not silently absorbed.

---

## 4. Reporting

Your report back to QA must carry:
- the exact `git diff` of all three touched files (`monitor.c`, `ft8_shim.h`,
  `Ft8LibInterop.cs`) — full, not summarised;
- new DLL SHA256, shim integer, and confirmation of AC-4 (build clean, test suite pass count);
- both `dump_window_*.txt` outputs in full;
- the branch name / commit you used for the scratch work (§1.6), so QA can point the arm at it and
  so `git show <main@2ae939c>:...` can still recover the untouched baseline DLL for the arm's
  "same session, same machine" baseline leg (spec §3) without needing you to hand over a separate
  baseline binary;
- confirmation you did **not** touch Linux/macOS binaries, `rebuild_shim.bat`'s export list, or
  `ft8_shim.c` itself.

---

## 5. What this task does NOT do (spec §8, restated, plus the two scope narrowings from §0.1)

- 🛑 Does not touch `src/` decoder logic, the LDPC path, candidate budgets, OSR, or any decode
  parameter — window function only.
- 🛑 Does not reopen subtract-and-resynthesise, input scaling, or spectral locality.
- 🛑 Does not touch Rung 2 (Blackman) — that stays behind its own fresh pre-registration per the
  Captain's authorisation, regardless of what this rung's result is.
- 🛑 Does not produce Linux or macOS binaries (§0.1) — flagged as a deferred, Captain/Architect-
  owed item, not silently skipped and not silently attempted against the wrong source tree.
- 🛑 Does not commit to `main`, push, or open a PR (§1.6) — this is a pre-arming experimental
  build; a merge recommendation can only follow a ROW 1 verdict, which QA has not yet produced.
- 🛑 Does not run `tools/pre_merge_check.py` (HK-006) or declare anything "ready for merge"
  (HK-010) — that is the Captain's initiative, unprompted by Developer or QA.

---

## 6. Boundaries (HK-011/HK-010/HK-014/HK-006/HK-009, restated)

- Separate Developer session, build + tests only, nothing pushed or merged without the Captain.
- Windows console is `cp1252` — keep `dump_window.c`'s output ASCII (HK-009); no `printf` of
  non-ASCII anywhere in this task's artefacts.
- NFR-021: no example callsigns beyond Q-prefix synthetic ones already permitted in VCS (not that
  this task touches any callsign logic — noted for completeness).
- Licence policy (programme §2.1, standing): permissive only. `hamming_i` is already in-tree under
  the same MIT licence as `hann_i` — no new third-party code is introduced, `THIRD-PARTY-NOTICES.md`
  is unaffected.
