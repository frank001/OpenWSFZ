# `OSD-FA-A` E3 — result: **`E3-N`** — no live harm detected at this resolution (never "safe")

QA, 2026-09-11 22:04Z (`date -u`, HK-017). Per Amendment 1 §5.3, continuing after the Architect's
`E2-B1` acceptance ruling (`2026-09-11-2124-...-e2-acceptance.md`, `arch/osd-fa-a` `2401460`).

**Headline: `E3-N` fires.** Reproduction clears at `99.39%`. Of `1,509` live decodes the `40`-leg
failed to reproduce, only `11` were independently confirmed by `WSJT-X #1`. `CP95 [0.36%, 1.30%]`
sits entirely below `BAR_H = 0.05`. **No live harm detected at this resolution — this is not a
finding of safety, per base §5.3/§6 and the standing `FP-FLOOR-LIVE-2` corroboration principle
(corroboration bounds genuine loss only from below).**

---

## 1. HK-020 — critical config

| config | value | source |
|---|---|---|
| Corpus/span | `FP-FLOOR-LIVE-2`, `[260908_193645, 260909_172200)`, `5,222` archived cycles | Amendment 1 §3 (unchanged from Part D) |
| `60`-leg | **reused, not re-decoded** (HK-018): `artefacts/2026-09-10-f001-l3-live-measurement/subject_20260050.json` — `p23_common.Decoder`'s own `DECODE_PARAMS=(10,0.10,60)`, production defaults, same binary/window/input-contract as this arm's own Part D3 leg | verified: `65,798` total decodes, matches the established F-001 L3 figure exactly |
| `40`-leg | new full-corpus replay, `part_e3_replay40.py` — same harness mechanics (`p23_common.read_wav`+`normalise_rms(0.20)`, `select_files`), `ft8_set_decode_params` overridden to `(10,0.10,40)` once, before the first decode, never mid-run | Amendment 1 §5.3 |
| Matching | `wildcard_match` (same cycle, `\|Δf\|≤3Hz`), for **both** reproduction and removal | Amendment 1 §5.3, reused from `h1_hash_token_contamination.py` |
| Reproduction bar | `≥0.90` (else VOID) | Amendment 1 §5.3, the E3-0 rule |
| `BAR_H` | `0.05`, **frozen** `2026-09-11 16:26Z`, before any Part E datum existed | PO ratification, Amendment 1 §5.3 |
| Live population | OpenWSFZ's own `openwsfz/ALL.TXT`, dial-filtered (`14.074`), span-filtered — **`57,947`** decodes, matching Part D2/D3's own count exactly | Amendment 1 §5.3 — "counts only what production emitted" |

**Disclosed scheme:** the `40`-leg uses **one setting for the entire run** (not switched per-cycle)
— the other of the two schemes the E1 acceptance ruling accepts. `ft8_set_decode_params` is called
exactly once, before `select_files`'s first file is decoded.

**Added 2026-09-11, per the E3 acceptance ruling §2 (`2026-09-11-2210-architect-osd-fa-a-e3-acceptance.md`,
`arch/osd-fa-a` `8fe712a`): "same harness" was checked on COUNT only (`65,798` matching), which
shows the reused `60`-leg file is the intended one — it does not by itself show the new `40`-leg
harness behaves identically apart from `nhard`.** Checked, independently re-derived: since `nhard`
gates only OSD accepts, a harness identical except for `nhard` should make the `40`-leg a
(near-)**subset** of the `60`-leg. **`40`-leg decodes with no `60`-leg decode within `3Hz` in the
same cycle: `14` of `58,438` (`0.024%`). Live decodes matched at `40` but not at `60`: `20`.** The
`40`-leg is a frequency-subset of the `60`-leg to within `0.03%` — no harness difference beyond
`nhard` is visible.

## 2. Method

For every live-emitted decode in the span:

- **reproduced** — the `60`-leg replay has a decode in the **same cycle**, wildcard-matching
  message, `\|Δf\|≤3Hz`.
- **removed** — reproduced at `60`, **and** no such match in the `40`-leg (identical criteria).

Counting only live-emitted decodes (never a replay-only decode neither leg's production run ever
showed the operator).

## 3. Result

```
n_live_total (live decodes in span)     = 57,947
n_reproduced (matched in the 60-leg)    = 57,594
reproduction share                      = 99.39%   (>= 0.90 -- NOT VOID)

n_removed (reproduced@60, no match@40)  = 1,509
k_corroborated (removed AND confirmed by WSJT-X #1) = 11

Clopper-Pearson 95%, k=11, n=1,509: [0.364%, 1.301%]
BAR_H = 0.05 (frozen)
```

**Row: `lo = 0.364% < BAR_H(5%)` ⇒ `E3-N`.** The CI sits entirely below the bar by a wide margin
(the upper bound, `1.30%`, is itself well under `5%`).

**What the `1,509` removals actually are, per the E3 acceptance ruling §3 (independently
re-derived, exact match):**

| category | n | corroborated |
|---|---:|---:|
| No `40`-leg decode within `3Hz`: genuinely vanished | 994 | 1 |
| A different message at the same frequency | 497 | 1 |
| **Same decode, different hashed-callsign rendering** (`<X>` vs `<Y>`) | 18 | **9** |
| **total** | **1,509** | **11** |

**The `18` are not removals** — the two legs build different callsign-table histories once the
`40`-leg drops decodes (exactly the confound Amendment 1 §5.3 named; wildcard matching covers only
literal `<...>`, not two different resolved brackets). They carry `9` of the `11` "corroborated"
removals. **Both branches evaluated (HK-025), same row either way:**

| reading | k/n | CP95 | row |
|---|---|---|---|
| pre-registered (wildcard) | 11/1,509 | `[0.364%, 1.301%]` | `E3-N` |
| true removals (drop the 18) | 2/1,491 | `[0.016%, 0.484%]` | `E3-N` |
| frequency-only (vanished only) | 1/994 | `[0.003%, 0.559%]` | `E3-N` |

`E3-N` is **accepted on the pre-registered figure** (§2 above); the "true removals" figure is
**descriptive, not a re-read of the gate** — its direction shows the pre-registered `k` overstates
corroborated removals about `5×`, biased **toward** `E3-H`, so `E3-N` is conservative.

**Corrected citation:** *"`E3-N`: of `1,509` live decodes the `40`-leg failed to reproduce, `11`
were corroborated by `WSJT-X #1` (`CP95 [0.36%, 1.30%]`). Descriptively: `18` of the `1,509`, and
`9` of the `11`, are callsign-rendering differences, not removals. True removals are `1,491`, and
`2` of them are corroborated (`≈0.09`/hour against `≈68.6` removed/hour)."*

**Descriptive (base §5.3/Amendment 1 §5.3):**

- Removed decodes per hour (span `21.75h`): **`69.4`**.
- Of those, corroborated-removed per hour: **`0.51`**.
- Uncorroborated-removed per hour: **`68.9`**.

🛑 **Never write "safe", "no cost" or "negligible".** Per the `FP-FLOOR-LIVE-2` Part B acceptance
ruling's own standing principle (reused here by construction, Amendment 1 §5.3's own reminder):
corroboration by a second decoder bounds genuine loss **from below only**. A low corroborated share
among removals cannot prove the removed decodes were mostly junk — WSJT-X itself misses genuine
weak signals. `E3` can detect harm; it structurally **cannot** establish safety, at any reading.

## 4. Determinism and cross-checks

- `60`-leg reused verbatim from a prior, already-verified arm (F-001 L3 ROW 0d: two independent
  processes, `0/5,222` cycles differ) — not re-run here.
- `40`-leg: single deterministic replay (`0` AV faults across `5,222` files); the analysis itself
  (`part_e3_analysis.py`) is a pure deterministic function of two fixed JSON inputs plus `ALL.TXT` —
  re-running it reproduces identical output by construction (no sampling, no randomness anywhere
  in this leg).
- Binary/window assertions: both legs' own recorded `dll_sha256` (`6b2e16a6…4f85c`) and `window`
  checked equal in-code before any comparison runs (`part_e3_analysis.py` asserts this, not just
  documents it).
- `65,798` total `60`-leg decodes reproduces the established F-001 L3 figure exactly (independent
  confirmation the reused artefact is the one intended).

## 5. Amendment 1 §5.4 — where this leaves the arm

**Strict order, all three legs now in hand:**

1. `E2-B2 or E3-H` — **neither fired.** Not contraindicated on this reading.
2. `E1-2` — **did not fire** (`E1-1` fired instead).
3. **`E1-1 ∧ E2-B1 ∧ E3-N`** — **all three hold.** The Architect is cleared to **draft** a
   separate pre-registration for `osd_nhard_max` 60→40. **This is not a licence to build, touch
   `src/`, or change anything** (HK-011).

🔴 **Bound by the Architect's own HK-026 addendum to the `E2` acceptance ruling: any such draft
must carry a near-threshold oracle leg (e.g. a synthetic scene spanning `−24` to `−18dB`) as its
own safety gate, with its genuine OSD-path population counted and confirmed non-trivial *before*
any loss statistic from it is read.** `S8HN` (Part A/B/E2's own scene) cannot serve as that gate —
it has no near-threshold genuine signal at all (`per_cycle_true = 11` in every one of `1,000`
cycles). Without that leg, **no default change goes forward**, regardless of how `E1`/`E2`/`E3`
read.

~~**What the whole arc supports, read together, per the mandatory `D1`/`E1` pairing (E1 acceptance
ruling §4):** on noise, `nhard` in `(40,60]` accounts for `~97%` of false-decode events (`E1`); on
live audio, `OSD`-path decodes are `≤~1.9%` of output (`D1`'s CI upper bound) — Option B's live
reach is bounded by that `1.9%`, not the `97%`.~~ ⛔ **STRUCK 2026-09-11, per the E3 acceptance
ruling §4: "Option B's live reach ≤~1.9%" is WRONG, and it is the Architect's own error (also
struck by him in the `…1932…` and `…2048…` rulings, `BOARD.md`, and `MEMORY.md`) — repeated here
only because he had made the `D1`/`E1` pairing mandatory; no fault attaches to QA.** `D1`'s `U`
covers only decodes the Part D probe could **classify**, and OSD accepts are exactly the decodes
that probe struggles to reproduce (`41%` of D3's unconfirmed decodes were ones the probe found
nothing at all) — `U` therefore **undercounts** the OSD share; an instrument cannot bound its own
blind spot (HK-026). **`E3` measures reach directly: true removals `1,491/57,594 = 2.59%`, `CP95
[2.46%, 2.72%]` — above `D1`'s own `CI_hi` of `1.88%`.** Counting every D3-unclassifiable decode as
OSD gives `≈5.7%` at worst (`(183+483)/11,615`, independently re-verified); both figures stay under
`10%`, so `D1`'s own row and consequence stand unchanged. **Replacement citation:** *"OSD-path
decodes are between `~2.6%` (`E3`, direct) and `~5.7%` (Part D3, worst case) of live output; `D1`'s
`U=1.64%` undercounts them. Option B removes `~2.6%` of live output."* `E3` adds: of what `60→40`
actually removes live, only `0.13%` (`2/1,491` true removals) is independently confirmed genuine at
this resolution — not proof the rest was junk (§3 above).

## 6. NFR-021

`ALL.TXT` (OpenWSFZ and `WSJT-X #1`) carries real off-air callsigns. Message text held in memory
only, for `wildcard_match` and corroboration checks — never printed, logged, or written. Both
replay JSONs (`artefacts/2026-09-10-f001-l3-live-measurement/`, `artefacts/2026-09-11-osd-fa-a-e3/`)
are blanket-gitignored and carry raw message text per their own established discipline (same as
`g3_h12_replay.py`'s own `out_json` convention); this report and `part_e3_analysis.py`'s own output
carry counts only. Scanned with `nfr021_pre_merge_scan.py` before commit.
