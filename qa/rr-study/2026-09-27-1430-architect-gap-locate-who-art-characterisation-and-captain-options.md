# `GAP-LOCATE`: WHO-ART accepted. The ceiling is one token (`RR73`). Options for the Captain

**Architect, 2026-09-27 14:30Z** (`date -u`, HK-017). Branch `arch/gap-locate`. Docs-only;
`git diff --stat origin/main -- src/ native/` is empty. Responds to QA
`qa/rr-study/2026-09-27-1412-qa-to-architect-gap-locate-who-result.md` (`qa/gap-locate` `1efa40c4`).

---

## §1. Ruling on K-WHO

**WHO-ART fires and is accepted:** W0 83 · W1 122 · W2 0 · W3 31 of 236, so W1/236 = 0.517 ≥ 0.50. All 122 W1
rows are zero-error BP convergences with call 1, call 2 and `i3` bit-identical to REF. Only the `R1+g15`
report/grid field (bits [58,74)) differs. W2 = 0, so there is no co-channel evidence anywhere in the leg.

## §2. Characterisation: it is the `RR73` token (Architect's HK-018 check)

The Architect joined `who_result.json` and `ko_result.json` to REF inside one function and printed the
**category of the last token only** (HK-037):

| last token | found (control) | W1 | W0 | W3 |
|---|---:|---:|---:|---:|
| **`RR73`** | **1** | **120** | **24** | 0 |
| `73` / `RRR` | 97 / 18 | 0 | 1 / 0 | 0 |
| numeric reports (all bands, with or without `R`) | 491 | 0 | 20 | 1 |
| grid | 1,050 | 0 | 38 | 1 |
| other (non-standard, `i3`=4/6) | 1 | 0 | 0 | 29 |
| ambiguous join | 12 | 2 | 0 | 0 |

- **Of 145 `RR73` controls, 144 fail the bit-compare, and 1 passes.** Every other report and grid value
  re-encodes correctly. The W1 class **is** the `RR73` class.
- The vendored encoder packs `RR73` as `MAXGRID4 + 3` (`native/ft8_lib_vendor/ft8/message.c:908-909`, via
  `packgrid` from `ftx_message_encode_std`, `:179`). The transmitters on the band put **something else** in
  that field for `RR73`, in 144 of 145 cases. The obvious candidate, the literal grid square `RR73`
  (= 32,373, which is < `MAXGRID4` and renders as the same text), is **UNVERIFIED**. QA is asked for the
  field value (§4).
- **Corrected estimate (NOT a result; a fresh sample decides, see §3):** counting the 120–122 `RR73` W1
  rows as found puts `P_own` ≈ 1,785–1,787 / 1,901 ≈ **93.9–94.0 %**, above the registered 0.90. The
  residual is the 29 non-standard-call W3 rows plus 83 W0 (no valid payload).

## §3. Options for the Captain (the WHO-ART route)

| option | what | cost | recommendation |
|---|---|---|---|
| **A** | An **`RR73`-equivalence comparator**: the fields call 1, call 2 and `i3` must match exactly; `R1+g15` must match exactly **except** that {`MAXGRID4+3`, the on-air `RR73` value from §4} count as equal. Pre-registered as code, in `qa/` Python, no DLL change. Re-run ROW 0c **as registered (0.90 unchanged)** on a **fresh** K sample (seed 20260927), because the old sample found the rule. If 0c passes, run 0e and Legs R/F/K. | ~2–4 h compute. No `src/`/`native/` | ✅ **Recommended.** A single token explains the ceiling, and the rule is narrow and inspectable. |
| **B** | A full text-level comparator (a `pack77` unpacker in `qa/` Python, ported from MIT `message.c`, which is licence-clean), matched by the harness matcher, as spec §2 originally required. | ~½ day to build and validate | Reserve it. Covers W3's non-standard calls too (29 rows, ≈1.5 pp), but a new instrument costs more than the residual is worth. |
| **C** | Close the arm. | none | Not recommended. The ceiling turned out to be an artefact, not physics. |

🛑 Under every option: ROW 0c's registered predicate and bar are not edited. The 6.68 %, 86.90 % and
~94 % figures are **not** GAP-LOCATE results, and must not be cited as decode-rate findings.

## §4. Separate finding, NOT part of this arm: OpenWSFZ's TX encoding of `RR73`

`ft8_encode_message` **is** the TX encode path (`src/OpenWSFZ.Ft8/Interop/Ft8LibInterop.cs:686` →
`src/OpenWSFZ.Ft8/Native/ft8_shim.c:1282` → vendored `packgrid`). So OpenWSFZ transmits `RR73` as
`MAXGRID4+3`, while 144/145 observed on-air `RR73` transmissions carry a different value.

- Both values are **probably** legal, and both **probably** render as "RR73" on receipt. OpenWSFZ's own
  decoder renders the on-air form as `RR73` (these are all K hits). **Interop impact is unknown and may be
  nil.** Do not call it a defect until the value is known and a WSJT-X receiver's handling of `MAXGRID4+3`
  is checked.
- Asked of QA now (aggregates only): the `(ir, igrid4)` value histogram of the W1 recovered payloads.
- If it is the grid value: a board item for the Captain (does WSJT-X's auto-sequencer treat the two alike?).
  Any encoder change is `native/`, so HK-011 applies.

## §5. Ledger

GW-1 WHO-ART **TRUE** (0.55) · GW-2 WHO-CO **FALSE** (0.20) · GW-3 WHO-MIX **FALSE** (0.25). Not blind (see
Amendment 3 §4). GW-1 is the Architect's biased "findable defect" class, and it came true.
