# `FP-FLOOR-LIVE-2` — Architect → QA spec: capture a post-`c3a9ea8` live corpus, then read the withdrawn arm against it

**Architect, 2026-09-08 17:54Z** (`date -u`, HK-017). Base `main`@`cf21ac5`, branch
`arch/fp-floor-operator-setting`. Ordered by the PO 2026-09-08 after
`FP-FLOOR-LIVE` was withdrawn for want of a valid population.

**Two parts.** Part A is a **capture run** — the PO operates the radio, QA runs the OpenWSFZ side and
gathers. Part B re-reads the withdrawn arm's gate, unchanged, against the new corpus.

🛑 **Part A is a capture run and therefore the Captain's to authorise.** This document specifies it;
it does not authorise it. No `src/` or `native/` change in any part — `git diff --stat -- src/ native/`
must be empty at every commit.

---

## 1. The PO's question, answered: TWO WSJT-X instances — but combined as a UNION, not an intersection

**Recommendation: two.** The reasoning is not "more data is better", and the combiner matters more
than the count.

### 1.1 🔴 `REF = A ∩ B` is the WRONG combiner here, and it is the one this project has always used

The D-001 work used `REF = A ∩ B` — decodes *both* WSJT-X instances produced — because it needed a
**high-confidence denominator**: decodes that certainly existed, against which our misses were
counted.

**This arm uses the reference for the opposite purpose.** Here WSJT-X is the instrument that
establishes **our** decodes are genuine. A decode the reference misses is scored *uncorroborated*,
which reads as *spurious*, which **understates genuine loss** — sibling (n) again: the instrument's
own weakness lands in the tail that reassures us about the filter.

⇒ **`REF = A ∪ B`.** Any instance corroborating our decode is evidence the signal was really on the
air. The union maximises corroboration, therefore maximises measured genuine loss, therefore errs
**against** the filter — the only direction an operator-facing claim may err in.

🛑 **Do not reuse an `A ∩ B` reference from any prior harness without changing it. Pin the combiner
in code and assert it in ROW 0.**

### 1.2 What the second instance actually buys

Not volume — the two instances historically agree **~99.8%** on `(ts, message)`, so the union adds
little. It buys the one thing a single instance cannot provide: **a measured bound on the
reference's own miss rate, on exactly the population that matters** (our `≤ −24 dB` decodes). With
one instance that quantity is unmeasurable and ROW 0b can only detect a *broken* matcher, not a
*lossy* reference.

### 1.3 Configuration, and the one thing that must not be got wrong

| | assignment |
|---|---|
| **OpenWSFZ** | the **FT-991A** chain — the same audio path as `WSJT-X #1` |
| **WSJT-X #1** (primary reference) | **same radio, same audio path as OpenWSFZ** |
| **WSJT-X #2** (independent corroborator) | the **second radio** (SDR Uno), same antenna split |

🔴 **`WSJT-X #1` must be on the identical audio path to OpenWSFZ.** Our reported SNR is computed
from *our* audio's local noise floor; if the reference sits on a different capture chain, a decode
we report at −25 may be −20 on theirs, and corroboration gets confounded with the documented
**~10–13% capture-chain effect**. `WSJT-X #2`'s different chain is fine and is the *point* — a
second receiver hearing the same message is strong independent evidence the signal existed — but it
may **never** be the primary reference.

### 1.4 ✅ Why two instances is safe now, when it was not in August

Two instances is what produced the **X0 defect** (`--wsjtx-link-from` materialised one instance
into both folders; `REF = A ∩ B` silently degenerated to `A ∩ A`; invisible for weeks). **G1 is now
implemented and tested** — `guard_wsjtx_link_from_premise`, `active_wsjtx_instances`,
`render_provenance_section` in `tools/gather_live_run_artefacts.py`, with
`tools/tests/test_gather_live_run_artefacts.py`. ⚠️ **`BOARD.md` still carries G1 as "NOT executed,
still open" — that line is STALE; corrected in the same edit as this spec.**

🛑 **Do NOT pass `--wsjtx-link-from`.** It exists for one physical install shared by two daemons.
That is not this run, and it is the exact flag that caused X0.

---

## 2. Part A — the capture

### 2.1 OpenWSFZ session (QA to launch and verify)

| setting | value | why it is not negotiable |
|---|---|---|
| binary | **current `main` `cf21ac5`, shim `20260050`** | the whole point: post-`c3a9ea8` |
| audio device | **`"Voicemeeter AUX Input"`, passed explicitly** | ⚠️ `run_study.py`/`warmup.py` still default to `"CABLE Input"`, and CABLE Output is documented unreliable |
| **cycle-audio archive** | **ON** | 🔴 **mandatory** — the WAVs are what make the corpus re-decodable later against a different binary. Without them this run is single-use |
| band | **20m (14.074)** | matches the primary comparison corpora; 🛑 not 80m — daytime D-layer absorption makes it dead |
| decoder settings | record `kMinScorePass2`, `osdCorrThreshold`, `osdNhardMax` in `contents.md` | pinned for the record, not varied |

**Before arming, assert `captureActive=true`** — capture endpoint GUIDs go stale silently across a
replug; the friendly name is unchanged, the daemon retries forever, stays "alive", and archives
nothing.

**Pin the binary by SHA256, not by version label** — `FT8_SHIM_VERSION` identifies nothing on its
own. Record the `libft8.dll` SHA256 in `contents.md` before the session starts.

### 2.2 🔴 Duration is set by a POPULATION target, not by the clock — and there is a hard floor

The quantity that sizes this run is `n` = OpenWSFZ decodes reported at **`≤ −24 dB`**. Against the
PO-ratified `hi ≤ 0.02`:

| `n` | CP95 hi at `k=0` | ROW 1 passes iff |
|---|---|---|
| 100 | 3.62% | 🛑 **never — unreachable even at zero** |
| 150 | 2.43% | 🛑 **never** |
| **200** | 1.83% | `k ≤ 0` |
| 300 | 1.22% | `k ≤ 1` |
| **600** | 0.61% | `k ≤ 5` |
| 900 | 0.41% | `k ≤ 9` |

🛑 **Below `n = 200` the ratified bar cannot be met even if not one removed decode is corroborated.**
A run that stops short of it produces an unreadable result, not a cautious one.

**Stopping rule, pre-registered:** run until **`n ≥ 600`** or **24 h elapsed**, whichever comes
first. ⚠️ **Stop on `n`, never on `k`** — `n` is fixed by band activity and the decoder; stopping
when the *answer* looks good is the prohibited practice.

**Sizing is genuinely uncertain and QA should expect to be surprised.** The pre-fix corpora yielded
~46 removed decodes/hour, but **an unknown share of those were the collapse artefact `c3a9ea8`
fixed.** Post-fix the rate may be far lower.

### 2.3 ROW A — the population outcome, read before anything else

- **ROW A1 — `n ≥ 200`** ⇒ proceed to Part B.
- 🔴 **ROW A2 — `n < 200` after 24 h** ⇒ **Part B is VOID for want of population, and that is a
  RESULT, not a failure.** It means the cut removes almost nothing on the current binary ⇒ **the
  operator setting is close to a no-op and the case for building it collapses.** Report `n`, the
  hours, and the implied rate per hour. 🛑 Do **not** extend the run to manufacture a population —
  that is selecting the corpus on the outcome.

---

## 3. Part B — the gate, unchanged

**Re-read `2026-09-08-1710-…`'s §3/§4/§5 verbatim against the new corpus.** Everything survives and
nothing may be re-tuned:

- ROW 0a–0d, with **ROW 0b's positive control** (`K(s ≥ 0 dB) ≥ 0.90`) unchanged;
- **wildcard message matching mandatory** (H1/H1a) — exact matching hides genuine loss;
- **Amendment 1**: the emitted SNR is `roundf`'d, so the measured filter removes `excess ≤ 3.0`
  against `T`'s `< 2.622` ⇒ **every loss figure is an UPPER bound on `T`'s own loss**;
- **Amendment 2**: the power disclosure, and the plain-English bar;
- **ROW 1 `hi ≤ 0.02`, PO-ratified 17:24Z — FIXED. Not re-openable on this run's result.**

**One addition, and only one:** ROW 0e — `REF` is the **union** per §1.1, asserted in code, with the
`A`-only and `B`-only corroboration counts reported separately so the union's contribution is
visible rather than assumed.

---

## 4. What this run does NOT do

- 🛑 It is **not** a re-read of `FP-PARITY` ROW 3, which stands.
- 🛑 It creates **no baseline**; `FP-REGRESSION`'s citation guards are untouched.
- 🛑 It authorises **no `src/` work.** ROW 1 clears the Architect only to *draft* a pre-registration
  for the operator control, which then needs PO ratification, a QA-authored dev-task and a Developer
  session (HK-011/HK-015).
- 🛑 It does **not** test the D-003 bandlimited-estimator concern, which remains untested and is a
  separate question from the `c3a9ea8` collapse this corpus is being captured to escape.

## 5. Reporting

Per HK-001, plus: 🔒 **NFR-021 — the corpus contains real third-party callsigns.** `artefacts/` is
blanket-gitignored and the raw capture stays there. Any committed artefact carries **aggregate counts
and rates only**; scan report **prose** as well as data files, and import `scan()`/`classify()`
rather than re-implementing them. ⚠️ `matcher.py` logs unmatched decodes with full `message_text` —
grep every derived CSV before committing it.
