"""Fetch, for later analysis, the reception reports PSK Reporter holds for OUR uploads during an endurance run.

Why: the daemon log records only per-datagram COUNTS ("28 record(s); excluded ... template=2"); the individual spots it sent are not written anywhere,
and the gatherer does not fetch the PSK side. PSK Reporter's public retrieve API returns the reports it stored for a receiver callsign (we are the
RECEIVER of every spot we upload), so this script polls it, de-duplicates, and appends the new reports to <corpus>/psk_reports.jsonl.
Politeness: one query per --interval-s (default 1800 s, far below the API's 5-minute guidance), an identifying User-Agent and appcontact, a fixed lookback
(--lookback-s, default 2400 s = interval + margin so consecutive windows overlap). Counts and raw fields only; the callsigns in the data are real third-party
calls, so everything stays under the gitignored artefacts/ tree (NFR-021): never commit psk_reports.jsonl.
Lines: psk_fetch.log has one line per query (utc, http status, reports in the response, new, total). Ends at --until-utc (a last query is made at the end) or
when <corpus>/psk_fetch.stop appears. Stdlib only. Detached start (HK-023) is the caller's job.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

URL = "https://retrieve.pskreporter.info/query"
UA = "OpenWSFZ-QA/1.0 (endurance cross-check)"
APPCONTACT = "openwsfz-qa-endurance"
RPT_LIMIT = 5000
KEY_FIELDS = ("flowStartSeconds", "senderCallsign", "frequency", "mode")


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def callsign_from_daemon(port: int) -> str:
    c = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/v1/config", timeout=10).read())
    call = (c.get("tx") or {}).get("callsign") or ""
    if not call:
        raise SystemExit("the daemon has no tx.callsign: PSK uploads cannot be running")
    return call


def fetch(call: str, lookback_s: int):
    q = urllib.parse.urlencode({"receiverCallsign": call, "flowStartSeconds": -lookback_s, "rptlimit": RPT_LIMIT, "appcontact": APPCONTACT})
    req = urllib.request.Request(f"{URL}?{q}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
        status = r.status
    reports = []
    for _ev, el in ET.iterparse(__import__("io").BytesIO(body), events=("end",)):
        if el.tag == "receptionReport":
            reports.append(dict(el.attrib))
            el.clear()
    return status, reports


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--until-utc", required=True, help="ISO UTC, e.g. 2026-11-15T11:10:00Z")
    ap.add_argument("--interval-s", type=int, default=1800)
    ap.add_argument("--lookback-s", type=int, default=2400)
    a = ap.parse_args()
    corpus = Path(a.corpus)
    out, log, stop = corpus / "psk_reports.jsonl", corpus / "psk_fetch.log", corpus / "psk_fetch.stop"
    until = dt.datetime.fromisoformat(a.until_utc.replace("Z", "+00:00"))
    call = callsign_from_daemon(a.port)
    seen: set = set()
    if out.exists():
        for ln in out.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(ln)
                seen.add(tuple(r.get(k) for k in KEY_FIELDS))
            except json.JSONDecodeError:
                pass

    def one_round(tag: str) -> None:
        stamp = utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            status, reports = fetch(call, a.lookback_s)
        except Exception as ex:   # noqa: BLE001  a failed query is logged and the next round retries
            with log.open("a", encoding="utf-8") as f:
                f.write(f"{stamp} {tag} ERROR {type(ex).__name__}\n")
            return
        new = 0
        with out.open("a", encoding="utf-8") as f:
            for r in reports:
                k = tuple(r.get(x) for x in KEY_FIELDS)
                if k in seen:
                    continue
                seen.add(k)
                r["_fetched_utc"] = stamp
                f.write(json.dumps(r, sort_keys=True) + "\n")
                new += 1
        with log.open("a", encoding="utf-8") as f:
            f.write(f"{stamp} {tag} http {status} in_response {len(reports)} new {new} total {len(seen)}\n")

    one_round("start")
    while utcnow() < until and not stop.exists():
        nxt = min(utcnow() + dt.timedelta(seconds=a.interval_s), until)
        while utcnow() < nxt and not stop.exists():
            time.sleep(5)
        one_round("poll")
    one_round("final")


if __name__ == "__main__":
    main()
