# ARCHITECT -> QA — SPEC: `F-001 R5` — own-callsign direct hash match on the answerer path

**From:** Architect · **To:** QA · **Date:** 2026-08-27 15:31Z · **Repo HEAD at drafting:** `58339c1`
**Ordered by:** the PO ("spec option 5"), following the options comment posted to GH #60.
**Status:** ARMED for the offline leg (Sec.4–Sec.6). The build-dependent leg (Sec.8) is a DESIGN
BRIEF for a future Developer session and is **NOT** authorised by this document.

---

## Sec.0 — What this is, and the reframing that came out of drafting

### 0.1 Route 5 is not what the #60 comment said it was

The #60 comment described route 5 as "hash **our own** callsign once at 12 bits and compare incoming
Type-4 hash fields against it directly … small, exact". Drafting this spec required reading the
answerer path, which the comment itself flagged as **not verified**. It is now verified, and the
description was wrong in two ways that matter.

**(a) The hash is the THIRD of three blocking layers, not the first.** A Type-4 message directed at
this station is discarded before the hash is ever consulted:

| layer | where | what it does | verified at |
|---|---|---|---|
| **L1 — parse** | `QsoAnswererService.TryParseMessage` | requires **exactly 3 tokens**; a 2-token Type-4 (`<CALL> RR73`) returns `false` and the decode is skipped | `QsoAnswererService.cs:1631-1645` |
| **L2 — bracket literal** | `dest = parts[0]` then `dest.Equals(ours, …)` | a **correctly** resolved hash prints as `<PD2FZ>`; `"<PD2FZ>" != "PD2FZ"` ⇒ `toUs == false` | `QsoAnswererService.cs:1637`, `:1079`, `:1161` |
| **L3 — hash** | `hash_table_lookup` first-match-wins | resolves to the wrong station, or to `<...>` | `ft8_shim.c:637-654` |

L2 is the one that reframes the route. `native/ft8_lib_vendor/ft8/message.c:604-611` adds angle
brackets **unconditionally** on every hash-resolved callsign — `add_brackets()` on success,
`"<...>"` on failure. Nothing downstream strips them: grepped `Ft8Decoder.cs` and the whole of
`src/OpenWSFZ.Daemon/` — the only bracket-aware code is shape-validation
(`Ft8Decoder.cs:733,886`), never normalisation.

**Consequence, stated plainly: fixing L3 alone changes nothing observable.** A perfect own-hash
match would resolve the reference to our call, the decoder would print `<PD2FZ>`, and L2 would
reject it exactly as it does today. **Route 5 as scoped in #60 is a no-op.**

**(b) The comparison sites are duplicated, and the caller path has the same defect.** Five sites,
two files, two independent copies of `TryParseMessage`:

- `QsoAnswererService.cs:1631` (`TryParseMessage`), consumed at `:1079` and `:1161`
- `QsoCallerService.cs:1349` (a second copy of `TryParseMessage`), consumed at `:938`
- `QsoCallerService.cs:1393-1394` — a **third** comparison, and the only one that already
  normalises anything: it accepts both `PD2FZ/P` and the base `PD2FZ`. Precedent exists for
  normalising the `dest` token; it simply does not cover brackets.

**(c) `n12` does not cross the ABI.** `Ft8NativeResult` is 48 bytes — `FreqHz`, `Dt`, `Snr`,
`Message[36]` (`Ft8NativeResult.cs:18-45`). The 12-bit hash field, `iflip` and `icq` are computed in
`ftx_message_decode_nonstd` (`message.c:400-434`) and discarded. Managed code cannot perform an
own-hash comparison against anything, because it never sees a hash. Route 5 therefore spans
**shim → ABI → answerer**, needs a shim version bump past `20260046` (`ft8_shim.h:626`), and a build
that does not exist. **HK-021(p) bites: no binary ⇒ no claim about a fixed build's behaviour, from
any outcome of this arm.**

### 0.2 Exposure, measured while drafting (HK-021(m))

Probe: `artefacts/2026-08-27-route5-probe/{probe_route5_exposure.py,probe_fp_uniformity.py}`
(gitignored, counts only). Corpus: `artefacts/20260803_live_run_1713/{owsfz,wsjt-x}/ALL.TXT`.

🔴 **Both logs contain ZERO `Tx` lines.** 64,417 `Rx` decodes ours, 43,423 theirs, no transmissions
at all. A station that never transmitted cannot be addressed. **The efficacy of route 5 — harm 2,
"a call directed at us is missed" — has STRUCTURALLY ZERO exposure in every artefact we hold.**
This is not a small sample that a bigger corpus fixes; it is a corpus of the wrong kind. It can only
be measured by a transmitting station, which means a live run, which means a build (Sec.8).

Hashed-reference population in **our** log (exactly one bracket token per message):

| shape | count | which layer blocks it |
|---|---:|---|
| 2 tokens, bracket first | 177 | **L1** — never parses |
| 2 tokens, bracket second | 18 | **L1** |
| 3 tokens, bracket at `dest`, **resolved** `<CALL>` | **293** | **L2** — brackets alone |
| 3 tokens, bracket at `dest`, **unresolved** `<...>` | **2,640** | **L3** (and L2 behind it) |
| 3 tokens, bracket at `src` | 1,206 | not addressed to anyone by hash |
| other (3-token pos 2; 4-token) | 9 | — |
| **total single-bracket decodes** | **4,343** | |

Reference log, same shape: 2,867 single-bracket decodes, 1,805 with the bracket at `dest`, of which
**626** resolved. ⚠️ These are **denominators, not benefits** — they size the population the rule
would be applied to, across all stations' traffic. The share directed at *us* is zero, per above.

Own-hash collision exposure (`OWNCALL = PD2FZ`, the NFR-021 exception):

- 11,233 distinct plain callsigns across both logs; **3,848 of 4,096** 12-bit codes occupied.
- **8 other callsigns heard in this corpus share our call's 12-bit code.** Those 8 are exactly the
  stations a direct own-hash match cannot distinguish from us.
- Observed hashed references carrying our code: **0 of 1,553**. 🔴 λ = 0.379 ⇒ **HK-021(j): that
  zero is not evidence of absence.** CP one-sided 95% upper bound 0.001927 ⇒ up to ~3.0 events per
  corpus is fully consistent with the data.
- The `1 in 4,096` false-positive figure quoted publicly rests on hashes being uniform over real
  callsigns. **That assumption was checked and survives:** occupancy against Poisson(λ=2.7424) —
  observed/expected 714/723.6, 1009/992.2, 914/907.0, 645/621.8, 339/341.1, 153/155.9, 40/61.1,
  22/20.9, 10/6.4, 2/1.7; occupied codes 3,848 vs 3,832.2 expected. Only k=7 wobbles materially.

### 0.3 The asymmetry, said up front and never dropped

🔴 **This arm can measure only the COST side of route 5.** The benefit (calls to us that would stop
being missed) has zero exposure and is unmeasurable offline, full stop. Every figure this arm
produces is a false-positive rate, a blocked-population count, or a containment share.

**A cost-only result must never be read as "route 5 is unfavourable".** It is an instrument with one
jaw. Sec.6 makes this a hard constraint on what any outcome authorises.

### 0.4 PO decisions taken at drafting

The PO was shown the L1/L2 finding and ruled two scoping questions before this spec was written:

1. **Scope:** all three layers are ONE route. Route 5 is respecified as L1+L2+L3, not L3 alone.
2. **Mechanism:** the 12-bit hash reaches managed code by a **TLS side-channel getter** modelled on
   the existing `ft8_get_last_snr_terms` (`ft8_shim.c:1186-1200`, TLS arrays at `:589-591`) — no
   `FT8Result` struct change, no ABI break, **no change to any displayed name**. Harm 1 stays out of
   scope by construction.

---

## Sec.1 — Every outcome this arm can have, enumerated before it runs

1. **ROW 0 VOID** — an instrument check fails; no gate is computed, nothing is claimed. (ARM 1C
   landed here after its spec forgot to enumerate it. It is enumerated.)
2. **G1 fails** — a hashed-`dest` decode IS recognised as "to us" by the current predicate for some
   hypothetical own-call. That falsifies Sec.0.1(a)/L2 and the whole reframing; **the spec is wrong
   and is withdrawn, not patched.**
3. **G1 holds, G3 lands FAVOURABLE** — the own-hash rule's false-positive rate is below the bar.
   Route 5's cost side is bounded. Authorises **nothing** (Sec.6); it removes one objection.
4. **G1 holds, G3 lands UNFAVOURABLE** — the FP rate exceeds the bar. Route 5 as an unconditional
   rule is contraindicated; the containment of Sec.8.4 becomes load-bearing rather than optional.
5. **G1 holds, G3 INDETERMINATE** — the interval straddles the bar. No verdict either way. This is
   a legitimate landing, not a failure.

---

## Sec.2 — Inputs, pins, and what must be REUSED not re-implemented (HK-018)

**Inputs (read-only, already on disk — no capture, no replay, no rebuild, no `src/` edit):**

| input | path | pin |
|---|---|---|
| ours `ALL.TXT` | `artefacts/20260803_live_run_1713/owsfz/ALL.TXT` | 64,417 `Rx` lines, 0 `Tx` lines |
| reference `ALL.TXT` | `artefacts/20260803_live_run_1713/wsjt-x/ALL.TXT` | 43,423 `Rx` lines, 0 `Tx` lines |

**Reuse verbatim, by import, never by re-implementation:**

- `common_arm1.n22_of` / `n12_of` — the hash. Do **not** re-type it.
- `common_arm1b.slot`, `build_theirs_index`, `best_match` — the reference pairing, unchanged.
- `common_arm1b.cp_lower_one_sided` / `cp_upper_one_sided` — the intervals.
- `common_b1.redact` — every callsign that reaches `result.json`, the report or a log line is a
  `CS-xxxxxx` token. **NFR-021: no real callsign strings leave memory**, `PD2FZ` included.
- `gap-census-a/common.parse_all_txt` — the parser.

**Harness location:** `qa/rr-study/f001-r5/{common_r5.py,run_r5.py}`, results under
`results/<date>-<sha>/`. Same shape as ARM 1D.

---

## Sec.3 — Shipped predicates, character for character (HK-021(r))

QA transcribes these **exactly**. A typo here becomes a harness defect, and that is the Architect's
fault, not QA's.

### 3.1 — The current managed predicate, transcribed from C#

Source of truth: `QsoAnswererService.cs:1631-1645` and `:1079`. Transcribed, not paraphrased:

```python
def try_parse_message(msg):
    """Transcription of QsoAnswererService.TryParseMessage (C#:1631-1645).
    C# splits on ' ' with RemoveEmptyEntries after Trim(); str.split() is
    equivalent for these inputs. Returns None where C# returns false."""
    parts = msg.strip().split()
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]   # dest, src, payload
    return None


def to_us_current(msg, ours):
    """Transcription of QsoAnswererService.cs:1079 --
    dest.Equals(ours, StringComparison.OrdinalIgnoreCase)."""
    p = try_parse_message(msg)
    if p is None:
        return False
    return p[0].upper() == ours.upper()
```

### 3.2 — The proposed predicate (L1+L2 only; L3 needs a hash the ABI does not carry)

```python
def to_us_l1l2(msg, ours):
    """L1: accept the 2-token Type-4 shorthand. L2: strip one bracket pair
    from dest before comparing. NO hash is consulted -- this is exactly the
    part of route 5 that needs no native change."""
    parts = msg.strip().split()
    if len(parts) == 2:
        dest, src, payload = parts[0], parts[1], ""
    elif len(parts) == 3:
        dest, src, payload = parts[0], parts[1], parts[2]
    else:
        return False
    if len(dest) >= 2 and dest[0] == '<' and dest[-1] == '>':
        dest = dest[1:-1]
    if dest == '' or set(dest) == {'.'}:
        return False                      # the <...> marker is not a callsign
    return dest.upper() == ours.upper()
```

### 3.3 — The own-hash predicate (L3), evaluated against reference ground truth

```python
def hash_dest_n12(msg, theirs_name):
    """The 12-bit code actually carried in the message's dest slot.
    theirs_name is the reference decoder's resolution of that slot; where the
    reference did not resolve it, this returns None and the decode is UNKNOWN.
    HK-026: our own decoder may NOT be used to bound its own blind spot, so
    the code is derived from the wider-aperture instrument, never from ours."""
    if theirs_name is None:
        return None
    h = n22_of(theirs_name)
    return None if h is None else n12_of(h)


def to_us_l3(msg, ours, theirs_name):
    """Route 5's rule: the dest slot's 12-bit code equals our own. TRUE
    POSITIVE iff theirs_name == ours; FALSE POSITIVE iff it fires and
    theirs_name != ours."""
    n12 = hash_dest_n12(msg, theirs_name)
    if n12 is None:
        return None                        # UNKNOWN -- never silently False
    h = n22_of(ours)
    return h is not None and n12_of(h) == n12
```

🔴 **`None` is a third value and must stay one.** ARM 1C was VOIDed for turning an unverifiable
decode into a filter. Here UNKNOWN decodes are **labelled and counted**, and every gate that touches
them reports an interval with both adversarial assignments, exactly as ARM 1D did.

---

## Sec.4 — ROW 0: the instrument checks. Any failure ⇒ VOID, no partial run.

Run in order. State the result of every row; skip none.

- **0a — input identity.** SHA-256 of both `ALL.TXT` files recorded; `Rx`/`Tx` line counts reproduce
  64,417/0 and 43,423/0 EXACTLY. 🔴 **A non-zero `Tx` count on either file VOIDs the arm** — the
  zero-exposure premise of Sec.0.2 would be false and the whole framing needs redrafting.
- **0b — population reproduction.** The six-row shape table of Sec.0.2 reproduces EXACTLY:
  177 / 18 / 293 / 2,640 / 1,206 / 9, total 4,343. Reference side: 2,867 / 1,805 / 626.
- **0c — hash reproduction.** `n22_of`/`n12_of` are the imported ARM 1 functions (assert module
  identity, not equal output); 11,233 distinct calls, 3,848 occupied codes, occupancy histogram
  `{1:714, 2:1009, 3:914, 4:645, 5:339, 6:153, 7:40, 8:22, 9:10, 10:2}` all EXACT.
- **0d — predicate-movement exhibit (HK-021(q)).** Exhibit at least one real corpus decode for which
  `to_us_current` is `False` and `to_us_l1l2` is `True` under some hypothetical own-call, and one for
  which both are `False`. A predicate that never moves cannot gate anything.
- **0e — transcription check.** `try_parse_message` returns `None` for the 195 two-token
  bracket-bearing decodes and a 3-tuple for all 4,146 three-token ones. This is the row that catches
  a mis-transcription of Sec.3.1 before it becomes a finding.
- **0f — determinism.** Full run twice, out of process, under two different `PYTHONHASHSEED`s;
  `result.json` **byte-identical**. (Board hazard: hash-randomised set iteration.)
- **0g — NFR-021 scan.** Grep `result.json`, `run.log` and the report for any callsign-shaped token.
  Zero hits required, `PD2FZ` included. The repo is public.
- **0h — reference-coverage exposure, stated not gated.** Report the share of our hashed-`dest`
  decodes that have ANY reference row, and the share whose reference row resolved the slot. 🔴 **Carry
  ARM 1B's scoping caveat verbatim beside every G3 figure: reference pairing covers a minority of our
  decodes and nothing licenses extrapolating past it.**

---

## Sec.5 — Gates

**Unit of analysis for G1/G2:** one *(hypothetical own-call, decode)* pair. Every one of the 11,233
distinct plain callsigns is treated in turn as the station's own call. This is the move that gets
past zero exposure on the cost side: we cannot observe calls to *us*, but the corpus contains
thousands of stations that *were* addressed, and the rule's false-positive behaviour is a property
of the hash, not of which call is ours.

⚠️ Report the standard-form subset (`STD` in `common_arm1b`) separately from the whole. Our own call
is standard; a distribution dominated by nonstandard hypotheticals would not describe our case.

### G1 — the reframing itself, falsifiable

> **G1a (PASS bar, hard):** over all 11,233 hypothetical own-calls × 4,343 single-bracket decodes,
> the count for which `to_us_current(msg, ours) is True` is **exactly 0**.
> **G1b:** the same count under `to_us_l1l2` is **> 0**.

- **G1a == 0 and G1b > 0** ⇒ **G1 HOLDS.** L1+L2 block every hashed reference today, and stripping
  brackets unblocks some.
- **G1a > 0** ⇒ **G1 FAILS ⇒ outcome #2.** Sec.0.1 is wrong; QA reports the counter-example decode
  (redacted) and **stops**. Do not proceed to G2/G3.
- **G1a == 0 and G1b == 0** ⇒ **VOID at 0d** — the predicate never moves, so it was never a gate.

🔴 **Resolution (HK-021(o)):** the quantum is one decode. The bar is exact zero. There is no
"nearly".

### G2 — how much each layer is worth, descriptive, NOT gated

Report, per layer, the number of *(own-call, decode)* pairs recovered: L1 alone (2-token parse),
L2 alone (bracket strip), L1+L2 together. **No bar, no verdict.** It exists so the Developer session
can size three changes against each other, and so nobody claims a layer's share without a number.

### G3 — the false-positive cost of the own-hash rule

Population: *(hypothetical own-call, hashed-`dest` decode)* pairs where the reference resolved the
slot, so `theirs_name` is known. UNKNOWN pairs are assigned **both** ways and the gate reports an
interval (ARM 1D's method, not ARM 1C's filter).

> **G3-1 (FAVOURABLE):** `fp_max / n_fires_max` has a CP one-sided 95% **upper** bound **< 0.0100**.
> **G3-2 (UNFAVOURABLE):** `fp_min / n_fires_min` has a CP one-sided 95% **lower** bound **> 0.0500**.
> **G3-3:** otherwise **INDETERMINATE**.

Rows are mutually exclusive and evaluated in strict order. `fp` counts pairs where `to_us_l3` fires
and `theirs_name != ours`; `n_fires` counts every pair where it fires.

The bars: the a-priori rate is 1/4096 = 0.000244. 0.0100 is ~41× that — a deliberately slack bar,
because a *cost* gate should be hard to pass, and passing a slack bar is still informative. 0.0500 is
the point at which one firing in twenty is a station we would wrongly answer.

🔴 **Power, against my own stated expectation (proposed sibling HK-021(v), applied voluntarily
pending the Captain's ruling).** My rationale says the true FP rate is near the a-priori 0.000244.
Expected firings across the whole cross-product ≈ 1,553 × 11,233 / 4,096 ≈ 4,258, so `n_fires` is in
the thousands and CP intervals are tight: at a true rate of 0.000244 with n ≈ 4,000, the 95% upper
bound is ≈ 0.0009 — far inside G3-1's 0.0100. **This arm is well-powered for the outcome I expect,
and it would take a true rate above ~0.008 to land INDETERMINATE.** Unlike ARM 1D, the gate can fire
on the squeaker I actually predict. If QA's measured `n_fires` comes out below 400, say so — below
that the bound loosens past the bar and the arm reverts to under-powered.

🔴 **Straddle statement (proposed sibling HK-021(w), applied voluntarily).** For G3, report
explicitly: which row `fp_min/n_fires_min` gives, which row `fp_max/n_fires_max` gives, and whether
the ignorance interval **straddles** either threshold. Width is not the property that matters —
position is. That is the correction that landed on ARM 1D's spec and it is not repeated here.

### G4 — containment by partner binding, descriptive, NOT gated

Of the G3 firings, report the share whose `src` token equals the hypothetical own-call's actual QSO
partner — i.e. how many survive the `fromPartner && toUs` conjunction that `:1081` and `:1163`
already require. ⚠️ There are no QSOs in this corpus, so this must be computed against a
**stated proxy** for "partner" and reported as a proxy, never as a measured containment rate.
If QA judges no honest proxy exists, **report G4 as NOT COMPUTABLE and move on** — that is the
correct answer, not a gap to paper over.

---

## Sec.6 — What no outcome of this arm authorises

- **No `src/` change. No `native/` change. No Developer session.** Sec.8 is a design brief; it is
  authorised by the PO/Captain, not by a favourable G3.
- **No claim about a fixed build.** HK-021(p): no binary carrying L1/L2/L3 exists. Nothing here may
  be phrased as "the fixed build would…".
- **No benefit claim, in either direction.** Zero exposure ⇒ efficacy is unmeasured, and a cost-only
  result is not a verdict on the route. 🔴 **G3 landing UNFAVOURABLE does not kill route 5**; it
  moves the containment of Sec.8.4 from optional to required.
- **Nothing about harm 1** (wrong names displayed and logged). The chosen mechanism does not touch
  displayed text. ARM 1B's A1/51.3%, ARM 1C's VOID and ARM 1D's C3+D3 all stand untouched.
- **No re-reading of a closed gate with a better metric.** This is a new pre-registration with its
  own ROW 0, not ARM 1D with a new column.

---

## Sec.7 — Blind predictions, recorded before the run

Scored honestly afterwards, including the ones that miss.

1. **G1a == 0 — HIGH.** L2 is a literal string comparison against a bracket-wrapped token; there is
   no path around it. If this misses, my code reading is wrong and the spec is withdrawn.
2. **G1b > 0 — HIGH.** 293 resolved hashed-`dest` decodes exist; each names some station.
3. **G3 lands G3-1 (FAVOURABLE) — MODERATE-HIGH.** The Poisson check supports uniformity, so the FP
   rate should sit near 1/4096. The mechanism that could sink it: hashes of *real* callsigns may
   cluster by prefix in a way the aggregate occupancy check cannot see, and the hypothetical-own-call
   cross-product would then concentrate firings.
4. **L2 alone (bracket strip) recovers more than L1 alone — MODERATE.** 293 vs 195, but the
   *(own-call, decode)* weighting could invert that.
5. **G4 comes back NOT COMPUTABLE — MODERATE.** I do not believe an honest partner proxy exists in a
   corpus with no QSOs, and I would rather QA said so than invented one. **Flagged as the prediction
   I most expect to be told I am wrong about.**

---

## Sec.8 — DESIGN BRIEF for a future Developer session (NOT authorised by this arm)

Recorded here so it is not re-derived. **HK-011/HK-015: `src/` and `native/` work is a separate
Developer session with the Captain's sign-off. QA proposes and stops.**

### 8.1 — L1: parse the 2-token Type-4 form
Both copies of `TryParseMessage` (`QsoAnswererService.cs:1631`, `QsoCallerService.cs:1349`) accept a
2-token message with an empty payload. ⚠️ **Two copies** — fixing one is a defect. Consider hoisting
to a single shared helper; that is a design call for the Developer, not a requirement of this brief.

### 8.2 — L2: normalise the `dest` token before comparing
Strip one leading `<` and one trailing `>`; reject `<...>` (all-dot) as not-a-callsign. Precedent for
`dest` normalisation already exists at `QsoCallerService.cs:1385-1394` (base vs compound callsign) —
extend that idea rather than adding a fourth ad-hoc comparison. **Five sites** must move together:
`QsoAnswererService.cs:1079`, `:1161`; `QsoCallerService.cs:938`, `:1393-1394`.
🔴 **L2 alone is a real, self-contained fix that needs no native change and no hash.** It is the
cheapest, highest-certainty part of route 5.

### 8.3 — L3: the TLS side-channel getter (PO-chosen mechanism)
Model on `ft8_get_last_snr_terms` exactly (`ft8_shim.c:589-591` TLS arrays, `:1186-1200` getter,
contract in `ft8_shim.h`): per-decode `n12`, `iflip`, `icq`, index-aligned with `results[]`, captured
where `tls_signal_db` is already captured (`ft8_shim.c:1531`). Values come from
`ftx_message_decode_nonstd` (`message.c:400-434`), which computes and currently discards them.

- **No `FT8Result` struct change** — stays 48 bytes, no ABI break, existing startup size assertion
  unchanged. **No change to any displayed name.**
- Shim version bumps past `20260046` so the startup ABI check catches a binary without the export.
- Managed side: a new `IFt8NativeInterop` member and a per-decode field on the managed result. The
  answerer then compares `n12 == Ihashcall(ourCallsign, bits: 12)` —
  `Ft8CallsignPacker.Ihashcall` already exists (`Ft8CallsignPacker.cs:165`, `:170-200`).
- ⚠️ **`iflip` decides which slot the hash is in.** Route 5 must fire only when the hash occupies the
  `call_to` slot — a hash in `call_de` is the *sender* being hashed, not us being addressed.

### 8.4 — Containment of the false positive
8 stations in this corpus alone share our 12-bit code. Recommended, and the reason G4 exists:

- In **partner-bound states** (`WaitReport`, `WaitRr73`), the existing `fromPartner && toUs`
  conjunction already contains the FP to "the station we are mid-QSO with sent a Type-4 addressed to
  a call colliding with ours". Adopting L3 there costs essentially nothing.
- In the **unengaged** state, no partner is bound, the FP is live, and a false fire means
  transmitting to a station that did not call us. **That case needs its own decision** — it is not
  covered by a favourable G3, which measures a rate, not a consequence.

### 8.5 — What the Developer session must measure that this arm cannot
Efficacy. It needs a transmitting station, a nonstandard-callsign correspondent, and a build with
L1+L2+L3 compiled in. Until that exists, route 5's benefit is **asserted from the protocol, never
measured**. Say it that way.

---

## Sec.9 — Residual assumptions that may not be dropped

1. **Reference ground truth.** `theirs_name` is WSJT-X's resolution, used because HK-026 forbids
   bounding our decoder's blind spot with our decoder. It is a wider aperture, not an oracle.
   ARM 1B's scoping caveat rides beside every G3 figure.
2. **Hypothetical own-calls are a stand-in.** The FP rate is measured over stations that were
   actually addressed; our own call was not one of them. The hash is call-independent, which is why
   this substitution is defensible — but it is a substitution, and it is stated at every figure.
3. **Zero exposure is a property of the corpus, not of the world.** "We observed no calls directed
   at us" says only that we never transmitted.
4. **The 8 colliding callsigns are a lower bound** on who could collide with us — 4 days, 2 bands,
   one antenna. A wider corpus finds more.
