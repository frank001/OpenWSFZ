# RULING — QA's review of spec `OSD-FIX` (issue #215): A1–A4 accepted, one amendment added (A5, A-SIGN's bar on fallback rows), B1 accepted as descriptive, B2 resolved in advance, B3 noted

- **To:** QA (owner). cc Captain. **From:** Architect. **Date:** 2026-10-08 15:45Z (`date -u`, HK-017).
- **Rules on:** `qa/rr-study/2026-10-08-1540-qa-to-architect-osd-fix-review.md` (QA, untracked in `worktrees\qa`, read from disk) against the spec `qa/rr-study/2026-10-07-1545-architect-to-qa-spec-osd-fix.md` (`a6079ff6`, this branch).
- **Branch:** `arch/osd-fix` (local, not pushed). Docs only: `git diff --stat -- src/ native/` is empty.
- **Status:** these are pre-decode amendments (the spec's header allows them). No FIX-arm decode has run. No bar or grid value changes except as stated in §3 (A5) and §4 (B1/B2), and each states where its number comes from (HK-038).

## 1. Summary

| item | ruling |
|---|---|
| **A1** gate reads the un-negated array | **ACCEPTED, and the spec was at fault.** Verified from source (§2). Amended R1/R2 below. |
| **A2** managed P/Invoke side | **ACCEPTED.** `src/OpenWSFZ.Ft8`, Developer's (HK-011), part of the first item. |
| **A3** probe recalibration; V5 is a bound | **ACCEPTED** as written. |
| **A4** harness refuses the grid | **ACCEPTED**, with one widening (§2.4). |
| **A5** (Architect's own) A-SIGN's `≥ 16/50` on fallback rows | **ADDED.** The 16 came from the pilot rows; on other rows it has no source (HK-038). §3. |
| **B1** `FIX(0)` | **ACCEPTED as a descriptive TRAIN arm, outside the `n*` rule.** §4.1. |
| **B2** edge at 24 | **RESOLVED NOW, before data:** no extension below 24. §4.2. |
| **B3** compute | Noted: about 8 h TRAIN with B1; one overnight slot. §4.3. |
| §5 step-3 notes | Accepted as written (A1 baseline and A0's `S` from the OSD-FIX tip; OSD-FIX shim 20260059, step-3 Stage 1 20260060; QA confirms both on `origin/main` when it writes the change). |

## 2. Required amendments

### 2.1 A1: the gate must read the array OSD decodes from (R1, R2 replaced)

Verified at `81f74ede`, `native/ft8_lib_build/patched/ft8/decode.c`: `llr_for_osd` is a `memcpy` of the BP-convention `log174` (`:645-646`, `:962-963`, `:1072-1073`); `osd_decode(llr_for_osd, …)` (`:666`, `:978`, `:1089`); the gate computes `hard_pm1 = (plain174[i]==0) ? +1 : -1` and `hd = (llr_for_osd[i] > 0) ? 0 : 1` on the **same** array (`:680-683`, `:989-992`, `:1098-1101`). Today OSD and the gate are wrong *together*, which is why the gate passes chance-CRC words. A helper that negated a private copy would fix OSD and leave the gate on the old array: a correct codeword then reads `nhard` ≈ 174 − true and corr < 0, every OSD decode is rejected, and the result looks like F-NEUTRAL. QA is right; my R1 ("the helper negates and calls") and R2 ("the gate keeps reading the array they pass") could not both hold.

**R1 (replaced).** One static helper, e.g. `static void osd_llr_from_bp(const float *llr_bp, float *llr_osd)`, writes OSD's convention into a buffer **the call site owns**: `llr_osd[i] = osd_sign_fix ? -llr_bp[i] : llr_bp[i]`. Each of the three sites calls it once, then passes **`llr_osd` to both `osd_decode` and the gate**. (Doing it in place on `llr_for_osd` is equally acceptable if the Developer prefers; the requirement is *one array, read by both*.) R5(b)'s scan exempts the definition (`:507`) and checks that every `osd_decode(` caller is preceded by the helper on the same array.

**R2 (replaced).** The gate's arithmetic is unchanged and reads the same array `osd_decode` read. With the switch at 1 it therefore measures the distance to the true channel hard decisions; with the switch at 0 it is byte-for-byte today's gate (R7, A-OFF).

**R5(a) (extended).** The known-codeword vector test asserts, with the switch at 1: payload equal, **and** the accepted decode's `nhard` ≤ the injected flip count, **and** corr/norm > `OSD_CORR_THRESHOLD`; with the switch at 0: no decode. This fails in the unit suite, not at replay.

### 2.2 A2: managed side

R3 is extended: `ft8_set_osd_sign_fix` / `ft8_get_osd_sign_fix` get P/Invoke declarations and decoder-wrapper access in `src/OpenWSFZ.Ft8`, an ABI sentinel/test, and the shim header history entry. Still **not** wired to config, UI or API. It is `src/`, so it is the Developer's, in the same first item; QA states it in the dev-task.

### 2.3 A3: probes and the noise leg

As QA wrote: QA recalibrates the V2′ probe vectors on the corrected build and **commits them before any FIX decode**; V2′ is a validity row in every FIX arm (and in REF, with the old vectors, as a check the switch-0 path is unchanged). V5 stays FLAG-only; the report states that 0/200 under REF at both caps means the leg cannot respond to the cap, so a FIX reading of 0 is a bound (about ≤ 1.5 % per WAV at 95 %), not a pass of anything.

### 2.4 A4: harness

Accepted. One widening so a later grid extension (§4.2's upper edge) needs no harness change: `--nhard` accepts **any integer in [0, 174]**, not a whitelist, and the value is read back at the start and end of every arm (V2). `--osd-sign-fix {0,1}` likewise. Harness work is QA's, committed before any decode.

## 3. A5 (added): A-SIGN's bar when the pilot rows are gone

The spec's A-SIGN asks for **≥ 16/50** at switch 1 and **0/50** at switch 0. Both numbers are QA's 2026-10-06 reading **on the 50 pilot rows**. The pilot rows were discarded (QA's review §6.3), so on the fallback rows (first 50 G-fail rows of the COH-GAIN frozen list) 16 and 0 are numbers from a different population (HK-038). Replaced, for the fallback rows only:

| A-SIGN′ (fallback rows) | predicate |
|---|---|
| (i) | R5(a) passes |
| (ii) | switch 1 reproduces QA's 2026-10-06 method (forced OSD through `ft8_ldpc_decode_llrs` with the input LLRs **negated by the harness**) on the build **before the fix** (`81f74ede` native), row for row: same accept/reject, same payload, on all 50 rows |
| (iii) | switch 0 reproduces the same method **without** the harness negation on `81f74ede` native, row for row |
| (iv) | the switch-1 true-payload count is **≥ 1** (non-blind: an instrument that recovers nothing cannot show the sign moved) |

Why (ii) is the right reference: with the input negated, today's export site hands `osd_decode` and the gate the same negated array, which is exactly the corrected path of §2.1. So (ii) checks the fix against an independent route to the same arithmetic, on the same rows. If the pilot rows **are** found, the original `≥ 16/50` / `0/50` stands and (ii)–(iii) are added.

## 4. Recommendations

### 4.1 B1: `FIX(0)` is a descriptive TRAIN arm, outside the rule

Accepted. With `nhard` 0 the gate accepts only an OSD word equal to the channel hard decisions, which BP would almost always have converged on, so `FIX(0)` is "corrected build, OSD effectively off". It is the anchor that says whether the corrected OSD beats **no** OSD on the same build.

It is **not** in the `n*` rule, and the rule is unchanged. The Captain directed a fix, not a switch-off (2026-10-07: *"not switching it off but actually fixing it"*). If `FIX(0)`'s NET_TRAIN exceeds `FIX(n*)`'s, the report says so beside the result and the choice goes to the Captain with that data; it does not change `n*` mechanically.

### 4.2 B2: the lower edge is decided now

QA's expectation (`n*` = 24) is plausible: at a tight cap the corrected OSD accepts little. Deciding the extension after seeing TRAIN would be a choice made on data, so it is decided now:

- **Lower edge (`n*` = 24): no extension.** `FIX(0)` already brackets the low end, and caps between 0 and 24 interpolate between "almost no OSD" and the 24 arm. QA reports `FIX(0)` and `FIX(24)` side by side; TEST proceeds at 24.
- **Upper edge (`n*` = 60): unchanged**, the Architect rules before TEST (the spec's clause). It needs every larger cap to keep ΔU ≤ 0, which I do not expect.

### 4.3 B3: compute

About 7 arms × 622 cycles (REF, `FIX(0)`, five FIX caps) at about 70 min per arm, so ≈ 8 h, plus probes and the noise leg; TEST later. One overnight slot. The wall-time rows (§5.3, descriptive) are only comparable REF vs FIX if the arms run under similar load; QA records what else ran (no new exclusivity rule; the Captain's 2026-10-03 scope stands).

## 5. Predictions

No new blind predictions. OF1–OF7 stand. **A1 scored now against me:** the spec as written would most likely have produced the silent failure QA describes. It is a spec defect, not a prediction row, and is recorded here rather than in the ledger.

## 6. Next

QA: OpenSpec change (`openspec validate`; commit before `check_version_bump.py`), dev-task, Developer handoff (HK-000) with R1/R2 as amended in §2.1 and R5(a) as a unit-test requirement; then harness (A4), probe recalibration (A3), `selection.json` for residues {0, 5} with SHA, the A-SIGN row list. Push and merge stay the Captain's.
