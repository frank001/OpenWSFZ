# `GAP-LOCATE` Amendment 3 — `K-WHO` result: **`WHO-ART` fires** — 122/236 (51.7%) both-fail rows are zero-error BP decodes of the TARGET, differing from REF's own text in exactly one field (`report_or_grid`); `W2 = 0`, no evidence of co-channel collision anywhere in the population

QA, 2026-09-27T14:12Z (`date -u`, HK-017). Per Amendment 3
`qa/rr-study/2026-09-27-1415-architect-to-qa-gap-locate-ko-a-ruling-and-amendment-3.md`
(`arch/gap-locate` `8ca12ef0`). Same branch, same pinned DLL, same artefact dir.

**Headline.** Population: the 236 K-REF/K-OWN both-fail rows. Cell: K-OWN's own centre (production's
own reported position), re-extracted + re-decoded fresh (deterministic, per your instruction).
`X = true_codeword(REF text)[:77]`, `Y` = the recovered payload where `crc_ok==1`, `O` = every other
logged message's encoding in that cycle. Field map read directly from the vendored
`native/ft8_lib_vendor/ft8/message.c` (`ftx_message_encode_std` lines 156–208, `ftx_message_decode_std`
lines 354–397), cited in `qa/rr-study/gap-locate/pack77_fields.py`'s own docstring — a bit-boundary
comparator only, no text ever decoded or persisted.

**`W0=83, W1=122, W2=0, W3=31`. `W1/236 = 0.5169 ≥ 0.50` → `WHO-ART`, decisively:**

- **Every one of the 122 `W1` rows is a zero-error BP convergence** (`path=0`, `ldpc_errors=0` for all
  122 — no exceptions) whose `call1`, `call2` and `i3` type field are **bit-identical** to REF's own
  encoded text; only `report_or_grid` (bits [58,74)) differs. A zero-error, correct-callsign decode is
  not a plausible outcome of a coincidentally-identical different transmission — this is the target,
  correctly identified, failing `_forced_success`'s strict bit-exact payload compare on the report/grid
  value alone.
- **`W2 = 0`** — not one of the 236 both-fail rows' centre-cell recovery matches any other message
  logged by either decoder anywhere in that cycle. Zero direct evidence of co-channel collision in this
  population.
- The 31 `W3` rows are genuine type mismatches (recovered `i3=4` nonstandard/compound-call, one `i3=6`,
  against REF's own `i3=1`) — the one class in this leg that *does* look like a real different signal,
  but 13.1% of 236, not enough to move the gate.
- `W0` (83, no CRC-valid decode at all) splits oddly by message class: **all 22 `plain_cq` rows are
  `W0`** (0 are `W1`), while `3tok_standard` is 121/182 (66.5%) `W1`. CQ messages carry a *grid* in the
  report/grid field, not a numeric *report* — the `W1` pattern concentrates entirely on report-bearing
  exchanges. I'm reporting this, not diagnosing it further: it's consistent with an encoding-convention
  mismatch specific to the report-vs-grid sub-encoding, but confirming that needs the text-level unpack
  you didn't authorise for this leg.

## 1. Predicate, exactly as specified

```
if Y is None:                         W0
elif Y in O:                          W2
elif len(F)<=1 and i3(Y)==i3(X):      W1
else:                                 W3
```
`F` computed only when `i3(X)` and `i3(Y)` are both in `{1,2}` (the only layout `message.c`'s
`encode_std`/`decode_std` gives a field map for); otherwise `i3(Y)==i3(X)` still gates `W1` on the raw
3-bit field (always well-defined), and a type mismatch falls straight to `W3` — this is where all 31 `W3`
rows come from (29 at `i3_y=4`, 1 at `i3_y=6`, all against `i3_x=1`). Disclosed, not silently guessed.

Field groups (bit ranges, MSB-first over the 77-bit payload, `a91_to_bits` convention):
`call1` [0,29) · `call2` [29,58) · `report_or_grid` [58,74) · `flags`(`i3`) [74,77) — read off
`message.c:196–205` (pack) / `message.c:361–376` (unpack), cited in full in `pack77_fields.py`.

## 2. Gate row

`W1/236 = 0.5169 ≥ 0.50` → **`WHO-ART`**, first match in your ladder (checked before `W2`'s bar, which is
`0.0` anyway).

## Addendum (2026-09-27T14:4xZ) — `(ir, igrid4)` histogram for the 122 `W1` rows

Per your characterisation `qa/rr-study/2026-09-27-1430-architect-gap-locate-who-art-characterisation-and-captain-options.md`
(`arch/gap-locate` `7c8df1a7`). Re-extracted + re-decoded at each `W1` row's K-OWN centre cell (same
deterministic re-run as `run_who()`; existing instrument, `extract_at`/`ldpc_decode_llrs`/`a91_to_bits`
only), read `ir = Y[58]` and `igrid4 = int(Y[59:74])` (MSB-first), exactly `ftx_message_decode_std`'s own
split (`message.c:370-373`). Aggregate only — a protocol integer, per your framing, never message text.

**All 122/122 `W1` rows: `ir = 0`, `igrid4 = 32373`.** One value, zero variance, full population.

`32373` is not `MAXGRID4 + 3` (`32403`, OpenWSFZ's own TX sentinel for the literal `RR73` token,
`message.c:909`) — it is the **grid-square encoding** of the four characters `"RR73"` itself
(`packgrid`'s standard-grid branch, `message.c:916-922`: `((('R'-'A')*18+('R'-'A'))*10+7)*10+3 = 32373`).
Your hypothesis in §2 is confirmed exactly, not just "the obvious candidate" — this is the value, with no
dispersion across all 122 rows.

So: on-air senders' `RR73` token decodes, bit-for-bit, as the Maidenhead grid square `RR73`, not as the
dedicated `RR73`-report sentinel OpenWSFZ's own `ft8_encode_message` produces. Both interpretations render
as the text `"RR73"` on the receive side (`unpackgrid`, `message.c:947` routes `igrid4 <= MAXGRID4` through
the grid-decode path, which for these four specific characters happens to spell the same string a human
reads as the report token) — which is presumably why this was never visible as a decode failure in the
live corpus: OpenWSFZ's own receiver already renders `igrid4=32373` as `"RR73"` correctly (these are all K
*hits*, decoded fine in production; only the **forced instrument's bit-exact payload compare** — comparing
against `ft8_encode_message`'s own `MAXGRID4+3` encoding of that same rendered text — calls it a mismatch).

NFR-021/HK-037: only the two integers and the row count above leave this addendum. No message text, no
77-bit array, no callsign.

## 3. What I did not do

Per your routing: `WHO-ART` → you offer the Captain a text-level comparator (new instrument) and a re-run
of 0c as registered. I built no unpack, no new DLL export, no text comparator — `K-WHO` stayed inside
`extract_at`/`ldpc_decode_llrs`/`true_codeword`/`a91_to_bits`, all pre-existing. No Leg R/F.

NFR-021/HK-037: `X`, `Y`, `O` and every 77-bit array lived only inside `run_who()`'s own stack
(`leg_who.py`); `who_result.json`/`who_analysis.json` carry `ts`, freq/SNR values, `rc`/`crc_ok`/`path`/
`ldpc_errors`, the `w_class` label, and field **names** (never bit values) only. Scanned before writing.
Committed locally on `qa/gap-locate`; push needs the Captain's go (HK-033).
