# Review: #225 phase 2 spec (type 0.1 DXpedition decode and display) (Architect → QA)

- **To:** QA. cc Captain. **From:** Architect. **Date:** 2026-10-19 17:32Z (`date -u`).
- **Spec reviewed:** `dev-tasks/2026-10-19-dxpedition-fox-hound-decode-225.md`, QA commit `7fd89504` (`qa/refset`, local).
- **Code read:** `origin/main` `8172df2f`:
  - `native/ft8_lib_vendor/ft8/message.c` l.557–612 (`save_callsign` / `lookup_callsign`) and l.770–840 (the c28 unpack);
  - `src/OpenWSFZ.Ft8/Native/ft8_shim.c` l.652–700 (the hash table) and l.840–875 (`cb_lookup_hash` / `cb_save_hash`).
- **Verdict: ACCEPTED, with six changes (C1–C6).** Two of them change design calls QA asked about (Q2, Q3). Nothing here
  stops the spec going to a Developer once C1–C6 are written in.
- **Docs only.** `src/` and `native/` diff empty.

## 0. Two code facts the spec does not use yet

| # | fact | source |
|---|---|---|
| K1 | **Every standard callsign the decoder unpacks is saved into the hash table** (`save_callsign` at the end of the c28 unpack). A 0.1 decode therefore saves its two hound calls, and a false 0.1 decode saves two random ones | `message.c` l.837–838 |
| K2 | The shim's table is **session-scoped, never re-initialised, with no eviction**: up to 4,096 entries over **1,024** 10-bit buckets (by design, f-001 D1–D3, g2-hash-table-sizing) | `ft8_shim.c` l.652–675 |

## 1. The five questions

### Q1. ABI: keep the struct (QA's call). The degradation rule needs one more step (C1)

**Keep `message[36]`, no ABI change.**
- Phase 3 will decide whether the Hound logic needs the raw 10-bit hash (to confirm the Fox when the text says `<...>`).
- If it does, that is **one** ABI change, made then, and it can widen the text field in the same change.
- Changing it now risks doing it twice.

**C1: the bound arithmetic.** Lengths in characters: `RR73;` with its two spaces = 7, report = 3, brackets included.

| call1 | call2 | call3 | length | fits in 35? |
|---|---|---|---|---|
| standard ≤ 6 | standard ≤ 6 | resolved ≤ 13 | 6+7+6+1+13+1+3 = **37** | **no**: so the `<...>` step is needed with standard calls too |
| standard ≤ 6 | standard ≤ 6 | `<...>` 5 | 29 | yes |
| a resolved 22-bit hash in the c28 field, ≤ 13 | standard 6 | `<...>` | 13+7+6+1+5+1+3 = **36** | **no** |
| `<...>` | `<...>` | `<...>` | 27 | yes |

- The spec's second step ("if it still would not fit … cannot happen with standard calls … return an error") would
  **drop a real decode** whenever a hound has a hashed (non-standard) call.
- **Replace it with a fixed degradation order:**
  1. render `call3` as `<...>`;
  2. if the text still doesn't fit, render any hashed `call1`/`call2` as `<...>`, call2 first.
- **The 27-character floor then proves it always fits.** The error branch stays only as a defensive assert, and the
  exhaustive bound test must show it is never taken.
- The special tokens (`CQ nnn`, up to 7 characters) also fit at the floor (31).

### Q2. The 10-bit hash: unique-match is right, but it must be measured (C2)

**What unique-match gives,** from K1 and K2. N = the calls in the session table, assumed spread evenly over 1,024 buckets:

| N in the table | Fox's call in the table: shown by name (no other call in its bucket) | Fox's call NOT in the table: a **wrong** name shown (exactly one other call in the bucket) |
|---|---|---|
| 300 | 75 % | **22 %** |
| 1,000 | 38 % | **37 %** |
| 2,000 | 14 % | **28 %** |
| 4,000 | 2 % | 8 % |

**Reading:**
- Unique-match is the right rule and stays: it follows F-001's "no name beats a wrong name", and nothing stricter
  is available without new state.
- On a long session it mostly shows `<...>`. That is expected, not a defect.
- **The wrong-name case is real whenever the Fox's own call was never decoded in full.** A Fox that sends its CQ during
  the session is normally in the table.
- So the policy stays; what was missing is a way to see it work.

**C2:**
1. **The 12-bit code path and its counters stay byte-for-byte as they are.** But K1 means their **values** can move:
   0.1 decodes add hound calls to the shared table. **F-001 12-bit counter figures from this build are a new era.**
   Never compare them with `main`'s.
2. **New row V2b** (QA's replay, mechanical). For each 0.1 decode matched to WSJT-X, class its `call3` against WSJT-X's text:
   - **same call**;
   - **OWS `<...>`, WSJT-X a call**;
   - **OWS a call, WSJT-X `<...>`**;
   - **different calls**.

   Report the four counts. **Any "different calls" ⇒ STOP and report to the Architect.** Each is examined by hand,
   with aggregates only in the repo (HK-037). Where the rule comes from: the F-001 policy. The count is not a numeric
   bar, and WSJT-X can be the wrong one.
3. **V1 needs the same allowance.** Because of K1, a later message's hashed token can now resolve differently. **V1 =
   every non-0.1 decode identical in its outcome fields.** Rows that differ **only** in a hashed `<…>` token are counted
   and reported separately, not as a failure. Any other difference fails V1. (Standing rule: compare outcome fields,
   not rendered text.)

### Q3. False positives: the plausibility rule alone is weak; add an estimate that needs no imported bar (C3)

**Why the rule alone is weak:**
- About 98 % of the c28 code space is the standard-callsign range.
- All 32 values of `r5` are valid reports, and `h10` always renders.
- So **a random 0.1 payload passes a shape rule almost every time.**
- K1 makes a false 0.1 decode costlier than other false decodes: it writes two random calls into the session table
  for the rest of the session. That raises later collisions, at 10 and 12 bits alike.

**C3a: tighten the rule from the 288 real rows (aggregates only).** Before the rule is frozen, QA counts on the 288
WSJT-X rows:
- how many have **call1 = call2**;
- how many have a **special token** (CQ/DE/QRZ) in token 0 or 2.

If either count is 0, the rule rejects that case. The spec currently allows special tokens; that is opened up only if
the rows show them. HK-038: the rule comes from this population.

**C3b: an estimate of the false-decode count, from the decoder's own counts.**
- The shim already sees every CRC-passing candidate that `ftx_message_decode` then rejects as an unsupported type
  (`ft8_shim.c` ~l.1888).
- **Add a counter of those rejections by (i3, n3).** It is measure-only and cannot change output, like SUP-B.
- Under chance, a false CRC pass is equally likely to land in **any** of the 64 (i3 = 0, n3) codes. The undefined code
  **n3 = 7** cannot be a real transmission. **Its count is therefore an unbiased estimate of how many false 0.1
  payloads reach the decoder.**
- Multiply it by the rule's acceptance rate on random payloads. Measure that rate exactly in a unit test: render N
  random 71-bit payloads, run `IsPlausibleMessage`, report the share.
- That gives **M2: expected false 0.1 rows per night** on `20261009_1752`, descriptive, with its basis stated. It needs
  no bar.
- **The two checks beside it:**
  - **V3, the S5 gate:** kept, but on 480 noise plays it has little power for this question.
  - **V2's OWS-only 0.1 count:** the empirical upper bound.
- **If V2's OWS-only count exceeds M2's estimate by a wide margin** (more than 3× and more than 5 rows): **STOP and
  report.** The rule is then letting through something chance doesn't explain. The 3×/5 threshold is the Architect's
  judgement, stated (HK-038).

### Q4. Inert consumers: agreed, with two things made explicit (C4)

1. **"Inert" covers every batch number.** Since #249, batches 2 and 3 reach the answerer and caller. A 0.1 text found by
   the residual or third pass must be just as inert. **One test per service per batch number.**
2. **Region attribution and noise suppression are a product choice. Don't leave them to the Developer:**
   - The sender of a 0.1 message is the Fox, `call3`.
   - **Rule for this phase:** region from `call3` when it is resolved; otherwise the row is a lookup miss, and the
     existing noise-suppression rule applies unchanged.
   - Consequence, from the Q2 table: **with noise suppression ON, most Fox rows on a long session will be hidden**
     (`<...>` ⇒ lookup miss). QA puts this to the Captain with the table (see §3). The Developer builds the rule above
     unless he says otherwise.
3. Everything else stays as the spec has it: no QSO effect, no CQ, no external spot, not subtracted.
   - Whether WSJT-X-format UDP decode datagrams (GridTracker) should carry 0.1 rows is a **phase 3** question.
   - Inert now is the safe default.

### Q5. The r5 mapping: fine, with the fact stated (C5)

- The protocol paper gives the 0.1 report as **−30 to +32 dB in 2 dB steps**, i.e. 32 values for 5 bits.
- The Developer derives the exact formula from the paper and cites the section.
- **QA's check:** the report of every matched decode on the 288 rows equals WSJT-X's text. **Any mismatch ⇒ STOP**
  (it is a formula error, not noise).

### Other types: agreed, out of this phase

- Types 0.2/0.3/0.4/0.6 and i3 3/5 stay undecoded.
- 5 RTTY/WWROF rows in a 15 h night are not worth a new false-positive surface.

## 2. Two smaller corrections (C6)

1. **Synthetic test calls:** the c28 unpack rewrites `Q` + letter as `3X…` (the Guinea workaround, `message.c`
   l.812–816). **Test vectors must use `Q` + digit** (`Q1ABC`, `Q2XYZ`), or they will render as `3X…` and fail for the
   wrong reason. That is also NFR-021-correct.
2. **"Prove it" for the length bound** = the exhaustive test of §1.3, plus the arithmetic table of C1 written into the
   test's comment. AddressSanitizer on the WSL leg is enough; say which tool was used.

## 3. For the Captain (via QA), with the data. A product choice, not housekeeping

**Fox rows with noise suppression on.**
- From the Q2 table: on a busy night the Fox's call resolves only 2–38 % of the time once the session table holds 1,000–4,000 calls.
- An unresolved Fox row is a region-lookup miss, which noise suppression hides.

| option | leads to |
|---|---|
| **A. As designed** (C4.2): a hidden row when unresolved and suppression is on | Consistent with the suppression rule today. Most Fox rows invisible to suppression users |
| B. Exempt 0.1 rows from suppression | Fox rows always shown. Any false 0.1 row is shown too (see M2) |
| C. Decide after the replay | M2 and V2b give the false-row rate and the resolve rate first. Build A meanwhile |

**Architect's view: C.** The data that decides it is produced by this task's own replay.

## 4. Changes to write into the spec

| # | where | change |
|---|---|---|
| C1 | §1.3 | degradation order `call3` → hashed `call1`/`call2` → (assert) ; arithmetic table in the test |
| C2 | §1.5, §6 | 12-bit code untouched but **F-001 counter values = new era**; V2b with STOP on any "different calls"; V1 on outcome fields, with hashed-token-only differences counted separately |
| C3 | §1.5, §2.1, §6 | rule tightened from the 288 rows (call1 = call2, special tokens); (i3, n3) reject counter (measure-only); random-payload acceptance test; M2 = expected false rows; STOP rule at 3× and > 5 |
| C4 | §2.3, §3 | inert for batches 1–3, tested per service per batch; region from resolved `call3`, else lookup miss; question to the Captain (§3 here) |
| C5 | §1.2, §6 | r5 −30..+32 dB in 2 dB steps, from the paper; any report mismatch on the matched rows ⇒ STOP |
| C6 | §3 | `Q` + digit test calls; ASan on WSL |

**Phase 3:** my design comes after this phase is merged and measured, as the spec's §7 says. It will take M2, V2b and
the Captain's answer to §3 as inputs.
