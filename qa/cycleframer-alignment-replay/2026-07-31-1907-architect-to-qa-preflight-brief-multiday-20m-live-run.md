# Architect → QA — pre-flight brief, multi-day 20m live run
# Read before arming. Nine items. Item 1 is the one that silently wastes the run.

**Author:** Architect, 2026-07-31 (19:07 UTC, `date -u`, per HK-017). Repo at `8fedeaf`.
**For:** QA, arming a multi-day dual-instance run at the Captain's direction.
**Run profile:** minimal interaction — unattended except when the Captain engages.
**Context:** the D-001 investigation is **parked**. This run is corpus gathering, not a measurement.

---

## 0. Why this run is worth getting right

The 8080 instance will produce **the corpus this programme has been missing**: one band,
continuous, with a live WSJT-X on the identical audio path. That combination answers *"does
WSJT-X suffer the same density penalty we do?"* — the single most decision-relevant unknown on
the board — from real data instead of a synthetic model.

Every prior attempt failed on something mundane: the last 20m corpus turned out to be two
sessions; the last 40m corpus was destroyed by clock drift after hour 12. **The failure mode is
never exotic.** Items 1–4 are the mundane things.

## 1. ⚠️ The archive fix must be in the RUNNING build — verify, do not assume

PR #119 is merged. I verified all three layers are on `main` at `8fedeaf`:

| layer | file | state |
|---|---|---|
| service | `CycleArchiveService.cs:185` — `(… ?? new CycleAudioArchiveConfig()).Mode` | present |
| web POST | `WebApp.cs:501` — `if (config.CycleAudioArchive is null)` | present |
| save path | `JsonConfigStore.cs:73` — SaveAsync guard | present |

**But the daemon serves a build-time copy.** A `.cs` change requires the process **stopped and
rebuilt** — a running instance keeps the old binary. If either instance is still up on a
pre-#119 build, **it still has the crash**, and CI being green says nothing about that.

**Both instances must be rebuilt from post-#119 `main` and restarted before arming.**

### 1.1 Two-minute proof, before committing days of capture

The defect's trigger is **any Settings-page save** (there is no UI field for cycle audio archive,
so every save omits the key). On the **8081** instance, before the real run starts:

1. Note the WAV count in the archive directory.
2. Save the Settings page — the exact action that failed live on 2026-07-29.
3. Confirm all three:
   - `cycleAudioArchive` in `config.json` is **not** `null`;
   - WAV count is **still increasing** two cycles later;
   - no `NullReferenceException` and no generic `Decode error:` stack trace in the log.

If any of the three fails, **stop and escalate** — do not start a multi-day run on it. This costs
two minutes and it is the only direct evidence that the fix is in the binary that will actually run.

## 2. ⚠️ The size cap binds at ~1 day — raise it or lose the early days

Measured from `20260729_live_run_1831-8080`, not estimated:

| quantity | value |
|---|---:|
| one cycle WAV | 360,044 bytes |
| 24 h 08 m of capture | **5,795 WAVs = 1,994 MB** |
| default `MaxSizeMb` | **2,048** |

That run finished **54 MB under the cap.** At `mode = "all"`, one instance fills the default cap in
almost exactly one day, then prunes oldest-first, **silently**. A multi-day run on defaults keeps
roughly the last 24 hours and discards everything before it.

**`MaxSizeMb` must be raised to cover the planned duration, per instance**, at ~2 GB per instance
per day plus headroom. `MaxAgeHours` (default 168 = 7 days) is not the binding constraint; size is.

**Keep the two instances' archive directories separate** — retention sweeps per-directory, so
separate directories each get their own budget instead of competing. Also confirm free disk covers
both instances for the full duration *plus* WSJT-X's own WAV saving.

## 3. 8080 is the decisive corpus — do not touch it once running

- **Stays on 14.074 MHz for the entire run.** Contiguity is the whole value; a gap over 5 minutes
  splits the corpus into segments that cannot be re-joined afterwards.
- **No Settings-page saves on 8080 at all**, for the duration. Even with the fix in, every save is
  an unnecessary risk on the one instance whose continuity matters.
- **`cycleAudioArchive.mode = "all"`.** Not `decoded` — the sparse overnight cycles are exactly the
  ones a density analysis needs, and `decoded` would discard the cycles where we decode nothing.

## 4. 8081 is free to hop — just record it

Band-hopping on 8081 is expected and additive. It produces a segmented corpus, which is now a
handled case rather than a hidden confound.

**Record the retune times** (or rely on the ≥5 min gap detection). If 8081 sits on 14.074 while
8080 is also there, note the overlap window explicitly — that gives a same-band, same-time,
two-receiver control, which is a genuine bonus.

## 5. Unattended operation — supervisor requirements (HK-013)

Minimal interaction means unattended, which means a supervisor is mandatory: kill + log + cooldown +
restart, **cap 5 retries**, and **live-tested before it is trusted**.

**Port the follow-rotation guard (HK-013 addendum).** The standard template pins a single log file
and misses the app's UTC-midnight rotation — it killed two healthy instances on 2026-07-29. A
multi-day run crosses **several** midnights, so this is the highest-probability supervisor failure
here, not a theoretical one.

**Before starting, check for orphans (HK-019):** `Get-CimInstance Win32_Process` for stray
`bash.exe … supervisor*.sh` left over from earlier runs. Kill the supervisor's own process at
teardown, not just the app.

## 6. Health sampling — what to watch without interacting

Sample periodically and stay silent unless something trips. The failure modes that matter here are
all **silent**, which is why they need sampling rather than log-watching:

| signal | healthy | escalate if |
|---|---|---|
| **WAV count per instance** | strictly increasing | flat for >2 cycles — archiving has stopped (the 07-29 failure) |
| **free disk** | covers remaining duration | projected to exhaust before the planned end |
| **`\|dt\|` on 8080** | inside 0.5 s | approaches or crosses 0.5 s — drift fix is merged, so this would be new |
| **our decodes vs WSJT-X** | ratio roughly stable | sustained collapse (07-29 went 59% → 18% → 2% at hour 13) |
| **supervisor retries** | 0 | any restart at all — log it; ≥2 means investigate |

**Wake the Captain for:** archiving stopped, disk exhaustion projected, drift crossing 0.5 s, or a
second supervisor restart. **Not for:** normal propagation swings, overnight decode counts dropping
(expected on 20m), or a single clean restart.

## 7. Post-run — three things, in this order

1. **Gather artefacts (HK-016).** `tools/gather_live_run_artefacts.py` is on `main`. Dated
   directory with a `README.md`, both `ALL.TXT`s, the daemon log, the WAVs, `cycle-archive.csv`.
   **Only 1 of 19 prior runs complied** — this is the step that gets skipped.
2. **Run jt9 offline over the 8080 WAVs.** `20260729_live_run_1831-8080` has our log and WSJT-X's
   but **no `jt9_ALL.TXT`** — only the 8081 band folders have one. Without it the new corpus cannot
   feed the existing analysis tooling at all. With it we have three decoders on identical audio.
3. **Produce a contiguity/segment report before any analysis.** Gap > 5 min in `cycle-archive.csv`,
   per instance, per band, with per-segment durations and density ranges. **This is today's lesson
   made procedural:** the last corpus was analysed for a month before anyone checked it was one
   session. Establish segment structure as a fact of the corpus, up front, not as a later discovery.

## 8. Not in scope for this run

- **No decoder experiment branches.** `d001-c1`, `d001-c2`, `d001-c4` carry candidate-cap, LLR and
  min-score changes. **Capture must run the shipped `main` build** — a corpus gathered on an
  experimental decoder is worthless as a baseline.
- **No analysis arms.** S.1b is designed but **not authorised**; the investigation is parked. This
  run gathers, it does not measure.
- **No `pre_merge_check.py`** (HK-006) — the Captain's trigger only, never QA's judgement call.
- **NFR-021:** real callsigns stay inside git-ignored `artefacts/`. Aggregates and counts only in
  anything committed.
- **WSJT-X instance setup is the Captain's.** One instance on the 8080 audio path is what's needed;
  a second WSJT-X would reintroduce the shared-`save\`-folder collision where UTC-synced WAV
  filenames silently overwrite each other.

## 9. Cross-references

- `2026-07-31-1702-…-s2a-diagnostic-exports-not-on-main.md` — why `d001-c4` is not merged and what
  depends on it (not this run).
- `2026-07-31-1730-…-s1-void-upheld-…md` — the parked investigation's state; S.1b awaits the Captain.
- `DEFECT-capture-clock-drift-silent-decode-loss.md` — the failure item 6's `|dt|` row watches for.
- `dev-tasks/2026-07-29-cycle-audio-archive-null-on-settings-save.md` — item 1's defect, with the
  live evidence from 2026-07-29.
- `tools/gather_live_run_artefacts.py` — item 7.1.

---

*Per HK-015 this is Architect → QA: material for QA to act on and scope, not tasks issued by me;
`dev-tasks/` remain QA's to author. Per HK-014/HK-010 committed locally, no push, no merge, and I do
not ask for one. Per HK-011 nothing here touches `src/`. Per HK-017 filename and byline carry
`date -u` UTC. Per HK-020 items 1–3 are the run's real goal and the configs that would silently
defeat it, verified before arming rather than inherited from a script header. Per HK-022 item 1
exists because a green CI leg says nothing about which binary the running daemon actually loaded —
§1's three layers were read from `main` at `8fedeaf`, not assumed from the PR being merged.*
