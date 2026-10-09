"""Passive WebSocket listener that CLASSIFIES unconfirmed early rows. HK-037: message text is read ONLY inside
`Tracker`; what leaves it is a label and integers (frequency differences in Hz). No text, callsign or per-row
message is written.

For each early row the final decode did not confirm (outcome "unconfirmed"), the row is compared with
  * this cycle's final rows (the batch-1 `decode` frame that carries the resolution), and
  * the previous cycle's final rows.
Matching: whitespace-normalised message text; the daemon's own tolerance for "same signal" is 10 Hz
(`EarlyDecodeMatcher.MaxFrequencyDeltaHz`).

Labels (exclusive, tested in this order):
  ECHO_PREV   : same text as a previous-cycle final row within 10 Hz of it AND no same-text final row in this cycle
                within 10 Hz  -> the early row looks like the previous slot's signal.
  FREQ_MISS   : a same-text final row exists in this cycle, but farther than 10 Hz (matcher tolerance) and the row is
                not ECHO_PREV.
  PREV_AND_THIS_FAR : same text in the previous cycle within 10 Hz AND in this cycle farther than 10 Hz (a special
                case of ECHO_PREV where the signal also moved); counted under ECHO_PREV, listed separately as a flag.
  NO_MATCH    : the text is in neither this cycle's finals nor the previous cycle's.
  TEXT_PREV_OTHER_FREQ : same text in previous cycle's finals, but more than 10 Hz away, none in this cycle.

Output: one JSON line per decode frame {utc, kind:'cycle', early_unconfirmed, labels:{...}, df_this:[ints], df_prev:[ints]}
and the same counts for early/confirmed rows. Usage: python ws_early_classify.py <out.jsonl> [ws-url]
"""
import asyncio
import datetime
import json
import sys

import websockets

TOL_HZ = 10


def utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def g(d, *names):
    for n in names:
        if isinstance(d, dict) and n in d:
            return d[n]
    return None


def norm(t):
    return " ".join(str(t or "").split())


class Tracker:
    """Holds message text. Nothing it returns contains text."""

    def __init__(self):
        self.early = {}        # earlyId -> (text, freq)
        self.prev_final = []   # [(text, freq)]

    def on_early(self, m):
        for it in m.get("payload") or []:
            d = g(it, "decode", "Decode") or {}
            eid = g(it, "earlyId", "EarlyId")
            if eid is None:
                continue
            self.early[eid] = (norm(g(d, "message", "Message")), g(d, "freqHz", "FreqHz"))
        return {"kind": "early", "early": len(m.get("payload") or [])}

    def on_final(self, m):
        cur = [(norm(g(r, "message", "Message")), g(r, "freqHz", "FreqHz")) for r in (m.get("payload") or [])]
        res = m.get("resolves") or []
        labels = {"ECHO_PREV": 0, "FREQ_MISS": 0, "TEXT_PREV_OTHER_FREQ": 0, "NO_MATCH": 0}
        df_this, df_prev, both = [], [], 0
        conf = unc = miss = 0
        for r in res:
            eid = g(r, "earlyId", "EarlyId")
            out = g(r, "outcome", "Outcome")
            row = self.early.pop(eid, None)
            if out == "confirmed":
                conf += 1
                continue
            unc += 1
            if row is None or row[1] is None:
                miss += 1
                continue
            text, f = row
            this_same = [abs(f - ff) for t, ff in cur if t == text and ff is not None]
            prev_same = [abs(f - ff) for t, ff in self.prev_final if t == text and ff is not None]
            this_near = any(x <= TOL_HZ for x in this_same)
            prev_near = any(x <= TOL_HZ for x in prev_same)
            if this_same:
                df_this.append(min(this_same))
            if prev_same:
                df_prev.append(min(prev_same))
            if prev_near and not this_near:
                labels["ECHO_PREV"] += 1
                if this_same:
                    both += 1
            elif this_same and not this_near:
                labels["FREQ_MISS"] += 1
            elif prev_same and not prev_near:
                labels["TEXT_PREV_OTHER_FREQ"] += 1
            else:
                labels["NO_MATCH"] += 1
        self.prev_final = cur
        self.early.clear()
        return {"kind": "cycle", "final": len(cur), "confirmed": conf, "unconfirmed": unc, "lookup_miss": miss, "labels": labels,
                "echo_with_same_text_also_far_in_this_cycle": both,
                "df_this_hz": sorted(df_this), "df_prev_hz": sorted(df_prev)}


def summarise(tr, raw):
    try:
        m = json.loads(raw)
    except Exception:
        return None
    t = m.get("type")
    if t == "decode-early":
        return tr.on_early(m)
    if t == "decode":
        return tr.on_final(m)
    return None


async def main(out, url):
    tr = Tracker()
    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps({"utc": utc(), "kind": "start", "url": url}) + "\n")
        f.flush()
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
                f.write(json.dumps({"utc": utc(), "kind": "disconnect", "err": type(exc).__name__}) + "\n")
                f.flush()
                await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "ws://127.0.0.1:8080/api/v1/ws"))
