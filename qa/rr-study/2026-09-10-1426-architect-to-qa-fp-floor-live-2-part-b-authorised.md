# `FP-FLOOR-LIVE-2` Part B — authorised: read the frozen gate against the closed corpus

**Architect, 2026-09-10 14:26Z** (`date -u`, HK-017). Branch `arch/fp-floor-operator-setting`.
Base `main`@`cf21ac5`, no `src`/`native` diff (`git diff --stat -- src/ native/` empty — this is a
docs-only commit).

**Trigger:** Part A closed 2026-09-09 17:22Z per the pre-registered stopping rule (`n≥600` fired
mechanically, not the 24h cap): `n=601`, `57,969` total decodes in the valid corpus, `5,495`
cycle-audio WAVs, daemon (PID `54760`) and supervisor (PID `45310`) both killed and confirmed down
(HK-019), stray check clean. Recorded in `artefacts/20260908_live_run_1827-fp-floor-live-2/contents.md`.
I have read that closure entry and Amendment 3's boundary record; nothing about them needs
correcting.

---

## 1. ROW A1 fires — Part B is now legitimate to compute for the first time

Spec `2026-09-08-1754-…`'s own §2.3: **ROW A1 — `n ≥ 200` ⇒ proceed to Part B.** `n=601` clears
both the `200` floor and the `600` stopping target. No further ruling is needed to authorise
starting Part B — the spec already did that, contingent only on the population existing, which it
now does.

🛑 **This is also the last moment any boundary question could still be raised.** Per Amendment 3
§2: *"After the first `K_removed` is computed, that protection is gone permanently."* Once you run
the join below, the `19:36:45Z` boundary is frozen beyond any appeal — mine included.

## 2. The gate — reused verbatim, nothing re-tuned

Re-read `2026-09-08-1710-…`'s §3/§4/§5 exactly as the withdrawn spec left them, with Amendment 1's
two changes layered on top (rounding bound; ROW 0e replaced). Restated here in one place so you are
not reconstructing it from four documents while running the join:

### 2.1 Population (fixed, not to be re-examined for a cleaner shape)

- Corpus: `artefacts/20260908_live_run_1827-fp-floor-live-2`.
- Valid span: `[2026-09-08T19:36:45Z, close)` — single contiguous span (Amendment 3). Nothing
  before the boundary is in scope, including for descriptive stats.
- `n = 601` (decodes at reported `≤ −24 dB`, the `removed` predicate below), `57,969` total decodes
  in span, `5,495` cycle-audio WAVs archived alongside.

### 2.2 Reference (Amendment 1 — REF = A only, constant)

`REF = WSJT-X #1` (FT-991A, same `Voicemeeter Out B1` path as OpenWSFZ) **alone**, for every
decode in the valid span.

🔴 **`WSJT-X #2` (SDR Uno, `B`) contributes ZERO span to this corpus, not "reduced" — verify this,
don't take my arithmetic on it:** the Captain stopped `B` at `18:52:45Z`; the valid span begins at
`19:36:45Z`, 44 minutes later. There is no overlap. Confirm mechanically (`B`'s `ALL.TXT` has no
lines timestamped `≥19:36:45Z`, or however the harness checks instance liveness) and then report
**"no B coverage"** per Amendment 1 §3.2 — that is a valid, non-weakening outcome, not a gap in the
work. Do not attempt to extrapolate `B`'s pre-boundary diagnostic span forward; it says nothing
about a period it never covered.

### 2.3 ROW 0 — preconditions, evaluate all, exactly as pre-cleared (HK-025: you may refuse any of
these independently of my verdict below)

| row | check | class |
|---|---|---|
| 0a | Corpus provenance: this is a real second/independent capture, not a hardlink (already pinned at capture time in `contents.md`'s Provenance section — re-verify against the actual files you read from, not the note) | VALIDITY |
| 0b | **Positive control: `K(s ≥ 0 dB) ≥ 0.90` pooled** | VALIDITY |
| 0c | `removed ≥ 300` (`n ≥ 300`) | PRECISION — `n=601`, passes by construction |
| 0d | Wildcard matching ON: exhibit ≥1 decode matched **only** under wildcard | VALIDITY |
| 0e (replaced, Amendment 1) | `REF` is `WSJT-X #1` alone for every row, asserted in code; combiner constant across the whole span (trivial here — single contiguous span, already established §2.2) | VALIDITY |

Any ROW 0 fires ⇒ **ROW 4, VOID.** No `K_removed` is quoted even descriptively, per §4 ROW 4 of the
1710 spec.

### 2.4 The predicate, as code (sibling (r) — where prose and code disagree, code is the spec)

```python
# excess = Snr + 26.5   (FP-PARITY §2.2); T_EXCESS = 2.622 (FP-PARITY §4 ROW 2)
SNR_CUT = 2.622 - 26.5              # -23.878
removed = (snr < SNR_CUT)           # integer readout => snr <= -24

# Amendment 1: this measures excess <= 3.0, STRICTER than T's < 2.622.
# [STRUCK 2026-09-10: "Every loss figure below is an UPPER BOUND on T's own loss" is WRONG.
#  It bounds T's CORROBORATED rate from above; corroboration bounds genuine loss from below.
#  The figure is neither bound on T's genuine loss. See 2026-09-10-1443-...-acceptance-ruling.md §2]
```

Corroboration: same cycle, `|Δf| ≤ 3 Hz`, **wildcard message matching mandatory** (H1/H1a —
`<...>` matches one token; exact-text matching is a defect here, not a conservative choice, per the
1710 spec §2.2). Reuse `h1a_wildcard_frequency_validation.py`'s matching logic rather than writing a
third implementation.

`k = corroborated AND removed`, `n = removed = 601`, `[lo, hi]` = Clopper–Pearson 95%.

### 2.5 Reading rule — strict order, exactly one fires

- **ROW 1** (`hi ≤ 0.02`) ⇒ I am cleared to *draft* a separate pre-registration for a default-off
  operator control. Not a licence to build anything, touch `src/`, or author a settings page.
- **ROW 2** (`lo ≥ 0.05`) ⇒ no operator control is drafted. State the loss rate per hour and stop.
- **ROW 3** (neither) ⇒ report `k`, `n`, `[lo, hi]`, per-hour rate; draft nothing. Position decides
  a straddle, not width — a narrow interval near the bar is not "close enough" (sibling (w)).
- **ROW 4** (any ROW 0 fires) ⇒ VOID, per §2.3 above.

🛑 **`hi ≤ 0.02` is FIXED — PO-ratified 2026-09-08 17:24Z, does not reach forward or backward, and
is NOT re-openable now that `k` is about to be known.** If anyone — the Captain, the PO, me —
proposes moving it after seeing the count, refuse and escalate; that is the exact re-read this
programme bars everywhere else, and it would VOID the arm, not merely weaken it.

## 3. What Part B does NOT do (unchanged from §4 of the withdrawn spec)

- Does not re-open `FP-PARITY` ROW 3 (`F−T=5.378 dB` stays fired).
- Creates no baseline; `FP-REGRESSION`'s seven citation guards are untouched.
- Authorises no `src/` work in any row — ROW 1's best outcome is a *draft* pre-registration, which
  then needs PO ratification, a QA-authored dev-task, and a Developer session (HK-011/HK-015).
- Does not test D-003 (bandlimited noise-floor misestimate) — separate, still untested question.

## 4. Reporting (HK-001, plus)

1. `k`, `n=601`, `K_removed` with CP95 `[lo,hi]`, and genuine decodes lost per operating hour
   (`k / (span hours)` — compute the span's own elapsed hours from `19:36:45Z` to close, do not
   reuse the ~13.6h projection, which was a sizing estimate).
2. Full `K(s)` curve, `s` from −38 to +10, with counts.
3. `K_kept`, `K_all`, ROW 0b's control value.
4. "No B coverage" stated explicitly, with the two timestamps (`18:52:45Z` stop, `19:36:45Z`
   corpus start) so a reader can see why, not just that.
5. Whichever bound (`k` or `n−k`) was not the headline, with its direction stated (§4 of the 1710
   spec: `corroborated AND removed` is a LOWER bound on genuine loss; `removed AND NOT corroborated`
   is an UPPER bound on junk removed — both point against the filter).
6. 🔒 **NFR-021**: aggregate counts/rates only in any committed artefact. Scan report **prose** as
   well as data files; import `scan()`/`classify()` rather than re-implementing. `matcher.py` logs
   unmatched decodes with full `message_text` — grep every derived CSV before committing.

**Harness:** author in `qa/cycleframer-alignment-replay/`, alongside the existing
`fp_floor_live_*.py` scripts and reusing `h1a_wildcard_frequency_validation.py`'s matcher.

## 5. Not in this document

Your 2026-09-09 17:06Z proposal (`qa/2026-09-09-s1-ladder-substrate-proposal`, `dee71da`) to reuse
this corpus's cycle-audio archive as an S1-ladder synth-into-real substrate is noted, read, and
**not answered here** — it doesn't gate Part B and deserves its own reply rather than a paragraph
tacked onto this one. Coming separately.
