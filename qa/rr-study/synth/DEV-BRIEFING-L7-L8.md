# Developer Briefing — Synthesiser L7 (message packing) & L8 (LDPC parity)

**Author:** QA · **For:** Developer · **Date:** 2026-06-05
**Parent docs:** [`BUILD-PLAN.md`](./BUILD-PLAN.md) · [`../STUDY-SPEC.md`](../STUDY-SPEC.md) (§5)
**Status:** Ready for implementation. CI on the L1–L6 spine is green (PR #27).

---

## 0. Roles — read this first

- **You (Developer)** implement L7 and L8 against the contracts below and make the listed
  acceptance tests pass.
- **I (QA)** own the acceptance criteria, the scenario corpus, and execution of the §5
  WSJT-X self-validation gate. I will review your implementation against this briefing and the
  STUDY-SPEC; I will not merge until the gates in §6 are green.
- **The boundary:** this document tells you *what* must be true and *which public sources* to
  transcribe from. It deliberately does **not** hand you the algorithm or the tables — deriving
  those from the public protocol description is the implementation work, and is what keeps the
  synthesiser clean-room.

---

## 1. Clean-room mandate (non-negotiable — STUDY-SPEC §5)

The synthesiser exists to be an **independent** oracle. If it shared a bug with the decoder under
test, that bug could mask a real defect. Therefore:

- **DO** derive packing and LDPC from the **published FT8 protocol description** (see §7).
  The bit-field layouts, the callsign/grid packing rules, and the LDPC generator/parity-check
  matrices are *published protocol facts* — transcribing them from the specification is expected
  and correct.
- **DO NOT** copy, paste, port, or line-by-line translate code from `ft8_lib`, WSJT-X, or any other
  decoder/encoder implementation. Transcribe the *published constants and field definitions*, then
  write your own code around them.
- If in doubt about whether a thing is "a published constant" vs "borrowed implementation," ask QA
  before proceeding.

---

## 2. Contracts you must preserve (already stubbed)

These signatures exist in `synth/packing.py` and `synth/ldpc.py` and are consumed by
`synth/encoder.py` and `synth/symbols.py`. **Do not change the signatures**; fill in the bodies.

```python
# synth/packing.py
def pack_message(text: str) -> list[int]:
    """Standard FT8 message text -> 77 bits, MSB first."""

# synth/ldpc.py
def encode_ldpc(message_plus_crc: list[int]) -> list[int]:
    """91 info bits (77 message + 14 CRC) -> 174-bit systematic codeword."""

def parity_check(codeword: list[int]) -> bool:
    """True iff H . c = 0 over GF(2)."""
```

**Pipeline already wired** (`encoder.message_to_tones`): `pack_message` → `crc.append_crc`
(done, L2) → `encode_ldpc` → `symbols.assemble_symbols` (done, L3). You only supply the two
missing bodies. Everything downstream (Gray coding, Costas, GFSK, channel, WAV) is finished and
tested — do not touch it.

---

## 3. L7 — message packing (`packing.py`)

### 3.1 Bit ordering convention (whole package)

All bit lists are **MSB-first**, value `0`/`1` per element. `pack_message` returns exactly **77**
bits. The 14-bit CRC (L2) is appended after, then the 83 LDPC parity bits (L8), giving the 174-bit
codeword in **transmit order** that `symbols.py` chunks 3-bits-per-symbol. Any deviation from this
ordering will fail the §5 gate even if each field is individually correct — order is load-bearing.

### 3.2 Scope: Type-1 standard messages only

The study corpus (see §5, scenario files I will provide under `scenarios/`) uses only **standard
messages** — message type `i3 = 1`. You must support these forms:

- `CQ <call> <grid>`           (e.g. `CQ Q1ABC FN42`)
- `<call1> <call2> <grid>`     (e.g. `Q1ABC Q9XYZ EN37`)
- `<call1> <call2> <report>`   where report ∈ signal report or `RRR` / `RR73` / `73`

Out of scope for the first study (raise with QA if a scenario needs them): non-standard callsigns
(hashed/`<...>`), compound/`/P`/`/R` suffixes beyond the single rover bit, free-text (i3=0),
telemetry, and the EU-VHF (i3=2) and contest types. Document any input your packer rejects.

### 3.3 The 77-bit Standard-message layout (from the published spec)

Transcribe the exact field widths and packing rules from the FT8 specification. The standard
message decomposes as:

| Field | Width | Meaning |
|---|---|---|
| c28 | 28 | callsign 1, packed (incl. special tokens `CQ`/`DE`/`QRZ`) |
| r1  | 1  | rover flag for call 1 |
| c28 | 28 | callsign 2, packed |
| r1  | 1  | rover flag for call 2 |
| R1  | 1  | signal-report acknowledgement bit |
| g15 | 15 | 4-char Maidenhead grid, **or** report/`RRR`/`RR73`/`73` via the reserved range |
| i3  | 3  | message type = `1` |

(28+1+28+1+1+15+3 = 77.) The c28 callsign packing (alphabets, offsets for special tokens) and the
g15 grid/report encoding are defined in the spec — implement them from there.

### 3.4 Acceptance for L7

Add `../tests/test_packing.py`. It must demonstrate:

1. `pack_message` returns a list of exactly 77 elements, all ∈ {0,1}.
2. **Bit-exact** against at least one **independently-sourced worked example** (a known
   message → known 77-bit vector taken from the published protocol material, *not* generated by
   `ft8_lib`). Coordinate with QA on the chosen vector so we agree the reference is independent.
3. Determinism: same input → same output across calls.
4. Each supported form in §3.2 packs without error; unsupported forms raise a clear exception.
5. (Recommended, not required) an `unpack_message` inverse to enable round-trip tests
   `unpack(pack(x)) == x` — a strong self-consistency check that costs little.

> The *ultimate* proof of L7 is the §6 gate (WSJT-X decodes the assembled signal). Unit tests
> catch regressions; the gate proves correctness.

---

## 4. L8 — LDPC(174,91) parity (`ldpc.py`)

### 4.1 What to build

FT8 protects the 91-bit (message+CRC) word with a **systematic** LDPC(174,91) code: the 174-bit
codeword is the **91 information bits unchanged, followed by 83 parity bits**. You must:

- Transcribe the published **generator** (the 83×91 parity-generation table) and the **parity-check
  matrix H** (83×174) from the FT8 specification. These matrices are part of the open protocol
  definition.
- `encode_ldpc(info91)` → compute the 83 parity bits and return `info91 + parity83` (174 bits),
  preserving the MSB-first, systematic, transmit-order convention from §3.1.
- `parity_check(codeword174)` → return `True` iff every parity-check row sums (XOR) to 0 over GF(2).

### 4.2 Acceptance for L8

Add `../tests/test_ldpc.py`. It must demonstrate:

1. `encode_ldpc` returns exactly 174 bits; the first 91 equal the input (systematic).
2. **Self-consistency:** `parity_check(encode_ldpc(x)) is True` for many random 91-bit `x`
   (e.g. 1000 seeded random words) — i.e. the generator and H are mutually consistent.
3. **Error detection:** flipping any single bit of a valid codeword makes `parity_check` return
   `False`.
4. `parity_check` and `encode_ldpc` reject wrong-length inputs (the stubs already raise `ValueError`
   on length — keep that).

> Item 2 is the decisive internal check: if your transcribed generator and H disagree, it fails
> here long before WSJT-X is involved. Make this test loud.

---

## 5. Scenario corpus (QA-owned — provided to you)

I will commit `qa/rr-study/scenarios/` with the exact message strings each scenario uses
(STUDY-SPEC §6). Your packer must handle every message in that corpus. If the corpus needs a form
outside §3.2, that is a scope change — flag it to me; do not silently extend the packer.

---

## 6. Definition of done & hand-back to QA

You are done with L7+L8 when **all** of the following hold:

1. `test_packing.py` and `test_ldpc.py` are green, including the bit-exact and self-consistency
   checks above.
2. The full suite passes: `cd qa/rr-study && .venv/Scripts/python -m pytest tests/ -q`.
3. `encoder.encode_message("CQ Q1ABC FN42", base_freq_hz=1500)` returns a 79-tone vector whose
   Costas arrays sit correctly at symbol indices 0/36/72 (add this as an integration assertion).
4. You hand back to QA for the **§5 gate**, which I will run: render every corpus message clean at
   +10 dB and confirm **WSJT-X decodes every one**. *This step requires WSJT-X and is mine to
   execute* — you are not expected to run it, but your code must be gate-ready.

Update `BUILD-PLAN.md` L7/L8/L9 status to ✅ only after step 4 passes; until the gate is green,
mark them "implemented, gate pending."

---

## 7. Authoritative references (public)

- Franke, Somerville & Taylor, **"The FT4 and FT8 Communication Protocols,"** QEX, 2020 —
  the canonical public description of 77-bit message types, callsign/grid packing, CRC-14, the
  LDPC(174,91) code, Gray coding, Costas arrays, and GFSK.
- The WSJT-X documentation set accompanying that paper (protocol tables / appendices).

Transcribe field layouts and matrices from these. Cite the source section in your code comments so
QA can verify provenance during review.

---

## 8. Common pitfalls I will be checking for

- **Bit order / endianness** — MSB-first throughout; codeword in transmit order (msg | CRC | parity).
- **CRC scope** — the CRC (L2, done) is over the 77 message bits padded to 82; do not re-pad or
  re-order it inside L8.
- **Systematic ordering** — parity *appended* after the 91 info bits, not interleaved.
- **Gray coding belongs to L3, not you** — `symbols.py` already Gray-maps. Do not Gray-code in L8,
  or you will double-apply it and fail the gate.
- **Clean-room provenance** — comments must cite the published spec, not `ft8_lib`.
