"""Tests for coh-gain/cg_encid.py and cg_encid_rows.py (ENC-ID). Y3 = this file: the ported type-4 unpacker and 12-bit hash, checked on synthetic messages.

The pinned DLL's encoder NEVER emits type 4 (it packs any compound/non-standard call as a standard message with a 22-bit hash, n28 = NTOKENS + n22), so Y3's "DLL-packed type-4 texts" cannot exist. What the DLL
CAN pin is the HASH: for DLL-packed compound-call texts the call field's n22 comes from the DLL's own compiled save_callsign, and `hash12` must equal n22 >> 10 on 100 % of them. The LAYOUT is checked against an
independent transcription of message.c's byte-shift packer (ftx_message_encode_nonstd), synthetic calls Q-prefixed (NFR-021).
"""
import random
import sys
from pathlib import Path

import pytest

CGD = Path(__file__).resolve().parent.parent / "rr-study" / "coh-gain"
sys.path.insert(0, str(CGD))
import cg_common as CG  # noqa: E402
import cg_encid as EN  # noqa: E402
import cg_encid_rows as ER  # noqa: E402
import pack77_fields as PF  # noqa: E402

DLL = Path(__file__).resolve().parents[2] / "artefacts" / "rr_2026-10-06_coh_gain" / "bin" / "libft8_20260058.dll"
needs_dll = pytest.mark.skipif(not DLL.exists(), reason="pinned DLL copy not present")
NTOKENS, MAX22 = 2063592, 4194304


def pack58(call):
    v = 0
    for ch in call.ljust(11):
        v = v * 38 + EN.CHARS.index(ch)
    return v


def pack_type4_c(n12, n58, iflip, nrpt, icq):
    """message.c:257-263 transcribed byte by byte, then expanded MSB first to 80 bits (the last 3 payload bits are i3 = 4)."""
    p = [0] * 10
    p[0] = (n12 >> 4) & 0xFF
    p[1] = ((n12 << 4) & 0xFF) | ((n58 >> 54) & 0xFF)
    for k, sh in zip(range(2, 8), (46, 38, 30, 22, 14, 6)):
        p[k] = (n58 >> sh) & 0xFF
    p[8] = ((n58 << 2) & 0xFF) | (iflip << 1) | (nrpt >> 1)
    p[9] = ((nrpt << 7) & 0xFF) | (icq << 6) | (4 << 3)
    bits = [(byte >> (7 - k)) & 1 for byte in p for k in range(8)]
    return bits[:77]


def synth_calls(n=120, seed=3):
    r = random.Random(seed)
    out = []
    for _ in range(n):
        base = "Q" + str(r.randint(0, 9)) + "".join(r.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(r.randint(1, 3)))
        out.append(r.choice([f"{r.choice(['PJ4', 'KH6', 'VE3', '3D2'])}/{base}", f"{base}/{r.choice(['QRP', 'MM', 'AM'])}", base + "ABCD"][:2]))
    return [c for c in out if 3 <= len(c) <= 11]


@needs_dll
def test_hash12_equals_the_dlls_own_n22_for_100_percent_of_packed_compound_calls():
    dec = CG.load_decoder(str(DLL))
    checked = 0
    for call in synth_calls():
        b = dec.true_codeword(f"CQ {call}")
        p = b[:77]
        assert PF.i3_of(p) == 1
        n28 = EN._bits_to_int(p[0:28]) if False else EN._bits_to_int(p[0:28])
        # CQ first word is token 2 for the first call; the compound call is the SECOND call (bits 29..57)
        n28b = EN._bits_to_int(p[29:57])
        assert NTOKENS <= n28b < NTOKENS + MAX22, call           # hashed (non-standard) call
        n22 = n28b - NTOKENS
        assert EN.hash12(call) == n22 >> 10, call
        checked += 1
    assert checked >= 100


def test_unpack_type4_round_trips_the_c_byte_layout_over_random_fields():
    r = random.Random(11)
    for _ in range(200):
        call = "".join(r.choice(EN.CHARS[1:]) for _ in range(r.randint(3, 11))).strip()
        n12, iflip, nrpt, icq = r.randrange(4096), r.randint(0, 1), r.randrange(4), r.randint(0, 1)
        p = pack_type4_c(n12, pack58(call), iflip, nrpt, icq)
        assert PF.i3_of(p) == 4
        assert EN.unpack_type4(p) == (n12, pack58(call), iflip, nrpt, icq, call)


def test_enc_match_true_for_a_real_type4_message_false_for_others_and_for_non_type4():
    call, other = "PJ4/Q1ABC", "Q2DEF"
    x = pack_type4_c(EN.hash12(other), pack58(call), 0, 2, 0)
    assert EN.enc_flags(x, f"{other} {call} RR73")["enc_match"] == 1
    assert EN.enc_flags(x, f"{other} PJ4/Q1ABD RR73")["call_eq"] == 0
    f = EN.enc_flags(x, "Q3GHI PJ4/Q1ABC RR73")                   # right call, wrong other call: hash fails, no placeholder
    assert f["call_eq"] == 1 and f["hash_eq"] == 0 and f["enc_match"] == 0
    g = EN.enc_flags(x, "<...> PJ4/Q1ABC RR73")                    # unresolved hash: the placeholder rule admits it
    assert g["call_eq"] == 1 and g["t_has_placeholder"] == 1 and g["enc_match"] == 1
    cq = pack_type4_c(0, pack58(call), 0, 0, 1)
    assert EN.enc_flags(cq, f"CQ {call}")["enc_match"] == 1 and EN.enc_flags(cq, f"{other} {call}")["enc_match"] == 0
    assert EN.enc_flags(pack_type4_c(0, 0, 0, 0, 0)[:74] + [0, 0, 1], f"CQ {call}")["enc_match"] == 0      # i3 = 1 payload: all flags 0


def test_call_tokens_rule_and_the_two_mutants_move_rows():
    assert EN.call_tokens("CQ DX PJ4/Q1ABC") == ["PJ4/Q1ABC"] and EN.call_tokens("CQ POTA Q1ABC FN42") == ["Q1ABC"]
    assert EN.call_tokens("<Q1ABC> Q2DEF/P R-10") == ["Q1ABC", "Q2DEF/P"] and EN.call_tokens("Q1ABC Q2DEF RR73") == ["Q1ABC", "Q2DEF"]
    assert EN.call_tokens("<...> Q2DEF 73") == ["Q2DEF"] and EN.has_placeholder("<...> Q2DEF 73")
    assert EN.call_tokens("Q1ABC Q2DEF RR73", "m1") == ["Q1ABC", "Q2DEF", "RR73"]            # mutant 1 changes the token set
    assert EN.call_tokens("Q1ABC Q2DEF/P RRR", "m2") == ["Q1ABC", "Q2DEF"]                      # mutant 2 drops /P
    x = pack_type4_c(EN.hash12("Q1ABC"), pack58("Q2DEF/P"), 0, 0, 0)
    assert EN.enc_flags(x, "Q1ABC Q2DEF/P RRR")["enc_match"] == 1 and EN.enc_flags(x, "Q1ABC Q2DEF/P RRR", "m2")["enc_match"] == 0   # m2 moves a row
    y = pack_type4_c(EN.hash12("RR73"), pack58("Q2DEF"), 0, 0, 0)
    assert EN.enc_flags(y, "Q1ABC Q2DEF RR73")["enc_match"] == 0 and EN.enc_flags(y, "Q1ABC Q2DEF RR73", "m1")["enc_match"] == 1      # m1 moves a row


def test_derangement_is_seeded_fixed_and_respects_the_30_minute_spacing():
    secs = [i * 400.0 for i in range(795)]
    p = EN.derange(secs)
    assert p == EN.derange(secs) and sorted(p) == list(range(795))
    assert all(p[i] != i and abs(secs[i] - secs[p[i]]) >= EN.MIN_APART_S for i in range(795))


def test_reading_rows_and_validity_gate():
    assert ER.reading(0.85, 0.95) == "ENC-CONFIRMED" and ER.reading(0.10, 0.49) == "ENC-REJECTED" and ER.reading(0.60, 0.90) == "ENC-PARTIAL"
    rows = [{"sample": 1, "cycle_index": i % 8, "widx": i, "kind": "X", "w1_ok": 1, "enc_match": 1, "call_eq": 1, "hash_eq": 1, "icq": 0, "nrpt": 0, "t_has_placeholder": 0, "m1": 1, "m2": 1,
             "y4_match": 0} for i in range(795)]
    rows += [{"sample": 1, "cycle_index": i % 8, "widx": 2000 + i, "kind": "OSD", "w1_ok": 1, "enc_match": 0, "call_eq": 0, "hash_eq": 0, "icq": 0, "nrpt": 0, "t_has_placeholder": 0, "m1": 0,
              "m2": 0, "y4_match": ""} for i in range(19)]
    a = ER.analyse(rows, cycles={1: list(range(8))})
    assert a["valid"] and a["reading"] == "ENC-CONFIRMED" and a["P"] == 1.0
    bad = [dict(r) for r in rows]
    bad[795]["enc_match"] = 1                                       # one OSD control row matches: Y2 fails, no reading
    assert ER.analyse(bad, cycles={1: list(range(8))})["reading"] == "NO READING"
    bad2 = [dict(r) for r in rows]
    for r in bad2[:20]:
        r["y4_match"] = 1                                           # 20 of 795 = 2.5 % shuffled matches: Y4 fails
    assert not ER.analyse(bad2, cycles={1: list(range(8))})["validity"]["Y4"]["pass"]
