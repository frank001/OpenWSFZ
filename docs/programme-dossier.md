# OpenWSFZ Programme Dossier

**Continuity record — everything needed to resume this project cold.**

| | |
|---|---|
| Compiled | 2026-08-27 21:00Z |
| Native shim | `20260046` |
| Last full S1–S8 sweep | `22b749c` — overall **PASS** |
| Open GitHub issues | 6 |

> **Scope and authority.** This is a navigational document. Where it and a dated report
> disagree, **the report is authoritative for its own run** and this dossier is stale.
> Figures in §3 and §5 were re-derived independently from the run's matched CSVs rather
> than quoted from the report.

---

## 1. Resume here

If you read nothing else, read this.

1. **The product works and its measurement system is sound.** The last full S1–S8 sweep
   passed every ratified gate. Measurement repeatability is excellent — %GR&R well under
   1% on all three continuous responses.
2. **The one material product problem is decode yield against WSJT-X**, specifically on
   overlapping and near-neighbour signals. This is **D-001**, and it is the whole story of
   the last three months.
3. **Decode performance has been flat since 2026-06-20.** The large early gain came from
   the D-009 fix in June. Eight sweeps since show no trend. Effort in that window went into
   *instruments and diagnosis*, not shipped decode changes.
4. **The remaining gap is localised, not diffuse.** Every one of the 46 co-channel misses
   in the latest sweep occurs at a frequency separation between 5 and 19 Hz. That band has
   an established cause and a measured footprint.
5. **The fix space is narrow because most of it is already closed.** Three of the four
   obvious remedies are under standing prohibition after being tried and reverted.

> **Before proposing any work, read §8 (closed routes) and §9 (prohibitions).**
> This programme has repeatedly re-derived conclusions that were already on disk, and has
> burned three build cycles on a remedy that was already dead. The single highest-value
> habit here is reading the existing findings before reasoning.

---

## 2. What OpenWSFZ is

A daemon-plus-web-GUI FT8 amateur-radio station: it captures receiver audio, decodes FT8
traffic, displays decodes, and can run automated QSOs including transmit, logging and spot
reporting.

- **Runtime** — .NET daemon (`OpenWSFZ.Daemon`) with a browser front end over WebSocket;
  audio via WASAPI on Windows.
- **Decoder** — native `libft8.dll`, a vendored fork of `kgoba/ft8_lib` v2.0, reached by
  P/Invoke through a shim.
- **Reference instrument** — WSJT-X, run side-by-side on identical audio.

### Component map

| Area | Path | Notes |
|---|---|---|
| Decode pipeline | `src/OpenWSFZ.Ft8/` | Framing, interop, decoder orchestration |
| Native decoder | `native/ft8_lib_vendor/` | Vendored ft8_lib plus `refine/` additions |
| Patched decoder TU | `native/ft8_lib_build/patched/ft8/` | **Only** `decode.c` is patch-vendored here |
| Audio capture | `src/OpenWSFZ.Audio/` | WASAPI capture, device selection |
| QSO automation | `src/OpenWSFZ.Daemon/` | Caller/answerer services, ADIF logging |
| Web GUI | `src/OpenWSFZ.Web/`, `web/js/` | Decode panel, settings, WebSocket hub |
| Measurement rig | `qa/rr-study/` | Gage R&R harness, scenarios, analyser |

**Licence posture.** The repository is AGPL-3.0. Standing policy is **permissive-only**
(MIT / BSD-2 / BSD-3 / ISC) for incoming third-party code. No GPL-derived code may be copied
in from WSJT-X or anywhere else — read for method only. Third-party attribution is not yet
shipped and is outstanding work.

---

## 3. Current state

As measured by the 2026-08-27 full sweep.

| Measure | OpenWSFZ | WSJT-X | Gap |
|---|---:|---:|---:|
| S7 co-channel recovery | **78.60%** | 97.67% | −19.1 pp |
| S8 realistic band scene | **91.67%** | 96.67% | −5.0 pp |
| S4 message recovery | **66.67%** | 64.81% | +1.9 pp |
| S1 SNR bias | +1.22 dB | +0.75 dB | both within ±2 dB |

### Ratified gate status

| Gate | Scope | Value | Verdict |
|---|---|---:|---|
| %GR&R / ndc | S1 reported SNR | 0.3% / 24 | PASS |
| %GR&R / ndc | S2 reported frequency | 0.0% / 1503 | PASS |
| %GR&R / ndc | S3 reported DT | 0.4% / 21 | PASS |
| FP event rate (95% UB) | S5, both appraisers | 0/60, UB 4.87% | PASS |
| SNR bias | S1 OpenWSFZ | +1.22 dB | PASS |
| Attribute κ | S4+S5 pooled | 0.588 | **Advisory — not evaluable**, see §12 |

**Overall verdict: PASS.**

### Recently shipped

- **F-001 R5 L1+L2 slice** — callsign-parse hardening at five of six comparison sites;
  the sixth deliberately unchanged and documented.
- **Sweep report corrections** — four review corrections landed, including two harness
  defects (an S8 station-pair collapse, and a verdict printed beside the wrong metric).
- **Tooling** — `pre_merge_check.py` gained `-h`/`--help`; a Windows console encoding
  crash fixed.

---

## 4. Architecture essentials

Four facts about the decode path that took six weeks to become visible, because every early
investigation aimed downstream of them. They explain most of the programme's history.

1. **There is no sync refinement.** Candidate search feeds `ftx_decode_candidate()`
   directly — the candidate's *quantised grid position* goes straight into likelihood
   extraction.
2. **The lattice is coarse.** `K_TIME_OSR = K_FREQ_OSR = 2` over 6.25 Hz tone spacing and a
   0.16 s symbol gives a **3.125 Hz / 0.08 s** lattice; worst case ±1.5625 Hz and ±0.04 s.
3. **Extraction is non-coherent, magnitude-only, single-symbol.** `ft8_extract_symbol()` is
   a max-log over 8 magnitude bins, phase discarded. `ft8_decode_multi_symbols()` exists
   with **no call site**.
4. **This is architectural, not parametric.** It is why a 45-point parameter sweep bought
   **+0.109 pp**. Do not propose parameter sweeps against it.

### Facts that will cost you if you miss them

| Fact | Why it matters |
|---|---|
| `ALL.TXT` fields are `[4]` SNR, `[5]` DT, `[6]` frequency | Confusing `[5]` and `[6]` does not merely corrupt a result — it **exactly inverts** the on-grid/off-grid contrast |
| Reported frequency is **integer Hz** | The lattice residual has only 13 possible values; the time axis is **not identifiable** from log output at all |
| Native sources are mostly *not* in the repo | Only `decode.c` is patch-vendored; everything else compiles from the vendored upstream tree |
| Hashed callsigns resolve to `<...>`, never discarded | An unknown hash costs message *text* only — the decode is not lost |
| The QA synthesiser is **encoder-only** | A round-trip through it tests self-consistency, not alignment. It drives the real decoder unmodified |
| `FT8_SHIM_VERSION` identifies nothing | Versions have collided across branches. **Pin the SHA256** and assert it against a manifest — never infer a build from a label |

---

## 5. D-001 — the decode gap

The central product problem, and the subject of essentially all investigative work since
June: OpenWSFZ recovers fewer signals than WSJT-X when signals overlap or sit close in
frequency.

### Evidence base

| Source | Population | Result |
|---|---|---|
| S7 synthetic, co-channel | 215 messages, controlled overlap families | 78.6% vs 97.7% |
| S8 synthetic, band scene | 12 stations × 5 trials | 91.7% vs 96.7% |
| S6 off-air corpus replay | 42 real WAVs, 2,799 observations | 69.7% of WSJT-X |

### Where the deficit actually sits

Attributing every one of OpenWSFZ's 46 S7 misses to its scenario part gives an unusually
clean result: **all 46 occur at frequency separations between 5 and 19 Hz.** Every part at
ΔF ≥ 25 Hz decodes perfectly. On S8, all five misses are a single station 12 Hz from its
neighbour.

| Miss family | Misses | ΔF | Status |
|---|---:|---:|---|
| Near-neighbour, weaker signal | 15 | 7–11 Hz | Open |
| Near-neighbour, equal level | 11 | 5–6 Hz | Open |
| 3-stack co-channel | 15 | 19 Hz | Structural — waived 2026-06-22 |
| Co-channel 2-stack | 5 | 7–13 Hz | Open |
| **Everything else** | **0** | — | — |

### The exclusion zone, measured

A dedicated arm established the mechanism causally: removing the interfering neighbour —
nothing else changed — flips the victim station from **0/100 to 100/100**. The locus is
**extraction**, not candidate selection, and the level dependence is a **~3 dB knife-edge**.

| ΔF | Tone bins | Recovery |
|---:|---:|---:|
| 6.25 Hz | 1 | 0% |
| 12.00 Hz | ~2 | 0% |
| 18.75 Hz | 3 | 0% |
| 25.00 Hz | 4 | 27% |
| 31.25 Hz | 5 | 98% |
| 50.00 Hz | 8 | 100% |

**The newest and least expected datum:** at *exactly* co-frequency (ΔF = 0) a 6 dB weaker
signal survives 5/5, while at 9 Hz the same deficit dies 0/5. Partial bin overlap appears to
be the hazard, not overlap as such. **That point rests on N = 5 — it is a lead, not a
result.**

### What closing this family would be worth

| Scenario | Now | If closed |
|---|---:|---:|
| S7 | 78.60% | ≈ 90.7% (+12.1 pp) |
| S8 | 91.67% | 100% (+8.3 pp) |

That would take S8 **past the reference decoder** and close roughly two-thirds of the S7
gap. It is an upper bound, and assumes one mechanism and one fix for the whole family —
which is exactly what is not established.

---

## 6. Defect register

Documents live at repository root as `DEFECT-*.md`.

| Defect | Severity | Locus | State |
|---|---|---|---|
| **12-bit hash misresolution** — the hashed-callsign lookup names the *wrong* station | High, product-facing | `ft8_shim.c:637-655` | **Open** |
| **Reported SNR carries a gain error**, not an offset — `ours ≈ 0.6865 × ref − 4.742 dB` | Moderate–high, product-facing | `ft8_shim.c` | **Open** |
| **Decode panel latency** — app consumes ~24% of the actionable QSO window | Moderate | `Ft8Decoder` / web | Filed, not pursued |
| **Cycle discard on restart** — valid cycles dropped for up to 15 s after restart | High | `Daemon/Program.cs` | **Open** |
| **WebSocket status omits `DecodingEnabled`** — GUI misreports state after restart | High | `WebSocketHub.cs` | **Open** |
| **Cross-platform decoder** — decoder Windows-only per its own document (NFR-001) | High | `Ft8LibInterop.cs` | Document never formally closed; Linux/macOS binaries are built and CI-tested — **verify current status before citing** |
| **Capture clock drift** — silent total decode loss after ~13 h | High | `CycleFramer` | Resolved (`be5960a`) |
| **Native stack overflow** on PCM residual | High | `ft8_shim.c` | Moot — feature reverted |
| **Modulator positive-DT clamp** — mislabelled synthetic truth for 2 of 10 parts | High, measurement integrity | `qa/.../modulator.py` | Fixed — see below |

> **Outstanding consequence of the modulator defect.** Because synthetic truth was wrong for
> 2 of 10 S3 parts from 2026-06-06 onward, **every S3 bias, linearity and GR&R figure since
> that date was scored against wrong truth for those parts.** An S3 re-grid and a follow-up
> pre-registration remain open. Separately, the WSJT-X DT convention offset (`0.55 s`) is an
> *unknown-accuracy correction, not a stable constant* — measured between 0.531 and 0.674
> across three builds.

---

## 7. Open GitHub issues

| # | Title | Substance |
|---|---|---|
| [#3](../../issues/3) | D-001 co-channel and weak-signal decode gap | The central issue. **Its stated fix path is now closed** — it proposes successive interference cancellation, which is prohibited. Its headline figures are stale (quotes ~46%; actual 78.6%). |
| [#132](../../issues/132) | 12-bit hash collisions resolve to the wrong callsign | 16,320 distinct callsigns seen against a 4,096-entry table; 50.9% of resolved queries had ≥2 entries sharing a code. Callsign-level disagreement 51.3% on the measurable subset; decode-level 37.9%. A wrong name is loggable — worse than an honest `<...>`. |
| [#122](../../issues/122) | Decode panel latency consumes ~24% of the QSO window | A budget problem, not a stall. TX occupies 12.64 s of the 15 s slot leaving ~2.36 s; decodes land at p50 ~15.56 s. No work authorised. |
| [#111](../../issues/111) | D-001 attribution rests on a single session | The "98.5% decoder-side" split — load-bearing for closing the whole capture thread — comes from *one* 21-minute session, one device, one band. Risk is asymmetric. |
| [#60](../../issues/60) | F-001 ~2–4% genuine hash-resolution gap | Structural cold-start explains 92–95%; a genuine residual of 3.68% / 2.12% persists across two independent nights. Root cause undetermined. |
| [#59](../../issues/59) | Pooled attribute-κ gate not ratifiable | Its original blocker (a matcher ceiling effect) **is fixed**. A second, independent blocker was raised 2026-08-27: κ is sensitive to the S5 negative count, which has since changed. |

---

## 8. Investigated angles and closed routes

The most valuable section for anyone resuming. Each of these consumed real effort;
re-proposing one wastes it twice.

### Closed with a real finding

| Arm | Question | Outcome |
|---|---|---|
| `F-NBR-A` | Why does one S8 station never decode? | **Neighbour is causally necessary and sufficient** (0/100 → 100/100 on ablation). Zone 3–5 tone bins; ~3 dB knife-edge; locus = extraction |
| `X1` | Is band a first-order term in the gap? | **Yes** — +5.70 pp standardised, falling only to +4.83 pp under the finest SNR stratification the corpus supports |
| `X2` | Does crowding drive recovery? | **Yes** — +17.22 pp at the density floor vs the crowded regime, and *not* an SNR-composition artefact |
| `T1` | Does frequency quantisation cost decodes? | Real but small — 3.16 pp, **a floor not a point estimate**. Never publish a "corrected" version of this figure |
| `C.1` | Does the candidate cap bind? | Swept 140/300/600 → +0.93% at 300, byte-identical at 600. The family is **bounded** |
| `P2` | Does PCM input scale cost decodes? | **No** (≤0.5 pp across ±18 dB). Closes input scaling permanently |
| `D-009` | Can parameters close the gap? | 45 parameter points bought **+0.109 pp**. This established the gap as architectural |

### Void, retracted or abandoned — read before re-deriving

| Item | Why it died |
|---|---|
| **Spectral locality** — *retired* | Four attempts, **zero readings**. Local-vs-diffuse is permanently unanswered and the route is decided without it. Do not re-propose under any name. X1/X2 are unaffected and remain citable |
| **`jt9 -d 3` as a reference decoder** — *void* | +93.8% vs OpenWSFZ and duplicate output pairs. Replacement: fresh WSJT-X on identically replayed audio |
| **The M-series** (proxy measurement of the refiner) — *abandoned* | The study design introduced a confound the real integration would never have had. Much of five rounds chased it |
| **Phase B kill gate** — *void, not failed* | The instrument-gain precondition still fires. The route **must not be called dead** — no verdict may be read from it |
| **`A` = 15.55, `k_50` = 13** — *uncitable* | Computed but voided at an instrument check. Never cite in any form |
| **"17m runs 2–3 points above 20m"** — *retired* | Under exact density × SNR standardisation it is +0.76 to +1.34 pp. Do not carry the old figure forward |

---

## 9. Standing prohibitions

Binding on all work. Each was earned by a failed attempt, and several were re-proposed after
closure — which is why they are stated this bluntly.

- **Subtract-and-resynthesise is DEAD.** Built three times, reverted three times, plus two
  production access violations. Best hypothesis: *you cannot subtract a signal you cannot
  locate* — templates sit on a coarse lattice.
- **The candidate-budget family is CLOSED TWICE.** No caps, no extra passes.
- **Input scaling is CLOSED** — normalisation, AGC, softmax/temperature, equalisation.
- **Oversampling ratio 2 → 4 is not closed**, but earns its own pre-registration *with
  false positives as the primary metric*, not recall.
- **Never re-read a closed gate with a better metric.** That earns a new pre-registration.
- **Privacy:** only synthetic `Q`-prefix callsigns in version control. Real-callsign text
  appears in matched CSVs and raw logs — all gitignored; verify per file, never assume.

---

## 10. Open decisions

Owed by the Product Owner. Work is blocked or ambiguous until each is answered.

| Decision | Options / recommendation | Blocks |
|---|---|---|
| **Near-neighbour route** | (a) run one bounded discriminator arm *(recommended)*; (b) go straight at the blocked coherent-extraction precondition; (c) accept the gap and stop proposing arms | All decode-yield work |
| **Fixed κ negative count** | Ratify a fixed S5 negative count, or accept that pooled κ stays non-comparable across the battery change | #59; any κ-based gate |
| **Hash misresolution remedy** | Shape not chosen. A wrong name is worse than `<...>` — "refuse to resolve on ambiguity" is the obvious candidate | #132 |
| **SNR gain-error correction shape** | The correction form is itself the open question — recalibrate the formula vs. correct downstream | Product-facing SNR, spots |
| **Shim version renumbering** | Versions collide across unmerged branches; a renumbering proposal awaits sign-off | Branch merges |
| **Git history purge** | ~96 MB of per-row JSON dumps. Explicitly *not urgent*; must not pre-empt decode work. A rewrite invalidates every commit SHA cited in reports | Nothing — deferred |

---

## 11. Potential improvements

### Tier 1 — moves the product

| Improvement | Prize | Cost / risk |
|---|---|---|
| **Close the near-neighbour exclusion zone** | Up to +12.1 pp S7, +8.3 pp S8 — would pass the reference decoder on S8 | Mechanism unresolved; most remedies prohibited. One bounded arm first |
| **Coherent multi-symbol extraction** (the known architectural limb) | Addresses the root architectural gap rather than a symptom | **Built but not shippable** — no production call site, and its own gate has not cleared. Clearing that precondition is the real task |

### Tier 2 — product quality, independent of decode yield

- **Hash misresolution** — stop emitting confidently wrong callsigns. High user-visible
  value, self-contained, and the measurement already exists.
- **SNR gain error** — reported SNR is systematically compressed; affects logs, display and
  outbound spots. Also interacts with a suppression threshold that assumes absolute dB.
- **Restart correctness** — cycle discard and the WebSocket state mismatch are both
  straightforward, both user-visible, and both open.
- **Cross-platform decoder** — a stated requirement whose defect document has never been
  formally closed.

### Tier 3 — infrastructure and hygiene

- **Pin the harness run directory once per battery.** A mid-run commit currently splits
  results across two directories and crashes the analyser. Cheap, and it has already bitten.
- **Stop the analyser appending to the trend file on ad-hoc runs** — an unguarded side
  effect that silently pollutes the historical series.
- **File the self-contained-publish crash** — the ahead-of-time build produces a daemon that
  crashes on real audio capture. Currently recorded only inside a report section.
- **S3 re-grid** — required to retire the modulator-defect contamination of historical S3.
- **Third-party attribution** — not yet shipped, and required by the licence posture.

---

## 12. The measurement rig

A Gage R&R study treating the two decoders as *appraisers* measuring known injected truth.
It is the programme's instrument, it is trustworthy — and it has traps.

| Scenario | Measures | Gated |
|---|---|---|
| S1 / S1b | Reported SNR accuracy; low-SNR decode threshold | Yes / No |
| S2 | Reported frequency accuracy | Yes |
| S3 | Reported time-offset accuracy | Yes |
| S4 | Attribute agreement under density / QRM | Advisory |
| S5 | False positives on signal-free slots | Yes |
| S6 | Real off-air corpus replay — external validity | No |
| S7 | Per-message recovery under overlap | No |
| S8 | Realistic 12-station band scene | No |

### Traps in the rig

- **The analyser appends to the trend file on every run**, including ad-hoc regenerations.
  Check and revert afterwards.
- **Run directories derive from live `HEAD` per scenario.** Any commit landing mid-battery
  splits the results and crashes the matcher. **Never commit while a run is live.**
- **Matched CSVs carry real-callsign text** from unmatched decodes — hundreds of rows per
  file. Gitignored, but verify per file.
- **An uncleared log contaminates every matched CSV.** Clear both decoders' logs before
  arming.
- **Pooled κ is prevalence-sensitive** — it moves when the negative battery is resized, with
  no change in decoder behaviour. Do not read trends across a battery change.
- **Population helpers may truncate in file order rather than sample.** Check what a
  `limit=` argument actually does before reusing one, and report cluster counts, not just
  row counts.
- **Observation ≠ independence.** Decodes cluster by station and by cycle; naive confidence
  intervals have been off by ~3.5–4×.

---

## 13. Working rules

The project runs a role separation and a housekeeping register (`HK-xxx`).

| Role | Responsibility |
|---|---|
| **Architect** | Specs, rulings, reviews. Writes *for* QA. Commits locally and stops — **never pushes or merges** |
| **QA** | Authors dev-tasks, runs studies, may **refuse** a spec whose gates are not mechanical. Never declares "ready to merge" unprompted |
| **Developer** | Separate session for any `src/` change. Docs and QA tooling are exempt |

### Rules with teeth

| Rule | What it requires |
|---|---|
| **Check gathered data first** | Open existing findings before any ruling or design. Prefer a five-minute measurement to a paragraph of reasoning. Has fired repeatedly — every time on a file that already existed |
| **Verify what a green result covered** | Which reference? Was the branch current? Could a leg have been skipped? A round-trip against your own generator tests self-consistency, not correctness |
| **Pre-registered checks must be mechanical** | Hard thresholds, consequence stated as an assertion, rows mutually exclusive in strict order, metric identifiable from its data |
| **An instrument cannot bound its own blind spot** | Before deriving a boundary, ask whether the instrument's response is flat where the boundary sits |
| **Byte-identical must be diffed** | Never asserted from a version label. Pin and assert SHA256 against a manifest |
| **Ask what the instrument already records** | A human is an actuator, not a sensor. Ask them to cause events; read consequences off the machine |
| **Merge needs explicit sign-off** | Green CI is necessary, never sufficient |

### Environment notes that waste hours if unknown

Audio routing runs through a virtual mixer input, not the previously used cable device —
several harness defaults still point at the old one and must be overridden explicitly.
Capture endpoint identifiers go stale silently across replug while the daemon keeps
reporting healthy. The Windows console is `cp1252` — write ASCII or reconfigure the stream.
CI runs twice per pull-request commit by design; the obvious de-duplication is blacklisted
because it kills the leg a release gate depends on.
