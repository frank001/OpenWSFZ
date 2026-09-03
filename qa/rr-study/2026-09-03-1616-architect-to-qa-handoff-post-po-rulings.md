# Architect → QA handoff, 2026-09-03 16:16Z — four PO rulings taken, three documents amended, one new arm

**Architect, 2026-09-03 16:16Z** (`date -u`, HK-017). Branch
`arch/2026-09-02-row0-redaction-and-awgn-fp-amendment`, base `main`@`b4dd754`. **Docs only —
`git diff --stat -- src/ native/` is empty and was verified before committing** (HK-014: local,
nothing pushed).

QA's two reports of 2026-09-03 (`S5-LEVEL` ROW 0, `AWGN-FP` M1–M4) were both accepted. The
Architect verified their load-bearing claims against source rather than inheriting them, and found
**three further defects, all in the Architect's own specs.** They are recorded in the amendments
below, not here.

---

## The four rulings

| # | Question | PO ruling | Where it now lives |
|---|---|---|---|
| 1 | `S5-LEVEL` repair option | **Option 2 — delete `level_dbfs`, S5 is single-level** | `2026-09-02-2002-…-s5-level-…md` **Amendment 1** |
| 2 | `F-001` L3 gate wording | **`tls_h12_lookup_performed && !tls_h12_resolved`** — the `== 1` parenthetical was the Architect's slip and is withdrawn | `2026-09-02-1631-…-f001-l3-…md` **Amendment 1** |
| 3 | The offline/in-chain rate gap | **Open it — cheap audit first, no hardware** | `2026-09-03-1616-…-fp-parity-and-inchain-floor.md` (new arm) |
| 4 | The emission-filter dev-task | **Hold** until the in-chain genuine excess floor is measured | same new arm, ROW 1 → ROW 2/3 |

## What QA does, in priority order

1. **`S5-LEVEL` Option 2 execution** — the deletion, under the amendment's ROW 0j/0k/0l gates.
   🔴 Not a free edit: **two** code paths read the key, and the second one
   (`run_scenario.py:1113`, `true_snr_db`) is not the amplitude path. 🛑 Do **not** touch
   `awgn-fp-replay/scenarios/` — there the key is functional. The STOP branch (revert, keep the
   record correction only) is real; take it rather than chasing bit-parity.
2. **`FP-PARITY`** — the new arm. Start with **ROW 0q** (pure analysis of CSVs already on disk,
   minutes) then **ROW 0m** (the independent in-chain recount). Both are zero-run. Read
   `qa/ARTEFACT_INVENTORY.md` **first**.
3. **M1–M4 report record correction** (`AWGN-FP` Amendment 2 A2.4) — §4's "matches M1 exactly" is
   wrong: 454 decode **rows** over 435 **slots**. ROW 2 unaffected. Correct the sentence and §2's
   table; restate nothing else.
4. **`F-001` L3 dev-task** — unblocked. §0's blocking question is answered: build the **first**
   §2.2 variant. Then re-read L3 spec **Amendment 1 A1.2–A1.3** before running the measurement arm:
   the padding population lands in the new counter, `U[0]` isolates it, and **ROW 0g's floor now
   reads `U_clean = U_total − U[0]`**, not `U_total`. The dev-task itself needs no change beyond
   §0's resolution — the amendment binds QA's *measurement* arm, not the Developer's build.
5. **Shim-renumber dev-task** — unchanged, still the Captain's to open.

## What is NOT authorised

- 🛑 **No hardware capture run.** `FP-PARITY` §5 step 7 is the only route to one, and it needs its
  own pre-registration.
- 🛑 **No emission filter.** ROW 2 authorises a *dev-task*, not a build. `T = 9.146 dB` is
  **withdrawn as a shippable number** — it cuts at reported SNR −17.35 dB, above the −18 dB genuine
  decodes on record (Amendment 2 A2.3).
- 🛑 **No candidate-budget or input-scaling change.** `NormalisePcm` parity is matching the
  production input contract, not scaling input, and may not be varied as a lever.
- 🛑 Nothing pushed or merged by the Architect (HK-014); `src/` work needs a Developer session
  (HK-011).

## Unclaimed, still not taken by anyone

`nfr021_pre_merge_scan.py` directory mode · `matcher.py` FP-window scoping (⚠️ now partly
**superseded in importance** by `FP-PARITY` ROW 0m, which recounts around the matcher rather than
fixing it — if ROW 0m fires, fixing the matcher becomes a real task rather than a tidy-up) ·
`ft8_get_h12_ambiguous_padding_count()` (🛑 explicitly **not required** for L3 — the by-code table
separates padding at row 0 for free; see L3 Amendment 1 A1.2).
