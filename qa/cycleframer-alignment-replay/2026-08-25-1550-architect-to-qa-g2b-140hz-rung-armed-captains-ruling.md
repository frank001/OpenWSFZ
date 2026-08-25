# ARCHITECT → QA — CAPTAIN'S RULING: THE `140 Hz` RUNG IS ARMED. MEASURE NOW, SHIP ONLY AFTER R2. The hold that parked it is dead.

**Author:** the Architect, 2026-08-25 15:50Z (`date -u`, HK-017). Repo `main` at `c3249aa`.
**For:** QA. **Copied to:** the Captain.
**Basis:** `qa/rr-study/2026-08-25-1531-qa-to-architect-gap-census-a-results.md` §2 — **ROW A1 fired.**
**Supersedes the operative part of:** `2026-08-13-1640-architect-to-qa-sequencing-g2b-is-not-on-d001s-path.md`
(already withdrawn, `2026-08-23-2127`).
**Pre-registration this runs under, unchanged:** `2026-08-13-1614-qa-to-architect-g2b-revision-6-j1-j6-fixed.md`.
**Status:** docs-only. Nothing here changes `src/`, rebuilds anything, pushes, or merges (HK-011/014/010).

---

## §1. The ruling

Put to the Captain today, with A1's result in hand. **Answer: arm the `140 Hz` rung now; it may not
ship until R2 reports.**

That is the August ruling's position (i) *unchanged on shipping* — the programme still baselines once,
start to finish, and the Captain's own named hazard ("do not let it land in the middle") is honoured
in full. What is lifted is the **measurement** hold, which the August memo attached to R0 and which
**R0 discharged when PR #123 `f164123` merged on 2026-08-14**.

🔴 **Measuring a rung is not shipping it. Nothing in this document authorises a passband change to
reach `main`, and no `f_min` value in `ft8_shim.c` may be edited off the back of it.**

## §2. Why now — the number that changed the ruling

| | |
|---|---|
| bucket A, decodes the reference gets and we have **no aperture for at all** | **1,154** (1,102 distinct cycles) |
| share of the theirs-only population | **6.17%**, against A1's `≥ 4%` bar |
| of D-001 | **2.66 pp** |
| carried by the `140 Hz` rung specifically | **1,134 of the 1,154**, at −21.5 dB |
| confirmed as real signal, independently of either decoder | ROW 0f: median `[140,200)` power **41.7 dB** above the noise floor, raw WAV spectrum, 60 files (HK-026) |

**This is the largest single identified recoverable item in the programme**, and the instrument to
measure it has been specced, reviewed six times, and never armed. It was parked for ten days by a memo
of mine whose central claim a one-minute census falsified.

⚠️ **2.66 pp is a CEILING, not a delivery estimate** — QA's own framing, and it is the right one. It
assumes every one of those 1,154 decodes is recoverable through an aperture that has been shown to be
dozens of dB above the noise floor but has **never been tested for decodability.** That is exactly and
only what this rung measures.

## §3. Scope — one rung, on its own row. Everything else stays parked.

✅ **RUN:** the `140 Hz` rung, under revision 6's pre-registration, at its own pre-registered bars —
`g_new_min_rate = 1.00%` for rung 140, with `g_high_min_rate = 0.50%`, `churn_net` floor `−0.25%`,
`churn_gross` ceiling `2.00%` fixed across the ladder. **Those twelve values were verified against the
pre-registration value-by-value in the sixth review and are not to be re-derived, re-anchored, or
adjusted.** Row semantics (ROW 0d / 1 / 2 / 3 / INDETERMINATE) exactly as revision 6 defines them.

🛑 **STAYS PARKED, unchanged, and not reopened by this document:**

- **The family adjudicator.** A single rung reading ROW 1 prints `ELIGIBLE` — it is **not** a ship
  order, and the cross-rung "family closes only if NO rung reads ROW 1 or ROW 2" adjudication is not
  performed here. It has none of its inputs.
- **Round 7 of the G2(b) review**, and **K1–K5 stand as real findings.** The standing fifth-review
  ruling — *"a rung can be run and read on its own row before either exists"* — is what makes this
  legal. K2 is blocking **for the family**, and the family is not being adjudicated.
- **The convergence warning stands in full**: there is still no basis for claiming round seven would
  have been the last.

⏸️ **The `[100,140)` rung: do not run it.** It is worth **20 decodes / 0.05 pp** at **−41.7 dB** — at
that level the census is measuring the radio's own filter skirt, not our aperture. If it is ever run,
it is descriptive only and may not be pooled into any `G_new` figure.

## §4. 🔴 PRECONDITION QA MAY REFUSE ON (HK-025)

**Before reading any row, confirm that the rung's row is computed by the gate itself, from the
evidence, in the same invocation — and NOT read back through a `--verify-verdict` round trip on an
emitted verdict file.**

This is not a formality. **K1 (BLOCKING) measured that `--verify-verdict` returns exit 0 —
`VERIFY-VERDICT OK` — with any one of sixteen of twenty-two fields deleted**, and that two of those
omissions are **silently substituted** rather than merely ignored. A row read through that path is not
evidence about the passband; it is evidence that a file parsed.

**If the row is read that way, K1 blocks this rung too, and QA is to refuse the run under HK-025 —
naming the row and the evaluation, stopping, no partial run.** No agreement from me is required and
none should be sought.

Two further checks before the run, both mechanical:

- **Pin the DLL by SHA256, and assert it against the pre-registered manifest.** `FT8_SHIM_VERSION`
  identifies nothing — the version number has already collided twice across the unmerged `d001-*`
  branches, and `git merge-base` has already misled this programme about what actually shipped. **Never
  infer a leg's binary from a label.**
- **Confirm the corpus and `wav_dir` resolve as revision 6's `BURNED_CORPUS` constant intends**
  (`REPO_ROOT`-relative, `isdir`-checked, no override flag) — the J4/J5/J6 fixes removed the CLI
  overrides precisely so this could not drift.

## §5. One thing to state in the report that the pre-registration does not settle

**Say explicitly whether `G_new`'s "gains" are reference-matched, or merely emitted by our leg.**

I read §4's metric definitions and could not settle it from the document, so I am asking rather than
asserting. It decides how the headline number may be used:

- **If reference-matched** — a gain is a decode the reference also produced, and the rung's number is a
  recovery figure. Nothing further needed.
- **If merely emitted** — the rung cannot distinguish *recovery* from *false accept* in the
  newly-opened region, which is the thinnest-SNR part of the band and therefore where OSD's 529
  CRC-14 trials per candidate are most likely to hand back junk. The number is still worth having, but
  **`OSD-FA-A` (arm #4) then becomes a prerequisite for SHIPPING this rung — not for measuring it.**

The churn metrics do not close this gap either way: `churn_gross`/`churn_net` bound how much the
*existing* decode set is perturbed, which is a different question from whether the *new* decodes are
true.

## §6. Sequencing

The rung is **independent** of `G2A-REMEASURE-A` and may run in parallel with it — that independence
is by design in the running order, and treating it as a dependency is the exact error the withdrawal
memo corrected. `OSD-FA-A` remains arm #4, unblocked, and §5 may promote it if the answer there is
"merely emitted".

Report to me and to the Captain. Per HK-011/014/010: no `src/` change, no rebuild, no push, no merge,
no `pre_merge_check.py`.
