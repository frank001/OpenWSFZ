# `PASSBAND-140` — acceptance ruling: **GATE = G1 ACCEPTED**, no corrections owed, Q2 confirmation recommended to the Captain

**Architect, 2026-09-14 17:16Z** (`date -u`, HK-017). Branch `arch/g2b-passband-140`.
Docs-only; `git diff --stat origin/main...HEAD -- src/ native/` empty.

Accepts: QA's `qa/rr-study/2026-09-14-1707-qa-to-architect-passband-140-result.md` (`qa/base`
`41075777`, zero `src/`/`native/` diff), against the spec
`2026-09-14-1542-architect-to-qa-spec-g2b-140-passband-rearm.md` (`69f372c0`) as amended by
Amendment 1 (`4b7b9044`).

**Handoff note.** My prior session ended unreachable partway through this arm, right after the six
legs finished decoding. QA completed the measurement and reported the result straight to the
Captain rather than relaying through me, per the spec's own §7 running order breaking down — the
right call, not a process gap. QA correctly did **not** author the ship dev-task without Q2, and the
Captain asked for me back in the loop before QA moves toward shipping. This ruling is that.

---

## 1. Verdict

**`GATE = G1`, and I accept it.** Opening the candidate passband to `[140,3075)` Hz recovers real,
WSJT-X-confirmed signal on C2 with no material in-band cost, and C1′ replicates in sign.

I did not just re-read QA's numbers — I re-executed QA's own `measure.py` against the committed
`_out/*_chained.jsonl` artefacts in QA's worktree (same code, re-run by me, not a from-scratch
reimplementation; the bootstrap is seeded so this is a legitimate identity check, not a coin flip):

```
D(C2)      = 1.4136 pp   (matches report to 4 dp)
D(C1')     = 0.5959 pp   (matches)
D CI (wider, freq)  = [0.4209, 2.7779]   (matches)
D_in CI (wider)      = [-0.0203, 0.0160] (matches)
additive identity: |diff| = 0.00e+00 (C2), 3.33e-16 (C1')  (matches)
GATE: G1 -- ship-eligible   (matches)
```

Exact reproduction, every figure. One cosmetic note, not a correction: `measure.py`'s own gate
banner still prints *"PROVISIONAL, Q1 not yet confirmed by the Captain"* — stale script text from
before Amendment 1 settled Q1's mechanical reading (§5 below). It doesn't reach the committed
report and changes nothing; QA can pick it up next time the file is touched.

## 2. ROW 0 review

All eight PASS, and I have no disagreement with how any of them was read:

- **0b** correctly used the spec's own fallback branch (`SHA(BASE)` ≠ shipped pin — a
  non-reproducible link, not a wrong build) and recorded it exactly as the manifest instructs:
  `BASE` = the fresh SHA, not the pin, with the 500/500-cycle, 0-differing K60/B60 evidence
  attached. This is the same non-reproducible-build pattern seen before; QA's handling matches
  precedent.
- **0d** `F_live = 0.9843` on C2, cross-checks cleanly against LIVE-GAP-NOW's independently-measured
  `F_live = 0.9832` on the *same* corpus/binary/`nhard` — two different arms' seam checks landing
  within 0.1pp of each other is a good sign the chain tooling itself is sound, not just internally
  consistent.
- **0f** both edges exhibited with `(ts, freq_hz, snr)` only, per spec — NFR-021 clean.
- **0c/0e/0g/0h** unremarkable passes, numbers match the spec's own drafted-in expectations where
  it had one (0c's `57,969` row count is exact).

Nothing here reads as a diagnostic dressed as a gate (HK-021(k)/(y)) — I checked the counterfactual
on each STOP-worthy row and a differently-landing result would have changed the verdict every time.

## 3. Corrections owed

**None.** Unlike THRESH-A and LIVE-GAP-NOW, this report needs no in-place fix before it can be
pushed. The bands, the yield calculation, the A3 density ratio, and the CI disclosure (§4, realised
SE ~3-6× the spec's own predicted range — correctly flagged as a power note, not hidden) all check
out on inspection and on independent re-execution.

## 4. Prediction scorecard (spec §4, on the record)

| | predicted | outcome |
|---|---|---|
| Row | G1 0.45 · G2 0.25 · G4 0.20 · G3 0.10 | **G1** |
| `D(C2)` | `[+0.55, +1.4]pp` | **+1.4136pp** — at the very top edge of my interval, not inside it |
| low yield | `[0.35, 0.65]` | **0.686** — above my interval |
| top yield | `[0.25, 0.65]` | **0.1120 ÷ 0.17% share ≈ 65.9%** — top of my interval |
| ROW 0b | SHA 0.4 / output-identity 0.9 | fallback fired, **PASS by output identity** |
| ROW 0d | PASS, 0.85 | **PASS** |
| A3 flag | fires, 0.6 | **did not fire** (ratio 1.80 < 3) |

Net: I called the right row (G1) but under-called its size on every magnitude prediction, and
over-called the A3 flag risk. The pattern across this and the last two arms (LIVE-GAP-NOW ROW 0d,
THRESH-A `T2`/`Δ50`) is a real signal about my own calibration, not this arm's result — noted, not
acted on here.

## 5. Q1 / Q2 / Q3 disposition

- **Q1 (bars):** QA's reading is right and not a judgement call — the spec's own §5 text is
  unconditional (*"frozen after [D is known]... refused and VOIDs the arm"*), and `D` exists now.
  Nothing to rule on; there is nothing left to move.
- **Q2 (ship-after-R2 condition) — the one open item, and it's the Captain's alone.** My §0.4
  reading stands unchanged since I wrote it: R2 reported 2026-08-22 (`fe98e171`), and its successor
  route (Route B2) was parked today on THRESH-A route A. Nothing has moved since I wrote that
  reading that would revise it. **I recommend the Captain confirm §0.4 discharged.** I am not the
  authority on his own prior ruling, so I am not treating this recommendation as a confirmation —
  QA was right to wait, and I'm not overriding that by ruling on Q2 myself.
- **Q3 (retire revision-6 bars):** already correctly implemented — QA reports the legacy terms
  descriptively only (A4, not computed this pass, explicitly non-blocking) and applies no revision-6
  gate. Consistent with §0.3.

## 6. What ships, if the Captain confirms Q2 (spec §3.7, restated so it doesn't need re-deriving)

1. `f_min` 140 and `f_max` 3075 at both `ft8_shim.c` call sites (`:1472`, `:1872`) — the two lines
   already proven in `WIDE`.
2. `FT8_SHIM_VERSION` bump, all-platform rebuild (macOS by CI, as standing).
3. `BUILD.md`'s "Monitor Configuration" block updated to match.
4. **The false comment at `Ft8LibInterop.cs:231`** — checked again just now, still reads *"the
   decode candidate passband widens from `[200, 3000)` Hz to `[140, 3030)` Hz"* on `main` today.
   Still false either way; fix it in the same task regardless of which edge(s) ship.
5. Merge needs the Captain (HK-010). From that point, `A1 = 61.09%` becomes a **pre-G2(b)** figure
   and must be labelled as such in any future citation.

QA's own §0.4/§3.7 reading — author the ship dev-task only after the Captain confirms — is correct
and I'm not shortcutting it.

## 7. Decision note for the Captain

**What QA measured, independently checked by me: real.** `+1.41pp` of genuine, WSJT-X-confirmed
20m recovery on today's live corpus and today's shipped binary, at essentially zero in-band cost,
replicating in sign on a second corpus. Nothing about the arm reads as marginal — all three `G1`
conjuncts clear their bars comfortably, not narrowly.

**Two things need your word before this moves further:**

1. **Confirm §0.4 (Q2) discharged**, so QA can author the ship dev-task. My reading hasn't changed:
   yes, discharged.
2. **Authorise QA to push `qa/base`** (HK-033) — this result and its two predecessor reports
   (THRESH-A, LIVE-GAP-NOW) are the only things riding on it.

Once both are given, the path is: QA authors the ship dev-task → Developer builds it (HK-011) →
merge on your sign-off (HK-010). I'll return to `arch/base` once this branch's own docs are on
`main`.
