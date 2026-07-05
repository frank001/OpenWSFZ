## 1. Reference values — confirm before coding

- [x] 1.1 Confirm `NTOKENS = 2,063,592`, `MAX22 = 4,194,304`, and the special-token assignments
      (`DE=0`, `QRZ=1`, `CQ=2`, `"CQ nnn"` = `3 + nnn` for `nnn` in `000`–`999`) against the
      vendored `ft8_lib` source (or WSJT-X's `packjt77.f90`) at implementation time, rather than
      assuming `qa/rr-study/synth/packing.py`'s citation (QEX 2020 §III-A Table I) is still
      current — mirrors `f-001-hashed-callsign-resolution` design D4's "confirm the actual value
      at implementation time" precedent.
- [x] 1.2 Confirm the `ihashcall` formula (`n8 = 38*n8 + char_index` over up to 11 characters,
      charset `" 0-9A-Z/"`; `hash = (47055833459 * n8) >> (64-m)`, `m=22` for the `c28`
      sub-range) matches `f-001-hashed-callsign-resolution/design.md`'s Context section and the
      native shim's own implementation — this change needs an independent C# port, not a shared
      implementation (design D2), so verify against the *published* formula, not just against
      one existing implementation.

## 2. C# `ihashcall` port

- [x] 2.1 Implement the `ihashcall` formula in C# (new private helper in
      `Ft8CallsignPacker.cs`, or a small dedicated internal class if that reads more clearly
      alongside the existing packing helpers).
- [x] 2.2 Add unit tests against the project's known-vector table for `ihashcall` (the same
      vectors already validated for `f-001`'s native shim tests and/or
      `qa/rr-study/synth/packing.py`'s own test coverage) — assert exact hash equality, not just
      "packs without throwing."
- [x] 2.3 Cross-check a handful of values against `qa/rr-study/synth/packing.py`'s `ihashcall`
      directly (e.g. via a small script run once during development, not a standing CI
      dependency on Python) as a belt-and-braces sanity check — not a substitute for 2.2's
      independently-sourced vector test, since a bug shared between this port and `packing.py`
      would not be caught by cross-checking the two against each other.

## 3. Extend `Ft8CallsignPacker`

- [x] 3.1 Add special-token packing (`"CQ"`, `"DE"`, `"QRZ"`, `"CQ nnn"` 3-digit numeral) to
      `Pack28`, producing the correct `n28` value from task 1.1's confirmed constants, packed
      into the same 4-byte MSB-first layout the existing standard-basecall branch already uses.
- [x] 3.2 Add nonstandard/compound-callsign packing to `Pack28`: for input that does not match
      either standard-basecall normalisation pattern and is 3–11 characters (after `/R`/`/P`
      suffix handling, matching `packing.py`'s documented `ipa`/rover-flag convention — see
      design Non-Goals), compute `NTOKENS + ihashcall(callsign, bits: 22)` and pack it.
- [x] 3.3 Confirm `Pack28` still returns an empty array unchanged for: directed CQ with a
      non-numeric suffix (`"CQ DX"`, `"CQ POTA"`, etc. — deferred, see section 6), and malformed
      input (empty/whitespace/too-long strings) — add/extend unit tests asserting this
      explicitly so a future change can't accidentally regress the "empty array means disable
      AP" contract the two call sites depend on.
- [x] 3.4 Add a unit test confirming the existing standard-basecall path's output is byte-for-byte
      unchanged for at least one previously-passing callsign (regression guard for design D1's
      "no behavioural change to the existing path" goal).

## 4. Wire into the QSO services

- [x] 4.1 Confirm `QsoAnswererService.ApplyApConstraints()` (~line 1161) requires no code change
      beyond the packer extension itself — it already treats `Pack28`'s return value generically
      (empty means disable, non-empty means arm). If it does need a change, document why here.
- [x] 4.2 Confirm `QsoCallerService`'s equivalent (~line 873) likewise requires no code change
      beyond the packer extension.
- [x] 4.3 Add/extend integration tests for both services confirming AP constraints arm
      successfully (not disabled) when `mycall` or `hiscall` is a nonstandard/compound callsign,
      covering the new `qso-caller`/`qso-answerer` spec scenarios added by this change.

## 5. AP-assisted decode — end-to-end proof

- [x] 5.1 Add a test proving AP-assisted decode succeeds for a nonstandard-callsign QSO exchange
      through the real native decoder (not a fake/mocked interop), now that both the persistent
      hash table (`f-001`, shipped) and the extended packer (this change) are in place — this is
      the scenario `f-001` tasks.md's deferred 6.3 originally described. If a true end-to-end
      test proves impractical (mirroring `f-001`'s own 3.5 finding that its AV-path test harness
      couldn't simulate a genuine native fault), document why here and cover the gap via code
      review instead, same as `f-001` did.

## 6. Deferred — directed "CQ ABCD" form (not required for this change to ship)

- [ ] 6.1 (Follow-up, out of scope for this change per design D3/Non-Goals) Confirm the exact
      `c28` encoding for a directed CQ with a non-numeric 2–4 character suffix (`"CQ DX"`,
      `"CQ NA"`, `"CQ POTA"`, etc.) from the vendored `ft8_lib` source or WSJT-X's
      `packjt77.f90`, then add it as an additional `Pack28` branch once confirmed. Tracked here
      so it isn't lost, matching `f-001`'s own precedent for explicitly recording deferred
      stretch work rather than silently dropping it.

## 7. Regression check

- [x] 7.1 Run the existing `OpenWSFZ.Ft8.Tests` and `OpenWSFZ.Daemon.Tests` suites to confirm no
      regression in existing standard-callsign AP-decode-assist behaviour or QSO
      caller/answerer state-machine tests.
- [x] 7.2 Confirm this change requires no R&R study re-run: the existing S1–S8 synthetic corpus
      uses only standard-shaped Q-prefix callsigns (per `f-001` task 4.2's finding, still true —
      confirm it hasn't changed), so AP-assist for nonstandard callsigns is not exercised by
      that corpus either way. If a future dedicated effectiveness study is wanted (comparing
      decode rate with vs. without AP-assist for nonstandard callsigns under realistic SNR), that
      is a candidate follow-on to `rr-study-hashed-callsign-effectiveness`'s S9/S11 scenarios,
      not required for this change.
