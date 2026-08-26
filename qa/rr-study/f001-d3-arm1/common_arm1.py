"""F-001 D3 ARM 1 -- offline hash-table policy simulation. Shared helpers.

Spec: qa/rr-study/2026-08-26-1149-architect-to-qa-spec-f001-d3-arm1-policy-simulation.md

Sec.1's predicates are shipped as code (HK-021(r)) -- n22_of/h10_of/n12_of/n10_of
below are transcribed character-for-character against the spec's own listing.
The plaintext-token predicate (`is_callsign_token`) and the B1-cap population
machinery (classify_b1 / key_and_callsign_buckets / build_t_plain_index) are
IMPORTED from common_b1.py / run_b1_coverage_a.py, never re-implemented
(Sec.4 ROW 0d; HK-018).

NFR-021: real callsign strings live in memory only, inside SimTable entries
and the event stream built here. Nothing that reaches result.json or the
report is anything but counts, cycle timestamps, and sha256[:6]-redacted
CS-xxxxxx tokens (common_b1.redact).
"""
from __future__ import annotations

import os
import re
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
B1_DIR = os.path.join(REPO_ROOT, "qa", "rr-study", "b1-coverage-a")
G2A_DIR = os.path.join(REPO_ROOT, "qa", "rr-study", "g2a-remeasure-a")
GAP_CENSUS_A_DIR = os.path.join(REPO_ROOT, "qa", "rr-study", "gap-census-a")
sys.path.insert(0, B1_DIR)
sys.path.insert(0, G2A_DIR)
sys.path.insert(0, GAP_CENSUS_A_DIR)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common_b1 as B            # noqa: E402
import common_g2a as G           # noqa: E402
import run_b1_coverage_a as RB   # noqa: E402  (classify_b1 / key_and_callsign_buckets -- imported, not re-implemented)

OURS_WAV_DIR = G.OURS_WAV_DIR
EXPECTED_N_WAVS = 4971

# ---- Sec.1 item 1: the FT8 hash, ported from message.c:557-590 ------------
FT8_CHARSET = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ/"   # text.h:59, 38 chars


def n22_of(callsign: str):
    """Returns the 22-bit hash, or None if the callsign leaves the charset
    (message.c returns false -> 'hash error (wrong character set)')."""
    n58 = 0
    for i in range(11):                       # 11 chars, space-padded (j = 0)
        if i < len(callsign):
            j = FT8_CHARSET.find(callsign[i])
            if j < 0:
                return None
        else:
            j = 0
        n58 = (38 * n58 + j) & 0xFFFFFFFFFFFFFFFF   # C uint64_t WRAPS -- keep the mask
    return ((47055833459 * n58) >> (64 - 22)) & 0x3FFFFF


def h10_of(n22): return (n22 >> 12) & 0x3FF          # first-probe key, all hash types
def n12_of(n22): return n22 >> 10
def n10_of(n22): return n22 >> 12


# ---- hash-slot text shape (message.c's add_brackets convention) -----------
_RESOLVED_HASH_RE = re.compile(r"^<[^>]*>$")
_UNRESOLVED_HASH_RE = re.compile(r"^<\.*>$")   # == common_b1.HASH_SLOT_RE


def hash_field_in(message_norm: str):
    """Returns ('unresolved', None) for the literal <...> marker, ('resolved',
    raw_bracket_text) for any other bracket-wrapped hash-type token, or
    (None, None) if the message carries no hash-type field. By construction
    of these message types (Sec.0 item 6 / message.c:400-458,732-841) at most
    one hash-type field appears per message."""
    for t in message_norm.split():
        if _UNRESOLVED_HASH_RE.fullmatch(t):
            return ("unresolved", None)
        if _RESOLVED_HASH_RE.fullmatch(t):
            return ("resolved", t[1:-1])
    return (None, None)


# ---- Sec.2: cycle index (for ROW 0b's freeze-cycle readout) ---------------

def load_cycle_index():
    """The corpus's full 4,971-cycle timeline, chronological because the wav
    filenames ARE the ts strings (YYMMDD_HHMMSS, fixed width, lexicographic
    == chronological). Returns (sorted_ts_list, {ts: index})."""
    names = sorted(f[:-4] for f in os.listdir(OURS_WAV_DIR) if f.endswith(".wav"))
    if len(names) != EXPECTED_N_WAVS:
        raise AssertionError("wav corpus count drifted: %d != %d" % (len(names), EXPECTED_N_WAVS))
    return names, {ts: i for i, ts in enumerate(names)}


# ---- Sec.3: the simulator --------------------------------------------------
#
# Faithful transcription of ft8_shim.c:637-700 (hash_table_add / hash_table_lookup),
# generalised per Sec.0 fact 3 / Sec.3.1 to support eviction with tombstones.
#
# Hash-type note (disclosed in the report, HK-021 Sec.6): every lookup in this
# arm uses the 22-bit (sh=0) form. hash10 is DEFINED in message.h but never
# actually invoked anywhere in this tree (grep-verified); the remaining choice
# is 22-bit (unpack28's non-standard-callsign branch, message.c:781) vs 12-bit
# (decode_nonstd's call_3, message.c:431) and the two are NOT reliably
# distinguishable from decoded text alone -- both render as an outwardly
# identical "CALL CALL REPORT"-shaped message with one bracketed slot. Per the
# spec's own contingency ("fall back to 22-bit and COUNT how many lookups took
# the fallback... report it as a stated limitation of the false-resolution
# figure; it does not affect Sec.5.1"), this arm falls back to 22-bit for
# 100% of lookups and reports that count. Consequence: Sec.5.1 (residency,
# arrival-order only, bit-width-independent) is unaffected; Sec.5.2's `false`
# count only ever measures genuine full n22 collisions (ROW 0c's ~32-event
# birthday population), never the 12-bit truncated-bit collisions Sec.0 fact 4
# warns about -- consistent with ROW 0b's own note that the probe/truncation
# path is the least-validated part of this arm.

EMPTY, TOMBSTONE, OCCUPIED = 0, 1, 2


class SimTable:
    def __init__(self, size: int, policy: str | None = None):
        self.n = size
        self.policy = policy  # None (fill-and-freeze) | "LRU" | "LFU"
        self.state = [EMPTY] * size
        self.callsign = [None] * size
        self.hash = [0] * size
        self.last_used = [0] * size
        self.freq = [0] * size
        self.count = 0            # active OCCUPIED entries
        self.reject_count = 0
        self.clock = 0

    def _start_idx(self, n22: int) -> int:
        h10 = (n22 >> 12) & 0x3FF
        return (h10 * 23) % self.n

    def lookup(self, n22: int):
        """ft8_shim.c:637-655's hash_table_lookup, sh=0 (22-bit). Breaks at
        the first EMPTY slot; TOMBSTONE and non-matching OCCUPIED slots do
        not stop the scan (Sec.0 fact 3)."""
        idx = self._start_idx(n22)
        for _ in range(self.n):
            st = self.state[idx]
            if st == EMPTY:
                return None
            if st == OCCUPIED and self.hash[idx] == n22:
                self.clock += 1
                self.last_used[idx] = self.clock
                self.freq[idx] += 1
                return self.callsign[idx]
            idx = (idx + 1) % self.n
        return None

    def _select_victim(self):
        occ = [i for i in range(self.n) if self.state[i] == OCCUPIED]
        if not occ:
            return None
        if self.policy == "LRU":
            return min(occ, key=lambda i: (self.last_used[i], i))
        if self.policy == "LFU":
            return min(occ, key=lambda i: (self.freq[i], self.last_used[i], i))
        return None

    def add(self, callsign: str, n22: int):
        """ft8_shim.c:667-700's hash_table_add: duplicate-scan first (D-012),
        reject a genuinely new callsign only when there is no room. Eviction
        (LRU/LFU) replaces a victim slot with the new entry in the same call
        -- see common_arm1.py's module docstring for why this is provably
        equivalent to a fresh probe-scan for the new entry once the table has
        saturated (every slot is within `n` probe-steps of every other)."""
        self.clock += 1
        idx = self._start_idx(n22)
        first_free = None
        for _ in range(self.n):
            st = self.state[idx]
            if st == EMPTY:
                if first_free is None:
                    first_free = idx
                break
            if st == TOMBSTONE:
                if first_free is None:
                    first_free = idx
            elif self.hash[idx] == n22 and self.callsign[idx] == callsign:
                self.last_used[idx] = self.clock
                self.freq[idx] += 1
                return  # already known -- no-op, NOT a reject (D-012)
            idx = (idx + 1) % self.n

        if first_free is None:
            # Full n-step scan found no EMPTY/TOMBSTONE anywhere -> every slot
            # is OCCUPIED -> count == n exactly (the scan covers the whole
            # table, wraparound included).
            if self.policy is None:
                self.reject_count += 1
                return
            victim = self._select_victim()
            if victim is None:
                self.reject_count += 1
                return
            self.state[victim] = TOMBSTONE
            self.callsign[victim] = None
            self.count -= 1
            first_free = victim

        self.state[first_free] = OCCUPIED
        self.callsign[first_free] = callsign
        self.hash[first_free] = n22
        self.last_used[first_free] = self.clock
        self.freq[first_free] = 1
        self.count += 1


# ---- population plumbing (imported orchestration, not re-implemented) -----

def load_l2run1_ours_rows():
    dump = G.load_decode_dump(G.L2_RUN1_JSON)
    return dump, G.rows_from_dump_corrected(dump)


def load_l2run2_ours_rows():
    dump = G.load_decode_dump(G.L2_RUN2_JSON)
    return dump, G.rows_from_dump_corrected(dump)


def load_l1_ours_rows():
    dump = G.load_decode_dump(G.L1_JSON)
    return dump, G.rows_from_dump_corrected(dump)


def build_b1cap_population(ours_rows_corrected, theirs_rows):
    """Reruns B1-COVERAGE-A's own classifier (imported) to name the 40
    CS-cap callsigns and their 307 B1-cap decode keys. Returns:
      per_key      -- {key: info} from run_b1_coverage_a.classify_b1
      b1cap_keys   -- sorted list of B1 keys whose key_bucket is "B1-cap"
      t_plain      -- session-wide plaintext-emission index
      cs_cap       -- sorted list of the 40 real callsign strings (CS-cap)
    """
    bucket_of, n_theirs_only, b1_keys, per_key = RB.classify_b1(ours_rows_corrected, theirs_rows)
    t_plain = B.build_t_plain_index(ours_rows_corrected)
    key_bucket, callsign_keys, cs_bucket = RB.key_and_callsign_buckets(
        b1_keys, per_key, t_plain, B.FREEZE_CYCLE_TS)
    b1cap_keys = sorted(k for k in b1_keys if key_bucket[k] == "B1-cap")
    cs_cap = sorted(x for x, b in cs_bucket.items() if b == "CS-cap")
    return {
        "per_key": per_key, "key_bucket": key_bucket, "b1_keys": b1_keys,
        "t_plain": t_plain, "cs_cap": cs_cap, "cs_bucket": cs_bucket,
        "callsign_keys": callsign_keys, "b1cap_keys": b1cap_keys,
    }


def locate_lfail_rows(ours_rows_corrected, theirs_rows, pop_info):
    """For each B1-cap key, find the SPECIFIC ours decode row (object
    identity, from `ours_rows_corrected`) that carries the failed lookup --
    the same candidate-search Sec.2.2/2.4 already runs inside classify_b1,
    reapplied only far enough to recover the row reference itself (classify_b1
    does not return it). Returns {id(row): named_callsign} for exactly the
    307 B1-cap rows."""
    pop = G.gc.Population(ours_rows_corrected, theirs_rows)
    ours_by_cycle = RB.build_ours_by_cycle(ours_rows_corrected)
    per_key = pop_info["per_key"]
    out = {}
    missing = []
    for key in pop_info["b1cap_keys"]:
        ts, r_norm = key
        r_tokens = r_norm.split()
        rep_freq = pop.theirs_only_rep_freq[key]
        named = per_key[key]["named"]
        candidates = [r for r in ours_by_cycle.get(ts, [])
                      if r["has_hash"] and abs(r["freq_hz"] - rep_freq) <= 4.0]
        chosen = None
        for c in candidates:
            pos = B.template_match(c["message_norm"].split(), r_tokens)
            if pos is None:
                continue
            tok = B.strip_enclosing_brackets(r_tokens[pos])
            if B.is_callsign_token(tok) and tok == named:
                chosen = c
                break
        if chosen is None:
            missing.append(key)
            continue
        out[id(chosen)] = named
    return out, missing
