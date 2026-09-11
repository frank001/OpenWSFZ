# `OSD-FA-A` Part D — Mechanism 2 bit-field diagnostic (ruling §3.2): sign-off mismatches are confined to ONE field; every other category's mismatches are scattered across all of them

QA, 2026-09-11 19:35Z (`date -u`, HK-017). Per the Architect's Part D2 ruling
(`2026-09-11-1918-architect-osd-fa-a-part-d2-ruling.md`, `arch/osd-fa-a` `68c6a07`, verified via
`git show` before acting) §3.2. Exploratory, disclosed, decides §3.3 mechanically.

**Field boundaries used** (read from `native/ft8_lib_vendor/ft8/message.c:354-376`
`ftx_message_decode_std`, not assumed from the ruling's field-name *order* — `i3` sits at the
**end** of the 77-bit payload, bits `[74,77)`, despite being named first):
`c28_1 [0,28)` `p1_1 [28,29)` `c28_2 [29,57)` `p1_2 [57,58)` `R1 [58,59)` `g15 [59,74)` `i3 [74,77)`.

**Population:** the D2 sample's own decodes (same seed, same corpus), restricted to unambiguous
`dt` (Mechanism 1 does not apply there) and no `<` token (hash-packing ground removed), where the
probe converges (`out_path ∈ {0,1}`) but its payload ≠ `true_codeword(text)`.

## Result

| category | considered | mismatched | fields hit (decode count) |
|---|---:|---:|---|
| **sign-off** | 928 | **578** | **`g15` only: 578/578 (100%)** |
| CQ | 2,229 | 68 | `c28_1`:68, `c28_2`:68, `g15`:68, `i3`:62, `R1`:34, `p1_1`:32, `p1_2`:29 |
| other | 2,368 | 15 | `c28_1`:11, `c28_2`:11, `g15`:11, `i3`:13, `R1`:7, `p1_1`:7, `p1_2`:5 |
| report (plain) | 1,064 | 1 | all seven fields (single decode) |
| report (`R`+) | 538 | 0 | — |

**Sign-off's 578 mismatches are confined to `g15` alone — never `c28_1`, `c28_2`, `i3`, `R1`, or
either `p1`.** Every other category's mismatches hit **every field simultaneously**, on almost
every mismatched decode (68/68 CQ mismatches touch `c28_1`/`c28_2`/`g15`; 62/68 also touch `i3`).
That is the signature of two genuinely different messages (a wrong match, or a true OSD false
accept) — the callsign fields disagree along with everything else. Sign-off's signature is the
opposite: **both callsign fields agree exactly** (extraction and decode found the right station
pair), and only the report/grid field differs.

## Reading, per ruling §3.3

**Sign-off is confined to a single field that identifies a comparator difference, not scattered
across the payload.** `g15` is exactly the field that encodes `RRR`/`RR73`/`73` sentinels
alongside numeric reports and grid squares (`message.c:906–911`, `unpackgrid`). The callsigns
matching exactly on every one of 578 decodes rules out a wrong-message match; a comparator that
cannot correctly reproduce `g15`'s encoding for this message shape is the only reading consistent
with both facts (right callsigns, wrong report field, in the same field every time).

**CQ / other / report (plain) do not show this signature** — their mismatches are scattered across
every field, indicating genuinely different messages, not a comparator artefact. Per §3.3's own
rule (*"never exclude a category because it fails; only because the diagnostic shows its
comparator is invalid"*), **they stay in.**

## Disposition

**Sign-off is excluded from ROW 0e eligibility, on this demonstrated mechanism, disclosed here.**
CQ, other, report-plain, report-`R` remain eligible unchanged. Proceeding to Part D's third run
(§3.1/§3.4) with this eligibility rule applied.

NFR-021: message text held in memory only for `true_codeword()`/category checks — never printed.
Output above is bit-position and decode counts only.
