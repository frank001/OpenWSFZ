# Developer handoff: G2 — `HASH_TABLE_SIZE` 256→4096, candidate passband widened

**Authored by:** QA (per HK-000/HK-015). **Status: AUTHORISED by the Captain** (2026-08-10, ruling
3 of 3: *"do a and b. we will look at FP later"*), specced in
`qa/cycleframer-alignment-replay/2026-08-10-1808-architect-to-qa-spec-g2-hash-table-sizing-and-candidate-passband.md`.
🔴 **Per HK-011 this document is a proposal, not approved work in itself.** A separate Developer
session runs `opsx:apply` (build + tests only — never `pre_merge_check.py`, that is HK-006, the
Captain's initiative alone). The Captain reviews the `src/` diff before any push or merge
(HK-010/HK-014). QA does not declare "ready for merge."

---

## 0. 🔴 The spec's own blocker is CLEARED — read this before starting

The spec's §3 named a blocker: `main`'s source read `FT8_SHIM_VERSION 20260033` while P2/P3/P1a
asserted shim `20260035` against DLL SHA `39aa1031…`, "those cannot both describe `main`," and a
Developer session was not to start until this was resolved.

**Traced and resolved this session**
(`qa/cycleframer-alignment-replay/2026-08-10-2042-qa-to-architect-shim-version-provenance-resolved.md`):
the DLL P2/P3/P1a ran is `d001-rc4-decode-depth`'s unmerged **three-pass diagnostic build**, not
`main`. `main`'s own committed decoder (`src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`, SHA256
`f2f30c890b253eb6b69aa1a89c26d2991ee70aa2a202c68361130344bb7d4015`) already correctly builds and
reports `FT8_SHIM_VERSION 20260033`, confirmed by direct `tools/check_native_version.py` run and
`git diff --stat HEAD` (byte-identical to the committed blob). **There is nothing to reconcile on
`main` itself — the confusion was entirely an off-tree DLL QA's harnesses had pinned.**

**Per the spec's own instruction, the new shim version for this change is `20260038`**
(20260034–20260037 are reserved: two are claimed by unmerged branches, colliding; two are W2's
proposed renumbering targets, not applied). Bump both `FT8_SHIM_VERSION`
(`src/OpenWSFZ.Ft8/Native/ft8_shim.h:297`, currently `20260033`) and `ExpectedShimVersion`
(`src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:224`) together, in the SAME commit as whichever of (a)/
(b) lands first (see §3).

---

## 1. Item (a) — `HASH_TABLE_SIZE` 256 → 4096

### 1.1 Where and why

`src/OpenWSFZ.Ft8/Native/ft8_shim.c:563`: `#define HASH_TABLE_SIZE 256`. The table keys on a
**10-bit bucket** (`h10 = (hash >> 12) & 0x3FF`, line 601; a shifted variant at line 575 for a
second call site), giving exactly **1024** possible key values. First-probe placement is
`idx = (h10 * 23) % HASH_TABLE_SIZE` (line 576) — `gcd(23, N) = 1` for every power of two, so this
placement is **injective up to N = 1024**. At the current `N = 256` it collides **4:1 by
construction, before the table is even full.**

Measured cost: `hashTableRejectCount` = **35 379** on the 2026-08-08 20m leg (against 595 across
C.1's entire 68-cycle corpus) — a huge jump attributable to sizing, not to genuinely running out of
distinct callsigns. H1 measured **5.5% of our decodes carry `<...>`** against the reference's
**1.7%**.

**Change:** `HASH_TABLE_SIZE` 256 → **4096** (64 KB; up from 4.0 KB). 1024 is the bijective floor
for the 10-bit key space; 4096 adds 4× probe headroom for distinct callsigns that share a 10-bit
bucket (unbounded population against 1024 buckets).

### 1.2 🛑 What must NOT change

The table is **session-scoped, never re-initialised, by design** (f-001, decisions D1/D2/D3) — a
Type 4 message decoded in an earlier cycle must stay resolvable later and across thread-pool
threads. **Do not add re-zeroing per cycle or per call.** The defect being fixed is sizing, not
lifetime. Keep `g_hash_table_reject_count` and `ft8_get_hash_table_reject_count()` exactly as they
are — do not remove the counter, and do not add an eviction policy (LRU or otherwise); that is a
larger, separately-authorised change if the counter still fires materially after this fix.

### 1.3 What this change does and does not buy

✅ Message **text** — fewer `<...>` shown where a resolvable callsign exists.
🛑 **Zero additional decodes.** `message.c:594-614`'s two call sites already discard hashed
callsigns' resolution failures without affecting whether a decode is produced at all — this is a
display/matching fix, not a recall fix. State this plainly in the PR description so it is not read
as a D-001 recall change.

### 1.4 Required verification (spec §1.4, transcribed)

1. **New unit test** (native or via interop — does not exist today): insert > 256 distinct
   callsigns into the table, assert every one still resolves by hash, and assert
   `ft8_get_hash_table_reject_count() == 0` at the end.
2. **Regression on a frozen corpus:** replay a 20m window before/after; assert **decode count is
   unchanged to the decode** (this must not move recall in either direction — it is purely a
   text/matching fix). The 20m weekend corpus (`artefacts/20260808_live_run_0016-8080/`) is the
   natural choice; reuse `p23_common.py`'s `Decoder`/`read_wav`/`normalise_rms` machinery rather
   than writing new replay plumbing.
3. **Report the new `hashTableRejectCount`** on a full 20m leg replay. If still non-zero, say so —
   do not round it to zero or omit it.

---

## 2. Item (b) — candidate passband widened

### 2.1 Where and why

`src/OpenWSFZ.Ft8/Native/ft8_shim.c:1183`, the `monitor_config_t` literal:
`.f_min = 200.0f, .f_max = 3000.0f`. This bounds the waterfall's extent, so a signal outside it is
**missed by construction, 100% of the time** — RC1 attributes 3.1% of misses to this; S.1r counted
exactly 50 such records across five runs (47 below 200 Hz, 3 above 3000 Hz — a ~94%/6% split at the
low end).

### 2.2 🔴 The boundary, derived from the corpora (HK-018 — computed this session, not argued)

Per the spec's explicit instruction not to accept a number from the Architect's own instinct
(~100–3600 Hz stated as instinct, not evidence): the reference decode-frequency distribution was
computed from all three corpora's WSJT-X `ALL.TXT` (both instances pooled, in-window, all Rx FT8
rows — not just the doubly-confirmed `REF` intersection, since the passband question is about what
is audible at all, not what both instances happened to agree on).

| band | n rows (pooled, both instances) | below 200 Hz | above 3000 Hz |
|---|---:|---:|---:|
| 20m | 138 732 | 1 606 (1.16%) | 144 (0.10%) |
| 17m | 78 756 | 404 (0.51%) | 31 (0.04%) |
| 80m | 21 894 | 110 (0.50%) | 6 (0.03%) |
| **pooled (all 3 bands)** | **239 382** | **1 993 (0.83%)** | **181 (0.076%)** |

The low-end asymmetry S.1r reported (~94% of the loss) is confirmed at this larger scale too: the
below-200 Hz population is consistently **~5–11× larger** than the above-3000 Hz population, per
band and pooled.

**Recommended boundary: `f_min = 140.0f, f_max = 3030.0f`** — covers **99.90%** of the pooled
reference population (0.048% below 140 Hz, 0.048% above 3030 Hz — deliberately close to symmetric
in what remains uncovered, even though the *extension* is asymmetric: −60 Hz at the low end vs
+30 Hz at the high end, directly reflecting the measured skew). Width 2890 Hz against today's
2800 Hz — **+3.2%**, far cheaper than the ~100–3600 Hz instinct's +25%, while recovering nearly all
of the measured loss. **State this stated-percentile derivation in the PR description**, per the
spec's requirement that the boundary be justified, not asserted.

⚠️ **This percentile computation is QA's own, done for this proposal, not re-derived by the
Developer session** — reuse it rather than re-running the analysis; the corpora and windows are
`t1_frequency_quantisation.LEG_20M`/`x1_cross_band_decomposition.LEGS` for 17m/80m, unmodified.

### 2.3 Costs to measure, not assume

- **Memory/CPU scale with `(f_max − f_min)`.** Measure the actual waterfall allocation size and
  per-cycle decode wall time before/after on the same 20m window; the 15 s cycle budget is the
  constraint that matters, not a percentage in the abstract.
- **Candidate-cap interaction.** `K_MAX_CANDIDATES` (140, pass 1) and `K_MAX_CANDIDATES_PASS2`
  (200, pass 2) are already saturated 95%/90% on busy cycles. 🛑 **Do not raise either cap to
  compensate** — that family is closed twice (RC2) and bounded at +0.93% (C.1). Report whether
  saturation *worsens* after widening (via `ft8_get_last_candidate_counts()`, already exported and
  logged per cycle); if widening displaces in-band candidates, **that is a finding to report
  upward, not something to fix in this change.**

### 2.4 Required verification (spec §2.4, transcribed)

1. Replay a frozen 20m window before/after; report **decodes gained**, and confirm the gained
   decodes' `freq_hz` actually falls in the newly-opened `[140,200)` / `[3000,3030)` ranges (if
   not, something unintended happened and that is a stop-and-report condition, not a thing to
   paper over).
2. Report per-cycle decode **wall time** before/after against the 15 s budget.
3. Report candidate-cap saturation before/after per pass.

### 3.3 FP instrumentation — recorded, NOT gated (Captain's ruling, spec §3.3 numbering kept as-is)

Record the standing FP proxy before/after on the same window: novel-decode count, and the share of
novel decodes whose callsigns appear nowhere in the reference across the full leg (the 9.1%/86.7%
split from the 08-08 comparison is the existing baseline to compare against). ⚠️ **Report the
numbers. Do not gate this change on them, and do not draw an FP conclusion in this PR** — the point
is only that the deferred FP decision does not later require a second re-run to get this data.

---

## 3. Sequencing — one branch, two commits, separately revertible

**(a) first, then (b), separately** — per the spec's own ordering (a is smaller, provably cannot
change recall, and its regression test is a clean equality assertion; b's recall/timing effects
should be attributable to b alone, not entangled with a's `<...>` change).

- **Commit 1:** item (a) — `HASH_TABLE_SIZE` 256→4096, the new unit test, the 20m regression
  (decode-count-unchanged assertion), the `hashTableRejectCount` report. Bump
  `FT8_SHIM_VERSION`/`ExpectedShimVersion` to **20260038** in this commit (the ABI/ behaviour
  changes even though the wire struct does not — same convention the shim's own history uses for
  a native constant change).
- **Commit 2:** item (b) — the passband widening, its own verification (§2.4), and the FP
  instrumentation report (§3.3). Bump the shim version again if the project's convention treats
  each behaviour-affecting native change as its own version (check recent history — several past
  commits bump once per `src/` session rather than once per commit; follow whichever the Developer
  session finds is the live convention, and say which was chosen).
- Both commits touch `ft8_shim.c`/`ft8_shim.h`/`Ft8LibInterop.cs` but not the same lines within
  those files (§1's constant vs §2's struct literal) — confirm this stays true so either commit
  can be reverted alone without touching the other's code.

---

## 4. What this task deliberately does not do

Per the spec's own §5, unchanged here:

- 🛑 No change to `K_MAX_CANDIDATES`, `K_MAX_CANDIDATES_PASS2`, `K_MAX_PASSES`, `K_FREQ_OSR`,
  `K_TIME_OSR`, any OSD parameter, or `PcmNormalisationTargetRms`. Each of those families is either
  closed by measurement or needs its own pre-registration — this task does not reopen any of them.
- 🛑 No eviction policy for the hash table.
- 🛑 No FP gate. FP is instrumented, not decided, here.

## 5. Boundaries (HK-011/HK-010/HK-014/HK-006, restated)

- The Developer session runs `opsx:apply`: build clean, existing test suite green, the two new/
  extended tests above green. **Nothing beyond build + tests** — no `pre_merge_check.py`, no push,
  no merge, no request for either.
- The Captain reviews the diff and decides on merge; QA does not declare readiness unprompted.
- **NFR-021:** every before/after number in the PR description is a count or a rate. No example
  callsigns, hashed or otherwise, beyond the Q-prefix synthetic ones already permitted in VCS.
- If this touches anything under `openspec/`, HK-002's pre-merge audit applies.
