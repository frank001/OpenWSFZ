# F-001 D3 PRE-REGISTRATION, ARM 1 — offline hash-table policy simulation. No `src/` change, no rebuild, no replay, no Developer session.

**Architect → QA.** 2026-08-26 11:49Z (`date -u`, HK-017). Repo `main` @ `48b31d6`.

**Authorised by:** ROW B1 of `B1-COVERAGE-A` (`p_frozen` = 40/40), as ruled in
`qa/rr-study/2026-08-26-1137-architect-to-qa-ruling-b1-coverage-a.md`. That row licensed **writing
this spec and nothing else.** PO/Captain chose **arm 1 only**, 2026-08-26: simulate first, decide
about touching the shim on arm 1's number.

**What this arm answers:** of the **307 decodes / 40 callsigns** that are addressable, how many does
each candidate table policy actually recover — **and how many does it destroy?** Nobody edits
`ft8_shim.c` until that is a number.

**Prize, stated once so effort is sized against it (from the ruling §4):** `B1-cap` = **307 decodes
= 0.7070 pp of D-001**, a lower bound. That is the ceiling on arm 1's upside.

---

## §0. What I read out of the source before drafting, and why it changes the design

All line references are `main` @ `48b31d6`.

1. **`src/OpenWSFZ.Ft8/Native/ft8_shim.c:646-680` — the table is OPEN-ADDRESSED with linear probing.**
   First probe is `(h10 * 23) % HASH_TABLE_SIZE` where `h10` is the **top 10 bits of `n22`** for every
   hash type (the shifts in `hash_table_lookup` make 10-, 12- and 22-bit lookups start at the same
   slot). `gcd(23, 2^k) = 1`, so first-probe placement is injective up to 1,024 and collides above it.
2. 🔴 **`ft8_shim.c:695` — rejection is on `tbl->count`, not on a probe failure.**
   `if (tbl->count >= HASH_TABLE_SIZE) { reject; }`. **⇒ under the CURRENT policy, residency is a pure
   function of ARRIVAL ORDER**: the first `N` distinct callsigns are resident, everything after is
   rejected, and probe chains only decide *which slot*, never *whether*. This is what makes arm 1
   simulable at all without emulating the decoder.
3. 🔴 **`ft8_shim.c:653` — `hash_table_lookup` BREAKS at the first empty slot.** That is correct for an
   insert-only table and **silently wrong the moment anything is deleted**: removing an entry mid-chain
   makes every later entry on that chain unreachable. **Any eviction implementation must use tombstones
   or backward-shift deletion.** This is the single likeliest way an eviction patch loses decodes while
   looking correct, and it belongs in arm 2's design before a line is written. Arm 1 records it; it
   does not test it.
4. 🔴 **`ft8_shim.c:656` — a 10- or 12-bit lookup compares TRUNCATED bits**
   (`((entry.hash & 0x3FFFFF) >> sh) == hash`). Two different callsigns sharing the truncated bits both
   match, and **the first one on the probe chain wins ⇒ a lookup can return the WRONG callsign.**
   That population is invisible in `B1` (which counts *failures*) and **it grows as the table grows.**
   ⚠️ **A bigger table therefore has a cost, not just a benefit, and arm 1 must measure it.** This is
   the finding that could invert the obvious answer.
5. **`native/ft8_lib_vendor/ft8/message.c:557-590` — `save_callsign` is pure arithmetic on the callsign
   string**, so `n22` is computable offline in Python from the plaintext token alone. No DLL, no
   rebuild. Charset from `text.h:59`, exactly 38 characters:
   `" 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ/"`.
6. **`ft8_shim.c:615-629`'s own comment already names the alternative to eviction** — the table was
   256, went to 4,096, and the comment concedes "any finite table eventually saturates on a multi-day
   daemon". **Enlargement and eviction answer DIFFERENT questions** (§5.3), and arm 1 tests both.

---

## §1. The predicates, shipped AS CODE (HK-021(r))

🔴 **Per the sibling this project adopted today: the code below is normative and the prose is a gloss
on it, not the other way round.** Where the two disagree, the code wins, and QA reports the
disagreement.

```python
# --- 1. the FT8 hash, ported from message.c:557-590 -------------------------
FT8_CHARSET = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ/"   # text.h:59, 38 chars

def n22_of(callsign: str):
    """Returns the 22-bit hash, or None if the callsign leaves the charset
    (message.c returns false -> 'hash error (wrong character set)')."""
    n58 = 0
    for i in range(11):                       # 11 chars, space-padded (j = 0)
        if i < len(callsign):
            j = FT8_CHARSET.find(callsign[i])
            if j < 0:
                return None
        else:
            j = 0
        n58 = (38 * n58 + j) & 0xFFFFFFFFFFFFFFFF   # C uint64_t WRAPS -- keep the mask
    return ((47055833459 * n58) >> (64 - 22)) & 0x3FFFFF

def h10_of(n22):  return (n22 >> 12) & 0x3FF          # first-probe key, all hash types
def n12_of(n22):  return n22 >> 10
def n10_of(n22):  return n22 >> 12

# --- 2. plaintext-token predicate: IDENTICAL to B1-COVERAGE-A's, by reference -
#   qa/rr-study/b1-coverage-a/common_b1.py :: is_callsign_token + the
#   build_t_plain_index rule (token must NOT start with '<').
#   Import it. Do NOT re-implement it -- a second implementation is a second
#   chance to diverge, and this arm's whole population is defined by it.
```

⚠️ **The `& 0xFFFFFFFFFFFFFFFF` is load-bearing.** C's `uint64_t` wraps; Python's `int` does not.
Without the mask the port silently diverges for every callsign.

---

## §2. Inputs — pinned, nothing re-derived

| input | path | pinned value |
|---|---|---|
| L2 decode dump (current `main` build) | `artefacts/2026-08-25-g2a-remeasure-a/L2_run1_decodes.json` | `n_decodes` = 71,600; `dll_sha256`/`shim_version` = 20260046 as asserted by `common_b1` |
| L2 replicate | `…/L2_run2_decodes.json` | used for ROW 0e only |
| L1 decode dump (256-slot build) | `…/L1_decodes.json` | used for ROW 0b only |
| measured L2 freeze cycle | `…/L2_freeze_cycle.json` | **767 / 4,971** (`ts` `260803_202600`) |
| measured L1 freeze cycle | `…/L1_freeze_cycle.json` | **25 / 4,971** |
| `HASH_TABLE_SIZE` (current) | `ft8_shim.c:631` | **4,096** |
| addressable population | `qa/rr-study/b1-coverage-a/results/2026-08-26-2ed5f7d/result.json` | `B1-cap` = **307 decodes / 40 callsigns** |
| D-001 normalisation basis | pinned | `n_theirs` = **43,423** |

🛑 **No capture, no replay, no rebuild, no `src/` or `native/` edit.** Everything above is on disk.

---

## §3. The simulator

Two streams, both reconstructed from the L2 dump in cycle order (`ts` sorts chronologically):

- **INSERT stream `S`** — for every emitted decode, in `(ts, freq_hz)` order, every plaintext
  callsign-shaped token, in message order. Each is one `hash_table_add(callsign, n22_of(callsign))`.
- **LOOKUP stream `L`** — every decode carrying a hash-type field, split into:
  - **`L_fail`** — the `B1-cap` decodes (307): the lookup that failed, with the callsign `B1-COVERAGE-A`
    named for it. These are the ones a better policy should recover.
  - **`L_hit`** — every decode whose hash field RESOLVED (a bracket-wrapped token that is not the
    literal `<...>` marker — `add_brackets` on the success branch, ruling §2). **These are what a
    policy can BREAK, and they are why this arm is two-sided.**

The simulator replays `S` and `L` interleaved in cycle order against a table implementing
`hash_table_add`/`hash_table_lookup` **as transcribed from `ft8_shim.c:640-700`** — real probing, real
truncated-bit comparison, real `count`-based rejection — parameterised by size `N` and a replacement
policy.

**Hash type per lookup.** Take it from the message format where it is identifiable; **where it is
not, fall back to 22-bit and COUNT how many lookups took the fallback.** Report that count. If it
exceeds 10 % of `|L|`, report it as a stated limitation of the false-resolution figure (§5.2) —
it does not affect §5.1, whose outcome is residency, not bit-width.

### 3.1 Policies to simulate

| id | policy | size | question it answers |
|---|---|---:|---|
| `CUR` | fill-and-freeze (current) | 4,096 | baseline — must reproduce reality (ROW 0b) |
| `SZ2` / `SZ4` / `SZ8` | fill-and-freeze | 8,192 / 16,384 / 32,768 | **does simply making it bigger solve it?** (64 KB → 512 KB) |
| `LRU` | least-recently-used eviction | 4,096 | does a policy beat size at equal memory? |
| `LFU` | least-frequently-used eviction | 4,096 | is frequency a better signal than recency here? |
| `LRU-S` | least-recently-used eviction | 1,024 | **does policy beat size at 1/4 the memory?** |

Eviction policies must be simulated **with tombstones** (§0 fact 3), and QA must state which deletion
discipline was used.

---

## §4. ROW 0 — preconditions, strict order, stop where each row says

| row | check | bar | on failure |
|---|---|---|---|
| **0a** | Dump identity | `dll_sha256`, `shim_version`, `n_decodes` = 71,600 match `common_b1`'s pins | **VOID.** Wrong build. |
| **0b** | 🔴 **Simulator fidelity — the load-bearing row.** Run `CUR` at N=4,096 and at N=256 and read off the cycle at which the table first rejects. | **Both** must land in `[767, 1150]` and `[25, 40]` respectively. | **VOID the arm.** The simulator does not model the real table and no policy number from it means anything. |
| **0c** | Hash-port sanity | `n22_of` returns non-`None` for ≥ 99 % of session plaintext callsign tokens, and the count of `n22` collisions among the 16,320 distinct tokens lands in **[10, 100]** (birthday expectation over 2²² is ≈ 32) | **VOID.** A broken charset or a missing 64-bit mask lands far outside this. |
| **0d** | Predicate reuse | The token predicate is `common_b1`'s, **imported**, not re-implemented (assert by import, not by eye) | **VOID.** |
| **0e** | Determinism + independent input | `CUR` and `LRU` runs give byte-identical per-callsign outcomes on a re-run, and `L2_run2` reproduces `CUR`'s freeze cycle | **VOID.** |
| **0f** | Population reproduction | `\|L_fail\|` = **307** decodes / **40** callsigns, matching `result.json` | **VOID.** Different population, different arm. |
| **0g** | 🔴 **Predicate-movement exhibit (HK-021(q), adopted 2026-08-26).** The comparator must be shown to distinguish policies at all. | `SZ8` holds **32,768 slots against 16,320 distinct session callsigns, so it NEVER FILLS** ⇒ **every `L_fail` decode whose `ts` is later than its callsign's `T_plain` MUST resolve under `SZ8`.** Report that subset's size, then require **100 %** of it. Paste one redacted worked example (`CS-xxxxxx`, its `T_plain`, its B1 `ts`, resolved-under-`SZ8` / failed-under-`CUR`) into the report. | **VOID.** If a table that cannot fill still fails to resolve a callsign it demonstrably contains, the simulator's lookup path is broken and no policy number from it means anything. |

**ROW 0b's bracket, justified before the run** (HK-021(m), two-sided per HK-021(n)): the insert stream
is the **emitted-decode proxy**, measured at **96.5 %** recovery (`B1-COVERAGE-A` ROW 0d). Missing
inserts can only make the simulated table fill **later** than reality, never earlier — so the **lower**
bound is the measured cycle itself (767 / 25) and a simulated freeze *before* it means the simulator
is inserting things the real table did not. The upper bound is set at ≈1.5× the measured cycle, well
beyond the ~3.5 % shortfall's arithmetic expectation (~795), to leave room for the arrival profile
being front-loaded. **A pass here is the strongest validation available in this arm: two constants,
measured independently by direct instrumentation of the real DLL, that the simulator must hit without
being told them.**

⚠️ **What ROW 0b CANNOT detect (HK-022):** it validates *arrival order and count*, because that is all
`CUR` depends on (§0 fact 2). It does **not** validate the probe arithmetic or the truncated-bit
comparison, which `CUR`'s residency never exercises. **ROW 0c covers the hash; nothing in this arm
validates the probe chain**, so §5.2's false-resolution figure is the least-validated number here and
must be reported as **indicative, not citable**, until arm 2 measures it against the real DLL.

---

## §5. Metrics and gates

### 5.1 PRIMARY (GATED) — net recall at the callsign level

**Unit of analysis: the named callsign (`k` = 40).** Never decodes — one station is 52.5 % of
corroborated B1 (ruling §6), and a decode-weighted gate would describe that station and not a policy.

For each policy `P` and each of the 40 addressable callsigns, the outcome is the pair
(`resolves under CUR`, `resolves under P`) over that callsign's `L_fail` decodes, plus any of its
`L_hit` decodes `P` breaks. Score each callsign **improved / unchanged / worsened**.

**Statistic: an exact two-sided sign test on the discordant callsigns** (improved vs worsened). Paired,
because the same 40 callsigns are scored under both policies; the corpus's counts are exact and the
test exists only to generalise beyond this session (as in `B1-COVERAGE-A` §6.1).

| row | condition | consequence |
|---|---|---|
| **P0** | `n_discordant` < 6 for **every** policy | 🔴 **UNRESOLVED — under-powered, and it is on the record before the run.** At 40 paired units an all-one-way sign test needs **`n_discordant` ≥ 6** for two-sided `p` < 0.05 (`2 × 0.5⁶` = 0.031); at 5 the best attainable `p` is 0.063. **Report exact counts, propose nothing, and do NOT proceed to arm 2 on this corpus.** |
| **P1** | some policy has `n_discordant` ≥ 6, all-improved, `p` < 0.05, **and** §5.2's net decode count is positive | 🔴 **That policy is a candidate.** ⇒ **Arm 2 (shim change + replay) earns a pre-registration.** Still not a code change: arm 2 needs its own spec, a Developer session, and the Captain (HK-011). |
| **P2** | the best policy's net decode count is **≤ 0** | 🛑 **F-001 D3 CLOSED as a D-001 route.** The table is not the lever; say so and stop. |
| **P3** | neither | **INDETERMINATE.** Report counts; propose nothing. |

⚠️ **P1 requires BOTH a callsign-level test and a positive decode-level net.** A policy that helps 7
callsigns while losing more decodes than it gains is not a win, and the sign test alone cannot see that.

**Leave-one-out, MANDATORY and pre-registered:** re-run the primary with `CS-235335` (178/339 = 52.5 %
of corroborated B1) removed, `k` = 39. **If the fired row changes, there is no finding** — report the
flip as the result. This is not a sensitivity footnote; it is a second gate.

### 5.2 The counter-metric (mandatory, reported beside every policy)

| quantity | why it is here |
|---|---|
| **gained** decodes (`L_fail` that now resolve) | the upside, bounded by 307 |
| **lost** decodes (`L_hit` that now fail — eviction only) | 🔴 eviction can evict an entry that is later needed |
| **false resolutions** (a truncated-bit lookup matching the WRONG resident callsign, §0 fact 4) | 🔴 **grows with `N`** — the cost of `SZ8` that nobody would look for |
| **net** = gained − lost − false | the only number that may be quoted as a policy's benefit |

🔴 **No CI on any of these** — they are decode-weighted, `n_eff` ≈ 3.5 (standing PO/Captain ruling,
2026-08-25). Exact counts for this corpus, with the concentration table beside them, and never a
confidence interval. **`net` is also a LOWER bound**, for the same reason `B1-cap` is (inserts happen
at `unpack`, before the emit filter).

### 5.3 DESCRIPTIVE (ungated) — the question arm 1 exists to settle honestly

**Size and eviction answer different questions, and the report must say which one each policy answers:**

- **Enlargement** (`SZ2`…`SZ8`) serves a **bounded session**. 16,320 distinct callsigns in 20 hours
  means 32,768 slots (512 KB) covers this corpus with headroom — **and if `SZ8` recovers most of the
  307 with a `net` no worse than `LRU`, then the right change is a `#define`, not an eviction policy,
  and arm 2 should be scoped accordingly.** I consider this the likeliest outcome and I would rather
  say so before the run than claim the complicated answer afterwards.
- **Eviction** (`LRU`/`LFU`/`LRU-S`) serves an **unbounded daemon**. At ~20 k distinct callsigns/day,
  no fixed size survives a week. **If `LRU-S` at 1,024 slots beats `CUR` at 4,096, that is the finding**
  — it means the lever is the policy, at a quarter of the memory, and enlargement is a delay tactic.

Report both readings side by side. Report the per-policy decodes-per-callsign concentration. Nothing
in §5.3 gates anything.

---

## §6. HK-021 checks run against this spec while drafting

- **(m) resolution stated before the run:** yes — `n_discordant` ≥ 6 in §5.1, ROW 0b's bracket in §4.
- **(n) two-sided:** yes — P2 exists and is a real closing row; ROW 0b and ROW 0c are two-sided brackets.
- **(i) observation ≠ independence:** the unit is the callsign, never the decode; decode counts carry
  no interval anywhere.
- **(k) every precondition changes the verdict:** each ROW 0 failure VOIDs; none is diagnostic-only.
  🔴 **HK-025 stands — QA may refuse this spec on (k) grounds without my agreement.**
- **(o) readout quantum:** the primary's quantum is one callsign of 40 = 2.5 pp; every threshold above
  is stated in whole callsigns, not in proportions.
- **(p) bounded confound + PRE-REGISTER THE BUILD** *(adopted 2026-08-26, after this spec's first
  draft)*: this arm runs **one** binary's dump, not an A/B of two builds, so the build corollary is
  satisfied trivially — the dump's `dll_sha256`/`shim_version` are pinned in §2 and nothing is compared
  across binaries. The confound that *does* exist is the **emitted-decode proxy**, and its tolerance is
  stated as a number in two places rather than as a note: **ROW 0b's `[767, 1150]` / `[25, 40]`
  brackets**, and **§5.2's declaration that `net` is a LOWER bound.** ⚠️ **Arm 2 will not get off this
  lightly — it IS a binary A/B, and (p) requires its two legs to be built back-to-back from one working
  tree differing only in the table change. That belongs in arm 2's §2, not in QA's first hour.**
- **(q) predicate-movement exhibit** *(adopted 2026-08-26, after this spec's first draft — **ROW 0g was
  added by amendment to satisfy it**)*: §4 ROW 0g, with a pasted worked example. Without it this spec
  had no row that could tell "every policy behaves identically" apart from "the simulator compares
  nothing", which is exactly the failure (q) exists to catch.
- **(r) predicates shipped as code:** §1, and the token predicate is imported rather than restated.
- **(s) exposure-adjusted threshold:** 🔴 **checked and it does not apply** — no gate in this arm splits
  a population on a point in time. Recorded here so the check is visibly run, not silently skipped.
- **(j) absence needs λ ≥ 5:** if any policy's `lost` or `false` count is reported as **zero**, state
  the expected count under a stated model or report it as "not detectable at this exposure", never as
  "does not happen".

---

## §7. Architect predictions — blind, on the record before the run

1. **`SZ8` (32,768) recovers ≥ 250 of the 307** — high confidence. Arrival-order residency plus 16,320
   distinct callsigns makes this close to arithmetic.
2. **`LRU` at 4,096 recovers 150–260** — moderate. Depends entirely on callsign re-appearance locality,
   which nobody here has measured.
3. **`LRU-S` at 1,024 beats `CUR` at 4,096** — moderate-to-low confidence, and it is the result I most
   want to be true, which is exactly why it is written down first.
4. **`lost` > 0 for every eviction policy** — high confidence. **`net` for `LRU` still positive** —
   moderate.
5. **`false` resolutions rise monotonically with `N` and stay under 20 decodes at `SZ8`** — low
   confidence; this is the number I understand least and the one §4 already flags as least-validated.

---

## §8. Scope

- 🛑 No `src/`, no `native/`, no rebuild, no replay, no capture, no push, no merge, no
  `pre_merge_check.py` (HK-011, HK-014, HK-010, HK-006).
- 🛑 **This arm authorises NO code change of any kind.** Row P1's maximum consequence is that **arm 2
  earns its own pre-registration** — a spec, which then needs a Developer session and the Captain.
- 🛑 Does not re-open `ΔB1`. Does not touch `OSD-FA-A` (held). Does not touch the `BASE`+`WIDE`/140 Hz
  Developer session.
- 🛑 No spectral-locality metric under any name.
- NFR-021: counts, cycle timestamps, and `sha256[:6]`-redacted `CS-xxxxxx` tokens only. No message
  text, no real callsign in any JSON, log, report, or commit. **`n22` values are derived from real
  callsigns — treat them as identifying and do not emit them; report collisions as counts.**

---

## §9. Reporting and stopping

1. ROW 0 in strict order; stop at the scope each row names.
2. Callsign counts where the statistic is about callsigns, decode counts where it is about decodes,
   never conflated (HK-021(i)).
3. **Never print a decode-weighted proportion with a confidence interval.**
4. **Never quote a policy's `gained` without its `lost` and `false` in the same sentence** — `net` is
   the only citable benefit.
5. **Report the leave-one-out result beside the primary, always**, whether or not it flips.
6. Disclose every correction in full. **Where QA disagrees with this spec, QA is the result and I am
   the error** — and per HK-021(r), that includes the code in §1.
7. Stop at the gate. Update the board in the same edit as the result (HK-024).
