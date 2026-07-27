# D-001: QA -> Architect notification — the `libft8.dll` +97 KB is explained, section-and-symbol level

**Author:** QA, 2026-07-27 (16:00). **For:** the Architect, per HK-015.
**Answers:** `2026-07-26-2030-architect-c2-phase2c-ruling.md` §9 — "explained by a section/symbol
comparison, not by argument."
**This is a notification, not an escalation.** The finding confirms the growth is a single,
already-documented, opt-in diagnostic buffer — not a build-configuration difference.

---

## 1. Method

`dumpbin /headers` and `/symbols` against two binaries: the committed HEAD copy of
`win-x64/libft8.dll` (60,416 bytes, shim 20260033-era) extracted via `git show HEAD:...`, and the
current working-tree copy (158,208 bytes, shim 20260035). Tool: MSVC 19.44 `dumpbin.exe` (matches
this DLL's own build compiler). Raw output under git-ignored `artefacts/d001_dll_size_check/`
(verified via `git check-ignore -v`, per NFR-021).

## 2. Result — the growth is one array, to the byte

| section | old virtual size | new virtual size | delta |
|---|---:|---:|---:|
| `.text` | 42,648 | 43,240 | **+592 bytes** |
| `.rdata` | 12,854 | 110,502 | **+97,648 bytes** |
| `.data` | unchanged (5,856) | unchanged (5,856) | 0 |
| `.pdata` / `.reloc` | unchanged | unchanged | 0 |

`.text`'s +592 bytes matches your prior read exactly ("a few hundred bytes... two new exported
functions and a blend in `ftx_normalize_logl`").

`.rdata`'s +97,648 bytes is accounted for to within 0.2%: `ft8_shim.c`'s new
`static _Thread_local float tls_diag_llr174[K_MAX_CANDIDATES][FTX_LDPC_N]` (140 x 174 floats,
added for the opt-in raw-LLR capture, shim 20260035) is **97,440 bytes** (140 x 174 x 4). Residue:
**208 bytes**, consistent with the new `IMAGE_TLS_DIRECTORY` descriptor that appeared in the
optional header's data directories (0x28 = 40 bytes, RVA `CF80`, absent from the old binary
entirely — `.text`/`.rdata` grep for "tls"/"Thread Storage" found nothing in the old headers) plus
minor export-table growth from the two new entry points.

Why an *uninitialized* thread-local array lands in a read-only, on-disk-sized section rather than
costing nothing (as an ordinary `static` array would in `.bss`): a TLS array has no `.bss` — the OS
loader copies a real template into each thread's TLS block at thread-attach time, so the template
itself must exist as real, on-disk bytes even though every one of them is zero. That toolchain
behaviour, not a build-configuration change, is the mechanism.

Symbol-table cross-check: `_thread_local` statics are non-exported and this is a stripped release
build, so `tls_diag_llr174` itself does not appear in `/symbols` (expected — no regression from the
old binary's symbol table either, both are equally stripped of statics).

## 3. Reading

Your 20:30 §9 candidate causes — optimisation level, CRT linkage, debug/RTTI metadata — are ruled
out. The delta is fully attributable to source already reviewed and accepted in this thread: the
raw-LLR capture buffer documented in `libft8.version.txt`'s shim 20260035 entry and in
`2026-07-26-c2-phase2c-shrinkage-trial-and-ber-findings.md`, sized by `K_MAX_CANDIDATES` (140) x
`FTX_LDPC_N` (174), opt-in and zero-cost-when-disabled on the decode path itself (the version
file's existing claim) — this notification adds that it is not zero-cost *on disk*, which is a
different claim your §9 was right to ask be checked rather than assumed.

## 4. What this does not settle

- **Whether an unused 97 KB TLS template is an acceptable permanent cost** of an opt-in diagnostic,
  versus something to shrink (e.g. only sizing the capture buffer to a smaller cap, or allocating
  it heap-side instead of as a fixed TLS array) — that is a design call, not a QA finding, and nothing
  here recommends either way.
- **No native or `src/` change** was made to produce this notification — read-only `dumpbin` against
  already-committed/already-built binaries only (HK-011 untouched).
- **No push, no merge** (HK-014). **No `pre_merge_check.py`** (Captain's trigger, HK-006, not run).
- **Branch disposition remains open**, untouched by this session.

## 5. Cross-references

- `2026-07-26-2030-architect-c2-phase2c-ruling.md` §9 — the question this answers.
- `src/OpenWSFZ.Ft8/Native/win-x64/libft8.version.txt` — shim 20260035 entry, the buffer's original
  documentation.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c` (`tls_diag_llr174` declaration, ~line 590) —
  `git diff HEAD -- src/OpenWSFZ.Ft8/Native/ft8_shim.c`.
- `artefacts/d001_dll_size_check/` — raw `dumpbin` output (git-ignored, NFR-021).

---

*Per HK-015, what this means for the merge-blocker status is yours to rule on, not QA's. Per
HK-014, nothing here is pushed or merged.*
