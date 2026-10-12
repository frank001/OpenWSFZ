#!/usr/bin/env python
"""REFERENCE-SET leg E driver (QA, 2026-10-12; spec 2c, 2n item 4): play WSJT-X's own recording of each block into a FRESH WSJT-X 2.7.0
in REAL TIME and record, per cycle, WSJT-X's decode time from its UDP messages. Linux (sol): aplay -> codec loopback -> ALSA rr_in.

  python run_leg_e.py --corpus <corpus> --block <id> [--block <id> ...] --scratch <dir OUTSIDE git> --rep 1 [--lead 0.2]

Per cycle it records (all monotonic-clock durations, UTC only in the log):
  T_wsjtx_busy   first Status 'Decoding' true after the cycle boundary -> next false (HK-027: step (i) verifies the flag)
  T_wsjtx_span   first true -> last false inside the cycle's window (several decode passes may run)
  n_busy         number of true intervals
  T_wsjtx_last   arrival of the cycle's last Decode message minus the cycle boundary
  n_decodes      Decode messages for the cycle (WSJT-X's own 'time' field says which cycle)
  overrun        1 if a Decode for cycle n arrives after cycle n+1's boundary
  n_live         lines of the live WSJT-X ALL.TXT for the same stamp (COUNT only); dropped = n_decodes - n_live
NFR-021 / HK-037: the per-message text is written ONLY to the working TSV in --scratch (outside git, deleted at job close); the JSON holds
counts and times. Nothing here touches src/ or native/.
"""
import argparse
import json
import os
import socket
import struct
import subprocess
import sys
import threading
import time

UDP_ADDR = ("127.0.0.1", 2237)
MAGIC = 0xADBCCBDA
TYPE_STATUS, TYPE_DECODE = 1, 2
CYCLE_S = 15.0
DEFAULT_LEAD_S = 0.0           # step (i) 2026-10-12: lead 0.2 s read DT 0.2 s low against the live log; lead 0.0 reads 0.0
START_TIMEOUT_S = 180
DRAIN_S = 25.0                 # after the last cycle: let the last decode and Status falling edge arrive
FIRST_BOUNDARY_MIN_AHEAD_S = 12.0
APLAY_DEVICE = "plughw:0,0"
HOME = os.path.expanduser("~")
START_SH = os.path.join(HOME, "start-wsjtx27.sh")
STOP_SH = os.path.join(HOME, "stop-wsjtx.sh")


def _read_str(buf, off):
    n = struct.unpack_from(">I", buf, off)[0]
    off += 4
    if n == 0xFFFFFFFF:
        return None, off
    return buf[off:off + n].decode("utf-8", "replace"), off + n


def parse_packet(buf):
    """WSJT-X UDP (QDataStream, big endian). Returns a dict or None. Only Status and Decode are parsed."""
    if len(buf) < 12 or struct.unpack_from(">I", buf, 0)[0] != MAGIC:
        return None
    mtype = struct.unpack_from(">I", buf, 8)[0]
    off = 12
    _id, off = _read_str(buf, off)
    if mtype == TYPE_STATUS:
        dial = struct.unpack_from(">Q", buf, off)[0]; off += 8
        mode, off = _read_str(buf, off)
        _dxcall, off = _read_str(buf, off)
        _report, off = _read_str(buf, off)
        _txmode, off = _read_str(buf, off)
        tx_enabled, transmitting, decoding = struct.unpack_from(">???", buf, off)
        return {"type": "status", "dial": dial, "mode": mode, "tx_enabled": tx_enabled, "transmitting": transmitting, "decoding": decoding}
    if mtype == TYPE_DECODE:
        new = struct.unpack_from(">?", buf, off)[0]; off += 1
        tms, snr = struct.unpack_from(">Ii", buf, off); off += 8
        dt = struct.unpack_from(">d", buf, off)[0]; off += 8
        df = struct.unpack_from(">I", buf, off)[0]; off += 4
        _mode, off = _read_str(buf, off)
        msg, off = _read_str(buf, off)
        return {"type": "decode", "new": new, "time_ms": tms, "snr": snr, "dt": dt, "df": df, "text": msg}
    return {"type": "other", "mtype": mtype}


class Listener(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(UDP_ADDR)
        self.sock.settimeout(0.5)
        self.events = []          # (mono, wall, dict)
        self.lock = threading.Lock()
        self.stop = False

    def run(self):
        while not self.stop:
            try:
                buf, _ = self.sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            m, w = time.monotonic(), time.time()
            try:
                p = parse_packet(buf)
            except Exception:
                p = None
            if p and p["type"] in ("status", "decode"):
                with self.lock:
                    self.events.append((m, w, p))

    def snapshot(self):
        with self.lock:
            return list(self.events)


def sh(cmd, **kw):
    return subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, **kw)


def start_wsjtx():
    sh(STOP_SH)
    time.sleep(2)
    subprocess.Popen(["nohup", "sh", START_SH, "rr"], stdout=open(os.path.join(HOME, "wsjtx27-rr.log"), "ab"), stderr=subprocess.STDOUT,
                     stdin=subprocess.DEVNULL, start_new_session=True)


def wait_status(lst, since_idx):
    t0 = time.monotonic()
    while time.monotonic() - t0 < START_TIMEOUT_S:
        ev = lst.snapshot()
        for m, w, p in ev[since_idx:]:
            if p["type"] == "status":
                return p
        time.sleep(1)
    return None


def live_counts(corpus, run, stamps):
    """COUNT of live WSJT-X ALL.TXT lines per stamp. The file is read here and only counts leave."""
    path = os.path.join(corpus, "wsjt-x", run, "ALL.TXT")
    want = set(stamps)
    out = {s: 0 for s in stamps}
    dts = {s: [] for s in stamps}
    with open(path, "r", errors="replace") as fh:
        for line in fh:
            f = line.split()
            if f and f[0] in want:
                out[f[0]] += 1
                try:
                    dts[f[0]].append(float(f[5]))
                except (IndexError, ValueError):
                    pass
    live_dt = {k: (sorted(v)[len(v) // 2] if v else None) for k, v in dts.items()}
    return out, live_dt


def run_block(corpus, blk, scratch, rep, lead):
    run, cycles = blk["run"], blk["cycles"]
    nwarm = blk["warmup_cycles"]
    lst = Listener(); lst.start()
    base_idx = 0
    start_wsjtx()
    first = wait_status(lst, base_idx)
    if first is None:
        lst.stop = True
        lst.sock.close()
        raise RuntimeError("WSJT-X sent no Status within the start timeout")
    time.sleep(8)  # let it settle; start time is excluded from the cycle timing (spec 2c item 2)
    now = time.time()
    t_first = (int(now + FIRST_BOUNDARY_MIN_AHEAD_S) // 15 + 1) * 15.0
    mono0 = time.monotonic() - time.time()          # wall -> monotonic offset (both read back-to-back)
    bnd_wall = [t_first + CYCLE_S * k for k in range(len(cycles))]
    # ONE continuous stream per block (a per-cycle aplay fails with 'device busy' where a file overlaps the next start: found in step (i), 2026-10-12)
    import wave
    frames, params = [], None
    for stamp in cycles:
        with wave.open(os.path.join(corpus, "wsjt-x", run, stamp + ".wav"), "rb") as w:
            pr = (w.getnchannels(), w.getsampwidth(), w.getframerate())
            if params is None:
                params = pr
            if pr != params or pr != (1, 2, 12000):
                raise RuntimeError(f"unexpected WAV format {pr} in {stamp}")
            fr = w.readframes(w.getnframes())
        want = int(CYCLE_S * 12000) * 2
        frames.append(fr[:want] + bytes(max(0, want - len(fr))))   # every cycle exactly 15.000 s, so cycle k starts at k * 15 s
    stream = os.path.join(scratch, f"{blk['id']}.stream.wav")
    with wave.open(stream, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(12000)
        w.writeframes(b"".join(frames))
    target = t_first - lead
    while time.time() < target:
        time.sleep(0.005)
    t_spawn = time.time()
    proc = subprocess.Popen(["aplay", "-q", "-D", APLAY_DEVICE, stream], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    spawn = [t_spawn - t_first] * len(cycles)
    procs = [proc]
    proc.wait()                                   # the stream is 40 x 15 s long
    time.sleep(DRAIN_S)
    aplay_rc, aplay_err = procs[0].poll(), (procs[0].stderr.read().decode()[:200] if procs[0].poll() is not None else "")
    ev = lst.snapshot()
    lst.stop = True
    lst.join(timeout=3)
    try:
        lst.sock.close()
    except OSError:
        pass
    sh(STOP_SH)
    # midnight of the block's UTC day, to turn WSJT-X's time_ms into a cycle boundary
    day0 = int(t_first // 86400) * 86400
    rows = []
    live, live_dt = live_counts(corpus, run, cycles)
    work = os.path.join(scratch, f"{blk['id']}.rep{rep}.decodes.tsv")
    with open(work, "w", encoding="utf-8") as wf:
        wf.write("cycle\tarrival_s\tsnr\tdt\tdf\ttext\n")
        for k, stamp in enumerate(cycles):
            b = bnd_wall[k]; b_next = b + CYCLE_S
            bm = b + mono0; bm_next = b_next + mono0
            decs = [(m, p) for m, w, p in ev if p["type"] == "decode" and abs((day0 + p["time_ms"] / 1000.0) - b) < 1.0]
            for m, p in decs:
                wf.write(f"{stamp}\t{m - bm:.3f}\t{p['snr']}\t{p['dt']:.2f}\t{p['df']}\t{p['text']}\n")
            # busy intervals that START inside [b, b_next)
            ivs = []
            cur = None
            for m, w, p in ev:
                if p["type"] != "status":
                    continue
                if p["decoding"] and cur is None and bm <= m < bm_next:
                    cur = m
                elif (not p["decoding"]) and cur is not None:
                    ivs.append((cur - bm, m - bm)); cur = None
            if cur is not None:
                ivs.append((cur - bm, None))
            closed = [iv for iv in ivs if iv[1] is not None]
            rows.append({
                "stamp": stamp, "warmup": k < nwarm, "spawn_offset_s": round(spawn[k], 3),
                "n_decodes": len(decs), "n_live": live[stamp], "dropped": len(decs) - live[stamp],
                "n_busy": len(ivs),
                "T_wsjtx_busy": round(closed[0][1] - closed[0][0], 3) if closed else None,
                "busy_first_true_s": round(ivs[0][0], 3) if ivs else None,
                "T_wsjtx_busy_sum": round(sum(e - s for s, e in closed), 3) if closed else None,
                "T_wsjtx_span": round(closed[-1][1] - closed[0][0], 3) if closed else None,
                "T_wsjtx_last": round(max(m for m, _ in decs) - bm, 3) if decs else None,
                "overrun": int(any(m > bm_next for m, _ in decs)),
                "dt_median": sorted(p["dt"] for _, p in decs)[len(decs) // 2] if decs else None, "dt_live_median": live_dt[stamp],
            })
    out = {"block": blk["id"], "run": run, "rep": rep, "lead_s": lead, "first_status": first, "cycles": rows,
           "aplay_rc": aplay_rc, "aplay_err": aplay_err, "status_msgs": sum(1 for _, _, p in ev if p["type"] == "status"), "decode_msgs": sum(1 for _, _, p in ev if p["type"] == "decode")}
    with open(os.path.join(scratch, f"{blk['id']}.rep{rep}.json"), "w") as f:
        json.dump(out, f, indent=1)
    try:
        os.remove(stream)                            # 14 MB per block; the corpus holds the originals
    except OSError:
        pass
    if aplay_rc != 0 or out["decode_msgs"] == 0:
        raise RuntimeError(f"block {blk['id']}: aplay rc {aplay_rc}, decode messages {out['decode_msgs']}: stream or WSJT-X failed")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--block", action="append", required=True)
    ap.add_argument("--scratch", required=True)
    ap.add_argument("--rep", type=int, default=1)
    ap.add_argument("--lead", type=float, default=DEFAULT_LEAD_S)
    a = ap.parse_args()
    os.makedirs(a.scratch, exist_ok=True)
    man = json.load(open(os.path.join(a.corpus, "manifest.json")))
    by_id = {b["id"]: b for b in man["blocks"]}
    for bid in a.block:
        blk = by_id[bid]
        if os.path.exists(os.path.join(a.scratch, f"{bid}.rep{a.rep}.json")):
            print(time.strftime("%FT%TZ", time.gmtime()), "skip (checkpoint)", bid, flush=True)
            continue
        print(time.strftime("%FT%TZ", time.gmtime()), "block", bid, blk["band"], blk["sun"], len(blk["cycles"]), "cycles", flush=True)
        r = None
        for attempt in (1, 2):                       # block-level failure: ONE re-run, then exclude and record (the refset's rule); no other retries
            try:
                r = run_block(a.corpus, blk, a.scratch, a.rep, a.lead)
                break
            except Exception as ex:                  # noqa: BLE001 - recorded, never swallowed silently
                print(time.strftime("%FT%TZ", time.gmtime()), f"block {bid} attempt {attempt} FAILED: {type(ex).__name__}: {ex}", flush=True)
                subprocess.run(["sh", STOP_SH], capture_output=True)
                subprocess.run(["pkill", "-x", "aplay"], capture_output=True)
                time.sleep(5)
        if r is None:
            with open(os.path.join(a.scratch, "EXCLUDED.txt"), "a") as ef:
                ef.write(" ".join([bid, "rep" + str(a.rep), "excluded after one re-run,", time.strftime("%FT%TZ", time.gmtime())]) + chr(10))
            print(time.strftime("%FT%TZ", time.gmtime()), f"block {bid} EXCLUDED (second failure); queue continues", flush=True)
            continue
        sc = [c for c in r["cycles"] if not c["warmup"]]
        print(time.strftime("%FT%TZ", time.gmtime()), "done", bid, "status", r["status_msgs"], "decodes", r["decode_msgs"],
              "scored cycles with a busy interval", sum(1 for c in sc if c["T_wsjtx_busy"] is not None), "of", len(sc), flush=True)


if __name__ == "__main__":
    main()
