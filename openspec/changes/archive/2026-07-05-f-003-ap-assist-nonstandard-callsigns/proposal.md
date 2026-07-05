## Why

`f-001-hashed-callsign-resolution` gave the native decoder a session-scoped callsign hash
table, so a nonstandard/compound callsign (`PJ4/K1ABC`, special-event calls) announced once via
a Type 4 message now resolves correctly when referenced by 22-bit hash in a later cycle. That
was deliberately the *only* thing that change shipped — it left "Gap B" (AP-assisted decode for
these same callsigns) as an explicitly deferred stretch item, because hinting a hash the decoder
couldn't yet look up would have bought nothing. The prerequisite is now in place and merged.

Today, `Ft8CallsignPacker.Pack28()` only encodes standard 6-character basecalls. For anything
else — special tokens (`CQ`/`DE`/`QRZ`, "CQ nnn", "CQ ABCD") and nonstandard/hashed callsigns —
it returns an empty array, and both `QsoAnswererService.ApplyApConstraints()` and
`QsoCallerService`'s equivalent respond to that empty array by disabling H6 AP-assisted LDPC
decode for the *entire* QSO. This silently removes a genuine decode-quality improvement (AP
constraints materially help weak-signal decode) for exactly the population `f-001` exists to
help: any operator working a station with a nonstandard or compound callsign gets no AP
assistance at all, standard party or not.

## What Changes

- Extend the callsign packer to encode two cases it currently rejects: special tokens (`CQ`,
  `DE`, `QRZ`, numeric-suffix "CQ nnn", directed-group "CQ ABCD") into their correct N28
  sub-range, and nonstandard/compound callsigns into the 22-bit-hash N28 sub-range via the
  `ihashcall` algorithm (`f-001`'s design.md documents the formula; `ft8_lib`/WSJT-X's `pack77`
  reference documents the special-token integer assignments this change needs to source during
  design).
- Wire the extended packer into `QsoAnswererService` and `QsoCallerService`'s AP-constraint
  arming so H6 AP-assisted decode stays active for a QSO where either party's callsign is
  nonstandard, instead of unconditionally disabling AP for the whole exchange.
- No change to the existing standard-callsign packing path or its output for calls that already
  pack successfully today (**not** a breaking change to that behavior).
- No native shim change expected: the AP constraint sink (`Ft8ApConstraints`,
  `Ft8Decoder.SetApConstraints`, native `ft8_set_ap_bits`) already accepts an arbitrary packed
  28-bit value agnostic to which N28 sub-range it represents — this is scoped as a
  managed-layer-only change unless design investigation finds otherwise.

## Capabilities

### New Capabilities
- `ap-assist-callsign-packing`: encodes special CQ/DE/QRZ tokens and nonstandard/hashed
  callsigns (via `ihashcall`) into the 28-bit N28 representation consumed by H6 AP-assisted
  decode, extending the packer beyond standard 6-character basecalls.

### Modified Capabilities
- `qso-caller`: "Arm H6 AP decode constraints for `(callsign, partner)`" (TxReport requirement)
  currently degrades to AP-disabled whenever either callsign is nonstandard; this changes so AP
  constraints are armed successfully in that case too.
- `qso-answerer`: the equivalent AP-constraint-arming behavior (mirrors `qso-caller`'s) gets the
  same fix, so AP decode-assist is not silently disabled for a nonstandard-callsign QSO.

## Impact

- **Managed**: `src/OpenWSFZ.Ft8/Ft8CallsignPacker.cs` (packer extension — new method(s) or
  `Pack28` behavior change), `src/OpenWSFZ.Daemon/QsoAnswererService.cs`'s
  `ApplyApConstraints()` (~line 1161), `src/OpenWSFZ.Daemon/QsoCallerService.cs`'s equivalent
  (~line 873).
- **Native**: none expected (see What Changes) — to be confirmed during design.
- **Testing**: packer unit tests against known `ihashcall` test vectors (an independent
  reference implementation already exists in `qa/rr-study/synth/packing.py`, usable for
  cross-checking without treating it as ground truth); AP-assisted decode integration coverage
  for a nonstandard-callsign QSO exchange, extending on `f-001`'s cross-cycle resolution tests
  and the existing H6 AP decode test coverage.
- **R&R study**: no expected regression to the existing S1–S8 synthetic corpus (standard
  callsigns only); any dedicated verification of AP-assist effectiveness for nonstandard
  callsigns is a candidate follow-on to `rr-study-hashed-callsign-effectiveness`'s S9/S11
  scenarios, not required for this change to ship.
