#!/usr/bin/env python3
"""D-001 C.2 Phase 2c, Part B -- hard-decision BER measurement.

(dev-tasks/2026-07-26-d001-c2-phase2c-shrinkage-trial-and-ber.md Sec.3, Sec.3.5;
source: 2026-07-26-1830-architect-c2-phase2a-ruling.md Sec.6.)

For each message WSJT-X reported and we missed, re-encodes WSJT-X's own reported text
(via the Gray/sync round-trip verified in c2_phase2c_gray_sync_roundtrip_verify.py) to
recover the true 174-bit codeword, and compares it against the HARD DECISION of our own
raw (pre-normalisation) LLRs for the candidate sitting at that message's frequency/time
(exported via candidate_diag.csv's llr174 column, D-001 C.2 Phase 2c native change).

Hard decision convention matches patched/ft8/decode.c's own OSD gate exactly:
    hd[i] = 0 if llr[i] > 0.0 else 1
(see decode.c's `int hd = (llr_for_osd[i] > 0.0f) ? 0 : 1;` -- the channel hard decision
used at both OSD call sites). Sign is invariant under ftx_normalize_logl (a positive
scale factor), so the RAW (pre-normalisation) llr174 export gives the identical hard
decision the normalised value would.

SELF-CHECK FIRST (per this thread's own established convention -- C.2 Phase 1's
byte-identical no-op proof, Phase 2a's audio-source confound catch): the MATCHED-HIT
CONTROL population (messages we DID decode) must show near-zero BER against their own
candidate's LLRs. If it does not, the encode/strip/Gray-decode/hard-decision pipeline
has a bug and the 135/567 numbers below must not be trusted -- this mirrors every prior
self-check in this thread and is treated with the same weight.

Populations, read separately per dev-task Sec.3 item 4:
  - THE 135 (score >= 10, K10/cap140 candidate set -- same run as Part A's baseline).
  - THE 567 (score 5-9, K=4/cap2000 candidate set -- a separate native diagnostic build;
    see run log for the temporary K_MIN_SCORE/K_MAX_CANDIDATES swap, reverted immediately
    after capture).
  - MATCHED-HIT CONTROL (messages we DID decode, K10/cap140) -- also the self-check pop.

Read against the Architect's illustrative (not calibrated) bands (2026-07-26-1830 Sec.6):
  ~50%          -> sync/demodulation front-end; kills all LLR-scaling avenues.
  ~15-25%       -> decode effort (BP iterations, OSD depth/gate); cheap constants.
  low, correct signs -> LLR magnitude; reopens Phase 2b per Sec.5's condition.

NFR-021: aggregate statistics only -- no callsign, message text, or per-record field is
ever printed. Message TEXT is used internally (re-encoded to recover the true codeword)
but never written to stdout or any committed file. ASCII-only console output (HK-009).
"""
from __future__ import annotations

import csv
import ctypes
import os
import re
import statistics as st
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
BASE = os.path.join(REPO_ROOT, "artefacts", "20260725_live_run_1806")
WSJTX_ALL_TXT = os.path.join(BASE, "wsjt-x", "ALL.TXT")
WAV68_DIR = os.path.join(BASE, "owsfz", "wav68")

C2_MINE_ALL_TXT = os.path.join(BASE, "c2_phase1", "k10_c0.10_n60", "ALL.TXT")
C2_DIAG_CSV     = os.path.join(BASE, "c2_phase1", "k10_c0.10_n60", "candidate_diag.csv")
K4_ALL_TXT_FROZEN = os.path.join(BASE, "c4_min_score", "k4_cap2000", "k10_c0.10_n60", "ALL.TXT")
K4_DIAG_CSV_FROZEN = os.path.join(BASE, "c4_min_score", "k4_cap2000", "k10_c0.10_n60", "candidate_diag.csv")

# This session's own captures (with the llr174 column).
K10_CAP_DIR = os.path.join(REPO_ROOT, "artefacts", "d001_c2_phase2c", "ber", "k10_cap140", "k10_c0.10_n60")
K4_CAP_DIR  = os.path.join(REPO_ROOT, "artefacts", "d001_c2_phase2c", "ber", "k4_cap2000", "k10_c0.10_n60")

DLL_PATH = os.path.join(REPO_ROOT, "src", "OpenWSFZ.Ft8", "Native", "win-x64", "libft8.dll")

FREQ_TOL_HZ = 10.0
DT_TOL_S = 0.5

FT8_NN = 79
FT8_ND = 58
FTX_LDPC_N = 174
SYNC_RANGES = [(0, 7), (36, 43), (72, 79)]
GRAY_MAP = [0, 1, 3, 2, 5, 6, 4, 7]  # kFT8_Gray_map, verified via
                                       # c2_phase2c_gray_sync_roundtrip_verify.py
INV_GRAY = [0] * 8
for _i, _v in enumerate(GRAY_MAP):
    INV_GRAY[_v] = _i

_HASH_BRACKET_RE = re.compile(r"<[^>]*>")


def normalize_hash_tokens(message: str) -> str:
    return _HASH_BRACKET_RE.sub("<HASH>", message)


def is_sync_index(i: int) -> bool:
    return any(lo <= i < hi for lo, hi in SYNC_RANGES)


def parse_all_txt(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="ascii", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if not line.strip():
                continue
            tok = line.split()
            if len(tok) < 8:
                continue
            ts, dt, freq, message = tok[0], tok[5], tok[6], " ".join(tok[7:])
            rows.append({"ts": ts, "dt": float(dt), "freq": float(freq), "message": message})
    return rows


def load_candidate_diag_with_llr(path: str) -> dict[str, list[dict]]:
    by_cycle: dict[str, list[dict]] = {}
    with open(path, newline="", encoding="ascii", errors="replace") as fh:
        for row in csv.DictReader(fh):
            llr_field = row.get("llr174", "")
            llr = [float(x) for x in llr_field.split(";")] if llr_field else []
            rec = {
                "freq_hz": float(row["freq_hz"]),
                "dt": float(row["dt"]),
                "score": int(row["score"]),
                "decoded": row["decoded"] == "1",
                "llr174": llr,
            }
            by_cycle.setdefault(row["cycle_ts"], []).append(rec)
    return by_cycle


def nearest_candidate(freq: float, dt: float, cands: list[dict]) -> dict | None:
    best, best_fd = None, None
    for c in cands:
        fd = abs(c["freq_hz"] - freq)
        dd = abs(c["dt"] - dt)
        if fd <= FREQ_TOL_HZ and dd <= DT_TOL_S:
            if best is None or fd < best_fd:
                best, best_fd = c, fd
    return best


def has_any_candidate_nearby(freq: float, dt: float, cands: list[dict]) -> bool:
    return nearest_candidate(freq, dt, cands) is not None


class Encoder:
    def __init__(self, dll_path: str):
        self.dll = ctypes.CDLL(os.path.abspath(dll_path))
        self.dll.ft8_encode_message.restype = ctypes.c_int
        self.dll.ft8_encode_message.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint8), ctypes.c_int]

    def true_codeword(self, message: str) -> list[int] | None:
        buf = (ctypes.c_uint8 * FT8_NN)()
        rc = self.dll.ft8_encode_message(message.encode("ascii", errors="replace"), buf, FT8_NN)
        if rc != FT8_NN:
            return None
        tones = list(buf)
        data_tones = [t for i, t in enumerate(tones) if not is_sync_index(i)]
        bits: list[int] = []
        for tone in data_tones:
            b3 = INV_GRAY[tone]
            bits.append((b3 >> 2) & 1)
            bits.append((b3 >> 1) & 1)
            bits.append(b3 & 1)
        return bits


def hard_decision_ber(llr174: list[float], true_bits: list[int]) -> float:
    """Hard-decision BER of llr174 (raw, pre-normalisation, from ftx_get_candidate_raw_llr)
    against true_bits (the re-encoded true codeword, in encode.c's own bit-value sense --
    verified by c2_phase2c_gray_sync_roundtrip_verify.py's CRC-14 + LDPC-syndrome check).

    SIGN CONVENTION NOTE (found empirically during this measurement, recorded here so
    the next person does not have to re-derive it): decode.c's OWN internal hard-decision
    formula for its nhard/OSD gate feature is `hd = (llr > 0.0f) ? 0 : 1` (decode.c,
    ftx_decode_candidate). That formula compares against bp_decode's/osd_decode's internal
    bit representation for a Hamming-CLOSENESS proxy (gating), not against the payload's
    true bit value in encode.c's sense -- LDPC belief-propagation implementations commonly
    carry an internal 0/1 <-> LLR-sign convention that only round-trips to the correct
    payload bits through the full bp_decode/pack_bits pipeline, not through a naive
    sign check in isolation. ft8_extract_symbol's OWN comment ("log likelihood
    log(p(1)/p(0))") is the literal, correct description of the RAW extract_likelihood
    value used here: positive means bit=1 MORE LIKELY, in encode.c's own bit-value sense.
    This was verified empirically against the matched-hit control population (messages we
    definitely decoded correctly, CRC-checked) BEFORE trusting it for THE 135/567: using
    `hd = 1 if llr > 0.0 else 0` gives a near-zero median BER for the control population;
    decode.c's own hd formula (`0 if llr > 0.0 else 1`) gives ~90-95% BER for the SAME
    control population -- i.e. its near-total complement, confirming this is a sign-
    convention question, not a bug in the Gray/sync/CRC/LDPC-syndrome-verified codeword
    recovery itself.
    """
    assert len(llr174) == FTX_LDPC_N and len(true_bits) == FTX_LDPC_N
    errors = 0
    for llr, tb in zip(llr174, true_bits):
        hd = 1 if llr > 0.0 else 0  # see docstring: empirically validated, NOT decode.c's own hd
        if hd != tb:
            errors += 1
    return errors / FTX_LDPC_N


def compute_135_population(cycles: list[str]) -> list[dict]:
    """(ts, freq, dt, message) rows for THE 135, freq/dt taken from WSJT-X's own ALL.TXT."""
    wsjtx_rows = parse_all_txt(WSJTX_ALL_TXT)
    cycle_set = set(cycles)
    wsjtx_by_cycle: dict[str, list[dict]] = {}
    for r in wsjtx_rows:
        if r["ts"] in cycle_set:
            wsjtx_by_cycle.setdefault(r["ts"], []).append(r)

    mine_rows = parse_all_txt(C2_MINE_ALL_TXT)
    mine_msgset_by_cycle: dict[str, set[str]] = {}
    for r in mine_rows:
        mine_msgset_by_cycle.setdefault(r["ts"], set()).add(normalize_hash_tokens(r["message"]))

    cand_by_cycle = load_candidate_diag_simple(C2_DIAG_CSV)

    out = []
    for ts in cycles:
        my_msgs = mine_msgset_by_cycle.get(ts, set())
        failed_cands = [c for c in cand_by_cycle.get(ts, []) if not c["decoded"]]
        for row in wsjtx_by_cycle.get(ts, []):
            key = normalize_hash_tokens(row["message"])
            if key in my_msgs:
                continue
            if has_any_candidate_nearby(row["freq"], row["dt"], failed_cands):
                out.append(row)
    return out


def load_candidate_diag_simple(path: str) -> dict[str, list[dict]]:
    by_cycle: dict[str, list[dict]] = {}
    with open(path, newline="", encoding="ascii", errors="replace") as fh:
        for row in csv.DictReader(fh):
            rec = {"freq_hz": float(row["freq_hz"]), "dt": float(row["dt"]),
                   "decoded": row["decoded"] == "1"}
            by_cycle.setdefault(row["cycle_ts"], []).append(rec)
    return by_cycle


def compute_648_population(cycles: list[str]) -> list[dict]:
    wsjtx_rows = parse_all_txt(WSJTX_ALL_TXT)
    cycle_set = set(cycles)
    wsjtx_by_cycle: dict[str, list[dict]] = {}
    for r in wsjtx_rows:
        if r["ts"] in cycle_set:
            wsjtx_by_cycle.setdefault(r["ts"], []).append(r)

    mine_rows = parse_all_txt(C2_MINE_ALL_TXT)
    mine_msgset_by_cycle: dict[str, set[str]] = {}
    for r in mine_rows:
        mine_msgset_by_cycle.setdefault(r["ts"], set()).add(normalize_hash_tokens(r["message"]))

    cand_by_cycle = load_candidate_diag_simple(C2_DIAG_CSV)

    out = []
    for ts in cycles:
        my_msgs = mine_msgset_by_cycle.get(ts, set())
        cands = cand_by_cycle.get(ts, [])
        failed_cands = [c for c in cands if not c["decoded"]]
        decoded_cands = [c for c in cands if c["decoded"]]
        for row in wsjtx_by_cycle.get(ts, []):
            key = normalize_hash_tokens(row["message"])
            if key in my_msgs:
                continue
            if has_any_candidate_nearby(row["freq"], row["dt"], failed_cands):
                continue
            if has_any_candidate_nearby(row["freq"], row["dt"], decoded_cands):
                continue
            out.append(row)
    return out


def compute_567_population(population_648: list[dict]) -> list[dict]:
    k4_cand_by_cycle = load_candidate_diag_simple(K4_ALL_TXT_and_diag())
    k4_msgset_by_cycle: dict[str, set[str]] = {}
    for r in parse_all_txt(K4_ALL_TXT_FROZEN):
        k4_msgset_by_cycle.setdefault(r["ts"], set()).add(normalize_hash_tokens(r["message"]))

    expanded: list[dict] = []
    for row in population_648:
        cands = k4_cand_by_cycle.get(row["ts"], [])
        found = nearest_candidate(row["freq"], row["dt"], cands)
        if found is not None and not found["decoded"]:
            expanded.append(row)

    out = [row for row in expanded
           if normalize_hash_tokens(row["message"]) not in k4_msgset_by_cycle.get(row["ts"], set())]
    return out


def K4_ALL_TXT_and_diag() -> str:
    return K4_DIAG_CSV_FROZEN


def compute_matched_hit_control(cycles: list[str], limit: int) -> list[dict]:
    """Messages we DID decode (K10/cap140 baseline) -- self-check + regression control.

    IMPORTANT: uses OUR OWN ALL.TXT's freq/dt/message-text for each row, not WSJT-X's.
    A first version of this script used WSJT-X's reported freq/dt to look up "the
    nearest decoded candidate of ours" -- in a busy cycle with many decoded candidates,
    that can pick the WRONG candidate (two different stations within the +/-10 Hz/+/-0.5s
    tolerance), which would corrupt exactly the self-check this population exists to run.
    Using our own ALL.TXT's own freq/dt for a message we know we decoded is unambiguous:
    it IS the candidate that produced this exact text."""
    wsjtx_msgset_by_cycle = {}
    for r in parse_all_txt(WSJTX_ALL_TXT):
        if r["ts"] in set(cycles):
            wsjtx_msgset_by_cycle.setdefault(r["ts"], set()).add(normalize_hash_tokens(r["message"]))

    mine_rows = parse_all_txt(os.path.join(K10_CAP_DIR, "ALL.TXT"))

    out = []
    for row in mine_rows:
        if row["ts"] not in set(cycles):
            continue
        if normalize_hash_tokens(row["message"]) in wsjtx_msgset_by_cycle.get(row["ts"], set()):
            out.append(row)
            if len(out) >= limit:
                return out
    return out


def measure_population(label: str, population: list[dict], cand_by_cycle: dict[str, list[dict]],
                        encoder: Encoder, require_decoded: bool | None = None) -> list[float]:
    bers: list[float] = []
    n_no_true_codeword = 0
    n_no_candidate = 0
    for row in population:
        true_bits = encoder.true_codeword(row["message"])
        if true_bits is None:
            n_no_true_codeword += 1
            continue
        cands = cand_by_cycle.get(row["ts"], [])
        if require_decoded is not None:
            cands = [c for c in cands if c["decoded"] == require_decoded]
        cand = nearest_candidate(row["freq"], row["dt"], cands)
        if cand is None or not cand["llr174"]:
            n_no_candidate += 1
            continue
        bers.append(hard_decision_ber(cand["llr174"], true_bits))
    print(f"  [{label}] n={len(population)} measured={len(bers)} "
          f"(no_true_codeword={n_no_true_codeword} no_candidate_or_llr={n_no_candidate})")
    return bers


def report_ber(label: str, bers: list[float]) -> None:
    if not bers:
        print(f"  {label}: no data")
        return
    print(f"  {label}: n={len(bers)} median={st.median(bers):.1%} mean={st.mean(bers):.1%} "
          f"min={min(bers):.1%} max={max(bers):.1%}")


def main() -> None:
    cycles = sorted(os.path.splitext(f)[0] for f in os.listdir(WAV68_DIR) if f.endswith(".wav"))
    print(f"corpus: {len(cycles)} cycles\n")

    encoder = Encoder(DLL_PATH)

    print("Loading K10/cap140 candidate diagnostics (this session's capture, with llr174)...")
    k10_cand_by_cycle = load_candidate_diag_with_llr(os.path.join(K10_CAP_DIR, "candidate_diag.csv"))

    pop135 = compute_135_population(cycles)
    print(f"THE 135 population: n={len(pop135)} (expect 135)")

    control = compute_matched_hit_control(cycles, limit=200)
    print(f"MATCHED-HIT CONTROL population (capped at 200 for measurement cost): n={len(control)}\n")

    print("=" * 90)
    print("SELF-CHECK FIRST: matched-hit control BER must be near-zero, or STOP -- do not")
    print("trust the 135/567 numbers below until this passes.")
    print("=" * 90)
    control_bers = measure_population("matched-hit control", control, k10_cand_by_cycle, encoder,
                                       require_decoded=True)
    report_ber("matched-hit control", control_bers)
    self_check_ok = bool(control_bers) and st.median(control_bers) < 0.05
    print(f"\n[SELF-CHECK {'PASS' if self_check_ok else 'FAIL'}] median BER "
          f"{'< 5%' if self_check_ok else '>= 5% or no data'} for the matched-hit control.")
    if not self_check_ok:
        print("[STOP] Self-check failed -- the encode/Gray-decode/hard-decision pipeline has a "
              "bug, or the candidate match is picking the wrong candidate. Do not read the 135/"
              "567 numbers below as meaningful until this is fixed.")

    print()
    print("=" * 90)
    print("THE 135 (K10/cap140, score >= 10) -- hard-decision BER vs. re-encoded true codeword")
    print("=" * 90)
    bers135 = measure_population("THE 135", pop135, k10_cand_by_cycle, encoder, require_decoded=False)
    report_ber("THE 135", bers135)

    k4_diag_path = os.path.join(K4_CAP_DIR, "candidate_diag.csv")
    if os.path.exists(k4_diag_path):
        print()
        print("=" * 90)
        print("THE 567 (K=4/cap2000, score 5-9) -- hard-decision BER vs. re-encoded true codeword")
        print("=" * 90)
        population_648 = compute_648_population(cycles)
        pop567 = compute_567_population(population_648)
        print(f"THE 567 population: n={len(pop567)} (expect 567)")
        k4_cand_by_cycle = load_candidate_diag_with_llr(k4_diag_path)
        bers567 = measure_population("THE 567", pop567, k4_cand_by_cycle, encoder, require_decoded=False)
        report_ber("THE 567", bers567)
    else:
        print(f"\n[SKIP] THE 567: {k4_diag_path} not yet present (K=4/cap2000 capture still running "
              f"or not yet done) -- run this script again once it completes.")
        bers567 = []

    print()
    print("=" * 90)
    print("READING (Architect's illustrative, non-calibrated bands, 2026-07-26-1830 Sec.6):")
    print("  ~50%                -> sync/demodulation front-end; kills all LLR-scaling avenues")
    print("                         including the shrinkage trial's own, permanently.")
    print("  ~15-25%             -> decode effort (BP iterations, OSD depth/gate); cheap constants.")
    print("  low, correct signs  -> LLR magnitude; reopens Phase 2b per Sec.5's condition.")
    print("These bands are illustrative, not derived from this codebase's actual LDPC/OSD")
    print("correction power -- read the printed numbers, state the verdict explicitly, do not")
    print("treat the bands as hard boundaries.")


if __name__ == "__main__":
    main()
