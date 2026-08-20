#!/usr/bin/env python3
"""AO1 -- shared infrastructure: the matched-pair population (Sec.4 of the spec),
with SNR retained (c2_phase2c_ber_measurement.parse_all_txt drops it -- Sec.4 flags
this explicitly, Part C needs it). A NEW parser, not an edit to the shared c2
module: every already-reported figure that depended on parse_all_txt's exact
behaviour stays untouched.

Spec: qa/rr-study/2026-08-19-1058-architect-to-qa-prereg-ao1-production-time-origin-offset.md
Sec.4 ("Instruments, populations, clustering").

NFR-021: build_matched_pairs() returns rows carrying `message` (in-process only,
consumed by the harness's true_codeword() call) -- never written to any emitted
file. The harness strips it before anything reaches disk or stdout beyond
aggregate counts, same discipline as plive_population.py.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "cycleframer-alignment-replay"))
sys.path.insert(0, os.path.join(REPO_ROOT, "qa", "rr-study", "p-live-population"))

import c2_phase2c_ber_measurement as C2  # noqa: E402 -- normalize_hash_tokens only
from plive_population import (  # noqa: E402,F401 -- re-exported unchanged
    ALL_CORPORA, EXTENSION_CORPORA, PRIMARY_CORPUS, corpus_paths,
)


def parse_all_txt_with_snr(path: str) -> list[dict]:
    """Same tokenisation as c2_phase2c_ber_measurement.parse_all_txt -- tok[5] is
    DT, tok[6] is freq in INTEGER Hz; confusing them inverts a result exactly
    (MEMORY.md standing note) -- but ALSO keeps tok[4]=SNR (dB, integer), which
    that function discards."""
    rows = []
    n_bad_snr = 0
    with open(path, encoding="ascii", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if not line.strip():
                continue
            tok = line.split()
            if len(tok) < 8:
                continue
            ts, dt, freq, message = tok[0], tok[5], tok[6], " ".join(tok[7:])
            try:
                snr = int(tok[4])
            except ValueError:
                snr = None
                n_bad_snr += 1
            rows.append({"ts": ts, "snr": snr, "dt": float(dt), "freq": float(freq),
                         "message": message})
    return rows, n_bad_snr


def build_matched_pairs(corpus_name: str) -> tuple[list[dict], dict]:
    """Sec.4: 'a reference decode whose hash-normalised message appears EXACTLY
    ONCE in our own ALL.TXT for the same ts. Uniqueness is required -- ambiguous
    pairings are dropped and counted, not resolved.'

    Symmetric construction: group BOTH files' rows by (ts, normalised message).
    A pair is admitted only when BOTH sides have exactly one row at that key. If
    the reference itself carries two decodes collapsing to the same normalised
    message at the same ts, pairing either one to our single match is exactly as
    ambiguous as the reverse case the spec names -- dropped by the same rule, not
    resolved by picking one arbitrarily. (Measured on PRIMARY: zero ambiguous
    cases either direction -- the symmetric rule and the spec's literal one-
    directional rule coincide here; this function reports both counts so a
    corpus where they diverge is visible, not silently absorbed.)

    Returns (pairs, diagnostics).
      pairs: [{ts, message, ref_freq_hz, ref_dt, ref_snr, our_freq_hz, our_dt,
                our_snr, d_dt (= our_dt - ref_dt, SIGNED), corpus}], sorted by
             (ts, ref_freq_hz, ref_dt, message) -- construction-stable order for
             any downstream seeded sampler (hash-randomised-set-iteration note).
      diagnostics: {n_ref_rows, n_our_rows, n_ref_snr_unparseable,
                    frac_ref_snr_unparseable, n_ambiguous_ref_side,
                    n_ambiguous_our_side, n_matched, n_matched_clusters}
    """
    paths = corpus_paths(corpus_name)
    ref_rows, n_ref_bad = parse_all_txt_with_snr(paths["wsjtx_all_txt"])
    our_rows, _n_our_bad = parse_all_txt_with_snr(paths["owsfz_all_txt"])

    ref_by_key: dict[tuple, list[dict]] = {}
    for r in ref_rows:
        key = (r["ts"], C2.normalize_hash_tokens(r["message"]))
        ref_by_key.setdefault(key, []).append(r)

    our_by_key: dict[tuple, list[dict]] = {}
    for r in our_rows:
        key = (r["ts"], C2.normalize_hash_tokens(r["message"]))
        our_by_key.setdefault(key, []).append(r)

    common_keys = sorted(set(ref_by_key) & set(our_by_key))  # sort before any
    # seeded draw indexes into this -- hash-randomised-set-iteration standing note
    pairs: list[dict] = []
    n_ambiguous_ref = 0
    n_ambiguous_our = 0
    for key in common_keys:
        rlist = ref_by_key[key]
        olist = our_by_key[key]
        ref_amb = len(rlist) != 1
        our_amb = len(olist) != 1
        if ref_amb:
            n_ambiguous_ref += 1
        if our_amb:
            n_ambiguous_our += 1
        if ref_amb or our_amb:
            continue
        r, o = rlist[0], olist[0]
        pairs.append({
            "ts": r["ts"], "message": r["message"],
            "ref_freq_hz": r["freq"], "ref_dt": r["dt"], "ref_snr": r["snr"],
            "our_freq_hz": o["freq"], "our_dt": o["dt"], "our_snr": o["snr"],
            "d_dt": o["dt"] - r["dt"],
            "corpus": corpus_name,
        })
    pairs.sort(key=lambda p: (p["ts"], p["ref_freq_hz"], p["ref_dt"], p["message"]))

    n_matched_clusters = len({p["ts"] for p in pairs})
    diagnostics = {
        "n_ref_rows": len(ref_rows), "n_our_rows": len(our_rows),
        "n_ref_snr_unparseable": n_ref_bad,
        "frac_ref_snr_unparseable": (n_ref_bad / len(ref_rows)) if ref_rows else float("nan"),
        "n_ambiguous_ref_side": n_ambiguous_ref, "n_ambiguous_our_side": n_ambiguous_our,
        "n_matched": len(pairs), "n_matched_clusters": n_matched_clusters,
    }
    return pairs, diagnostics


def build_reference_population(corpus_name: str) -> list[dict]:
    """Every reference (WSJT-X) decode, with SNR, freq, dt, and whether OUR own
    ALL.TXT for the same ts contains it (membership test, same convention as
    plive_population.build_p_hit_population -- NOT the strict-uniqueness matched
    -pair test above, because Part C's recall statistic is a population-level
    rate and does not care about pairing ambiguity). Used ONLY by Part C.

    Returns [{ts, snr, dt, recovered: bool}] -- message text dropped immediately,
    never retained (NFR-021; Part C never needs it past the membership check)."""
    paths = corpus_paths(corpus_name)
    ref_rows, _ = parse_all_txt_with_snr(paths["wsjtx_all_txt"])
    our_rows, _ = parse_all_txt_with_snr(paths["owsfz_all_txt"])

    our_msgset_by_cycle: dict[str, set[str]] = {}
    for r in our_rows:
        our_msgset_by_cycle.setdefault(r["ts"], set()).add(C2.normalize_hash_tokens(r["message"]))

    out = []
    for r in ref_rows:
        key = C2.normalize_hash_tokens(r["message"])
        recovered = key in our_msgset_by_cycle.get(r["ts"], set())
        out.append({"ts": r["ts"], "snr": r["snr"], "dt": r["dt"], "recovered": recovered})
    return out


if __name__ == "__main__":
    for _name in ALL_CORPORA:
        _pairs, _diag = build_matched_pairs(_name)
        print("AO1 matched pairs %s: %s" % (_name, _diag))
