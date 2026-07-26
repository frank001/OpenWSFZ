# Developer handoff: D-001 C.2 — is LDPC survival collapsing because of LLR normalisation?

**Authored by:** QA (per HK-000/HK-015). **Status:** ready for a Developer session. Needs native
changes (a new per-candidate diagnostic export, and — only if Phase 1 supports it — a
normalisation-scheme change), so this is HK-011 work — not QA-only.
**Source:** `qa/cycleframer-alignment-replay/2026-07-26-0015-d001-consolidation-and-clean-slate.md`
§3 and §6.2, refined by C.1's result
(`qa/cycleframer-alignment-replay/2026-07-26-c1-candidate-cap-sweep-findings.md`): raising
`K_MAX_CANDIDATES` recovered only +12 decodes (1.6% of the decoder-attributable gap) and the
extra candidates found beyond 140 were overwhelmingly low-confidence noise. **98.4% of the
740-decode decoder-attributable gap (≈728 decodes) is untouched by the candidate cap and routes
here.**

---

## 1. Why this is the right experiment now

D-001's gap is fully decomposed and everything except one thread is closed by direct measurement
(consolidation doc §1–§2): capture chain 0.5%, live path 0.9%, decoder 98.5%. Within the decoder
share, C.1 just closed the "are we truncating the candidate list" sub-question — we are not,
materially. What's left is the other half of the consolidation doc's §3 split:

> Candidate yield is *identical* on cycles that decode 22 messages and cycles that decode none
> (median 140, p90 140, both populations). What varies is **survival**: `failCands` 82 → 136 as
> decodes collapse, `meanAbsLLR` 4.075 → 3.83, `prenormVar` 116 → 91.

So the decoder is finding the same candidates on good and bad cycles, and then failing to decode
a growing fraction of them as sessions/deciles get harder. That is an LDPC survival question, not
a candidate-generation question, and the two numbers that move with it — `meanAbsLLR` and
`prenormVar` — both come from one specific piece of code: the LLR normalisation step.

## 2. Where this lives in code

- **`ftx_normalize_logl`** — `native/ft8_lib_build/patched/ft8/decode.c:380-399`. For every
  candidate, computes the raw sample variance of its 174-bit log-likelihood array (`log174`),
  then rescales the *entire* array by `norm_factor = sqrt(24.0f / variance)` so the
  post-normalisation variance is always exactly 24 — regardless of how strong or noisy the raw
  signal actually was. This runs identically before every `bp_decode` attempt (decode.c:638,
  25→50-iteration belief propagation) and again before OSD if BP fails.
- **`ftx_compute_candidate_llr_stats`** — decode.c ~752-808 (doc comment at 752). Computes
  pre-normalisation variance and post-normalisation mean\|LLR\| for a single candidate. Currently
  called *only* for candidates that already failed to decode
  (`src/OpenWSFZ.Ft8/Native/ft8_shim.c:1321-1332`), and only summed into **per-pass aggregate
  totals** (`tls_llr_mean_abs_sum`, `tls_llr_prenorm_var_sum`, `tls_llr_fail_count`). There is no
  per-candidate, per-frequency record today — the consolidation doc's numbers are decile
  aggregates over an 11h51m live session, not "this specific missed message had LLR X." That is
  the gap Phase 1 below closes.
- **`bp_decode`** vs the disabled `ldpc_decode` (decode.c:638-639, commented out) — confirm which
  belief-propagation variant is actually linked, and whether its convergence behaviour has any
  documented sensitivity to LLR magnitude that would corroborate or rule out the hypothesis below
  before spending time on it.
- Managed-side exposure for reference: `Ft8Decoder.cs:411-421` (per-pass log line),
  `Ft8LibInterop.cs:344-554` (`GetLastLlrStats` P/Invoke).

## 3. The concrete hypothesis

`ftx_normalize_logl`'s fixed-target-variance scheme (`sqrt(24/variance)`) forces every candidate's
LLR distribution to the same post-normalisation variance, using only that candidate's own 174-value
sample variance as the scale estimate. Two non-exclusive readings:

- **(a) Estimator noise:** for weak or co-channel candidates, a 174-sample variance is a genuinely
  noisy estimate of the true underlying noise power. A bad estimate produces a bad `norm_factor`,
  over- or under-scaling the LLRs relative to what `bp_decode`'s iteration count was tuned against
  — independent of whether the candidate is, in principle, decodable.
- **(b) Wrong target constant:** `24.0` may not be the right target variance for this pipeline's
  specific candidate-generation/extraction path (AP-constrained decode, dual-pass, this codebase's
  own `ftx_find_candidates` scoring), even if the estimator itself were noise-free.

**This is a hypothesis, not a finding.** Falling `meanAbsLLR`/`prenormVar` on bad deciles is a
correlation observed at the aggregate level; it has not yet been shown that the *specific*
messages WSJT-X decoded and we didn't are the ones with weak normalised LLR, as opposed to being
uniformly low-quality candidates that were never going to decode by any normalisation scheme.
Phase 1 exists to tell those apart.

## 4. Method — diagnostic first, fix attempt only if it's warranted

### Phase 1 — per-candidate diagnostic (does the correlation hold at the message level?)

1. Extend the native diagnostic surface so **every pass-0 candidate** (not just failing ones) can
   report: frequency, time offset (`dt`), sync score, decoded/not-decoded, pre-normalisation
   variance, and post-normalisation mean\|LLR\| — mirroring what
   `ftx_compute_candidate_llr_stats` already computes, but recorded per-candidate instead of
   summed into a pass total. Surface this via the harness's existing opt-in `--debug-log` path
   (added in C.1, `qa/rr-study/d001-param-sweep-2026-07-22/Program.cs` — reuse rather than
   inventing a second logging path) or a new dedicated CSV, whichever is the smaller diff.
2. Re-decode the same fixed 68-cycle corpus used throughout D-001
   (`artefacts/20260725_live_run_1806/wsjt-x/wav/`, filename-matched intersection, `k10_c0.10_n60`)
   with this instrumentation on.
3. For each cycle, identify the **matched-missed set**: messages present in WSJT-X's `ALL.TXT` for
   that cycle but absent from ours. Match by frequency (± a few Hz — FT8 tone spacing is ~5.86 Hz,
   pick a tolerance and record it) and approximate time, since message text isn't available for a
   candidate that failed to decode. `score_recall.py`'s existing message-text matching logic is the
   right model to adapt (same repo, same corpus, same join-key discipline) even though this needs
   frequency-based matching instead.
4. For the matched-missed set, compare pre-norm variance and post-norm mean\|LLR\| against a
   control population — candidates on the *same cycles* that **did** decode successfully, at
   comparable sync score. This is the actual test: does the LLR-normalisation hypothesis predict
   the specific messages we're missing, or is it just aggregate noise?

### Phase 2 — fix attempt (only if Phase 1 shows the correlation holds at message level)

If matched-missed candidates show systematically weaker/more erratic normalised LLR than
successfully-decoded candidates at comparable score: try an alternative normalisation — e.g. a
clamped/floored variance estimate, or scaling against a cycle- or session-level noise-floor
estimate instead of each candidate's own 174-sample variance — and re-run the same 68-cycle corpus
decode count, exactly like C.1's before/after comparison. Report the delta the same way C.1 did
(total decodes, `failCands`, `meanAbsLLR`, elapsed time against the 15s budget).

**Do not attempt Phase 2 before Phase 1 reports.** Changing the normalisation scheme without first
confirming it's the actual discriminator between hit and miss is exactly the kind of speculative
`src/` change this project has been trying to avoid (see C.1's own stack-safety-fix discipline —
verify before trusting, verify again before shipping).

## 5. Decisive interpretation

- **Phase 1 confirms the correlation** (matched-missed candidates show weaker/more erratic
  normalised LLR than matched-hit candidates at comparable score) ⇒ proceed to Phase 2; a fix here
  has a real shot at recovering a meaningful slice of the 728.
- **Phase 1 finds no systematic difference** (missed candidates look like ordinary low-score/
  low-SNR candidates, no different from ones that also fail on cycles with plenty of headroom) ⇒
  the LLR-normalisation hypothesis is falsified as the primary mechanism. Do not proceed to
  Phase 2. Escalate to the consolidation doc's §6.3 (structural comparison against WSJT-X — more
  decode passes, successive interference cancellation, a-priori decoding) as a Captain-level
  product decision, not a further bug hunt.

Either outcome is decisive, which is why Phase 1 goes first and alone.

## 6. Definition of done

- [ ] Per-candidate diagnostic export added (native + harness), producing frequency/dt/score/
      decoded/prenorm-var/post-norm-mean\|LLR\| for every pass-0 candidate on the 68-cycle corpus.
- [ ] Matched-missed set computed per cycle against WSJT-X's `ALL.TXT`, with the frequency-match
      tolerance used recorded explicitly.
- [ ] Matched-missed vs. matched-hit LLR comparison reported, controlling for sync score.
- [ ] A written verdict: hypothesis supported or falsified, per §5's criteria — not left
      ambiguous.
- [ ] If Phase 2 was warranted and run: before/after decode counts, `failCands`, `meanAbsLLR`,
      elapsed time vs. the 15s budget, same reporting shape as
      `2026-07-26-c1-candidate-cap-sweep-findings.md`.
- [ ] Any deviation from this spec recorded in the findings doc's own "Done (deviation recorded)"
      annotation, per project convention.
- [ ] `python3 tools/pre_merge_check.py` green (HK-006) before any "ready" claim.
- [ ] `git status` clean of any rebuilt `libft8.dll` unless a normalisation change is actually
      being shipped, with its own explicit Captain sign-off (HK-010/HK-011).

## 7. Cross-references

- `qa/cycleframer-alignment-replay/2026-07-26-0015-d001-consolidation-and-clean-slate.md` §3, §6.2
  — the finding and framing this executes.
- `qa/cycleframer-alignment-replay/2026-07-26-c1-candidate-cap-sweep-findings.md` — C.1, the
  sibling experiment this follows; establishes that the candidate cap is not the constraint.
- `dev-tasks/2026-07-26-d001-candidate-cap-sweep.md` — C.1's own dev-task, same house style.
- `native/ft8_lib_build/patched/ft8/decode.c:380-399` (`ftx_normalize_logl`), `:752-808`
  (`ftx_compute_candidate_llr_stats`) — the code this investigates.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c:1321-1332` — current (aggregate-only) exposure of LLR fail
  stats.
- `qa/cycleframer-alignment-replay/score_recall.py` — message-matching logic to adapt for
  frequency-based matching of failed candidates.
- Consolidation doc §6.3 — the fallback avenue (structural WSJT-X comparison) if this is
  falsified.
