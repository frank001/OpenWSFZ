#!/usr/bin/env python3
"""SUB-FEAS corpus + population construction (spec sec.2/3, Amendment 1).

HK-037/NFR-021: this module is one of the two places (with common.py) permitted to
touch message text, and only transiently, in-process, to (a) decide standard/
re-encodable-ness and twin-pairing via the pinned DLL's true_codeword/
ft8_encode_message, and (b) obtain the 79-tone sequence the fitter needs. Message
text and callsigns are NEVER returned from this module, logged, or written to disk
-- only numeric fields, booleans and tone arrays (a lossy FSK-index encoding, not
text) cross this module's boundary.

Amendment 1 (2026-09-27 ~19:20Z, arch/subtraction-feasibility b4b9748d): sec.3.2's
isolation predicate originally counted each strong signal's own WSJT-X twin (the
SAME transmission, independently logged) as "another decode" -- QA found this
collapsed |P| to 4. Ruling: de-twin first (same payload outcome, RR73-equivalent,
|df|<=10 Hz, paired once, nearest first), THEN apply the 60 Hz isolation check to
whatever's left. A WSJT-X-only neighbour still disqualifies (real RF energy in the
band). New ROW 0i (twin_share.py) checks the pairing itself is sane.
"""
from __future__ import annotations

import collections
import csv
import ctypes
import io
import os

import comparator as CMP  # gap-locate/comparator.py -- RR73-equivalence payload_match
import common
import ldpc_encode as LE

FT8_NN = 79
TWIN_DELTA_F_HZ = 10.0
ISOLATION_HZ = 60.0


def _load_all_txt(path: str) -> dict:
    """(ts, message) -> (snr, dt, freq_hz). Numeric fields only in the VALUE; the KEY
    still carries message text but never leaves this function's caller's caller (see
    build_population, which destructures immediately)."""
    out = {}
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.split()
            if len(f) < 8 or f[2] != "Rx" or f[3] != "FT8":
                continue
            if not f[1].startswith(common.DIAL_PREFIX):
                continue
            ts = f[0]
            try:
                snr, dt, freq_hz = int(f[4]), float(f[5]), int(f[6])
            except ValueError:
                continue
            out[(ts, " ".join(f[7:]))] = (snr, dt, freq_hz)
    return out


def cycle_order() -> list:
    """Chronological cycle timestamp list, from cycle-archive.csv (same source LIVE-
    GAP-MAP/GAP-LOCATE use). Filenames are 'YYMMDD_HHMMSS' -- lexicographic order is
    chronological order for this run (no month/year rollover inside one run)."""
    ts = []
    with io.open(common.CYCLE_ARCHIVE_CSV, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            fn = row["filename"]
            if fn.endswith(".wav") and not fn.endswith("_2.wav"):
                ts.append(fn[:-4])
    ts.sort()
    return ts


class Encoder:
    """Thin wrapper: ft8_encode_message (raw 79 tones) + true_codeword-equivalent
    77-bit payload extraction, used for (a) re-encodability, (b) the tone sequence
    the fitter needs, and (c) Amendment 1's twin-pairing payload comparison.
    Independent of the LDPC decode path (gl_dll_pin.LdpcDecodeLLRs) though it loads
    the SAME pinned DLL file."""

    FT8_NN = 79
    SYNC_RANGES = [(0, 7), (36, 43), (72, 79)]
    GRAY_MAP = [0, 1, 3, 2, 5, 6, 4, 7]

    def __init__(self, dll_path: str):
        self.dll = ctypes.CDLL(os.path.abspath(dll_path))
        self.dll.ft8_encode_message.restype = ctypes.c_int
        self.dll.ft8_encode_message.argtypes = [
            ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint8), ctypes.c_int]
        self._inv_gray = [0] * 8
        for i, v in enumerate(self.GRAY_MAP):
            self._inv_gray[v] = i

    def encode_tones(self, message: str):
        buf = (ctypes.c_uint8 * FT8_NN)()
        rc = self.dll.ft8_encode_message(message.encode("ascii", errors="replace"), buf, FT8_NN)
        if rc != FT8_NN:
            return None
        return list(buf)

    def _is_sync_index(self, i: int) -> bool:
        return any(lo <= i < hi for lo, hi in self.SYNC_RANGES)

    def payload77(self, message: str):
        """message -> 77-bit payload (MSB-first 0/1 list), or None if unencodable.
        Mirrors extract_llrs_ctypes.ExtractLLRs.true_codeword, truncated to the
        first 77 (of 174) codeword bits -- the systematic message payload."""
        tones = self.encode_tones(message)
        if tones is None:
            return None
        data_tones = [t for i, t in enumerate(tones) if not self._is_sync_index(i)]
        bits = []
        for tone in data_tones:
            b3 = self._inv_gray[tone]
            bits.append((b3 >> 2) & 1)
            bits.append((b3 >> 1) & 1)
            bits.append(b3 & 1)
        return bits[:77]


# RR73 on-air grid value vs our own MAXGRID4+3 encoding -- GAP-LOCATE Amendment 4 /
# the board's RR73 finding. §4/ROW 0f fit BOTH encodings and keep the winner by
# correlation. "32373" here is the suspected PACKED igrid4 FIELD VALUE, not a
# parseable Maidenhead locator string -- ft8_encode_message's text parser cannot
# produce it (it would either fail or silently parse as something else entirely),
# so the alternate codeword is built at the BIT level via ldpc_encode.py, not by
# feeding alternate text to the encoder.
RR73_ONAIR_IGRID4 = 32373


def _is_rr73_message(tokens: list) -> bool:
    return len(tokens) >= 1 and tokens[-1] == "RR73"


def _rr73_alt_tones(ows_payload77: list):
    """ows_payload77: the 77-bit payload for the STANDARD (MAXGRID4+3) RR73
    encoding (from Encoder.payload77). Returns the on-air-grid alternative's 79
    tones, built by splicing the (ir, igrid4) field to RR73_ONAIR_IGRID4 and
    recomputing CRC-14 + LDPC parity from scratch (ldpc_encode.py)."""
    alt_payload = LE.rr73_alt_payload77(ows_payload77, RR73_ONAIR_IGRID4)
    alt_codeword = LE.encode174_bits(alt_payload)
    return LE.codeword174_to_tones(alt_codeword)


def _payloads_match(enc: "Encoder", ows_msg: str, ows_payload: list, wsjtx_msg: str) -> bool:
    """Amendment 1's twin test: same payload outcome fields, RR73-equivalent
    (comparator.payload_match, GAP-LOCATE Amendment 4). Both X and Y here come
    from RE-ENCODING RENDERED TEXT with our own encoder (never from raw decoded
    RF bits), so Y == X already covers the identical-text case (including RR73,
    since both logs render the RR73 report as literal 'RR73' text -- board note,
    2026-09-27). v_star is passed for interface parity with GAP-LOCATE's
    comparator; it cannot fire here (see module docstring reasoning in the
    accompanying report) because Y is never a real-RF-decoded value that could
    legitimately differ from X only in the RR73 sentinel field."""
    y = enc.payload77(wsjtx_msg)
    if y is None:
        return False
    if y == ows_payload:
        return True
    return CMP.payload_match(ows_payload, y, ows_msg, CMP.RR73_STD)


def compute_twins(enc: "Encoder", owsfz_raw: dict, wsjtx_raw: dict, log) -> dict:
    """Amendment 1's de-twin pass. Returns, per (ts, ows_msg) key, the matched
    (ts, wsjtx_msg) twin key if one was assigned, plus ROW 0i's two mechanical
    counts (twin_share denominator/numerator, and the double-twin count)."""
    owsfz_by_cycle = collections.defaultdict(list)
    for k, v in owsfz_raw.items():
        owsfz_by_cycle[k[0]].append((k, v))
    wsjtx_by_cycle = collections.defaultdict(list)
    for k, v in wsjtx_raw.items():
        wsjtx_by_cycle[k[0]].append((k, v))

    twin_of = {}          # ows_key -> wsjtx_key
    wsjtx_match_counts = collections.Counter()  # wsjtx_key -> # distinct ows candidates
    n_snr_ge0 = 0
    n_twinned = 0

    payload_cache = {}

    def payload_of(msg):
        if msg not in payload_cache:
            payload_cache[msg] = enc.payload77(msg)
        return payload_cache[msg]

    for ts, ows_entries in owsfz_by_cycle.items():
        wsjtx_entries = wsjtx_by_cycle.get(ts, [])
        if not wsjtx_entries:
            for key, (snr, _dt, _f) in ows_entries:
                if snr >= 0:
                    n_snr_ge0 += 1
            continue

        # Build candidate edges (i, j, |df|) for SNR>=0 OWS rows only (ROW 0i's own
        # scope), payload-matched within TWIN_DELTA_F_HZ.
        edges = []
        for i, (ows_key, (snr, _dt, ows_f)) in enumerate(ows_entries):
            if snr < 0:
                continue
            n_snr_ge0 += 1
            ows_payload = payload_of(ows_key[1])
            if ows_payload is None:
                continue
            for j, (wsjtx_key, (_s2, _d2, wj_f)) in enumerate(wsjtx_entries):
                df = abs(wj_f - ows_f)
                if df > TWIN_DELTA_F_HZ:
                    continue
                if _payloads_match(enc, ows_key[1], ows_payload, wsjtx_key[1]):
                    edges.append((df, i, j))

        # ROW 0i double-twin count: how many distinct OWS candidates each wsjtx
        # row matches, BEFORE the one-per-row pairing constraint.
        per_wsjtx_candidates = collections.defaultdict(set)
        for _df, i, j in edges:
            per_wsjtx_candidates[j].add(i)
        for j, is_ in per_wsjtx_candidates.items():
            if len(is_) >= 2:
                wsjtx_match_counts[(ts, j)] = len(is_)

        # Greedy nearest-|df|-first, at most one pairing per side.
        edges.sort(key=lambda e: e[0])
        used_i, used_j = set(), set()
        for df, i, j in edges:
            if i in used_i or j in used_j:
                continue
            used_i.add(i)
            used_j.add(j)
            twin_of[ows_entries[i][0]] = wsjtx_entries[j][0]
            n_twinned += 1

    n_double_twinned = len(wsjtx_match_counts)
    twin_share = (n_twinned / n_snr_ge0) if n_snr_ge0 else 0.0
    log("twin: n_snr_ge0=%d n_twinned=%d twin_share=%.4f n_double_twinned_wsjtx=%d"
        % (n_snr_ge0, n_twinned, twin_share, n_double_twinned))

    return {
        "twin_of": twin_of,
        "row0i": {
            "n_snr_ge0": n_snr_ge0,
            "n_twinned": n_twinned,
            "twin_share": twin_share,
            "n_double_twinned_wsjtx": n_double_twinned,
            "pass": bool(twin_share >= 0.90 and n_double_twinned == 0),
        },
    }


def _is_isolated(freq_hz: float, others: list) -> bool:
    for f in others:
        if abs(f - freq_hz) < ISOLATION_HZ:
            return False
    return True


def build_population(enc: "Encoder", log) -> dict:
    """Returns a dict with numeric-only population records plus in-memory tone
    arrays (never message text). Population P = OWS decodes meeting SNR/isolation/
    re-encodable-standard filters (spec sec.3, Amendment 1's de-twinned isolation).
    Split A = even cycle index, B = odd.
    """
    owsfz_raw = _load_all_txt(common.OWSFZ_ALL_TXT)
    wsjtx_raw = _load_all_txt(common.WSJTX_ALL_TXT)
    order = cycle_order()
    cycle_index = {ts: i for i, ts in enumerate(order)}

    twins = compute_twins(enc, owsfz_raw, wsjtx_raw, log)
    twin_of = twins["twin_of"]
    row0i = twins["row0i"]

    owsfz_by_cycle = collections.defaultdict(list)
    for k, v in owsfz_raw.items():
        owsfz_by_cycle[k[0]].append((k, v))
    wsjtx_by_cycle = collections.defaultdict(list)
    for k, v in wsjtx_raw.items():
        wsjtx_by_cycle[k[0]].append((k, v))

    excluded_reasons = collections.Counter()
    rows = []
    n_rr73 = 0
    row_id = 0

    for ts, entries in owsfz_by_cycle.items():
        if ts not in cycle_index:
            continue
        wsjtx_entries = wsjtx_by_cycle.get(ts, [])
        for i, (key, val) in enumerate(entries):
            _ts, msg = key
            snr, dt, freq_hz = val
            if snr < 0:
                excluded_reasons["snr_below_0"] += 1
                continue
            own_others = [f for j, (_, (_, _, f)) in enumerate(entries) if j != i]
            twin_key = twin_of.get(key)
            wsjtx_others = [f for wk, (_, _, f) in wsjtx_entries if wk != twin_key]
            if not _is_isolated(freq_hz, own_others + wsjtx_others):
                excluded_reasons["not_isolated"] += 1
                continue
            tokens = msg.split()
            if msg.startswith("<") or "<" in msg:
                excluded_reasons["hashed_nonstandard"] += 1
                continue
            if len(tokens) < 3:
                excluded_reasons["two_token_or_fewer"] += 1
                continue
            tones = enc.encode_tones(msg)
            if tones is None:
                excluded_reasons["not_reencodable"] += 1
                continue
            is_rr73 = _is_rr73_message(tokens)
            tones_alt = _rr73_alt_tones(enc.payload77(msg)) if is_rr73 else None
            if is_rr73:
                n_rr73 += 1
            rows.append({
                "row_id": row_id,
                "cycle_ts": ts,
                "cycle_index": cycle_index[ts],
                "freq_hz": freq_hz,
                "dt": dt,
                "snr": snr,
                "is_rr73": is_rr73,
                "tones": tones,
                "tones_alt": tones_alt,
            })
            row_id += 1

    log("population: n_cycles=%d n_owsfz_rows=%d n_P=%d n_rr73=%d"
        % (len(order), len(owsfz_raw), len(rows), n_rr73))
    log("population: excluded_by_reason=%s" % dict(excluded_reasons))

    n_total_cycles = len(order)
    excl_first10 = int(round(0.10 * n_total_cycles))
    first10_ts = set(order[:excl_first10])

    anchor_rows = [r for r in rows if r["cycle_ts"] in first10_ts]
    ab_rows = [r for r in rows if r["cycle_ts"] not in first10_ts]
    split_a = [r for r in ab_rows if r["cycle_index"] % 2 == 0]
    split_b = [r for r in ab_rows if r["cycle_index"] % 2 == 1]
    for r in anchor_rows:
        r["split"] = "anchor"
    for r in split_a:
        r["split"] = "A"
    for r in split_b:
        r["split"] = "B"

    log("population: n_anchor_pool(first10%%)=%d n_A=%d n_B=%d"
        % (len(anchor_rows), len(split_a), len(split_b)))

    return {
        "all_rows": rows,
        "anchor_rows": anchor_rows,
        "split_a": split_a,
        "split_b": split_b,
        "n_total_cycles": n_total_cycles,
        "excluded_reasons": dict(excluded_reasons),
        "n_rr73": n_rr73,
        "row0i": row0i,
    }


def cycle_wav_path(ts: str) -> str:
    return os.path.join(common.OWSFZ_WAV_DIR, ts + ".wav")
