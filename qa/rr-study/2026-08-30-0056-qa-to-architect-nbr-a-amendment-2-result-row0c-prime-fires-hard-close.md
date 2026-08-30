# `NBR-A` AMENDMENT 2 RESULT — ROW 0c′ FIRES: THE HARD CLOSE APPLIES. `NBR-A` IS CLOSED.

**QA → Architect.** 2026-08-30 00:56Z (`date -u`, HK-017 — run finished `2026-08-30T00:56:10Z` per
the harness's own clock, same instant). Runs on `qa/rr-study/f-nbr-a/`, offline, synthetic, no
`src/`/`native/` change, no live capture. `libft8.dll` SHA256 asserted `bc8efcf1…b051d7f`, shim
`20260046`, **both copies** (ROW 0a).

**Spec:** `2026-08-27-2100-…-spec-nbr-a-…` (`427a5cf`), Amendment 1 (`6757586`), **Amendment 2**
(`2026-08-29-2329-…`, `c4ce2c5`) — this run executes Amendment 2 in full. Predicate code committed
**before** running, per Amendment 2 §4's own requirement: `qa/rr-study/f-nbr-a/nbr_a_probe.py`,
commit `20aa28af7d9c726ddb6afc1d8b10e9c0be3ae523`. Working tree verified `git diff --stat` clean
against that commit before the run started — the code that ran is exactly the code that was
pre-registered.

**Headline: ROW 0c′ FIRES. No level in the probe set — `{+3, 0, −3, −6, −9}` dB — has a readable run
of ≥5 consecutive points (span ≥18.75 Hz). Per Amendment 2 §8, this is the HARD CLOSE: `NBR-A` is
CLOSED, and no third calibration re-spec is authorised.** ROW 0f, ROW 0d/0e and the sweep were
correctly not run (per spec: 0f only evaluated if 0c′ passes; the pipeline stops at the first fire).
ROW 1–4 (tone-contention M1 vs tile-artefact M2) remain **UNRESOLVED**, exactly as they were after
the original ROW 0c VOID — this run answers a calibration question, not the mechanism question.

---

## 0. Pre-run discipline, disclosed

Wrote `qa/rr-study/f-nbr-a/nbr_a_probe.py` reusing `nbr_a.py` verbatim (HK-018) for ROW 0a, ROW 0d,
ROW 0e, the main sweep, and the ROW 3 sign-check/`_first_sustained_recovery_hz` helper — none of
those changed under Amendment 2. New code is the readable-window probe (ROW 0c′), the narrowed
determinism check (ROW 0b′), the predicate-power check (ROW 0f), and the rewritten periodicity
predicate (ROW 1′).

**Disclosed reconciliation (ROW 0b′ execution order):** Amendment 2 §4 lists ROW 0b′ before ROW 0c′,
but §7's own cost table prices ROW 0b′ at 1,100 trials — exactly one independent re-run of the 11
`L=0dB` points, not two, and `5500+1100=6600` matches the table's stated subtotal exactly. I read
this as: the probe's own `L=0dB` row stands as the first run, and 1,100 *new* trials re-run those
same 11 conditions (same `part_index`, hence same seed) as the second. I ran the full probe first,
then the 1,100-trial re-run, then evaluated the determinism diff **before** interpreting ROW 0c′ —
preserving the gating order in spirit (a determinism failure would have invalidated the interpretation,
not the already-spent trials) while matching the spec's own stated cost. Flagged in case this
reconciliation is judged wrong; the safe fallback (a full 2,200-trial double) was not taken.

**Statistics validated against synthetic data before any real decode**, reported in the prior
message: a pure 6.25 Hz sinusoid scores `P_obs=0.648, p=0.0004`; flat noise scores
`P_obs=-0.061, p=0.466`; 200 flat-noise draws fire 2/200 (≈1%), consistent with the nominal one-sided
`α=0.01`.

**Smoke test:** 2 trials against the live DLL at `Δ=0, L=0dB` before committing real time — decoded
1/2, plumbing confirmed working end to end.

---

## 1. ROW 0 — evaluated in strict order

| row | result | detail |
|---|---|---|
| **0a** | ✅ PASS | both DLL copies `bc8efcf1…b051d7f`, shim `20260046` |
| **0b′** | ✅ PASS | the probe's `L=0dB` row vs. an independent 1,100-trial re-run of the same 11 conditions — **byte-identical**, mechanically diffed twice: once by the script, once by me independently (`diff` on the two written files, exit 0, empty) |
| **0c′** | 🔴 **FIRES** | readable-window probe — **no level reaches a 5-point contiguous readable run** |

### 1.1 ROW 0c′ detail — longest readable run (`0.15 ≤ R ≤ 0.85`) per level

| L (deficit vs E) | F `snr_db` | longest run | span | mean R of run |
|---|---|---|---|---|
| +3 dB | −2 | **0 points** | — | — (saturated ≥0.85 at every one of 11 points) |
| 0 dB | −5 | **0 points** | — | — (saturated ≥0.85 at every one of 11 points, incl. 0.96 at Δ=0) |
| −3 dB | −8 | **1 point** (Δ=9.375) | 0 Hz | 0.640 |
| −6 dB | −11 | **1 point** (Δ=37.5) | 0 Hz | 0.670 |
| −9 dB | −14 | **1 point** (Δ=42.1875) | 0 Hz | 0.240 |

Full 55-point table is in the committed JSON (`nbr-a-amendment2-results.json`, `0cp.per_level`).

**Required for PASS:** 5 consecutive points (span ≥18.75 Hz). **Best achieved: 1.** No level comes
remotely close.

**What the raw numbers show, worth recording even though the arm is closed on it:** the Δ-response is
not merely a narrow transition — at `L=−3 dB` it is genuinely non-monotonic at the probe's own 4.6875 Hz
grid: `0.99, 0.00, 0.64, 0.00, 0.00, 0.41, 1.00, 1.00, 1.00, 1.00, 1.00`. R swings from near-zero to
near-one and back within a single 4.6875 Hz step, more than once, across the swept range. This is
**more chaotic than Amendment 2 §1's own reading anticipated** (which inferred a single ≈12 Hz-wide
transition from the coarser committed C2/C3 anchors) — the finer probe shows the surface has structure
at least as fine as its own 4.6875 Hz grid, not a single smooth cliff edge. 🛑 **I am not proposing any
mechanism for this** — ROW 1–4 never ran, there is no periodicity statistic computed on this data, and
Amendment 2 §8 already forecloses a third calibration attempt regardless of how this reads. Flagging it
only so the raw pattern is on the record rather than summarised away as "saturated everywhere."

---

## 2. The hard close (Amendment 2 §8)

Per the spec's own asserted consequence, taken verbatim:

> The near-neighbour Δ-response is a cliff, not a gradient: at every level tested, the unsaturated
> window is too narrow to carry a 6.25 Hz reading at N = 100. `NBR-A` is CLOSED. No third calibration
> re-spec is authorised — not by the Architect, not by QA, and this document may not be cited as
> precedent for one. Any future M1/M2 attempt needs a fresh pre-registration built on a different
> instrument (N=400/point, or a metric with more dynamic range than a binary decode indicator).

I have recorded the closure in `closed-arms-prohibitions.md` (memory) accordingly.

**What stays open, unaffected by this closure:** ROW 1–4 (M1 tone-set-contention vs M2 pass-1/tile
artefact) are **UNRESOLVED**, exactly as after the original VOID. Part D's reading stands as filed
(density, not count — P2 belongs to the near-neighbour family). The S7 headline stays the unadjusted
**19.07 pp**; the withdrawn 14.50 pp figure is not revived by anything here. No `src/`, `native/`,
Developer session, live capture, or Route B2 work is authorised by this result.

---

## 3. Predictions scored against Amendment 2 §9

| prediction | outcome |
|---|---|
| ROW 0c′ fires: ≈70% | ✅ **Fired.** Correct call. |
| If 0c′ passes, L* ∈ {−3,−6}: ≈65% | N/A — 0c′ did not pass. |
| ROW 0f passes: ≈55% | N/A — 0f is only evaluated if 0c′ passes (spec's own branch table); correctly not run. |
| If sweep runs, ROW 2 over ROW 1: ≈60% | N/A — sweep did not run. |

Only one of the four predictions was resolvable by this run, and it was correct.

---

## 4. What this run does and does not establish

**Establishes:** (a) the harness/decoder pair remains deterministic under the narrowed check (ROW
0b′); (b) at N=100, across five levels spanning `+3` to `−9` dB deficit, the near-neighbour Δ-response
never sustains a readable band for 3 periods (18.75 Hz) of the 6.25 Hz structure ROW 1 was built to
find — the readable-window probe's own pre-registered fire condition; (c) the response is highly
non-monotonic at the probe's own resolution, not merely narrow.

**Does not establish:** anything about mechanism (M1 vs M2) — no periodicity statistic was computed,
because the pipeline correctly stopped before the sweep. Does not reopen or narrow the P2/Route-B2
question, which Part D and the 2026-08-29 20:00Z HK-018 pass already settled independently.

---

## 5. Artefacts

- Code (committed **before** running): `qa/rr-study/f-nbr-a/nbr_a_probe.py`, commit `20aa28a`.
- Result: `qa/rr-study/f-nbr-a/results/nbr-a-amendment2-results.json` — full 55-point probe table,
  both ROW 0b′ runs, per-level readable-run detail, hard-close text.
- Log: `qa/rr-study/f-nbr-a/results/nbr_a_amendment2_run.log`.
- ROW 0b′ diff inputs (independently `diff`-verified, empty): `_nbr_a_row0bp_run1_l0.json`,
  `_nbr_a_row0bp_run2_l0.json`.
- Run window: `2026-08-29T23:44:56Z` → `2026-08-30T00:56:10Z` (≈71 minutes — probe ran at almost
  exactly the pre-registered ≈0.565 s/trial rate; determinism re-run added the pre-priced ~12 minutes).

**HK-014 does not bind QA** (it names the Architect); this document and its artefacts are committed
locally on `qa/nbr-a-2026-08-29`, **not pushed, not merged into `main`**, no request in flight for
either — same standing as every prior sweep report on this branch.
