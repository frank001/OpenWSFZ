#!/usr/bin/env python3
"""Issue #262 (PSK Reporter upload), spec section 4 P0: the T1 golden-bytes fixture, hand-built by QA from https://pskreporter.info/pskdev.html.

INDEPENDENT of any product code (there is none yet): every byte below comes from the page's byte tables ("Cookie Cutter Information"), not from an encoder under test.
The page was fetched raw with curl on 2026-10-25 11:34:26Z (HTML SHA-256 prefix fba4c8f173952488), not through a summarising tool.

SELF-CHECK FIRST: the builder must reproduce the page's own two worked datagrams byte for byte (the complete datagram with sequence number 1, and the later one with sequence number 4).
The page's examples use real third-party callsigns; NFR-021 keeps those out of version control, so the examples are encoded here with Q-prefix calls of the SAME LENGTH
(the page's first example call -> Q1DQ, its second -> Q1MBXZ; locator and software string unchanged). Only those ASCII bytes differ from the page's hex; every other byte (headers, descriptors, lengths, padding, order) is the page's.
`--page <pskdev.txt> --page-calls <first>,<second>` additionally checks the builder against the page's hex lines themselves, after the same substitution (run locally; the page text and the page's two real calls are
supplied on the command line and are not committed).

Findings the page forces (see the review record): set id 3 for the receiver descriptor (an options template: field count, then scope field count 1) and set id 2 for the sender descriptor; the
field order inside a sender record follows the chosen descriptor (callsign, frequency, [sNR, iMD], mode, informationSource, [locator], flowStartSeconds); the page's two worked datagrams disagree on the
mode bytes ('PSK' 4B in the complete datagram, 4C in the fragment and the seq-4 example), a typo on the page, immaterial here.
"""
import argparse
import calendar
import re
import struct
import sys

ENT = 0x768F                      # enterprise number 30351 (page: 00 00 76 8F)
RECV_TID = 0x9992
SEND_TID_FOR = {5: 0x9993, 6: 0x9993, 7: 0x9994, 8: 0x9993}   # template ids are arbitrary in 256..65535 (page); two sender descriptors in ONE datagram need two ids (spec section 10: 8-field with a grid, 7-field without)


def u16(v): return struct.pack(">H", v)
def u32(v): return struct.pack(">I", v)
def vs(s): b = s.encode("utf-8"); assert len(b) <= 254; return bytes([len(b)]) + b          # variable-length string: 1-byte length (page: <= 254), then UTF-8
def pad4(b): return b + b"\x00" * (-len(b) % 4)


def field(fid, length, enterprise=True):                                                      # one field specifier: [0x8000|id][length][enterprise 30351] ; IANA fields have no enterprise part
    return u16((0x8000 | fid) if enterprise else fid) + u16(length) + (struct.pack(">I", ENT) if enterprise else b"")


def recv_descriptor(antenna: bool):                                                           # page: set id 3, 00 24 (3 fields) or 00 2C (4 fields), 99 92, field count, scope field count 1
    fields = [field(2, 0xFFFF), field(4, 0xFFFF), field(8, 0xFFFF)] + ([field(9, 0xFFFF)] if antenna else [])
    body = u16(RECV_TID) + u16(len(fields)) + u16(1) + b"".join(fields)
    return _set(3, body)


def _set(set_id, body):
    padded = pad4(body)
    return u16(set_id) + u16(4 + len(padded)) + padded


SEND_FIELDS = {"callsign": (1, 0xFFFF, True), "frequency": (5, 4, True), "snr": (6, 1, True), "imd": (7, 1, True), "mode": (10, 0xFFFF, True),
               "source": (11, 1, True), "locator": (3, 0xFFFF, True), "flow": (150, 4, False)}
VARIANTS = {                                                                                  # the page's four sender descriptors (field counts 5, 6, 7, 8), in the page's order
    5: ["callsign", "frequency", "mode", "source", "flow"],
    6: ["callsign", "frequency", "mode", "source", "locator", "flow"],
    7: ["callsign", "frequency", "snr", "imd", "mode", "source", "flow"],
    8: ["callsign", "frequency", "snr", "imd", "mode", "source", "locator", "flow"],
}


def send_descriptor(variant):
    names = VARIANTS[variant]
    body = u16(SEND_TID_FOR[variant]) + u16(len(names)) + b"".join(field(*SEND_FIELDS[n][:2], enterprise=SEND_FIELDS[n][2]) for n in names)
    return _set(2, body)


def recv_record(call, loc, sw, ant=None):
    body = vs(call) + vs(loc) + vs(sw) + (vs(ant) if ant is not None else b"")
    padded = pad4(body)
    return u16(RECV_TID) + u16(4 + len(padded)) + padded


def send_block(variant, records):
    out = b""
    for r in records:
        for n in VARIANTS[variant]:
            v = r[n]
            out += vs(v) if n in ("callsign", "mode", "locator") else (struct.pack(">b", max(-128, min(127, v))) if n in ("snr", "imd") else (bytes([v]) if n == "source" else u32(v)))
    padded = pad4(out)
    return u16(SEND_TID_FOR[variant]) + u16(4 + len(padded)) + padded


def datagram(t, seq, sid, parts):
    body = b"".join(parts)
    return u16(0x000A) + u16(16 + len(body)) + u32(t) + u32(seq) + u32(sid) + body


def rec(call, freq, mode, flow, loc=None, snr=None, imd=None):
    return {"callsign": call, "frequency": freq, "mode": mode, "source": 1, "flow": flow, "locator": loc if loc is not None else "", "snr": snr, "imd": imd}


def hexs(b): return " ".join(f"{x:02X}" for x in b)


def selfcheck(page_text=None, page_calls=None):
    """The page's complete datagram (seq 1, 'PSK') and the later one (seq 4, fragments with 'PSL'), calls replaced by same-length Q-calls."""
    t, sid = 1200960114, 0
    recv = recv_record("Q1DQ", "FN42hn", "Homebrew v5.6")
    r1 = rec("Q1DQ", 14070567, "PSK", 1200960084)
    r2 = rec("Q1MBXZ", 14070987, "PSK", 1200960104)
    full = datagram(t, 1, sid, [recv_descriptor(False), send_descriptor(5), recv, send_block(5, [r1, r2])])
    exp_full = bytes.fromhex(
        "000A00AC47953272000000010000000000030024999200030001" "8002FFFF0000768F"
        + "8004FFFF0000768F" + "8008FFFF0000768F" + "0000"
        + "0002002C9993" "0005" + "8001FFFF0000768F" + "800500040000768F" + "800AFFFF0000768F" + "800B00010000768F" + "00960004"
        + "99920020" + "04" + b"Q1DQ".hex() + "06" + b"FN42hn".hex() + "0D" + b"Homebrew v5.6".hex() + "0000"
        + "9993002C" + "04" + b"Q1DQ".hex() + "00D6B327" + "03" + b"PSK".hex() + "01" + "47953254"
        + "06" + b"Q1MBXZ".hex() + "00D6B4CB" + "03" + b"PSK".hex() + "01" + "47953268" + "0000")
    assert full == exp_full, f"complete datagram differs:\n got {hexs(full)}\n exp {hexs(exp_full)}"
    later_r1 = rec("Q1DQ", 14070567, "PSL", 1200960084)
    later_r2 = rec("Q1MBXZ", 14070987, "PSL", 1200960104)
    later = datagram(t, 4, sid, [recv, send_block(5, [later_r1, later_r2])])
    exp_later = bytes.fromhex("000A005C47953272000000040000000099920020" "04" + b"Q1DQ".hex() + "06" + b"FN42hn".hex() + "0D" + b"Homebrew v5.6".hex() + "0000"
                              + "9993002C" "04" + b"Q1DQ".hex() + "00D6B327" "03" + b"PSL".hex() + "01" "47953254" + "06" + b"Q1MBXZ".hex() + "00D6B4CB" "03" + b"PSL".hex() + "01" "47953268" "0000")
    assert later == exp_later, f"later datagram differs:\n got {hexs(later)}\n exp {hexs(exp_later)}"
    # the receiver descriptor with the antenna field and the other three sender descriptors: lengths must be the page's 0x2C, 0x34, 0x3C, 0x44 and the header's 0xAC
    assert recv_descriptor(True)[2:4] == b"\x00\x2c" and recv_descriptor(False)[2:4] == b"\x00\x24"
    assert [send_descriptor(v)[2:4] for v in (5, 6, 7, 8)] == [b"\x00\x2c", b"\x00\x34", b"\x00\x3c", b"\x00\x44"]
    assert len(full) == 0xAC and len(later) == 0x5C
    if page_text is not None:
        # the page's own hex lines, with the same-length call substitution, must equal the builder's output
        def norm(s): return re.sub(r"\s+", "", s).upper()
        assert page_calls and len(page_calls) == 2 and len(page_calls[0]) == 4 and len(page_calls[1]) == 6, "--page needs --page-calls <4-char call>,<6-char call>"
        sub = {page_calls[0].encode().hex().upper(): b"Q1DQ".hex().upper(), page_calls[1].encode().hex().upper(): b"Q1MBXZ".hex().upper()}
        page_hex = norm(page_text)
        for src, dst in sub.items():
            page_hex = page_hex.replace(src, dst)
        for name, blob in (("complete datagram", full), ("later datagram", later)):
            # the page prints the full datagram in sections; check every section appears in order inside the page text
            h = blob.hex().upper()
            pos = 0
            for i in range(0, len(h), 8):
                chunk = h[i:i + 8]
                j = page_hex.find(chunk, pos)
                assert j >= 0, f"{name}: bytes {chunk} (offset {i // 2}) not found in order in the page"
                pos = j + len(chunk)
    return full, later


def t1():
    """T1 (spec section 10, Captain's D4 = iMD sent as 0): one receiver record and two sender records, templates due. Q-prefix calls only; times are computed from the calendar, not from a clock.
    A message WITH a grid (Q1ABC, JO22) goes in the 8-field block (template 0x9993), one WITHOUT (Q2DEF) in the 7-field block (template 0x9994); the 8-field block comes first.
    Session id 0xA1B2C3D4, sequence 7, export time 2026-10-25T11:35:00Z, cycle start (flowStartSeconds) 2026-10-25T11:34:45Z, dial 14.074 MHz + audio offsets 1,500 and 987 Hz; SNR -12 and -5, iMD 0."""
    t_export = calendar.timegm((2026, 10, 25, 11, 35, 0))
    t_cycle = calendar.timegm((2026, 10, 25, 11, 34, 45))
    sid, seq, dial = 0xA1B2C3D4, 7, 14_074_000
    recv = recv_record("Q1OFZ", "JO33", "OpenWSFZ 0.63")
    a = rec("Q1ABC", dial + 1500, "FT8", t_cycle, loc="JO22", snr=-12, imd=0)
    b = rec("Q2DEF", dial + 987, "FT8", t_cycle, loc=None, snr=-5, imd=0)
    descs = [recv_descriptor(False), send_descriptor(8), send_descriptor(7)]
    main = datagram(t_export, seq, sid, descs + [recv, send_block(8, [a]), send_block(7, [b])])
    ant = datagram(t_export, seq, sid, [recv_descriptor(True), send_descriptor(8), send_descriptor(7), recv_record("Q1OFZ", "JO33", "OpenWSFZ 0.63", "Q1 test antenna"), send_block(8, [a]), send_block(7, [b])])
    later = datagram(t_export + 300, seq + 2, sid, [recv, send_block(8, [rec("Q1ABC", dial + 1510, "FT8", t_cycle + 300, loc="JO22", snr=-127 - 5, imd=0)])])   # templates NOT due; SNR clamped to -128 (T13)
    # Architect Amendment 2 (F-d): the receiver locator is the normalised 6-character locator (first 4 upper case, last 2 lower case) when pskReporter.locator
    # is valid and matches tx.grid: the same datagram as the main fixture with receiver locator "JO33ed" instead of "JO33".
    recv6 = recv_record("Q1OFZ", "JO33ed", "OpenWSFZ 0.63")
    loc6 = datagram(t_export, seq, sid, descs + [recv6, send_block(8, [a]), send_block(7, [b])])
    return {"t1_8field_and_7field": main, "t1_with_antenna": ant, "t1_templates_not_due_snr_clamped": later, "t1_receiver_locator6": loc6}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", help="pskdev.txt (the page converted to text), to check the builder against the page's own hex")
    ap.add_argument("--page-calls", help="the page's two example callsigns (4 and 6 characters), comma separated, supplied at run time so they are not committed")
    ap.add_argument("--out", help="write the fixtures as annotated hex files into this directory")
    a = ap.parse_args()
    page = open(a.page, encoding="utf-8").read() if a.page else None
    selfcheck(page, a.page_calls.split(",") if a.page_calls else None)
    print("self-check OK: the builder reproduces the page's complete datagram (172 bytes, seq 1) and the later one (92 bytes, seq 4)" + (" and every byte of both appears in order in the page text" if page else ""))
    fx = t1()
    for name, blob in fx.items():
        print(f"\n{name}: {len(blob)} bytes\n{hexs(blob)}")
        if a.out:
            open(f"{a.out}/{name}.hex", "w", newline="\n").write(hexs(blob) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
