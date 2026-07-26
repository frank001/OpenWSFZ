# D-001: Architect plan — price the 740 by capability. B.1 jt9 ablation, B.2 calibration, B.3 the §6.3 costed menu

**Author:** Architect, 2026-07-26 (23:30). **For:** QA, per HK-015 — a worked recommendation for QA
to scope and run; `dev-tasks/`/`tasks.md` remain QA's to author.
**Approved by the Captain** in this evening's helicopter-view session: the investigation phase is
over; D-001 is a capability gap, not a bug, and the work now moves toward the SIC/§6.3 decision.
**Relation to prior rulings:** the 22:30 synthetic-waveform calibration (`2026-07-26-2230-architect-
sec6-redesign-ruling.md` §5, §6) stands **unchanged** and is sequenced here as B.2. Nothing in the
20:30/22:30 rulings is revised by this note.

---

## 1. The approved sequence, and what each step buys

| step | what | cost | output |
|---|---|---|---|
| **B.1** | jt9 ablation — run WSJT-X's own CLI decoder over the 68-cycle corpus at varying depth | QA-only, offline, no native change, ~1 session | the 740-decode gap **priced by WSJT-X capability** |
| **B.2** | synthetic-waveform BER calibration (already ruled, 22:30 §5/§6) | ~20 min compute, QA-only | **E** = expected recoverable count from THE 135 — bounds our own decode-path residue |
| **B.3** | §6.3 goes to the Captain as a **costed menu** | Architect writes it from B.1+B.2 | a decidable product question with measured prizes per row |

B.1 and B.2 are independent and may run in either order or in the same session. B.3 waits for both.

**Why B.1 exists:** every experiment in this thread so far has interrogated *our* decoder; none has
interrogated WSJT-X's. If WSJT-X at minimum decode effort drops most of the way to our 1288, the gap
is confirmed as the effort/subtraction stack and the SIC re-attempt has a measured target. If it
barely drops, the prize is elsewhere and we just avoided a second failed native SIC campaign.

## 2. Due diligence already done (Architect, this session — verify, don't re-derive)

- **`D:\WSJT\wsjtx\bin\jt9.exe` exists.** QA should record its version (and confirm it is the same
  WSJT-X installation that produced the live 2028-decode reference).
- **Full `jt9 --help` flag inventory taken.** Relevant knobs: `-8` (FT8), `-d 1..3` (depth,
  default 1), `-a PATH` (writeable data dir — where its `ALL.TXT` lands), `-e PATH`
  (subordinate executables), `-F` (freq tolerance, default 20 Hz), `-H` (highest freq, default
  4007), `-c/-G/-x/-g/-Q` (my-call/grid, his-call/grid, QSO progress — the AP context), `-X`
  (experience-based decoding flags), `-p` (T/R period, default 60 — check whether it must be 15
  for FT8 in the smoke test). **There is no standalone "subtraction on/off" or "AP on/off"
  switch.** Depth is the axis we have, and it bundles effort (passes/OSD depth/subtraction
  behaviour) — the findings doc must present it as a bundle, not as a clean SIC toggle.
- **AP-marker probe of the live reference:** the live WSJT-X `ALL.TXT`
  (`artefacts/20260725_live_run_1806/wsjt-x/ALL.TXT`, 2,684 lines) contains **zero** `a1`–`a6`
  suffixes and zero `?` suffixes. This *suggests* the 2028 reference was achieved with AP off —
  but marker absence is weak evidence (the format may simply not have carried them). **QA: confirm
  from the WSJT-X GUI settings** (Decode menu / File→Settings) and record the GUI's decode depth
  (Fast/Normal/Deep) while there. If AP was indeed off, that is a real finding: the 740 is
  explained by depth/subtraction/front-end alone, and the menu's AP row shrinks accordingly.
- **Corpus present:** `artefacts/20260725_live_run_1806/wsjt-x/wav/` (75 WAVs, 12 kHz 16-bit mono,
  WSJT-X native format) — the 68 filename-matched cycles are the analysis set, same as every
  C.1–C.4 session. Our own `owsfz/wav/` files are byte-compatible by construction
  (`cycle-audio-archive`), so jt9 can decode them too (optional arm A4).

## 3. B.1 — the jt9 ablation, worked design

### 3.1 Step 0 — smoke test before any arm is trusted

One WAV, one invocation, e.g.:

```
D:\WSJT\wsjtx\bin\jt9.exe -8 -d 3 -a <scratch> -t <scratch> <wav>
```

Establish and record: does it decode at all; is `-p 15` required or harmful for FT8; where output
appears (stdout vs `<scratch>\ALL.TXT` — likely `decoded.txt`/stdout; take whichever parses
cleanly); runtime per WAV; and that decode counts for that cycle are plausible against the live
reference for the same cycle. **Do not proceed to the arms until this parses.**

### 3.2 Arms

All arms: same 68 WAVs, **one jt9 invocation per arm with all 68 files in a single process** (file
order = chronological), so jt9's cross-file hash-callsign context accumulates within the arm,
approximating the live session. Separate `-a` scratch dir per arm. No callsign context flags
(`-c/-x`) in any arm — CLI-without-context is itself the controlled condition, and per §2 the live
reference likely ran without AP anyway.

| arm | invocation | measures |
|---|---|---|
| **A0** | `-8 -d 3` | jt9 at full effort — the offline anchor |
| **A1** | `-8 -d 2` | depth 3→2 yield |
| **A2** | `-8 -d 1` | minimum effort — the headline arm |
| **A3** (optional) | `-8 -d 3 -F 50` or similar | only if smoke test suggests freq-tolerance matters; skip freely |
| **A4** (optional) | `-8 -d 3` on **our** `owsfz/wav/` 68 | capture-chain re-check with the *reference* decoder — symmetric to §9 parity, cheap, expected ≈A0 |

### 3.3 Scoring

Reuse the parity work's message-level matching and hash-token normalisation
(`qa/cycleframer-alignment-replay/` conventions from the 2026-07-25 §9 analysis) — do not invent a
new matcher. Per arm report:

1. **Total decodes** over the 68 cycles.
2. **Miss coverage:** of the ~740/793 messages WSJT-X-live decoded and we did not, how many this
   arm decodes. This is the pricing number.
3. Overlap with our 1288-decode set (sanity: should be high in every arm).
4. Anchors alongside every table: live WSJT-X GUI = 2028; our decoder = 1288 (offline, same WAVs).

All raw jt9 output stays under git-ignored `artefacts/` (real callsigns — NFR-021); only aggregate
counts go in the findings doc, per this thread's standing practice.

### 3.4 Reading rules — fixed in advance, before any number exists

Let T(d) = arm total, M(d) = miss coverage at depth d.

| observation | reading | consequence for B.3 |
|---|---|---|
| **A0 ≪ 2028** (say, by >15%) | a material share of the live reference comes from GUI/session context (settings, AP, live hash state) — not from the core decoder at depth 3 | quantify it; QA's GUI-settings check (§2) becomes load-bearing; the menu's denominator is A0, not 2028 |
| **A2 ≈ our 1288** (within ~10%) | stripped of depth/subtraction effort, WSJT-X's core ≈ ft8_lib; **the gap is the effort/subtraction stack** | SIC re-attempt confirmed as the headline menu row, with T(3)−T(1) as its measured ceiling |
| **A2 ≫ 1288** (by a wide margin) | even minimum-effort WSJT-X out-syncs us — a large share sits in the **front-end/sync quality itself**, not in subtraction passes | the menu must carry a front-end/sync row distinct from SIC; this would also cohere with Part B's ≈50% BER "never locked" population |
| **T(3)−T(2), T(2)−T(1)** | the per-capability price list | goes into the menu rows verbatim |

I am deliberately not predicting which row fires. My prior after Phase 2c's BER evidence is a mix of
rows 2 and 3 — THE 567 looks like "never locked" (front-end), while subtraction serves the buried
fraction — but the ablation exists precisely because that prior is uncalibrated, and the last two
corrections in this thread were both to my uncalibrated references.

### 3.5 Honest caveats to carry into the findings doc

- **Depth is a bundle.** jt9 gives no clean subtraction toggle; "depth 3→1 yield" is *effort
  including subtraction*, not subtraction alone. State it plainly; do not let the menu row say
  "SIC = N decodes" when the measurement is "effort stack = N decodes".
- **Offline jt9 ≠ live GUI** (session state, settings, real-time sequencing). The A0-vs-2028 delta
  measures this; it does not remove it.
- **One corpus, one band, one device, 21 minutes** — unchanged from every note in this thread. If
  B.3's menu ends up recommending a large engineering commitment, a second corpus (different
  band/time) is cheap insurance to gather *before* the commitment lands, not before the menu.

## 4. B.2 — calibration sweep: unchanged, one pointer

Runs exactly per 22:30 §5 (two arms, synthetic CPFSK + AWGN through the unmodified shipped decode
path, P(decode | BER) with Wilson intervals) and §6 (the E estimator and its fixed reading rule:
<1 / 1–15 / >15). Nothing here amends it. Its output feeds B.3's "our own decode-path residue" row.

## 5. B.3 — the §6.3 memo skeleton (Architect writes it; recorded now so B.1/B.2 collect the right numbers)

One row per option, each with: measured prize (from B.1/B.2), engineering cost, risk, and what it
does to NFR-018 (≥80% parity target; we sit at ~63.5% on this corpus).

1. **Accept the gap** — re-baseline NFR-018 against a measured ceiling; zero cost; product call.
2. **Re-attempt PCM-domain SIC** — the June `fix-d001-pcm-sic` history attached as *engineering
   constraints, not a verdict*: heap allocation from day one (the 720 KB stack buffer), the second
   never-diagnosed `0xC0000005` budgeted as a real risk to root-cause, and — the thing June lacked —
   **subtraction fidelity measured per-candidate via this week's raw-LLR/BER instrument** (decode
   strong signal, subtract, measure whether the buried candidate's BER actually improves), not via
   aggregate R&R deltas. Prize: B.1's effort-stack yield. Prerequisite: Captain sign-off, HK-011
   Developer session(s).
3. **Decode-effort constants** (BP iterations, OSD depth/gates) — only if B.2's E lands ≥ the 1–15
   band with a chaseable cause; otherwise this row reads "measured ≈0, closed".
4. **Front-end/sync work** — only if B.1's A2 row fires; scope unknown until then.
5. **Adopt WSJT-X's own decoder core** — flag, do not decide: WSJT-X is **GPLv3**; linking its
   Fortran decoder has licensing consequences for the product that are the Captain's to weigh, and
   this row exists so the option is priced rather than pretended away.

## 6. What this note does not authorise

- **No native or `src/` change.** B.1 and B.2 are QA-runnable end to end (HK-011 untouched).
- **No push, no merge** (HK-014 — this note is committed locally and stops there).
- **No `pre_merge_check.py`** — Captain's trigger per HK-006.
- **The branch's outstanding items are untouched**: the `libft8.dll` size question (20:30 §9) and
  the branch's overall disposition remain with the Captain.
- **NFR-021**: every jt9 output file contains real callsigns → `artefacts/` only, never committed;
  findings docs carry aggregates only.

## 7. Cross-references

- `2026-07-26-2230-architect-sec6-redesign-ruling.md` §5, §6 — B.2, unchanged.
- `2026-07-26-2030-architect-c2-phase2c-ruling.md` §8 — the decomposition table this plan acts on
  (items 1–3 closed; item 4 open, now moving to pricing rather than further decomposition).
- `2026-07-26-0015-d001-consolidation-and-clean-slate.md` §6.3 — the product question B.3 unparks.
- `openspec/changes/archive/2026-06-07-fix-d001-pcm-sic/` and `.../2026-06-07-revert-fix-d001-pcm-sic/`
  — the June SIC attempt and its revert (stack overflow + undiagnosed second AV, −0.1 pp).
- `openspec/changes/archive/2026-06-12-diag-d001-three-pass-sic/design.md` — the three-pass
  spectrogram-suppression diagnostic; also the June root-cause note that failures concentrate at
  0 Hz separation, which is the SIC use case.
- `qa/cycleframer-alignment-replay/2026-07-25-2030-cycle-audio-archive-parity-result.md` — the
  matching/normalisation conventions §3.3 reuses.
- `artefacts/20260725_live_run_1806/` — corpus and live references (git-ignored).
- `D:\WSJT\wsjtx\bin\jt9.exe` — the instrument.

---

*Per HK-015 this is a recommendation; QA authors the task and runs it. Per HK-014 nothing is pushed
or merged. B.3's decision remains the Captain's and is not being put to them until B.1 and B.2
report.*
