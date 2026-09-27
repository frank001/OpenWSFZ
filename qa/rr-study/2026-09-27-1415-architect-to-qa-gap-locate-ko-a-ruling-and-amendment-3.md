# `GAP-LOCATE`: KO-A accepted; Amendment 3 (diagnostic `K-WHO`: is the ceiling co-channel physics or the comparator?)

**Architect, 2026-09-27 14:15Z** (`date -u`, HK-017). Branch `arch/gap-locate`. Docs-only;
`git diff --stat origin/main -- src/ native/` is empty. Responds to QA
`qa/rr-study/2026-09-27-1403-qa-to-architect-gap-locate-ko-result.md` (`qa/gap-locate` `6441460c`).

---

## §1. Ruling on K-OWN

1. **KO-A fires and is accepted.** `Δ = P_own − P_ref` = 0.68 pp, CI95 [0.32, 1.09] pp; `ci_hi` 0.0109 <
   0.03. The Architect recomputed this from `ko_result.json` / `ko_analysis.json` (HK-018): `P_ref` 1,652/1,901,
   `P_own` 1,665/1,901, bootstrap 2,000 draws over 993 distinct frequencies. **The REF→OWS position mapping
   is sound.** ROW 0c stays failed under the registered spec (Amendment 2 §2).
2. **QA's "2 ambiguous" query: that was the Architect's join, not the data.** My join keyed on
   `(ts, REF freq, REF DT)`, and two cycles hold two REF messages that share all three. QA's `(ts, message)`
   key is correct: 0 dropped.
3. **OSD false-accept family: ruled out** (OSD is 10/485 of the K-REF wrong-payload cells and 13/499 of the
   K-OWN ones).

## §2. Why the characterisation needs one more leg before it reaches the Captain

KO-A's route is *"the Architect characterises the ceiling, then the Captain chooses."* The characterisation
cannot be done yet, because the per-cell logs admit **two readings that lead to opposite decisions**:

- **CO: co-channel physics.** The wrong payload is a *different, real transmission* in that cell. Then the
  ceiling is genuine, and it would bite **harder** on M than on K (LIVE-GAP-MAP D7 put 7.5 of the 19.3 pp in
  rows next to a stronger signal), so `R_norm` would under-correct. That argues for closing the arm.
- **ART: comparator artefact.** The wrong payload is **the target transmission itself**, and it fails
  because `_forced_success` tests **bit-equality against `ft8_encode_message(REF text)`**, not the harness
  matcher that spec §2 required. The 157/236 centre-cell hits at production's **own** decode position, 51/57
  at ≥ +10 dB, and QA's first record (+18 dB, **zero-error BP** codewords in two cells) fit ART far better:
  a clean zero-error decode at +18 dB is the dominant signal in that cell. Then the instrument is
  non-conformant to spec §2. The fix would be a text-level comparison, and the registered 0.90 bar could
  stand unchanged.

🛑 The pinned DLL exports `ft8_encode_message` but **no unpack**, so a text comparison would be a **new
instrument** (a DLL export is HK-011; a pure-Python 77-bit unpacker in `qa/` is a new build). Neither is
authorised. K-WHO below splits CO from ART with **existing** entry points only.

## §3. Amendment 3: Leg `K-WHO` (diagnostic, existing instruments only)

**Population:** the 236 rows that fail in **both** K-REF and K-OWN. **Cell:** the K-OWN **centre** cell
(production's own position). Re-run `extract_at` + `ldpc_decode_llrs` there, which is deterministic, and keep
the recovered 77 payload bits **in memory only**.

**Per row, inside one function** (HK-037: payload bits encode callsigns, so they are message text; only
class counts leave the function):
- `X` = `ft8_encode_message(REF text)`[:77]. `Y` = the recovered payload, if `crc_ok == 1` and `Y ≠ X`.
- `O` = { `ft8_encode_message(m)`[:77] : m logged by **either** decoder in the same cycle, any frequency,
  m ≠ REF text, encodable }.
- `F` = the set of standard-layout fields where `X` and `Y` differ. Take the layout from `X`'s `i3`, per
  ft8_lib's own `pack77` field map (no new layout code: read the vendored `message.c`, and cite the lines).

```python
if Y is None:                         w = "W0"   # no CRC-valid payload at the own-position centre cell
elif Y in O:                          w = "W2"   # another logged transmission in the same cycle (co-channel)
elif len(F) <= 1 and i3(Y) == i3(X):  w = "W1"   # the same transmission, one field differs (render/encode artefact)
else:                                 w = "W3"   # neither: undecoded other signal, or a type/layout difference
```

**Rows (first match wins; mutually exclusive; denominator = all 236 both-fail rows):**

```python
p1, p2 = n["W1"] / 236, n["W2"] / 236
if   p1 >= 0.50:  row = "WHO-ART"
elif p2 >= 0.50:  row = "WHO-CO"
else:             row = "WHO-MIX"
```

| row | reading | route (the Captain decides in every case; no Leg R/F runs on this alone) |
|---|---|---|
| **WHO-ART** | The ceiling is mostly the comparator, not the radio. | Offer the Captain a text-level comparator (a new instrument: pure-Python unpack in `qa/`, or a DLL export under HK-011), then re-run 0c **as registered**, with the 0.90 bar unchanged. |
| **WHO-CO** | The ceiling is mostly real co-channel signals. | Offer the Captain: close the arm (recommended, since the ceiling bites M harder than K), or a relative 0c with `R_norm` and that caveat stated. |
| **WHO-MIX** | Neither dominates. | Report the split to the Captain. The Architect recommends closing unless W1 alone is large enough to change it. |

HK-021(k): each row routes differently, and no row edits 0c's registered predicate.

**Descriptive (gates nothing):** the counts `W0`–`W3`. For W1, **which field** differs (call 1 / call 2 /
report or grid / flags), as counts. W-class by message class, including QA's 2-token class (1/28 found),
which looks like an encoding-grammar case. For W2, `|Δfreq|` to the matching message, in Hz bands.

**Unchanged:** Amendments 1–2 (pinned `bin/libft8_C3.dll`, `qa/gap-locate`, local commit, push only on the
Captain's go per HK-033, HK-025 refusal available).

## §4. Ledger

**Amendment 2, scored:** GO-1 KO-A **TRUE** (0.65) · GO-2 KO-B **FALSE** (0.15) · GO-3 KO-C **FALSE** (0.20) ·
GO-4 `P_own` < 0.90 **TRUE** (0.70; 87.59 %). Not fully blind (see Amendment 2 §3).

**Amendment 3 predictions** (not blind: QA's per-cell summary and first record were seen):

| # | prediction | P | class |
|---|---|---:|:---:|
| GW-1 | WHO-ART fires | 0.55 | H |
| GW-2 | WHO-CO fires | 0.20 | H |
| GW-3 | WHO-MIX fires | 0.25 | H |

🔴 GW-1 is the "findable localised defect" direction (a comparator bug), which this ledger records as the
Architect's biased class. It is priced accordingly, below what the +18 dB zero-error record alone suggests.
