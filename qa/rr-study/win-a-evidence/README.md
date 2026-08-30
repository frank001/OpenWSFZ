# `WIN-A` evidence archive — the measurement artefacts behind a standing prohibition

**Preserved:** 2026-08-29, on the Captain's instruction that the session's work and analyses not be
lost.
**Why this directory exists:** these three files were committed only on
`experiment/win-a-hamming-rung1` @ `2401915`, a branch that carries the **retired Hamming build** and
is **never to be merged**. If that branch is deleted under HK-003 branch hygiene, the raw evidence
behind the window-family prohibition would go with it.

🔴 **These are measurement artefacts, not build inputs.** Nothing here is compiled, linked, or
shipped. `dump_window.c` is preserved as the *method* that produced the two dumps, so the
measurement can be reproduced — **not** so it can be rebuilt into anything.

---

## What they prove

The **analysis-window family is CLOSED** (Captain's ruling, 2026-08-29 — Hann stays; Hamming and
Blackman both retired, Blackman never built). The prohibition is recorded in
`memory/closed-arms-prohibitions.md`; the ruling is
`qa/rr-study/2026-08-29-1928-architect-to-qa-win-a-closed-branch-a-directed.md`.

`baseline_window.txt` (Hann) and `treatment_window.txt` (Hamming), both at `nfft = 3840`:

| | baseline (Hann) | treatment (Hamming) |
|---|---|---|
| `window[0]` | 0.000000000 | 0.000045290 |
| `sum` | 1.000000026 | 1.086956532 |

These support two independent conclusions:

1. **ROW 0d passes** — `max_abs_diff ≈ 4.5e-5 > 1e-6` and the sums differ, so the window change was
   live and wired, not inert.
2. **The build was correct** — with `fft_norm = 2/3840`, `sum = 1.086957 = 2α` gives **α = 25/46**,
   the optimal-Hamming coefficient, and `window[0] = (2α − 1)·fft_norm = 4.529e-5` matches the dump
   to all nine printed digits. `fft_norm` was preserved, so the standing input-scaling prohibition
   was not breached.

⚠️ **The baseline's `window[0] = 0.000000000` is what proves it is Hann, not rectangular** — a
rectangular window is constant across all indices. One run report mis-described the change as
"rectangular→Hamming"; these files are the correction.

## What they do NOT prove

🛑 `WIN-A` was closed on a **failed pre-registered ROW 0e**, **not** on a decode verdict. The gate
never fired. **There is no ROW 1/2/3/4 for `WIN-A`** and none may be quoted.

🛑 **Never write "sidelobe leakage is not the capture mechanism."** That was ROW 4's wording and
ROW 4 was conditional on ROW 0e *passing*. The capture deficit (≈6.98 pp of the S7 gap) **remains
open** under D-001.

## Provenance

| file | origin |
|---|---|
| `baseline_window.txt` | `2401915:native/ft8_lib_build/baseline_window.txt` |
| `treatment_window.txt` | `2401915:native/ft8_lib_build/treatment_window.txt` |
| `dump_window.c` | `2401915:native/ft8_lib_build/dump_window.c` |

Extracted verbatim with `git show`; **not edited.** Paths changed only because the originals sat in
the native build directory, where they would read as build outputs of a retired arm rather than as
evidence.

⚠️ Documents written before this archive existed cite the **original** paths
(`native/ft8_lib_build/{baseline,treatment}_window.txt`). Those citations are correct as of their
writing; this directory is where the files survive.

## Reproducing the analysis

`qa/rr-study/win_a_row0e.py` recomputes both windows from first principles and **checks itself
against these dumps** before drawing any conclusion — run it and compare its "window identity check"
block to the two `.txt` files. It also carries the ROW 0e leakage computation that closed the arm.

**Related binaries, for the record — neither is in this directory:** the retired Hamming build was
`c82812976e8bd3290a9ac3ff36a8af583b9c3893e48818040263cbc59434c77a`; `main`'s shipped decoder is
`bc8efcf148046f199c057b62c7987c4b69f2dc62d72509458a671305ab051d7f`.
