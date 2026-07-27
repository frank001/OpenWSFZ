# D-001: Architect → QA consolidated handoff — where the study stands, what was withdrawn, and QA's four tasks

**Author:** Architect, 2026-07-27 (17:52 UTC, `date -u`, per HK-017). **For:** QA (to review and act
on), and the Captain (§2, §7).
**Supersedes as the single point of reference:** every Architect note from 14:44 to 17:38 today. Those
remain the detailed record; **this document is the one to work from.**
**Written to stand alone** — a QA session that has read none of today's notes should be able to act
from this document alone.

---

## 1. How to read this

§2 is where the study stands. §3 is what must **not** be cited any more. §4 is QA's task list — four
items, one of which is standing. §5 is what is explicitly *not* QA's. §6 is what I still owe. §7 is
the process changes that came out of today.

**Nothing in §4 is a Developer-facing artefact.** Per HK-015 the `dev-tasks/*.md` files are QA's to
author; two of the four tasks *are* "author a dev-task," and the design content they need is given
inline so QA does not have to reconstruct it.

## 2. Where the study stands

### 2.1 The prize, unchanged

**437 messages.** It has not moved through any arm, on either corpus. Six arms and an afternoon of
withdrawals later, the quantity the row-4-vs-row-5 decision rests on is the stable part of this study.

### 2.2 What is now excluded as the mechanism

Each of these is a measurement, not an inference:

| mechanism | verdict | evidence |
|---|---|---|
| **Pure sensitivity** | Minority contributor | ΔSNR = **2.62 dB** (R.4, corrected); real-corpus marginal shift **7.4% / 6.8%** (R.4b, with a zero-shift control) |
| **Demodulation on clean signals** | Excluded | **147/147** — we match jt9 exactly on isolated synthetic signals across the whole high-SNR plateau (R.4, once the out-of-band slot is removed) |
| **Candidate capacity / cap truncation** | Excluded | C.1: 300 and 600 give **byte-identical** decode sets; population plateaus at ~220–295/cycle; answer is **+12 decodes**, 1.6% of the gap |
| **Band limits** | ~1–2%, closed | Below `f_min`: **0.76% / 1.96%** of the miss population. Above `f_max`: 0.00% / 0.21%. WSJT-X decoded nothing meaningful above 3000 Hz on either corpus |
| **Harmonics / audio-chain distortion** | Excluded | Averaged FFT over 6 cycles: 3000–4000 Hz sits at **−65 dB** (SSB filter skirt), bounding post-filter nonlinearity at **≤ −49 dBc**. Also: a harmonic of an 8-FSK signal has doubled tone spacing (6.25 → 12.5 Hz) and cannot decode as FT8 |
| **Co-channel (cycle-density proxy)** | Not supported; bet withdrawn | +5.8 points corpus 1, **+1.6 corpus 2** — no replication. The rescue was tested and failed: corpus 2 has *more* density spread (p90/p10 **1.84** vs 1.57), not less |

### 2.3 What remains open — the one live statement

> **Whatever costs us the 437 is a property of real received audio that isolated synthetic buffers do
> not have.**

The sharpest form of it: at −14 dB on isolated synthetic signals we decode **100%**; at ≥ +5 dB on
real corpus audio — far stronger — we decode **89.8% / 89.0%**. That persistent ~10% strong-signal
deficit is the structural core of row 4, and band limits account for only 1–2 points of it.

Named candidates, none yet measured directly: co-channel collision at close frequency spacing
(*proximity*, not cycle density — the crude proxy is what failed); channel effects absent from the
synthetic generator (fading, drift, multipath); or something in our own capture/processing chain
ahead of the decoder.

### 2.4 Merge-relevant state

- **The `libft8` size blocker is cleared.** The `tls_diag_llr174` compile-time gate took the Windows
  DLL from 158,208 → **60,416 bytes** and `.tbss` from 100,208 → 2,768. Verified independently.
- **One pre-merge requirement remains**: the shim version misdescribes the binaries (§4, Q1).
- The branch remains **+4,608 bytes over `main`**, which is expected — two new exports and the small
  `tls_diag_*` scalars. Do not let "back to baseline" harden into "no delta."

## 3. Numbers and readings that must NOT be cited

These were withdrawn today. If any appears in a future findings doc, task spec or Captain-facing
summary, that is a defect:

| withdrawn | replacement |
|---|---|
| **ΔSNR = 2.86 dB** | **2.62 dB** (independently verified two ways, agreeing to three decimals) |
| **"6.3% / 6.2%" step-model recovery** | **7.4% / 6.8%** marginal, from R.4b's shift model *with* its zero-shift control |
| **"Anti-correlation"** (R.1b row 2) | Rows 1 and 2 collapse: *no demonstrable location information at lattice resolution*. The null was never strength-matched |
| **"Row 4 is an indivisible commitment"** (R.4's design table row) | **Not applied.** The curve is small because sensitivity is the *wrong axis* — a different result, and not evidence for row 5 over row 4 |
| **"Symbol demodulation → LLR sign correctness is where the residue lives"** | Withdrawn 19:00; 147/147 now positively contradicts it |
| **THE 135 / THE 567's BER interpretation** | The measurements stand; reading them as "our demodulator produces wrong bits on located signals" does not |

## 4. QA's tasks

### Q1 — Author the dev-task for the shim version correction ⟨pre-merge requirement⟩

**Why:** the gate changed the shipped binary's observable behaviour under an unchanged version.
20260035 before the gate returns real LLR data in the default build; 20260035 after the gate returns
zeros. Same version, same default configuration, different behaviour. Sharpened by CI: the Linux
`.so` and macOS `.dylib` are auto-rebuilt from current `ft8_shim.c` on every push and never set the
capture flag, while the Windows DLL is built by hand and could be either — so **three platform
binaries can differ in capability while all reporting the same version.**

**Design content for the dev-task (four parts, all small):**

1. **Bump `FT8_SHIM_VERSION` 20260035 → 20260036** (`src/OpenWSFZ.Ft8/Native/ft8_shim.h:333`) and
   `ExpectedShimVersion` (`src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:246`).
2. **Add `ft8_get_shim_capabilities()`** returning a bitmask — bit 0 = raw-LLR capture compiled in,
   remaining bits reserved. A version cannot express a build-time variant; this is the part that can.
3. **Managed:** read capabilities in `LoadAndVerify`, log them at startup beside the version, and make
   `SetCandidateDiagLlrCapture(true)` **throw** when the loaded binary lacks the capability — at the
   moment the workflow asks, not after it has collected a cycle of zeros.
4. **Defence in depth:** `ft8_get_last_candidate_llr` returns **−1** (not 0) from its gated-off branch
   (`ft8_shim.c:1301–1305`), and `Ft8LibInterop.GetLastCandidateLlr174` (`:754–771`) stops collapsing
   `n <= 0` so that −1 ("capability absent") is distinguishable from 0 ("no rows").

**Acceptance criteria to write in:** the ABI check must reject a 20260035 binary; a gate-off build
must report capabilities bit 0 clear and a gate-on build must set it; `SetCandidateDiagLlrCapture(true)`
against a gate-off binary must throw rather than silently no-op; and the existing suite must stay
green. **Note for the review:** all eight test files touching `GetLastCandidateLlr174` do so through
**mocks** of `IFt8NativeInterop` — a green suite alone does not prove the native surface. The real
coverage comes from `Ft8Decoder.cs:402–403` (unconditional calls every cycle) plus the real-interop
decode tests.

**Scope discipline:** one `#define`, one small export, one managed constant, one guard. Not a redesign
of the diagnostic surface.

### Q2 — Author the `MaxPass0Candidates` guard dev-task ⟨long owed⟩

**Why:** my 2026-07-26 20:30 ruling said "the third time it happens it should become a guard that
errors rather than truncates." **It has now happened five times** — C.4's `MaxPass0Candidates=140`
truncation, THE 567's 279/567 subsample, C.1's stale-DLL run, R.4's out-of-band slot 7, and the
gated-off silent zero (Q1 part 4). I checked `dev-tasks/` before writing this: **no such task has
been authored.**

**Shape:** a diagnostic export that fills its capacity should be an error or a loud warning carrying
the truncated count, not a silent head-take. The managed side should surface it, not swallow it.
Exact form is QA's call.

### Q3 — Resolve the uncommitted `src/` state ⟨housekeeping, but not trivial⟩

`git status` shows **679 insertions across 20 files uncommitted** on this branch — `ft8_shim.c`,
`ft8_shim.h`, both binaries, the managed interop, and eight test files. The last commit touching
`src/` is `593c212` (the C.4 sweep). Some of this predates today; the TLS gate was applied on top.

An afternoon-plus of Developer work is sitting unstaged, and **Q1 would modify `ft8_shim.h` on top of
it.** Either get it committed or record an explicit decision not to — but it should not stay
accidental. Per HK-014 I do not commit `src/` myself, and per HK-011 this is QA/Developer territory.

### Q4 — R.3 remains held ⟨standing, nothing to run⟩

Do not start R.3. Both its axes are dead: the candidate-cap axis was already answered by C.1 (§2.2),
and Arm A's isolated geometry cannot reproduce the loss it was meant to attribute (§2.3). **There is
no arm to run until I deliver the replacement design** (§6).

## 5. What is explicitly NOT QA's to do here

- **No `src/` or native edits** (HK-011) — Q1 and Q2 are *authoring dev-tasks*, not applying them.
- **No push, no merge** (HK-010/HK-014). **No `pre_merge_check.py`** — Captain's trigger only, HK-006.
- **The sub-200 Hz band floor is a logged non-priority**, not a task. 0.76%/1.96% does not buy an
  NFR-018 false-positive exposure plus a Developer session. Bundle it into some future native change
  if one comes along; do not chase it.
- **Branch disposition and the `main` merge remain the Captain's.**
- **No new arm.** §2.3 names candidate mechanisms; none of them is authorised as work.

## 6. What I still owe

1. **The R.3 replacement design.** Per HK-018 (added today) it starts with a pass over what the B- and
   C-series already answer, *before* I propose anything. It will carry §2.2's exclusions and the
   harmonics result as its candidate-mechanism list.

That is the whole list. The `libft8.dll` size ruling and the version correction are both delivered.

## 7. Process changes from today, worth QA knowing

- **HK-017** — dated filenames and bylines carry real `date -u`/`git log` UTC, never hand-typed; the
  two must agree.
- **HK-018** (new, from the Captain) — in the Architect role, open the data already gathered before
  concluding. Four wrong rulings today all had their answer already on record.
- **Band-intersection check** — before any gap between two decoders is attributed to algorithm
  quality, state and verify the search band each one used. Every arm's output header should carry it.
  This caught two live defects today.
- **Flat SNR-independent offsets between two decode curves** are to be treated as suspected harness
  defects until excluded, never as curve shape.
- **Frequency estimates are clamped at `f_min`** — a decode reported at exactly 200.0 or 3000.0 Hz is
  a censored value, not a measurement. Relevant to any matcher built near the band edges.

## 8. Cross-references

Today's Architect notes, in order — retained as the detailed record:

- `2026-07-27-1444-architect-r1b-ruling-and-r3-amendment.md` — R.1b row 2 rejected; R.2 deferred.
- `2026-07-27-1522-architect-r4-ruling-and-r4b.md` — ΔSNR corrected to 2.62 dB; 6.3% rejected.
- `2026-07-27-1555-architect-r4b-ruling-and-band-limits.md` — band limits; co-channel bet withdrawn.
- `2026-07-27-1603-architect-hold-r3.md` — R.3 held (Q4).
- `2026-07-27-1622-architect-dll-size-ruling.md` — the size blocker and its fix.
- `2026-07-27-1731-architect-tls-gate-accepted.md` — gate accepted, blocker cleared. **§3 withdrawn.**
- `2026-07-27-1738-architect-version-correction.md` — the correction Q1 implements.

Key prior evidence this handoff rests on:

- `2026-07-26-c1-candidate-cap-sweep-findings.md` §3–§5 — the cap sweep (§2.2).
- `2026-07-27-r4-sensitivity-gap-findings.md`, `2026-07-27-r4b-realworld-sensitivity-findings.md`.
- `2026-07-26-c3-candidate-generation-gap-findings.md` — the SNR split.
- `2026-07-27-1611-qa-band-floor-cycle-set-correction.md` — the corrected band-floor figures.

---

*Per HK-015 this is Architect → QA material: Q1 and Q2 are for QA to author as dev-tasks, not tasks
issued by me to a Developer. Per HK-014 this note is committed locally and goes no further. Per HK-011
nothing here touches `src/` or native code. The decision the study feeds — row 4 vs. row 5 — remains
the Captain's, on the Captain's clock.*
