"""GAP-CENSUS-A -- shared parsing, population construction, matching, and stats
helpers. Spec: qa/rr-study/2026-08-23-2113-architect-to-qa-spec-gap-census-a.md.

NFR-021: real off-air callsigns live in `message`/`message_norm` in memory only,
to build match keys and to test for an unresolved-hash marker. Neither field is
ever written to a results JSON, a report, or a log line -- only counts, cycle
timestamps, and frequencies leave this process. `git check-ignore -v` every
artefact under artefacts/ before any commit (it is blanket-gitignored already).

Hazards from the spec's Sec.2.1, applied throughout:
  1. Sort at construction everywhere a set/sample is built (hash-randomised
     set iteration silently breaks seeded determinism).
  2. This module does not use any `limit=`-style truncating helper.
  3. Every count reported downstream is a CLUSTER (cycle) count where the
     statistic is about cycles, and a decode count where it is about decodes --
     never conflated (HK-021(i)).
"""
from __future__ import annotations

import os
import re
from collections import defaultdict

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CORPUS_DIR = os.path.join(REPO_ROOT, "artefacts", "20260803_live_run_1713")
OURS_ALL_TXT = os.path.join(CORPUS_DIR, "owsfz", "ALL.TXT")
THEIRS_ALL_TXT = os.path.join(CORPUS_DIR, "wsjt-x", "ALL.TXT")
OURS_WAV_DIR = os.path.join(CORPUS_DIR, "owsfz", "wav")
THEIRS_WAV_DIR = os.path.join(CORPUS_DIR, "wsjt-x", "wav")

F_MIN_HZ = 200.0  # ft8_shim.c:1278 / :1640, hardcoded -- the aperture floor bucket A censuses
F_MAX_HZ = 3000.0  # both legs produce zero at/above this; out of scope per spec Sec.4
FREQ_TOLERANCE_HZ = 4.0  # matcher.py's own tolerance, pinned not re-derived (spec Sec.5.1)

_HASH_BRACKET_RE = re.compile(r"<[^>]*>")


def has_hash_marker(message: str) -> bool:
    return bool(_HASH_BRACKET_RE.search(message))


def normalise_text(message: str) -> str:
    """Whitespace-only normalisation -- NOT hash-normalisation. The population
    (Sec.2, ROW 0a) is defined on raw distinct (ts, message) keys, matching the
    Architect's own Sec.0.2 basis and the f-nbr-a harness's _decode_result_key
    convention, so B1 (hash-carrying) and B2 (other) stay distinguishable."""
    return " ".join(message.split())


def parse_all_txt(path: str) -> list[dict]:
    """This repo's ALL.TXT writer format (and the real WSJT-X's, which it
    mimics): ts dial Rx MODE snr dt freq message... Reimplemented locally
    (not imported from qa/endurance/anova_common.py) so this arm has no
    dependency on a module whose own docstring is scoped to the ANOVA
    harness; the parsing convention is identical and verified against it in
    tests/test_gap_census_a.py."""
    rows = []
    with open(path, encoding="ascii", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if not line.strip():
                continue
            tok = line.split()
            if len(tok) < 8:
                continue
            try:
                snr = float(tok[4])
                dt = float(tok[5])
                freq_hz = float(tok[6])
            except ValueError:
                continue
            message = " ".join(tok[7:])
            rows.append({
                "ts": tok[0],
                "snr": snr,
                "dt": dt,
                "freq_hz": freq_hz,
                "message_norm": normalise_text(message),
                "has_hash": has_hash_marker(message),
            })
    return rows


class Population:
    """The corpus, parsed once. All raw message text is discarded immediately
    after `message_norm`/`has_hash` are derived -- neither this class nor
    anything downstream retains the original string."""

    def __init__(self, ours_rows: list[dict], theirs_rows: list[dict]):
        self.ours_rows = ours_rows
        self.theirs_rows = theirs_rows

        self.ours_by_cycle: dict[str, list[dict]] = defaultdict(list)
        for r in ours_rows:
            self.ours_by_cycle[r["ts"]].append(r)
        self.theirs_by_cycle: dict[str, list[dict]] = defaultdict(list)
        for r in theirs_rows:
            self.theirs_by_cycle[r["ts"]].append(r)

        self.ours_key_set = {(r["ts"], r["message_norm"]) for r in ours_rows}
        self.theirs_key_set = {(r["ts"], r["message_norm"]) for r in theirs_rows}
        self.both_key_set = self.ours_key_set & self.theirs_key_set
        self.theirs_only_key_set = self.theirs_key_set - self.ours_key_set

        # sort at construction (hazard 1) -- everything downstream iterates
        # this list, never the raw set, so iteration order is fixed.
        self.theirs_only_keys = sorted(self.theirs_only_key_set)

        # representative freq_hz/snr per theirs-only key (first occurrence,
        # sorted rows) + a spread diagnostic in case a key ever appears at >1
        # freq (duplicate emission was measured at zero on this corpus, but
        # checked here rather than assumed).
        rep_freq: dict[tuple, float] = {}
        rep_snr: dict[tuple, float] = {}
        freq_spread: dict[tuple, set] = defaultdict(set)
        for r in sorted(theirs_rows, key=lambda r: (r["ts"], r["message_norm"], r["freq_hz"])):
            key = (r["ts"], r["message_norm"])
            if key in self.theirs_only_key_set:
                freq_spread[key].add(r["freq_hz"])
                if key not in rep_freq:
                    rep_freq[key] = r["freq_hz"]
                    rep_snr[key] = r["snr"]
        self.theirs_only_rep_freq = rep_freq
        self.theirs_only_rep_snr = rep_snr
        self.theirs_only_freq_spread_keys = sorted(k for k, v in freq_spread.items() if len(v) > 1)

    @property
    def n_ours(self) -> int:
        return len(self.ours_rows)

    @property
    def n_theirs(self) -> int:
        return len(self.theirs_rows)

    @property
    def n_theirs_only(self) -> int:
        return len(self.theirs_only_key_set)

    def d001_pct(self) -> float:
        return 100.0 * self.n_theirs_only / self.n_theirs

    def pp_of_d001(self, count: int) -> float:
        """count / theirs_total * 100 -- the normalisation the spec's Sec.0.2
        table uses (buckets sum to the whole D-001 percentage, not to 100% of
        theirs-only)."""
        return 100.0 * count / self.n_theirs


def load_population() -> Population:
    ours_rows = parse_all_txt(OURS_ALL_TXT)
    theirs_rows = parse_all_txt(THEIRS_ALL_TXT)
    return Population(ours_rows, theirs_rows)


def cluster_bootstrap_ci(cycle_values: dict[str, float], n_boot: int = 2000,
                          seed: int = 20260823, alpha: float = 0.05) -> tuple[float, float, float]:
    """Cluster (by-cycle) bootstrap CI for the SUM of a per-cycle statistic.
    Resamples cycle labels with replacement, n_boot times, seeded. Returns
    (point_estimate, lo, hi) at the given alpha (default 95%)."""
    import random
    cycles = sorted(cycle_values.keys())  # sort at construction (hazard 1)
    n = len(cycles)
    point = sum(cycle_values.values())
    if n == 0:
        return point, point, point
    rng = random.Random(seed)
    values = [cycle_values[c] for c in cycles]
    boot_sums = []
    for _ in range(n_boot):
        s = 0.0
        for _ in range(n):
            s += values[rng.randrange(n)]
        boot_sums.append(s)
    boot_sums.sort()
    lo_idx = int((alpha / 2) * n_boot)
    hi_idx = int((1 - alpha / 2) * n_boot) - 1
    hi_idx = min(hi_idx, n_boot - 1)
    return point, boot_sums[lo_idx], boot_sums[hi_idx]
