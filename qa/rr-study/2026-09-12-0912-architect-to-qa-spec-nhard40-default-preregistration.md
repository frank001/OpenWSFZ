# `NHARD40-DEFAULT` — pre-registration: change the `osd_nhard_max` default 60 → 40, gated on a near-threshold oracle safety leg (`NT`)

**Architect, 2026-09-12 09:12Z** (`date -u`, HK-017). Branch `arch/osd-nhard40-default` (cut from
`origin/main`). Docs-only; `git diff --stat origin/main -- src/ native/` empty.

~~**Status: DRAFT, and not runnable yet.** `NT` may not produce a datum until the PO ratifies `BAR_S`
(§5, Q1). The dev-task may not be written until the PO answers Q2.~~

> ✅ **2026-09-12 09:15Z: `BAR_S = 0.05` ratified and Q2 = M2 (PO, §5). `NT` is cleared to run.**

---

## §0. What this is, what licenses it, and what it reuses

**Licence.** `OSD-FA-A` Amendment 1 §5.4 clause 3 holds (`E1-1 ∧ E2-B1 ∧ E3-N`; E3 accepted
`2026-09-11-2210-architect-osd-fa-a-e3-acceptance.md`). That clears the Architect to *draft* this
document. The Captain said to draft it: verbatim, *"1. yes. 2. not now. 3. yes"*, where item 1 was
this draft and item 2 declined setting 40 on his own station for now.

**What it is bound by.** The E2 acceptance ruling §2 (`2026-09-11-2124-…`): S8HN has no near-threshold
genuine signal, so **no `OSD-FA-A` leg shows that weak real stations survive 60 → 40.** Any default
change must carry a near-threshold oracle leg as its safety gate. That leg is `NT` (§3), and it is
**the only new measurement in this document.**

**What carries without re-measurement, and why it may.** The product change (§1) is a C# config
default. **The native binary does not change** (`6b2e16a6…4f85c`, shim `20260050`). Every `OSD-FA-A`
measurement at `nhard = 40` was made on that same binary at that same setting, so these carry
verbatim:

| gate | carried result | citation |
|---|---|---|
| **G1: FP benefit (primary statistic, base `OSD-FA-A` §7)** | **E1-1:** slots with any false decode fall from 10.325% to 0.35%, `r = 399`, `a = 0`, `p ≈ 1.5e-120` | `…-2048-…-e1-acceptance.md` |
| **G3: live harm** | **E3-N:** 11/1,509 corroborated, CP95 [0.36%, 1.30%] < `BAR_H` 5%. Descriptive: true removals 2/1,491; live reach 2.59% | `…-2210-…-e3-acceptance.md` |

🛑 **If the binary changes before this arm closes, G1 and G3 stop carrying** and must be
re-registered on the new binary.

**Reused, not rebuilt (HK-018):** `qa/rr-study/f-nbr-a/scene_render.py`
(`render_scene(signals, seed)` at 12 kHz); Part A's payload labeller (`osd-fa-a/part_a.py`
`is_true`); Part B / E2's pairing key `(payload, freq ±4.0 Hz)`; E1's production input contract
(`normalise_rms(pcm, 0.20)`, verified as `Ft8Decoder.cs`'s own `NormalisePcm` in the E1 ruling §2).

---

## §1. The product change (QA translates this into a dev-task, on `S1` only; HK-015, HK-011)

1. **`src/OpenWSFZ.Abstractions/DecoderConfig.cs`: change the default from 60 to 40 in BOTH places,
   the property initialiser (`:68`) and the `[JsonConstructor]` parameter default (`:36`).** Missing
   one gives a partial-JSON divergence (the file's own Lesson 6 / D-WFC-001 note). Update the doc
   comment's "Default: 60 (D-009 calibrated…)" to cite this arm.
2. **The native default stays at 60** (`src/OpenWSFZ.Ft8/Native/ft8_shim.c` `s_osd_nhard_max`). No
   rebuild, no shim bump, no SHA-pin churn. The product always sets the value explicitly at startup
   (`Program.cs:728–732`) and on every config change (`Program.cs:867`). The divergence is
   deliberate; state it in the C# doc comment.
3. **Existing installs: PO QUESTION Q2 (§5).** `JsonConfigStore.CreateDefault` writes an explicit
   `"osdNhardMax": 60` into every new `config.json`, and every save writes all fields
   (`DefaultIgnoreCondition.Never`). **Changing the code default alone never reaches an existing
   install, including the Captain's** (his `config.json` has `"osdNhardMax": 60`). There is no config
   schema versioning; the one migration today is a field rename (`JsonConfigStore.cs:147`).
4. **Known test consequences (for the dev-task author):**
   - `tests/OpenWSFZ.Config.Tests/DecoderConfigTests.cs`: facts 7.1b, the absent-key fact and the
     default-config fact assert 60; they move to 40.
   - `tests/OpenWSFZ.Ft8.Tests/FpParityP3Tests.cs` ROW 0o asserts **live config == code default**. Under
     Q2 option M1 it **fires** on every existing install. Under M2 the live-effective value becomes
     40, so every later P3-class offline decode runs at 40.
   - 🛑 **From the change onward, every offline FP rate states its `nhard`.** `10.325%` becomes
     *"10.325% at `nhard` 60"*, never an unlabelled "production default".
5. **QA harness constants:** `p23_common.DECODE_PARAMS = (10, 0.10, 60)` is described as "production
   defaults". When the change lands it becomes "pre-change defaults". Relabel it; do not silently
   change it.
6. **Rollback:** the operator sets `Decoder.OsdNhardMax = 60` in `config.json`; it applies on the next
   cycle. No build.

---

## §2. Gate structure and consequence (strict order, first match wins)

| gate | source | status |
|---|---|---|
| G1 FP benefit | E1-1 | carried (§0) |
| **G2 near-threshold safety** | **`NT` (§3)** | **new** |
| G3 live harm | E3-N | carried (§0) |

1. **`NT-S2`** ⇒ **Option B is contraindicated as a default.** Record the per-rung figures. `D-009`
   Option B's HOLD becomes CLOSED as a default change. The operator setting stays available.
2. **`NT-S3`** ⇒ **unresolved.** Nothing changes. Report every figure. Any follow-up is a new
   proposal.
3. ~~**`NT-S1`** ⇒ **the Architect asks QA to author the dev-task per §1**, carrying the PO's Q2 answer.
   A Developer session implements it (HK-011). Merge still needs the Captain's sign-off (HK-010).~~

> ⛔ **AMENDED 2026-09-12 10:00Z (PO decision, after `NT-S1`, before any `CC` datum):** item 3 now
> requires **`NT-S1` and `CC-S1`**. A co-channel oracle gate G4 is added. `NT`'s row is unchanged.
> See `2026-09-12-1000-architect-to-qa-nhard40-default-amendment-1-cc-leg.md` §1.

---

## §3. `NT`: the near-threshold oracle leg

### 3.1 Scene

- **One Q-prefixed station per cycle**, rotating by `trial_index mod 4` over four (message,
  frequency) pairs from `qa/rr-study/scenarios/study-messages.json`:

  | `trial mod 4` | message | freq |
  |---|---|---|
  | 0 | MSG-01 `CQ Q1ABC FN42` | 700 Hz |
  | 1 | MSG-02 `Q4XYZ Q1ABC -07` | 1,300 Hz |
  | 2 | MSG-04 `Q1ABC Q4XYZ FN42` | 1,900 Hz |
  | 3 | MSG-05 `Q5DEF Q1ABC +03` | 2,500 Hz |

  `dt_s = 0.0`, as S8HN used, so the renderer runs as already validated.
- **SNR ladder:** nominal −26.0 to −16.0 dB in 0.5 dB steps (21 rungs), in the renderer's own units.
  🛑 **These are nominal renderer units. Never cite them as on-air dB.**
- **Trials:** 250 per rung ⇒ **5,250 cycles**. Fresh noise per cycle. Seed
  `compute_seed('NHARD40-NT', rung_index, trial_index)`, derived from a label, not the data.
- **Input contract:** `normalise_rms(render_scene(…), 0.20)`, the production contract (E1 ruling §2).
  Parts A/B/E2 decoded the renderer's level directly; `NT` does not.

**Why a single station:** every cycle holds at most one genuine decode, so there is no clustering
and the CI is exact (Clopper–Pearson). Nothing else in the cycle can displace or be displaced by it.
**What it therefore cannot see** is §6.

### 3.2 Legs

Each cycle's **identical PCM** is decoded three times, with `k = 10` and `corr = 0.10` fixed:

| leg | `nhard` | role |
|---|---|---|
| **60** | 60 | control: the current default |
| **40** | 40 | treatment |
| **0** | 0 | **ceiling / positive control:** rejects every OSD accept (base ROW 0b showed `osd 1 → 0`) |

Settings scheme: one setting per leg, **or** switching between complete decodes on one thread (E1
ruling §3). **State which.** Never change settings with a decode in flight. **Persist per-cycle
arrays** for every leg: genuine present (0/1) and number of false decodes.

### 3.3 Labels and pairing

- **Genuine** = a decode whose payload is the injected payload (`part_a.is_true`, payload not text)
  **and** `|f − f_injected| ≤ 4.0 Hz`.
- Cross-leg pairing uses Part B / E2's key `(payload, freq ±4.0 Hz)`.

### 3.4 Definitions (predicates as code, HK-021(r))

- `p60(r)` = share of rung-`r` cycles with a genuine decode at 60. `p40(r)` and `p0(r)` likewise.
- **Band `B` = `{ r : p60(r) < 0.95 }`**, computed from **the 60-leg only**, in code, **before** any
  60-vs-40 comparison (HK-021(y): the split is not outcome-chosen).
- `G_B` = genuine decodes at 60 on band-`B` rungs.
- `K_B` = those absent at 40 (**killed by the change**).
- `C_B` = those absent at `nhard` 0 (**OSD-dependent: the most any `nhard` setting could kill**).
- **`L_B = K_B / G_B`** (the gate statistic) and `L0_B = C_B / G_B` (the ceiling), each with a
  Clopper–Pearson 95% interval.

### 3.5 ROW 0: strict order

| row | check | on failure |
|---|---|---|
| **0a** | DLL SHA-256 = `6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c` (shim `20260050`), asserted in code | VOID |
| **0b** (validity) | the ladder brackets the threshold at 60: `p60(−26.0) ≤ 0.05` **and** `p60(−16.0) ≥ 0.95` | Extend on the failing side in 0.5 dB rungs, **60-leg first**, at most 6 rungs per side, then run 40 and 0 on the added rungs. Still failing ⇒ VOID and escalate (the renderer's scale is not where I think it is). |
| **0c** | determinism: a second independent process re-decodes a seeded 500-cycle sample on all three legs; per-cycle arrays **element-wise identical** | VOID |
| **0d** (power, routes) | `G_B ≥ 300` | Top up band-`B` rungs in blocks of 250 trials (band still chosen on the 60-leg only), at most 2 blocks. Still short ⇒ **S3**. |

**Report only, not a gate (HK-021(k), evaluated both ways):** the count of decodes killed at 40 but
**present** at `nhard` 0. It is expected to be 0, because `nhard` gates only OSD accepts. A non-zero
count would still be genuine loss caused by the change, and `L_B` counts it either way, so the row
would not move. Report it; don't stop on it.

⚠️ **What ROW 0 cannot detect (HK-022):** a renderer whose nominal SNR scale is off by a constant.
0b catches a scale error large enough to push the threshold off the ladder, not one that shifts it
within the ladder. Band `B` is defined relative to the measured 60-leg curve, so the gate does not
depend on the scale being right; only the dB labels do.

### 3.6 Gate rows (first match wins)

| row | predicate | reading |
|---|---|---|
| **S2** | `CP95_lo(L_B) ≥ BAR_S` | **Measurable genuine loss near threshold.** ⇒ §2 item 1. |
| **S1** | `CP95_hi(L_B) < BAR_S` | **No genuine loss detected near threshold at this resolution, on this scene.** ⇒ §2 item 3. |
| **S3** | otherwise, or ROW 0d short | Unresolved. ⇒ §2 item 2. |

**The ceiling, read with the row:** if `CP95_hi(L0_B) < BAR_S`, then **no `nhard` setting at all**
could cost more than `BAR_S` on this scene, because the OSD path contributes too few genuine
near-threshold decodes. That is a structural result, and a legitimate one, because 0b guarantees the
scene contains the threshold. **This is the fix for E2's blindness:** E2 had no threshold in its
scene, and `NT` must.

### 3.7 Descriptive (no row)

- `p60`, `p40`, `p0` per rung. The 50% point at each setting by linear interpolation between rungs,
  and **the shift in dB between 60 and 40** (the "sensitivity cost" in operator terms, nominal units).
- False decodes per cycle at each setting: the noise-plus-weak-signal FP picture, complementing E1
  (HK-021(t), cost on the complement).
- `L0_B`, and the share of genuine near-threshold decodes that are OSD-dependent at all.

### 3.8 Resolution, computed while drafting (HK-021(m))

The transition width is unknown. If band `B` holds about 4 rungs at a mean `p60` of about 0.5, plus
its tail, then **`G_B ≈ 500`**. At `G_B = 500`, with `BAR_S = 0.05` (proposed, §5):

| true `L` | `K_B` | CP95 | row |
|---|---:|---|---|
| 0 | 0 | [0.00%, 0.74%] | S1 |
| 2% | 10 | [0.96%, 3.65%] | S1 |
| 3% | 15 | [1.69%, 4.90%] | S1 |
| 4% | 20 | [2.46%, 6.11%] | S3 |
| 7% | 35 | [4.92%, 9.60%] | S3 |
| 8% | 40 | [5.78%, 10.73%] | S2 |

**S1 needs a true loss of about 3% or less. S2 needs about 7.5% or more.** Between those the arm
reads S3 and nothing changes, and that is the correct reading at this size. The rows are
**conservative in the direction of no change.**

---

## §4. Architect predictions: blind, on the record, before any `NT` datum

| row | probability | reasoning |
|---|---|---|
| **S1** | 0.35 | E1 shows the (40, 60] band is overwhelmingly noise. |
| **S3** | 0.40 | Near threshold, genuine hard-decision error counts climb. A genuine OSD accept with 41–60 hard errors at the bottom rungs is physically plausible, and `decode.c:41` calibrated 60 against S7 (co-channel), **not** a near-threshold ladder. |
| **S2** | 0.25 | The same physics, if the OSD path carries more of the threshold than I expect. |

My last two predictions in this programme missed (E2's removal count; the "≤ 1.9%" reach). Weigh
these accordingly.

---

## §5. PO questions

**Q1 (needed BEFORE any `NT` datum): ratify `BAR_S`.** I propose **`BAR_S = 0.05`**: the gate passes
only if near-threshold genuine loss is confidently under 5%.

- **Why this value:** it is the same unit and value as the PO-ratified `BAR_H` (E3) and Part B's bar,
  so the harm leg and the safety leg speak the same language. §3.7's dB shift gives the PO the
  operator reading alongside it.
- **Alternative:** 0.02. It is stricter, and needs roughly **3× the trials** to be reachable.
- 🛑 Once ratified it is **FROZEN** for this arm (the `BAR_H` precedent). If anyone, me included,
  proposes moving it after `K_B` is known, refuse: that VOIDs `NT`.

> ✅ **PO RULING, 2026-09-12 09:15Z: `BAR_S = 0.05` RATIFIED** (the PO chose "5% (Recommended)"
> over the stricter 2%). Recorded **before any `NT` datum exists**: no `NT` harness has been written
> or run. **FROZEN for this arm**; it does not reach forward or backward.

**Q2 (needed before the dev-task, NOT before `NT` runs): what happens to existing installs?**

| option | what it does | trade-off |
|---|---|---|
| **M1** | Code default only | New installs and configs with no `decoder` key get 40. **Every existing install, including yours, stays at 60** until the operator edits `config.json`. `FpParityP3Tests` ROW 0o fires on existing installs. |
| **M2 (recommended)** | Code default **plus a one-time migration**: a persisted value of **exactly 60** becomes 40, once, logged, with a marker so it never re-applies after an operator deliberately sets 60 again | Reaches everyone. It would override a deliberate 60, but ~~**the web UI does not expose this setting** (no `wwwroot` reference; API or hand-edit only), so a persisted 60 is, in practice, the old default.~~ ⛔ **STRUCK 2026-09-12 10:4xZ (Architect): WRONG.** The settings page DOES expose it ("OSD Max Hard Errors", `web/settings.html:359`; reset-to-defaults sets `'60'`, `web/js/settings.js:1116`). I searched `src/OpenWSFZ.Web` only; the UI lives in `web/`. **Corrected basis:** every settings-page save posts `osdNhardMax` with the field's current value (`settings.js:389`/`:1331`), so a persisted 60 is almost always the shown default carried through a save. A deliberate 60 is possible and indistinguishable. It would be migrated once, and the marker then respects a re-set 60. Needs one small new config field for the marker. |
| **M3** | Code default plus a notice suggesting 40; no automatic change | Leaves the choice to the operator. Reaches only operators who read notices. |

> ✅ **PO RULING, 2026-09-12 09:15Z: Q2 = M2, migrate once.** On S1, the dev-task carries the code
> default 60 → 40 **plus** a one-time migration of a persisted `osdNhardMax` of **exactly 60** to 40.
> It must be logged, and a marker must stop it re-applying after an operator deliberately sets 60.
> The marker's name and shape are the dev-task's to specify (a new config field). §1.4's
> `FpParityP3Tests` ROW 0o note applies in its M2 form: the live-effective value becomes 40.
>
> ✅ **PO RE-CONFIRMED M2, 2026-09-12 ~10:4xZ**, on the corrected basis (the settings page DOES
> expose the setting; see the struck M2 row above).
>
> 🔴 **BINDING REQUIREMENT ADDED 2026-09-12 (Architect, HK-035): the marker must be SERVER-OWNED and
> must survive a settings-page save.** `POST /api/v1/config` deserialises the body as the **whole**
> new `AppConfig` (`WebApp.cs:349–372`, full replace, not a merge). The settings page sends only
> `{kMinScorePass2, osdCorrThreshold, osdNhardMax}` (`web/js/settings.js:1328–1332`). A marker stored
> in `DecoderConfig` and not carried forward would therefore be **reset to false by every settings
> save**. An operator who sets 60 back on the settings page would then be **re-migrated to 40 on the
> next restart**, breaking the exact guarantee the PO confirmed.
>
> ⇒ **The POST handler must carry the marker forward from the current config regardless of the
> request body.** No client may clear it. **Required end-to-end test:**
> 1. a migrated config (40, marker true);
> 2. `POST /api/v1/config` with `decoder: {…, osdNhardMax: 60}` and no marker;
> 3. the persisted file has 60 **and** marker true;
> 4. reloading the store gives 60, not re-migrated.
>
> A marker test on a hand-edited file alone is insufficient.

---

## §6. What this arm does NOT do, and what `NT` cannot see

- 🛑 **No `src/` or `native/` change, no rebuild, no push, no merge** in the measurement phase (HK-011,
  HK-014, HK-010). §1 is written for QA to translate on S1 only.
- 🛑 **No other parameter moves:** `k_min_score_pass2` and `osd_corr_threshold` stay fixed.
- **`NT` tests an ISOLATED weak station.** It cannot see:
  - a weak station **next to strong ones** (candidate competition, first-hit displacement: base
    `OSD-FA-A` §0.3, still out of scope);
  - **fading, Doppler, drift or timing spread** (E4, still unopened);
  - message types outside the four rotated (e.g. Type-4 non-standard calls, S11).

  An S1 here reads *"no near-threshold genuine loss for an isolated station on AWGN"*, never *"safe"*.
- Spectral locality stays barred in any form (base §0.1).
- NFR-021: Q-prefix synthetic only. Scan anyway.

## §7. Running order and authorisation

| step | status |
|---|---|
| This draft | ✅ Captain: *"1. yes"* |
| **Q1 `BAR_S` ratification** | ✅ **`BAR_S = 0.05`, PO 2026-09-12 09:15Z** (§5), recorded before any `NT` datum |
| `NT` (ROW 0 → S-row) | ✅ **cleared to run.** Supervise it if long (HK-013 / HK-023); about 15,750 decode calls. |
| Q2 migration answer | ✅ **M2, migrate once, PO 2026-09-12 09:15Z** (§5) |
| Dev-task → Developer → CI → merge | on S1 only; HK-015 / HK-011 / HK-010 |

🔴 **HK-025 is available in full.** If any row above is a diagnostic dressed as a gate, name it,
evaluate both branches, and refuse. I have done exactly that on several arms this month.
