# R-F4 + L1′ **default ON**: Developer handoff spec (no arm, no replay)

**From:** Architect · **To:** QA (for the Developer handoff) · **Date:** 2026-11-09 16:34:25Z (`date -u`) · **Branch:** `arch/rf4-l1p-default-on`
**Authority:** the Captain, 2026-11-09, on the SUB-COVER ruling's §3 options: "1. option a. turn them both on." Option (a) was **both defaults ON now, with no live ON run first**. He was told the alternative (one live ON run under `frans` first) and did not choose it.
**Base:** `origin/main` `e3db42cf` (VERSION 0.68). **Format copied from the COH-MULTISET default-ON handoff** (`dev-tasks/2026-10-25-coh-multiset-default-on.md`, `6e1bdb2a`, merged as #264), per HK-034. This document is docs only: `git diff --stat origin/main -- src/ native/` is empty.

---

## §0. What changes, and what the evidence is

| setting (JSON key under `decoder`) | today | after | evidence on file (each measured **alone**) |
|---|---|---|---|
| `coherentFallbackResidualUngated` (COH-GATE-G **R-F4**) | `false` when absent | **`true` when absent**; explicit `false` stays OFF | NET **+1.470 pp [1.296, 1.638]**, its second night (accepted) |
| `lateSubtractionRound` (LATE-SUB **L1′**, PR #274) | `false` when absent | **`true` when absent**; explicit `false` stays OFF | NET **+0.772 pp [0.655, 0.889]**, its third night (ACCEPT-3N, ruling `eb422516`) |

- **Together they are unmeasured.** They need not add: both act on the residual side of the fallback, R-F4 on what the fallback publishes and L1′ on a round after it. The Captain chose to turn them on without a combined measurement; §3 makes the first live data show the combination, **reported, not gated**.
- **No `native/` change.** Both behaviours are on `main` already, behind their flags (`DecoderConfig.cs:57–60`, `:276–294`; daemon wiring `Program.cs:855–856` at startup and `:964–965` per config change). Only the defaults move.
- **Preconditions are already defaults** (checked in `DecoderConfig.cs:50–56`): R-F4 acts only in `coherentFallbackAudio = Both` (default `Both`); L1′ needs `decodingDepth = Deep` (default) and `coherentFallbackEnabled = true` (default). A station config with an explicit `Original`/`Residual`, `Normal`, or fallback off would leave one or both inert. §2's readback covers that.

## §1. Developer task (rows D1–D3, as #264)

**Sites of each default (all must move together, or the JSON-absent and code-constructed paths disagree):**
- `src/OpenWSFZ.Abstractions/DecoderConfig.cs`: the `[JsonConstructor]` parameters `coherentFallbackResidualUngated = false` and `lateSubtractionRound = false` (`:58`, `:60`), the two property declarations (`:283`, `:294`, which have no initialiser today and so read the CLR `false` on the non-JSON path; give them `= true`), their doc comments ("**Default `false`**"), and the two "(default false)" comments at `:57`, `:59`.
- `src/OpenWSFZ.Daemon/Program.cs:855–856`: the two "default false (key absent = off)" comments.
- The backing-field comments in `Ft8Decoder.cs:246` and `:259` ("the daemon sets the configured value (default false)"). Whether `Ft8Decoder`'s own backing fields start `false` is **not** changed: the daemon always sets them from config (`Program.cs:855–856`), and tests that build an `Ft8Decoder` directly keep today's behaviour. The Developer states which way each such site went.

- **D1 (tests first, each able to fail).** For **each** of the two keys: (a) a configuration with the key absent gives `true` in the daemon's decoder: the `DecoderConfig` bound from JSON without the key, **and** the `Ft8Decoder` the daemon sets up from it reads back true. (b) An explicit `false` gives `false` in both. Run (a) against the old default first and watch it fail (QA repeats that against `e3db42cf`). A config POST that does not mention the key leaves the current value as it was (the existing overlay tests must still hold in both states, HK-035).
- **D2.** The existing COH-GATE-G (R-F4), LATE-SUB (L1′), `Coherent*` and config overlay tests pass. A test that assumed the old default is changed **only where it asserted that default**; list each one with FILE:LINE so QA can see none was weakened. Full unfiltered `dotnet test OpenWSFZ.slnx` green (exact command line and per-project counts; HK-022). `openspec validate --all --strict` clean.
- **D3.** QA's HK-039 review record (`Reviewed-commit: <40-hex>` + `Verdict:`) committed before anything is deployed. QA repeats four mutations: each new default reverted to `false` must fail its D1(a); each `false` branch forced to ignore the explicit key must fail its D1(b).

**User-facing: yes.** `VERSION` 0.68 → **0.69** (the #272 build used 0.69 on an unmerged branch; it was closed, so 0.69 is free on `main`; `check_version_bump.py` decides, and the Developer quotes its output). README/REQUIREMENTS anchors as the version check requires. OpenSpec: amend the main specs `ft8-late-subtraction` and the COH-GATE-G spec for the new default (QA's convention for the change folder).

**Report to QA:** commit hash(es); exact test command lines with counts; the D1 fail-then-pass evidence for both keys; the old-default assertions changed (FILE:LINE); the VERSION bump and `check_version_bump.py` output; confirmation that the diff touches nothing under `native/`. **Do not push.**

## §2. Before and at deploy (QA)

- **Readback of the station's saved config under `frans`** (HK-035; a readback, not an assumption): no explicit `"coherentFallbackResidualUngated": false`, no explicit `"lateSubtractionRound": false`; and `coherentFallbackAudio` = `Both`, `decodingDepth` = `Deep`, `coherentFallbackEnabled` = true (or absent). If any of them is explicit and blocks the default, **QA tells the Captain** with the key and value. It is his station config, so he decides whether to change it; QA does not POST it on its own.
- Order (HK-006, HK-010, HK-033): HK-039 record → `pre_merge_check.py` from a clean checkout of the exact commit → the Captain's push go → his merge sign-off → deploy.
- 🔴 **Era.** The daemon start on the merged build starts a new live era, **"RF4+L1′ ON"**. QA stamps it with `date -u` on the board. Live figures are never pooled across it (same rule as "MS ON", `nhard` and the `frans` cutover). It falls inside the `frans` era, which has **no OFF live data yet**, so there is no same-account OFF baseline. That is the cost of option (a), and the Captain accepted it.

## §3. First live session: reported, not gated

The Captain chose not to gate the defaults on a live run. The first live session on the new build (radio and antenna are his part) is therefore read, not judged. QA reports, from the daemon log and `ALL.TXT` aggregates only (HK-037):
- that the daemon read back both flags `true` (the per-cycle log line or the config API);
- per 100 cycles: batch-5 (L1′) decodes; residual-run rows published by R-F4's ungating; residual-pass and fallback **deadline abandons**, beside the same counts from the last ON-arm replays of each lever (L1′ third night, R-F4 second night) for scale, **not** as a bar;
- the latest batch arrival time (p95, max) against the 13 s cycle, because L1′'s batch 5 can arrive too late for that cycle's TX decision (`DecoderConfig.cs:289–290`).

**If abandons or late arrivals look materially worse than either lever's own replay, QA says so to me and the Captain, with the numbers.** Turning one or both off again is an explicit `false` POST: the overlay keeps everything else (HK-035).

## §4. Predictions (Architect; scored when QA's §3 report arrives)

| # | prediction | P | class |
|---|---|---:|:---:|
| DO-1 | D1–D3 pass on the Developer's first submission (no CHANGES REQUIRED from QA) | 0.65 | C |
| DO-2 | the station readback finds no explicit key blocking either default | 0.70 | C |
| DO-3 | first live session: deadline abandons per 100 cycles ≤ the larger of the two levers' own replay rates + 1 | 0.70 | H |

**Reasoning.** DO-1: #264's equivalent change passed review first time (`93a209cb`), but this one has two keys and four mutations. DO-2: an explicit `false` exists only if someone POSTed it or the config was saved with every key written; the `frans` config is new. DO-3: the levers ran together in no arm. 🔴 **Bias check:** H-class calls lean toward "it works"; DO-3 is held at 0.70, not higher.
