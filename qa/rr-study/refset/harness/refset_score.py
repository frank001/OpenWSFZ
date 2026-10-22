"""REFERENCE-SET scoring (QA). Reads the per-block WORKING files written by the replay harness (text allowed there only: HK-037 amended
2026-10-10, scratch outside git, read by code only) and the corpus ALL.TXT files, and returns AGGREGATES ONLY. Message text never leaves
this module: no function returns, prints or logs a text, and the counters carry none.

Matching rule (spec section 4, sm_01): key = (cycle, text with every <...> bracket collapsed to <HASH>), paired in order per key, verbatim.
The row-level port of the W-pilot harness's ScoreCycle (same counters, same self-test cases) so RS-V2 and the pilot read alike.
"""
from __future__ import annotations

import dataclasses
import json
import os
import re
from collections import defaultdict
from typing import Dict, Iterable, List, Sequence

_HASH_RE = re.compile(r"<[^>]*>")
_WS_RE = re.compile(r"\s+")


def norm(s: str) -> str:
    return " ".join(_WS_RE.split(s.strip()))


def key_of(text: str) -> str:
    return _HASH_RE.sub("<HASH>", norm(text))


def is_hashed(text: str) -> bool:
    return "<" in text


def has_dots(text: str) -> bool:
    return "<...>" in text


@dataclasses.dataclass
class Counts:
    live_rows: int = 0
    live_non_hashed: int = 0
    live_hashed: int = 0
    repro_all: int = 0
    repro_non_hashed: int = 0
    repro_hashed_key: int = 0
    repro_hashed_exact: int = 0
    own_rows: int = 0
    extra_all: int = 0
    extra_non_hashed: int = 0
    extra_hashed_key: int = 0
    render_live_resolved_own_dots: int = 0
    render_live_dots_own_resolved: int = 0
    render_both_resolved_different: int = 0
    live_hashed_dots: int = 0

    def add(self, other: "Counts") -> None:
        for f in dataclasses.fields(self):
            setattr(self, f.name, getattr(self, f.name) + getattr(other, f.name))


def _by_key(texts: Iterable[str]) -> Dict[str, List[str]]:
    d: Dict[str, List[str]] = defaultdict(list)
    for t in texts:
        n = norm(t)
        d[key_of(n)].append(n)
    return d


def score_cycle(live: Sequence[str], own: Sequence[str]) -> Counts:
    """One cycle: 'live' = the reference rows (live OpenWSFZ output for RS-V2), 'own' = the replay's rows."""
    c = Counts()
    L, O = _by_key(live), _by_key(own)
    for t in live:
        c.live_rows += 1
        if is_hashed(t):
            c.live_hashed += 1
            if has_dots(t):
                c.live_hashed_dots += 1
        else:
            c.live_non_hashed += 1
    c.own_rows += len(own)
    for key, lt in L.items():
        ot = O.get(key, [])
        n = min(len(lt), len(ot))
        hashed = "<HASH>" in key
        c.repro_all += n
        if hashed:
            c.repro_hashed_key += n
        else:
            c.repro_non_hashed += n
        if hashed and n > 0:
            pool: Dict[str, int] = defaultdict(int)
            for t in ot:
                pool[t] += 1
            left_live: List[str] = []
            exact = 0
            for t in lt:
                if pool.get(t, 0) > 0:
                    pool[t] -= 1
                    exact += 1
                else:
                    left_live.append(t)
            left_own = [t for t, k in pool.items() for _ in range(k)]
            c.repro_hashed_exact += exact
            for i in range(min(len(left_live), len(left_own))):
                ld, od = has_dots(left_live[i]), has_dots(left_own[i])
                if not ld and od:
                    c.render_live_resolved_own_dots += 1
                elif ld and not od:
                    c.render_live_dots_own_resolved += 1
                else:
                    c.render_both_resolved_different += 1
    for key, ot in O.items():
        extra = len(ot) - min(len(ot), len(L.get(key, [])))
        c.extra_all += extra
        if "<HASH>" in key:
            c.extra_hashed_key += extra
        else:
            c.extra_non_hashed += extra
    return c


# ------------------------------------------------------------------ readers (text stays inside these)
def read_all_txt(path: str, stamps: Iterable[str]) -> Dict[str, List[str]]:
    """ALL.TXT (OpenWSFZ or WSJT-X; same column layout: stamp, dial, Rx, FT8, snr, dt, freq, text...) -> {stamp: [text]} for 'stamps'."""
    want = set(stamps)
    out: Dict[str, List[str]] = {s: [] for s in want}
    with open(path, "r", encoding="ascii", errors="replace") as fh:
        for line in fh:
            t = line.split()
            if len(t) < 8 or t[0] not in want:
                continue
            out[t[0]].append(" ".join(t[7:]))
    return out


def read_work(path: str) -> Dict[str, List[str]]:
    """Per-block working file -> {stamp: [text]}. (snr/dt/freq columns are read by the legs that need them.)"""
    out: Dict[str, List[str]] = defaultdict(list)
    with open(path, "r", encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            parts = line.rstrip("\n").split("\t", 4)
            if len(parts) == 5:
                out[parts[0]].append(parts[4])
    return out


def score_block(live_by_cycle: Dict[str, List[str]], own_by_cycle: Dict[str, List[str]], scored: Sequence[str]) -> Dict[str, object]:
    """Aggregate over the scored cycles; also the per-cycle equality and |diff| of row counts (SM-V2's side-by-side read)."""
    tot = Counts()
    equal = 0
    sum_abs = 0
    per_cycle = []
    for s in scored:
        live, own = live_by_cycle.get(s, []), own_by_cycle.get(s, [])
        c = score_cycle(live, own)
        tot.add(c)
        d = abs(len(live) - len(own))
        equal += 1 if d == 0 else 0
        sum_abs += d
        per_cycle.append((s, c))
    return {"counts": dataclasses.asdict(tot), "cycles": len(scored), "cycles_equal_rowcount": equal, "sum_abs_rowdiff": sum_abs, "_per_cycle": per_cycle}


def rsv2_shares(counts: Dict[str, int]) -> Dict[str, float]:
    """RS-V2 as 2l item 2 states it: share of the live NON-HASHED rows reproduced, and extra non-hashed rows as a share of the live non-hashed rows.
    The all-rows-by-key shares (SM-V2's definition, hashed rows matched on the collapsed key) are reported beside them."""
    ln, la = counts["live_non_hashed"], counts["live_rows"]
    return {
        "repro_nonhashed_share": counts["repro_non_hashed"] / ln if ln else float("nan"),
        "extra_nonhashed_share": counts["extra_non_hashed"] / ln if ln else float("nan"),
        "repro_all_share_by_key": counts["repro_all"] / la if la else float("nan"),
        "extra_all_share_by_key": counts["extra_all"] / la if la else float("nan"),
    }


def cluster_bootstrap_share(num_by_cycle: Sequence[int], den_by_cycle: Sequence[int], n_boot: int = 2000, seed: int = 20261011) -> List[float]:
    """Cycle-clustered percentile CI [2.5, 97.5] of sum(num)/sum(den) (the cycle is the cluster)."""
    import numpy as np
    num, den = np.asarray(num_by_cycle, float), np.asarray(den_by_cycle, float)
    rng = np.random.default_rng(seed)
    n = len(num)
    idx = rng.integers(0, n, size=(n_boot, n))
    d = den[idx].sum(axis=1)
    ratio = np.where(d > 0, num[idx].sum(axis=1) / np.where(d > 0, d, 1), np.nan)
    lo, hi = np.nanpercentile(ratio, [2.5, 97.5])
    return [float(lo), float(hi)]


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def block_scored_stamps(block: Dict[str, object]) -> List[str]:
    cycles = block["cycles"]
    return list(cycles[int(block["warmup_cycles"]):])


def dump_json(path: str, obj) -> None:
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True)
    os.replace(tmp, path)
