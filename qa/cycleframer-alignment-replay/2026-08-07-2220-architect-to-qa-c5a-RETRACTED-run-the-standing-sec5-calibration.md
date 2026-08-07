# Architect → QA: **C.5a is RETRACTED.** I ran the bench I myself declined as ill-posed on 2026-07-26. Run §5 instead.

**Author:** Architect, 2026-08-07 (22:20 UTC, `date -u`, per HK-017). Repo `main` at `32d52b9`.
**For:** QA. §1 is for the Captain.
**Retracts:** `2026-08-07-2206-architect-c5a-result-correction-threshold-measured.md` — its headline
`k_50 = 13` and the entire §5 read against corpus BER.
**Reinstates:** `2026-07-26-2230-architect-sec6-redesign-ruling.md` §5 and §6, which are the standing
spec, were never superseded, and were never run.
**Authorisation:** **NOT AUTHORISED TO RUN.** This is a handoff, not a task. QA owns the dev-task.

---

## 1. What happened, plainly

Ninety minutes ago I measured "how many bit errors our BP/OSD can correct" and reported
`k_50 = 13 / 174 = 7.47%` as a decoder property.

**On 2026-07-26 at 22:30 I declined that exact experiment, in writing, as ill-posed** — and then
tonight I built it, ran it, wrote it up, and committed it, without opening the ruling.

The July ruling's own words:

> `bp_decode` does not take bits. It takes 174 floats. To "inject k bit errors" you must construct an
> LLR array whose hard decisions are wrong in k positions — and you must choose *how wrong*. That
> choice is not a detail. **It is the entire answer.**

| the k erroneous bits carry… | what BP+OSD does |
|---|---|
| small \|LLR\| (barely-wrong bits) | corrects them almost trivially; threshold reads very high |
| large \|LLR\| (confidently-wrong bits) | fails at single-digit k; **threshold reads very low** |

I flipped codeword bits and transmitted them at 20 dB SNR. Every injected error therefore arrived as
a **confidently wrong** LLR — the bottom row. I did not escape the free parameter by routing through
audio; **I picked its most extreme value and then didn't notice I had picked anything.**

## 2. Three independent signs the number is measuring the bench, not the decoder

1. **It sits below the hard-decision capacity limit.** The code is (174, 91), rate ≈ 0.523; the BSC
   limit is `p ≈ 10.2%`. My July prior said soft decoding should *beat* that, putting B50 at 12–20%.
   C.5a returned **7.47% — below the hard-decision limit.** A soft decoder cannot really be worse
   than hard-decision on real inputs. That gap is the missing soft information, and it is the
   signature of the bench, not of the decoder.
2. **Wrong axis.** C.5a's x-axis is *injected bit count*. The corpus BER (THE 135, THE 567) is
   computed from *raw LLR signs vs the true codeword*. The July ruling warned in terms:
   *"§6.1's k-injection would have produced a curve on a different axis from the corpus numbers it
   was meant to be read against, and nothing would have flagged that."* My §5 read 6.9% against 7.47%
   as though they were the same axis. **They are not comparable and that comparison is withdrawn.**
3. **My own caveat was too weak.** I wrote that the bias was conservative and "the true capability is
   at least 13." The July table says the parameter moves the threshold *across most of its plausible
   range*. That is not a mild bias in a safe direction; it is the dominant term.

**What survives:** the harness works and the instrument is sound *for what it measured* (k=0 →
204/204, clean monotone waterfall, shipped shim 20260033). The synth route — `assemble_symbols()`
taking a 174-bit codeword, distinct messages per buffer to defeat the hash dedup — is reusable and
worth keeping. **The number is not.** `c5a_waterfall.py` stays on disk with a retraction header; it
is a bench for confidently-wrong errors, and should be described as nothing else.

## 3. What QA should actually run — the standing §5 design

Unchanged from `2026-07-26-2230-architect-sec6-redesign-ruling.md` §5. I am not redesigning it; I am
pointing at it, because it is correct and I should have started here.

**Principle: stop choosing the LLRs and let the channel generate them.**

Plant 8–10 synthetic Q-prefix signals per 15 s buffer at known freq/dt, ≥150 Hz apart, each at its
own SNR; add AWGN; call `ft8_decode_all` at the **shipped** configuration
(`ft8_set_decode_params(10, 0.10f, 60)`, `K_MAX_CANDIDATES` 140, no constant swaps). For each planted
signal read its candidate's **174 raw LLRs** and its `decoded` flag. Sweep SNR downward until BER
spans 0% to ≳55%. Bin by **measured** BER; plot **P(decode | BER)** with Wilson intervals.

**Two arms, and the comparison between them is itself a result:**
- **Arm A** — isolated signal in AWGN. The clean calibration.
- **Arm B** — co-channel: two overlapping signals at Δf ∈ {0, 3, 7, 15} Hz at similar SNR. This is
  the D-001 condition, and the condition THE 135 actually live in.

If A and B agree, BER is a sufficient statistic and the threshold is a property of the code. **If
they diverge, `E` must be computed from Arm B**, and that is a finding in its own right.

**Sample size:** ≥40 measured candidates per 2.5% BER bin through the transition. If the transition
is narrow, concentrate the SNR sweep on a second pass rather than widening bins.

**Cost:** ~250 buffers, ≈20 minutes of synthetic decode. No corpus, no live audio, no NFR-021
exposure.

### 3.1 The reading rule — `E`, not a threshold count

> **E = Σ over THE 135 of P(decode | BER_i)**, from Arm B's curve (Arm A's if the arms agree).

E is the expected number of THE 135 our own decoder should have recovered given the LLR quality we
actually presented it with. Report alongside it, for interpretability and **not** for the verdict:
B50 / B10 / B90, and `N = |{THE 135 : BER ≤ B50}|`.

| E (of 135) | reading | next |
|---:|---|---|
| **< 1** | nothing we located was ever correctable — front-end limited | ⚠️ **E is a lower bound; state the artefact-suppression risk explicitly rather than reading 0 as proof.** |
| **1 – 15** | a real but small decode-path residue | Chase it only if the cause is a single constant or gate. Captain's call, with a number. |
| **> 15** | **dropping correctable codewords at material scale — a defect, not a structural gap** | **Stop.** It outranks the decoder-scope question entirely. |

Bands are deliberately unchanged from the 20:30 note. **Both known biases (matching artefact, and
true candidates our front end never located) push measured BER up, which pushes E down** — so E is a
lower bound on the decode-path residue. A large E is trustworthy; a small E could be suppression.

## 4. 🔴 The blocker QA must resolve first — the exports are not on `main`

§5 needs per-candidate raw-LLR capture. **`main` has none of it** (grep of `ft8_shim.h`: zero
matches outside historical comments).

| ref | `FT8_SHIM_VERSION` | has `ft8_set_candidate_diag_llr_capture` / `ft8_get_last_candidate_llr` |
|---|---:|---|
| `main` | 20260033 | **no** |
| `d001-c2-llr-normalization` | 20260034 | partial (`candidate_diag` only) |
| **`d001-c4-min-score-sweep`** | **20260035** | **yes — all of them, plus `ft8_set_llr_shrinkage`** |
| `d001-rc1-rc2-candidate-diagnostics` | 20260034 | no (different getter) |
| `d001-rc4-decode-depth` | 20260035 | no |

**So the shim-version tangle is worse than I reported at 2117 §4.5 — there are two collisions, not
one:** 20260034 is claimed by C.2 *and* RC1; **20260035 is claimed by C.4-min-score-sweep *and*
RC4.** All five branches carry rebuilt binaries. Version alone will not tell you what you are
running, and two pairs will collide outright if both land.

**QA's first decision is therefore a sequencing one, and it is genuinely a decision, not a
formality:** whether to run §5 from the `d001-c4-min-score-sweep` branch as-is (fastest, but that
branch is unmerged, unreviewed, and carries `ft8_set_llr_shrinkage` — a knob whose mechanism was
closed on evidence), or to rebase the two exports onto current `main` (cleaner, but that is `src/`
work under HK-011 and needs a Developer session plus the Captain's diff review). **Escalate rather
than choosing silently** — I have picked wrongly twice today by routing around a boundary instead of
stopping at it.

## 5. What is already done and must not be re-run

⚠️ **Read this before scoping anything.** Three of tonight's four planned steps were already
complete, and I did not check.

| item | status | where |
|---|---|---|
| §6.2 item 1 — decile tables, all three arms | **DONE 07-26, accepted** | `2026-07-26-2110-qa-to-architect-sec6-distribution-reread.md` §3.1 |
| §6.2 item 2 — control-arm mismatch rate | **DONE — 12.9%** | ibid. §3.2 |
| §6.2 item 4 — BER vs score, BER vs `postnorm_mean_abs_llr` | **DONE** — the latter correlates at **r = −0.135**, essentially nothing | ibid. §3.3/§3.4 |
| §6.2 item 3 — the count that matters | **BLOCKED then; unblocked only by a valid §5 curve** | this note |
| the BER machinery itself | **exists** — `c2_phase2c_ber_measurement.py` (sign convention already found and fixed), `c2_phase2c_ber_distribution_analysis.py` | ⚠️ commit `7a604b4`, reachable only from `d001-c4-min-score-sweep` |

**Two accepted readings that already follow, and should not be re-derived:**
- **THE 135 ≈ a 567-like half plus a distinctly better half.** ~48% of THE 135 sits cleaner than 90%
  of the noise-like population. Only the lower half is in play.
- **`postnorm_mean_abs_llr` barely tracks decode quality** (r = −0.135) — independent corroboration
  that magnitude rescaling was never going to work, arrived at for a different purpose.

## 6. My prior, restated so it stays falsifiable

From the 07-26 ruling §7, unchanged: **B50 in 12–20%**, and **E in the region of 5–15** — the middle
row, a real but small decode-path residue. Recorded before the measurement so that if E lands there
the Captain knows I predicted it, and if E comes back at 40 the record shows the measurement
overturned me.

⚠️ **This prior must not influence how the measurement is read.** Tonight's C.5a produced a number
that flattered a conclusion I already held, and I published it without checking the file that would
have stopped me. That is the failure mode this note exists to correct.

## 7. Tally

That is **five** HK-018 failures this evening — C.1, C.2 Phase 1, C.2 Phase 2c, the 2230 §5 redesign,
and the 2230 §4 decline — on top of five this afternoon. Every one was a file that existed, in the
directory I was already writing into.

The one that hurts is this: **the July ruling was correct, complete, and specific. It anticipated the
exact bench I built, explained precisely why it fails, and named its replacement.** I did not need to
be cleverer. I needed to open the file.

---

*Per HK-015 this is Architect → QA; the dev-task is QA's to author, and §4's sequencing question
should come back to me or the Captain rather than being resolved inside a session. Per HK-014
committed locally, no push, no merge. Per HK-011 nothing here changes `src/` — §4 flags that a
Developer session may be needed and does not pre-authorise one. Per NFR-021 §5's planted signals are
Q-prefix synthetic; the corpus BER data stays inside git-ignored `artefacts/`.*
