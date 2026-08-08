# Architect → QA: spec H1 — how much do `<...>` hash tokens distort the 55.5% and the ~4% FP rate?

**Author:** Architect, 2026-08-08 (21:21 UTC, from `date -u`, per HK-017). Repo `main` at `78fcb0a`.
**Answers:** the open board item of 2026-08-08 — *"~30 min to settle. Recommend it runs before either
figure is quoted further."*
**Bears on:** `2026-08-08-1942-qa-to-architect-four-decoder-live-comparison-two-legs.md` §2.1 (55.5%
recovery) and §2.3 (~4% FP). Both currently carry citation limits that this run either lifts or hardens.
**Status:** pure re-analysis of `ALL.TXT` already on disk and inventory-verified. No `src/` change, no
capture, no rebuild, no Developer session. NFR-021: **no message text and no callsign may appear in
any output, report, or committed harness** — counts and rates only. ⚠️ This run touches the FP
plausibility proxy, which handles callsign tokens; **log only aggregates, never an example.**

---

## 0. The claim being tested, and why it is not what it looks like

`hashTableRejectCount` hit **35 379** on the 20m leg. The 256-slot table (`ft8_shim.c:599-632`) is
process-global and **never re-initialised**, so on a busy band it saturates run-wide. Live effect:
**5.5% of our decodes carry an unresolved `<...>` against the reference's 1.7% — roughly 3.3×.**

🔴 **These are not lost decodes. This is a MEASUREMENT artefact.** `message.c:594-614` writes the
literal `"<...>"` and both call sites discard the return value, so `ftx_message_decode` returns
`RC_OK` and nothing is dropped (an Architect hypothesis to the contrary was raised and **retracted the
same day** — do not re-scope it). We demodulated and error-corrected those frames **correctly**. What
we lost is the callsign *text* — and because both headline figures key on an exact `(ts, message)`
string match, a correct decode whose text reads `<...>` **cannot match the reference**.

So it is counted twice against us:

1. **In recovery** — the reference row it should have matched has no partner, so it scores as a
   **miss**, depressing the 55.5%.
2. **In false positives** — our unmatched row lands in the **novel** bucket, where the plausibility
   proxy cannot resolve `...` either, inflating the ~4%.

**Magnitude has never been measured.** That is all this run does.

⚠️ **Consequence framing, to be stated precisely and not overstated:** if the effect is material, part
of the measured D-001 gap is **hash-table sizing, not decode capability** — and unlike sync
refinement (architectural, expensive) that is a **cheap** candidate treatment. But for the end user a
`<...>` decode is still a decode with a degraded callsign, not a missing one. **Do not describe any
recovery gained here as "new decodes."**

---

## 1. Scope, and the one trap that will silently produce garbage

**In scope:** the 20m leg only, same window as §2.1 and as T1, so the numbers are directly comparable.

🛑 **1.1 The existing harness's source paths are DEAD. Verified 2026-08-08 21:21Z.**
`qa/endurance/2026-08-08-four-decoder-interim-comparison.py:20-23` reads

```
D:/Projects/claude/OpenWSFZ-8080-capture/ALL.TXT      <-- NO LONGER EXISTS
D:/Projects/claude/OpenWSFZ-8081-capture/ALL.TXT      <-- NO LONGER EXISTS
C:/Users/Frank/AppData/Local/WSJT-X - FT991A/ALL.TXT  <-- exists, but has since grown with 17m rows
```

The 20m corpora were **moved** (not deleted) into `_archived_20260808_20m_already-in-artefacts/` when
the leg was gathered. **Re-point every source at `artefacts/`:**

```
artefacts/20260808_live_run_0016-8080/owsfz/ALL.TXT     OpenWSFZ 8080
artefacts/20260808_live_run_0016-8081/owsfz/ALL.TXT     OpenWSFZ 8081
artefacts/20260808_live_run_0016-8080/wsjt-x/ALL.TXT    WSJT-X FT991A
artefacts/20260808_live_run_0016-8081/wsjt-x/ALL.TXT    WSJT-X FT991A-Copy
```

**ROW 0a exists to catch exactly this failure**, so do not skip it even if the run looks healthy.
Keep the `DIAL_PREFIX = "14.074"` filter — the AppData files are append-only and now contain 18.100
rows too.

🛑 **1.2 Do not re-open T1 or T2.** Different thread. `G`, `D_int` and `U` do not appear here.

🛑 **1.3 17m is out of scope.** §2.3 states plainly that the 17m FP analysis was never done on a clean
window and its full-corpus numbers look anomalous. Do not quote or extend them.

🛑 **1.4 No `src/` change and no recommendation to make one inside this run.** If H1 fires ROW 1, the
hash-table remedy goes to the Captain as a *recommendation with a number* (HK-011), never as work
started in-session.

---

## 2. Population and window — identical to §2.1 and T1

- **Window:** `260808_004000` .. `260808_111500` (the 20m clean window).
- **Reference:** intersection of the two WSJT-X instances on `(ts, message)`.
- **Expected reference population: 69 222**, of which **38 440** matched by 8080 = **55.5%**.
- Run `python qa/artefact_inventory.py --check` clean before starting.

⚠️ **Note for comparability:** T1 already excluded reference-side `<...>` rows (1 113) but **not
ours**, so T1's 56.2% is also mildly depressed. That does not affect T1's result — `G` is a
**contrast**, and this is a **level** effect. Do not "correct" T1.

---

## 3. What to compute — three populations, one baseline

### 3.1 `R_base` — reproduce the published number first

Exact `(ts, message)` match, full population, no exclusions. **This must reproduce 55.5%.** It is the
instrument check, not a result.

### 3.2 `R_excl` — symmetric exclusion

Drop every row on **either** side whose message contains `<...>`, then recompute recovery. This is
the clean-population figure: what recovery looks like among decodes where the hash table never
interfered on either instrument.

⚠️ **Symmetric exclusion does NOT credit the mismatched pairs.** If the reference has a fully
resolved message and we have the `<...>` form, dropping our row leaves the reference row in the
denominator, still unmatched, still a miss. `R_excl` therefore answers *"is the clean subpopulation
different?"* — not *"how much did `<...>` cost us?"* That is §3.3's job. **Do not conflate them.**

### 3.3 `R_wild` — wildcard matching, the upper bound

Match a reference row if the exact key matches **or** our message is token-wise identical after
treating each `<...>` token as a wildcard matching **exactly one** token in the same position.
Token count must be equal; only `<...>` positions may differ.

**Implement as exact-OR-wildcard so the match set is a strict superset of §3.1's** — ROW 0c depends
on that property.

**Mandatory ambiguity accounting.** A wildcard row may match more than one reference row in the same
cycle. Report:

- `n_wild_gained` — reference rows newly matched under wildcarding;
- `n_ambiguous` — of those, how many were matched by a `<...>` row that also matched ≥2 reference
  rows, or matched by ≥2 distinct `<...>` rows.

**`R_wild` is an UPPER bound and must always be quoted as one**, because a wildcard match is a claim
we cannot verify from text alone. Quote `n_ambiguous / n_wild_gained` beside it, every time.

### 3.4 The FP side

Recompute §2.3's three-class plausibility table after removing **our** `<...>` rows from the novel
buckets, and report the FP rate estimate before (`F_base`) and after (`F_excl`).

⚠️ **The existing proxy is already partly insulated and you must quantify by how much.**
`2026-08-08-four-decoder-interim-comparison.py:80` strips `<>` from tokens, so `<...>` becomes `...`,
fails `CALLSIGN_RE`, and is dropped from that message's callsign list — and line 83's `if not cs:
continue` **excludes from the denominator entirely** any message whose only callsign-shaped tokens
were hashed. **Report how many rows that silently removed.** An unknown-size silent exclusion sitting
underneath a published figure is exactly the kind of thing this run exists to surface.

---

## 4. Pre-registered gate (HK-021) — two independent gates, each mechanical

Drafted as the code that evaluates it. Rows mutually exclusive, strict order, boundaries explicit.
**Each gate carries its own explicit ROW 0, evaluated first.**

```python
# --- shared instrument checks -------------------------------------------
def h1_row0(r_base, m, ours_hash_share, n_ours_hash, n_ref_pop):
    if abs(r_base - 55.5) > 0.5:
        return "ROW 0a"    # did not reproduce the published number -- wrong sources (S1.1) or window
    if not (0.03 <= ours_hash_share <= 0.08):
        return "ROW 0b"    # our <...> share contradicts the measured 5.5%: not the population we think
    if m < -0.1:
        return "ROW 0c"    # wildcard is a superset of exact; it cannot LOSE matches
    if m > 100.0 * n_ours_hash / n_ref_pop:
        return "ROW 0d"    # more recovery gained than we have <...> rows to gain it with -- impossible
    return None

# --- GATE A: recovery.   M = R_wild - R_base  (pp) ----------------------
def h1_gate_a(m):
    if m >= 2.0:
        return "A-ROW 1"   # material
    if m <= 0.5:
        return "A-ROW 2"   # immaterial
    return "A-ROW 3"

# --- GATE B: false positives.  dF = F_base - F_excl  (pp) ---------------
def h1_gate_b(d_f):
    if d_f >= 1.0:
        return "B-ROW 1"
    if d_f <= 0.25:
        return "B-ROW 2"
    return "B-ROW 3"
```

**ROW 0d is the bound that runs against my own prediction** (HK-021(e)) and it is computed **from the
data, not chosen** — the physical system supplies it. You cannot recover more reference rows than you
have `<...>` rows to recover them with.

### Consequences, as assertions

| row | consequence — what it COMMITS us to |
|---|---|
| **ROW 0a–0d** | **Instrument failure, not a null.** Report the failing check and its value; draw no conclusion in either direction. 0a almost certainly means §1.1's dead paths. Do not repair-and-rerun in the same session without a fresh pre-registration. |
| **A-ROW 1** (`M ≥ 2.0`) | **The 55.5% is materially depressed by a text artefact and must be RESTATED as a bracket** `[R_base, R_wild]` everywhere it is used — including the "~55–64% three-estimate band" and §5's "size of the prize." Assert into the board: **part of the measured D-001 gap is hash-table sizing, not decode capability**, and the 256-slot never-re-initialised table becomes a **cheap** candidate treatment — recommendation to the Captain **with a number**, no session work (HK-011). 🛑 Still not "new decodes" — see §0. |
| **A-ROW 2** (`M ≤ 0.5`) | **The `<...>` concern is CLOSED for recovery.** 55.5% stands as published, un-bracketed. **Remove the caveat from the board** rather than leaving it to decay, and do not raise the hash table as a D-001 treatment again without new evidence. |
| **A-ROW 3** | Report the bracket. Attach `[R_base, R_wild]` as a standing caveat wherever 55.5% is quoted, but **do not restate the headline** and do not promote the hash table to a treatment candidate. |
| **B-ROW 1** (`ΔF ≥ 1.0`) | **The ~4% FP rate must be RESTATED** as `F_excl`, with `F_base` shown as the contaminated original. This **strengthens the case against D-009 Option B**, whose live evidence rests on that FP figure (§7.3 of the 1942 report) — say so explicitly in the Captain's decision record. |
| **B-ROW 2** (`ΔF ≤ 0.25`) | **The ~4% stands** with its existing upper-bound caveat. `<...>` is not what drives it. |
| **B-ROW 3** | Report both figures; quote the ~4% with `ΔF` attached. No restatement. |

⚠️ **The two gates are independent and may land on different rows.** That is a legitimate outcome, not
a contradiction — recovery and FP are different denominators. Report both rows; do not reconcile them
into one verdict.

---

## 5. Architect's recorded predictions (HK-021)

Recorded before QA runs anything. Where a prediction is itself a ROW 0 bar, my being wrong **voids
the run** rather than producing a finding.

| # | prediction | tested by |
|---|---|---|
| 1 | `R_base` reproduces **55.5% ± 0.5** | ROW 0a |
| 2 | our `<...>` share ≈ **5.5%**, reference ≈ **1.7%** | ROW 0b |
| 3 | `M` = **1.5–3.0 pp**. Reasoning, so it can be checked: ~2 500 of our rows carry `<...>`; at most 1 113 of them can already be matching reference rows that are *also* hashed; the remainder over a 69 222 denominator is ~2.0–3.6 pp, and not all of those correspond to a real reference row. | Gate A |
| 4 | **A-ROW 1** — material | Gate A |
| 5 | `ΔF` = **0.5–1.5 pp**, i.e. **B-ROW 3 or B-ROW 1**; less confident than #4 because the proxy is already partly insulated (§3.4) | Gate B |
| 6 | `n_ambiguous / n_wild_gained` **< 15%** | §3.3 |

On T1 I predicted ROW 1 and it came back ROW 3. **Score #4 and #5 against the outcome plainly,
whichever way they go.**

---

## 6. Deliverables

1. Harness `qa/cycleframer-alignment-replay/h1_hash_token_contamination.py`. It **may** import from
   `t1_frequency_quantisation.py` (whose `load()` already reads `artefacts/` correctly) — preferred
   over copying the four-decoder harness, whose paths are dead.
2. Report `qa/cycleframer-alignment-replay/<UTC>-qa-to-architect-h1-hash-token-contamination-results.md`,
   filename and byline both from real `date -u` and in agreement (HK-017), carrying: `R_base`,
   `R_excl`, `R_wild`, `M`; `F_base`, `F_excl`, `ΔF`; the ambiguity accounting; the §3.4 silent-exclusion
   count; **both** gate reads printed as strict ordered traces; predictions #4/#5 scored; and its own
   citation-limits section.
3. **No push, no merge, no `src/` change.** Committing is the Captain's call (HK-010/HK-014).
4. Update `BOARD.md` in the **same edit** as the result (HK-024), and — because both headline figures
   carry citation limits today — **update §8 of the 1942 report too**, or the limits it publishes will
   contradict the board.

## 7. Citation limits set in advance

**May be cited once complete:** `R_base` as the reproduction check; `R_excl` as *"recovery among
decodes where the hash table interfered on neither instrument"*; `R_wild` **only as an upper bound,
always with its ambiguity fraction attached**; `M` and its row; `ΔF` and its row; the §3.4
silent-exclusion count.

🛑 **May not be cited, under any row:** `R_wild` as *"the real recovery rate"* or without its
ambiguity fraction; any recovery gained here described as **"new decodes"** or as a decode-capability
improvement (§0 — the decodes already existed); any 17m FP number (§1.3); any restatement of T1's `G`
(§1.2); and — unless Gate A fires ROW 1 — any claim that the hash table is a D-001 treatment candidate.
