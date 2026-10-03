#!/usr/bin/env python
"""Builds the run config for the SUB-FEAS first on-air session (2026-09-30/10-01) from the last PROVEN endurance config, changing only
what the plan pins, and prints the exact differences (values of callsign/grid/passphrase fields are never printed).

Base: qa/endurance/12h-direct-codec-config/config.json (the 20260925_2010 run's config). Changes, all pinned by the Captain/Architect:
  audio device          -> Voicemeeter Out B1 (same stream as WSJT-X; device id from the 20260922_2056 run's arm_config.json)
  port                  -> 8080
  decoder               -> {subtractionEnabled: true, subtractionMaxThreads: 8, osdNhardMax: 40}   (Architect 2026-09-30: 8 pinned)
  tx.autoAnswer         -> false (asserted)
  cycleAudioArchive     -> mode "all", maxAgeHours 48 (the base had 14, which would PRUNE the corpus of a ~18 h run), maxSizeMb 16384,
                           directory <run>/cycle-audio
  decodeLog             -> <run>/ALL.TXT, dialFrequencyMHz 7.074 (40m)
  logging               -> directory <run>/daemon-logs, Information
Everything else (cat disabled, externalReporting disabled, ptt AudioVox, remoteAccess off) is inherited unchanged.

Usage: python make_subfeas_onair_config.py <run-dir> <out-config.json>
"""
import copy
import json
import os
import sys

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "12h-direct-codec-config", "config.json")
B1_NAME = "Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)"
B1_ID = "{0.0.1.00000000}.{8dbb88e8-fd07-44b8-9ee9-88b906b8d11f}"
SECRET = ("call", "grid", "pass", "key", "secret")


def redact(k, v):
    return "<redacted>" if any(x in str(k).lower() for x in SECRET) else v


def flat(d, p=""):
    out = {}
    for k, v in d.items():
        q = f"{p}.{k}" if p else k
        if isinstance(v, dict):
            out.update(flat(v, q))
        else:
            out[q] = redact(k, v)
    return out


def main():
    run_dir, out = os.path.abspath(sys.argv[1]).replace("\\", "/"), sys.argv[2]
    base = json.load(open(BASE, encoding="utf-8"))
    c = copy.deepcopy(base)
    c["audioDeviceFriendlyName"] = B1_NAME
    c["audioDeviceId"] = B1_ID
    c["port"] = 8080
    c["decoder"] = {"subtractionEnabled": True, "subtractionMaxThreads": 8, "osdNhardMax": 40}
    c.setdefault("tx", {})["autoAnswer"] = False
    c["cycleAudioArchive"] = {**base.get("cycleAudioArchive", {}), "mode": "all", "directory": run_dir + "/cycle-audio",
                              "maxSizeMb": 16384, "maxAgeHours": 48, "writeManifest": True}
    c["decodeLog"] = {**base.get("decodeLog", {}), "enabled": True, "path": run_dir + "/ALL.TXT", "dialFrequencyMHz": 7.074}
    c["logging"] = {**base.get("logging", {}), "fileEnabled": True, "directory": run_dir + "/daemon-logs", "fileLogLevel": "Information"}
    c["decodingEnabled"] = True
    # asserts: the things that would silently defeat the run (HK-020)
    assert c["decoder"]["subtractionEnabled"] is True and c["decoder"]["subtractionMaxThreads"] == 8
    assert c["tx"]["autoAnswer"] is False
    assert c["cycleAudioArchive"]["mode"] == "all" and c["cycleAudioArchive"]["maxAgeHours"] >= 48
    assert c["port"] == 8080 and c["audioDeviceId"] == B1_ID
    assert (c.get("cat") or {}).get("enabled") is False and (c.get("externalReporting") or {}).get("enabled") is False
    json.dump(c, open(out, "w", encoding="utf-8"), indent=2)
    fb, fc = flat(base), flat(c)
    for k in sorted(set(fb) | set(fc)):
        if fb.get(k, "<absent>") != fc.get(k, "<absent>"):
            print(f"CHANGED {k}: {fb.get(k, '<absent>')!r} -> {fc.get(k, '<absent>')!r}")
    print("wrote", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
