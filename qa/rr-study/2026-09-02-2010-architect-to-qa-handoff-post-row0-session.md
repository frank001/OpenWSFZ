# Architect → QA — task handoff, 2026-09-02 20:10Z session

**Base `main`@`b4dd754`, shim `20260049`.** The PO gave a blanket go-ahead on the Architect's five
recommendations (A–E of the 2026-09-02 19:5xZ status). This records what the Architect did, and
hands QA the parts the Architect **may not** do.

Per HK-015 these are **QA's** tasks. No instruction to any Developer session has been issued here,
and §3 explains why one item deliberately stops short of that.

---

## 1. Done by the Architect this session — no QA action needed, listed so it is not repeated

| | Item | Result |
|---|---|---|
| **C** | Stop `OpenWSFZ.Daemon.exe` PID 37944 (left running from the prior sweep, holding `bin\Release` DLLs open) | **Stopped**, verified gone; `Win32_Process` swept for strays — none. ⚠️ Two `tail.exe` processes with `OpenWSFZ` in their command lines survive from an earlier session's `Monitor`; harmless, not this session's to kill, flagged per HK-019 |
| **E** | NFR-021 redaction of the `AWGN-FP` ROW 0 result directory | **Done.** 73 distinct tokens / 92 occurrences, all in `results/*_decodes.csv`; report prose clean. Re-scan after: **0/0**. Byte-level rewrite, BOM + CRLF counts asserted, all seven CSVs re-parsed at original dimensions. Map at `results/REDACTION-MAP.md` (placeholder ↔ one-way fingerprint) |
| **E** | `_work/` (610 WAVs, 210 MB) | **gitignored**, not committed — regenerable from the seeds in the committed `results/*_slots.csv` |
| **B** | The S5 `level_dbfs` finding | **Specced** — `2026-09-02-2002-architect-to-qa-spec-s5-level-normalisation-scope-and-repair.md`. See §2.1 |
| — | ROW 0d correction + Amendment 1 to the `AWGN-FP` spec | See §2.2. Both are Architect artefacts; QA executes the amended rows |

## 2. QA's tasks

### 2.1 `S5-LEVEL` — run the scoping spec (small, no capture, no rebuild)

`qa/rr-study/2026-09-02-2002-architect-to-qa-spec-s5-level-normalisation-scope-and-repair.md`.

🔴 **Read its §0 before anything else.** The scope is far narrower than the ROW 0 report's
Recommendation 2 implies — `level_dbfs` occurs in exactly four scenario files, all S5, and only
`s5-noise.json` varies it. **The S5 false-positive gate arithmetic is not affected and must not be
restated.** ROW 0f is the check that can overturn the whole spec; if it fails, stop and say so
rather than patching around it.

Ends with a **recommendation to the PO** between two repair options, not with a repair. Do not pick.

### 2.2 `AWGN-FP` M1–M4 — authorised, but run the AMENDED rows

The PO has authorised the N ≥ 2,000/part measurement (recommendation A). Before arming:

- 🔴 **ROW 2 and ROW 3 in the original spec body are SUPERSEDED.** Execute **Amendment 1** at the
  end of `2026-09-02-1906-architect-to-qa-spec-awgn-fp-offline-replay.md`. The originals tested
  **disjointness**, which is the wrong property — the exploratory data in the ROW 0 report §7.3
  would have fired the original ROW 3 and permanently closed a route the same data shows to be
  live. Amendment 1 replaces them with a threshold-and-margin test.
- 🔴 **A1.5 is the load-bearing line:** M3 must flag, per genuine decode, whether its message
  matches the injected truth for its own `(part, trial)`. ROW 0d's "336 genuine decodes" was
  really **250 genuine + 86 spurious**, and the spurious ones sit at the *low* end of the excess
  distribution — unflagged, they would poison the cost condition and force a false ROW 3.
- 🔴 **A1.0 discloses that the Architect de-blinded himself** on an adjacent population and that
  Amendment 1's two thresholds (6 dB, 10%) are anchored on peeked data. Architect
  prediction-scoring is suspended for these rows. If QA wants an unanchored gate, reject those
  numbers and set your own **before** running — that is a legitimate HK-025-adjacent call.
- **Operationally:** multi-hour unattended ⇒ HK-013/HK-023 treatment (validated supervisor,
  `nohup … & disown` with a PID check, disposable `tail -f` Monitor for notification only — a
  `Monitor`-owned process dies at session end). Not an ad hoc foreground `dotnet test`.
- The daemon lock that forced `-c Debug` is gone (§1, item C), so `-c Release` is available.

### 2.3 `FT8_SHIM_VERSION` renumber — **QA authors the dev-task; the Architect may not**

The PO signed off on the renumber recommendation (item D). **The Architect has not executed it and
will not**, because `ft8_shim.h` lives at `src/OpenWSFZ.Ft8/Native/ft8_shim.h` ⇒ it is a `src/`
change ⇒ **HK-011 in full** (QA authors `dev-tasks/*.md` and stops; a separate Developer session
applies; the Captain reviews the diff pre-push), and **HK-015** bars the Architect from writing a
Developer-facing artefact at all.

**Both collisions independently re-verified this session** at `main`@`b4dd754`, by content hash —
never by version string, per the standing rule that a shared version is only a collision if the
content differs:

| Version | Branches | `.h` differs | `.c` differs | Verdict |
|---|---|---|---|---|
| `20260034` | `d001-c2-llr-normalization` vs `d001-rc1-rc2-candidate-diagnostics` | ✅ `2dd38848` vs `9888eb61` | ✅ `0aeb76b9` vs `703ee05b` | 🔴 **REAL** |
| `20260035` | `d001-c4-min-score-sweep` vs `d001-rc4-decode-depth` | ✅ `5803433d` vs `eac5dfe8` | ✅ `7c43a33b` vs `09dff7ee` | 🔴 **REAL** |

15 unmerged branches confirmed (`git branch --no-merged main`), matching the 2026-09-02 re-measure.

🔴 **The previously-recorded recommendation collided with a pre-registered gate, and is CORRECTED
here.** It assigned `20260050`/`20260051` to the two branches. But `20260050` is already reserved by
the `F-001` L3 spec for `ft8_get_h12_unresolved_by_code`, and — decisively — that number is not
merely mentioned there, it is **load-bearing inside a pre-registered ROW 0a gate**
(`2026-09-02-1631-…-f001-l3-own-hash-compare-sizing.md:198`: *"Built DLL's `ft8_lib_version_check()`
≠ `20260050` … Wrong binary. STOP."*), and appears in six places including the ROW 0e
byte-identity check.

**Architect's ruling on the clash, made rather than punted:** L3's `20260050` **stays**. A
pre-registered gate that pins a specific number is load-bearing; the renumber targets are arbitrary
— chosen only to sit above `main`'s `20260049` — so they are the cheap side to move.

**Corrected recommendation** (Architect's, PO-approved in substance, *not* executed): renumber only
the two branches that are **not** the raw-LLR home —
`d001-rc1-rc2-candidate-diagnostics` **`20260034 → 20260051`**,
`d001-rc4-decode-depth` **`20260035 → 20260052`** — both above `20260050` so neither can collide
with L3 or with `main`.

⚠️ **Landmine for whoever writes the dev-task:** `d001-c4-min-score-sweep` is on a colliding pair
*and* carries fresh commits (`6fd94b2`, `f44c854`). It keeps `20260035` under this recommendation,
and `rebuild_diag_llr.README.md` on that branch references the number — if the PO ever reverses and
renumbers *that* branch instead, the README must move in the same change.

### 2.4 `F-001` L3 — unchanged, still open

QA authors the dev-task for the measure-only `ft8_get_h12_unresolved_by_code` export under HK-011
and stops. The PO's ruling stands: the compare — **and the export itself** — is gated to
`tls_h12_multiplicity == 1`, and the power arithmetic must be **re-derived, not inherited**.
See §2.3 — the version-number clash is resolved in L3's favour, so `20260050` stands.

## 3. Unclaimed follow-ups — not assigned, listed so they stay visible

- **`nfr021_pre_merge_scan.py` has no directory mode.** `changed_files()` is
  `git diff --name-only base...HEAD`, so pointed at an uncommitted directory it prints
  "CLEAN — 0 text files" (HK-022 false green). Worked around twice now by importing its own
  `scan()`/`classify()` over a directory walk. Wiring it in properly is a real, small, unclaimed
  task.
- **`matcher.py`'s `false_positive` column is not scoped to each scenario's own play window**, so
  S8 traffic leaks into `S5_matched.csv` as spurious "S5 false positives" (routine sweep
  Recommendation 3). This is why S5 attribution needed a manual `cycle_utc`-vs-`truth.csv` join.

## 4. Nothing has been pushed

Per HK-014 the Architect commits locally and stops. This session's work is on a local branch; push,
PR and merge are QA's, and merge additionally needs the Captain's explicit sign-off (HK-010).
