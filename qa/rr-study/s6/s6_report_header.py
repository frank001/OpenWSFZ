"""Header of an S6-only run's report.md (QA tooling): the build and the settings, from the run's own arm_config.json (HK-022: never the analysis tree's HEAD)."""
from __future__ import annotations

import json
from datetime import datetime, timezone


def header(run_dir, arm: dict, args) -> str:
    d = (arm or {}).get("daemon", {})
    b = (arm or {}).get("build", {})
    rb = d.get("decoder_readback") or {}
    w = (arm or {}).get("wsjtx", {})
    rows = [("Run date", datetime.now(timezone.utc).strftime("%Y-%m-%d")), ("Run folder", str(run_dir.name)),
            ("OpenWSFZ SHA", "`%s` (the daemon build, from arm_config.json)" % b.get("commit")),
            ("native library SHA-256", "`%s` (shim %s, daemon %s)" % (d.get("dll_sha256"), d.get("shim_version"), d.get("daemon_version"))),
            ("Decoder flags (read back)", ", ".join("`%s` = %s" % (k, rb[k]) for k in sorted(rb))),
            ("WSJT-X", "NDepth %s, mode %s (version string: see the S6 pins; this report does not infer it)" % (w.get("NDepth"), w.get("mode"))),
            ("Scenarios run", "S6 only, tier `%s`" % getattr(args, "s6_tier", "?"))]
    return ("# OpenWSFZ R&R Study Report: S6 only (off-air WAV replay)\n\n"
            "> **An S6-only run: no S1-S8 scenario was played, so there is no S1-S8 verdict and no Section 5 / Section 6 of the battery report.** "
            "S6 is informational on its first battery.\n\n| Field | Value |\n|---|---|\n" + "\n".join("| %s | %s |" % r for r in rows) + "\n")
