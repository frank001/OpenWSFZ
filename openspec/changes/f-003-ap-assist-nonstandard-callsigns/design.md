## Context

`Ft8CallsignPacker.Pack28()` (`src/OpenWSFZ.Ft8/Ft8CallsignPacker.cs`) exists solely to build
28-bit a-priori (AP) LDPC decode-assist hints — it packs a known callsign into the same 28-bit
`c28` representation `ft8_lib` uses on the wire, so the native decoder can bias its LDPC search
toward a specific, already-known message rather than searching blind. It is consumed by
`QsoAnswererService.ApplyApConstraints()` and `QsoCallerService`'s equivalent, both of which
call `Pack28` for `mycall` and `hiscall` and, on either returning an empty array, disable AP
entirely for the QSO (`SetApConstraints(null)`).

Today `Pack28` only implements the standard-basecall branch of `c28`'s three-way partition
(`f-001-hashed-callsign-resolution/design.md`'s Context section documents this partition in
full): special tokens (`n28 < NTOKENS`), a 22-bit nonstandard-callsign hash
(`NTOKENS ≤ n28 < NTOKENS + MAX22`), and standard basecalls (`n28 ≥ NTOKENS + MAX22`, the only
branch implemented). The *decode* side already handles all three branches correctly — this
project's own decoded text output includes directed-CQ forms (`Ft8Decoder.cs` already documents
and scores `"CQ <modifier> <call> <grid>"`, e.g. `"CQ DX Q1ABC FN42"`), proving the native
`ft8_lib` unpacker fully supports them. The gap is entirely on the *encode* side, and entirely
in this managed-layer packer — `f-001`'s persistent hash table already makes the decode side
correctly resolve a hashed callsign; this change is what lets the packer *produce* AP hints for
the same population.

**Reference values (confirmed, cited).** `NTOKENS = 2,063,592`, `MAX22 = 4,194,304`, and the
special-token assignments `DE=0`, `QRZ=1`, `CQ=2`, `"CQ nnn"` (3-digit numeral suffix) `= 3+nnn`
(i.e. `CQ 000=3` … `CQ 999=1002`) are documented with source citation (Franke/Somerville/Taylor,
*QEX* 2020, §III-A Table I) in `qa/rr-study/synth/packing.py`'s `_pack_callsign` — an
independent second implementation of the published protocol (not a port of `ft8_lib`), already
used as the R&R study's encode-side test oracle. The `ihashcall` formula itself is documented in
`f-001-hashed-callsign-resolution/design.md`'s Context section and already implemented natively
in `ft8_shim.c`; this change needs a **second**, independent C# implementation (see D2) rather
than a shared native call, matching the project's existing convention of the QA synth encoder
being an independent oracle rather than a port of the code under test.

**Not yet confirmed.** The directed "CQ ABCD" form (a 2–4 character token after CQ that is
*not* purely numeric — `"CQ DX"`, `"CQ NA"`, `"CQ POTA"`, contest/activity-specific directed
calls) is real and already decodes correctly (see above), but neither `packing.py` (which defines
only `DE`/`QRZ`/`CQ`/`CQ nnn` and falls through to the hash branch for anything else, meaning it
has never actually been asked to *encode* this form) nor `f-001`'s design doc documents its exact
`c28` encoding. This needs sourcing from the vendored `ft8_lib` source
(`native/ft8_lib` — shallow-cloned at build time, not committed to this repo) or WSJT-X's
`packjt77.f90` at implementation time, mirroring `f-001` design D4's precedent of confirming an
exact value against the real source rather than assuming a documented figure is still current.

## Goals / Non-Goals

**Goals:**
- `Ft8CallsignPacker` packs a plain `"CQ"` token, `"DE"`, `"QRZ"`, `"CQ nnn"` (3-digit numeral),
  and any nonstandard/compound callsign (3–11 characters, via `ihashcall`) into a correct 4-byte
  MSB-first `c28` representation, so `ApplyApConstraints` no longer needs to disable AP for
  these cases.
- AP-assisted decode is armed for a QSO whenever *both* `mycall` and `hiscall` are packable —
  which, after this change, includes standard basecalls, the tokens above, and nonstandard
  callsigns.
- No behavioural change to the existing standard-basecall packing path (same inputs produce the
  same 4-byte output as today).

**Non-Goals (this change):**
- The directed "CQ ABCD" form is **not required** for this change to ship (see Open Questions
  and Context's "Not yet confirmed" note). It is real, already decodes correctly, and packing it
  is a natural follow-on once its exact `c28` encoding is confirmed — but gating this entire
  change on that confirmation would block the two much more common, well-sourced cases (plain
  `CQ`, and nonstandard callsigns — the actual population `f-001` was written for) on a detail
  that mostly matters for contest/activity operators, a narrower slice of Gap B's motivation.
  Tracked as a follow-on task (see tasks.md) rather than silently dropped.
- No native shim change. `Ft8ApConstraints`/`Ft8Decoder.SetApConstraints`/native
  `ft8_set_ap_bits` already accept an arbitrary packed 28-bit value with no validation of which
  `c28` sub-range it falls in — the shim's AP-bit injection loop (shim `20260021`, per
  `Ft8CallsignPacker.cs`'s own doc comment) reads whatever 28 bits it is given. Confirmed by
  reading the existing shim/interop code during this design; no further native investigation
  needed unless implementation reveals otherwise.
- No change to `/R` or `/P` suffix handling beyond what nonstandard-callsign hashing already
  implies (a suffixed nonstandard callsign hashes as given, matching `packing.py`'s documented
  behaviour for the equivalent QA-oracle case — see its `ipa`/rover-flag doc comment).
- Persisting or looking up *remote* nonstandard callsigns' hashes is out of scope — that's
  `f-001`'s already-shipped decode-side table. This change only needs to hash a callsign string
  the caller already has in hand (the operator's own callsign, or a partner callsign already
  known from a decoded exchange), not resolve one.

## Decisions

### D1 — Extend `Pack28` in place, don't add a parallel method

`Pack28`'s two call sites (`QsoAnswererService`, `QsoCallerService`) already treat "empty array"
as the uniform "can't pack this, disable AP" signal. Adding the token/hash branches as additional
cases inside `Pack28` itself (rather than a new `Pack28Extended` or similar) means both call
sites need **no logic change** beyond passing whatever callsign string they already have — the
widening happens entirely inside the packer, which is exactly what the proposal's Impact section
scoped ("wire the extended packer into `ApplyApConstraints`", not "call a different method").

Alternative considered: a new method with the old `Pack28` left untouched for backward
compatibility. Rejected — nothing else in the codebase depends on `Pack28` returning `[]` for
non-standard input as meaningful behaviour (both call sites treat it purely as a failure signal,
not a distinguishable case), so there is no compatibility surface to preserve, and a second
method would just duplicate the byte-packing/bit-layout tail end of the function for no benefit.

### D2 — Independent C# `ihashcall`, not a P/Invoke into the native shim

The native shim already computes `ihashcall` internally (for its own encode/decode paths), but
it is not exported as a callable entry point — exporting one purely so the managed packer could
call it would add new P/Invoke surface for a ~10-line pure-integer function with no I/O, no
allocation, and no dependency on native state.

**Decision**: port the formula directly into C# (`n8 = 38*n8 + char_index` over up to 11
characters from the documented charset, then `hash = (47055833459 * n8) >> (64-m)`), matching
`packing.py`'s existing independent port line-for-line where practical. Test against the same
known-vector table `packing.py`/its tests already use, plus cross-check a handful of values
against `packing.py` itself at test time (belt-and-braces, not a substitute for the shared
published-formula test vectors — a bug shared between this port and `packing.py` would not be
caught by cross-checking the two against each other, only against the independently-sourced
vector table).

Alternative considered: export a new `ft8_ihashcall` entry point from the shim and P/Invoke it.
Rejected for this change — adds ABI surface (new export, new shim version bump, new interop
marshalling) for a pure function with zero native-state dependency; revisit only if a future
need for bit-exact native parity (rather than "matches the published formula") emerges.

### D3 — "CQ ABCD" deferred, not guessed

Per Non-Goals, the directed "CQ ABCD" form's exact `c28` encoding is not sourced with confidence
right now. Rather than encode a guessed value (wrong AP hints are worse than no AP hint — they
actively mislead LDPC toward the wrong codeword) or block this entire change on confirming it,
`Pack28` returns `[]` for this specific shape exactly as it does today, with a tracked follow-up
task to confirm the encoding from the vendored `ft8_lib` source at implementation time of that
follow-up (mirroring `f-001` design D4's "confirm the actual value at implementation time, don't
assume" precedent) and add it as an additional branch once confirmed.

Alternative considered: block this change until "CQ ABCD" is confirmed. Rejected — plain `CQ`
and nonstandard-callsign hashing (the two well-sourced, high-value cases) would sit unshipped
waiting on a narrower, lower-frequency case.

## Risks / Trade-offs

- **[Risk] A wrong `ihashcall` port produces a plausible-looking but incorrect AP hint**, which
  could actively *hurt* decode (biasing LDPC toward a codeword that isn't the transmitted one) —
  worse than today's "AP disabled" fallback. **Mitigation**: test against the same known-vector
  table already validated for `f-001`'s native shim and `packing.py`'s independent port; add an
  integration test that AP-assisted decode of a real nonstandard-callsign exchange still
  succeeds (proposal's Testing item), not just that the packer's bytes match a table.
- **[Risk] "CQ ABCD" silently continues to disable AP** for that specific directed-CQ shape
  after this change ships, which could read as "still broken" to an operator who doesn't know
  the distinction. **Mitigation**: D3's explicit follow-up task; this design doc and the
  proposal's Non-Goals are the record of why, so it isn't lost the way it nearly was between
  `f-001` and this change.
- **[Trade-off] Two independent `ihashcall` implementations to maintain** (native shim,
  `packing.py`, and now this C# port) — a shared-bug risk if the published formula itself is
  ever found to be wrong or ambiguous. **Accepted**: matches this project's existing convention
  (the QA synth encoder is deliberately independent of the shim under test, per
  `architecture-ft8-lib` conventions) and the alternative (P/Invoke, D2) has its own cost.

## Migration Plan

- Managed-only change; no data migration, no persisted state, no ABI/native surface change
  expected (D1 Non-Goals).
- Rollback is a straight revert; `QsoAnswererService`/`QsoCallerService` need no corresponding
  change either way since they already treat `Pack28`'s return value generically.
- Roll out behind the existing test suite: packer unit tests against known vectors, then the
  AP-assisted-decode integration test, before wiring into the two QSO services.

## Open Questions

- Exact `c28` encoding for the directed "CQ ABCD" form — confirm from vendored `ft8_lib` source
  or WSJT-X's `packjt77.f90` when that follow-up task is picked up (D3).
- Should `Pack28`'s existing empty-array-means-disable-AP contract at the two call sites be
  tightened to distinguish "genuinely unpackable" from "not yet implemented" (e.g. for logging
  clarity when "CQ ABCD" is hit)? Recommend deferring — the existing warning log at both call
  sites already names which callsign failed to pack, which is enough signal for now; a
  finer-grained reason code is only worth adding if field logs show this case is common enough
  to want the distinction.
