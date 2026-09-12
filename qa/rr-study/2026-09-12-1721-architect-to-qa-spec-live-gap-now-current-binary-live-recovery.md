# `LIVE-GAP-NOW` — pre-registration: what is the 20m live decode gap on today's binary, and how much of any change is the decoder?

**Architect, 2026-09-12 17:21Z** (`date -u`, HK-017). Branch `arch/live-gap-now` (cut from
`origin/main` `19737b32`). Docs-only; `git diff --stat origin/main -- src/ native/` empty.

**Status: cleared to run.** The Captain, 2026-09-12: *"now FP is off the menu I want to go back to
improve the decode rate"* and, on this recommendation, *"proceed with your recommendations"*.
`BAR_D` (§3.6) is Architect-set, not PO-ratified. The Captain may move it **before the first
datum**. After that it is frozen, and anyone proposing to move it (me included) gets refused.

---

## §0. What this is, why now, and what it reuses

**The one-line reason.** Every live D-001 figure we cite was measured on a build older than
2026-08-22: the 20m headline **57.79%** (H1, `40,003 / 69,222`, `20260808_live_run_0016-8080`), X1,
X2, C-GAP-D and the ledger's route sizings. On 2026-08-22, `c3a9ea8` (`fix(ft8): negative
time_offset SNR collapse`, shim `20260046`) changed the production decode path. The reported SNR
feeds `suppress_candidate_tiles`, so pass 1 can behave differently in crowded cycles. The
2026-09-08 withdrawal (`2026-09-08-1745-…`) measured the SNR effect on the synthetic battery: S4
collapse share **32.3% → 0.0%**, S8 **20.0% → 0.0%**, at exactly that sweep. OpenWSFZ's S7 count
stepped from 147–160 to 169–180 of 215 the same week and has held for nine sweeps (board,
2026-09-12 16:18Z). **Nobody has re-measured the live gap since.**

It is also not the only change. Between the 08-08 live build and today's `main` the win-x64 DLL
went `f2f30c89…` (shim `20260033`) → `6b2e16a6…` (shim `20260050`). That span includes the
passband and hash-table sizing (`9500e03`), the SNR-collapse fix, and the 12-bit unique-match
suppression (#138). **This arm measures the whole span as one contrast. Attributing it to commits
is out of scope (§6).**

**Why it comes first.** If the live gap has moved materially, every downstream sizing was made on
a stale number: E4's premise, the near-neighbour prize, the ledger's route credences. If it hasn't
moved, we know the 08-22 → 09-12 work did not reach live 20m, which is its own finding.

**A post-fix live corpus already exists** and recovery has never been computed on it (checked
2026-09-12: the `FP-FLOOR-LIVE-2` Part A/B reports and the Part B ruling contain no recovery or
recall figure). `artefacts/20260908_live_run_1827-fp-floor-live-2/` holds 20m, dial 14.074,
build `cf21ac5` = DLL `6b2e16a6…` = today's `main` pin, `osdNhardMax = 60`. OpenWSFZ and WSJT-X #1
(FT-991A) share the `Voicemeeter Out B1` audio path. The valid window starts `2026-09-08T19:36:45Z`
(Amendment 3). All cycles are archived as WAVs (`mode: "all"`).

**Reused, not rebuilt (HK-018):**

| what | where | why it is the right one |
|---|---|---|
| matcher | `qa/cycleframer-alignment-replay/h1_hash_token_contamination.py`: `load()`, `wildcard_match()`, and the `R_wild` block of `main()` (exact ∪ per-`ts` wildcard) | the exact code that produced 57.79% |
| decoder binding | `qa/cycleframer-alignment-replay/p23_common.py`: `Decoder` (ctypes, SHA-asserted), `read_wav()`, `normalise_rms()` | mirrors `Ft8Decoder.NormalisePcm`; drives old binaries through the raw C ABI, which the managed wrapper's `ExpectedShimVersion` self-test blocks (FP-REGRESSION E2's machinery note) |
| paired bootstrap | `p23_common.cluster_bootstrap()`: frequency clusters (T2a design effect), resampled once per draw across all legs | the programme's standing paired-contrast method |
| old binaries | `git show <sha>:src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll`, hashed, into `artefacts/` | FP-REGRESSION E0/E1 precedent: **no rebuild, so no HK-011 Developer session** |

**Feasibility checked while drafting, not assumed:**
- **ABI:** `ft8_lib_version_check()`, `ft8_decode_all(…)`, `ft8_set_decode_params(int, float, int)`
  and the `FT8Result` layout (`int freq_hz; float dt; int snr; char message[36]`) are identical in
  `ft8_shim.h` at `b8845cd` and at `origin/main`.
- **Audio:** both corpora's cycle WAVs are mono, 16-bit, 12 kHz, 180,000 samples, named
  `yymmdd_hhmmss.wav` by cycle start, with a `cycle-archive.csv` manifest.
- **Blob pins, hashed from git this session:** see §2.

⚠️ **Disclosure (de-blinding check).** While confirming the corpus exists I saw the raw line counts
of `FP-FLOOR-LIVE-2`'s two `ALL.TXT` files. I computed no match, no recovery and no replay. Nothing
else outcome-bearing was looked at.

---

## §1. Corpora and reference

| id | corpus | window | our audio | `REF` |
|---|---|---|---|---|
| **C1** | `artefacts/20260808_live_run_0016-8080/` | `260808_004000`..`260808_111500` (`WINDOW_20M`, 2,529 cycles) | `owsfz/wav/`, **our own capture**, not WSJT-X's WAVs | `wsjt-x/ALL.TXT` (WSJT-X FT991A), **A only** |
| **C2** | `artefacts/20260908_live_run_1827-fp-floor-live-2/` | `260908_193645`..the last cycle in `openwsfz/ALL.TXT` | `cycle-audio/` | `wsjtx-1-ft991a/ALL.TXT` (the snapshot, **not** `%LOCALAPPDATA%`), **A only** |

- **Dial filter:** `14.074` on every `ALL.TXT` read (H1's `DIAL_PREFIX`).
- 🔴 **`REF` is A-only on both corpora, for every primary number.** C2 has no second instance
  (Amendment 1), so the arm uses one basis throughout (the H1a/X0 mixed-basis rule). C1's `A ∩ B`
  appears **only** in ROW 0c (reproducing the published 57.79%) and as one labelled descriptive line.
- **Our audio is `owsfz/wav`, deliberately.** P2/P3 decoded WSJT-X's WAVs to remove the capture path.
  This arm wants the capture path in, because it is asking about the live figure.
- **C2 cycles** are those whose WAV `cycle_start_utc ≥ 2026-09-08T19:36:45Z` and whose `dial_mhz` is
  `14.074`, from `cycle-archive.csv`. Any `*_2.wav` duplicate-pipeline file is excluded (none is
  expected after the boundary; count and report them).

## §2. Legs (binaries)

Each leg runs in **its own process(es)**. Each DLL copy gets a **distinct filename**
(`libft8_L08_20260033.dll`, `libft8_NOW_20260050.dll`). Two modules with one base name in one
process is a loader trap, and the callsign hash table is process-global. Parallelism is by process
only, with contiguous chronological partitions (p23 §1.1).

| leg | binary (git blob) | SHA-256 (hashed 2026-09-12) | shim | params `(k, corr, nhard)` |
|---|---|---|---|---|
| **L08** | `b8845cd` | `f2f30c890b253eb6b69aa1a89c26d2991ee70aa2a202c68361130344bb7d4015` | `20260033` | `(10, 0.10, 60)` |
| **NOW** | `origin/main` (`19737b32`) | `6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c` | `20260050` | `(10, 0.10, 60)` |
| **NOW40** | same as NOW | same | `20260050` | `(10, 0.10, 40)` (the station's setting since `11:52:18Z`) |

⚠️ **L08 is a stand-in, not the live 08-08 binary.** `20260808_live_run_0016-8080/contents.md`
records "`main` at `b8845cd` (**uncommitted changes present**)". ROW 0e measures how good the
stand-in is, and the report must carry that number next to every L08 figure.

Every leg decodes **every C1 cycle and every C2 cycle**: `read_wav()` → `normalise_rms(…, 0.20)` →
`ft8_decode_all`. That is about (2,529 + |C2|) × 3 decode calls. C2 has roughly 5,200 cycles, so
about 23,000 calls. That's roughly 3 h serial and under 1 h with process parallelism. If it runs
longer than an hour, supervise it (HK-013 / HK-023).

**Truncation guard:** if any cycle returns exactly `MAX_RESULTS`, raise `MAX_RESULTS` to 400 and
re-run that leg on that corpus. Report the count.

## §3. `LIVE-GAP-NOW` measurement

### 3.1 Definitions (predicates as code, HK-021(r))

- `load(path, lo, hi, "14.074")` → `{(ts, message): (snr, freq_hz)}`, exactly as H1. A replay leg's
  output is keyed the same way, with `ts` = the WAV's cycle-start stem.
- `R(OWS, REF)` = `100 × (|REF ∩ OWS| + |wild_gained|) / |REF|`, where `wild_gained` is H1's per-`ts`
  `wildcard_match` over `REF − exact`. **This is H1's `R_wild` code path verbatim.** Report `R_base`
  (exact only) beside it.
- `Δ(C)` = `R(NOW, C) − R(L08, C)`, in pp.
- **Paired CI:** frequency-clustered bootstrap over `REF`'s distinct `freq_hz`. Resample once per
  draw and recompute both legs' `R` on the same cluster set, then take `Δ` per draw. `N_BOOT = 2000`,
  seed `20260912`. `p23_common.cluster_bootstrap()` returns per-metric summaries, so extend it to keep
  per-draw arrays; do not difference two independent CIs. `CI95` = the 2.5/97.5 percentiles of the
  per-draw `Δ`; `SE` = their standard deviation.

### 3.2 ROW 0: strict order

| row | check (as code) | on failure |
|---|---|---|
| **0a** identity | For each leg: SHA-256 of the **loaded file** equals §2's pin, **and** `ft8_lib_version_check()` called **through the loaded handle** returns §2's shim. That proves the intended module loaded, not a cached one. | VOID |
| **0b** ABI | re-confirm from `git show b8845cd:src/OpenWSFZ.Ft8/Native/ft8_shim.h` that the three signatures and the `FT8Result` layout equal `origin/main`'s (checked while drafting; QA confirms independently) | STOP, escalate |
| **0c** matcher | On C1, the **live** `owsfz/ALL.TXT` vs `REF = A ∩ B` (H1's two `wsjt-x` files) gives `|REF| = 69,222` and `exact + wild = 40,003` exactly (`R_wild = 57.79%`) | STOP. The metric is not the one the headline was computed with. |
| **0d** seam fidelity | On C2, **NOW's replay** vs C2's **live** `openwsfz/ALL.TXT`, same binary and same `nhard`, over cycles present in both. `F_live` = share of live decodes reproduced by the replay; `F_rep` = share of replay decodes present live. Keys are `(ts, message)` under `wildcard_match` with `|Δfreq| ≤ 1 Hz`. **PASS iff `F_live ≥ 0.99` and `F_rep ≥ 0.99`.** Report live cycles with no archived WAV. | **§3.6 rows VOID** (a replay contrast would not speak for live). §3.5 A1, which is read from live logs, still stands. |
| **0e** stand-in fidelity (**report only**, HK-021(k)) | The same two shares for **L08's replay** vs C1's live `owsfz/ALL.TXT` | Report both numbers. See below. |
| **0f** seam sensitivity | L08's and NOW's full output tuples `(ts, freq_hz, dt, snr, message)` on C1 are **not identical on every cycle** | **§3.6 rows VOID, "instrument blind".** Never B2. |
| **0g** power (routes) | `SE(Δ(C1)) ≤ 0.75 pp` | → **B4** (underpowered), not VOID |

**Why each row changes the verdict (HK-021(k), both branches evaluated):**
- **0d:** if it fails, a replay `Δ` could be a property of the replay path. B1/B2/B3 would each read
  something false, so VOID.
- **0f:** if the two binaries' outputs were byte-identical on 2,529 live crowded cycles, despite a
  passband change, a hash table 16× larger and the SNR fix, `Δ = 0` would read B2. That B2 would be
  false. This is FP-REGRESSION E2's lesson turned round: there the seam was blind to a change that
  existed.
- **0e is deliberately NOT a gate.** Whatever it reads, `Δ(C1)` still compares the `b8845cd`
  committed blob with `NOW` on identical audio, a valid build contrast. What changes is only whether
  L08 may be **called** "the 08-08 live binary". So it can't move a row, only the wording, and it is
  reported instead.

⚠️ **What ROW 0 cannot detect (HK-022):** `REF` is WSJT-X, not truth. Every `R` is "recovery of what
WSJT-X FT991A decoded" (HK-026). Neither ROW 0 nor anything else here bounds WSJT-X's own misses.
**`R` is also not a false-positive measure.** Our decodes that WSJT-X lacks never enter it.

### 3.3 Resolution, computed while drafting (HK-021(m), (o))

- **Readout quantum:** one `REF` row of about 69,000 is **0.0014 pp**, far below every bar.
- **Paired SE:** P1 measured a frequency-clustered `SE = 0.347 pp` on this same C1 window and
  denominator. A paired contrast of two legs on identical audio should do no worse. That gives
  `CI95` half-width ≈ **0.7 pp**, so `BAR_D = 2.0` sits about 3 SE clear of the dead band's centre.
  ROW 0g routes to B4 if the realised SE is more than twice P1's.
- ⇒ **B1 needs a true `Δ` of about +2.7 pp or more. B2 needs `|Δ|` of about 1.3 pp or less.**
  Between those, the arm reads B4, and that is the correct reading.

### 3.4 Why `BAR_D = 2.0 pp`

It is the smallest shift that would move a route sizing on the board. T1's `G = 3.16 pp` was ruled
"real but small", and RC3's out-of-band share was 3.1% of misses. 2.0 pp is about 5% of the ~42 pp
gap. A symmetric ±2.0 pp dead band stops a 1 pp drift being over-read in either direction. It does
not depend on any number this arm will produce.

### 3.5 Descriptive, no row (report every one)

- **A1: the current-binary live figure.** `R(C2 live openwsfz/ALL.TXT, REF A)`, with `R_base`,
  `|REF|` and the window. **This is the number that replaces "57.79%" as the current live figure.** It
  is citable only with all of its qualifiers: binary `6b2e16a6…`, `nhard 60`, 20m, REF = WSJT-X
  FT991A alone, the 2026-09-08/09 window.
- **A2:** `R` for every leg × corpus (six numbers), plus `R(NOW, C1, A∩B)` beside the 57.79% it
  would be compared with.
- **A3:** `R(NOW40, C) − R(NOW, C)` for both corpora, paired-bootstrap CI. At fixed `REF` a lower
  `nhard` can only **lose** WSJT-X-corroborated decodes; its FP benefit is invisible to `R`
  (HK-021(t)). Descriptive only. It does **not** reopen `NHARD40-DEFAULT`. If `CI_hi < −0.5 pp`, flag
  it to the Architect the same day.
- **A4: where the change lives.** Recovery by **reference SNR**, in 2 dB bins, for L08 and NOW on
  each corpus (the C-GAP-D presentation), with the per-bin `Δ`. Plus `Δ` split into three frequency
  bands: below 200 Hz (passband), 200–3000 Hz, and above 3000 Hz.
- **A5:** `Δ(C2)` with its paired CI, the replication of §3.6 on post-fix audio.

🛑 **Never compare A1 with 57.79% as a build effect.** C1 and C2 differ by 31 days, propagation,
density and band conditions (X1/X2 show both density and band are first-order terms). **The build
effect is `Δ`, measured on identical audio, and nothing else.** If anyone wants the day-to-day
difference, it needs X1's density × SNR standardisation in a separate descriptive note.

### 3.6 Gate rows (first match wins)

| row | predicate | reading |
|---|---|---|
| **B1** | `CI_lo(Δ(C1)) ≥ +BAR_D` **and** `Δ(C2) > 0` (point) | **The build span materially raised live recovery.** |
| **B3** | `CI_hi(Δ(C1)) ≤ −BAR_D` **and** `Δ(C2) < 0` (point) | **A material live recall regression since 08-08.** |
| **B2** | `CI_lo(Δ(C1)) > −BAR_D` **and** `CI_hi(Δ(C1)) < +BAR_D` | **No material change: the live gap is where it was.** |
| **B4** | otherwise (straddles a bar, replication sign disagrees, or ROW 0g) | Unresolved. |

`BAR_D = 2.0` pp. Mutually exclusive by construction: B1 and B2 cannot both hold (`lo ≥ 2` against
`hi < 2`, with `lo ≤ hi`), and likewise B3 and B2. B4 is the remainder.

### 3.7 Consequences

- **B1** ⇒ the D-001 headline is re-based. From then on, cite A1 (with its qualifiers) as the
  current live figure. "57.79%" becomes an 08-08-build figure and must name its build wherever it
  appears. Every route sizing computed on pre-08-22 corpora (the ledger §9, X1/X2 magnitudes, C-GAP-D's
  16% ceiling) is flagged **stale by build**. They are not retracted, but each must be re-derived
  before it gates anything. E4 is re-sized on A1 before it is specced.
- **B2** ⇒ the live gap on today's binary is where the 08-08 measurements put it. The 08-22 → 09-12
  work did not reach live 20m. The standing figures stay citable, and **each gets the qualifier
  "confirmed on `20260050`, `LIVE-GAP-NOW` B2"**. E4 proceeds on the standing premise.
- **B3** ⇒ **the Architect escalates to the Captain the same day.** A live regression is a product
  defect. The next step is FP-REGRESSION's machinery (git-blob binaries, seam sensitivity first),
  aimed at recall instead of FP.
- **B4** ⇒ report every figure. Nothing is re-based, and `Δ` may not be cited as a change or as the
  absence of one.

---

## §4. Architect predictions: blind, on the record, before any datum

| row | probability | reasoning |
|---|---|---|
| **B2** | 0.50 | The synthetic battery moved only where SNR collapsed on multi-signal scenes. Live 20m is crowded, but most live misses are 44% BER, far from the correction threshold (W1 bimodality). A suppression change buys the recoverable fringe only. |
| **B1** | 0.30 | Three independent mechanisms all push up: the passband (bounded by RC3 at ≈ 1.3 pp of recovery if every out-of-band miss were recovered), the SNR fix reviving pass-1 suppression in exactly the cycles X2 says cost the most, and S7's +20/215 step. |
| **B4** | 0.17 | The ±2 dead band is wide, and C2 may disagree in sign on a small effect. |
| **B3** | 0.03 | Nothing on record predicts a live loss. |

**Point prediction:** `Δ(C1) ∈ [+0.5, +2.5] pp`. **ROW 0d:** PASS, probability 0.75. The risk is
managed-side handling between `ft8_decode_all` and `ALL.TXT` that I have not read. Calibration:
my last three categorical calls in this programme missed. Weight these accordingly.

---

## §5. PO question (optional, before the first datum only)

**Q1: `BAR_D = 2.0 pp`?** Architect-set per §3.4. The Captain may change it **before QA produces any
`Δ`**. After that it is **FROZEN** for this arm. A move proposed once `Δ` is known is refused and
VOIDs the arm.

---

## §6. What this arm does NOT do

- 🛑 **No `src/` or `native/` change, no rebuild, no capture, no push, no merge** (HK-011, HK-014,
  HK-010). Old binaries come from git blobs into `artefacts/`, never into the tracked native tree.
- 🛑 **No per-commit attribution.** `Δ` is the whole `b8845cd → 19737b32` span. A bisect is a
  separate arm, and it starts from ROW 0f's lesson.
- 🛑 **Does not re-read** X1, X2, C-GAP-D, T1, AO1 or any closed gate. A B1 re-bases citations; it
  does not reopen a row.
- 🛑 **Spectral locality stays barred.** Nothing here asks whether misses sit near strong signals.
- **Cannot see:** any band other than 20m; WSJT-X's own misses (HK-026); false positives; E4.

**NFR-021.** C1 and C2 `ALL.TXT` and WAVs carry real third-party callsigns. Message text stays in
memory. Any per-row dump goes to `artefacts/` (gitignored), never `qa/`. The report carries counts,
rates, frequencies and SNRs only. **Scan the report prose** with `scan()`/`classify()` before
committing, because the scanner skips uncommitted directories.

## §7. Running order and authorisation

| step | status |
|---|---|
| This spec | ✅ Captain: *"proceed with your recommendations"* |
| Q1 `BAR_D` | Architect-set 2.0 pp. Open to the Captain until the first `Δ` exists. |
| Extract the L08 blob and pin both DLLs (ROW 0a/0b) | QA |
| ROW 0c, then decode the three legs × two corpora, then ROW 0d–0g, then the B-row, then §3.5 | QA, in that order. Supervise if longer than 1 h. |
| Report, committed locally | QA. Push/PR needs the Captain's go (HK-033). |

🔴 **HK-025 is available in full.** If any row here is a diagnostic dressed as a gate, name it,
evaluate both branches, and refuse it.
