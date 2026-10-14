"""EARLY-DUP Part A1 listener, classifier v2 (spec 2026-10-09-1025-architect-to-qa-spec-early-dup.md, amendment 1).

A passive WebSocket listener on /api/v1/ws. HK-037: message text is read ONLY inside `Tracker` and `classify_row`; everything that leaves them is a label, a boolean or an integer
(Hz). The listener BUFFERS each cycle's unconfirmed early rows and final rows (text and frequency, in memory only) until it is told to FINALIZE, because the play's own truth.csv
(the S4 cycle starts) does not exist until the play is over: when the file given by --finalize-file appears, it holds the path of the play's truth.csv; the listener reads it
(inside this module), classifies every buffered cycle against that cycle's truth, writes counts and Hz only, and exits.

Per unconfirmed early row (labels v1, kept): ECHO_PREV / FREQ_MISS / TEXT_PREV_OTHER_FREQ / NO_MATCH, with the matcher's own 10 Hz tolerance, PLUS:
  DUP              : the early row's text occurs >= 2 times in this cycle's S4 truth;
  E_ON_COPY        : the early row's frequency is within 10 Hz of one truth copy of its text;
  F_ON_OTHER_COPY  : a same-text final row of this cycle lies within 10 Hz of a DIFFERENT truth copy than the one the early row is on.
Per cycle: unconfirmed, confirmed, lookup_miss (a resolution whose early row was never seen: must be 0), whether a final (decode) frame arrived.

  python ws_early_classify_v2.py <out.jsonl> --finalize-file <path> [--url ws://127.0.0.1:8080/api/v1/ws]
"""
import asyncio
import csv
import datetime
import json
import os
import sys

import websockets

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import early_dup_a0 as A0  # noqa: E402  (cycle_of: frame time -> truth cycle)

TOL_HZ = 10     # EarlyDecodeMatcher.MaxFrequencyDeltaHz


def utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def g(d, *names):
    for n in names:
        if isinstance(d, dict) and n in d:
            return d[n]
    return None


def norm(t):
    return " ".join(str(t or "").split())


def _nearest(f, copies):
    """index of the truth copy nearest f within TOL_HZ, or None."""
    best = min(((abs(f - c), i) for i, c in enumerate(copies)), default=None)
    return best[1] if best and best[0] <= TOL_HZ else None


def classify_row(text, f, finals, prev_finals, truth_cycle):
    """One unconfirmed early row -> {label, DUP, E_ON_COPY, F_ON_OTHER_COPY, df_this_hz, df_copy_hz}. Pure (tested); text stays inside.
    finals / prev_finals: [(text, freq)]; truth_cycle: [(text, freq)] of this cycle."""
    this_same = [abs(f - ff) for t, ff in finals if t == text]
    prev_same = [abs(f - ff) for t, ff in prev_finals if t == text]
    this_near, prev_near = any(x <= TOL_HZ for x in this_same), any(x <= TOL_HZ for x in prev_same)
    if prev_near and not this_near:
        label = "ECHO_PREV"
    elif this_same and not this_near:
        label = "FREQ_MISS"
    elif prev_same and not prev_near:
        label = "TEXT_PREV_OTHER_FREQ"
    else:
        label = "NO_MATCH"
    copies = [c for t, c in truth_cycle if t == text]
    e_idx = _nearest(f, copies)
    f_idx = {_nearest(ff, copies) for t, ff in finals if t == text} - {None}
    return {"label": label, "DUP": len(copies) >= 2, "E_ON_COPY": e_idx is not None,
            "F_ON_OTHER_COPY": bool(f_idx - ({e_idx} if e_idx is not None else set())),
            "df_this_hz": int(round(min(this_same))) if this_same else None,
            "df_copy_hz": int(round(min(abs(f - c) for c in copies))) if copies else None}


class Tracker:
    """Buffers text in memory; nothing it returns contains text."""

    def __init__(self):
        self.early = {}      # earlyId -> (text, freq)
        self.cycles = []     # [{utc, unconf: [(text,f)], finals: [(text,f)], confirmed, lookup_miss}]

    def on_early(self, m):
        for it in m.get("payload") or []:
            d = g(it, "decode", "Decode") or {}
            eid = g(it, "earlyId", "EarlyId")
            if eid is not None:
                self.early[eid] = (norm(g(d, "message", "Message")), g(d, "freqHz", "FreqHz"))
        return {"kind": "early", "early": len(m.get("payload") or [])}

    def on_final(self, m, now):
        finals = [(norm(g(r, "message", "Message")), g(r, "freqHz", "FreqHz")) for r in (m.get("payload") or [])]
        unconf, conf, miss = [], 0, 0
        for r in m.get("resolves") or []:
            row = self.early.pop(g(r, "earlyId", "EarlyId"), None)
            out = g(r, "outcome", "Outcome")
            if out == "confirmed":
                conf += 1
            elif row is None or row[1] is None:
                miss += 1
            else:
                unconf.append(row)
        self.early.clear()
        self.cycles.append({"utc": now, "unconf": unconf, "finals": finals, "confirmed": conf, "lookup_miss": miss})
        return {"kind": "frame", "final": len(finals), "unconfirmed": len(unconf), "confirmed": conf}

    def finalize(self, truth_rows, disconnects=0):
        """truth_rows: dict rows of the play's truth.csv. -> list of per-cycle records (counts and Hz only)."""
        tr = {}
        for r in truth_rows:
            if r["scenario_id"] == "S4":
                tr.setdefault(r["cycle_utc"], []).append((norm(r["message_text"]), float(r["true_freq_hz"])))
        starts = set(tr)
        by_cycle, prev_finals = {}, []
        for rec in self.cycles:
            c = A0.cycle_of(rec["utc"], starts)
            if c is None:
                prev_finals = rec["finals"]
                continue
            rows = [classify_row(t, f, rec["finals"], prev_finals, tr[c]) for t, f in rec["unconf"]]
            by_cycle[c] = {"cycle_utc": c, "final_frame": True, "unconfirmed": len(rows), "confirmed": rec["confirmed"], "lookup_miss": rec["lookup_miss"], "rows": rows,
                           "repeated_text_in_truth": max([sum(1 for t2, _ in tr[c] if t2 == t) for t, _ in tr[c]] or [1]) >= 2}
            prev_finals = rec["finals"]
        out = []
        for c in sorted(starts):
            out.append(by_cycle.get(c, {"cycle_utc": c, "final_frame": False, "unconfirmed": 0, "confirmed": 0, "lookup_miss": 0, "rows": [],
                                        "repeated_text_in_truth": max(sum(1 for t2, _ in tr[c] if t2 == t) for t, _ in tr[c]) >= 2}))
        return out


def summarise(tr, raw):
    try:
        m = json.loads(raw)
    except Exception:
        return None
    t = m.get("type")
    if t == "decode-early":
        return tr.on_early(m)
    if t == "decode":
        return tr.on_final(m, utc())
    return None


async def main(out, finalize_file, url):
    tr = Tracker()
    disconnects = 0
    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps({"utc": utc(), "kind": "start", "url": url}) + "\n")
        f.flush()

        async def listen():
            nonlocal disconnects
            while True:
                try:
                    async with websockets.connect(url, max_size=None) as ws:
                        async for raw in ws:
                            row = summarise(tr, raw)
                            if row:
                                row["utc"] = utc()
                                f.write(json.dumps(row) + "\n")
                                f.flush()
                except Exception as exc:
                    disconnects += 1
                    f.write(json.dumps({"utc": utc(), "kind": "disconnect", "err": type(exc).__name__}) + "\n")
                    f.flush()
                    await asyncio.sleep(3)

        task = asyncio.ensure_future(listen())
        while not os.path.exists(finalize_file):
            await asyncio.sleep(2)
        truth_path = open(finalize_file, encoding="utf-8").read().strip()
        for cyc in tr.finalize(csv.DictReader(open(truth_path, encoding="utf-8"))):
            cyc["kind"] = "cycle_v2"
            f.write(json.dumps(cyc) + "\n")
        f.write(json.dumps({"utc": utc(), "kind": "finalized", "disconnects_total": disconnects}) + "\n")
        f.flush()
        task.cancel()


if __name__ == "__main__":
    args = sys.argv[1:]
    fin = args[args.index("--finalize-file") + 1]
    url = args[args.index("--url") + 1] if "--url" in args else "ws://127.0.0.1:8080/api/v1/ws"
    asyncio.run(main(args[0], fin, url))
