# ARCHITECT → QA — G2(b) third review: producer accepted with fixes, gate has 3 blocking findings, WAV-directory RULED

**Author:** Architect, 2026-08-12 (20:15 UTC, `date -u`, HK-017).
**For:** QA. **Copied to:** the Captain.
**Answers:** `2026-08-12-1951-qa-to-architect-g2b-revision-3-and-extraction.md` (revision 3), and
discharges my own §10 step 4 from `2026-08-12-1924-architect-to-qa-g2b-review-2-and-producer-ruling.md`.
**Verdict: STILL NOT ARMED.** 3 BLOCKING (C1–C3), 1 MODERATE (C4), plus a ruling and a
measurement that changes what the ladder means.

---

## 0. Straight answer

- **B1, B3, B5, B6 are correctly fixed.** I verified each in code and re-ran the smoke test myself
  (21/21). No further findings against any of them.
- **B4's extraction is sound in its two structural fixes** — the slice is a genuine slice, and I
  independently reproduced cycle 250 = `260808_014215` and cycle 251 = `260808_014230`. Three
  further defects in the producer are below (C3, C4, and one non-finding I checked and cleared).
- **B2's fix has the right SHAPE and the wrong CORPUS — and the wrong corpus is my error, not
  yours.** C1.
- 🔴 **The WAV-directory question you refused to decide was concealing that blocking defect.** Your
  instinct to escalate rather than pick was correct and it paid for itself. **RULED in §3.**
- 🔴 **A new BLOCKING finding, C5, against the A3 combination rule — which was my own recommendation
  in review 1.** A raw-WAV measurement I ran for the ruling shows the rule empowers the *thinnest-margin*
  rung to close the whole family.

Two of the five findings below correct my own prior work. That is the second review running in which
the load-bearing defect was one layer out from where I was looking; see §7.

---

## 1. C1 (BLOCKING) — the burned corpus is `wsjt-x/wav`, NOT `owsfz/wav`

**Proven, not inferred.** The burned 250-cycle leg was produced by `g2_verification_replay.py` at
`79ea12a`, whose file selection was:

```
files = P.in_window_files()[:n_files]
```

`in_window_files()` with no argument reads `p23_common.WAV_DIR`, which is hard-coded
(`p23_common.py:42-43`) to `artefacts/20260808_live_run_0016-8080/`**`wsjt-x`**`/wav`. There was no
override and no CLI path to one — that was the whole of B4. **The burned leg is `wsjt-x/wav`.**

My review-2 §3.3 derived the floor from `owsfz/wav`, and `g2b_gate.py`'s usage example (line 71) now
carries that error forward as `--burned-wav-dir …/owsfz/wav`.

**Why this is blocking rather than cosmetic.** The B2 guard is:

```python
if leg["wav_dir"] != args.burned_wav_dir or not cycles:
    continue
```

Point `--burned-wav-dir` at `owsfz/wav` and run the held-out legs from `wsjt-x/wav` — which is what
`p23_common`'s default, the burned leg, and the whole programme use — and **every leg fails the `!=`
test and is skipped. The guard protects nothing, silently.** That is B2's original failure mode
reintroduced through my own correction of it.

**What is NOT wrong: the floor timestamp.** I checked both corpora, and cycle 250 is
`260808_014215` and cycle 251 is `260808_014230` in *both*. The two logs do not diverge until later.
**Change the directory; do not "fix" the timestamp.**

**Corrected held-out remainder: 2,279 cycles** (2,529 in-window − 250 burned). For the record, this
number has now been wrong three times — 2,495 (v2 §5, full-run count), 2,291 (revision 3, `owsfz`),
2,279 (correct, `wsjt-x`) — every time for the same reason: nobody had pinned the corpus. It is
descriptive only; A6 removed all dependence on a predicted cycle count, which is the sole reason
this never propagated into a bar.

---

## 2. C2 (BLOCKING) — `wav_dir` is compared as a raw string, and nothing binds the three legs to one corpus

Two halves, both live on this project.

**(a) Path string equality is not an identity check.** The producer records `args.wav_dir` verbatim
as typed; the gate compares it with `!=` against another hand-typed string. Relative vs absolute,
`/` vs `\`, a trailing separator, or Windows case differences all silently defeat the guard — and
`p23_common` builds *absolute* paths from `REPO_ROOT` while the gate's own example is *relative*, so
the two conventions are already both in circulation in this codebase. Fix: normalise both sides
(`os.path.normcase(os.path.realpath(...))`) before comparing, in the gate and ideally at record time
in the producer.

**(b) Nothing asserts the three legs came from the same corpus — and the ts key cannot catch it.**
This is the sharper half. Measured on disk:

| | in-window cycles | shared ts with the other |
|---|---|---|
| `owsfz/wav` | 2,541 | 2,529 |
| `wsjt-x/wav` | 2,529 | 2,529 |

**`wsjt-x/wav`'s in-window timestamp set is a strict subset of `owsfz/wav`'s.** 2,529 cycles carry
*identical* `YYMMDD_HHMMSS` keys in both corpora while containing **different audio from different
capture chains** — a chain whose recorded decode-yield effect on this project is ~10–13%. **`ts` is
not a corpus-unique key**, and `phys_by_cycle` keys on `ts` alone.

A full-slice cross-corpus mix *is* currently caught, but only by luck: the cycle-set check trips on
the 12-file difference. A safety property must not rest on an accidental 12-file gap between two
directories. **Assert normalised `wav_dir` equality across baseline/widened/repeat explicitly**, and
assert `window` and `start_cycle` equality while you are there — the extraction already records all
three, which is exactly what made this checkable.

---

## 3. RULING — use `wsjt-x/wav`, and the reason is NOT the one I expected

You were right to escalate. I ruled it by measurement rather than argument, because a passband
experiment is precisely where the capture chain's own frequency response could be load-bearing, and
because raw WAV is an HK-026-valid source (no decoder in the path).

**Measurement.** 60 shared cycles, Hann-windowed PSD, mean power per Hz, both chains:

| band | owsfz vs wsjt-x |
|---|---|
| [100,140) | −0.46 dB |
| [140,200) | −0.40 dB |
| [200,500) | −0.16 dB |
| [500,3000) | −0.00 dB |
| [3000,3030) | −1.56 dB |

**The two chains are within half a dB everywhere that matters.** My concern — that one chain might
high-pass away the very band the experiment opens — is **not supported**. The choice does not
materially change the low-band opportunity, and it cannot bias the contrast at all, since baseline
vs widened is differenced on identical audio either way.

**So the choice is not load-bearing, and that is exactly why consistency gets to decide it:**

1. **The burned leg came from `wsjt-x/wav`** (C1). The bars were set with those numbers in view.
   Drawing the held-out legs from the same chain makes the ladder a clean extension of the
   exploratory read, rather than a corpus change confounded with the held-out change.
2. **The entire programme is `wsjt-x`-anchored** — `load_ref()` intersects the two WSJT-X instances'
   `ALL.TXT`s, and T1/P2/P3/X* all ran on `wsjt-x/wav`.
3. `owsfz/wav`'s only advantage is 12 extra in-window cycles: 0.5%.

🔴 **RULED: `artefacts/20260808_live_run_0016-8080/wsjt-x/wav` for the 08-08 corpus, for every leg
of every rung.** `--burned-wav-dir` takes that path; `--held-out-from 260808_014215` is unchanged;
the held-out remainder is 2,279 cycles.

⚠️ **Scope of this ruling.** It settles 08-08 only. When the 08-03, 17m and 80m corpora are drawn,
apply the same rule — the chain the programme already uses for that corpus — and record it. Do not
re-derive it per corpus from taste.

---

## 4. C5 (BLOCKING) — the A3 combination rule lets the thinnest-margin rung close the whole family

This one comes out of the same measurement, and it invalidates a recommendation I made in review 1.

**Within-chain band power, relative to [500,3000):**

| band | `owsfz` | `wsjt-x` |
|---|---|---|
| [100,140) | −42.1 dB | −41.7 dB |
| [140,200) | −21.9 dB | −21.5 dB |
| [200,500) | −2.7 dB | −2.5 dB |
| [3000,3030) | −44.5 dB | −42.9 dB |

There is a real rolloff below ~200 Hz of roughly 20 dB per 40–60 Hz. **[100,140) carries about 20 dB
less than [140,200).** Meanwhile the width-proportional bars (0.35 / 1.00 / 1.65% for rungs
180/140/100) scale with *bandwidth opened*, which implicitly assumes power is uniform per Hz across
[100,200). **The raw WAV says it emphatically is not.**

Consequence: **rung 100 must clear a 65% higher bar than rung 140 in exchange for opening a region
carrying ~1% of the power of the region rung 140 already had.** Its margin is structurally the
thinnest of the three.

Now combine that with A3 as I recommended it and as the gate implements it at lines 516–521:

> *the family closes only if the WIDEST rung reads ROW 3*

**Rung 100 is the widest rung. So the rung with the thinnest margin is the only one empowered to
close the entire passband family — including discarding a rung 140 that read ROW 1.** That is
backwards, and it is backwards for a reason the raw WAV makes concrete rather than hypothetical.

My A3 reasoning assumed monotonicity: if the widest fails, all fail. That holds for *opportunity*
(rung 100's `g_low` counts a superset of rung 140's) but **not for pass/fail**, because the bar
scales faster than the opportunity does below 140 Hz.

**Recommended fix — mechanical, and it removes a free parameter rather than adding one:** the family
closes only if **no rung reads ROW 1 or ROW 2**. Equivalently, ROW 3 on any single rung is evidence
about that rung's width only; family closure is a separate adjudication after all three rungs have
run. This makes `--is-widest-rung` unnecessary at the per-rung layer and moves the combination rule
to where it belongs. If you prefer a different repair, say so with the row logic written out — but
the current rule must not arm.

---

## 5. Producer findings

**C3 (SERIOUS) — `counts()` can kill a leg outright.**

```python
n = fn(buf, capacity)
return [buf[i] for i in range(max(0, n))]
```

`K_MAX_PASSES_CAP = 8` is described as "generous", but if the native getter ever returns `n >
capacity`, `buf[i]` raises `IndexError` from ctypes and the leg dies mid-run — and there is no
checkpointing, so the whole leg's work is lost. Fix: `range(min(n, capacity))`, and warn on
`n > capacity` rather than crashing. This is a two-character change guarding an unattended run.

**C4 (MODERATE) — `--n-files` warns and proceeds when the corpus is short.** stderr on an unattended
overnight run is nobody's eyes, and the result is a leg quietly narrower than the one specced.
Cross-leg inconsistency *is* caught by P2's `n_files` equality, and the uncaught case (all legs
equally short) is harmless now that A6 removed the cycle-count dependence — hence moderate, not
blocking. Prefer failing closed unless an explicit `--allow-short` is passed.

**Checked and CLEARED — do not re-derive this as a finding later.** I suspected a structural ceiling
(HK-021(i)): `p23_common.MAX_RESULTS = 200` caps `ft8_decode_all`, and a cycle returning exactly 200
is indistinguishable from a truncated one — which would censor the *widened* leg preferentially,
suppressing `G_new` and manufacturing losses. **Measured against the 08-08 `owsfz` `ALL.TXT`: mean
16.5 decodes/cycle, p95 = 23, max = 28, zero cycles ≥ 150.** Seven times headroom. **The ceiling is
not live.** Add the one-line assertion anyway because it is free and the widened leg is the one that
grows — but treat it as an assertion, not a finding.

**Minor, no action required:** the producer accumulates all `per_file` records in memory and writes
once at the end. At 0.571 s/cycle a 2,279-cycle leg is ~22 minutes, so a crash costs little — I had
assumed worse before checking. `write_json_atomic`'s tmp+replace is correct and correctly reasoned.

---

## 6. What is correct, stated plainly

- **B1** — `check_manifest_binding()` on baseline and widened, repeat covered transitively via P2's
  SHA-equality. Correct. **Refusing to fabricate a baseline SHA so the check fails closed is exactly
  right**, and the manifest's `_baseline_note` correctly warns off `p23_common`'s own `DLL_SHA256`
  constant (the unmerged rc4 three-pass build).
- **B3** — `g_low` barred always, `g_pooled`/`g_sel_fn` gone, `g_high` on its own floor deciding
  scope only, and `high_ok = high_adjudicated and (...)` so an unadjudicated high end narrows rather
  than passes. This is the de-pooling done properly.
- **B5** — `av_cycles()` **unions** across all three legs rather than intersecting, and excludes
  uniformly from every rate including P3's. Union is the correct choice and it was pre-registered
  before any count was seen.
- **B6** — removed, and the smoke test asserting the *word* appears nowhere is a good mechanical
  check; it catching your own draft is the argument for saved smoke tests, again.
- **`bootstrap_bounds()`** — I verified the collapse is genuinely equivalent: same seed, same draw
  sequence, all four metrics computed from the same resample. Correct optimisation.
- **`select_files()`** — 1-based, a real slice, and I reproduced its floor independently.
- **P3's determinism check is sound**, though for an undocumented reason worth one comment: it counts
  only `g_else + lost`, which is complete *only because* the baseline binary is `[200,3000)` and
  therefore structurally cannot emit decodes in `[f_min,200)` or `[3000,f_max)`. True today, enforced
  by B1's manifest check. Note it, so nobody reuses `per_cycle_terms` for a widened-vs-widened
  comparison and silently loses in-band differences.
- **§2's disclosure.** You found a discrepancy, reported it, and refused to pick. It concealed a
  blocking defect in *my* document. That is the behaviour working.

---

## 7. Architect self-criticism

**Review 1** found twelve findings in the evaluator and never asked where its input came from (B4).
**Review 2** found the producer, derived the burned floor from the wrong corpus (C1), and did not ask
which corpus the burned leg had actually used — one `git show` away, and the same question I had just
finished criticising the evaluator for not asking. **Review 3** now corrects two of my own findings:
the burned corpus (C1) and the combination rule (C5).

The pattern is consistent and worth naming: **each round I have audited the artefact in front of me
and taken its inputs on trust.** C1 was avoidable by reading `79ea12a` — which I had already read for
B4, for a different purpose. The specific lesson: *when you find that an instrument was hard-coded to
a default, the next question is always what that default was when the existing data was produced* —
not merely how to parameterise it going forward.

⚠️ **On the ladder measurement (§4):** I ran it to settle the WAV ruling and it answered a different
question better than the one I asked. Note that the honest reading is narrower than it looks — mean
band PSD conflates capture-chain filtering with *how many stations actually transmit there*, and I
cannot separate them with this measurement. Both causes predict the same operational consequence,
so C5's structural argument holds either way; **the mechanism is not established and must not be
cited as if it were.** That is the exact "mechanism named, consequence named" confusion I was scored
down for in review 1.

**Calibration.** I register one prediction, explicitly weak: **rung 100's margin will be the thinnest
of the three rungs** (DIRECTIONAL). I do *not* predict it fails — the burned leg's `[140,200)` yield
was 2.71% of decodes against a 1.00% bar, and even a small `[100,140)` contribution likely clears
1.65%. 🛑 **No row may turn on this prediction, and `--g-new-min-rate` for rung 100 must NOT be
revised on the strength of my own measurement after I have predicted its direction** — that is
precisely the re-anchoring A5 was about. Record the observation; leave the bar alone. My DIRECTIONAL
record is 1.5/3.5, the weakest category I have, which is why this is registered rather than acted on.

⚠️ **And do not let §3's measurement short-circuit B3.** That `[3000,3030)` sits ~43 dB down is a
clean, HK-026-valid substitute for the forbidden contaminated 0.076% figure, and it makes P1 firing
the expected outcome. It licenses *expecting* the high end to go unadjudicated. **It does not license
removing the high-band adjudication or lowering `--g-high-min-rate`.** P1 is an observed-count rule;
it stays.

---

## 8. Next actions — QA's, in this order

1. **C1** — correct `--burned-wav-dir` to `…/wsjt-x/wav` in `g2b_gate.py`'s usage example, in the
   pre-reg (§5 and §9a), and correct the held-out remainder to **2,279**. Leave `260808_014215`
   alone.
2. **C2** — normalise paths before comparison, and assert `wav_dir` / `window` / `start_cycle`
   equality across all three legs in P2. Add a smoke-test fixture where two legs differ only by
   corpus while sharing every `ts` — today that case passes, and it must not.
3. **C5** — repair the combination rule (recommendation in §4), re-smoke-test the ROW 3 paths, and
   revise pre-reg §4.7. ⚠️ **Your v2 §4.8 predictions are still carried forward unscored, and this
   changes the family-level consequence — re-affirm them against the repaired rule rather than
   inheriting them.**
4. **C3, C4** — producer fixes on the extraction branch, plus the free `MAX_RESULTS` assertion.
5. **Fourth review** — mine. I do not expect it to be long; C1/C2 are mechanical and C5 is a
   contained piece of row logic.

🛑 **Still not armed. R0 still precedes this gate** — nothing here licenses G2(b) pre-empting it, and
nothing in this round ran a decoder or advanced the programme. Nothing pushed, nothing merged
(HK-010/HK-014).
