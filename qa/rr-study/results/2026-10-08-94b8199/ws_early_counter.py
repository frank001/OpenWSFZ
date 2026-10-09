"""Passive WebSocket listener: counts early rows and their resolutions. COUNTS ONLY (HK-037): no message text,
callsign or frequency is read into the output; the frame is parsed in this function and only integers leave it.

Output: one JSON line per frame {utc, kind, early, confirmed, unconfirmed, final}.
Usage: python ws_early_counter.py <out.jsonl> [ws-url]
"""
import asyncio
import datetime
import json
import sys

import websockets


def utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def summarise(raw):
    """Return a counts-only row for a frame, or None. The parsed frame does not leave this function."""
    try:
        m = json.loads(raw)
    except Exception:
        return None
    t = m.get("type")
    if t == "decode-early":
        return {"kind": "early", "early": len(m.get("payload") or []), "confirmed": 0, "unconfirmed": 0, "final": 0}
    if t == "decode":
        res = m.get("resolves") or []
        conf = sum(1 for r in res if r.get("outcome") == "confirmed")
        unc = sum(1 for r in res if r.get("outcome") == "unconfirmed")
        return {"kind": "final", "early": 0, "confirmed": conf, "unconfirmed": unc, "final": len(m.get("payload") or [])}
    return None


async def main(out, url):
    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps({"utc": utc(), "kind": "start", "url": url}) + "\n")
        f.flush()
        while True:
            try:
                async with websockets.connect(url, max_size=None) as ws:
                    async for raw in ws:
                        row = summarise(raw)
                        if row:
                            row["utc"] = utc()
                            f.write(json.dumps(row) + "\n")
                            f.flush()
            except Exception as exc:  # reconnect; a gap is recorded, never hidden
                f.write(json.dumps({"utc": utc(), "kind": "disconnect", "err": type(exc).__name__}) + "\n")
                f.flush()
                await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "ws://127.0.0.1:8080/api/v1/ws"))
