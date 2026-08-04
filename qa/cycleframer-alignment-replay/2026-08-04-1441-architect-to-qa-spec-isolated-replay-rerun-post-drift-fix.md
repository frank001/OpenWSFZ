# Architect → QA — spec: re-run the isolated-replay pilot against the fixed build
# Two arms, one contrast, entirely offline. No capture run. No `src/` change.

**Author:** Architect, 2026-08-04 (14:41 UTC, `date -u`, per HK-017). Repo at `cccfd54`.
**For:** QA.
**Executes:** `qa/rr-study/results/2026-07-23-d001-live-path-root-cause/report.md` §5.3 item 2 —
*"If a fix ships, re-run the Tight/Isolated replay pilots against a corrected build to measure how
much of the ~23.4% Isolated-class gap the fix actually recovers."* The fix shipped 2026-08-03
(`be5960a`). **That validation has never been run.**
**Authorised by the Captain, 2026-08-04.** This is the only item authorised here.

---

## 1. The question, stated so it can be answered wrongly

PR #103 measured **≈23.4% Isolated-class Decoded-on-replay**: of the signals WSJT-X decoded and
OpenWSFZ missed *live*, ~23.4% of the Isolated class decoded when the same audio was replayed. The
2026-07-23 investigation root-caused that to window drift (−42 ppm device + sample-count-only
framing), with two independent methods agreeing to 89%.

**If drift was the mechanism, a build that no longer drifts should lose those decodes far less
often live, and the replay should therefore recover far fewer of them.** If the recovery rate
barely moves, a **second pre-decoder mechanism exists that we have not named**, and that is the
more important result of the two.

**This does not re-open D-001.** D-001's deficit was measured on segment 1 of the 8081/20m corpus,
drift-screened at **0.136 s peak over 2.72 h** (PASS, 3.5× headroom, `2026-07-31-1719`). Drift was
not the mechanism there and this spec does not claim otherwise.

## 2. Design — two arms, because a single post-fix number means nothing

The pre-fix 23.4% came off a different corpus, band and propagation than anything we can capture
now. Comparing a fresh number against it directly would confound the fix with the corpus. **Run
both arms through the same script, same build, same day.**

| arm | corpus | live leg framed by | expectation |
|---|---|---|---|
| **A** (positive control) | `20260731_live_run_2004-8080` (43.6 h, both legs) | **drifting** build | recovery rate materially > 0 — reproduces the PR #103 effect |
| **B** (the measurement) | `20260803_live_run_1713` (20.73 h, both legs) | **fixed** build (`be5960a`) | recovery rate collapses if drift was the mechanism |

Both corpora carry an OpenWSFZ leg, a WSJT-X leg and both WAV sets — verified in
`qa/ARTEFACT_INVENTORY.md`. **Nothing needs capturing.**

The contrast works because the *replay* side of both arms runs on today's fixed build. Only the
**live** side differs: arm A's live decodes were produced by a drifting framer, arm B's by a fixed
one. **`r = recovery_B / recovery_A` is the statistic.**

## 3. Pre-registered rule — commit this to git BEFORE running either arm (HK-021)

Let `recovery_X` = (Isolated-class live misses that decode on replay) / (Isolated-class live
misses), per arm. Let `r = recovery_B / recovery_A`.

Strict order, first match wins, mutually exclusive:

| row | condition | consequence |
|---|---|---|
| **1 VOID** | either arm has `< 200` Isolated-class live misses | no verdict; report the counts and stop |
| **2 VOID** | arm A's corpus does **not** fire ROW 2 on `drift_screen.py` | wrong corpus — the positive control must be the drifting one ⇒ no verdict |
| **3 VOID** | `recovery_A < 0.10` | the instrument cannot reproduce the effect it exists to measure ⇒ no contrast is interpretable |
| **4 STRONG** | `r <= 0.333` | drift accounted for **most** of the live-path loss. The fix is validated on the live path |
| **5 PARTIAL** | `0.333 < r <= 0.667` | drift accounted for **part** of it. A second pre-decoder mechanism stands, and is comparable in size |
| **6 NULL** | `r > 0.667` | the live-path loss is **largely not drift**. Escalate — a named second mechanism becomes the priority |

**Report the row verbatim, VOID included. Do not reinterpret, do not tune a threshold after seeing
a number, do not run arm B first.** Run arm A first: if it VOIDs on rows 2 or 3 there is no point
running arm B at all.

## 4. Mandatory self-checks, before any analysis

1. **Contiguity and epoch structure of both corpora**, from daemon log boundaries (not gaps —
   a supervisor cooldown is shorter than the 300 s fallback and would merge two epochs). Arm B is
   known to be two epochs, 1.76 h + 18.96 h.
2. **Drift screen both corpora** and report both rows. Arm A is expected ROW 2 FAIL (known:
   −47.3/−48.6/−47.7 ppm), arm B is known ROW 5 PASS. This is row 2's input and doubles as an
   instrument check.
3. **Normalise hashed callsigns** before matching. §8 of the PASS report measured this at
   1.55 pts (57.11% → 58.66%) — real, small, and it must not be left in.
4. **Grid alignment control** — confirm a ±1 cycle tolerance recovers zero additional matches, as
   it did on arm B's corpus. If it recovers matches on arm A, say so; that is drift showing up in
   the labels and it changes how the miss set is built.
5. **Report the Isolated/Tight classification counts per arm.** If the class balance differs
   materially between arms, the contrast is confounded and I need to know before you compute `r`.

## 5. Constraints that bound what this may use

- **`jt9` offline is NOT a reference leg.** The live WSJT-X instance is the reference, and replay
  runs through OpenWSFZ's own decode path. If the harness reaches for `jt9`, stop and escalate —
  it overshoots both real-time decoders (+11.2% / +93.8%) and emits duplicate `(ts, message)` pairs.
- **WSJT-X is a co-appraiser, not an oracle.** Its own within-appraiser repeatability is 86.9–93.0%
  on bit-identical audio, so the "live miss" set contains WSJT-X's own noise. That is acceptable
  here **only because it applies equally to both arms and cancels in `r`** — it does not license
  citing either arm's absolute recovery rate as a clean figure.
- **The harness is on `main`** at `qa/rr-study/results/2026-07-23-d9ab692-d001-isolated-pipeline-diagnosis/`
  (`run_isolated_replay.py`, `materialise_isolated_sample.py`, committed `0726bd6`). **I have not
  read it.** Confirm it runs unmodified against both corpora before trusting it; if it needs
  changes to accept a corpus path, that is expected (every prior drift script hardcoded its corpus)
  — **disclose any change, and make it before pre-registering, not after.**
- **No `src/` change.** If the replay needs a rebuild, it is the *current* `main` build for both
  arms, and both arms must use the same binary. Record the commit hash in the report.

## 6. What this does not decide

- **Not D-001.** §1 above. The baseline deficit and density penalty are untouched.
- **Not decoder quality.** A recovered decode is not a validated decode; there is still no oracle.
- **Not the settings-page stall**, and not the cap (already lifted, 2026-08-04).

## 7. Open item I am flagging rather than acting on

The Captain's instruction of 2026-08-04 was that **S.1 is already solved**. My record disagrees:
`2026-07-31-1730-architect-ruling-s1-void-upheld-estimator-defect-not-null.md` records **V1 "the
VOID stands, arm S.1 produced no reading"** and **V7 "nothing opens; S.1 fired no row"**, with the
corrected estimator **S.1b** designed at its §5 and marked *"needs the Captain"*. QA executed S.1
exactly and correctly; the defect was mine, in the estimator.

**This spec does not depend on S.1 either way** — it is listed here so the discrepancy is on the
record and not silently inherited. If something later resolved the frequency-local vs
cycle-global question by another route, that supersedes my note and I would like the pointer.
