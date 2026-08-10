# ARCHITECT → QA — spec G2: two approved `src/` changes (hash-table sizing, candidate passband)

**Author:** Architect, 2026-08-10 (18:08 UTC, `date -u`, HK-017).
**For:** QA. **Authorised by:** the Captain, 2026-08-10 (ruling 3 of 3: *"do a and b. we will look at
FP later"*).
**Nature:** 🔴 **`src/` + native rebuild ⇒ HK-011 applies in full.** QA specifies, proposes and
**stops**; a separate **Developer session** runs `opsx:apply` (build/tests only, never
`pre_merge_check.py` — that is HK-006, the Captain's); the Captain reviews the diff.

---

## 0. Scope, and one concern stated once

Two independent, small, well-localised changes. **They are unrelated to each other and must be
separable** — one branch, two commits, so either can be reverted alone.

| item | change | what it buys | what it does NOT buy |
|---|---|---|---|
| **(a)** | `HASH_TABLE_SIZE` 256 → larger | **message TEXT** — fewer `<...>` shown to the user | 🛑 **zero additional decodes.** Hashed callsigns are never discarded (`message.c:594-614`, both call sites discard the return value) |
| **(b)** | candidate passband `[200, 3000)` Hz widened | **decodes** — RC1 puts 3.1% of misses out of band, a *certain* mechanism | nothing about the crowding term; this is orthogonal to D-001's main line |

⚠️ **Concern, stated once and then respected, per the Captain's ruling.** (b) enlarges the candidate
search space and therefore false-positive opportunity, against a standing FP level of **4.24–4.90%**
and an **open, unresolved post-fix FP surge** with no Task 5 ruling. The Captain has ruled FP is
looked at later. **This spec therefore does not gate on FP — but it does require FP to be
INSTRUMENTED (§3.3), so that when we do look, the before/after data already exists rather than
needing a re-run.** That is not re-litigating the ruling; it is making the deferred decision cheap.

---

## 1. Item (a) — `HASH_TABLE_SIZE`

### 1.1 The measured problem

- `hashTableRejectCount` = **35 379** on the 2026-08-08 20m leg (against 595 across C.1's entire
  68-cycle corpus).
- **5.5% of our decodes carry `<...>` against the reference's 1.7%** (H1, measured).
- Consequence for the user: a decode is produced, is correct, and displays an unreadable callsign.
- Consequence for QA: `<...>` rows cannot match by text, contaminating miss counts and FP proxies
  alike — H1 measured `M` = 2.26 pp of matching effect, and H1a's wildcard validation
  (`V` = 0.9968) is what currently works around it.

### 1.2 🔴 The size is derivable, not a guess — this is the part that matters

The table keys on a **10-bit bucket**: `h10 = (hash >> 12) & 0x3FF` (`ft8_shim.c:576, 602`), so the
key space has exactly **1 024** values. Placement is `idx = (h10 * 23) % HASH_TABLE_SIZE`, and
`gcd(23, N) = 1` for every power of two, so first-probe placement is injective **up to `N = 1024`**:

| `HASH_TABLE_SIZE` | memory | distinct first-probe slots over the 10-bit key space |
|---:|---:|---:|
| 256 (current) | 4.0 KB | **256 — collides 4:1 by construction, before the table is even full** |
| **1 024** | 16.0 KB | **1 024 — bijective; the natural size of the key space** |
| **4 096** *(recommended)* | 64.0 KB | 1 024 first-probe + 3 072 slots of linear-probe headroom |

**Recommendation: 4 096.** 1 024 is the principled floor — it makes `(h10 * 23) mod N` a bijection
on the key space, so no two *distinct* 10-bit hashes ever collide on first probe. But distinct
callsigns **do** share 10-bit buckets (1 024 buckets, unbounded callsign population), so a
long-running session needs probe headroom beyond the key space. 4 096 gives 4× headroom at 64 KB.

### 1.3 🛑 What must NOT be changed, and why the obvious fix is wrong

The table is **session-scoped and never re-initialised by design** — f-001-hashed-callsign-resolution,
decisions D1/D2/D3, so a Type 4 message decoded in an earlier cycle stays resolvable later and across
thread-pool threads. **Do not "fix" this by re-zeroing per cycle or per call.** That would destroy the
feature the table exists to provide. The defect is **sizing**, not lifetime.

⚠️ **Honest limit on this fix, and it should be recorded rather than discovered later:** any finite
never-reinitialised table saturates eventually on a multi-day daemon. 4 096 moves the wall, it does
not remove it. **Keep `g_hash_table_reject_count` and its getter.** If the counter still fires
materially after this change, the correct next step is an **eviction policy (LRU)**, which is a
larger change and is **not** authorised here — flag it, do not build it.

### 1.4 Verification required

1. **Unit test, native or via interop:** insert > 256 distinct callsigns, assert every one still
   resolves by hash, and assert `reject_count == 0`. This test does not exist today.
2. **Regression on frozen corpora:** replay a 20m window before and after; assert **decode count is
   unchanged to the decode** (this change must not alter recall in either direction) while the
   `<...>` share falls.
3. **Report the new `reject_count`** on a full 20m leg. If it is still non-zero, say so plainly.

---

## 2. Item (b) — the candidate passband

### 2.1 Where it lives

`ft8_shim.c:1181-1183`, the `monitor_config_t`: `.f_min = 200.0f, .f_max = 3000.0f`. This is the
waterfall's extent, so it bounds candidate search absolutely — **a signal outside it is missed by
construction, 100% of the time**, which is why S.1r had to exclude such decodes as a known unrelated
cause rather than treat them as evidence.

### 2.2 🔴 Derive the boundary from the corpora; do not accept a number from me

Measured evidence available: RC1 attributes **3.1% of misses** to out-of-band; S.1r counted exactly
**50** such records across five runs — **47 below 200 Hz, 3 above 3000 Hz**, i.e. the loss is ~94%
at the **low** end. That asymmetry is a real finding and should drive the change.

**Required before proposing a value (HK-018 — compute it, do not argue it):** from the three existing
corpora (20m, 17m, 80m, both WSJT-X instances), compute the **reference decode-frequency
distribution** and report the percentiles below 200 Hz and above 3000 Hz, per band. **Choose
`f_min`/`f_max` to cover a stated percentile of reference decodes, and state which.** My own instinct
is roughly `100–3600 Hz`, but that is an instinct, and the distribution is on disk. **Use the data.**

### 2.3 Costs to quantify, not assume

- **Memory and CPU scale with `(f_max − f_min)`.** A 100–3600 Hz band is 3 500 Hz against today's
  2 800 — **+25%** waterfall size and candidate-search work. Measure the actual waterfall allocation
  and per-cycle decode time before and after; the 15 s cycle budget is the constraint.
- **Candidate caps interact.** `K_MAX_CANDIDATES` = 140 / pass 2 = 200 are already **saturated
  (95%/90%)** on busy cycles. Widening the band without touching the caps means the extra spectrum
  competes for the same fixed budget. 🛑 **Do not raise the caps to compensate** — C.1 bounded that
  family at +0.93% and RC2 is closed twice. **Report whether saturation worsens; do not treat it.**
  If widening the band displaces in-band candidates, that is a finding and it belongs upstream.

### 2.4 Verification required

1. Replay a frozen 20m window before and after; report **decodes gained** and confirm the gained
   decodes actually sit outside the old band (they should, or the change did something unintended).
2. Report per-cycle decode **wall time** before and after against the 15 s budget.
3. Report candidate-cap saturation before and after (`ft8_get_last_candidate_counts()` — the getters
   are already logged per cycle; A1.5 established they have been there all along).

### 3.3 FP instrumentation — recorded, NOT gated (per the Captain's ruling)

Record the standing FP proxy before and after on the same window: novel-decode count, and the
share of novel decodes whose callsigns appear nowhere in the reference across the full leg (the
9.1% / 86.7% split from the 08-08 comparison). ⚠️ **Report the numbers; do not gate the change on
them, and do not draw an FP conclusion in this session.** The point is that the deferred FP decision
should not later require re-running this.

---

## 3. Sequencing, and a blocker that must be resolved first

🔴 **BLOCKER — the shim version on `main` does not match what QA has been running, and a Developer
session must not start until this is resolved.**

- `src/OpenWSFZ.Ft8/Native/ft8_shim.h:297` → `FT8_SHIM_VERSION 20260033`
- `src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:224` → `ExpectedShimVersion = 20260033`
- but P2 / P3 / P1a all asserted shim **20260035** against DLL SHA `39aa1031…`

Those cannot both describe `main`. Add to that the standing mess: **five unmerged `d001-*` branches
each carrying a rebuilt `libft8.dll`, with `FT8_SHIM_VERSION` colliding twice** (20260034 and
20260035 each claimed by two branches), and W2's renumbering proposal **approved by nobody and
applied nowhere**.

**Escalation, not a QA decision:** establish which source tree produced the DLL QA has been running,
before building a new one on top of it. **The new version for G2 should avoid 20260034–20260037
entirely** (the latter two are W2's proposed renumbering targets) — **20260038** is the first
unambiguously free integer. **The SHA, not the version integer, remains the authority for identifying
a binary.**

**Suggested order once unblocked:** (a) first — it is smaller, cannot change recall, and its
regression test is an equality assertion. Then (b), separately, so its recall and timing effects are
attributable.

---

## 4. Boundaries

- 🔴 **HK-011: QA proposes and STOPS.** A separate Developer session runs `opsx:apply` (build + tests
  only). The Captain reviews the diff. **QA does not run `pre_merge_check.py`** (HK-006) and does not
  declare "ready for merge" unprompted.
- **HK-014/HK-010:** no push, no merge, no request for one.
- **HK-002** applies if any `openspec/` file is touched.
- Per HK-015 this is Architect → QA; **`dev-tasks/*.md` for the Developer session are QA's to author**,
  not mine.
- **NFR-021:** any before/after evidence must carry counts and rates only — the `<...>` work is
  inherently about callsign text, so **report shares, never example callsigns**, except the Q-prefix
  synthetic ones permitted in VCS.

## 5. What this spec deliberately does not do

- 🛑 No change to `K_MAX_CANDIDATES`, `K_MAX_CANDIDATES_PASS2`, `K_MAX_PASSES`, `K_FREQ_OSR`,
  `K_TIME_OSR`, the OSD parameters, or `PcmNormalisationTargetRms`. Every one of those families is
  either closed by measurement or requires its own pre-registration.
- 🛑 No eviction policy for the hash table (§1.3).
- 🛑 No FP gate (§3.3), per the Captain's ruling.
