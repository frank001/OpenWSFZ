# Architect → QA brief — `F-001` Option A: 12-bit unique-match suppression

**From:** the Architect
**For:** QA (authors the `dev-tasks/*.md` — HK-015), the Developer session that builds it (HK-011),
the Captain (diff review and merge — HK-010)
**Date:** 2026-09-01 19:49 UTC
**Implements:** `qa/rr-study/2026-09-01-1510-po-decision-f001-sup-b-step7-option-a.md` (PO decision,
Option A, "NO NAME BEATS A WRONG NAME")
**Branch:** `feat/f001-h12-unique-match-suppression`, off `main`@`68a014d`

🛑 **This brief authorises NOTHING on its own.** It is a design document. HK-015: the `dev-tasks/*.md`
is QA's to author, not mine. HK-011: the `src/` + native change needs a separate Developer session and
the Captain's diff review. HK-014: this branch is local and unpushed.

---

## 1. What is being built, in one sentence

When a decoded message's 12-bit callsign hash resolves against **more than one** entry in the session
hash table, the name is **not displayed** — the message renders `<...>` in its place, and the decode
itself is kept.

That is the whole behaviour change. Everything below is about doing it without breaking the
instrument that measured it, and without touching the vendored decoder.

---

## 2. Correction to the decision record — the `message.c` caveat is WITHDRAWN

🔴 **The Option A decision record's §5 carried this caveat, and it was mine:**

> *"the callsign is already substituted into the rendered text upstream in `message.c`, so undoing the
> substitution cleanly may belong in `message.c`'s decode path rather than at the counting site.
> Small, not zero."*

**I have now read that path, and the caveat is wrong. It is withdrawn, and nothing should be built on
it.** Evidence, read on `main`@`68a014d`, not inherited:

`native/ft8_lib_vendor/ft8/message.c:594` — `lookup_callsign` **already** renders the unresolved form
itself when the lookup reports failure:

```c
static bool lookup_callsign(const ftx_callsign_hash_interface_t* hash_if,
                            ftx_callsign_hash_type_t hash_type, uint32_t hash, char* callsign)
{
    char c11[12];
    bool found;
    if (hash_if != NULL) found = hash_if->lookup_hash(hash_type, hash, c11);
    else                 found = false;

    if (!found) { strcpy(callsign, "<...>"); }        /* :606 */
    else        { add_brackets(callsign, c11, strlen(c11)); }
    ...
    return found;
}
```

And at the **only** 12-bit call site — `message.c:431`, inside `decode_nonstd` — **the return value is
discarded**:

```c
    /* Decode the other call from hash lookup table */
    char call_3[14];
    lookup_callsign(hash_if, FTX_CALLSIGN_HASH_12_BITS, n12, call_3);   /* :431, return ignored */
```

⇒ **A 12-bit lookup that reports "not found" is not an error path.** The message decodes normally and
renders `<...>` in that position. `ftx_message_decode` still returns `FTX_MESSAGE_RC_OK`.

**Two consequences, both good:**

1. ✅ **`native/ft8_lib_vendor/` is NOT touched by this change.** No vendor patch, no string surgery on
   already-rendered text, no re-render.
2. ✅ **The semantics land exactly on the PO's decision:** the name becomes `<...>`, **the decode
   survives**. This is what the decision's scale arithmetic assumed ("would become `<...>`"), and it is
   now confirmed in source rather than hoped for.

⚠️ **Honest limit:** I have **read** these paths, not executed them. §6's acceptance criteria are what
prove it. Do not treat §2 as verification.

---

## 3. The mechanism — where the change goes

Everything needed is already present and already ROW-0-verified. Verified line references, all
`src/OpenWSFZ.Ft8/Native/ft8_shim.c` on `main`@`68a014d`:

| What | Where | State today |
|---|---|---|
| `hash_table_count_h12_multiplicity` — read-only probe replay, counts matches | `:668` | shipped (`20260047`) |
| `g_h12_displaying` / `g_h12_ambiguous` / `g_h12_divergent` | `:718`–`:720` | shipped |
| `tls_h12_lookup_performed` / `_resolved` / `_multiplicity` / `_divergent` / `_code` | `:791`–`:794` | shipped |
| **`cb_lookup_hash`** — our callback; calls `hash_table_lookup`, then counts multiplicity | `:796`–`:810` | **the change goes here** |
| Native getters | `:1191`–`:1193` | shipped |
| **Emission point** — `tls_h12_multiplicity >= 2` already evaluated here | `:1617`–`:1631` | shipped |
| `FT8_SHIM_VERSION 20260048` | `ft8_shim.h:661` | to bump |
| `ExpectedShimVersion = 20260048` | `Ft8LibInterop.cs:398` | to bump |

**The predicate is already computed one statement above the return we need to change.** `cb_lookup_hash`
calls `hash_table_count_h12_multiplicity` into `tls_h12_multiplicity` (`:804`) and *then* returns
`found` (`:810`). Option A is: return `false` instead, when that count is ≥ 2.

---

## 4. Design decisions

### D1 — Suppress by returning `false` from `cb_lookup_hash`. Do not touch `message.c`.

Rationale in §2. The suppression decision is made in **our** code, in the shim we own, at the point
where the information already exists. The vendored MIT decoder renders the result.

⚠️ `hash_table_lookup` will already have written the resolved callsign into the `cs` buffer before we
decide to suppress. That is harmless — `lookup_callsign` overwrites the caller's buffer with `<...>`
on the `!found` branch and never reads `c11` again. **The Developer must not "helpfully" clear `cs`**;
leave the existing call and its buffer exactly as they are.

### D2 — The predicate is `tls_h12_multiplicity >= 2`, inside the 12-bit branch only.

- **Scope is `FTX_CALLSIGN_HASH_12_BITS` and nothing else.** The 22-bit path (`message.c:782`) and the
  10-bit path are untouched. The existing `if (t == FTX_CALLSIGN_HASH_12_BITS)` block is the boundary.
- The predicate is **multiplicity**, *not* divergence. `divergent` is a strictly narrower signal and is
  **not** what Option A ships. This is the "unconditional unique-match rule": display only when the
  probe chain holds exactly one match.
- 🛑 **`hash_table_lookup` itself stays byte-for-byte unchanged (SUP-B TRAP 1), and so does
  `hash_table_add` / `announce_stamp` (TRAP 2).** Only `cb_lookup_hash`'s own return changes.

### D3 — The instrument must keep counting. This is the decision most easily got wrong.

The SUP-B counters are gated at the emission point on `tls_h12_lookup_performed && tls_h12_resolved`
(`:1616`). 🔴 **If the fix expresses suppression by setting `tls_h12_resolved = false`, then
`g_h12_displaying` and `g_h12_ambiguous` collapse toward zero the moment this ships — and we lose both
the ability to re-measure and any way to check the fix did what we think.**

**Required shape:**

- `tls_h12_resolved` continues to mean **"the table resolved it"** — unchanged semantics, set from
  `found` exactly as today.
- Add `tls_h12_suppressed`, set in `cb_lookup_hash` when the predicate fires.
- `cb_lookup_hash` returns `!suppressed && found`.
- The emission-point block (`:1616`–`:1632`) keeps incrementing **every existing counter exactly as it
  does today**, including the 4,096-row by-code table.

⇒ Every ROW 0 reading already taken stays comparable, and the instrument continues to report what
*would* have been displayed.

### D4 — New suppression counter, incremented at the EMISSION POINT, never in the callback.

The PO chose native counter **plus** a C# binding and a per-cycle log line (2026-09-01).

🔴 **TRAP — SUP-B's TRAP 3 applies again, and the obvious implementation walks straight into it.**
`cb_lookup_hash` fires during `ftx_message_decode`, which runs for messages that are **later
discarded** when the decode fails (`ft8_shim.c:1604`, `continue`). A counter incremented inside the
callback would therefore count **decode attempts**, while `g_h12_ambiguous` counts **displays** — the
two would not agree, and the disagreement would look like a defect in the predicate when it is only an
artefact of where the `++` was placed.

⇒ **Set a thread-local flag in the callback; increment `g_h12_suppressed` in the emission block at
`:1616`, alongside its three siblings.**

📌 **Stated honestly, because HK-022 asks it of every check:** once wired this way, `g_h12_suppressed`
is **arithmetically identical to `g_h12_ambiguous`** on every run, and carries no new information in
the nominal case. Its value is as a **consistency invariant** (AC-4): it is read at the *decision* site
and reported at the *emission* site, so a divergence proves a wiring fault between the two. **What it
cannot detect: an error in the predicate itself** — both counters descend from the same
`tls_h12_multiplicity`, so a wrong multiplicity is invisible to this check. That is AC-5's job.

### D5 — Version bump and the Windows-only export trap.

- `FT8_SHIM_VERSION` `20260048` → **`20260049`** (`ft8_shim.h:661`) with a changelog entry naming the
  mechanism and stating plainly that, unlike `20260047`/`20260048`, **this one changes decode output**.
- `ExpectedShimVersion` → `20260049` (`Ft8LibInterop.cs:398`).
- 🔴 **`native/ft8_lib_build/rebuild_shim.bat` carries an explicit `/EXPORT:` list (`:155`–`:158`); the
  Linux build script has none** (default visibility). A new getter that is added to the header and the
  `.c` but not to that list **builds clean and links clean on Linux and fails only on Windows, only at
  runtime, on P/Invoke resolution.** Add the `/EXPORT:` line.
- macOS ARM64 is not rebuilt locally (no Mac) — CI's `macos-latest` leg owns it, as on every prior
  native change. This is expected and is **not** a finding.

### D6 — Managed surface.

`GetH12SuppressedCount()` on `IFt8NativeInterop`, mirroring the three existing members
(`IFt8NativeInterop.cs:71/77/85`), through `Ft8LibInterop` and `Ft8NativeInteropAdapter`, folded into
`Ft8Decoder`'s existing per-cycle h12 log line.

⚠️ **Cost, verified by grep not inherited: 13 files declare an `IFt8NativeInterop` implementation** —
12 in `tests/`, plus the production adapter. Each needs a fixed-zero stub. (The SUP-B proposal's
"11 implementers" is now **stale**; do not plan against that number.)

---

## 5. Scope — what changes, and what must not

**Changes:**

- `src/OpenWSFZ.Ft8/Native/ft8_shim.c` — `cb_lookup_hash` predicate + return; one thread-local; one
  process counter; one getter; emission-block `++`.
- `src/OpenWSFZ.Ft8/Native/ft8_shim.h` — version bump, getter declaration, changelog.
- `src/OpenWSFZ.Ft8/Interop/{IFt8NativeInterop.cs,Ft8LibInterop.cs,Ft8NativeInteropAdapter.cs}`,
  `src/OpenWSFZ.Ft8/Ft8Decoder.cs` — one member each, plus the log line.
- The 12 test-double implementers — fixed-zero stubs.
- `native/ft8_lib_build/rebuild_shim.bat` — one `/EXPORT:` line; rebuilt Windows + Linux binaries.
- New tests (§6, AC-5).

🛑 **Must NOT change:**

- `native/ft8_lib_vendor/**` — **anything at all** (§2; also the standing licence policy's
  read-for-method boundary is not at issue here, but a vendor diff invites the question).
- `hash_table_lookup`, `hash_table_add`, `announce_stamp`, `hash_table_count_h12_multiplicity`.
- The existing emission-point counters' semantics (D3).
- The 22-bit and 10-bit hash paths.
- `S_max` = 40%, which stays **FROZEN**. This build is the *consequence* of an escalation resolved by
  the PO under Sec.6.4, **not** a bar move (decision record §1).

---

## 6. Acceptance criteria

The strong ones are AC-2 and AC-3: **the already-shipped instrument predicts, in advance and
mechanically, exactly how many output lines this change should alter.** That is a far better proof
than a green suite.

| # | Criterion | How it fails |
|---|---|---|
| **AC-1** | On a replay of the `S-17M` corpus, the decode **count** is identical to the pre-change run: zero gained, zero lost. | Any delta ⇒ suppression is killing decodes, not names ⇒ **STOP**, the change is wrong. |
| **AC-2** | The number of decode lines whose text differs from the pre-change run **equals** `ft8_get_h12_ambiguous_count()` read from the same run. | Any mismatch ⇒ the predicate is firing somewhere other than where the instrument counted. |
| **AC-3** | Every differing line differs **only** by one bracketed callsign token becoming `<...>`. Frequency, DT, SNR and payload byte-identical. | A changed numeric field ⇒ the change has escaped its scope. |
| **AC-4** | `ft8_get_h12_suppressed_count() == ft8_get_h12_ambiguous_count()`, exactly, on every run. | Divergence ⇒ wiring fault between decision site and emission site (D4). |
| **AC-5** | Unit test: a table seeded so two synthetic callsigns collide on one 12-bit code ⇒ that message renders `<...>`; a uniquely-matching code ⇒ still renders the bracketed callsign. Both directions, one test each. | — |
| **AC-6** | ABI self-test passes at `20260049` on all three platforms; the new symbol resolves on **Windows** (D5's trap) and Linux. | — |
| **AC-7** | Full suite green; Gate G10 (`check_test_delay_sync.py`) OK; NFR-021 scan **post-commit** CLEAN. | — |

📌 **AC-1–AC-4 need a replay run, which is QA harness work** (`qa/` tooling — HK-011 does not apply to
it). AC-5–AC-7 are the Developer session's.

🔒 **NFR-021:** AC-5's fixtures use **Q-prefix synthetic callsigns only** (e.g. `Q1ABC`, `Q2XYZ`
chosen to collide). No real callsign enters a test, a fixture, or this branch.

---

## 7. What this brief does NOT authorise

- 🛑 No push, no merge, no `pre_merge_check.py` (HK-006 — Captain's initiative only).
- 🛑 **No re-opening the accepted risk.** At `S-17M`'s CI upper bound this withholds a large share of
  currently-displayed 12-bit names and **how many were correct is unmeasured**. That is on the record
  as an ACCEPTED RISK taken with my concern stated (decision record §2). It is not a new finding and
  must not be re-raised as one.
- 🛑 **No capture run to resolve it** — R6 stands.
- 🛑 No pooling, no "two of three" result, no bare `1,582/847` (R1/R3 stand). Each band remains citable
  only as point estimate paired with its own interval.
- 🛑 No work on `F-001` L3, on the site-6 mitigation, or on `ARM 2`. Different slice, still unscoped.
- 🛑 No flag, no staged default-off rollout — the PO explicitly did **not** take that path.

---

## 8. Recommended sequence

1. **OpenSpec change entry, opened BEFORE the Developer session.** 🔴 **A new change — NOT an extension
   of `f001-sup-b-instrumented-suppression-sizing`**, whose proposal states in terms that *"Both phases
   are MEASURE-ONLY. No unique-match suppression rule is implemented, enabled, or flagged by this
   change."* A behaviour change does not belong inside a measure-only change. Suggested id:
   `f001-h12-unique-match-suppression`. Capabilities touched: `hashed-callsign-resolution` (a real
   behaviour Requirement, the first one that is not read-only) and `ft8lib-interop` (shim constant
   `20260048` → `20260049`, one new exported getter with a managed binding).
2. **QA authors `dev-tasks/*.md`** from this brief (HK-015), re-verifying every cited line
   independently (HK-018/HK-022), then stops (HK-011).
3. **Developer session** makes the edit; QA's replay run covers AC-1–AC-4.
4. **Captain** reviews the diff and rules on the merge (HK-010).

📌 Also worth landing with this work: `qa/sup-b-step7-2026-08-31` (6 commits, unpushed) carries the PO
decision record this brief implements. It should not stay stranded — Captain's call.

---

## Sources

- `qa/rr-study/2026-09-01-1510-po-decision-f001-sup-b-step7-option-a.md` — the decision (§1, §2 risk,
  §4 sequencing, §5 mechanism).
- `src/OpenWSFZ.Ft8/Native/ft8_shim.c` — read on `main`@`68a014d` for every line cited in §3.
- `native/ft8_lib_vendor/ft8/message.c:431`, `:594`–`:612` — the §2 correction.
- `openspec/changes/f001-sup-b-instrumented-suppression-sizing/proposal.md` — the MEASURE-ONLY scope
  statement that §8.1 turns on.
