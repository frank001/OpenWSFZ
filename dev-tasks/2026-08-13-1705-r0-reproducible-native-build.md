# Developer handoff: R0 — a native build reproducible from pinned, vendored sources

**Authored by:** QA (per HK-000/HK-015), transcribing
`qa/cycleframer-alignment-replay/2026-08-11-1910-architect-to-qa-spec-r0-reproducible-native-build.md`
(re-pinned 2026-08-13, `qa/cycleframer-alignment-replay/2026-08-13-1649-qa-to-architect-captains-ruling-g2b-ships-after-r2.md`
and the sequencing memo cleared the path — see board).
🔴 **Per HK-011 and the spec's own §6 ("HK-011 in full"), this document is a proposal, not
approved work in itself.** A separate Developer session runs `opsx:apply` (build + tests only —
never `pre_merge_check.py`, that is HK-006, the Captain's initiative alone). The Captain reviews
the `src/`/`native/` diff before any push or merge (HK-010/HK-014). QA does not declare "ready for
merge." **This applies to all five deliverables below, including D3/D4 — the spec bundles them
into one build-spec document and does not carve those two out, so QA is not freelancing an
exception here.**

**Behaviour change: NONE INTENDED.** R0 is a reproducibility fix, not a decoder change. If a
source file must be edited to compile, that is a **finding to report**, not a change to make
silently (spec §3).

---

## 0. Current state, verified this session (not re-stated from the spec unchecked)

- Baseline DLL is now **`c559a049d103c1f350f1a87b319033d5f8d1a2f91b74d9756d8d7cf03d2e6112`**, shim
  **20260038** (G2(a) merged to `main` at `9500e03`, 2026-08-13 — supersedes the spec's original
  `f2f30c89…`/20260033 pin; see the spec's own §1 re-pin note).
- `native/ft8_lib_build/rebuild_shim.bat` compiles **only** `ft8/decode.c` (the MSVC-patched copy
  at `native/ft8_lib_build/patched/ft8/decode.c`, already tracked in git) and `ft8_shim.c`
  (`src/OpenWSFZ.Ft8/Native/ft8_shim.c`, already tracked). It then **links nine `.obj` files it
  never builds**, of which only `native/ft8_lib_build/obj/message.obj` is tracked in git:
  `constants.obj`, `crc.obj`, `kiss_fft.obj`, `kiss_fftr.obj`, `ldpc.obj`, `text.obj`,
  `encode.obj`, `monitor.obj` (the MSVC-patched copy — source is tracked at
  `native/ft8_lib_build/patched/common/monitor.c`, but the pre-built `.obj` itself is not).
- Vendor source tree `C:\Temp\ft8_lib_headers` (**outside version control**) — verified this
  session: `origin` = `github.com/frank001/ft8_lib.git`, HEAD =
  `d18ed84f058290b36652f50db41875f2cafbaa4c`. `git status --short` reports 123 modified paths, but
  `git diff --ignore-cr-at-eol` is **empty** (only CRLF/LF warnings, zero diff hunks) — **content-
  identical to `d18ed84`**, confirmed independently, not inherited from the spec.
- Header include graph traced this session (`grep` across `ft8/`, `common/`, `fft/`) to determine
  the **actual** transitive closure needed for the link — see §1.1. Total tree size at the source
  is 45 MB including `.git`/`test/`/`demo/`/`ft4_ft8_public/`; none of that is needed (§1.1 lists
  ~24 files).

---

## 1. D1 — Vendor the native sources into version control

### 1.1 Exact file list (traced by include graph, not guessed)

Directory: **`native/ft8_lib_vendor/`** (spec's suggested name — free to rename, record whichever
is chosen).

| from `C:\Temp\ft8_lib_headers\...` | note |
|---|---|
| `LICENSE` | MIT, © 2018 Kārlis Goba — needed verbatim for D5/AC-4 |
| `ft8/constants.c`, `.h` | |
| `ft8/crc.c`, `.h` | |
| `ft8/decode.h` | **`.h` only** — `decode.c` itself is the MSVC-patched copy, already tracked at `native/ft8_lib_build/patched/ft8/decode.c`; see §1.3 on whether to relocate it |
| `ft8/encode.c`, `.h` | |
| `ft8/ldpc.c`, `.h` | |
| `ft8/message.c`, `.h` | |
| `ft8/text.c`, `.h` | |
| `ft8/debug.h` | pulled in by `message.c` |
| `common/monitor.h` | **`.h` only** — `monitor.c` is the MSVC-patched copy, already tracked at `native/ft8_lib_build/patched/common/monitor.c`; see §1.3 |
| `common/common.h` | pulled in by `monitor.c` |
| `fft/kiss_fft.c`, `.h` | |
| `fft/kiss_fftr.c`, `.h` | |
| `fft/_kiss_fft_guts.h` | |

**Explicitly excluded** (not in the link, don't vendor): `common/audio.c/.h`, `common/wave.c/.h`
(demo/test-only — the shim doesn't call them), `demo/`, `test/`, `utils/`, `Makefile`,
`README.md`, `.clang-format`, `.gitignore`, `.git/`. 🛑 **`ft4_ft8_public/` explicitly excluded per
the spec — no licence header, nothing we build compiles Fortran, no Fortran plan (Captain
withdrew that ask). Do not vendor it and do not revive the question without a new ruling.**

⚠️ **Verify this list by attempting the build (§2), not by trusting it as final** — it was traced
by `grep`-ing `#include "..."` and `#include <.../...>` transitively from the 9 untracked `.obj`s'
source files plus what they pull in; a missed transitive header will show up as a `cl.exe` error
naming the missing file, which is the correct way to discover it, not a failure of this task.

### 1.2 Provenance — mechanical, not prose

Record, verbatim, in the vendor directory (e.g. `native/ft8_lib_vendor/PROVENANCE.md`) or in the
PR description if the Captain prefers no extra file:
- upstream remote: `https://github.com/frank001/ft8_lib.git`
- HEAD SHA: `d18ed84f058290b36652f50db41875f2cafbaa4c`
- the exact `git diff --ignore-cr-at-eol` command run against that tree and its output (expected
  empty — re-run it yourself in the Developer session; do not copy this document's run)

### 1.3 Open question for the Developer session to resolve and record (not mandated here)

`ft8/decode.c` and `common/monitor.c` (the two MSVC-VLA-patched files) are **already tracked** at
`native/ft8_lib_build/patched/`, documented in `src/OpenWSFZ.Ft8/Native/BUILD.md`. D1 does not
strictly require moving them — the vendor directory can hold everything else and `BUILD.md` can
point to both locations. Two reasonable options, pick one and say which in the PR:
- **(a)** leave the patched files where they are (less churn, `BUILD.md` already documents them
  there), vendor only the unpatched remainder into `native/ft8_lib_vendor/`; or
- **(b)** consolidate everything under one vendor root for a single source of truth, updating
  `rebuild_shim.bat`'s `/I` and source paths accordingly.

Whichever is chosen, `rebuild_shim.bat` (D2) must reference the real, final paths — this is why D1
and D2 land together in one commit, not two.

### 1.4 What NOT to do (spec §2, restated)

- 🛑 Do not vendor `.git/`, test corpus, or build detritus.
- ⚠️ **Do not "tidy" the sources while vendoring** — no reformatting, no line-ending
  normalisation, no warning fixes. Whatever is on disk today is what built the shipped 20260038
  DLL; capture it as-is, or AC-1's equality check measures the cleanup instead of the build.
- Report the total committed size (spec's own instruction, §5 reporting).

---

## 2. D2 — `rebuild_shim.bat` rebuilds every translation unit from vendored sources

No pre-built object may be linked. The build must start from an **empty** `obj/` directory
(`native/ft8_lib_build/obj/` — currently gitignored except the one tracked `message.obj`, which
this task makes redundant; consider whether to remove that gitignore carve-out once D2 lands) and
produce a complete DLL. Keep the existing `/EXPORT:` list in `rebuild_shim.bat` **unchanged** —
eleven exports, unmodified by G2(a) or this task.

Concretely: add `cl` compile steps for the nine currently-linked-not-built objects (§0), pointing
at the D1 vendor tree via `/I`, before the existing `link` step. The existing `decode.c`/
`ft8_shim.c` compile steps and the `link` step's object list stay as-is in *content* (same eleven
inputs) but now every one of them is a same-session build output, not a stale artefact.

---

## 3. AC-1 through AC-4 — required verification, all mechanical (spec §4)

**AC-1 (primary): behavioural equality against the pinned baseline.**
Build the DLL from vendored sources per D2. Replay a fixed corpus subset (**≥ 200 contiguous
cycles** from the pinned 20m corpus, `artefacts/20260808_live_run_0016-8080/` — report the exact
cycle range) through **both** the new DLL and the pinned `c559a049…`/20260038 DLL, same input,
same parameters, same order.
> **PASS:** decode output **byte-identical** — same decodes, same order, same `freq_hz`/`dt`/SNR,
> every cycle. **FAIL:** any difference at all.
The comparison must be a **mechanical diff of serialised output** — never an eyeballed summary or
a count-of-decodes match.

🔴 **Evaluate both branches before running (HK-021(k)):**
- **PASS** ⇒ vendored sources genuinely reproduce the shipped binary; R1 proceeds on a
  trustworthy foundation. Expected outcome.
- **FAIL** ⇒ 🔴 **the shipped DLL does not correspond to its nominal sources** — a finding about
  everything already published off that binary (X3 in particular, pinned to it), not merely a
  blocker for this task. **STOP. Do not adjust sources to force a PASS. ESCALATE to the Architect/
  Captain immediately, through QA.**

**AC-2: reproducibility.** Two clean builds (empty `obj/`, fresh checkout) must produce DLLs whose
**decode output** is byte-identical to each other on the AC-1 subset. Do **not** require the DLL
*files* themselves to be byte-identical — MSVC embeds a build timestamp; behaviour is the
contract, not the binary.

**AC-3: version hygiene.** The R0 DLL asserts shim **20260039** at startup (this task's own shim
version, per the spec header — distinct from G2's 20260038). `ft8_shim.h` and `Ft8LibInterop.cs`
must agree. Record the new DLL's SHA256 in the report.

**AC-4: licence hygiene — mechanical.**
> PASS requires all four:
> 1. `THIRD-PARTY-NOTICES.md` exists at the repo root (D5) and reproduces, in full, the MIT text
>    with Kārlis Goba's copyright **and** the BSD-3-Clause text with Mark Borgerding's;
> 2. every vendored source file's own licence header is present and **unmodified**;
> 3. **no vendored file is GPL- or AGPL-licensed** — scan the vendored tree for `GNU General
>    Public`, `GPL`, `Affero`; report every hit with file and line;
> 4. `ft4_ft8_public/` is **absent** from the vendored tree.

⚠️ Check 3 will **legitimately hit `ft8/constants.h` lines 75 and 78** (WSJT-X-derived LDPC table
comments) — Captain-ruled, flagged-not-blocking, expected, does **not** fail AC-4. 🛑 Any *other*
hit does. 🛑 **Do not "fix" the expected hit by deleting the attribution comments** — that is the
only record of where those tables came from and removing it makes provenance worse.

---

## 4. D3 — Fix `p23_common.py:182` (QA tooling, bundled into this task per the spec's §6)

`qa/cycleframer-alignment-replay/p23_common.py:182`:
`ref = {k: a[k] for k in a.keys() & b.keys()}` iterates a hash-randomised set — a fixed
`random.Random(seed)` still draws different *indices* across processes because set iteration order
is per-process-random over string keys. **Fix: sort at construction**, the same fix already applied
in `x4_spectral_locality.py` / `x3_lattice_crowding.py` (grep those two files for the pattern used
and match it, don't re-derive a new one).

🔴 **Why this matters and can't be skipped:** P2/P3/P1a's "two runs, byte-identical" determinism
claims are **UNVERIFIED, not confirmed**, specifically because of this bug — they ran pre-fix. R2
(the next spec in this programme) depends on `p23_common.py`, so this must land before R2 starts,
not just before R0 closes.

---

## 5. D4 — `--assert-dll-sha` on the replay harness (QA tooling, bundled per spec §6)

Add (if not already present — check `p23_common.py` and `g2_verification_replay.py` first, this
may partially exist) a capability so every downstream replay run pins the binary it is handed by
SHA256 and **fails loudly** on mismatch, rather than silently running whatever DLL happens to be on
disk. 🔴 **The SHA is the authority; the shim version integer is not** — it has already collided
twice (20260034/20260035 across unmerged branches). Wire this into R0's own AC-1/AC-2 replay so
those two runs self-verify which binaries they actually compared.

---

## 6. D5 — `THIRD-PARTY-NOTICES.md` at the repo root

**Real, pre-existing compliance gap, not optional.** Audit finding 2026-08-11: the repository
ships **no** third-party attribution today — no `NOTICE`, `THIRD-PARTY`, `COPYING`, nothing. Both
licences below require their notice to travel with the distribution.

| component | licence | obligation |
|---|---|---|
| **ft8_lib** (`ft8/`, `common/`) | **MIT**, © 2018 Kārlis Goba | copyright notice + permission notice in all copies or substantial portions |
| **KISS FFT** (`fft/kiss_fft.c`, `kiss_fftr.c`, `_kiss_fft_guts.h`) | **BSD-3-Clause**, © 2003–2010 Mark Borgerding | binary redistribution must reproduce the notice in accompanying materials, plus the no-endorsement clause |

✅ **KISS FFT stays** — Captain ruled BSD-3-Clause acceptable under the MIT-compliance policy; it
needs attribution, not removal. ⚠️ The upstream KISS FFT header says *"See COPYING file"* but **no
`COPYING` file exists in the vendored `fft/` directory** — reproduce the BSD-3-Clause text **in
full** in the notices file rather than pointing at a file we don't ship.

🔴 **Also record, FLAGGED-NOT-BLOCKING (Captain's ruling):** `ft8/constants.h` lines 75/78 credit
WSJT-X as the source of the LDPC parity tables (`ldpc_174_91_c_reordered_parity.f90`,
`bpdecode174.f90`). Inherited from upstream `ft8_lib`, not introduced by us. Captain's ruling:
**flag it, do not block** — LDPC parity matrices are FT8 **protocol constants** any conformant
implementation must reproduce identically. 🛑 Record plainly, do not stop the programme for it, do
not re-open without a new ruling.

⚠️ QA/Architect/Developer are not lawyers and this is not a legal opinion — an accurate record of
licences as found on disk. Professional review before third-party distribution at scale is the
Captain's call, outside this task's scope.

---

## 7. Sequencing

1. **D1 + D2 together, one commit** (§1.3's path choice affects both).
2. **AC-1/AC-2/AC-3** — run before anything else lands on top; this is the gate that decides
   whether the rest of the task even proceeds (see AC-1's FAIL branch above).
3. **D5** (`THIRD-PARTY-NOTICES.md`) + **AC-4** licence scan — needs D1's vendored tree to scan.
4. **D3** (`p23_common.py:182`) — independent of D1/D2, can land any time, but must land before R2.
5. **D4** (`--assert-dll-sha`) — independent, but most useful once D1–D3 are in so it can be
   exercised on the AC-1/AC-2 replay itself.

---

## 8. What R0 must NOT do (spec §3, restated)

🛑 **No change to decoder behaviour.** No parameter change. No `K_MAX_PASSES`, no candidate caps,
no passband, no OSR, no LLR scaling. If a source file must be edited to compile, **report it as a
finding**, do not make the edit silently and move on.

---

## 9. Reporting (spec §5)

The Developer session's report back to QA must carry:
- upstream remote + HEAD SHA, plus the `git diff --ignore-cr-at-eol` output (expected empty);
- old and new DLL SHA256, and the shim integer;
- the AC-1 cycle range, the diff command used, and its exit status;
- the AC-4 licence scan output **in full**, including the two expected `constants.h` hits;
- the committed vendored size;
- **for AC-1 FAIL: which decodes differ and how**, before any diagnosis is attempted.

---

## 10. Boundaries (HK-011/HK-010/HK-014/HK-006, restated)

- The Developer session runs `opsx:apply`: build clean, existing `OpenWSFZ.Ft8.Tests` suite green
  (currently 306/306 on the G2(a) baseline — re-verify, don't assume it stays 306 after this task).
  **Nothing beyond build + tests** — no `pre_merge_check.py`, no push, no merge, no request for
  either.
- The Captain reviews the diff and decides on merge; QA does not declare readiness unprompted.
- **NFR-021:** every before/after number in the PR description is a count or a rate. No example
  callsigns beyond the Q-prefix synthetic ones already permitted in VCS.
- If this touches anything under `openspec/`, HK-002's pre-merge audit applies.
- 🛑 **Licence policy (programme §2.1):** permissive only — MIT / BSD-2 / BSD-3 / ISC. **No GPL-
  derived code may be copied in, from WSJT-X or anywhere else.**
