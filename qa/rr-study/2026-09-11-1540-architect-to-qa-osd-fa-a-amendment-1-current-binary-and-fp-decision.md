# `OSD-FA-A` Amendment 1 — brought onto the current binary, re-aimed at the FP decision, with a Part 0 that settles `ROW 0r`

**Architect → QA.** 2026-09-11 15:40Z (`date -u`, HK-017). Branch `arch/osd-fa-a`.
Docs-only; `git diff --stat origin/main -- src/ native/` empty.

**Amends:** `qa/rr-study/2026-08-23-2026-architect-to-qa-spec-osd-fa-a-osd-false-accept-audit.md`
(`b7565b1`, never run, held since 2026-08-23). Where this amendment is silent, the base spec stands.

**Ordered by the Captain, 2026-09-11:** *"I want to resolve the FP issue."* The Captain approved
(1) a check on whether the `20260050` counter build perturbs decoding, and (2) scoping a
decoder-side FP arm, *"after you have validated your own work"*. §0 records what that validation
changed.

---

## 0. Why this is an amendment, not a new arm (HK-018)

I set out to specify a new decoder-side FP arm. **It already existed.** `OSD-FA-A` asks exactly the
right questions:

- how often live decodes take the OSD path (Part D);
- what share of emitted decodes are false under oracle truth (Part A);
- whether the `nhard`/`corr` gate removes junk or genuine decodes (Part B);
- where the gate's cut sits (Part C).

It has been held since 2026-08-23 behind other D-001 arms, and nobody picked it up (board: "not
attempted"). Three things in it are stale, and this amendment fixes only those:

| stale item | now |
|---|---|
| Binary pin `bc8efcf1…`, shim `20260046` (ROW 0a) | `6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c`, shim `20260050`. `sha256sum` of `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` on `origin/main`, re-computed today |
| Part D corpus `20260803_live_run_1713` (pre-fix; two population counts on the board that were never reconciled) | `FP-FLOOR-LIVE-2`: post-fix, same binary, `REF` = WSJT-X #1 on the same audio device, span fixed for reasons unrelated to this arm (§3) |
| Framed only as a D-001 hypothesis (E2) | E2 ("our exclusive decodes are largely false") **is** the live FP question. New **Part E** tests the one decoder-side FP remedy on the board, D-009 Option B (§5) |

**Code facts re-verified today against `native/ft8_lib_build/patched/ft8/decode.c` (all still
hold; only line numbers moved):**

- 529 CRC-14 trials per candidate at `ndeep=2` (`:429`).
- `osd_decode` returns the first CRC-valid codeword (`:596`, `:608`, `:620`).
- Both gate thresholds are runtime variables (`:57–62`), set via the exported
  `ft8_set_decode_params`.
- `ft8_extract_llrs_at` and `ft8_ldpc_decode_llrs` are still exported (`libft8.version.txt`).

**One product fact the base spec did not have.** `osd_nhard_max` is already an **operator setting**,
not just a native knob:

- It lives in `config.json` as `Decoder.OsdNhardMax`, default 60.
- The web API accepts values in `[30, 100]` (`WebApp.cs:611–618`).
- A save takes effect on the next cycle (`Program.cs:867`).
- It is not on the settings page.

⇒ **Option B needs no build to try.** Changing the *default* is a `src/` change (HK-011). This
shapes Part E's consequences.

---

## 1. PART 0 — does the `20260050` build perturb decoding? Run this FIRST, standalone

### 1.1 Why it exists

Citation guard (g) (`fp-regression-2026-09-04-citation-guards.md` §0.1) records that
`ac6150d`'s "provably non-perturbing" claim **stays contradicted**, because `AWGN-FP` `ROW 0r`
found 246 of 4,000 noise slots with a different decode set across `20260049` → `20260050`.

The `ROW 0r` report (`qa/rr-study/fp-parity/results/2026-09-04-row0r-carry-forward-report.md` §2)
shows exactly what differed:

- **0 of 435** event slots changed decode count.
- **0** changed `freq_hz`, `dt_s` or `reported_snr_db`.
- All 246 differ **only in message text**. ~~The `20260049` run shows `<...>` where the `20260050`
  run shows a resolved-looking callsign.~~ ⛔ **STRUCK 2026-09-11 16:19Z: those "placeholders"
  are `<RDCTMnn>` NFR-021 redaction tokens in the committed "before" CSV, not hash misses. See
  `2026-09-11-1619-architect-osd-fa-a-part0-acceptance-and-row0r-reclassified.md` §2.**

Its comparison was **not** a same-harness A/B (report §0). "Before" was the committed CSV from a
different test class (`AwgnFpReplayTests`, `4a7fb3d`). "After" was a fresh run of a new class
(`Row0rCarryForwardTests`).

~~The callsign table is one global table per process (`g_session_hash_table`, `ft8_shim.c:787`), and
it persists across `ft8_decode_all` calls. So resolution text depends on what that process decoded
earlier. **That is a candidate explanation, not a finding.**~~ ⛔ **STRUCK 2026-09-11 16:19Z: the
hypothesis is FALSE. The 246 are exactly the slots whose committed "before" CSV carries NFR-021
redaction placeholders: raw text was compared against redacted text. Fresh decoding reproduces
that CSV with 0 numeric mismatches, and every text difference is a placeholder (0 mapping
conflicts). See `2026-09-11-1619-…-row0r-reclassified.md` §2.** (The session-table fact itself is
true; it just is not what happened here.) The F-001 L3 run's ROW 0e is
independent evidence the other way: dual-binary, same harness, **0 differences in 65,798 live
decodes, message text included**. But it covered live audio, not the noise-only population where
FPs live.

### 1.2 Method

- **Population:** the 4,000 WAVs at
  `D:\Projects\claude\OpenWSFZ\qa\rr-study\awgn-fp-replay\_work\m1m4_s5\`, in the **Architect
  worktree root** (gitignored, present, 4,000 files counted today). **Read them in place by absolute
  path; do not copy.** Copying gitignored data between worktrees needs the Captain's
  sign-off. Reading does not.
- **Instrument:** the ctypes replay path, `g3_h12_replay.py` or its mechanics, extended additively
  if its filename/window parsing needs it. It is the instrument behind L3's ROW 0e. The C# path
  cannot load `20260049` (`ExpectedShimVersion` is a compile-time constant, `ROW 0r` report §0).
- **Three legs, each a separate OS process** (so each starts with a fresh session table), run
  **one after another, not concurrently**:

  | leg | binary | SHA256 (assert in-run, HK-021(p)) |
  |---|---|---|
  | `S1` | shim `20260050`, `src/OpenWSFZ.Ft8/Native/win-x64/libft8.dll` | `6b2e16a6…4f85c` |
  | `S2` | the same, a second fresh process | `6b2e16a6…4f85c` |
  | `C` | shim `20260049`, `artefacts/2026-09-03-f001-l3-shim-rebuild/libft8-20260049-prechange.dll` | `ce02c7ba…153e` (re-hashed today, matches) |

- **Identical configuration on every leg:** files in sorted filename order, AP bits cleared per
  slot, default decode params (`ft8_set_decode_params` not called), **no PCM normalisation**
  (matching M1 and `ROW 0r`, so the result speaks to that comparison).
- **Compare per slot, mechanically:** the full ordered decode list, i.e. count, and for each decode
  `freq`, `dt`, `snr` and message text. Print the diff count per field. Never assert
  byte-identity; diff it.

### 1.3 Rows — strict order, first match wins (predicates as code, HK-021(r))

| row | predicate | consequence |
|---|---|---|
| **P0-0a** | any leg's loaded DLL SHA ≠ its pin | **VOID.** Wrong binary. |
| **P0-0b** | any leg decodes ≠ 4,000 slots | **VOID.** Population mismatch. |
| **P0-R1** | `S1` vs `S2`: any field differs on any slot | **The harness is not deterministic on one binary.** `S1` vs `C` cannot be read, so STOP Part 0 and report the diff counts by field. ⚠️ This also blocks every same-binary ctypes contrast in this arm (Parts B, E2) until explained, so escalate. |
| **P0-1** | `S1` vs `C`: zero differences in every field | **The counter build does not perturb decoding, or its text, on noise-only input in one harness.** `ROW 0r`'s 246 text differences came from the run, not the binary. Guard (g) is **resolved for this population and harness** (HK-022 scope: nothing wider). |
| **P0-2** | `S1` vs `C`: any count, `freq`, `dt` or `snr` difference | **The build perturbs decoding.** A real defect. Escalate; any fix is HK-011. |
| **P0-3** | `S1` vs `C`: counts and numerics identical, text differs | **The build changes hash-resolution text only**, reproducing `ROW 0r` within one harness. Escalate. |

HK-021(k) check: P0-R1 changes the verdict. With it firing, P0-1/2/3 are unreadable. The rows are
mutually exclusive and exhaustive after 0a/0b.

**Descriptive only, never gated:**

- Wall-clock seconds per leg. The legs run one after another for this reason: it answers the
  Captain's "does it only hit performance?" on a like-for-like basis. The L3 run's legs ran
  concurrently, so their 3,116.0 vs 3,116.2 s is not a benchmark.
- The count of `<...>` renderings per leg, beside the same count read from the committed
  `qa/rr-study/awgn-fp-replay/results/m1m4_s5_decodes.csv` (`20260049`, `4a7fb3d`) and
  `qa/rr-study/fp-parity/results/m1m4_s5_20260050_decodes.csv` (`ROW 0r`).
  Redaction maps callsigns, not `<...>`, so both counts are readable. **Check that before relying
  on it.**

**Prediction (blind, nothing gates on it):** P0-R1 clears and **P0-1 fires**. Confidence
moderate-high; L3's ROW 0e is the reason.

---

## 2. Base-spec corrections (ROW 0 and instruments)

1. **ROW 0a pin →** `6b2e16a6991ae953d18c85e5f0fea99d1e003c84b90ae5a69a8f1cfade34f85c`, shim
   `20260050`. 🛑 `qa/rr-study/f-nbr-a/dll_common.py:28–29` hard-codes the old `20260046` pin,
   and its `load_decoder()` takes **no** pin arguments. It passes its own constants at `:80–81`,
   so it would refuse the current binary. **Do not edit that module**; it is a closed arm's
   instrument. Construct `LdpcDecodeLLRs(path, expected_sha256=…, expected_shim_version=20260050)`
   (`ldpc_decode_ctypes.py:57`) directly with the new pin. Keep reusing `dll_common`'s
   `extraction_time_offset_s` / `SYMBOL_PERIOD_S` for the `+0.16 s` correction. Both DLL copies
   (`native/ft8_lib_build/libft8.dll` and `src/…/win-x64/libft8.dll`) hash to the new pin today.
2. **ROW 0f is WITHDRAWN.** It reconciled two population counts on the old Part D corpus, which
   §3 replaces. It was DIAGNOSTIC and never gated, so nothing downstream moves.
3. **Input contract (Parts A, B, E2).** `FP-PARITY` P3 established that the production input path
   applies `NormalisePcm` (≈6.9 dB level difference against an un-normalised offline decode). That
   difference is closed as an explanation of the offline/in-chain gap, but it is still a different
   operating point. **Name the input contract used in every figure, and use the same one on every
   leg of any contrast.** Use the production contract where the instrument allows. Where it does
   not (the ctypes path), say so in the headline, not in a footnote.
4. Base ROW 0b–0e are unchanged. Base ROW 0d (determinism, synthetic legs) is **not** replaced by
   P0-R1; they cover different populations.

---

## 3. Part D — corpus substituted

**Population:** `artefacts/20260908_live_run_1827-fp-floor-live-2/`, span
`[2026-09-08T19:36:45Z, 2026-09-09T17:22:00Z)`.

- The start boundary is `FP-FLOOR-LIVE-2` Amendment 3's, frozen for reasons unrelated to this arm,
  so it is not outcome-chosen (HK-021(y)). The end is the corpus's natural close, as used by the L3
  run.
- Sample **1,000 cycles**, seeded, **sorted at construction** (base §2.4 hazard 2).

**Decodes and positions come from OpenWSFZ's own live `ALL.TXT` in that span** (production-emitted
decodes), exactly as base §4.1 specifies, ~~with the `+0.16 s` correction applied uniformly~~ ⛔
**at the reported `dt` with NO offset. Live `dt` is already decoder-reported. My error, inherited
from base §2.4; QA caught it (Part D ruling `2026-09-11-1652-…` §2).**

⚠️ **Not from a replay.** An offline replay of this span on this binary emitted **65,798** decodes
over 5,222 cycles, against the live daemon's **57,969** (L3 result §1; `FP-FLOOR-LIVE-2` Part B).
That gap is **not reconciled**, and that includes whether the two cover exactly the same cycles. A
replay population could mix in decodes production never showed the operator.

Base ROW 0e (probe fidelity ≥ 0.90 on a 200-decode control subset) applies unchanged.

**Rows D1/D2/D3 are unchanged.** One added reading: **`U` bounds Part E's live reach.** A change to
the OSD gate can only remove OSD-path decodes, so under D1 Option B can affect at most `U` of live
output.

**Descriptive only, no row:** `U` reported separately within (a) decodes corroborated by
`REF` = WSJT-X #1 and those not, and (b) `snr ≤ −24` vs `> −24`.

- Corroboration uses `FP-FLOOR-LIVE-2` Part B's matcher: same cycle, `|Δf| ≤ 3 Hz`, wildcard
  mandatory. Reuse `fp_floor_live_2_part_b.py`'s `load` / `is_corroborated`, not a third
  implementation.
- Both splits were fixed before any `U` exists (the `−24` cut is `FP-FLOOR-LIVE-2`'s).
- This is where a live link between the OSD path and uncorroborated decodes would show. It is
  **not** a gate.

---

## 4. Parts A, B, C

Unchanged, apart from §2. Part B's B1 consequence (*"D-009 Option B gets its first real evidence"*)
is now superseded by Part E, which tests Option B directly.

---

## 5. NEW Part E — D-009 Option B (`osd_nhard_max` 60 → 40): does it buy FP reduction, and at what cost?

**Treatment:** `ft8_set_decode_params(10, 0.10, 40)`. Only `nhard` moves. 40 is inside the
product's accepted range. **Control:** production defaults `(10, 0.10, 60)`. Set parameters before
the first decode and never mid-run (base §2.5).

### 5.1 E1 — the FP benefit, on noise only

- **Population and instrument:** the 4,000 M1 S5 slots, **through the production input contract**
  (`FpParityP3Tests`' normalised path, the one behind the only citable offline rate, `10.325%`).
  Two legs, nhard 60 and 40, same session, paired by slot.
- **Event** = a slot with ≥1 decode. It is **count-based; message text plays no part**. The
  session callsign table makes text depend on decode history (§1.1), and a text-based event would
  import that.
- **Statistic:** `r` = slots with an FP event at 60 and none at 40. `a` = the reverse. Exact
  two-sided McNemar (`binomtest(r, r+a, 0.5)`, as `p3_parity.py` does).

| row | predicate | reading |
|---|---|---|
| **E1-1** | `p < 0.05` **and** `r > a` | Option B produces a **detectable FP reduction** on noise. Report `r`, `a`, the events at each setting, and the rate at each setting. |
| **E1-2** | otherwise | **No detectable FP benefit.** Option B has nothing to buy on this evidence. |

Resolution: at the P3 base rate (≈413 events), `r ≥ 9` with `a = 0` gives `p ≈ 0.004`. A benefit
confined to a handful of slots will read E1-2, and that is the correct reading of "a handful".

### 5.2 E2 — genuine cost under oracle truth (synthetic, signal present)

Identical PCM to Part A (S8HN, 1,000 cycles), decoded at nhard 60 and 40. Using Part B's pairing
key `(payload, freq ±4.0 Hz)`:

- `N_killed40` = genuine decodes at 60, absent at 40.
- `N_caught40` = false decodes at 60, absent at 40.
- `Q40 = N_killed40 / (N_killed40 + N_caught40)`, with a cycle-clustered CI.

The rows are Part B's, verbatim:

- **E2-B1:** `CI_hi < 0.05`.
- **E2-B2:** `CI_lo > 0.20`.
- **E2-B3:** otherwise, or fewer than 100 removals.

Also report genuine decodes lost per 1,000 cycles, and decodes present at 40 but absent at 60
(expected ≈0; any excess is a disclosed confound, per base §6.1).

**This is the only leg that can show Option B is *safe*.** Oracle truth is a reference with a known
miss rate (zero). It carries its own transfer caveat (synthetic scene, input contract per §2.3).

### 5.3 E3 — live harm check (real audio; can detect harm, can NEVER establish safety)

🛑 **Read this first.** `FP-FLOOR-LIVE-2` Part B's acceptance ruling §3
(`2026-09-10-1443-…`): corroboration by a second decoder bounds genuine loss **from below**. A low
corroborated share cannot prove a loss is small. **E3 has no "safe" row, by construction.**

**Population:** OpenWSFZ **live-emitted** decodes in the §3 span (production `ALL.TXT`, the
**57,969**).

- Replay the span's cycle audio on `20260050` at nhard 60 and at 40, same harness, same input
  contract.
- A live decode is **reproduced** if the 60-leg replay has a decode in the same cycle, with a
  matching message, and `|Δf| ≤ 3 Hz`.
- It is **removed** if it is reproduced at 60 and has no such match at 40.
- 🔴 **"Matching message" means wildcard matching** (`<...>` matches one token, the §3 matcher),
  for both reproduction and removal. The two replay legs build different callsign-table histories
  once the 40 leg drops decodes, so exact text would record a resolution-text change as a
  "removal".

Counting only live-emitted decodes keeps out whatever the replay adds that production never
showed.

- **E3-0 (VALIDITY):** reproduction share `< 0.90` ⇒ **E3 VOID.** The replay does not reproduce
  production, so its 60→40 contrast is not a statement about production. The 0.90 bar is this
  spec's own ROW 0e fidelity bar, reused, not new.
- `n` = removed decodes. `k` = removed decodes corroborated by `REF` = WSJT-X #1 (§3 matcher).
  `[lo, hi]` = Clopper–Pearson 95%.

| row | predicate | reading |
|---|---|---|
| **E3-H** | `lo ≥ BAR_H` | **Option B measurably removes real stations on live audio.** Report `k`, `n`, `[lo, hi]`, corroborated decodes lost per hour, and uncorroborated decodes removed per hour. |
| **E3-N** | otherwise | **No live harm detected at this resolution.** Report the same figures and `n`. 🛑 **Never write "safe", "no cost" or "negligible".** |

🔴 **`BAR_H` needs the PO's ratification before E3's count is computed** (the `R_STAR` precedent). I
propose **`BAR_H = 0.05`**: the same value the PO ratified as `FP-FLOOR-LIVE-2`'s ROW 2 bar, which
by that ruling's own terms "does not reach forward" to this arm, so it must be re-ratified here,
not inherited. **E1, E2 and Parts A–D may run before ratification. E3's `k` may not be computed
until `BAR_H` is recorded in this file.**

> ✅ **PO RULING, 2026-09-11 16:26Z — `BAR_H = 0.05` RATIFIED.** PO (verbatim): *"5% ratified"*.
> Recorded before any Part E datum exists: Part 0 has run, and no Part D/A/B/C/E leg has. It is
> **FROZEN for this arm**, and does not reach forward or backward. 🛑 If anyone (the Captain, the
> PO, me) proposes moving it after E3's `k` is known, refuse and escalate: that is the re-read
> this programme bars, and it would VOID E3.

### 5.4 Part E consequence — strict order, first match wins

1. **E2-B2 or E3-H** ⇒ **Option B is contraindicated as a default.** Record it with the per-hour
   figures. The PO may still set `OsdNhardMax` in their own config with those figures in hand;
   that is an operating choice, not a product change.
2. **E1-2** ⇒ **Option B buys nothing.** Recommend to the PO that its HOLD becomes CLOSED.
3. **E1-1 and E2-B1 and E3-N** ⇒ the Architect is cleared to **draft** a separate
   pre-registration for changing the default 60 → 40 (a `src/` change, HK-011). This is not a
   licence to change anything.
4. **Anything else** ⇒ report every figure; nothing is drafted.

### 5.5 Predictions (blind, nothing gates on them; weigh by my record)

- **E1-1** (0.6).
- **E2-B3** (0.5): fewer than 100 removals seems likely at 60→40.
- **E3-H** (0.5, low confidence): `FP-FLOOR-LIVE-2` found weak decodes corroborated at 40–52%,
  and nhard 41–60 accepts are weak ones.
- **Most likely overall consequence: 1.**

My last three predictions each missed in some respect (`FP-FLOOR-LIVE-2` Part B's row call, the
`D003-LIVE` rate, F-001 L3's row call).

---

## 6. Running order and authorisation

| step | status |
|---|---|
| **Part 0** | ✅ **DONE and ACCEPTED**: P0-1 (`2026-09-11-1619-…-row0r-reclassified.md`). P0-R1 cleared. |
| Base ROW 0 → D → A → B → C → E1 → E2 | ✅ **GO: Captain, 2026-09-11 16:26Z ("go ahead with OSD-FA-A"). `OSD-FA-A` is OFF HOLD.** Part 0's P0-R1 has cleared, so B and E2 are unblocked. Run in this order. Read ROW 0 first and Part D before A and B (base §10). |
| **E3** | ✅ **GO: `BAR_H = 0.05` ratified and recorded in §5.3.** Runs after E1/E2. |

## 7. Unchanged

- No `src/` or `native/` change, no rebuild, no push, no merge (HK-011, HK-014, HK-010).
- No product threshold moves in any row. §5.4's best outcome is a *draft*.
- 🛑 Spectral locality is barred in any form (base §0.1, §9). First-hit displacement stays out of
  scope (base §0.3).
- NFR-021: Part D and E3 read live `ALL.TXT` with real callsigns. **Output counts only**; message
  text never printed, logged or written. Part 0 and the synthetic legs are noise-only or
  Q-prefix-only, but scan anyway (the `ROW 0r` noise CSV carried 361 callsign-shaped tokens).
- 🔴 **HK-025 is available in full.** If any row here is a diagnostic dressed as a gate, name it,
  evaluate both branches, and refuse. I have missed exactly that on three arms this month.
