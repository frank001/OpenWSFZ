# ARCHITECT → QA — SPEC `D1`: which file carries the offset, and the shape of the fix that follows

**2026-08-19 12:26Z · Architect → QA · Captain-authorised ("write the specs for QA so they can
create the openspec stuff for the developer")**

**Status: PRE-REGISTRATION, NOT RUN. `D1` is a ~3-minute measurement on data already on disk. It
BLOCKS the OpenSpec change, and it may cancel it.**

---

## 0. Read this first — I am withdrawing part of my own 12:17Z recommendation

At 12:17Z I recommended a Developer session for a **`CycleFramer`** fix. Writing this spec, I went
to `CycleFramer.cs` to describe the change and found a contradiction that I should have resolved
**before** naming a file. **I named a fix location without establishing the mechanism.** That is the
same error class I have now logged three times in two days, and it is the reason this document is a
diagnostic rather than the change spec the Captain asked for.

🛑 **The 12:17Z recommendation is downgraded from "open a Developer session" to "open a Developer
session *for a locus D1 names*".** Everything else in that ruling — C2 accepted, AO1 closed, the
ledger correction — is **unaffected**, because none of it depends on where the defect lives.

---

## 1. The contradiction, stated precisely

Three measured facts. Any two are comfortable; all three are not.

| # | fact | source |
|---|---|---|
| **F1** | Our archived WAV and WSJT-X's archived WAV, **same filename**, contain the same audio to **median \|lag\| 15.5 ms, max 34 ms**, on 4,956 pairs | ROW 0a, `row0a_audio_path_correspondence.py:122-136` — it compares `owsfz/wav/` against `wsjt-x/wav/` |
| **F2** | Sweeping extraction over **our** WAV, anchored at the reference's own `(freq, dt)`, the codeword is found at **+0.650 s**, BER 6.90% vs 49.43% (chance) at the raw anchor | AO1 `K`, 11:35Z |
| **F3** | Our published `dt` differs from the reference's by **+0.700 s** on 25,411 matched rows | AO1 `R`, 11:35Z |

🔴 **F1 and F2 are in direct tension.** If the two files are the same audio to 16 ms, then a signal
the reference locates at `dt = d` in *its* file sits at `d` in *ours* too — not at `d + 0.65`. The
same sweep, anchored the same way, run on either file, is **forced by F1 to return the same answer**.

**So one of these must be true, and they demand opposite fixes:**

- **(A) The offset is in the SHARED capture/save path** — both files carry it, and the reference
  decoder compensates for it while we do not. Then **`CycleFramer`'s window placement is not the
  culprit**, and a fix there would move the window that is already where the reference's window is.
- **(B) The offset is OURS alone** — something between the shared audio and our decode buffer
  displaces it, and F1 missed it. Then the locus is our framing/labelling path and a code fix there
  is right.

**Nothing in the AO1 evidence discriminates (A) from (B).** AO1 never swept the reference's audio —
it had no reason to; that was not its question.

---

## 2. `D1` — the discriminator

**One measurement: run AO1's `K` sweep unchanged, on `wsjt-x/wav/` instead of `owsfz/wav/`.**

Literally the only change is the WAV directory. Same anchor (the reference's own `freq`/`dt`), same
true codeword (from the reference's own decoded message), same 49-point grid
(`m3_common.TIME_ANCHOR_OFFSETS_S`), same seeded sample, same corpus (PRIMARY,
`20260803_live_run_1713`). Call the result **`K_ref`**; AO1's published `K` = **+0.650 s** is
**`K_ours`**.

🔴 **Reuse `run_ao1.py`'s sweep path verbatim — do not re-implement it.** A re-implementation would
make any difference between `K_ref` and `K_ours` uninterpretable, which is the whole measurement.

### 2.1 Pre-gate — ROW 0. HK-025 classification in §2.3

| row | class | fires if | consequence |
|---|---|---|---|
| **0a** | instrument | DLL SHA256 ≠ pin (`6890d84c…`, shim 20260042), re-hashed from disk and asserted before arming | STOP |
| **0b** | power | `n_measured` < 500 rows **OR** `n_clusters_measured` < 200 | STOP |
| **0c** | instrument | sign unit test fails (AO1/Stage 2 construction, reused verbatim, both signs) | STOP |
| **0d** | validity | median `BER_V0` at `K_ref`'s argmin outside **[1.0%, 15.0%]** (two-sided, HK-021(n)) | STOP — the sweep is not reading on this file |
| **0e** | validity | the cycles swept are not the **same cycle set** AO1 swept (filename-matched), overlap < 400 rows | STOP — a different population makes `K_ref` vs `K_ours` a confounded comparison |

### 2.2 Main rows — mutually exclusive, strict order. `θ = 0.10 s`

`θ` is the reference instrument's own reporting resolution, unchanged from AO1 §5. 🔴 **Both
statistics are SIGNED and both must be reported signed with their full trough shape** (HK-021(l)) —
the `|·|` below are magnitude *tests*, and §2.4 states why a signed alternative does not exist here.

| row | condition | verdict and consequence — as an assertion |
|---|---|---|
| **ROW 1** | `\|K_ref\| ≥ θ` **AND** `\|K_ref − K_ours\| ≤ 0.10 s` | **Locus (A): SHARED.** Both files carry the same offset. **`CycleFramer`'s window placement is NOT the defect** and the 12:17Z Developer recommendation is **WITHDRAWN in full**. The defect is in the shared capture/save path or in the `dt` convention itself. 🛑 **No OpenSpec change is written on this branch** — it earns a follow-up design, because "the reference compensates and we do not" names no mechanism yet. |
| **ROW 2** | `\|K_ref\| < θ` **AND** `\|K_ours\| ≥ θ` | **Locus (B): OURS.** The reference's file is clean and ours is displaced ⇒ the defect is between the shared audio and our decode buffer. ⚠️ **F1 must then be explained, not ignored** — a 0.65 s displacement that a 16 ms cross-correlation missed is itself a finding, and §3.2's first task is to say how. **OpenSpec change proceeds, per §3.** |
| **ROW 3** | `\|K_ref\| ≥ θ` **AND** `\|K_ref − K_ours\| > 0.10 s` | **Two effects, not one.** Both files displaced, by different amounts. **NO single fix. Escalate.** Report both curves; propose nothing. |
| **ROW 4** | `\|K_ref\| < θ` **AND** `\|K_ours\| < θ` | **Contradicts AO1's own published `K`** on the same corpus and sample. **Instrument failure, not a finding. Escalate.** Do not report a number for either. |

### 2.3 HK-025 — classify, then evaluate BOTH branches

| row | fires ⇒ | does not fire ⇒ | class |
|---|---|---|---|
| 0a | unidentified binary | pinned build | **VALIDITY** — differ |
| 0b | argmin too noisy to compare against a 0.05 s grid | powered | **PRECISION** — differ |
| 0c | sign uninterpretable, and sign drives every main row | verified | **VALIDITY** — differ |
| 0d | sweep reads noise on this file ⇒ `K_ref` is not a position | `K_ref` is a position | **VALIDITY** — differ |
| 0e | `K_ref` vs `K_ours` confounded by population | like-for-like | **VALIDITY** — differ |

🔴 **I assert no row is diagnostic. Test that claim rather than adopting it — HK-025 refusal is
available on every row, and after ROW 0f I would rather be refused than humoured.**

### 2.4 Resolution, stated while drafting — HK-021(m)

The sweep grid is **0.05 s**. Every row tests against **`θ` = 0.10 s = two grid steps**, and ROW 1's
agreement bound is likewise **0.10 s = two grid steps**. 🔴 **The gate therefore resolves at 2× its
own quantum — it is not the ROW 0f failure repeated**, where the tolerance *equalled* the grid step
and the row had no power at all. A one-step disagreement (0.05 s) clears ROW 1's bound
comfortably; only a ≥3-step disagreement fires ROW 3.

🔴 **Float discipline (11:55Z §4.1): evaluate every comparison in INTEGER GRID-STEP UNITS**
(`round(x / 0.05)`), never as raw floats. That defect is one row-boundary away from repeating.

**On `|·|`:** the underlying quantities are reported signed, and ROW 3 exists precisely so that a
sign or magnitude disagreement cannot hide inside an absolute value. What the rows test is
*co-location of two offsets*, for which magnitude-vs-`θ` plus a signed difference is the faithful
form — not a slope in disguise.

---

## 3. What QA writes AFTERWARDS — the OpenSpec change, ROW 2 branch only

🛑 **Only on ROW 2.** On ROW 1/3/4 QA writes **no** OpenSpec change and reports instead.

Per HK-015 the `dev-tasks/*.md` and the OpenSpec artifacts are **QA's to author** — this section is
the design envelope they must satisfy, not their content.

### 3.1 The prohibition that matters most

🛑 **DO NOT HARDCODE 0.65 s, 0.70 s, or any fitted constant, anywhere, under any name.** A
compensating constant fitted to one machine, one device chain and one corpus is exactly the class of
change this project has already prohibited elsewhere. The routing on this host is
**Voicemeeter AUX Input → B1**, capture-device drift is **device-dependent** (48.0 ppm USB CODEC vs
4.7 ppm Voicemeeter), and a constant that is right here would be wrong on the Captain's other chain.
**The fix must make the quantity measured, not assumed.**

### 3.2 The change must

1. **Explain F1 first.** State how a 0.65 s displacement survives a 16 ms cross-correlation between
   the two files. If that cannot be stated, the ROW 2 reading is not yet safe to build on — say so
   and stop.
2. **Remove the error class, not the error.** The framer currently infers when its first sample was
   captured, at consumption time, from `_clock.UtcNow` minus the unconsumed remainder
   (`CycleFramer.cs:240-241`). Any delay between physical capture and that inference biases it, and
   `CycleFramer.cs:195-232` **already documents this bias as "bounded and benign"** — an assumption
   that a measured constant offset would contradict. 🔴 **The architecturally clean fix is for a
   chunk to CARRY its own capture timestamp**, stamped on the capture thread where the chunk is
   produced (`WasapiAudioSource.cs:157-171`, 2048 samples @ 12 kHz = **170.67 ms**/chunk), so that
   neither bounded channel (inner 32, `WasapiAudioSource.cs:36-42`; outer 16,
   `CaptureManager.cs:66-72`, both `DropOldest`) can bias the estimate at any queue depth.
3. **Accept that this is a type change through the pipeline** — `float[]` → a chunk carrying
   `(samples, capturedUtc)` across `IAudioSource` / `CaptureManager` / `CycleFramer`. ⚠️ **Say so in
   the proposal.** It is the honest scope, and a reviewer discovering it mid-implementation is worse
   than a reviewer weighing it up front.
4. **Keep the realignment behaviour it already has.** The grid-realignment fix (`consume` varying
   per cycle) is load-bearing against 48 ppm drift and is **not** what D1 questions. Do not
   regress it while changing how capture time is obtained.
5. **Carry a test that would have caught this.** ⚠️ `SimulatedCaptureDevice` derives its clock from
   its own production position and is **lag-free by construction** (`CycleFramer.cs:234-238`) — the
   existing oracle **cannot** see this defect, and a green suite proved nothing about it (HK-022:
   ask what error the test could not detect). A test that injects a capture-to-consumption delay and
   asserts the window still lands on the grid is the minimum bar.
6. **State the expected effect on the number.** `L = +0.706 pp` [+0.49, +0.93] is what a correct fix
   should recover, and `R` should collapse toward 0. 🔴 **Pre-register that before the fix ships**,
   so "it worked" is a measurement and not an impression.

### 3.3 Standing constraints that apply unchanged

**HK-011** — QA proposes and stops; the Developer runs `opsx:apply` (build/tests only, **never**
`pre_merge_check.py`); the Captain reviews the diff. **HK-014** — no push, no merge. **HK-010** —
merge needs explicit sign-off. **Licence policy** — permissive only, no GPL-derived code from
WSJT-X; read-for-method only. **Binary identity** — any rebuilt DLL pins a **SHA256**, never a
`FT8_SHIM_VERSION` integer (20260039–41 are reserved; pick outside that range and record it).

---

## 4. Order of work

1. Run **`D1`** (§2). ROW 0 first, in order, HK-025 refusal available throughout.
2. **Report and STOP.** Do not proceed to §3 in the same session.
3. On **ROW 2 only**, and only after the Captain's go-ahead, author the OpenSpec change + the
   `dev-tasks/*.md` per §3.
4. **GitHub #3/#111** — the Captain has assigned this to QA; fold in AO1 Part B/C and note that the
   locus is pending `D1` rather than settled.

---

## 5. Predictions, recorded before the harness exists

🔴 **Architect calibration: categorical 8/13 · ranges 11/19 · directional 2.5/5.5 · mechanical 3/4.**

| quantity | my call | scoreable? |
|---|---|---|
| `D1` row | 🔴 **ROW 1 (shared locus), P ≈ 0.80**; ROW 2 P ≈ 0.12; ROW 3 P ≈ 0.05; ROW 4 P ≈ 0.03 | **YES — categorical** |
| `K_ref` | **+0.60 to +0.70 s** | **YES — range** |
| `\|K_ref − K_ours\|` | **0.00 s** (bit-identical argmin) | **YES — range** |

**Why I expect ROW 1, and what it costs me.** F1 very nearly forces it: same audio to 16 ms, same
anchor, same grid ⇒ the same argmin. If ROW 1 fires, **my 12:17Z `CycleFramer` recommendation was
pointed at the wrong file**, and the mechanism is somewhere neither AO1 nor this spec has yet named.

🛑 **I am running it anyway, and QA should not treat P ≈ 0.80 as licence to skip it.** "Nearly
forced" is precisely the reasoning that produced the withdrawn Stage 1, the mis-wired Part C gate,
and the 12:17Z recommendation I am withdrawing above. **Three minutes of measurement beats another
paragraph of mine.**

---

## 6. Scope

No `src/` change, no Developer session, no DLL rebuild, no capture run, no new corpus — **HK-011 not
engaged by `D1` itself.** PRIMARY (`20260803_live_run_1713`) only; the extension corpora are
**descriptive replication** if run at all and gate nothing. **NFR-021**: grep every emitted file
individually before committing.

🛑 **`D1` cannot rehabilitate any withdrawn number, reopen N1 ROW 2 / limb 1 / R2, or revisit ROW 0f,
ROW 3 or C2.** It answers one question: **which file carries the offset.**
