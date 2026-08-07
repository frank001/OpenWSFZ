# Architect → QA: consolidated work queue — everything from the 2026-08-07 evening session, in one place

**Author:** Architect, 2026-08-07 (22:41 UTC, `date -u`, per HK-017). Repo `main` at `856352d`,
20 commits ahead of `origin/main`, all local (HK-014).
**For:** QA. §0 and §6 are for the Captain.
**Replaces as the entry point:** the four documents this session produced (2117, 2140, 2206, 2220).
They remain the evidence; **this is the index and the queue.** Where they disagree with this, this
wins — 2206 in particular is **retracted**.
**Authorisation:** **NOTHING BELOW IS AUTHORISED TO RUN.** Per HK-015 the `dev-tasks/*.md` are
QA's to author; this is the Architect's handoff, not a task file. W1's blocker is an **escalation**,
not a decision for a session to make.

---

## 0. Read this before anything else — two withdrawn claims

| claim | status |
|---|---|
| **`k_50 = 13/174 = 7.47%`** — "our BP/OSD correction threshold" | 🛑 **RETRACTED.** Not a decoder property. **Do not cite, do not build on.** §1.1 |
| **`c_bottom = 0.476%`** — "bottom-decile candidates barely convert, so RC3 displaces nothing" | 🛑 **ROW 0, no verdict.** The data cannot identify which candidate decoded. **Not evidence for or against RC3.** §5 |

Both were Architect errors, published and then withdrawn within the same session. Neither reflects
anything QA or the Developer did.

---

## 1. Where D-001 actually stands

**RC1 fired ROW 2.** Of 894 pooled misses: **3.1% out-of-band** (known, unrelated defect),
**8.9% no-candidate**, **87.9% candidate-present-and-failed**. In 9 of 10 misses we located the
signal and failed to read it. Cite the decomposition, never "40% unexplained."

| arm | status | why |
|---|---|---|
| RC1 candidate generation | **CLOSED** | ROW 2, `f_nocand = 0.0924`, uniform across every stratum |
| RC2 candidate budget | **CLOSED twice** | excluded by RC1; already bounded at **+0.93%** by C.1 in July |
| RC4 decode depth | **CLOSED** | ROW 2, `d = +0.70` pp |
| C.2 Phase 2 LLR shrinkage | **CLOSED on evidence** | 0/135 recovered at every weight; harm rose 0/0/1/2/5 |
| RC3 search band | **deferred** | worth **3.1%**; its objection is unresolved, see §5 |
| **the §5 calibration** | **NEVER RUN** | specified 2026-07-26, still the standing spec — **this is W1** |

### 1.1 Why C.5a is retracted

`2026-07-26-2230-architect-sec6-redesign-ruling.md` §4 declined that exact bench as **ill-posed**
three weeks before I built it. `bp_decode` takes 174 floats, not bits — so "inject k bit errors"
forces a choice of *how wrong* each bit is, and **that choice is the answer**. Transmitting a
corrupted codeword at 20 dB SNR silently pins it at "confidently wrong," the extreme its own table
says makes the threshold read very low.

Three tells: it landed **below** the (174,91) hard-decision capacity limit of **10.2%**, which a soft
decoder cannot really be; its x-axis (injected bit count) is **not** the corpus BER axis (raw LLR
signs vs true codeword); and the caveat was written but priced as mild when it is dominant.

**What survives and is reusable:** `qa/rr-study/synth`'s `assemble_symbols()` takes a **174-bit
codeword**, so `codeword → tones → GFSK → ft8_decode_all` drives the real decoder with no native
change. ⚠️ **Distinct messages per buffer are mandatory** — the hash dedup at `ft8_shim.c:1387`
silently collapses repeats and every duplicate reads as a failure.

---

## 2. W1 — the §5 calibration 🔴 **the only thing that matters this week**

**Goal:** measure `P(decode | measured BER)` for our own decoder, so every BER reading in this
project stops being read against a number the Architect invented.

**Principle: stop choosing the LLRs and let the channel generate them.**

**Method** (unchanged from `2026-07-26-2230-…` §5; I am pointing at it, not redesigning it):

1. Plant 8–10 synthetic **Q-prefix** signals per 15 s buffer at known freq/dt, **≥150 Hz apart**,
   each at its own SNR. Add AWGN.
2. Decode with `ft8_decode_all` at the **shipped** configuration —
   `ft8_set_decode_params(10, 0.10f, 60)`, `K_MAX_CANDIDATES` 140, **no constant swaps**.
3. For each planted signal read its candidate's **174 raw LLRs** and its `decoded` flag.
4. Sweep SNR downward until BER spans **0% to ≳55%**.
5. Bin by **measured** BER; plot `P(decode | BER)` with Wilson intervals.

**Two arms — the comparison between them is itself a result:**
- **Arm A** — isolated signal in AWGN. The clean calibration.
- **Arm B** — co-channel: two overlapping signals at **Δf ∈ {0, 3, 7, 15} Hz** at similar SNR. This
  is the D-001 condition and the one THE 135 actually live in.
- **If A and B diverge, compute `E` from Arm B** — and say so loudly, because it would mean BER is
  not a sufficient statistic for correctability and every band framing in this thread is keyed on the
  wrong axis.

**Sample size:** ≥40 measured candidates per 2.5% BER bin **through the transition region**. If the
transition proves narrow, concentrate a second SNR pass there rather than widening bins.

**Cost:** ~250 buffers, ≈20 min of synthetic decode. No corpus, no live audio, no NFR-021 exposure.

### 2.1 Reading rule — pre-registered, `E`, not a threshold count

> **`E = Σ over THE 135 of P(decode | BER_i)`** — the expected number of THE 135 our own decoder
> should have recovered, given the LLR quality we actually presented it with.

| `E` (of 135) | reading | consequence |
|---:|---|---|
| **< 1** | nothing we located was ever correctable — front-end limited | ⚠️ **E is a LOWER bound. State the artefact-suppression risk explicitly; do not read 0 as proof.** The decoder-scope question goes to the Captain with `N` as its denominator. |
| **1 – 15** | a real but small decode-path residue | Chase only if the cause is a single constant or gate. Captain's call, **with a number**. |
| **> 15** | **dropping correctable codewords at material scale** | 🛑 **STOP. This is a defect, not a structural gap, and it outranks everything else on the D-001 board.** Re-decompose around it. |

Report alongside, **for interpretability and not for the verdict**: B50 / B10 / B90 from the curve,
and `N = |{THE 135 : BER ≤ B50}|`.

**Why `E` and not a count below a threshold:** a mismatched candidate reads ≈50% BER where
`P(decode) ≈ 0`, so it contributes ≈0 to `E`. The ≥12.9% contamination QA measured is concentrated
exactly where `E` is insensitive. Both known biases push measured BER *up*, which pushes `E` *down* —
so a large `E` is trustworthy and a small `E` could be suppression.

**Architect's prior, on record so it can be falsified:** B50 in **12–20%**, `E` in **5–15** (middle
row). ⚠️ **This must not influence how the measurement is read.** C.5a produced a number that
flattered a conclusion I already held and I published it without checking; that is the failure this
queue exists to avoid repeating.

### 2.2 🔴 W1 is BLOCKED — escalate, do not route around it

**The per-candidate raw-LLR exports are not on `main`.**

| ref | `FT8_SHIM_VERSION` | raw-LLR capture |
|---|---:|---|
| `main` | 20260033 | **none** |
| `d001-c2-llr-normalization` | **20260034** | partial (`candidate_diag` only) |
| `d001-rc1-rc2-candidate-diagnostics` | **20260034** | no (different getter) |
| **`d001-c4-min-score-sweep`** | **20260035** | **all of it, + `ft8_set_llr_shrinkage`** |
| `d001-rc4-decode-depth` | **20260035** | no |

**The decision — genuinely a decision, not a formality:**
- **(a)** run W1 from `d001-c4-min-score-sweep` as-is — fastest, but that branch is unmerged,
  unreviewed, and carries `ft8_set_llr_shrinkage`, a knob whose mechanism was closed on evidence; or
- **(b)** rebase the two exports onto current `main` — cleaner, but that is `src/` work under HK-011
  and needs a Developer session plus the Captain's diff review.

**Escalate this to the Architect or the Captain. Do not settle it inside a session.** Routing around
a boundary instead of stopping at it is what produced §1.1 — and when QA hit this exact boundary in
July, stopping and asking was the correct call and caught a defect.

### 2.3 ⚠️ Do NOT re-run — already done 2026-07-26 and accepted

| item | result |
|---|---|
| decile tables, all three arms | **done** |
| control-arm mismatch rate | **done — 12.9%** |
| BER vs sync score, BER vs `postnorm_mean_abs_llr` | **done — r = −0.135**, essentially nothing |

Only **item 3** (the count that matters) was ever blocked, and only on the missing curve.

**Machinery already exists:** `c2_phase2c_ber_measurement.py` (sign convention already found and
fixed — do not re-derive it) and `c2_phase2c_ber_distribution_analysis.py`, at commit `7a604b4`,
⚠️ **reachable only from `d001-c4-min-score-sweep`**.

**Two accepted readings — do not re-derive:** **THE 135 ≈ a 567-like half plus a distinctly better
half** (~48% sits cleaner than 90% of the noise-like population) — only the lower half is in play;
and **mismatch inflates BER toward 50% and never down**, so the low tail is artefact-proof while THE
567's truncation biases it optimistically.

---

## 3. W2 — `FT8_SHIM_VERSION` collides twice ⚠️ merge hazard, independent of D-001

Six unmerged `d001-*` branches, each carrying a rebuilt `libft8.dll`, and **two version collisions**
(table in §2.2). **Version alone will not tell you which binary you are running**, and two pairs
collide outright if both land.

⚠️ **`d001-c1-candidate-cap-sweep` is not an ancestor of `main`, yet its `K_MAX_CANDIDATES_ANY_PASS`
fix *is* on `main`** — it landed by squash. `git merge-base` will mislead about what shipped. Per
HK-003, verify individually before deleting any of these branches.

**Ask:** an audit and a proposed renumbering, reported up. No pushing, no merging.

---

## 4. W3 — HK-016 widening (approved 2026-08-07, never started)

Widen the live-run artefact-gather standard. **No preconditions** — the NFR-021 concern I attached to
it was withdrawn (`artefacts/` is blanket-gitignored at `.gitignore:105`, 0 tracked files). Small,
approved, unstarted.

---

## 5. W4 — RC3 is deferred, and the cheap route to unblocking it does not exist

C.5c tried to settle RC3's displacement objection from RC1's retained `_work/` and returned **ROW 0**:
`c_bottom` reads **0.476%** under one attribution policy and **36.5%** under the other, with the top
decile *inverting* (83.7% vs 0.36%).

**Root cause:** `candidate_lists.json` records which candidates **existed**, not which one
**decoded** — RC1's getter runs before any LDPC attempt, correctly. A median of **4** candidates sits
within tolerance of every decode. No matching rule over frequency and timing can recover the link.

**Consequence:** answering RC3's objection needs a **per-decode originating-candidate index** — a
`src/` change. **It is worth 3.1% and must not jump ahead of W1**, which bears on the 87.9%.
Not scoped here.

---

## 6. For the Captain — decisions, not QA work

- **RC4 branch** — recommend **reverting `K_MAX_PASSES` to 2** (a third pass costs CPU inside a 15 s
  budget and `K_MAX_DECODED` 340→540 for a measured no-effect) but **landing the test fix** that
  removes a hardcoded two-pass literal, broken twice now (20260007, 20260035).
- **D-009 Option B (`osd_nhard_max` 60→40)** — recommend **HOLD**. Its "after RC2" sequencing is
  void, and it makes OSD **shallower** at exactly the stage RC1 localised. Fairly stated: recall tied
  exactly (`recall_dpp = 0.000`), but on synthetic arms only, never the live window.
- **RC1 and RC4 branches** both await HK-011 pre-push diff review. **`main` is 20 commits ahead of
  `origin/main`, all local.**

---

## 7. Lower priority — carried, not queued

- **Mechanism 1 (~34%) needs a low-density WINDOW**, not just a reference — the replay corpus is the
  busiest by construction. ⚠️ **Open `qa/ARTEFACT_INVENTORY.md` before proposing anything.**
- **The 60-signal `co_channel_sweep` subset** of the current sweep has never been computed. Cheap,
  needs a small fresh S7 sub-run.
- **The post-fix FP surge is still open** — Tasks 2–4 didn't close it and **no Task 5 ruling exists**.
- **S5's OpenWSFZ-only fallback** — spec'd, not coded; would silently miscount real off-air decodes
  as false positives. ~1 h `qa/` fix, priced, not authorised.

---

## 8. Standing warning for whoever picks this up

**HK-018 fired ten times on 2026-08-07.** Three of the four RC arms re-derived work that already
existed on disk; one published a retracted number. **Every instance was a failure to open a file that
existed, in the directory already being written into.**

Before speccing or running anything on this board:

1. Open the D-001 branches — `d001-c1-*`, `d001-c2-*`, `d001-c4-*`.
2. Open `qa/ARTEFACT_INVENTORY.md`.
3. **Grep `qa/cycleframer-alignment-replay/` by topic and read the results in date order** — the July
   thread ran to a dozen dated rulings and revisions, several superseding each other within hours.
   The 22:30 ruling that retracted C.5a sat four documents after the 20:30 one that specified it.

**Treat the feeling of already knowing as the trigger to go and look.**

---

*Per HK-015 this is Architect → QA; `dev-tasks/*.md` remain QA's to author, and §2.2's blocker is an
escalation rather than a session decision. Per HK-014 committed locally, no push, no merge, and I am
not asking for one. Per HK-011 nothing here changes `src/`. Per HK-006 `pre_merge_check.py` is the
Captain's to run. Per NFR-021 all planted signals are Q-prefix synthetic; the corpus BER data stays
inside git-ignored `artefacts/`.*
