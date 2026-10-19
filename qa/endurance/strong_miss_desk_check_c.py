#!/usr/bin/env python3
"""STRONG-MISS desk check (c), items 2 and 3, for endurance run 20261009_1752 (QA, 2026-10-10).

Spec: qa/rr-study/2026-10-10-1015-architect-to-qa-spec-strong-miss-replay.md section 4.
Question: does the h12 hashed-callsign suppression (the shim renders `<...>` and KEEPS the decode)
explain the hashed WSJT-X-only misses?  The matching key collapses every <...> token, so a decode
whose callsign OpenWSFZ suppressed still matches WSJT-X's resolved text.

  (2) Of the matched pairs, how many have an OpenWSFZ text containing the literal `<...>` placeholder
      while WSJT-X's raw text differs, i.e. matched ONLY because of the collapse.  > 0 means the
      suppressed decodes are being counted as matched, not missed.
  (3) Of the strong (SNR > 0 dB) hashed WSJT-X-only rows, how many have an OpenWSFZ row in the same
      cycle within 10 Hz whose collapsed text differs (an overlap/other-text case, not suppression).

HK-037 / NFR-021: message text never leaves `analyse()`; it returns counters only. Nothing per
message is printed or written. Matching rule = the standing one (cycle ts + text with <...>
collapsed, paired in order per key).  Asserts the 62,340 / 31,271 split.
"""
import json
import re
import sys
from collections import defaultdict

HASH_RE = re.compile(r"<[^>]*>")
PLACEHOLDER = "<...>"
STRONG_SNR_DB = 0.0
NEAR_HZ = 10.0
EXPECT_MATCHED, EXPECT_WSJT_ONLY = 62340, 31271


def analyse(ows_path: str, wsj_path: str) -> dict:
    def read(p):
        rows = []
        for line in open(p, encoding="ascii", errors="replace"):
            t = line.split()
            if len(t) < 8:
                continue
            try:
                snr, f = float(t[4]), float(t[6])
            except ValueError:
                continue
            raw = " ".join(t[7:])
            rows.append({"ts": t[0], "snr": snr, "f": f, "raw": raw, "key": HASH_RE.sub("<HASH>", raw)})
        return rows

    ows, wsj = read(ows_path), read(wsj_path)
    by_o, by_w = defaultdict(list), defaultdict(list)
    for r in ows:
        by_o[(r["ts"], r["key"])].append(r)
    for r in wsj:
        by_w[(r["ts"], r["key"])].append(r)
    pairs, u_w = [], []
    for k in sorted(set(by_o) | set(by_w)):
        a, b = by_o.get(k, []), by_w.get(k, [])
        n = min(len(a), len(b))
        pairs += list(zip(a[:n], b[:n]))
        u_w += b[n:]
    assert len(pairs) == EXPECT_MATCHED and len(u_w) == EXPECT_WSJT_ONLY, (len(pairs), len(u_w))

    # (2)
    ows_ph = [(a, b) for a, b in pairs if PLACEHOLDER in a["raw"]]
    ph_differs = sum(1 for a, b in ows_ph if a["raw"] != b["raw"])
    wsj_ph_matched = sum(1 for a, b in pairs if PLACEHOLDER in b["raw"])
    ows_total_ph = sum(1 for r in ows if PLACEHOLDER in r["raw"])
    wsj_total_ph = sum(1 for r in wsj if PLACEHOLDER in r["raw"])

    # (3)
    ows_cyc = defaultdict(list)
    for r in ows:
        ows_cyc[r["ts"]].append(r)
    strong_hashed = [r for r in u_w if r["snr"] > STRONG_SNR_DB and "<" in r["raw"] and ";" not in r["raw"]]
    near_other = 0
    near_same_key = 0
    wsj_cyc = defaultdict(list)
    for r in wsj:
        wsj_cyc[r["ts"]].append(r)
    near_other_and_crowded = 0
    for r in strong_hashed:
        near = [o for o in ows_cyc.get(r["ts"], []) if abs(o["f"] - r["f"]) <= NEAR_HZ]
        if any(o["key"] != r["key"] for o in near):
            near_other += 1
            if any(w is not r and abs(w["f"] - r["f"]) <= 25.0 for w in wsj_cyc[r["ts"]]):
                near_other_and_crowded += 1
        if any(o["key"] == r["key"] for o in near):
            near_same_key += 1
    return {
        "matched_pairs": len(pairs),
        "check2_openwsfz_rows_with_placeholder_total": ows_total_ph,
        "check2_wsjtx_rows_with_placeholder_total": wsj_total_ph,
        "check2_matched_pairs_openwsfz_placeholder": len(ows_ph),
        "check2_of_those_wsjtx_raw_text_differs_matched_only_by_collapse": ph_differs,
        "check2_matched_pairs_wsjtx_placeholder": wsj_ph_matched,
        "check3_strong_hashed_wsjtx_only_rows": len(strong_hashed),
        "check3_with_ows_row_within_10hz_different_collapsed_text": near_other,
        "check3_of_those_also_wsjtx_neighbour_within_25hz": near_other_and_crowded,
        "check3_with_ows_row_within_10hz_same_collapsed_text": near_same_key,
    }


if __name__ == "__main__":
    print(json.dumps(analyse(sys.argv[1], sys.argv[2]), indent=1, sort_keys=True))
