"""Minimal ``sounddevice`` stand-in for the R&R harness on a Linux box with plain ALSA (no PortAudio, no PulseAudio).

The harness only uses: query_devices(), query_hostapis(), play(samples, samplerate=, device=, blocking=False), wait(),
PortAudioError. Playback goes through ``aplay`` (raw float32 on stdin). Put this directory FIRST on PYTHONPATH.

The ALSA playback device is taken from the environment variable RR_ALSA_PLAYBACK (default ``plughw:0,0``) and is
advertised under the name ``RR-ALSA <device>``, so ``--device "RR-ALSA"`` selects it.
"""
import os
import subprocess
import threading

import numpy as np


class PortAudioError(Exception):
    pass


_ALSA = os.environ.get("RR_ALSA_PLAYBACK", "plughw:0,0")
_DEVICES = [{"name": "RR-ALSA " + _ALSA, "hostapi": 0, "max_output_channels": 2, "max_input_channels": 0,
             "default_samplerate": 48000.0}]
_state = {"proc": None, "thread": None, "err": None}


def query_hostapis():
    return [{"name": "ALSA"}]


def query_devices(device=None, kind=None):
    return list(_DEVICES) if device is None else _DEVICES[0]


def _writer(proc, payload):
    try:
        proc.stdin.write(payload)
        proc.stdin.close()
    except (BrokenPipeError, OSError) as e:       # aplay died early: wait() reports its stderr
        _state["err"] = repr(e)


def stop():
    p = _state["proc"]
    if p is not None and p.poll() is None:
        p.terminate()
    _state["proc"] = None


def play(data, samplerate=None, device=None, blocking=False, **kwargs):
    stop()
    arr = np.asarray(data, dtype="<f4")
    channels = 1 if arr.ndim == 1 else arr.shape[1]
    cmd = ["aplay", "-q", "-D", _ALSA, "-t", "raw", "-f", "FLOAT_LE", "-r", str(int(samplerate)), "-c", str(channels)]
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as e:
        raise PortAudioError("cannot start aplay: %r" % (e,))
    _state["err"] = None
    th = threading.Thread(target=_writer, args=(proc, np.ascontiguousarray(arr).tobytes()), daemon=True)
    th.start()
    _state["proc"], _state["thread"] = proc, th
    if blocking:
        wait()


def wait():
    p, th = _state["proc"], _state["thread"]
    if p is None:
        return
    if th is not None:
        th.join()
    rc = p.wait()
    err = (p.stderr.read() or b"").decode("utf-8", "replace").strip()[:300]
    _state["proc"] = None
    if rc != 0:
        raise PortAudioError("aplay exited %d: %s" % (rc, err))
