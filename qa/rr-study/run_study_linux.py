#!/usr/bin/env python
"""Linux entry point for the standing detached S1-S8 battery (QA tooling; the Windows launcher is untouched).

Installs the POSIX compatibility layer (linux/linux_compat.py), swaps in the Linux PRECHECK twin
(rr_precheck_linux.py), then runs run_study_detached.main() in its INTERNAL ``--poll`` mode. The Windows launcher's own
detach step (DETACHED / NEWGROUP creation flags) is not used: start this under ``nohup ... &`` (HK-023).

    nohup python run_study_linux.py --poll --supervisor-dir <dir> --daemon-exe <exe> --config <config> --port 8080 \\
          --wsjtx-ini <ini> -- --scenarios S1,S1b,S2,S3,S4,S5,S7,S8,S3c --skip-warmup --device "RR-ALSA" \\
          > <dir>/supervisor.log 2>&1 &

Environment: PYTHONPATH must put qa/rr-study/linux/shim FIRST (the ``sounddevice`` stand-in playing through aplay);
RR_ALSA_PLAYBACK names the ALSA playback PCM (default plughw:0,0).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "linux", "shim"))
sys.path.insert(0, os.path.join(HERE, "linux"))
sys.path.insert(0, HERE)

import linux_compat  # noqa: E402

ES = linux_compat.install()

import rr_precheck        # noqa: E402  (imports the SAME patched endurance_supervisor module object)
import rr_precheck_linux  # noqa: E402

rr_precheck.precheck = rr_precheck_linux.precheck
rr_precheck.ES = ES

import run_study_detached  # noqa: E402

if __name__ == "__main__":
    sys.exit(run_study_detached.main())
