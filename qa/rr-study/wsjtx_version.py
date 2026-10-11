"""WSJT-X appraiser: MEASURE that it can decode Q-prefix callsigns, and record what ran (QA tooling).

Why: WSJT-X 3.x added `callok` (lib/77bit/packjt77.f90) which rejects every standard callsign starting with Q, and the synthetic
S1-S8 truth set is Q-prefix only (NFR-021), so a 3.x appraiser decodes none of it and every between-appraiser row is void
(found 2026-10-11; 2.7.0 has no `callok`). Architect, REFERENCE-SET 2026-10-11: refuse a Q-prefix battery when the appraiser is >= 3.0;
and (same day) do not trust a typed version: read it from the executable that will actually run.

Mechanism (the gate): find the RUNNING WSJT-X process, take its executable and its environment, run the `jt9` that sits beside it
on a freshly rendered +20 dB `CQ Q1ABC FN42` FT8 cycle, and require the decode. That is the property that matters, measured on the
install that will play the part of the appraiser; a typed string cannot pass it. A stated version (`--wsjtx-version`, optional) is only a
LABEL and must agree with the measurement (< 3.0 <=> the canary decodes). Not found, not runnable, or no decode: refused (the default rule).
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile

_VERSION_RX = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")
Q_PREFIX_MAX_EXCLUSIVE = (3, 0)      # first WSJT-X version that rejects Q-prefix callsigns (evidence: callok in 3.0.2)
CANARY_MESSAGE = "CQ Q1ABC FN42"
CANARY_SNR_DB = 20.0
CANARY_FREQ_HZ = 1500.0
CANARY_SEED = 42
CANARY_STAMP = "261011_000000"       # jt9 takes the cycle time from the file name (YYMMDD_HHMMSS)
CANARY_TIMEOUT_S = 120


def parse_version(text):
    """-> (major, minor, patch) from the first dotted number in `text`, or None."""
    if not text:
        return None
    m = _VERSION_RX.search(str(text))
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)


def canary_decoded_in(jt9_stdout):
    """True if jt9's stdout contains the canary message as a decode (pure; unit-tested)."""
    return any(CANARY_MESSAGE in line and "DecodeFinished" not in line for line in (jt9_stdout or "").splitlines())


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def find_running_wsjtx():
    """-> (exe_path, env_dict_or_None, reason). The first running 'wsjtx' process; env is that process's own environment
    (needed on Linux for LD_LIBRARY_PATH / QT_PLUGIN_PATH), None on Windows (the default environment is the process's)."""
    if os.name == "nt":
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command",
                                "Get-Process -Name wsjtx -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Path"],
                               capture_output=True, text=True, timeout=60)
        except Exception as e:  # noqa: BLE001
            return None, None, "cannot list processes: %r" % (e,)
        p = r.stdout.strip()
        return (p, None, "") if p and os.path.isfile(p) else (None, None, "no running wsjtx process")
    for d in sorted(os.listdir("/proc")):
        if not d.isdigit():
            continue
        try:
            exe = os.readlink("/proc/%s/exe" % d)
            if os.path.basename(exe) != "wsjtx":
                continue
            with open("/proc/%s/environ" % d, "rb") as fh:
                env = dict(kv.split("=", 1) for kv in fh.read().decode("utf-8", "replace").split("\0") if "=" in kv)
            return exe, env, ""
        except OSError:
            continue
    return None, None, "no running wsjtx process"


def render_canary_wav(path):
    """Writes the 15 s, 12 kHz, 16-bit mono canary cycle to `path` (needs numpy/scipy and the study's own synth modules)."""
    import wave
    import numpy as np
    from scipy.signal import resample_poly
    from synth import channel, encoder
    clean = encoder.encode_message(CANARY_MESSAGE, base_freq_hz=CANARY_FREQ_HZ, dt_s=0.0, snr_db=None, sample_rate_hz=48000)
    noisy = channel.add_noise(clean, CANARY_SNR_DB, CANARY_SEED, sample_rate_hz=48000).astype("float32")
    noisy = noisy * (0.5 / float(np.max(np.abs(noisy))))
    pcm = np.clip(resample_poly(noisy, 1, 4), -1.0, 1.0)
    pcm = (pcm * 32767).astype("<i2")
    pcm = np.concatenate([pcm, np.zeros(max(0, 180000 - len(pcm)), dtype="<i2")])[:180000]
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(12000)
        w.writeframes(pcm.tobytes())


def probe(wsjtx_exe=None, wsjtx_env=None):
    """Measures the WSJT-X that will run. Returns a dict with: found, exe, exe_sha256, jt9, canary_decoded (True/False/None), reason."""
    out = {"found": False, "exe": None, "exe_sha256": None, "jt9": None, "canary_decoded": None, "reason": ""}
    exe, env, reason = (wsjtx_exe, wsjtx_env, "") if wsjtx_exe else find_running_wsjtx()
    if not exe:
        out["reason"] = reason
        return out
    out["found"], out["exe"] = True, exe
    try:
        out["exe_sha256"] = _sha256(exe)
    except OSError as e:
        out["reason"] = "cannot read the executable: %r" % (e,)
        return out
    jt9 = os.path.join(os.path.dirname(exe), "jt9.exe" if os.name == "nt" else "jt9")
    if not os.path.isfile(jt9):
        out["reason"] = "no jt9 beside the executable"
        return out
    out["jt9"] = jt9
    wd = tempfile.mkdtemp(prefix="wsjtx_canary_")
    try:
        wav = os.path.join(wd, CANARY_STAMP + ".wav")
        render_canary_wav(wav)
        r = subprocess.run([jt9, "-8", "-p", "15", "-d", "3", "-a", wd, "-t", wd, wav], capture_output=True, text=True,
                           timeout=CANARY_TIMEOUT_S, cwd=wd, env=env if env else None)
        out["canary_decoded"] = canary_decoded_in(r.stdout)
        if not out["canary_decoded"]:
            out["reason"] = "the Q-prefix canary was not decoded (this WSJT-X rejects Q-prefix callsigns, or jt9 cannot run)"
    except Exception as e:  # noqa: BLE001  (a measurement that cannot be made is a refusal)
        out["canary_decoded"] = None
        out["reason"] = "canary could not be run: %r" % (e,)
    finally:
        shutil.rmtree(wd, ignore_errors=True)
    return out


def check(stated_version, measured):
    """Returns {"stated": str|None, "stated_parsed": "x.y.z"|None, "measured": <probe dict>, "checks": {...}} for arm_config.json.

    checks.wsjtx_found_running               a running WSJT-X (and its jt9) was found and read
    checks.wsjtx_q_prefix_canary_decodes     the measurement: that install's jt9 decodes a Q-prefix message
    checks.wsjtx_stated_version_consistent   no stated version, or it agrees with the measurement (< 3.0 <=> decodes)
    """
    v = parse_version(stated_version)
    decoded = measured.get("canary_decoded")
    consistent = True
    if stated_version:
        consistent = v is not None and decoded is not None and ((v < Q_PREFIX_MAX_EXCLUSIVE) == bool(decoded))
    return {
        "stated": stated_version if stated_version else None,
        "stated_parsed": ".".join(str(x) for x in v) if v else None,
        "measured": measured,
        "checks": {
            "wsjtx_found_running": bool(measured.get("found")) and bool(measured.get("jt9")),
            "wsjtx_q_prefix_canary_decodes": decoded is True,
            "wsjtx_stated_version_consistent": consistent,
        },
    }
