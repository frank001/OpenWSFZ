# Vendored source provenance — `native/ft8_lib_vendor/`

Recorded per `native-build-provenance` capability, r0-reproducible-native-build.

- **Upstream remote:** `https://github.com/frank001/ft8_lib.git`
- **Branch:** `msvc-compat`
- **HEAD commit SHA:** `d18ed84f058290b36652f50db41875f2cafbaa4c`
- **Upstream of the fork:** `kgoba/ft8_lib`, tag `2.0` (`50ee0c06361388a992c80a1af9c1189652b72e51`); the fork's
  only changes are the MSVC VLA compatibility patches to `common/monitor.c` and `ft8/decode.c`
  (both excluded from this vendored tree — they are already tracked, patched, at
  `native/ft8_lib_build/patched/`; see Open Question 1 in this change's `design.md` for why they
  stay there rather than moving into this directory).

## Content-identity check

Command (run against a local clone of the remote/branch/SHA above):

```
git diff --ignore-cr-at-eol
```

Output: **empty** (0 bytes, exit 0). `git status --short` on the same clone reports every
tracked path as modified, but every one of those is a CRLF/LF line-ending difference only —
confirmed by piping the diff to `wc -c` (0) separately from `git status`'s warnings. The vendored
tree is genuinely content-identical to upstream HEAD `d18ed84f…`, modulo line endings.

## Files vendored (22 + this file)

Traced by include-graph analysis of every `#include` reachable from the two already-tracked
patched files (`decode.c`, `monitor.c`) and `ft8_shim.c`, re-derived independently rather than
copied from the design doc's estimate — matches the spec's minimum list exactly, with nothing
additional required:

```
ft8/constants.c   ft8/constants.h   ft8/crc.c    ft8/crc.h    ft8/decode.h
ft8/encode.c      ft8/encode.h      ft8/ldpc.c   ft8/ldpc.h   ft8/message.c
ft8/message.h     ft8/text.c        ft8/text.h   ft8/debug.h
common/common.h   common/monitor.h
fft/kiss_fft.c    fft/kiss_fft.h    fft/kiss_fftr.c   fft/kiss_fftr.h   fft/_kiss_fft_guts.h
LICENSE
```

`ft8/decode.c` and `common/monitor.c` are deliberately **not** duplicated here — they remain the
sole, already-tracked copies at `native/ft8_lib_build/patched/`, since that tree carries genuine
MSVC-compatibility modifications and this tree's whole purpose is to stay byte-identical to
upstream. `ft4_ft8_public/`, `demo/`, `test/`, `utils/`, `Makefile`, `README.md`,
`.clang-format`, `.gitignore`, `.git/` are excluded (not needed by any build step; the Fortran
directory in particular carries no licence header of any kind).

## Byte-for-byte copy verification

Every vendored file `cmp`'d against its source in the upstream clone at copy time: zero
mismatches. Total committed size: 159 KB (22 files, 115,705 bytes).

## GPL/AGPL scan (AC-4)

`grep -rin "gnu general public|\bgpl\b|affero"` (case-insensitive) across this entire tree plus
`native/ft8_lib_build/patched/`: **zero hits.** The two WSJT-X-derived LDPC-table attribution
comments this change's spec anticipated as "expected hits" (`ft8/constants.h` lines 75 and 78)
say only `"From WSJT-X's ..."` / `"... from WSJT-X's ..."` — they do not contain the literal
strings the scan searches for, so the scan is cleaner than the pre-registered scenario describes
(zero hits total, not two flagged ones). Confirmed present at those exact line numbers,
unremoved, via a separate `grep -rn "WSJT-X"` sanity check (which also surfaces several
methodology-attribution comments in `patched/ft8/decode.c`, none of them licence text).
