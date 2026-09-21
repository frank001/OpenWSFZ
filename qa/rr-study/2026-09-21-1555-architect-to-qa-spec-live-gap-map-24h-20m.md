# `LIVE-GAP-MAP` — pre-registration: a fresh 24 h live 20m gap on today's decoder, and where the misses sit

**Architect, 2026-09-21 15:55Z** (`date -u`, HK-017). Branch `arch/live-gap-map` (cut from
`origin/main` `607b7b95`). Docs-only; `git diff --stat origin/main -- src/ native/` empty.

**Status: the Captain has cleared the capture and its shape.** On 2026-09-21 he parked DENSITY, held the
decode-panel latency defect, and chose this measurement: *"20m for 24h should be enough"* and *"24h is
managable"*. He left the choice of build to the Architect and QA (§2). **One question is open to him before the
first datum (§5 Q1). It gates one descriptive table only, not the capture.**

---

## §0. What this is, why now, and what it reuses

**The one-line reason.** The live gap has never been measured on the decoder the station runs today. The
current headline is **`A1` = 61.09%** (`R_wild`, `n_ref` 91,046, C2, 20m, REF = WSJT-X FT991A alone, binary
`6b2e16a6…`, `nhard` 60, 2026-09-08/09). Since that corpus was recorded:

- the station moved to **`nhard` 40** (2026-09-12 11:52:18Z);
- **PASSBAND-140** shipped (PRs #175/#176, shim `20260051`);
- the decoder-parameter read-out landed on `decoding_improvement` (#184, shim `20260054`). It is **inert at
  defaults**: `DENSITY-REMEDY` Stage 3's null leg was identical on outcome and text on all 5,222 cycles.

Every breakdown of the gap is older still (C-GAP-D, T1 and X1 predate the 2026-08-22 SNR-collapse fix). DENSITY
has just been priced live at ≈ 0.10 pp of in-geometry gain (spec `2026-09-19-1228` §19.3), so the programme has
no current target. **This arm makes the map the next target is chosen from.**

**The question the map is aimed at**, counted on C2 while drafting E4 (spec `2026-09-15-1645` §0.2):
**16,355 of 35,430 misses (46.2%) were signals WSJT-X itself rated at −10 dB or better**, a ceiling of
**17.96 pp**. At those SNRs the synthetic bench loses nothing on clean signals (S8HN: 11 of 12 stations 25/25).
The two candidate explanations were fading (E4, parked unresolved) and density (now priced small). **Does that
pool still exist on today's decoder, and how big is it?** That is the primary row (§3.6).

**Reused, not rebuilt (HK-018):**

| what | where | why it is the right one |
|---|---|---|
| matcher | `qa/rr-study/live-gap-now/matcher.py`, `recovery()` | reproduced A1 to the digit; E4 §0.2 and `DENSITY-REMEDY` Stage 3 both used it |
| SNR table | E4 spec §0.2's eight REF-SNR bands, verbatim | HK-034: the recurring table keeps its format, so C2 and C3 sit side by side |
| bootstrap | `p23_common.cluster_bootstrap()` over REF's distinct `freq_hz` | the programme's standing clustered-CI method |
| capture | the daemon's cycle archive (`mode: "all"`) + WSJT-X's own `ALL.TXT` | C2's layout (`contents.md`, `cycle-audio/`, `openwsfz/`, `wsjtx-1-ft991a/`) |
| supervision | the HK-013 supervisor as used on `FP-FLOOR-LIVE-2` | a 24 h unattended run |

---

## §1. Corpus and reference

| id | corpus | window | our decodes | `REF` |
|---|---|---|---|---|
| **C3** | `artefacts/<yyyymmdd_hhmm>_live_run-live-gap-map/` (new, HK-016) | 24 h from the first cycle after ROW 0 passes; dial **14.074** throughout | **live** `openwsfz/ALL.TXT` (post-`IsPlausibleMessage` + text-dedup: what the operator sees) | WSJT-X `- FT991A` profile `ALL.TXT`, **snapshotted** into the corpus dir at the end, **A only** |

- 🔴 **One radio, one audio stream.** The Yaesu FT-991A is the only radio, and both decoders listen on the
  **same Windows capture endpoint**. No SDR Uno, no second WSJT-X instance (the Captain, 2026-09-21: a second
  radio adds variance). **Every miss in this corpus is then a decoder difference on identical audio.** ROW 0c
  checks this mechanically. Nobody is asked to confirm it (HK-027).
- 🔴 **Primary figures are read from the live logs, not a replay.** A raw-C-ABI replay is not the live path
  (`LIVE-GAP-NOW` seam diagnosis). The cycle archive is kept so a *later* arm can replay the corpus. This arm
  does not.
- **`ALL.TXT` contamination guard.** Before the window opens, record each `ALL.TXT`'s byte length and read only
  appended lines, or rotate both files. An uncleared `ALL.TXT` has contaminated every R&R matched CSV once
  already (memory: `rr-study-matched-csv-nfr021-contamination`).
- **Windowing.** A cycle is in C3 iff its start is inside the window **and** both decoders were demonstrably live
  for it (ROW 0e). The 24 h is **wall-clock**. The denominator is REF rows in the included cycles, never "24 h".

## §2. The build: `decoding_improvement` `fa8a56ae`

Chosen by QA and the Architect, as the Captain directed. The reasons were checked while drafting:

- **Its decoder path is `main`'s plus the inert read-out.** `git log origin/decoding_improvement..origin/main
  -- native/ src/OpenWSFZ.Ft8/ src/OpenWSFZ.Daemon/` is **empty**. Nothing decoder-relevant on `main` is
  missing from it.
- **Its DLL is the one Stage 3 already characterised:** `libft8.dll` SHA-256
  `38a21f840b00af146348c166786cb54e178cd2201c5ed4dba3016a4c589a1cba` (hashed from the git blob today), shim
  `20260054`. A later replay of C3 therefore needs no new pin.
- **Any future decode-rate remedy lands on this branch**, so the baseline is taken where the fix will be
  measured.
- **Its read-out lets the running daemon report its own parameters**, so ROW 0b reads them instead of assuming
  them.

🔴 **Amendment 1 (2026-09-21, before any datum): the pin is the DLL, not the commit.** `decoding_improvement` is
now `84cac119`, a docs-only merge of `main` into `fa8a56ae`. I checked this myself, not from QA's word:
`git diff --stat fa8a56ae 84cac119 -- src/ native/ tests/ web/ openspec/ .github/ VERSION` is empty, the
`libft8.dll` blob is `3bc4b742…` at both, and `fa8a56ae` is an ancestor of `84cac119`. **The build is identified
by the DLL SHA-256 `38a21f84…1cba` and shim `20260054`.** Either `fa8a56ae` or any docs-only descendant of it
(currently `84cac119`) qualifies. ROW 0a asserts the SHA, unchanged.

⚠️ If the station is running a different build when QA arms, **deploying `fa8a56ae` is an operational step for
the Captain** (a native change needs the daemon stopped). QA does not deploy silently.

## §3. `LIVE-GAP-MAP` measurement

### 3.1 Definitions (predicates as code, HK-021(r))

- `R3` = `matcher.recovery(live_openwsfz, REF, window=C3)` → `R_wild`, `R_base`, `n_ref`. It is the same call
  that produced A1.
- `miss` = a REF row not recovered under `R_wild` (exact ∪ wildcard).
- **`H10`** = `100 × |{miss : REF snr ≥ −10}| / n_ref`, in pp. **This is the strong-miss pool.** It is the
  recovery that would be gained if every miss WSJT-X rates at −10 dB or better were recovered. On C2 it is
  **17.96** (E4 §0.2, recomputed by ROW 0f).
- **CI:** frequency-clustered bootstrap over REF's distinct `freq_hz`, `N_BOOT` = 2000, seed `20260921`, for
  `R_wild` and `H10`. `CI95` = the 2.5/97.5 percentiles.

### 3.2 ROW 0: strict order, all before the window opens except 0e and 0g

| row | check (as code) | on failure |
|---|---|---|
| **0a** identity | SHA-256 of the DLL **the running daemon loaded** (the file at the path its process maps, `Get-Process` modules) equals §2's pin, and the daemon's reported shim is `20260054` | STOP. Do not open the window |
| **0b** params | the daemon's parameter read-out (#184) returns `nhard` = 40 and the default suppression triple | STOP |
| **0c** one audio stream | `audioDeviceFriendlyName` in the daemon's `config.json` **and** `SoundInName` in the WSJT-X `- FT991A` profile `.ini` name the **same endpoint**. Both are quoted in the report. Expected: `Voicemeeter Out B1`, the FT-991A chain C2 used | STOP. Hand to the Captain; routing is his |
| **0d** reference depth | the same `.ini` has `NDepth=3` with **no AP bit**; the WSJT-X version is recorded | STOP |
| **0e** coverage (after the window) | share of window cycles with an archived OpenWSFZ WAV **and** ≥ 1 REF row within ±1 cycle ≥ **0.95**; `captureActive = true` at arm time (memory: stale endpoint GUIDs archive nothing, silently) | < 0.95 ⇒ all §3.6 rows **VOID**; report the gaps |
| **0f** matcher | the harness, pointed at C2's live logs, returns `n_ref` 91,046, `R_wild` 61.09% and `H10` 17.96 exactly | STOP. The metric is not the one the baseline was computed with |
| **0g** power (after the window) | `n_ref(C3)` ≥ **40,000** | → **M4** (underpowered), not VOID |

**Why each row changes the verdict (HK-021(k), both branches evaluated):**
- **0a/0b:** without them the corpus measures an unknown decoder, and whichever M-row fires would be attributed
  to the wrong build. That is a wrong reading, so STOP.
- **0c:** if the two decoders heard different endpoints, every miss could be a capture difference, so M1 could
  fire on no decoder defect at all.
- **0e:** a daemon that stops archiving still leaves WSJT-X decoding. `R` would then fall for a reason that is
  not the decoder, and M1 could fire on it.
- **0g's bar:** C2 produced 91,046 REF rows in about 22 h. 40,000 is below half that, which covers a quiet day.
  At 40,000 with `H10` near 18%, the binomial SE is about 0.19 pp. A design effect of 2 on the variance
  gives a CI half-width of about 0.5 pp, far inside the M-row bars.

⚠️ **What ROW 0 cannot detect (HK-022/HK-026):** REF is WSJT-X, not truth. Every figure is "recovery of what
WSJT-X FT991A decoded". Its own misses are invisible, and **our decodes WSJT-X lacks never enter `R`**. They are
not a false-positive rate (FP citation guards §0).

### 3.3 Resolution (HK-021(m), (o), (aa))

- **Readout quantum:** one REF row in about 80,000 is **0.00125 pp**.
- **The bars are stated against a measured baseline** (HK-021(aa)). C2's `H10` is 17.96 pp. §3.6's bars are
  10 pp and 5 pp: a pool that has shrunk to about half, or about a quarter, of the baseline. Each is many CI
  half-widths from the other.
- 🛑 **C2 and C3 differ by 13 days, propagation, density and band conditions.** `H10(C3) − H10(C2)` is
  **reported, never read as a build effect** (`LIVE-GAP-NOW` §3.5's guard). The M-rows gate on C3's absolute
  `H10`, which is the size of today's pool whatever caused it.

### 3.4 Descriptive, no row (report every one)

- **D1: the new live figure.** `R_wild`, `R_base`, `n_ref`, window. It is citable only with all its qualifiers:
  binary `38a21f84…` / shim `20260054` / `decoding_improvement` `fa8a56ae`, `nhard` 40, 20m, REF = WSJT-X FT991A
  alone, the window dates. 🛑 **Never compared with A1 as a build effect.**
- **D2: E4 §0.2's eight-band SNR table on C3, in the same columns, beside C2's.** HK-034: same format.
- **D3: frequency bands.** Recovery and miss counts below 200 Hz, 200–3000 Hz, and above 3000 Hz.
- **D4: cycle load.** Recovery by the number of REF decodes in the cycle, in quintiles fixed on C3's own REF
  counts. This is X1's density axis, a cycle count, **not spectral locality**.
- **D5: time of day.** Recovery by UTC hour, to show whether the pool moves with band conditions.
- **D6: what we decoded that WSJT-X did not.** Counts only, labelled "uncorroborated, not false".
- **D7 (only if the Captain answers yes to §5 Q1): strong misses by nearby-signal exposure.** The `DENSITY-LIVE`
  classifier with TEST = C3's live log, reporting `H10` split into EXPOSED / not.

### 3.5 Where the map points (reading, not a row)

The M-rows decide only **whether** the strong-miss pool is the next target. **What** is inside it is a later
arm, specced on C3 after this report, with the cycle archive as its input.

### 3.6 Gate rows (first match wins)

| row | predicate | reading |
|---|---|---|
| **M4** | ROW 0g routes here | Underpowered. Report everything and route nothing |
| **M1** | `CI_lo(H10) ≥ 10.0` | **The strong-miss pool is still large on today's decoder.** It is the next target |
| **M2** | `CI_hi(H10) < 5.0` | **The pool has largely closed.** The gap is now mostly below threshold, which is bit-formation territory (THRESH-A, parked). The next question is the Captain's |
| **M3** | otherwise | Between the bars. Report, and route nothing on it alone |

Mutually exclusive: M1 needs `lo ≥ 10` and M2 needs `hi < 5`, and `lo ≤ hi`. M3 is the remainder. M4 comes
first by order.

### 3.7 Consequences

- **M1** ⇒ the Architect specs a localisation arm on C3's archive. The question: are the strong misses **not
  found** (candidate stage) or **found and misread** (decode stage)? The answer is read from forced decodes at
  WSJT-X's reported position and existing instruments only. No `src/` change is implied.
- **M2** ⇒ the Architect brings the Captain one decision: reopen the below-threshold route on **sensitivity**
  grounds (THRESH-A's T2, parked 2026-09-14), or stop decode-rate work here.
- **M3/M4** ⇒ every figure is reported and nothing is re-based. D1 still replaces A1 as the current live figure,
  **with its qualifiers**, because it is read from live logs and needs no row.

---

## §4. Architect predictions: blind, on the record, before any datum

Ledger discipline: these are scored at ruling time in `architect-prediction-ledger.md`, with the P written here.

| # | prediction | P | class |
|---|---|---:|:---:|
| L1 | ROW 0f reproduces C2 exactly (91,046 / 61.09% / 17.96) | 0.95 | C |
| L2 | ROW 0 (0a–0f) passes at arm time without a Captain routing change | 0.70 | H |
| L3 | **M1 fires** | 0.80 | H |
| L4 | M2 fires | 0.03 | H |
| L5 | D1's `R_wild` lies in [57.0, 65.0] % | 0.65 | H |

Reasoning, briefly. **L3:** nothing aimed at strong signals has shipped since C2, and the density lever (the
only candidate we priced) was worth about 0.1 pp, so a pool of 17.96 pp should not fall below 10 on a
different day. This is the "nothing has changed" direction, not the named bias (inventing a findable
mechanism). **L5:** a wide band on purpose. `nhard` 40 can only lose corroborated decodes at fixed REF, the
passband can only add, and the day's conditions dominate both.

---

## §5. PO question (before the first datum only)

**Q1: may D7 run?** The spectral-locality bar is **retired, do not re-propose**, and the Captain cleared
`DENSITY-LIVE` as **one confirmatory test only**, with *"no second live stratification without a new ruling"*.
D7 would be that second stratification. It is useful (it says how much of the strong-miss pool sits next to a
stronger signal on today's decoder), but **the capture and every M-row run without it.** Yes ⇒ D7 is reported,
descriptive, and gates nothing. No or unanswered ⇒ D7 is dropped and never computed.

---

## §6. What this arm does NOT do

- 🛑 **No `src/` or `native/` change, no rebuild, no push, no merge** (HK-011, HK-014, HK-010). The deployment
  in §2, if needed, is the Captain's operational step.
- 🛑 **No replay leg.** The cycle archive is captured for a later arm.
- 🛑 **No build contrast.** One build, so `C3 − C2` is never a build effect.
- 🛑 **Does not reopen** DENSITY (parked), FADE/E4 (parked), THRESH-A (parked) or any closed gate. An M-row
  routes a *question* to the next spec or to the Captain. It re-reads nothing.
- **Cannot see:** any band but 20m; WSJT-X's own misses; false positives; anything a single reference decoder
  cannot corroborate.

**NFR-021.** `ALL.TXT` and the WAVs carry real third-party callsigns. They stay in `artefacts/` (gitignored).
The report carries counts, rates, frequencies and SNRs only. **Scan the report prose** with `scan()`/`classify()`
before committing.

## §7. Running order and authorisation

| step | status |
|---|---|
| Capture shape (20m, 24 h, one radio) | ✅ Captain, 2026-09-21 |
| Build | ✅ `decoding_improvement` `fa8a56ae` (§2) |
| §5 Q1 (D7) | ⏳ Captain, before the first datum; the arm runs either way |
| ROW 0f on C2, then 0a–0d on the live station | QA |
| Arm the capture: supervisor (HK-013), detached with a log tail (HK-023), `captureActive` checked | QA, with the Captain present at arm time |
| 24 h window, then snapshot `ALL.TXT`, teardown (HK-019), `README.md`'d artefacts dir (HK-016) | QA |
| 0e, 0g, then the M-row, then §3.4 | QA, in that order |
| Report, committed locally | QA. Push/PR needs the Captain's go (HK-033) |

🔴 **HK-025 is available in full.** If any row here is a diagnostic dressed as a gate, name it, evaluate both
branches, and refuse it.
