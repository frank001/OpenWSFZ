## Context

`F-001` gave the decoder a session-scoped callsign hash table so a nonstandard callsign announced in
one cycle resolves in a later one. For 12-bit hash references that table is a many-to-one map: a
probe chain can legitimately hold several matching callsigns, and today the decoder displays the
first one it finds.

`SUP-B` instrumented how often that happens, on the real table, on three bands. Two of three bands
returned `MARGINAL` against the frozen `S_max` = 40% bar, which by design escalates to the Product
Owner. The PO decided on 2026-09-01: **ship the unconditional unique-match rule on all bands**
("NO NAME BEATS A WRONG NAME"). This design implements that decision and nothing else.

**Design authority:**
`qa/rr-study/2026-09-01-1949-architect-to-qa-brief-f001-option-a-unique-match-suppression.md`.
**Decision authority:** `qa/rr-study/2026-09-01-1510-po-decision-f001-sup-b-step7-option-a.md`.

Two constraints shape everything below:

1. **The vendored `ft8_lib` tree is read-only to this project** in practice, and the standing licence
   policy makes any vendor diff a question worth avoiding. It turns out not to need one.
2. **The `SUP-B` instrument must survive the change it motivated.** It is the only way to re-measure
   this rule's effect, and it is what makes the acceptance criteria mechanical.

## Goals / Non-Goals

**Goals:**

- A 12-bit-hash-resolved callsign is displayed only when its probe chain holds exactly one match.
- A suppressed message keeps its decode; only the callsign token changes.
- The `SUP-B` counters keep reporting what *would* have been displayed, so prior readings stay
  comparable and the instrument predicts, in advance, how many output lines this change alters.
- The suppression is observable at runtime, per cycle.

**Non-Goals:**

- ❌ Deciding *which* of several ambiguous candidates is correct. That needs a truth source; `R6`
  rules against buying one.
- ❌ Measuring how many suppressed names were correct. Unmeasured, and an ACCEPTED RISK on record.
- ❌ Any per-band gating, runtime flag, staged default-off rollout, or configuration switch. The PO
  explicitly declined all of these and chose the unconditional rule directly.
- ❌ Moving `S_max`. It stays **FROZEN** at 40%; this build is Sec.6.4 exercised, not a bar move.
- ❌ `F-001` L3, the site-6 mitigation, and `ARM 2`. Separate, still-unscoped slices.
- ❌ Any change to the 22-bit or 10-bit hash paths.

## Decisions

### D1 — Suppress by returning "not found" from the project's own hash-lookup callback

**Decision:** `cb_lookup_hash` (`src/OpenWSFZ.Ft8/Native/ft8_shim.c`) returns `false` when the probe
chain is ambiguous. `native/ft8_lib_vendor/` is not modified.

**Why this works, verified in source on `main`@`68a014d`:** the vendored `lookup_callsign`
(`native/ft8_lib_vendor/ft8/message.c:594`) already writes `<...>` on its `!found` branch (`:606`),
and its **only** 12-bit call site (`:431`, inside `decode_nonstd`) **discards the return value**. A
12-bit lookup reported as not-found is therefore **not an error path**: `ftx_message_decode` still
returns `FTX_MESSAGE_RC_OK` and the message renders with the placeholder. The semantics we want fall
out of the vendored code as it already stands.

**Alternative considered — patch `message.c` to re-render after the fact.** Rejected. It was the
approach the PO decision record's §5 anticipated, on my own advice, and **that caveat is withdrawn**:
reading the code shows it is unnecessary. It would mean a vendor diff, a second rendering path to
keep in step, and string surgery on already-formatted text.

**Alternative considered — post-process the decoded text in the shim's emission block.** Rejected:
same string-surgery fragility, and it would have to re-identify which token was the hashed one.

⚠️ `hash_table_lookup` will already have written the resolved callsign into the caller's buffer
before we decide to suppress. That is harmless — `lookup_callsign` overwrites it with `<...>` and
never reads it again. **Do not "helpfully" clear that buffer**; leave the existing call untouched.

### D2 — The predicate is multiplicity ≥ 2, inside the 12-bit branch only

**Decision:** suppress when the probe-chain match count is two or more. Evaluate only inside the
existing `if (t == FTX_CALLSIGN_HASH_12_BITS)` block.

- **Multiplicity, not divergence.** The divergence signal is strictly narrower and is not what
  Option A ships. The rule is "display only on a unique match".
- `hash_table_lookup` stays byte-for-byte unchanged (`SUP-B` TRAP 1), as do `hash_table_add` and the
  `announce_stamp` mechanism (TRAP 2). Only the callback's own return changes.

### D3 — The instrument keeps counting; suppression rides a separate signal

**Decision:** the "the table resolved this hash" thread-local keeps its existing meaning and is set
from the table's own result. A **separate** thread-local carries the suppression decision. The
callback returns *resolved AND NOT suppressed*. The emission-point counters — displaying, ambiguous,
divergent, and the per-code cluster table — are **untouched**.

🔴 **This is the decision most easily got wrong.** The emission-point counters are gated on the
"resolved" flag. Expressing suppression by clearing that flag would collapse the displaying and
ambiguous counts toward zero the moment this ships, and **every ROW 0 reading already taken would
stop being comparable**. The instrument that motivated this change would be blinded by it.

**Payoff:** because the counters keep measuring what would have been displayed, the instrument
predicts the change's own effect. The number of output lines that differ from a pre-change run of
the same audio must equal the ambiguous count — a mechanical acceptance criterion available before
the code is written, and far stronger than a green test suite.

### D4 — Count suppression at the emission point, never in the callback

**Decision:** the callback sets a flag; the process-lifetime counter increments in the emission block,
beside its three siblings.

🔴 **`SUP-B`'s TRAP 3 fires again here, and the obvious implementation walks into it.** The callback
runs during text decode, which also runs for messages whose decode then fails and which are never
emitted. A counter incremented in the callback would measure decode **attempts** while the ambiguous
counter measures **displays** — the two would disagree, and the disagreement would look like a defect
in the predicate when it is only an artefact of where the increment was placed.

📌 **Stated honestly:** once wired this way the suppressed count is arithmetically identical to the
ambiguous count and carries no new information in the nominal case. Its value is as a **wiring
invariant** between the site that decides and the site that counts. **What it cannot detect is an
error in the multiplicity computation itself** — both counts descend from it. The behavioural
scenarios cover that; this counter does not.

### D5 — Version bump, and the Windows-only export trap

**Decision:** `FT8_SHIM_VERSION` / `ExpectedShimVersion` `20260048` → `20260049`, with a changelog
entry stating plainly that — unlike `20260047` and `20260048` — **this bump changes decode output**.

🔴 **`native/ft8_lib_build/rebuild_shim.bat` carries an explicit `/EXPORT:` list; the Linux build
script carries none** (default visibility). A getter added to the header and the `.c` but omitted
from that list **builds clean and links clean on Linux, and fails only on Windows, only at runtime,
on `P/Invoke` resolution.** The export line is part of the change, not an afterthought.

macOS ARM64 is not rebuilt locally (no Mac on the bench); CI's `macos-latest` leg owns it, as on
every prior native change. The local pre-merge warning about it is **expected and permanent**, not a
finding.

### D6 — Managed surface: full binding and a per-cycle log line

**Decision (Product Owner, 2026-09-01):** native counter **plus** a C# binding **plus** the per-cycle
log line, chosen over a native-only counter (readable by the replay harness but invisible in live
operation) and over no counter at all.

**Cost, verified by search rather than inherited: 13 files declare an `IFt8NativeInterop`
implementation** — 12 in `tests/`, plus the production adapter — each needing a fixed-zero stub.
⚠️ The `f001-sup-b-instrumented-suppression-sizing` proposal's "11 implementers" is **stale**; do not
plan against that number.

## Risks / Trade-offs

- **Suppressed names may have been correct, and how many is unmeasured** → Bounded, not removed, by
  two things already on record: the sizing ratio is an **upper bound on UX cost and never
  correct-name loss**, and the suppressed set is *enriched* for wrong names by construction
  (enriched ≠ mostly wrong). 🛑 **ACCEPTED RISK, taken by the PO with the Architect's concern on the
  record.** Do not re-open it as a new finding, and do not propose a capture run to resolve it.
- **The instrument gets blinded by the change it motivated** → D3. Called out as the primary
  implementation hazard, and pinned by a spec scenario rather than left to reviewer vigilance.
- **The suppression counter silently measures the wrong population** → D4, pinned by its own
  scenario (a suppressed lookup whose decode later fails must not increment it).
- **The new export is missing on Windows only** → D5, pinned by a scenario that explicitly states a
  successful Linux build does not satisfy it.
- **Scope creep into the 22-bit path or into `hash_table_lookup`** → D2 plus an explicit
  must-not-change list; the diff is small enough that a reviewer can confirm it by inspection.
- **The design rests on reading the vendored decoder, not on running it** → ⚠️ The `message.c`
  analysis in D1 is a **read**, not an execution. The replay-based acceptance criteria are what
  actually prove it; D1 is not verification.

## Migration Plan

There is no data migration. The rollout is a native rebuild plus a managed constant bump, which the
ABI self-test already makes fail-fast and unambiguous: a mismatched binary throws on first load
rather than decoding subtly differently.

**Rollback** is reverting the change and rebuilding at `20260048`. Nothing persists across the
change — no schema, no on-disk format, no stored state. The hash table is process-scoped and rebuilt
every session either way.

**Verification before merge** rests on a replay of the `S-17M` corpus, comparing against a pre-change
run of the same audio:

1. decode count identical — zero gained, zero lost;
2. the number of differing lines equals the instrument's own ambiguous count;
3. every differing line differs only by one bracketed callsign token becoming `<...>`, with
   frequency, DT, SNR and payload byte-identical;
4. suppressed count equals ambiguous count exactly.

The replay is QA harness work (`qa/` tooling); the unit-level scenarios and the build gates belong to
the Developer session.

## Open Questions

- 🔴 **Archive ordering against `f001-sup-b-instrumented-suppression-sizing`.** That change's spec
  deltas have **not** been merged into `openspec/specs/` — the base `ft8lib-interop` spec still reads
  `20260046`, and the base `hashed-callsign-resolution` spec carries none of the 12-bit sizing
  Requirements. This change's deltas are written against `SUP-B`'s deltas as their baseline (its
  `20260048` pin, its counters). **`SUP-B` must be spec-synced and archived first**, or this change's
  `MODIFIED` block will overwrite version history that was never recorded. Whoever archives is the
  one who must check this; it is not automatic.
- **Should the accidental startup behaviour of the 12-bit path be pinned while we are here?** Out of
  scope as written, and deliberately not folded in — raised only so it is not mistaken for an
  oversight later.
- **Does any downstream consumer (ADIF log, decode panel filtering, QSO answerer) treat `<...>` as a
  parse failure rather than a legitimate unresolved callsign?** The placeholder already occurs today
  for never-announced hashes, so the path is exercised — but this change makes it **more frequent**,
  and no one has measured whether any consumer's behaviour is frequency-sensitive. Worth one
  deliberate check during implementation rather than an assumption either way.
