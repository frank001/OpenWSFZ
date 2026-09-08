# `FP-FLOOR-LIVE` — Architect → QA spec: does the emission floor `T` destroy genuine decodes on live audio?

**Architect, 2026-09-08 17:10Z** (`date -u`, HK-017). Base `main`@`cf21ac5`, branch
`arch/fp-floor-operator-setting`. Ordered by the PO on 2026-09-08 in response to the proposal that
the emission floor be exposed as an **operator-configurable option in Advanced Settings** rather
than shipped as a project default.

---

## 0. What this is, and what it is NOT

**Pure re-analysis of live corpora already on disk.** No capture run. No rebuild. No `src/` or
`native/` change. No Developer session. No Tx.

🛑 **This arm does NOT build the filter, does not author a settings page, and does not re-open
`FP-PARITY` ROW 3.** ROW 3 fired on its written terms (`F − T = 5.378 dB` against a 6.0 dB bar) and
**stays fired**. Nothing in this document may be cited as narrowing, softening or re-reading it.

🛑 **This arm authorises no `src/` work in any row.** Its best outcome is that the *Architect* is
cleared to draft a separate pre-registration for the operator control — which would then need the
PO's ratification, QA to author the dev-task, and a Developer session (HK-011/HK-015).

### 0.1 Why an operator control is a different question from ROW 3 — stated once, so it is auditable

`FP-PARITY` §4's 6.0 dB policy margin is insurance against **one specific harm**: the project
shipping a default that silently costs operators decodes they never consented to lose and cannot
see going missing. An **opt-in, default-off, instantly reversible** control does not carry that
harm — the operator accepts the risk knowingly and can withdraw it in one click.

🔴 **That is a different proposition, not a smaller version of the same one, and it therefore needs
its own evidence rather than ROW 3's margin re-scored.** What an operator control needs, and what
ROW 3 never measured, is: **how many genuine decodes does the cut actually remove, on live air, at
n large enough to state a rate?** `F = 8.00 dB` came from an S1b ladder of a handful of decodes and
is a **sample minimum, truncated by the ladder** (HK-026). This arm replaces that with ~10⁵ live
decodes and an independent decoder as the corroborating instrument.

### 0.2 🔴 Architect de-blinding disclosure (mandatory, HK-021)

Before drafting I ran an **outcome-blind marginal probe**, committed with this spec as
`qa/cycleframer-alignment-replay/fp_floor_live_snr_marginal_probe.py` so the disclosure is
re-runnable rather than asserted — computing **only** the distribution of
OpenWSFZ's reported SNR. It performs **no join against the reference decoder**, so it cannot see
the corroboration split this arm's rows turn on. **I am de-blinded on the size of the removed set
and blind on the answer.** The threshold `T` is inherited unchanged from `FP-PARITY` (fixed
2026-09-03, before any of this) and was **not** chosen by looking at that histogram — sibling (y).

🔴 **One incidental finding from the probe that binds this spec, and every future use of reference
SNR: WSJT-X's reported SNR is CLAMPED AT −24 dB.** On `20260803_live_run_1713` its minimum is
exactly −24 with **856 decodes piled on it against 390 at −23** — a clamp, not a tail. Two
consequences, both binding:

1. ⚠️ **The published gain regression `ours ≈ 0.6865 × ref − 4.742` was fitted with its regressor
   censored at the bottom.** It may **not** be used to map our cut onto the reference scale, and any
   argument of the form *"our −24 corresponds to reference −28, which is below FT8's floor, so the
   cut is safe"* is **barred in this arm.** I had drafted exactly that argument and it is withdrawn
   here rather than deployed.
2. ✅ **It does not obstruct the measurement**, because corroboration is matched on
   `(cycle, frequency, message)` and never on SNR. Say so in the report; do not let a reader assume
   the clamp censors the join.

---

## 1. Where `T` comes from — restated, not re-derived

| Symbol | Meaning | Value | Source |
|---|---|---|---|
| `C` | max `excess` over false accepts (offline n=454, plus in-chain historicals) | **+1.622 dB** | `FP-PARITY` §2.2 |
| `T` | the emission floor, `≜ C + 1.0 dB` (one in-chain readout quantum above `C`) | **2.622 dB** | `FP-PARITY` §4 ROW 2 |
| `excess` | in-chain, **not recorded** — reconstructed as `Snr + 26.5`, quantum 1 dB | — | `FP-PARITY` §2.2 |

⇒ **In the shipping product this filter is exactly one thing: drop decodes whose reported SNR is
`≤ −24 dB`.**

`excess < T` ⟺ `Snr < 2.622 − 26.5` = `Snr < −23.878`.

✅ **Sibling (o), and it is a genuinely good property: the cut falls strictly between two integer
readout values.** SNR is emitted as an integer, so **no decode can straddle the threshold** and the
partition is exact — `−24` and below removed, `−23` and above kept. There is no quantum ambiguity
to price. State this in the report; it is the one place this arm is better off than `FP-PARITY` was.

---

## 2. The measurement

### 2.1 Populations

**Primary corpus: `artefacts/20260803_live_run_1713`.** Chosen on provenance, before any outcome
was computed: it is the only corpus where the inventory records **both decoders on ONE verified
audio path** (median |r| = 0.987 over 8 WAV pairs, lags ≤ 34 ms), 20m, one contiguous 18.96 h epoch,
post-`be5960a`, drift screen ROW 5 PASS.

**Replication corpora, reported separately and never pooled with the primary:**
`20260808_live_run_0016-8080` and `-8081` (20m), `20260808_live_run_1154-8080-17m` and `-8081-17m`.

🛑 **The 80m pair (`20260809_live_run_0155-*`) is EXCLUDED.** Its `wsjt-x/wav/` are still hardlinked
across the two folders (X0's unrepaired half) and its ROW 0e fires — the deep tail has no reference
at all. A missing reference manufactures "uncorroborated", which is this arm's reassuring direction.
**Do not include it, and do not treat its exclusion as a result.**

### 2.2 The statistic

For each OpenWSFZ decode, `removed ≜ (Snr ≤ −24)`.

`corroborated ≜` the reference decoder emitted a matching decode in the **same cycle**, with
`|Δf| ≤ 3 Hz`, under **wildcard message matching**.

🔴 **The matching rule is INHERITED, not invented, and both halves are load-bearing:**

- **`|Δf| ≤ 3 Hz`** is H1a's derived tolerance (`1.5625 + 0.5 + 0.5 = 2.5625`), and H1a measured the
  `Δf` distribution to be **bimodal with an empty gap between 4 and 20 Hz** ⇒ the result is
  insensitive to any tolerance in 3–20 Hz. Do not re-tune it.
- 🔴 **Wildcard matching (treat `<...>` as matching one token in position) is MANDATORY, and exact
  text matching is a DEFECT here, not a conservative choice.** H1 measured this: symmetric exclusion
  moved recovery +0.08 pp while wildcard matching moved it +2.26 pp. An unresolved-hash decode that
  fails to match looks **uncorroborated**, which inflates "junk removed" and **hides genuine loss** —
  sibling (n), the instrument's failure landing in the tail that reassures us.

**Primary quantity:**

```
K_removed  =  corroborated AND removed   /   removed
```

**Reported alongside it, in the same table (sibling (u) — a rate without its base rate is not
evidence):** `K_kept`, `K_all`, and `K(s)` for every integer SNR `s` from −38 to +10.

### 2.3 The probe's own predicate, as code (sibling (r))

The prose above is a gloss on this. Where they disagree, **this is the spec**:

```python
# excess = Snr + 26.5   (FP-PARITY §2.2)
T_EXCESS = 2.622
SNR_CUT  = T_EXCESS - 26.5          # -23.878
removed  = (snr < SNR_CUT)          # integer readout => snr <= -24
```

Marginal distribution measured at drafting, outcome-blind, disclosed per §0.2:

| corpus | n decodes | removed (`≤ −24`) | share |
|---|---|---|---|
| `20260803_live_run_1713` / `owsfz` | 64,417 | **873** | 1.3552% |
| `20260808_live_run_0016-8080` / `owsfz` | 45,258 | **794** | 1.7544% |

✅ **Sibling (q) is satisfied and this is the exhibit: the predicate MOVES.** It selects ~1.4–1.8% of
decodes — neither empty (the gate could never fire) nor everything (the gate would be inert).

⚠️ **And the shape is a caution, stated now rather than discovered later: OpenWSFZ's low tail is
smooth and monotone from −17 down through −30, with no gap at the cut.** The cut lands in the middle
of a continuous distribution, not in a valley between two modes. A mixture with no visible gap does
not prove overlap — but it does not support cleanliness either, and **nobody may report a clean
separation on the strength of the marginal alone.**

---

## 3. ROW 0 — preconditions, with my own HK-025 classification

**Pre-cleared by the Architect so QA can check the working rather than reconstruct it.** Per HK-025
QA runs the two-step check independently and **may refuse any row outright** without my agreement.

| row | check | class | both-branch evaluation | my verdict |
|---|---|---|---|---|
| **0a** | Corpus provenance: primary corpus's two legs are distinct captures (inode + md5 distinct, per `ARTEFACT_INVENTORY.md`) | **VALIDITY** | a hardlinked reference is not a second instrument at all | ✅ legitimate |
| **0b** | **Matcher positive control:** `K(s) ≥ 0.90` pooled over `s ≥ 0 dB` | **VALIDITY** | a broken join makes every `K` meaningless, not merely imprecise | ✅ legitimate |
| **0c** | `removed ≥ 300` in the primary corpus | **PRECISION** | pass ⇒ a row; fire ⇒ VOID for want of resolution. **Differs** | ✅ legitimate |
| **0d** | Wildcard matching is ON: exhibit ≥1 decode matched **only** under wildcard | **VALIDITY** | exact-only matching measures the parser, not the decoder | ✅ legitimate |

### 3.1 🔴 ROW 0b is the row that matters, and here is why it exists

**If the matcher silently fails, `K_removed` → 0, and this arm concludes "the filter costs
nothing."** That is sibling (n) exactly: the instrument's own failure mode lands in the reassuring
tail, and the more broken it is the more comfortably the arm passes. `FP-PARITY`'s own ancestor
made this mistake (P-LIVE Stage 1's ROW 0f could only fire on implausibly *low* BER while a
mis-anchor pushes BER *up*).

**The bar is derived, not chosen.** Our published live false-accept level is bounded
**4.24–4.90% across all decodes** ⇒ corroboration across all decodes is ≈95%; restricted to
`s ≥ 0 dB` it can only be higher. **0.90 sits below that with margin**, so a pass is uninformative
about the decoder and a *fire* is unambiguous evidence the join is broken. That asymmetry is the
point of a positive control.

⚠️ `n` at `s ≥ 0` is in the thousands, so `1.96·SE` on `K` there is well under 1 pp — the bar is
~7 pp from its expected value, i.e. resolvable by a wide margin (sibling (m)).

### 3.2 Sibling (t), evaluated and found not to bite — recorded so nobody has to re-derive it

(t) says a gate whose population is selected on the treatment's target outcome is blind to the
treatment's cost elsewhere. Here the treatment's **blast radius is exactly the selected population**:
the filter touches decodes at `≤ −24 dB` and provably nothing else, because the predicate is a pure
function of one emitted field. **There is no complement population to gate.** Stated explicitly
because "(t) does not apply" must be demonstrated, not assumed.

---

## 4. Reading rule — evaluate in strict order, exactly one row fires

🔴 **`corroborated AND removed` is a LOWER bound on genuine loss**, not an estimate: the reference
misses decodes too, so genuine decodes it did not corroborate are invisible here.
🔴 **`removed AND NOT corroborated` is an UPPER bound on junk removed**, not a count of junk:
uncorroborated ≠ false. **Both bounds point the same way — against the filter — which is the
direction an operator-facing claim must err in.** Neither may be reported without its direction.

Let `k = corroborated AND removed`, `n = removed`, and `[lo, hi]` its Clopper-Pearson 95% interval.

### ROW 1 — the provable genuine cost is negligible

**FIRES iff `hi ≤ 0.02`.**

⇒ **Consequence:** the Architect is cleared to draft a **separate** pre-registration for the
default-off operator control, carrying `k`, `n`, `hi`, and the per-hour rate on its label.
🛑 Not a licence to build, to author a settings page, or to touch `src/` — see §0.

### ROW 2 — the cut demonstrably costs genuine decodes

**FIRES iff `lo ≥ 0.05`.**

⇒ **Consequence:** **no operator control is drafted.** State the loss rate per hour and stop. 🛑 Do
not soften this into "with a higher threshold it would be fine" — a threshold chosen after seeing
this result is the prohibited re-read and earns a new pre-registration.

### ROW 3 — the interval straddles

**FIRES iff neither ROW 1 nor ROW 2 fires.**

⇒ **Consequence:** report `k`, `n`, `[lo, hi]` and the per-hour rate; **draft nothing.** Per sibling
(w), a straddling interval is decided by **position, not width** — do not argue that a narrow
interval near a bar is "close enough".

### ROW 4 — instrument

Any ROW 0 fires ⇒ **VOID**. No row outcome of any kind is reported, and `K_removed` is not quoted
even descriptively.

---

## 5. What QA reports (HK-001)

1. `k`, `n`, `K_removed` with its CP95 interval, and the **genuine decodes lost per operating hour**
   (`k / 18.96 h` on the primary) — the only unit the operator experiences.
2. The full `K(s)` curve, `s` from −38 to +10, with counts. **This is the deliverable that outlives
   the verdict** — it is the first per-SNR corroboration curve the programme will hold.
3. `K_kept`, `K_all`, and the ROW 0b control value (sibling (u)).
4. The four replication corpora, **each reported separately**, never pooled with the primary and
   never with each other.
5. Whichever bound was NOT the headline, with its direction stated (§4).
6. 🔒 **NFR-021: aggregate counts and rates only.** No `message_text`, no callsigns, in the report
   or in any committed artefact. Scan **report prose** as well as data files, and import
   `scan()`/`classify()` rather than re-implementing them — the scanner skips `.cs`/`.h`/`.yaml`/
   `.bat` and cannot scan uncommitted directories.

**Harness:** author it in `qa/cycleframer-alignment-replay/`, reusing `h1a_wildcard_frequency_
validation.py`'s matching rather than writing a third one. The spec lives here because it is
`FP-PARITY` lineage; the code belongs where the live-corpus matchers already are.

---

## 6. Architect prediction, and the calibration to discount it by

**Recorded before the join is computed. My tally: categorical ROW calls 2 of 4; ranges 3 of 5, and
both range misses were too PESSIMISTIC about how cleanly an effect separates.** Read the range wide
and the row call as close to a coin flip.

- **`K_removed`: 0.005–0.04.** Predicted **ROW 1**, at ~55% credence; ROW 3 at ~35%.
- Reasoning, so it can be falsified rather than merely scored: S1b showed OpenWSFZ produces
  **nothing** at −24 or −21 dB injected while WSJT-X took 2/3 at −21, i.e. our decoder's own
  sensitivity floor sits **above** the cut. If that holds live, genuine decodes at reported `≤ −24`
  should be rare.
- ⚠️ **The named threat to my own prediction, priced rather than noted (the failure I have committed
  three times):** our SNR is biased **low** relative to the reference by several dB, so a genuine
  decode can be *reported* at −25 while being physically well above our sensitivity floor. That is a
  mechanism for `K_removed` to be materially non-zero, and I cannot bound it without the join —
  which is the whole reason this arm exists rather than an argument in prose.

---

## 7. 🔴 The one thing the PO must ratify BEFORE QA arms this

**The ROW 1 bar of `hi ≤ 0.02` is a product decision wearing statistical clothing, and it is not
mine to set.** It says: *losing up to 2% of the decodes this filter removes — on the primary corpus,
roughly **one genuine decode per hour** — is an acceptable price for removing the junk.*

I have proposed 2% because it is the level at which the loss is smaller than the cycle-to-cycle
noise in what the panel shows anyway. **But this is the same class of number as the decode-latency
target: the operator is the only person who can say what it is worth.** QA does not arm this arm
until the PO has ratified or replaced that figure, and if the PO replaces it, the replacement goes
in before commit — **never after the count is known.**

---

## 8. Standing prohibitions this arm does not touch

- 🛑 `FP-PARITY` ROW 3 stays fired. `F − T = 5.378 dB` is unchanged and uncontested here.
- 🛑 `NBR-A` calibration stays closed; the M1/M2 question is not reopened.
- 🛑 No baseline is created. `FP-REGRESSION` is untouched — all seven citation guards stand.
- 🛑 `21/660 = 3.182%` and `18/540` keep their denominators; nothing here is pooled with either.
- 🛑 Input scaling, OSR, subtract-and-resynthesise, spectral locality: all still closed.
