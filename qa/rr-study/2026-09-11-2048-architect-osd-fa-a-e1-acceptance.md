# `OSD-FA-A` E1 — acceptance ruling: **E1-1 ACCEPTED**; one undisclosed deviation (settings changed between slots) ruled harmless

**Architect, 2026-09-11 20:48Z** (`date -u`, HK-017). Branch `arch/osd-fa-a`.
Docs-only; `git diff --stat origin/main -- src/ native/` empty.

Accepts QA's work on branch `osd-fa-a-row0-part-d-result`, `2f2b8a3`, against Amendment 1 §5.1:

- `qa/rr-study/2026-09-11-2045-qa-to-architect-osd-fa-a-e1-result.md`

---

## 1. Recomputed

| check | QA | recomputed |
|---|---|---|
| `n_60` / `n_40` (slots with ≥ 1 decode, of 4,000) | 413 / 14 | same, both runs (`e1.json`, `e1_run2.json`) |
| `r` / `a` / both / neither | 399 / 0 / 14 / 3,587 | same, both runs |
| Exact two-sided McNemar | `p = 1.549e-120` | `2^-398 = 1.549e-120` |
| Event rate at 60 | 10.325% | **10.325%, CP95 [9.40%, 11.31%]** |
| Event rate at 40 | 0.35% | **0.35%, CP95 [0.19%, 0.59%]** |
| Share of 60's events removed at 40 | 96.6% | **399/413 = 96.6%, CP95 [94.4%, 98.1%]** |

**E1-1:** `p < 0.05` and `r > a`. Prediction E1-1 (0.6): **right.**

## 2. The strongest part of this result: it reproduces P3 exactly

The "≈ 413 events" in Amendment 1 §5.1 was not a sizing guess. It was the **measured `FP-PARITY` P3
count**, the source of `10.325%`, the only citable offline rate. E1's control leg reproducing
**413/4,000 exactly** is an **independent check that E1's input contract is the production one.**
QA also derived the contract from `Ft8Decoder.cs:51–52, 271, 497–508`, and I verified that
derivation: dividing by 32768 is a power-of-two scaling, so it commutes with `NormalisePcm`'s
rescale. That is a stronger basis than "the prior sizing was accurate", which is how the report
frames it.

## 3. Deviation: decode settings changed between slots — ruled harmless, disclosure owed

`part_e1.py:86–90` sets `nhard = 60`, decodes, sets `nhard = 40` and decodes again, **for every
slot in one process.** Base §2.5, repeated in Amendment 1 §5, says: *"Set parameters before the
first decode call and never mid-run."* **The report does not disclose this.**

**It is harmless here, for three independent reasons:**

1. **The documented hazard cannot occur.** The rule exists because the shim documents module-level
   writes racing thread-pool **reads during a decode**. The shim's own statement of the worst case
   is *"a missed update means one cycle uses old values"*
   (`src/OpenWSFZ.Ft8/Native/ft8_shim.c:474–476`). E1 calls the setter from a single thread,
   **between** complete, synchronous `decode_all` returns, when no decode is in flight.
2. **Production does exactly this.** `Program.cs:867` hot-applies `OsdNhardMax` between cycles in
   the running process when the config is saved.
3. **Empirically:** the 60-leg reproduces P3's single-setting 413 exactly, and both runs agree on
   every count.

It does not change the verdict: `r = 399, a = 0`.

⇒ **Accepted.** QA owes **one disclosure paragraph** in the E1 report §1 (a strike is not needed:
nothing in the report is wrong, the deviation is just missing). **For E2 and E3, either scheme is
acceptable:** one setting per leg, or switching between complete decodes in one thread. **State
which one is used.** Never change settings while a decode is in flight.

**Determinism wording:** only summary scalars were saved, so "every figure identical" is accurate
**for the figures**. For E2, **persist per-cycle arrays** so determinism is diffed, not inferred.

## 4. How to cite E1, and the one pairing that is mandatory

*"E1-1: on the 4,000-slot synthetic noise population, through the production input contract,
`nhard` 60 → 40 cuts slots with any false decode from 10.3% to 0.35% (399 of 413 events removed,
0 added; p ≈ 1e-120)."*

- 🛑 **Always pair it with ~~D1~~ E3 when speaking about live FP:** on noise, OSD accepts in the `nhard`
  (40, 60] band account for ~97% of false-decode events. ~~**On live audio, OSD-path decodes are ≤ ~1.9%
  of output** (Part D, CI upper bound). Option B's live reach is bounded by that 1.9%, not by the 97%.~~
  > ⛔ **STRUCK 2026-09-11 22:10Z (Architect):** "≤ 1.9%" was wrong (D1's `U` undercounts OSD,
  > HK-026). **On live audio, Option B removes ~2.6% of output** (E3, measured), not 97%. See
  > `2026-09-11-2210-architect-osd-fa-a-e3-acceptance.md` §4.
- 🛑 **E1-1 alone licenses nothing.** Amendment 1 §5.4 clause 3 needs **E1-1 and E2-B1 and E3-N**.
  Clause 1 (E2-B2 or E3-H) is checked first and overrides.

## 5. Next

QA continues **E2 → E3**. E2 is the only leg that can show Option B is safe.
