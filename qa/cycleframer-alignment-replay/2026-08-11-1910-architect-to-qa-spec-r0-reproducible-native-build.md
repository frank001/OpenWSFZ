# SPEC R0 — A native build reproducible from pinned sources

**Author:** Architect → QA
**Date:** 2026-08-11 19:10:21Z (mechanically derived, HK-017)
**Programme:** `2026-08-11-1910-architect-to-qa-programme-d001-sync-refinement.md`
**Shim version for this spec:** **20260039**
**Type:** 🔴 **BUILD SPEC with acceptance criteria.** Not a measurement arm. No ROW is read.
**Behaviour change:** 🛑 **NONE INTENDED.** That is the whole point — see §4.

---

## 1. Why this exists

Established by code read 2026-08-11, and it is worse than the board records:

`native/ft8_lib_build/rebuild_shim.bat` compiles **only** `decode.c` and `ft8_shim.c`. It then
links nine object files it never builds:

| object | date on disk | tracked in git? |
|---|---|---|
| `constants.obj`, `crc.obj`, `kiss_fft.obj`, `kiss_fftr.obj`, `ldpc.obj`, `text.obj` | 2026-05-29 | no |
| `encode.obj` | 2026-06-06 | no |
| `monitor.obj` | 2026-06-07 | no |
| `message.obj` | 2026-06-14 | **yes** — the only one |
| `decode.obj`, `ft8_shim.obj` | 2026-08-07 | no — but these two ARE rebuilt by the script |

Source tree: `C:\Temp\ft8_lib_headers` — a git repo, `github.com/frank001/ft8_lib`, **MIT**,
HEAD `d18ed84f058290b36652f50db41875f2cafbaa4c` ("feat: add MSVC VLA compatibility patches").

✅ **CORRECTION to this spec's own first draft, and it materially lowers the alarm.** The first
draft said the sources were *"modified and uncommitted"*, implying the linked objects were built
from code that has since changed. **That was overstated and QA should not carry it forward.**
`git status` does report ~27 modified files under `ft8/`, `common/`, `fft/` — but
`git diff --ignore-cr-at-eol` returns **empty**. 🔴 **Every modification is line-ending noise
(LF→CRLF); the tree is content-identical to `d18ed84`.** The same is true of `LICENSE`, which also
appeared modified. ⚠️ **Re-verify this yourself — it is one command — but do not inherit the panic
version.**

🔴 **The real problem is narrower, and still disqualifying: nine of eleven linked objects are
untracked build artefacts with no recorded provenance, and the build cannot regenerate them.**
The pinned production DLL `f2f30c89…` therefore cannot be rebuilt from source today, and every
replay arm is pinned to a binary we cannot reconstruct. R1/R2 modify `decode.c`/`ft8_shim.c` and
would link new code against those same opaque artefacts — **so a null result in R2 could be caused
by the artefacts rather than by the change.**

---

## 2. Deliverables

**D1 — Vendor the native sources into version control.**
The upstream is MIT and is the Captain's own fork, so vendoring is licence-clean.
- Commit the sources and headers **actually needed for our link** into the repo under a directory
  of QA's choosing (suggest `native/ft8_lib_vendor/`), preserving the upstream `LICENSE` verbatim.
- 🔴 **Record provenance mechanically, not in prose:** upstream remote URL and HEAD SHA
  (`d18ed84f058290b36652f50db41875f2cafbaa4c`), plus the command and output establishing that the
  working tree is content-identical to it (`git diff --ignore-cr-at-eol`, expected empty).
- 🛑 **EXCLUDE `ft4_ft8_public/`.** It carries **no licence header of any kind**, and **nothing we
  build compiles Fortran** — `rebuild_shim.bat` has no Fortran step. It is not needed and its
  provenance is unestablished. ⚠️ The Captain's original ruling mentioned needing "the FT8 fortran
  decoder"; he has since withdrawn that (*"skip it, i misunderstood"*). **There is no Fortran plan.
  Do not vendor it, and do not revive the question without a new ruling.**
- 🛑 Do not commit the upstream `.git/` directory, its test corpus, or build detritus (the tree is
  45 MB including `.git`; the link needs ~30 `.c`/`.h` files). Report the committed size.
- ⚠️ **Do not "tidy" the sources while vendoring** — no reformatting, no line-ending normalisation
  of content, no warning fixes. Whatever is on disk is what built the shipped DLL; capture it
  as-is, or §4's equality check is measuring your cleanup instead of the build.

**D2 — `rebuild_shim.bat` rebuilds every translation unit from vendored sources.**
No pre-built object may be linked. The build must start from an **empty** `obj/` directory and
produce a complete DLL. Keep the existing `/EXPORT:` list unchanged.

**D3 — Fix `p23_common.py:182`.**
`ref = {k: a[k] for k in a.keys() & b.keys()}` iterates a hash-randomised set, so a fixed
`random.Random(seed)` still draws different indices across processes. Fix by sorting at
construction, the same fix already applied in `x4_spectral_locality.py` / `x3_lattice_crowding.py`.
🔴 **P2/P3/P1a's determinism claims are UNVERIFIED, not confirmed** — this is why. Small, and R2
depends on it.

**D4 — A `--assert-dll-sha` capability for the replay harness**, if one does not already exist, so
every downstream run pins the binary by SHA and fails loudly on mismatch. **The SHA is the
authority; the shim version integer is not — it has collided twice.**

**D5 — 🔴 `THIRD-PARTY-NOTICES.md` at the repo root. This closes a real, PRE-EXISTING compliance
gap and is not optional.**

Audit finding, 2026-08-11: **the repository ships no third-party attribution of any kind** — no
`NOTICE`, no `THIRD-PARTY`, no `COPYING`, nothing. Both licences below require their copyright
notice to travel with the distribution, so **the obligation is unmet today**, independently of this
programme. R0 is the right place to fix it because R0 is the spec that vendors the sources.

| component | licence | obligation |
|---|---|---|
| **ft8_lib** (`ft8/`, `common/`) | **MIT**, © 2018 Kārlis Goba | Copyright notice + permission notice in all copies or substantial portions |
| **KISS FFT** (`fft/kiss_fft.c`, `kiss_fftr.c`, `_kiss_fft_guts.h`) | **BSD-3-Clause**, © 2003–2010 Mark Borgerding | Binary redistribution must reproduce the notice in accompanying materials; plus the no-endorsement clause |

✅ **KISS FFT stays — the Captain has ruled BSD-3-Clause acceptable under the MIT-compliance
policy.** No replacement work. It needs attribution, not removal. ⚠️ Note the upstream header says
*"See COPYING file"* and **no `COPYING` file exists in the vendored `fft/` directory** — reproduce
the BSD-3-Clause text in full in the notices file rather than referencing a file we do not ship.

🔴 **Also record, as a FLAGGED-NOT-BLOCKING entry (Captain's ruling):** `ft8/constants.h` states in
its own comments that the LDPC tables derive from WSJT-X — line 75 *"From WSJT-X's
`ldpc_174_91_c_reordered_parity.f90`"*, line 78 *"Mn from WSJT-X's `bpdecode174.f90`"* — and
`constants.obj` is linked into the shipped DLL. **This is inherited from upstream ft8_lib, not
introduced by us.** The Captain has ruled: **flag it, do not block**, on the basis that LDPC parity
matrices are FT8 **protocol constants** that any conformant implementation must reproduce
identically. 🛑 **Record it plainly and move on. Do not stop the programme for it, and do not
re-open it without a new ruling.**

⚠️ **QA/Architect are not lawyers and this file is not a legal opinion** — it is an accurate record
of the licences as found on disk. If OpenWSFZ is ever distributed to third parties at scale, the
Captain may want a professional review; that is his call and is outside R0's scope.

---

## 3. What R0 must NOT do

🛑 No change to decoder behaviour. No parameter change. No `K_MAX_PASSES`, no candidate caps, no
passband, no OSR, no LLR scaling. **If a source file must change to compile, that is a finding to
report, not a change to make silently.**

---

## 4. Acceptance criterion — mechanical, and it is a real check

**AC-1 (primary): behavioural equality against the pinned baseline.**

Build the DLL from vendored sources per D2. Replay a fixed corpus subset through **both** the new
DLL and the pinned `f2f30c89…` DLL, same input, same parameters, same order.

> **PASS:** the decode output is **byte-identical** — same decodes, same order, same
> `freq_hz`/`dt`/SNR fields, on every cycle.
> **FAIL:** any difference at all.

Subset: **≥ 200 contiguous cycles** from the pinned 20m corpus. Report the exact cycle range.
The comparison must be a **mechanical diff of serialised output**, never an eyeballed summary or a
count-of-decodes match — 🔴 *"two runs, byte-identical" must be MECHANICALLY DIFFED, never
asserted.*

**Evaluate BOTH branches before running (HK-021(k)):**

- **PASS** ⇒ the vendored sources genuinely reproduce the shipped binary. R1 proceeds on a
  trustworthy foundation. This is the expected and desired outcome.
- **FAIL** ⇒ 🔴 **the shipped DLL does not correspond to its nominal sources.** This is a finding
  about **everything already published** off that binary — X3 in particular, which is pinned to it
  — not merely a blocker for this programme. **STOP, do not attempt to make it pass by adjusting
  sources, and ESCALATE to the Captain immediately.**

Both branches change what happens next, so this is a legitimate gate and not a diagnostic.

**AC-2: reproducibility.** Two clean builds (empty `obj/`, fresh checkout) must produce DLLs whose
**decode output is byte-identical to each other** on the AC-1 subset. ⚠️ Do **not** require the
DLL files themselves to be byte-identical — MSVC embeds timestamps and its output is not
bit-reproducible. Behaviour is the contract.

**AC-3: version hygiene.** The R0 DLL asserts shim **20260039** at startup. `ft8_shim.h` and
`Ft8LibInterop.cs` agree. Record the new DLL's SHA256 in the report.

**AC-4: licence hygiene — mechanical, not a judgement call.**

> **PASS** requires all four:
> 1. `THIRD-PARTY-NOTICES.md` exists at the repo root and reproduces, in full, the MIT text with
>    Kārlis Goba's copyright **and** the BSD-3-Clause text with Mark Borgerding's;
> 2. every vendored source file's own licence header is present and **unmodified**;
> 3. **no vendored file is GPL- or AGPL-licensed** — assert by scanning the vendored tree for
>    `GNU General Public`, `GPL`, `Affero`, and reporting every hit with its file and line;
> 4. `ft4_ft8_public/` is **absent** from the vendored tree.

⚠️ **Check (3) will legitimately hit `ft8/constants.h` lines 75 and 78** (the WSJT-X comment
references). That is the known, Captain-ruled, flagged-not-blocking entry from D5 — **it is
expected, and it does not fail AC-4.** Any *other* hit does. 🛑 Do not "fix" it by deleting the
comments: the attribution comment is the only record of where those tables came from, and removing
it would make the provenance worse, not better.

---

## 5. Reporting

Standard QA→Architect report. Must carry:
- upstream remote and HEAD SHA, plus the `git diff --ignore-cr-at-eol` output establishing content
  identity (expected empty);
- old and new DLL SHA256, and the shim integer;
- the AC-1 cycle range, the diff command used, and its exit status;
- the AC-4 licence scan output **in full**, including the two expected `constants.h` hits;
- the committed vendored size;
- **for AC-1 FAIL: which decodes differ and how**, before any diagnosis.

## 6. Constraints

🔴 **HK-011 in full** — QA authors `dev-tasks/*.md` and **STOPS**; a separate Developer session
runs `opsx:apply`; the Captain reviews the diff. The Captain's "I don't care if there is developer
work involved" authorises the *work*, not a shortcut through the *process*.
🔴 **HK-014** — no push, no merge. **HK-010** — merge needs explicit sign-off.
🔴 **HK-006** — `pre_merge_check.py` runs on the Captain's initiative only.
🛑 **Licence policy (programme §2.1):** permissive only — MIT / BSD-2 / BSD-3 / ISC. **No GPL-
derived code may be copied in, from WSJT-X or anywhere else.**

## 7. Architect predictions (scored on report)

- **AC-1: PASS.** Rationale: the frozen objects are old, but the source tree is now **verified**
  content-identical to `d18ed84` (§1), so the objects most likely correspond to it. ⚠️ **This is a
  DIRECTIONAL call and my record on those is 1/3** — nothing in this spec gates on it, and AC-1 is
  drafted so that FAIL is fully actionable and is in fact the higher-value outcome for the record.
- ✅ **Superseded:** the first draft declined to predict how many files were line-ending-only,
  saying I had not looked. **I then looked** — `git diff --ignore-cr-at-eol` is empty, so the
  answer is *all of them*. Recorded as a measurement, not a prediction. This is HK-018 working as
  intended: a five-minute check beat a paragraph of reasoning, and it removed a false alarm from
  this spec's own §1.
