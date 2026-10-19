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

## Addendum 1: rulings on the build `87beed94` before QA's replay (2026-10-19 18:17Z, `date -u`)

Facts as QA reported them. The CI lines were checked by the Architect (`ci.yml` on `origin/main`, both the macOS and
Linux jobs: clone `frank001/ft8_lib` `msvc-compat`, overlay only `native/ft8_lib_build/patched/ft8/decode.c`).

**R1. A stricter hound guard: yes, as a candidate measured before the replay. Use a STATIC ITU prefix table, not the region data.**
- **Not the station's region data.** `callsign-regions.json` is refreshable: sol's was refreshed on 2026-10-18. A decode
  rule that depends on it would make decode output change when the file changes. That breaks the determinism the R&R
  and every replay rely on.
- **Rule:** tokens 0 and 2, when they are standard calls, must start with an allocated ITU call-sign series. The table
  is compiled in, taken from the ITU's public Table of Allocation of International Call Sign Series (facts, no licence
  issue), and never refreshed. Hashed `<...>` hounds stay allowed (as confirmed).
- 🔴 **`Q` is not an ITU country series, and the synthetic test calls are all `Q` + digit (NFR-021).**
  - The table must be **injectable**: production = ITU only; tests add `Q`.
  - The synthetic-fixture differential decode then runs with the test table, and the replay on real audio with the production one.
- **Measure before adopting (QA, aggregates only):**
  - (a) the share of the **576** real hound calls on the 288 rows that pass;
  - (b) the rule's acceptance of random payloads, the same N = 100,000 and seed as the 71.8 % figure.
- **Adopt if (a) = 576/576.** Any miss ⇒ report the misses' shapes to the Architect before adopting.
  - Where the bar comes from (HK-038): the 288 rows are the only real population we have. Losing a real hound is a
    lost decode, and the table should not need to lose any.
  - Report (b) beside it. M2 then uses the new acceptance figure.

**R2. The four Developer fixes: all ACCEPTED.**
- (a) External reporting skips 0.1 rows explicitly. My C4 region rule is what opened that path, and the guard is right.
- (b) `engage-decode` refuses a 0.1 row up front.
- (c) `decodeRowClasses.js` never marks a 0.1 row as a responder.
- The subtraction keep-by-text fix, without which every batch-2/3 0.1 decode would have been hidden.
- Each one replaces an accident with an explicit rule. Phase 3 will revisit (a)–(c) deliberately.

**R3. The CI gap: confirmed, and it must be closed before the #225 PR. One more check first.**
- The fix (copy `message.c`/`message.h` from the vendored tree in both jobs) is right in kind.
- **Before it merges, QA establishes for each platform which copy of every `ft8/*.c` and `*.h` is compiled.** There are
  three candidate sources: the `msvc-compat` clone, `native/ft8_lib_vendor/ft8/`, and `native/ft8_lib_build/` (Windows,
  which per the shim history once linked a **binary-patched `message.obj`**).
- **Diff every file of the vendored tree against the clone.** Then:
  1. If any file other than `decode.c` **already** differs today, Linux/macOS have been compiling a different source
     from Windows. List the files, and say whether it touches decode output.
  2. Check that the Developer's Windows `libft8.dll` compiled `message.c` **from the vendored source**, and that the old
     MSVC pointer-truncation fix is still present in it, in source or as the binary patch.
  3. The CI fix overlays every file that differs, not only `message.c`/`.h`, unless a file differs on purpose (say why).
- **Era note:** the sol `.so` changes with shim 20260064 in any case, so this is a new sol build era. The B2CAP and Deep/sol bands are not carried over.

**R4. The rest: noted.**
- `r5` = 2·r5 − 30, printed `%+03d`. The check is V2c against WSJT-X's text, since the paper could not be opened
  offline (say so in the hand-back, as was done).
- The (i3, n3) counter as a native getter plus a per-cycle log line is enough for M2.
- The F-001 12-bit values are a new era.
- The synthetic-fixture false 0.1 decodes are a warning, as QA says. The live figure is the replay's.

## Addendum 2: R1 and R3 results (2026-10-19, after QA's measurements; figures as QA reported them)

**R1, the ITU guard: NOT adopted now. It is deferred to the replay.**
- **It passes the bar:** 576/576 real hound tokens.
- **But it buys little:** at most a factor of about 0.64 on the 71.8 % acceptance of random payloads, to about 46 % or
  more, and less where it overlaps `IsParsedCallsign`.
- **And its table was written from memory.** An unverified table in a decode rule risks dropping real hounds from
  rare series. A real example: **`1A` (the Sovereign Military Order of Malta)** starts with `1`, which the prototype rejects.
- **Decision:** ship without it. If the replay's M2 / V2 shows false 0.1 rows at a level the Captain finds too high,
  the guard comes back as its own change. Its table would then be checked line by line against the ITU's published
  allocation table, plus the known non-ITU series in use (`1A`, `4U`), and re-measured on the 576.

**R3, the CI fix: ACCEPTED as `b78a418d`** (overlay `message.c`, `message.h` and `common/monitor.c` in both jobs).
- QA's diff shows that **until now Linux/macOS compiled the same decode source as Windows**: all 21 vendored files are
  identical to the clone, and `decode.c` was already overlaid. **No earlier cross-platform figure is affected.**
- **One side effect to check before it merges:** the `monitor.c` overlay removes four INFO lines per `ft8_decode_all`
  from the CI-built Linux/macOS libraries' stderr.
  - QA confirms that **no sol tooling** (battery, pull-series, F2/third-pass parsers, supervisors) greps those lines.
  - If one does, it must be changed in the same step.
- It must merge before the #225 PR, on the Captain's go.

## Addendum 3: the quick-check replay, and the ruling on the 10-bit Fox name (2026-10-19 18:59Z, `date -u`)

Figures as QA reported them: 455 cycles of `20261009_1752`, Deep both arms, OLD `5229beec` vs NEW `87beed94`.

**Results:**
- **V1 PASS:** 0 of 455 cycles differ, 0 abandoned.
- **V2:** 64 new 0.1 decodes, 63 matched, **0 OWS-only**.
- **V2c:** 0 report mismatches.
- **M1:** 63 of 77 WSJT-X 0.1 rows = **81.8 % [71.8, 88.9]** (one 40 m night, offline, every 8th cycle).
- **V2b:**

  | class | count |
  |---|---|
  | same call | 7 |
  | OWS `<...>`, WSJT-X a call | 56 |
  | OWS a call, WSJT-X `<...>` | 0 |
  | **different calls** | **1** ⇒ **STOP fired, as ruled** |

**The STOP case.** It is exactly the K2 collision:
- OWS's name shares the Fox's 10-bit hash but not its 22-bit hash;
- it is a real station heard that night;
- the unique-match rule took the only call in the bucket, and it was not the Fox.

That is **1 wrong of 8 resolved.** The sample is tiny, but the full night fills the table about 8× more, so the
rate there will be higher (the K2 table).

**RULING: option (a). Never resolve the 10-bit hash in this phase: `call3` is always `<...>`.**
- **Why:**
  - The standing F-001 policy is "no name beats a wrong name".
  - A wrong name was observed in this phase's own replay, and the rate grows with session length.
  - A wrong Fox name also gives a wrong region (C4).
  - The cost is the 7 correct names in this sample, about 11 % of the 0.1 rows, which are display-only in this phase.
- **(b) is rejected.** It knowingly displays wrong names.
- **(c) (heard recently as a sender) is not rejected, but it is not for this phase.** It is new state with its own
  failure modes, and it needs a design.
- **Phase 3 has a safe form of resolution anyway.** A Hound that is calling a chosen Fox knows the Fox's full call, so it
  can **check** the 10-bit hash against that one call. That is verification, not a table lookup, and it cannot pick a
  stranger. The phase 3 design takes this up.

**What changes in the build (QA → Developer, a small amendment to `87beed94`):**
1. The 0.1 path renders `call3` as `<...>` unconditionally. The 10-bit lookup is not called for 0.1. The 12-bit and
   22-bit paths are untouched.
2. C1's degradation step 1 is therefore always in effect, and the bound test still runs.
3. V2b becomes "OWS `<...>` in every row" by construction. **Keep it as a check:** any resolved `call3` ⇒ FAIL.
4. C4: a 0.1 row is now **always** a region-lookup miss.

**The suppression question for the Captain changes with this (it replaces §3's A/B/C):**
- With (a), option A would hide **every** Fox row from noise-suppression users, not most.
- The false-row data so far:
  - 0 OWS-only of 64 in the replay;
  - the (i3, n3) counter read 0 in every cell over 455 cycles. That is **not yet validated** (see below).

| option | leads to |
|---|---|
| A. Suppression applies to 0.1 rows | Users with suppression on never see a Fox row |
| **B. 0.1 rows exempt from suppression** | Fox rows always shown. False rows would be shown too, at a rate the live night must confirm (counter + V2 OWS-only) |
| C. Decide after the live night | Build B or A meanwhile. The night supplies the validated counter and a full-night OWS-only count |

**Architect's view: B,** once the live night confirms the false-row rate is as low as the replay suggests. Until then, C.
The Captain decides.

**M2, the zero counter: validate it before anyone reads it.**
- The Developer's raw-DLL test counted 33 drops in 24 synthetic windows. The managed replay read 0 in every cell over
  455 real cycles. Before 0 is a result, the managed path needs a **positive control**: feed the same synthetic window that
  produced drops in the raw-DLL test through the managed replay path, and the counter must read non-zero.
- If it does, the 455-cycle zero stands as "no chance CRC passes in an unsupported type" (one-sided 95 % bound about
  3 / 455 cycles). That puts expected false 0.1 rows at well under one per night.
- If it doesn't, the counter is broken. Fix it before the live night is read.

**The live endurance run tonight on `87beed94`: yes, as QA plans, with these conditions:**
- **Build:** `87beed94` as is (the change above cannot be made before the run). So the run measures the full-night
  wrong-name rate of the unique-match rule. That is useful evidence for this ruling's record, never for shipping it.
- **Config:** the station's own. Record the depth **read back** from status (Deep is the default on this base). Make no
  other change.
- **New era:** shim 20260064 on the station. Never pool it with DI or `main`-era runs.
- **Read on close:**
  - HK-036 Section 4;
  - V2 OWS-only 0.1 count;
  - V2b, all four classes, full night;
  - M1 by SNR band;
  - the live `unsupportedType total=` line: does it move? That doubles as the counter's validation;
  - 0 external spots of 0.1 rows (R2a).
- On air, the station will show bracketed Fox names, some wrong, during the run. That is display only: no spots, no QSO
  use. Acceptable for one night.

**Phase 3:** my design comes after this phase is merged and measured, as the spec's §7 says. It will take M2, V2b and
the Captain's answer to §3 as inputs.
