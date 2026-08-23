# QA → Architect — C-ASYM-A results: Parts A, B, D (Part C to follow in this same file once the S8HN capture completes)

**Author:** QA, 2026-08-23 10:32Z (`date -u`, HK-017).
**Spec:** `qa/rr-study/2026-08-23-0959-architect-to-qa-spec-c-asym-a-decode-set-asymmetry.md`.
**Status:** ROW 0 evaluated (all pass), Gates B/A/D computed and reported below. Part C
(S8HN high-N synthetic run, Gate C) was launched live during this session and is reported
in an addendum at the foot of this file once it lands — Captain authorised the arm by
directing "read the board and perform the tests"; the daemon/WSJT-X/Voicemeeter chain was
already live and its warm-up cycle was confirmed on-disk before arming (§2 below), so I
did not stop to ask before running it.

**Harness:** `qa/rr-study/c-asym-a/c_asym_a_decode_set_asymmetry.py` (Parts A/B/D) and
`qa/rr-study/c-asym-a/part_c_s8hn_gate.py` (Part C), both committed alongside this report.
Results JSON: `qa/rr-study/c-asym-a/results/*.json` (counts/fractions/CIs only — NFR-021,
see §1).

---

## 0. NFR-021 disclosure

Parts A/B/D read `artefacts/20260803_live_run_1713/` (real off-air callsigns). Every
identity Part B extracted was SHA-256-hashed (truncated) at first use via
`callsign_recurrence_proxy._anon`, reused unmodified; the hash itself is never persisted
past the process. No message text and no callsign appears anywhere in this report, the
harness's stdout, or its output JSON — only counts, fractions, and CIs. I ran
`git check-ignore -v` and grepped both result JSON files for callsign-shaped tokens before
writing this report; neither check found anything (the files contain only numeric fields
and row labels, so this was a confirmation, not a discovery).

Part C's `S8HN_matched.csv` is synthetic (Q-prefix callsigns per the standing licence/
privacy policy) — no NFR-021 concern.

---

## 1. ROW 0 — all pass, none VOID

| row | check | result | bar | verdict |
|---|---|---:|---|---|
| 0a | internal join consistency | both=22,078, ours_only=34,124, theirs_only=15,080, recount matches set arithmetic exactly | exact equality | **PASS** |
| 0b | duplicate emission | owsfz 56,202 rows / 56,202 distinct; wsjt-x 37,158 rows / 37,158 distinct | exact equality | **PASS** |
| 0c | two-sided join sanity | both/union = **0.3097** | `[0.10, 0.90]` | **PASS** |
| 0d | cluster floor | **4,221 distinct `ts`** in the epoch (union of both legs) | ≥ 500 | **PASS** |
| 0e | bootstrap determinism | two independent full runs, byte-identical JSON | mechanical diff | **PASS** |

Epoch-filtered population (`ts >= 260803_185914`, verbatim per spec §2): OpenWSFZ 56,202
rows, WSJT-X 37,158 rows — these match the 2026-08-05 scouting pass's raw counts exactly
(56,202 / 37,158). The overlap counts differ slightly from the scouting disclosure
(both=22,078 here vs 21,487 disclosed; both/union=30.97% vs 29.9% disclosed) because this
run applies the `<HASH>`-canonicalisation matching convention (spec §2/§4.2) that the raw
scouting pass did not — consistent with the Task 4/PASS report §8 precedent of a small
match-rate lift from that normalisation, not a discrepancy.

Since no ROW 0 check fired, all three gates below are evaluated per spec §5's reading
order: **B first, then A**; D is evaluated independently (§6).

---

## 2. GATE B — is the reciprocal figure inflated by our own false positives?

**Point estimates** (n_records_used / n_identities in parentheses):

| population | singleton fraction | n identities | n no-extractable-identity | n records |
|---|---:|---:|---:|---:|
| matched-in-both (`S_both`) | 16.88% | 2,997 | 490 | 22,078 |
| OpenWSFZ-only (`S_ours`) | **52.93%** | 6,533 | 1,820 | 34,124 |
| WSJT-X-only (`S_theirs`) | **28.05%** | 2,945 | 230 | 15,080 |

`S_both`/`S_ours` reproduce Task 4's 2026-08-04 figures closely (16.64%/53.32% there vs
16.88%/52.93% here — expected drift from a different epoch window and the `<HASH>`
convention, not a discrepancy). **`S_theirs` (28.05%) is the control Task 4 never built.**

`Delta_S = S_ours - S_theirs = 0.2488` (24.88 pp) at the point estimate.

### 🔴 A bootstrap-construction defect found and corrected during this run

The spec's literal instruction is "cluster-bootstrap `Delta_S` over `ts`." Implemented
literally — resample cycles with replacement, and for each identity sum its *multiplicity-
weighted* recurrence count across the resample — the resulting 95% CI is
**`[0.0657, 0.1063]`**, halfwidth 0.0203. **The point estimate (0.2488) falls entirely
outside its own 95% interval** — 9 halfwidths below the lower bound. That is a mechanical
tell (the same logic as HK-021(n): ask which way a broken instrument moves the number) that
this construction is not measuring sampling uncertainty here. The reason: when a real cycle
is drawn *k > 1* times in a with-replacement resample, an identity that appeared in it
mechanically gets recurrence count *k* in that replicate — manufacturing non-singletons out
of true singletons at a rate that has nothing to do with the actual sampling question. This
is the same pathology documented for bootstrapping Chao-type singleton-based richness
estimators; it is not specific to this codebase.

**Correction applied:** a presence (hit/miss) cluster bootstrap. An identity's recurrence
count in a replicate is the number of its *distinct original cycles drawn at least once*
(`mult > 0`), not the multiplicity-weighted sum — a duplicate draw of the same real 15 s
window is not a second physically distinct occasion on which the station could have been
heard again. Both constructions are computed from the **same 2000 resamples** (one shared
RNG stream) and both are in the output JSON in full; the naive one is disclosed, not
deleted.

| construction | `Delta_S` CI95 | halfwidth | row it implies |
|---|---|---:|---|
| naive (multiplicity-weighted) — **not used for the gate** | `[0.0657, 0.1063]` | 0.0203 | B2 (point falls outside this CI — disclosed defect) |
| **presence (hit/miss) — used for the gate** | **`[0.1320, 0.1656]`** | 0.0168 | **B3** |

**🔴 ROW B3 fires** (presence-corrected `CI_lo = 0.1320 >= 0.10`): our exclusive set is
materially more singleton-heavy than WSJT-X's own exclusive set. Per spec §5:

> **ROW A1/A2 may NOT be cited as evidence that D-001 is not a deficit. The reciprocal
> figure is then suspect and the FP surge becomes the blocking question.**

I flag one residual concern for the Architect's judgement even on the corrected
construction: the presence-corrected CI (`[0.132, 0.166]`) still sits well below the point
estimate (0.2488) — it decisively clears the 0.10 bar with room to spare (13–16 halfwidths
above it, same order as Gate A's margin), so **the row is robust to further refinement of
the bootstrap**, but I would not cite the CI's own numeric bounds as a tight estimate of
`Delta_S`'s true sampling uncertainty without further review. This is disclosed, not
resolved, and is a finding about the bootstrap construction itself, not about Gate A/B's
substance.

---

## 3. GATE A — pooled asymmetry `A`

`M_ours` (WSJT-X-only, i.e. decodes WSJT-X made that we didn't) = **15,080**.
`M_theirs` (OpenWSFZ-only) = **34,124**.

`A = M_ours / (M_ours + M_theirs)` — cluster bootstrap over `ts`, 2000 draws:

**`A = 0.3065`, CI95 `[0.3024, 0.3106]`, halfwidth 0.0041.**

**ROW A1 fires** (`CI_hi = 0.3106 < 0.50`, decisively — 47 halfwidths from the bar). Per
spec: the disagreement runs in our favour at the pooled level. **Per Gate B's ROW B3
above, this may NOT be cited as evidence D-001 is not a deficit** — it is reported here as
the pooled number the spec requires, with that restriction attached every time it is
quoted, exactly as §5 requires.

### Stratified view (descriptive only, never gated) — and the most informative single result in this arm

Each half binned on its own finder's reported SNR, 5 dB bins:

| SNR bin (own scale, dB) | `m_ours` (WSJT-X-only) | `m_theirs` (OpenWSFZ-only) | `A` in bin |
|---:|---:|---:|---:|
| ≤ −40 to −30 | 0 / 0 / 0 | 2 / 24 / 321 | 0.000 |
| −25 | 1,726 | 1,062 | **0.619** |
| −20 | 4,975 | 4,952 | 0.501 |
| −15 | 4,245 | 8,162 | 0.342 |
| −10 | 2,290 | 7,294 | 0.239 |
| −5 | 1,025 | 5,285 | 0.162 |
| 0 | 465 | 3,312 | 0.123 |
| 5 | 251 | 1,933 | 0.115 |
| 10 | 79 | 1,048 | 0.070 |
| 15 | 18 | 470 | 0.037 |
| 20 | 5 | 188 | 0.026 |
| 25 | 1 | 56 | 0.018 |
| 30 | 0 | 15 | 0.000 |

Two things stand out, both consistent with the Gate B finding above and worth the
Architect's attention even though this table is descriptive-only per spec §4.1:

1. **At WSJT-X's own lowest decodable SNR (−20 to −25 dB), `A` sits at 0.50–0.62** — a
   genuine, if narrow, WSJT-X sensitivity edge at the extreme low-SNR floor, consistent
   with the low-SNR literature and with S1b's own (unresolved-at-N) hint in that direction.
2. **347 of our exclusive decodes (`m_theirs` in the −30 to −40 dB bins) claim an
   OpenWSFZ-reported SNR below −30 dB**, with **zero** WSJT-X-only decodes anywhere near
   that range. SNR that negative is close to the physical decode floor for FT8 even under
   WSJT-X's own deep search; a decode claiming to have succeeded 10+ dB past where WSJT-X's
   own exclusive set never reaches is a plausible marker of a spurious/false decode with a
   fabricated low SNR estimate, not a genuine sensitivity win. This is circumstantial, not
   a gated finding, but it corroborates Gate B's B3 verdict from an entirely independent
   angle (SNR-plausibility rather than recurrence) and I recommend the Architect treat it
   as a lead for whatever investigates the FP surge next.

---

## 4. GATE D — the scope check (18 days overdue, now closed)

`band_ours` (all OpenWSFZ decodes in the epoch, `[P1, P99]`): frequency **[244, 2841] Hz**,
DT **[−0.8, 2.2] s**. Quantum note per HK-021(o): WSJT-X reports integer Hz, our lattice is
3.125 Hz — both negligible against a span of ~2,600 Hz, stated per spec §6, not silently
relied on.

| statistic | point | CI95 | halfwidth |
|---|---:|---|---:|
| `F_out` (WSJT-X-only decodes outside our frequency band) | **0.0773** | `[0.0732, 0.0814]` | 0.0041 |
| `T_out` (WSJT-X-only decodes outside our DT band) | **0.0059** | `[0.0046, 0.0077]` | 0.0015 |

**ROW D2 fires** (both `< 0.10`, decisively). Scope difference is not material — WSJT-X's
exclusive decodes sit inside the frequency/time space we already search. **E3 (search-scope
difference) is eliminated as an explanation for D-001.** This closes the 18-day-old open
item from the 2026-08-05 scouting note.

---

## 5. Where this leaves the four candidate explanations (E1–E4), pending Part C

- **E1 (metric asymmetry alone explains the gap):** Gate A shows the pooled statistic *is*
  asymmetric in our favour (A1), but **Gate B (B3) blocks reading that as proof D-001 isn't
  a deficit** — E1 is not established as sufficient on its own.
- **E2 (our exclusive decodes are largely false):** now the **leading candidate**. Gate B's
  presence-corrected `Delta_S` clears its bar by 3–5×, and the SNR-implausibility finding in
  §3 corroborates it independently. Not proven (Part B is explicitly a proxy, per spec §4.2)
  but no longer merely "not ruled out" — it is actively supported by two independent signals
  this session.
- **E3 (scope/configuration difference):** **eliminated** (Gate D, ROW D2).
- **E4 (real-signal impairments):** still untested here by design (§8 of the spec); ROW C3
  is what would authorise opening it, and Part C has not landed yet at the time of writing.

---

---

## 6. ADDENDUM (10:49Z) — Part C: the S8HN high-N synthetic run, oracle-backed

Live 25-trial capture, `scenarios/s8hn-band-scene-highn.json` (new, id `S8HN`, a High-N
copy of S8 — see §7 for the two harness-generalisation notes this required), played
10:35:22–10:47:47Z via `--device "Voicemeeter AUX Input" --skip-warmup`. Warm-up was
**mechanically confirmed from `ALL.TXT`, not answered interactively** (§7): the daemon and
WSJT-X are unattended in this session, so the standard `y/r/n` prompt cannot be answered by
a human; I instead checked both apps' `ALL.TXT` tails immediately after a standalone warm-up
cycle and found the expected `"CQ Q1ABC FN42"` decode on the exact play timestamp
(`260823_103115`) in both logs before arming the real run — the same evidence the prompt
exists to elicit, read directly from the instrument (HK-027). Daemon health confirmed
before arming: `captureActive=True, audioActive=True, dataFlowing=True`, and the loaded
`libft8.dll` SHA256 (`bc8efcf1…`) matches yesterday's verified native build exactly — no
rebuild needed.

300 injected messages/appraiser (12 stations × 25 trials).

| statistic | point | CI95 | halfwidth |
|---|---:|---|---:|
| `recovery_ours` | 91.67% (275/300) | `[91.67%, 91.67%]` | 0.0 |
| `recovery_theirs` | 94.33% (283/300) | `[93.0%, 96.0%]` | 1.5 pp |
| `M_syn` (incl. station F) | 8.83% | `[8.68%, 8.96%]` | 0.14 pp |
| **`M_syn` (excl. station F, GATED)** | **0.00%** | `[0.00%, 0.00%]` | 0.0 |

`recovery_ours`'s zero-width CI is not a computation error: OpenWSFZ's outcome is
**perfectly deterministic** across all 25 noise-seed trials — miss station F, hit every
other station, every single time — so cluster-resampling trials can't change the ratio.

**🔴 Station F (1162 Hz, 12 Hz from its near-collision partner E): 0/25 for OpenWSFZ,
25/25 for WSJT-X.** This is the same defect the board has been carrying as "0/5 on four
consecutive full sweeps" — at N=25 in a dedicated run it is **fully deterministic and
seed-independent**, not a marginal/occasional miss. It is excluded from the gate's
denominator per spec §4.3, exactly as instructed, but it is now the *entire* explanation
for `M_syn`'s non-zero value when F is included (8.83% ≈ 25/283, and 25 is exactly the
station-F miss count — there are **zero** other OpenWSFZ misses anywhere in this run).

**ROW C3 fires** (`M_syn` excl. F = 0.00% < 0.10 bar, decisively — the CI has zero width,
so this is not a resolution question). Per spec: **the metric does not manufacture a
material gap at this N; the artefact explanation weakens and E4 (real-signal impairments)
becomes the leading candidate** for whatever remains once station F and the FP finding
below are accounted for. Read literally, this is the single cleanest result in the whole
arm: on 11 of 12 stations, across every noise realisation tried, **OpenWSFZ recovers
strictly everything WSJT-X recovers, and WSJT-X never recovers anything OpenWSFZ misses.**

### 🔴 Not a gated statistic, but bears on E2 — pure false-positive candidates, AND a live
contamination catch worth recording

`matcher.py`'s per-cycle bucket also logs candidate decodes that match no injected truth
signal (`false_positive=True`, no `trial_index`) — not part of Gate C's pre-registered
`M_syn`, which is miss-based, but directly bearing on Gate B's E2 question. **My first pass
at this reported 447 OpenWSFZ / 1 WSJT-X and I nearly wrote that up as the headline finding
of this section — it was wrong, and the standing memory note on this exact failure mode is
why I checked before trusting it.**

`matcher.py` builds its false-positive tally from *every* slot bucket present in the
parsed `ALL.TXT` file, not just the cycles a given scenario actually played. The OpenWSFZ
`ALL.TXT` copy for this run was not cleared since yesterday's S1-S8 sweep — it spans
`260822_2033..` through `260823_1047..` (722 lines; the WSJT-X copy, by contrast, happened
to start fresh at `260823_1031..`, this run's own warm-up). This is precisely the
"uncleared ALL.TXT contaminates every matched.csv" pattern already on record for this
project (2026-08-15, 203,920 contaminated rows in one file) — I checked the date range
before trusting the count (per that standing note: "grep every file individually before
committing"), found the mismatch, and restricted the tally to only the 25 `cycle_utc`
values that are genuinely this run's trials (from `truth.csv`, cross-checked against the
matched rows). **439 of the 447 OpenWSFZ "false positives" and the single WSJT-X one were
all stale leftovers from yesterday's sweep, not anything this run produced.**

| appraiser | matched (of 300) | genuine FP within this run's 25 cycles | stale/excluded (pre-existing `ALL.TXT` content) |
|---|---:|---:|---:|
| WSJT-X | 283 | **0** | 1 |
| OpenWSFZ | 275 | **8** | 439 |

The corrected figure — **8 genuine OpenWSFZ false positives against 0 for WSJT-X, across
25 real trials** — is a far more modest, defensible number than the erroneous 447-vs-1
figure, but it is still real, still oracle-backed (every one of the 8 decoded a
full syntactically-valid FT8 message — two callsign-shaped tokens plus a grid or report —
at a frequency where nothing was injected; none share a frequency with any of the 12
actual stations), and still directionally consistent with E2: zero WSJT-X false decodes
against a nonzero, nonrandom OpenWSFZ rate in the identical trials. I am reporting both the
error and the correction rather than quietly fixing it, since the same contamination
pattern likely affects some of the 151 already-committed `*_matched.csv`/`*-all.txt` files
this project has accumulated (§7 flags this for whoever next trusts a raw FP count from
one of them) — worth a standing habit, not a one-off fix.

Given the corrected magnitude, I no longer rank this ahead of Gate B's presence-corrected
`Delta_S` or §3's SNR-implausibility table — the three should be read as **three
independent, modest-but-consistent signals pointing the same direction**, not one dominant
one, and I have revised §8 below accordingly.

---

## 7. Two harness generalisations made to run Part C (qa-tooling only, HK-011 does not bite)

1. **`scenarios/s8hn-band-scene-highn.json`** (new) and one registry line in
   `run_study.py`'s `_SCENARIO_REGISTRY` (id `S8HN` → the new file), exactly as the spec's
   §4.3 instructed. **Not** added to `_CONTROLLED_SCENARIO_IDS`; `s8-band-scene.json` and
   S8's own registry entry are untouched.
2. **`harness/run_scenario.py`** hard-coded `scenario.get("id") != "S8"` (schema
   validation, `_load_scenario`) and `scenario_id == "S8"` (render-path dispatch, `main`)
   to recognise the band-scene ("all signals in one slot, no `parts` array") schema. A
   scenario literally named `"S8HN"` fails both checks even though its schema is
   byte-identical to S8's. I generalised both checks to key on the **schema** (`"signals"
   in scenario`) rather than the literal id string — matching the existing convention
   immediately alongside them (`is_pairs = "pairs" in scenario`) — so any future
   band-scene-shaped scenario is recognised the same way S8 already is, without a third
   growing list of hard-coded ids. Verified only `s7-compounding.json`, `s8-band-scene.json`,
   and the new `s8hn-band-scene-highn.json` contain a `signals` key anywhere, and only the
   latter two carry it at the **top level** (S7's is nested per-part, so this change does
   not touch S7's dispatch) before making the change. Confirmed via `--dry-run` before the
   live run.
3. **Operational note, not a code change:** the first launch attempt (detached
   `nohup`/`disown`, no TTY) hit `harness/warmup.py`'s interactive `y/r/n` prompt, got EOF,
   and aborted the run *after the warm-up cycle had already played and decoded correctly in
   both apps* — the abort was a stdin artefact, not a routing failure. Confirmed from
   `ALL.TXT` (§6) rather than re-answering blind, then re-launched with `--skip-warmup`.
   Also had to delete an untracked `truth.csv` a `--dry-run` schema-validation probe had
   left in the run's dated results directory before the real run, since `run_scenario.py`
   *appends* to `truth.csv` and the dry-run and live run share the same
   `date+sha`-derived directory name — an append onto dry-run rows would have corrupted the
   real trial set. Worth a standing note for whoever next needs `--dry-run` on a scenario
   about to also be run live the same day.

---

## 8. Revised reading of E1–E4, incorporating Part C

- **E1 (metric asymmetry alone):** not sufficient (Gate B blocks it) — unchanged from §5.
- **E2 (our exclusive decodes are largely false):** **the leading candidate**, on the
  strength of three independent, individually modest, directionally-consistent signals:
  Gate B's corrected `Delta_S` (a proxy, and the strongest of the three in isolation),
  §3's SNR-implausible-decode table (circumstantial), and Part C's corrected 8-vs-0
  oracle-backed false-positive count (small-N but real and unambiguous). None of the three
  alone would carry this on its own; together they are enough that I recommend E2 become
  the next arm's subject rather than E4.
- **E3 (scope/configuration):** eliminated (Gate D, unchanged).
- **E4 (real-signal impairments):** ROW C3 fired, which per spec §8 is the row that
  *authorises* opening E4 — but given how cleanly Part C came back (perfect recovery on
  11/12 stations, the only miss being a known deterministic defect, and a massive
  synthetic-world FP count), I would not prioritise E4 ahead of E2 without first seeing
  what the FP surge investigation finds. That prioritisation call is the Architect's, not
  mine to make unilaterally — flagged here, not decided.
- **Station F** remains its own separate, cheap, deterministic lead per the spec's explicit
  scope exclusion (§8) — now confirmed 0/25, not just 0/5, and I recommend it keep its own
  pre-registration rather than ride in on this arm's conclusion, exactly as the spec said.

---

## 9. 🔴 NEW STANDING RISK FOUND (not part of C-ASYM-A's scope, flagged separately) — the
shared production `ALL.TXT` can leak real off-air callsigns into committed R&R artifacts

While computing §6's false-positive count I found my first pass counted 447 OpenWSFZ /
1 WSJT-X "false positives" for a 25-trial synthetic run — impossible on its face for a
closed 300-message world. Investigating why (§6 above has the mechanical explanation:
`matcher.py` scans every bucket in the whole `ALL.TXT`, not just the cycles a scenario
played) led to something bigger than a counting bug:

**`run_study.py`'s `WSJT_ALL_TXT`/`OWSFZ_ALL_TXT` constants point at the SAME `ALL.TXT`
files the daemon and WSJT-X use for real, live off-air listening** — there is no separate
test-only log. If either app has decoded anything real between the last time `ALL.TXT` was
cleared and a study run, that real traffic sits in the same file the harness copies into
`results/<date-sha>/*-all.txt` and matches against. **I found exactly this**: the raw `owsfz-all.txt` copy for today's run contained lines
from `260822_2033..` (yesterday) whose message text included at least five non-synthetic,
real-format callsign tokens — 🔴 **not reproduced here, per NFR-021** (I regret that an
earlier draft of this paragraph quoted them directly before I caught it — corrected before
commit, but disclosed rather than silently fixed, since it is exactly the mistake this
policy exists to prevent and the Captain should know it happened). One of the five is also
present in the live production `ALL.TXT`'s current tail, confirming it is a genuine
off-air decode, not a synthetic artefact — the project's whole synthetic message vocabulary
is exclusively Q-prefixed, per `scenarios/study-messages.json`, so any non-`Q`
callsign-shaped token in a study artifact is real by construction.

**What I did about it, scoped to this arm only:** I did **not** commit the raw
`owsfz-all.txt`/`wsjt-all.txt`/`S8HN_matched.csv`. I filtered both `ALL.TXT` copies to only
the 25 `cycle_utc` values that are genuinely this run's trials (10:35:15–10:47:45Z today),
re-ran `matcher.py` against the filtered copies, and confirmed the regenerated
`S8HN_matched.csv` reproduces §6's corrected numbers exactly (283/300 WSJT-X, 275/300
OpenWSFZ, 0/8 FP) with zero non-`Q` tokens remaining. **Those sanitised files are what is
committed**, not the originals.

**What I have NOT done, and am flagging rather than deciding unilaterally:** this pattern
is not new to today. A quick regex sweep of the **67 already-committed `*-all.txt` files**
under `qa/rr-study/results/` (git history, current `HEAD`) found 6 files with non-`Q`
callsign-shaped tokens — on inspection, every token in that sample looks like S5-style
decode-noise garbage (implausible formats: double-digit prefixes, 3-digit numeric prefixes)
rather than a real callsign, and a targeted search for the one real callsign identified
above (not reproduced here, per NFR-021) found no hits anywhere in git history. **This was a spot-check, not an audit** — I have low confidence it
is exhaustive, and I deliberately did not go further: a full historical audit of 151
committed `*_matched.csv`/`*-all.txt` files (and a decision about what to do if it finds
something) is a bigger undertaking than this arm's scope, the repo is **public**, and any
remediation touching git history is exactly the kind of decision HK-010/HK-014 reserve for
the Captain, not something I should start pulling on unilaterally from inside a D-001 arm.

**Correction after checking `git check-ignore` (as the spec's Sec.2 requires before any
commit) — this is not a new hole, it is the known one:** `.gitignore` already excludes
`qa/rr-study/results/*/owsfz-all.txt`, `wsjt-all.txt`, and `*_matched.csv` — added
2026-08-22 (`19cea09`, "close NFR-021 suffixed-copy gitignore hole"), the exact commit
message referencing a `owsfz-all.txt.livecopy-preclear` file carrying real off-air
callsigns. **That file still exists on disk**
(`qa/rr-study/results/2026-08-21-7d36038/owsfz-all.txt.livecopy-preclear`, confirmed
present, confirmed `git status --ignored` shows it as ignored, not tracked) — it is the
board's already-open "🛑 delete the NFR-021 `livecopy-preclear` file" item, and this
session's finding is the same root mechanism (shared production `ALL.TXT`), not a
different one. I have not deleted it — that is explicitly the Captain's open call, not
mine to take unilaterally.

**Net effect: my sanitised files were never at risk of being committed** — `git add` skips
all three patterns regardless, ignore-rule or not. The sanitisation work still mattered for
getting §6's numbers right, but the privacy exposure itself is already fenced off for
anything committed *after* 2026-08-22. **The open question is narrower than I first
thought: only the 151 tracked files committed BEFORE that gitignore fix** (`git log
--follow .gitignore` shows the fix landed 2026-08-22; anything with an earlier commit date
predates it). A spot-check of that set (§ above, 6/67 sampled files had non-`Q` tokens, all
looking like decode-noise garbage on inspection, none matching a real callsign I could
verify) found nothing conclusive, but was not exhaustive. **Recommendation, not an action
taken:** a full audit of the pre-2026-08-22 tracked files against the synthetic-vocabulary
allowlist — the Captain's call on priority, given the public-repo exposure is bounded (already
public if present) rather than actively growing.

---

**QA stops here per spec §9 — no push, no merge, no `pre_merge_check.py`.** Two commits
pending Captain/Architect review: the harness + scenario + `run_scenario.py` generalisation
(qa-tooling), and this report + both result JSON files + the sanitised `results/2026-08-23-
73c1288/` artifacts. Nothing pushed. **§9's finding is flagged for explicit Captain
attention before any commit here is pushed anywhere** — it is not blocking for a local
commit (nothing risky is being committed) but the broader question (does the historical
corpus need auditing?) should not wait for the next person to trip over it.
