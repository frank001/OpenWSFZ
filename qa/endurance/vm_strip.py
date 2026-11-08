#!/usr/bin/env python3
"""Voicemeeter strip control for QA's live runs (QA 2026-10-19; Captain: "can you unmute/mute the channels when required?").

Voicemeeter Banana, Remote API (VoicemeeterRemote64.dll, as qa/audio-setup/sampler.py). Every write is READ BACK and logged as a JSON
line (UTC time, action, strip, value before, value after, ok). Nothing here touches routing, gain, buses or any other parameter: only
`Strip[i].Mute`, and only on a strip the caller names.

  python vm_strip.py status [--strips 0,2,4]
  python vm_strip.py unmute --strip 0 [--log F]        mute --strip 0 [--log F]
  python vm_strip.py mute-at --strip 0 --utc 2026-10-20T14:31:00Z [--log F]    (blocks until the time, then mutes; run it detached)

Exit code 0 only when the read-back equals the requested state.
"""
from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import json
import sys
import time

DLL = r"C:\Program Files (x86)\VB\Voicemeeter\VoicemeeterRemote64.dll"


class VM:
    def __init__(self) -> None:
        self.dll = ctypes.WinDLL(DLL)
        if self.dll.VBVMR_Login() != 0:
            raise OSError("VBVMR_Login failed")
        time.sleep(0.8)

    def close(self) -> None:
        self.dll.VBVMR_Logout()

    def get(self, name: str) -> float | None:
        self.dll.VBVMR_IsParametersDirty()
        v = ctypes.c_float()
        return v.value if self.dll.VBVMR_GetParameterFloat(name.encode(), ctypes.byref(v)) == 0 else None

    def set_mute(self, strip: int, muted: bool) -> tuple[float | None, float | None, bool]:
        before = self.get(f"Strip[{strip}].Mute")
        rc = self.dll.VBVMR_SetParameters(f"Strip[{strip}].Mute={1 if muted else 0};".encode())
        after = None
        for _ in range(20):                       # the engine applies the write asynchronously: poll the read-back up to 2 s
            time.sleep(0.1)
            after = self.get(f"Strip[{strip}].Mute")
            if after is not None and int(after) == (1 if muted else 0):
                break
        return before, after, rc == 0 and after is not None and int(after) == (1 if muted else 0)


def log_line(path: str | None, rec: dict) -> None:
    rec = {"utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), **rec}
    print(json.dumps(rec))
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["status", "mute", "unmute", "mute-at"])
    ap.add_argument("--strip", type=int)
    ap.add_argument("--strips", default="0,1,2,3,4")
    ap.add_argument("--utc")
    ap.add_argument("--log")
    a = ap.parse_args()
    vm = VM()
    try:
        if a.cmd == "status":
            for i in (int(x) for x in a.strips.split(",")):
                log_line(a.log, {"action": "status", "strip": i, "mute": vm.get(f"Strip[{i}].Mute"), "B1": vm.get(f"Strip[{i}].B1"), "gain": vm.get(f"Strip[{i}].Gain")})
            return 0
        assert a.strip is not None, "--strip is required"
        if a.cmd == "mute-at":
            assert a.utc, "--utc is required"
            at = dt.datetime.fromisoformat(a.utc.replace("Z", "+00:00"))
            log_line(a.log, {"action": "mute-at armed", "strip": a.strip, "at": a.utc})
            while dt.datetime.now(dt.timezone.utc) < at:
                time.sleep(15)
        want_mute = a.cmd in ("mute", "mute-at")
        before, after, ok = vm.set_mute(a.strip, want_mute)
        log_line(a.log, {"action": "mute" if want_mute else "unmute", "strip": a.strip, "before": before, "after": after, "ok": ok})
        return 0 if ok else 1
    finally:
        vm.close()


if __name__ == "__main__":
    sys.exit(main())
