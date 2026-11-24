#!/usr/bin/env python3
"""FD-PROXY V-AGREE, U' side: the frozen cf_fbid tone test (cf_uprime.load_instrument asserts the ecc4c5e7 blob) at a row's own (freq, dt) on the ORIGINAL audio,
start offset calibrated on the first 80 confirmed controls exactly as cf_uprime / tc_score do (here on OUR dt). Present iff the data-symbol hit share >= T_FROZEN 0.276
(cf_uprime.T_FROZEN, asserted below). HK-037: message text is read here to make tones, never written; numbers out.
"""
from __future__ import annotations

import os
import sys

import numpy as np

CF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "rr-study", "coh-fallback")
sys.path.insert(0, CF)
import cf_uprime as U   # noqa: E402

T_FROZEN = 0.276
CALIBRATION_CONTROLS, CALIBRATION_MIN_SYNC_HIT = 80, 0.6
assert (T_FROZEN, CALIBRATION_CONTROLS, CALIBRATION_MIN_SYNC_HIT) == (U.T_FROZEN, U.CALIBRATION_CONTROLS, U.CALIBRATION_MIN_SYNC_HIT)


class Tone:
    def __init__(self, wav_dir, dll):
        self.F, self.blob = U.load_instrument()
        self.enc = self.F.encoder(dll)
        self.wav_dir = wav_dir
        self._pcm = {}
        self.c_off = None

    def pcm(self, stamp):
        if stamp not in self._pcm:
            if len(self._pcm) > 40:
                self._pcm.clear()
            self._pcm[stamp] = self.F.wavio.load_cycle_pcm(os.path.join(self.wav_dir, stamp + ".wav"))
        return self._pcm[stamp]

    def calibrate(self, controls):
        """controls: [(stamp, f, dt, text)] confirmed, sorted by (stamp, f); the first 80 with a non-hashed, encodable text."""
        offs, used = [], 0
        for (st, f, dt, text) in controls:
            if used >= CALIBRATION_CONTROLS:
                break
            if "<" in text:
                continue
            tones = self.enc(text)
            if tones is None:
                continue
            used += 1
            h, start = U.locate_start(self.F, self.pcm(st), f, dt + 0.5, self.F.CALIB_HALF_WINDOW_S, [tones[i] for i in self.F.SYNC_IDX])
            if h >= CALIBRATION_MIN_SYNC_HIT:
                offs.append(start - dt)
        self.c_off = float(np.median(offs)) if offs else 0.5
        return dict(controls_used=used, with_sync_hit_ge_0p6=len(offs), start_minus_dt_median_s=self.c_off)

    def share(self, stamp, f, dt, text):
        """data-symbol hit share at the position chosen by the Costas symbols; None if the text cannot be encoded."""
        tones = self.enc(text)
        if tones is None:
            return None
        _, outs = self.F.locate_and_score({}, self.pcm(stamp), f, dt + self.c_off, self.F.DT_HALF_WINDOW_S, [tones[i] for i in self.F.SYNC_IDX], [tones])
        return outs[0]
