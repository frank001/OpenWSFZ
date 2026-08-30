# ARCHITECT → QA — RULING: `WIN-A` ROW 0c wording, and the CI external-repo finding

**Author:** Architect → QA
**Date (UTC, `date -u`, HK-017):** 2026-08-29 15:13:26Z
**Subject:** the two findings flagged (not resolved unilaterally) in
`dev-tasks/2026-08-29-1504-win-a-hamming-window-build.md` §0/§1.3, against
`qa/rr-study/2026-08-29-1400-architect-to-qa-spec-win-a-analysis-window-sidelobe-ladder.md`
(`fb25010`) ROW 0c.
**Status:** RULING. Amends ROW 0c's check text **in effect** — the spec file itself is left
untouched (same convention as the `dee9d90` review of the 08-27 sweep: correction lives in a new
dated document, not an edit to the original). Docs-only, local, **nothing pushed** (HK-014).
Authorises no `src/` change (HK-015).

---

## 0. Verified before ruling (HK-018/HK-022 — not taken on the dev-task's transcription)

Read both files named in the two findings directly, this session:

- `native/ft8_lib_build/patched/common/monitor.c:21-47` and `:78-86` — confirms QA's finding
  exactly. Lines 27-34 are `hamming_i`'s commented-out function body; 7 of those 8 line numbers
  carry a `// ` marker to strip (line 31 is already blank in the source, nothing to strip there).
  Lines 81-85 are the `window[]` assignment block, matching the dev-task's §1.2 transcription
  exactly.
- `.github/workflows/ci.yml:82-95` and `:204-215` — confirms the second finding. Both the macOS and
  Linux legs run `git clone --depth 1 --branch msvc-compat https://github.com/frank001/ft8_lib.git`
  and overlay **only** `patched/ft8/decode.c` from this repo on top of that clone. `monitor.c` is
  never referenced by either leg — it is sourced entirely from the external fork's `msvc-compat`
  branch, untouched by anything committed here.

Both findings verified independently, not taken on report.

---

## 1. ROW 0c — the wording was wrong, and it was my error, not QA's

Spec §1.5 excerpted only the assignment-line change and stated the treatment "MUST be
`me->fft_norm * hamming_i(i, me->nfft);`, character for character" — true as far as it went, but I
wrote ROW 0c's "`git diff` of `monitor.c` between legs is exactly one changed line" from that same
incomplete excerpt without re-deriving it from `monitor.c` itself. That is an HK-018 miss on my own
part: §1 re-derived every *number* in the spec from the matched CSVs but did not re-derive this one
*structural* claim from the source file it names. QA's finding stands exactly as filed — there is
no interpretation to arbitrate here, the original ROW 0c text is simply wrong about what a
spec-conformant diff looks like, because calling `hamming_i(...)` by name (§1.5's own "MUST")
requires the function to exist outside a comment first.

QA's proposed replacement — "the diff consists of exactly the uncommented `hamming_i` block,
unmodified apart from removed comment markers, plus the single assignment-line swap, and nothing
else" — has the right shape and I'm not overriding its substance. But prose describing a diff is
exactly the form HK-021(r) exists to replace, and ROW 0c's own stated consequence is "**VOID —
mechanically diffed, never asserted by eye**." The replacement earns the same standard as the
error it's fixing. §2 below ships it as an executable predicate instead of adopting the prose
directly.

## 2. ROW 0c, corrected — ship this predicate as code (HK-021(r))

Diff computed as `git diff main@2ae939c -- native/ft8_lib_build/patched/common/monitor.c` between
the two legs, split into `(sign, text)` pairs per changed line (`+`/`-` only; file headers and
`@@` hunk headers excluded):

```python
EXPECTED_REMOVED = {
    "// static float hamming_i(int i, int N)",
    "// {",
    "//     const float a0 = (float)25 / 46;",
    "//     const float a1 = 1 - a0;",
    "//     float x1 = cosf(2 * (float)M_PI * i / N);",
    "//     return a0 - a1 * x1;",
    "// }",
    "        me->window[i] = me->fft_norm * hann_i(i, me->nfft);",
    "        // me->window[i] = hamming_i(i, me->nfft);",
}
EXPECTED_ADDED = {
    "static float hamming_i(int i, int N)",
    "{",
    "    const float a0 = (float)25 / 46;",
    "    const float a1 = 1 - a0;",
    "    float x1 = cosf(2 * (float)M_PI * i / N);",
    "    return a0 - a1 * x1;",
    "}",
    "        // me->window[i] = me->fft_norm * hann_i(i, me->nfft);",
    "        me->window[i] = me->fft_norm * hamming_i(i, me->nfft);",
}

def row_0c_ok(diff_files, monitor_diff_lines):
    """diff_files: set of file paths touched, treatment vs main@2ae939c.
    monitor_diff_lines: list of (sign, text) for monitor.c's diff body only."""
    if diff_files != {"native/ft8_lib_build/patched/common/monitor.c"}:
        return False  # ROW 0c licenses this ONE file; any other file touched fails it here,
                       # not just at AC-2 (shim.h/Ft8LibInterop.cs are checked separately)
    removed = {t for s, t in monitor_diff_lines if s == "-"}
    added   = {t for s, t in monitor_diff_lines if s == "+"}
    if removed != EXPECTED_REMOVED or added != EXPECTED_ADDED:
        return False
    if len(monitor_diff_lines) != len(EXPECTED_REMOVED) + len(EXPECTED_ADDED):
        return False  # catches a duplicated/reordered line a set-equality check alone would hide
    return True
```

What this guards, each corresponding to a real failure mode the prose version leaves to
inspection:

- **File scope** — restricted to `monitor.c` alone. Touching `hann_i`, `blackman_i`, or anything
  else in the file fails ROW 0c outright, independent of whether the hamming/window lines are
  right.
- **Exact content per line, whitespace included** — a reformatted or reflowed `hamming_i` body
  fails it. This is the mechanical form of §1.1's "byte-identical... only comment markers
  removed."
- **Exact count** — a duplicated or reordered line that happens to match the content *set* still
  fails it, which a bare set-equality check would miss.
- **The `fft_norm` trap stays enforced** — `EXPECTED_REMOVED` contains the *un-normalised*
  commented form (`hamming_i(i, me->nfft)`, no `fft_norm`) and `EXPECTED_ADDED` contains the
  *normalised* active form (`me->fft_norm * hamming_i(...)`). A build that uncomments the line
  verbatim without inserting `fft_norm *` produces a different `added` set and fails ROW 0c — this
  was the spec's single most important line (§1.5) and the corrected check still asserts it
  mechanically, not by eye.

ROW 0c's bar in the spec's §4 table (`if it fails: VOID — mechanically diffed, never asserted by
eye`) is unchanged; only the check text is replaced by `row_0c_ok(...)` above, evaluated in effect
as though substituted into §4 at commit `fb25010`.

## 3. The CI / external-repo finding — ratified, Windows-only scoping stands

QA's §0.1 scoping decision is correct and I'm ratifying it, not just letting it stand unchallenged:
the WIN-A gate (spec §3 pins) runs the S7/S5 battery against the Windows DLL only — the daemon and
the WSJT-X comparison both run on this Windows machine — so cutting the blocking deliverable to
Windows-only is the right scope, and a same-repo `monitor.c` edit genuinely cannot reach the
Linux/macOS CI legs (confirmed in §0 above) without a separate push to `frank001/ft8_lib`'s
`msvc-compat` branch on a **different repository**, which is correctly outside what a
`dev-tasks/*.md` in this repo can authorise. Correctly flagged as deferred, not silently skipped
and not silently attempted against the wrong source tree.

One addition to the queue, not a change to the dev-task as drafted: **if Rung 1 reads ROW 1**
(spec §6.2 — "recommend Hamming to the Captain for merge"), the merge precondition list needs this
added explicitly. A "merge" that ships Hamming on Windows while Linux/macOS silently keep compiling
Hann forever from the untouched external fork is a platform-parity regression riding along on a
win, not a clean merge. Recording this now so it isn't rediscovered at merge time, days after a
ROW 1 result has everyone's attention on the good news instead.

---

## 4. Ruling

- **ROW 0c** — replaced by `row_0c_ok(...)` in §2 above. QA is unblocked to evaluate it once the
  Developer build lands; the substance QA proposed was right, the form is now mechanical.
- **CI finding** — ratified as correctly scoped and correctly deferred. §3's merge-precondition
  addition is recorded for whichever session reaches a ROW 1 verdict; it does not block Rung 1's
  build or arming.
- No other change to the spec: the gate (§6), the metrics (§5), the pins (§3), or the scope (S7+S5,
  Rung 2 held back behind its own pre-registration) are all unchanged by this ruling.

Developer build remains the blocker (HK-021(p)/HK-011) — this ruling clears the wording question
QA was stopped on, nothing else.
