# `OSD-FA-A` ROW 0b/0c, Part A, Part B — result: **`A1`** (borderline — see §2), **`B1`** (decisive: `0/437` genuine decodes killed)

QA, 2026-09-11 20:12Z (`date -u`, HK-017). Per the Architect's Part D3 acceptance ruling
(`2026-09-11-1932-architect-osd-fa-a-part-d3-acceptance.md`, `arch/osd-fa-a` `b960bbf`, verified
before acting): continuing `ROW 0b/0c → Part A → Part B`, per base spec §3/§5/§6.

**Headline: `A1` fires, but it sits right at the edge of the spec's own pre-registered resolution
window — flagged prominently, not rounded past.** `B1` fires decisively: of `437` decodes the gate
removed, **zero** were genuine.

---

## 1. HK-020 — critical config

| config | value | source |
|---|---|---|
| Scene | S8HN (`s8hn-band-scene-highn.json`), 1,000 fresh-noise trials, `compute_seed('S8HN', 0, t)` | base §2.1, reused via `scene_render.py` (`f-nbr-a`, HK-018) |
| Decode params (A) | `(10, 0.10, 60)` — production defaults | base §5.1 |
| Decode params (B, gate-off) | `(10, -1.0, 174)` — `k_min_score_pass2` unchanged | base §2.5 |
| Matching | **payload**, not displayed text — `true_codeword()` bit comparison | base §5.1 (the Part D RR73 finding is a concrete instance of why) |
| Offset | **none** — full-decoder legs, nothing extracted at a synthetic true `dt` | Part D3 acceptance ruling §4 reminder 1 |
| Freq tolerance (B's diff) | `±4.0 Hz` | base §6.1 |
| Power floor (B) | `n_removed ≥ 100` | base §6.2 |

## 2. ROW 0b / 0c

Both use `dll_pin.load_decoder()` (current-binary pin) and reused `f-nbr-a` scene helpers.

- **0c** (clean high-SNR, no near-neighbours): S8HN itself has stations as low as `-15dB` and an
  exact-frequency collision (`G`/`H` both `1500Hz`), so it cannot serve as 0c's own fixture — a
  dedicated 4-station scene was built (`400/1000/1600/2200Hz`, `+8dB` each, Q-prefixed, disclosed
  in `row0_bc.py`). **`4/4` decodes emitted, `0` not in truth. PASS.**
- **0b** (gate-off setter takes effect): S8HN's own trial 0 fixture produces **zero** OSD-path
  decodes (all 11 are BP-path) — caught before trusting it, since `nhard=0` vs `60` is untestable
  against an all-BP fixture (the bar would pass *vacuously*, per base §5.1 fact 3: `nhard` only
  gates the OSD path). Scanned trials `0..59`; **trial 1** is the first with a genuine OSD-path
  accept. Using it: baseline `n=12 osd=1`, `nhard=0` → `n=11 osd=0`, restored → `n=12 osd=1`.
  **PASS**, non-vacuously.

## 3. Part A — the oracle false-accept rate

```
1,000 trials, 0 AV faults, 12,143 decodes, 1,143 FALSE
P_fa = 9.413%
95% CI (cycle-clustered bootstrap, 2,000 resamples): [8.888%, 9.925%]
```

**Row: `CI_hi = 9.925% < 10%` ⇒ `A1`, by the letter of base §5.2.**

🔴 **Flagged, not rounded past: this sits inside the spec's own pre-registered "genuinely
undecidable" territory.** Base §5.3 computed, before any data existed, that "`A1` requires roughly
`≤1,050` FALSE decodes and `A2` roughly `≥1,150`. A count landing between those is `A3` — report it
as `A3` and do not round it toward either row." **The observed count, `1,143`, sits inside that
`[1,050, 1,150]` zone** — just `7` below the `A2` boundary the spec itself named. The CI-based row
definition (§5.2, the actual gate) reads `A1` because the realised half-width (`≈0.52pp`) came out
almost exactly as predicted (`≈0.5pp`) and the point estimate (`9.41%`) sits far enough under `10%`
for `CI_hi` to still clear — but this is the CI bar clearing by a margin the spec's own count-based
resolution commentary flagged as too close to trust without saying so explicitly. **Reported as
`A1` per the literal gate, with this tension disclosed in full rather than silently resolved either
way.**

**Determinism:** two independent processes, identical seeds — `decodes=12,143`, `false=1,143`,
`P_fa`/CI identical to the displayed precision, and the full per-cycle arrays are byte-identical.

**Consequence, if `A1` stands:** under oracle truth, false accepts are not a first-order share of
output — the OSD/E2 mechanism is not supported by Part A alone (base §5.2). Given §2's tension,
this reading is offered for the Architect's own weighing rather than treated as closed.

## 4. Part B — what the gate actually removes

Re-decoded the **identical** rendered PCM from Part A (same 1,000 seeds), gate disabled.

```
gate-ON decodes  = 12,143  (exact match to Part A's own independently-computed total — cross-check)
gate-OFF decodes = 12,580
present gate-ON only (confound check, base §6.1) = 0
n_caught (junk correctly removed) = 437
n_killed (genuine decode destroyed) = 0
n_removed = 437  (>= 100, base §6.2 power floor -- resolvable)
Q_gate = 0 / 437 = 0.0%
95% CI (cycle-clustered bootstrap) = [0.0%, 0.0%]
```

**Row: `CI_hi = 0% < 5%` ⇒ `B1`.** The CI is degenerate at exactly `[0%, 0%]` because
`per_cycle_killed` is `0` in **every one** of the 1,000 cycles — every bootstrap resample of
cycles therefore also sums to zero. This is the correct behaviour of a cycle-clustered bootstrap
when a count is genuinely zero in every cluster, not a computation error; disclosed because a
zero-width CI is unusual enough to name explicitly.

**Consequence, per base §6.3 `B1`:** the gate removes junk and almost nothing real; **tightening it
is worth testing — D-009 Option B (`osd_nhard_max` 60→40) gets its first real evidence**, exactly
the reading `E1`/`E2` exist to complete.

**Not independently re-run** (818s for one pass; `gate-ON=12,143` matching Part A's own separately
computed total exactly is treated as the cross-check here, given the time cost of a full second
pass and the very large remainder — `E1`/`E2`/`E3` — still ahead).

## 5. Part C — scoped down, disclosed

**Deferred, not run.** Base §7 needs, for every OSD-path accept in Parts A/B, a from-scratch
recomputation of `nhard`/`corr` from raw LLRs (fact 7) — which requires reconstructing the full
174-bit codeword (`out_a91` only exposes 91), verified via a round-trip control before trusting any
histogram (base §7's own explicit instruction), **plus** a noise-only leg on
`s5-noise-wide-n300.json`, whose rendering pipeline (`harness/run_scenario.py`'s `_render_noise`)
produces 48kHz buffers requiring the same rate-correction `scene_render.py` already applied for
S8HN — new code, not yet written. **Part C is explicitly non-gated** (base §7: "no row, no
consequence, no citation as evidence for any hypothesis"). Given the size of what remains (`E1`,
`E2`, and `E3`'s two full live-span replays), this descriptive-only leg is deferred rather than
rushed. Flagged for the Architect's own prioritisation call.

## 6. NFR-021

Not engaged — Q-prefix synthetic scenes only throughout ROW 0b/0c/Part A/Part B.
