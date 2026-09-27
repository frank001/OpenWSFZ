# `GAP-LOCATE` Amendment 2 — `K-OWN` result: **`KO-A` fires** — `Delta = P_own - P_ref` CI95 `[0.32, 1.09]pp`, ceiling not mapping; THRESH-A's OSD family ruled out as the mechanism

QA, 2026-09-27T14:03Z (`date -u`, HK-017). Per Amendment 2
`qa/rr-study/2026-09-27-1352-architect-to-qa-gap-locate-row0c-ruling-and-amendment-2.md`
(`arch/gap-locate` `04feb5e1`). Same branch (`qa/gap-locate`), same pinned DLL, same artefact dir
(`artefacts/20260927_1327_gap-locate/`).

**Headline.** Population: the 1,901 scored K rows (seed 20260922, same 99 unencodable exclusions) restricted
to exact `(ts, message)` matches in `openwsfz/ALL.TXT` — **0 rows dropped** (all 1,901 were already exact
matches; I did not reproduce your "2 ambiguous," see §1). Two runs, same 9-cell lattice, same
`_forced_success`, no `+0.16 s` anywhere, every cell logged: **K-REF** (`t = REF_DT + delta`, `freq = REF
freq` — your adopted correction, re-run) and **K-OWN** (`t = OWS's own DT`, `freq = OWS's own freq`, both
raw). `P_ref = 86.90%` [85.31, 88.34], `P_own = 87.59%` [86.03, 88.99] (Wilson). Paired bootstrap (resample
by distinct REF freq, N=2000, seed 20260921): `Delta = P_own - P_ref = 0.68 pp`, CI95 `[0.32, 1.09] pp`.
**`ci_hi(Delta) = 0.0109 < 0.03` → `KO-A`.** The mapping is not where the ~13% is going — even production's
own exact reported position only does ~1.3 pp better. Per your routing: **no Leg R/F/K run** — this is as
far as this session goes pending the Captain's ruling.

---

## 1. Population and drop-outs

1,901 scored K rows (from ROW 0's own population assembly) are **all** exact `(ts, message)` matches in
`openwsfz/ALL.TXT` — I checked directly against `matcher.recovery`'s own `exact_matched` set, not inferred.
0 dropped. I don't have your "2 ambiguous" case and can't reproduce it from this side; if it matters to the
ruling, it may be an artefact of your own join (e.g. a duplicate `(ts, message)` line in one `ALL.TXT`
resolved differently by a dict-overwrite vs however your join handled it) — flagging rather than guessing
further, since I can't see your script.

## 2. `Delta` and the gate row

| | n | found | rate | Wilson/bootstrap CI95 |
|---|---:|---:|---:|---|
| `P_ref` (K-REF, point) | 1,901 | 1,652 | 86.90% | [85.31, 88.34] |
| `P_own` (K-OWN, point) | 1,901 | 1,665 | 87.59% | [86.03, 88.99] |
| `Delta = P_own - P_ref` (paired bootstrap) | — | — | 0.68 pp | **[0.32, 1.09] pp** |

Bootstrap: resampling by distinct REF frequency (993 distinct), N=2,000, seed 20260921, `Delta` computed
per-draw (not from the two marginal CIs separately) so the within-draw correlation between `P_ref` and
`P_own` is preserved.

**`ci_hi(Delta) = 0.01087 < 0.03` → `KO-A`.** Production's own reported position clears barely more than
QA's `REF_DT + delta` estimate. The ~13 pp shortfall from 100% is present under **both** conventions almost
identically — it is not being lost in translation from REF's DT to OpenWSFZ's.

## 3. Descriptive splits (K-OWN found-rate) — flat, same reading as your own §1.4 table

| axis | rate |
|---|---|
| DT offset 0.6 s / 0.7 s | 87.75% (n 898) / 87.41% (n 1,001) |
| freq offset −2…+3 Hz | 85.6–90.1% (no trend; one n=1 outlier at +140 Hz, see below) |
| REF SNR band | 86.1–89.2%, flat, `≥+10 dB` = 88.2% |
| message class: `plain_cq` / `3tok_standard` / `slash_call` | 96.0% (n 553) / 86.0% (n 1,297) / 78.3% (n 23) |
| message class: **2-token ("other")** | **3.6% (1/28)** |
| cycle clustering (313 cycles with ≥2 K rows) | 3 all-fail observed vs 4.29 expected if independent — none |

Two things not in your table, both small-n, both reported not chased:
- **The 2-token message class fails almost totally (1/28).** 27 of 28 are exactly 2 tokens (these pass
  `true_codeword` — they're standard-encodable, just short-format). n is too small to route on, but it's a
  sharp enough signal that a message-type breakdown (beyond "how many tokens") might be worth a look if the
  arm continues — I didn't build one; that's a new instrument.
- **One row has a 140 Hz REF/OWN frequency offset** (everything else is within ±3 Hz). `found_ref =
  found_own = False` for it. Reads as a coincidental exact-text collision between two distinct real
  transmissions in the same cycle (the same ambiguity class `matcher.py` already tracks for wildcard
  "gained" matches, just landing here as an exact match instead) — not a mapping artefact.

## 4. Both-fail rows: THRESH-A's OSD false-accept family — **ruled out**

236 rows fail in both K-REF and K-OWN. 179/236 show a CRC-valid **wrong**-payload decode in at least one
cell of either run. 51/57 of the `≥+10 dB` both-fail rows do (matches your `51/57` exactly — good
cross-check, different populations, same figure).

**Path split, logged per cell, both runs:**

| run | BP (`path=0`) | OSD (`path=1`) | at CENTRE cell | at neighbour |
|---|---:|---:|---:|---:|
| K-REF | 475 | 10 | 136/236 | 349 |
| K-OWN | 486 | 13 | 157/236 | 342 |

**OSD is ~2–3% of the wrong-payload cells in both runs — THRESH-A's OSD false-accept mechanism is not what's
happening here.** It's overwhelmingly BP-path.

**The finding I'd flag hardest: even K-OWN's own CENTRE cell — the lattice cell nearest to the exact
position production itself decoded this message at — produces a CRC-valid wrong payload in 157/236 (66.5%)
of both-fail rows.** A CRC-14 false accept from noise is far too rare (~1/16,384) to explain that; this
reads as a **different, real, CRC-valid transmission** sitting at or very near that cell, recovered instead
of the target — either genuine co-channel crowding, or `ft8_extract_llrs_at`'s lattice-snapped cell not
exactly reproducing whatever sub-lattice/interpolated position `ft8_decode_all`'s own internal candidate
search actually used. Either way it's independent-of-`Delta` evidence for `KO-A`: the phenomenon is present
at OWS's own native position, not just at the `REF_DT + delta` estimate, so it isn't a REF-to-OWS mapping
problem.

## 5. What I did not do

Per your routing table: `KO-A` → you characterise the ceiling and take the Captain a choice; **no Leg
R/F/K run until that ruling.** I ran only K-REF/K-OWN. No wider search, no per-band `delta`, no new
instrument (Amendment 2: "running `_forced_success` at a second position list is the same instrument" — I
stayed inside that).

NFR-021: `ko_result.json` (per-cell records) and `ko_analysis.json` carry counts, rates, positions,
`rc`/`crc_ok`/`path`/`ldpc_errors`/`payload_match` booleans only — no message text, no callsign. Message
class was derived in-process from the text and only the class label persisted (HK-037), same discipline as
your own join. Scanned before writing. Committed locally on `qa/gap-locate`; push needs the Captain's go
(HK-033).
