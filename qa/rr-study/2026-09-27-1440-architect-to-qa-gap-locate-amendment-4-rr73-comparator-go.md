# `GAP-LOCATE` Amendment 4: `RR73`-equivalence comparator, fresh-sample 0c, then the full arm (Captain: option A)

**Architect, 2026-09-27 14:40Z** (`date -u`, HK-017). Branch `arch/gap-locate`. Docs-only;
`git diff --stat origin/main -- src/ native/` is empty.

**Authorised:** the Captain, 2026-09-27, chose **option A** from `…-1430-…-captain-options.md` §3.
Pre-registered here **before** any datum from the fresh sample exists.

---

## §1. The comparator (it replaces bit-equality in `_forced_success`'s success test, for K and M alike)

```python
RR73_STD = (0, MAXGRID4 + 3)               # (ir, igrid4) as the vendored encoder packs "RR73"

def payload_match(X, Y, ref_text, v_star):  # X = encode(REF text)[:77], Y = recovered [:77]
    if Y == X:
        return True
    if ref_text.split()[-1] != "RR73":
        return False
    fx, fy = fields(X), fields(Y)          # pack77_fields.py (QA, 1efa40c4), message.c-cited
    return (fx.i3 == fy.i3 == 1
            and fx.call1 == fy.call1 and fx.call2 == fy.call2
            and (fx.ir, fx.igrid4) == RR73_STD
            and (fy.ir, fy.igrid4) == v_star)
```

`F_wrong` = a CRC-valid payload for which `payload_match` is False. All else in spec §2 is unchanged.

## §2. ROW 0 (strict order; any fail ⇒ §4 VOID, report and stop)

| row | check | pass |
|---|---|---|
| **0a, 0b, 0d** | as already passed (QA `8c4e617b`) | carried; not re-run unless the DLL copy or loader changes |
| **0f** (new) `v_star` | the modal `(ir, igrid4)` over the 122 W1 recovered payloads from K-WHO (the old sample, which is where the rule was found) | `v_star` covers ≥ 0.95 of the 122. It must not equal `RR73_STD`, and it must not coincide with any `(ir, igrid4)` that a non-`RR73` token produces. Else STOP |
| **0c′** | Leg K on a **fresh** sample K′: REF, hit, SNR ≥ −10 dB, n = 2,000, **seed 20260927**, **excluding every row in the old K** (seed 20260922). Position per Amendment 2 (`REF_DT + δ` raw, no `+0.16 s`), 9 cells, §1's comparator | **`P_ctrl` ≥ 0.90**. That is the registered bar, unchanged. Wilson CI reported, point estimate gates (as the spec's ROW 0) |
| **0e** | as spec §3 (Leg R replay ≥ live in ≥ 0.95 of cycles) | as spec |

## §3. Then: spec §2 Legs R, F and K (K = K′) and §4 rows S1/S0 and LA/LB/LC, **as registered**

- `R_norm = R_F / P_ctrl`, with `P_ctrl` from K′. CIs as spec §2.
- 🔴 D1 must add up to `H10`: S / F / N / **`M_unencodable`** (Amendment 2 §1.3), and **also `M_nonstd_W3`**
  (M rows whose best CRC-valid payload is an `i3` type mismatch) as its own count. That residual is not
  covered by option A, and must be disclosed, not folded into N.
- D2–D6 as spec §5. Add **D7**: F and N split by REF last-token category (`RR73` / `73` / `RRR` / report /
  grid / other). It shows whether the comparator rule is doing work in M.

## §4. What does not change

Amendments 1–2 (pinned `bin/libft8_C3.dll`, `qa/gap-locate`, dated artefact dir, supervised if long,
HK-037 aggregates only, local commits only, push only on the Captain's go per HK-033). Spec §6 predictions
G-2 … G-5 are **still registered and still unscored**, and they score on this run. No new instrument beyond
§1's comparator, which the Captain authorised. HK-025 refusal is available in full: refuse before running.

## §5. Predictions (Architect, registered now)

| # | prediction | P | class |
|---|---|---:|:---:|
| GA-1 | 0f passes (a single `v_star` ≥ 0.95) | 0.85 | C |
| GA-2 | 0c′ passes (`P_ctrl` ≥ 0.90 on K′) | 0.75 | C |
| GA-3 | 0e passes | 0.75 | C |
