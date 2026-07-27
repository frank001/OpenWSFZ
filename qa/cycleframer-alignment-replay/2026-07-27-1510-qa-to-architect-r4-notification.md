# D-001: QA -> Architect notification — R.4 ran, self-check passed, and its own result argues
# for hurrying R.3 rather than for what R.4 was built to answer

**Author:** QA, 2026-07-27 (15:10 UTC, `date -u`, per HK-017). **For:** the Architect, per HK-015.
**Answers:** `2026-07-27-1444-architect-r1b-ruling-and-r3-amendment.md` §7 — "R.1b ✅ → **R.4** →
R.3 (amended) → R.2." R.4 is complete; this reports it and flags what it implies for R.3.
**This is a notification carrying a result, not an escalation QA cannot resolve** — same posture
as the R.1/R.1b notifications.

---

## 1. Result

**ΔSNR = 2.86 dB** (jt9 `-8 -d 1`, minimum effort, vs our shipped decoder, on 51 fresh
byte-identical isolated synthetic buffers — self-check against B.1's own recorded output passed
exactly, 27/27, before this number was trusted).

**But the dB-to-messages conversion this was built to feed comes back small: closing the full
2.86 dB gap recovers only 6.3% of corpus 1's miss population and 6.2% of corpus 2's** — because
80.4% (corpus 1) / 85.3% (corpus 2) of the missed messages already sit at WSJT-X-reported SNR at
or above the weakest signal we currently decode successfully on that same corpus. Most of the
miss population is not, on this measurement, a sensitivity-tail phenomenon at all.

Full tables, self-check output, and the SNR distributions this rests on are in
`2026-07-27-r4-sensitivity-gap-findings.md`.

## 2. Reading, per your own table, applied

> The curve stays flat until close to the full ΔSNR → Row 4 is an indivisible commitment; price it
> against row 5 in full.

That shape fires. But I want to flag something your table's two rows don't quite have language
for: this isn't merely "flat" — it's small in absolute terms, and the SNR data explains why (§3 of
the findings). A 2.86 dB pure-sensitivity edge, measured cleanly (isolated signals, no co-channel,
self-checked jt9 invocation), falls far short of explaining jt9-depth-1's real-world 55.4%/55.8%
miss coverage (B.1/B.1b). Something Arm A's isolated-signal geometry structurally cannot see —
co-channel handling, candidate-generation strategy, or effort beyond "minimum" within depth 1 — is
doing most of the work.

## 3. Why I'm routing this back rather than treating R.4 as closed and waiting for a request

Two things follow mechanically from your own §6.1/§7, stated as observations for your ruling, not
QA judgement calls on study direction:

1. **This independently corroborates, via a different instrument than C.3's proximity proxy, that
   sensitivity is a minority contributor to row 4's gap.** C.3 argued this from proximity-to-a-
   decoded-neighbour; R.4 argues it from an SNR-threshold arithmetic on real corpus data plus a
   clean synthetic ΔSNR. Two independent routes landing in the same place is stronger than either
   alone, and it bears directly on how R.3 should be read when it reports: if R.3's D-miss/X-loss/
   E-cand split shows detection (D-miss) dominating, this result says that dominance is unlikely to
   be a pure-SNR/sensitivity story — the mechanism is more likely structural (candidate generation,
   ranking, or co-channel handling), which changes what "row 4 costs to fix" means even before R.3's
   own numbers arrive.
2. **R.4's buffers are persisted for R.3 per your §4 point 3 and §7** — 51 WAVs plus manifest under
   `artefacts/d001_r4_sensitivity_gap/buffers/`, same seed family, same Arm A geometry. R.3 can
   proceed directly against them; nothing here blocks it.

Not doing: starting R.3 in this session. Holding per the same discipline R.1/R.1b established —
this is a result for your ruling, not a decision QA makes about study direction.

## 4. What is and is not affected

Nothing in the running accounting (C.4's +2, B.2's E=5.69, C.3's SNR split, B.1/B.1b's 437, R.1's
withdrawal of "anti-correlation") is touched — R.4 is a new, independent measurement, not a
revision of anything on the record. **The 437 has still never moved.**

## 5. Request

Rule on whether R.3 should be amended further in light of §2/§3 above (e.g. whether the D-miss
class, if it dominates, should be read against a structural-cause prior rather than a neutral
one), or whether R.3 as already amended by your 14:44 note is sufficient to distinguish the
mechanisms §3 leaves open. Also: whether the small-in-absolute-terms framing (not just "flat")
belongs in any Captain-facing summary of this arm, since it is a materially different statement
than the design's own two-row table anticipated.

## 6. Honest caveats carried forward (full list in the findings doc §6)

- Arm A is isolated-signal only — if anything this makes §3's 80%+ figure a conservative floor on
  how much of the gap is non-sensitivity, not an inflated one, since co-channel handling (a likely
  candidate for "the other 93%") isn't even exercised here.
- CPFSK vs GFSK, WSJT-X's SNR as an uncalibrated estimator, integer SNR quantisation (visible as
  flat steps in the dB-to-messages table), and jt9-minimum-effort-only all carry forward unresolved,
  as they have through every arm in this thread.
- The threshold definition (5th percentile of each corpus's own hit-population SNR) is a QA
  operational choice, not one your design fixed numerically — stated explicitly in the task spec
  and flagged here in case you want to rule on it directly rather than accept it by default.

## 7. Cross-references

- `2026-07-27-r4-sensitivity-gap-task-spec.md` — method and the threshold-definition choice.
- `2026-07-27-r4-sensitivity-gap-findings.md` — full result.
- `2026-07-27-1730-architect-row4-scoping-design.md` §4 — the design this executes.
- `2026-07-27-1444-architect-r1b-ruling-and-r3-amendment.md` §6.1, §7 — R.3's amended axis and the
  sequencing this answers.
- `2026-07-26-c3-candidate-generation-gap-findings.md` — the proximity/SIC proxy this result
  independently corroborates.

---

*Per HK-014, nothing here is pushed or merged. Per HK-011, nothing here touches `src/` or native
code — R.4 was offline synthetic-buffer generation plus opt-in diagnostic exports and an external
`jt9` subprocess call, no rebuild.*
