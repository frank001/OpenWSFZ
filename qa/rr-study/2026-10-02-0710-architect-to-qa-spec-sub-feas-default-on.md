# SPEC — SUB-FEAS subtraction ON by default, with a one-time migration of existing installs

- **To:** QA (owner; SUB-FEAS is QA's workstream) — cc Captain  **From:** Architect  **Date:** 2026-10-02 ~07:10Z (HK-017)
- **Branch:** `arch/subtraction-feasibility`. Docs only: `git diff --stat -- src/ native/` empty.
- **Captain's decisions, 2026-10-02 (after the replay ruling `2026-10-02-0620`):** *"default ON"*; existing installs **"migrate once to ON"*; the default thread count and Stage B **"hold for now"**; band replication **"not now"**. Batch 2 reaching the auto-QSO: decided in principle, but the mechanism waits on the lateness measurement (separate spec `2026-10-02-0720-…-lateness-tolerance.md`). **It is NOT part of this change.**
- **Implementation:** `src/` ⇒ QA writes the Developer handoff, and a separate Developer session builds it (HK-011, HK-000).

## 1. What changes

| # | Change | Where (at `origin/main` `9bade2bc`) |
|---|---|---|
| C1 | Code default `subtractionEnabled` **true** (both the constructor parameter and the property initialiser) | `src/OpenWSFZ.Abstractions/DecoderConfig.cs:40`, `:133` |
| C2 | One-time migration on load: a persisted `subtractionEnabled: false` becomes `true` **once**, with a server-owned marker (`subtractionOnMigrationApplied`), and is written back to disk immediately. After that, an operator's OFF persists. | Same pattern as `Nhard40MigrationApplied`, `src/OpenWSFZ.Config/JsonConfigStore.cs:245-270` |
| C3 | The POST overlay treats the marker as server-owned (forced from the store), like `nhard40MigrationApplied` | `src/OpenWSFZ.Web/WebApp.cs:525`, `ConfigOverlay.cs:31` |
| C4 | One stderr line on migration, as for nhard 40 (wording: the setting, the old and new value, and how to turn it off) | — |
| C5 | Requirements: the flag FR (FR 9.4 per the merge) says default ON + migration; VERSION 0.53 → **0.54**; user-facing docs say the setting exists, defaults ON, and how to turn it off | REQUIREMENTS, README, VERSION (G9a/G9b) |

**Unchanged:** `subtractionMaxThreads` stays `0 = auto` (`max(1, ProcessorCount − 2)`, spec A4). Batch 2 stays out of the QSO controllers. Two-stage publish stays as built.

## 2. 🔴 The marker trap: verify it in the nhard 40 pattern before copying it

As I read `JsonConfigStore.cs:245-252`, the migration fires only on `{ OsdNhardMax: 60, Nhard40MigrationApplied: false }`, and **a config with no `decoder` key resolves to the code defaults with the marker still `false`**. If that is right, then on a fresh install the operator later sets 60, the POST forces the marker from the store (still `false`), and the save writes `60 / false`. **The next load then migrates it back to 40.** "An operator's explicit choice persists" would fail on exactly the installs that never had a legacy value.

Copied as is, C2 would have the same hole, and worse: a fresh install where the operator turns subtraction OFF would come back ON at the next restart.

- **QA first verifies this with a test against the nhard 40 path on `main`** (fresh config → set 60 via POST → reload → read `osdNhardMax`). I have not run it, so it is a reading, not a finding (HK-022).
- **For C2, whatever that test shows:** the marker is set to `true` and persisted **whenever the migration check runs on a load, whether or not it changed anything**. A config is then migrated at most once in its life. Its first load under 0.54 is that once.
- If the nhard 40 hole is confirmed, it gets **its own issue** and is not folded into this change (scope). The Captain decides on the fix.

## 3. Acceptance (rows are mechanical; QA may refuse any on HK-025(k) grounds)

| Row | Predicate |
|---|---|
| A1 | No config file ⇒ loaded `SubtractionEnabled == true`, marker `true` on disk after the first load |
| A2 | Legacy file `subtractionEnabled:false`, no marker ⇒ `true`, marker `true`, written to disk, one stderr line |
| A3 | File `false` + marker `true` ⇒ stays `false` across 2 reloads |
| A4 | Fresh install → POST sets `false` → reload ×2 ⇒ stays `false` (the §2 trap, for this flag) |
| A5 | POST body carrying `subtractionOnMigrationApplied` (either value) cannot change the stored marker |
| A6 | Existing config-save tests T4/T5 (reflection-enumerated) pass with the new field |
| A7 | CI green on all three platforms (macOS `.dylib` `[WARN]` expected) |
| A8 | **Live, on the station's real config** (a copy taken first, kept as the rollback): the daemon starts, the log shows the migration line and subtraction ON, a Settings save leaves it ON (HK-035: overlay on this build), and the panel shows batch-2 rows. ~15 min, RX only. |

No decode-rate row: the decode path is the flag-ON path already measured (`NET +11.73 pp`, replay ruling). The DLL is unchanged (`ee00d118…`), and QA asserts that.

## 4. 🔴 Measurement consequences (QA's to carry; the reason this is not "just a default")

1. **From the day this lands, the station runs flag ON unless a run pins it OFF.** Every endurance/R&R `arm_config.json` must record `subtractionEnabled` and `subtractionMaxThreads`. 🛑 **Never pool flag-ON with flag-OFF runs**, the same rule as nhard 60/40. The endurance history before this date is flag-OFF, except for the 2026-09-30 on-air night. Add that boundary to the guards with its UTC timestamp.
2. **Section 4 (live WSJT-X comparison) moves when this lands**, by roughly the size of the NET. That is the flag, not a decoder change. The first flag-ON endurance report says so in its header.
3. **R&R S1–S8:** the battery's history is flag-OFF. Pin it OFF in the R&R arm for comparability, or start a new flag-ON baseline. That is QA's call; record which.
4. `decoding_improvement`: the DI sync (`sync/di-with-main-3`) carries SUB-FEAS but is not yet pushed. QA sequences: land the sync first, then this change goes to `main` and is merged into DI in the usual way. Endurance builds from DI get the default when DI is next synced.

## 5. Concerns, stated once (Captain has decided; recorded, not re-argued)

- **The thread default ships unresolved.** Default ON exposes `ProcessorCount − 2` workers to every user's CPU. Only 8 workers on this CPU has a clean on-air record. The 12-worker check and the per-fit log are held. The hard native deadline bounds the harm, so the cost of a bad thread count on a weak CPU is **abandoned residual passes (lost extras), not a hang or a late batch 1** (S2: batch-1 latency unaffected). Acceptable on that basis. The abandon count is in the §4.2 log line if a user reports it.
- **The band-D FP flag** (replay ruling §2): ≈ 54 excess not-corroborated decodes per night over the batch-1 rate, upper bound 194. They are display only until batch 2 reaches the auto-QSO.
- **One band, one station, one CPU** of evidence. Accepted by the Captain ("band replication not now").

## 6. Predictions (blind; scored at QA's acceptance report)

| # | Prediction | P | Class |
|---|---|---:|:---:|
| DO1 | QA's §2 test confirms the nhard 40 marker trap on `main` | 0.70 | C |
| DO2 | A1–A7 pass on the first Developer build | 0.65 | H |
| DO3 | A8 passes first time | 0.80 | H |
