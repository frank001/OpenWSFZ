"""ctypes binding of the COH-FALLBACK Stage 1 exports (shim 20260066; header src/OpenWSFZ.Ft8/Native/ft8_shim.h, "COH-FALLBACK (A' step 3) Stage 1").
QA-owned, used only by cf_a2.py and cf_a0.py. No message text is handled here."""
import ctypes as C
import hashlib

import numpy as np

SIZE_RES, SIZE_STATS, SIZE_ROW = 112, 80, 136                         # shim 20260066 (44f0df4e); shim 20260067 (d926bdc6): Stats 96, Row 144 (StatsV67 / RowV67)
FLAG_FORCE_C3, FLAG_SKIP_F1B, FLAG_ESTIMATE_ONLY, FLAG_INCLUDE_DECODED, FLAG_GATE_FIRST = 1, 2, 4, 8, 16
BP_NOT_RUN = 99
PCM_LEN = 180_000


class Res(C.Structure):
    _fields_ = [("est_df_hz", C.c_double), ("est_dt_s", C.c_double), ("peak", C.c_double), ("f1b_db", C.c_double),
                ("estimate_ms", C.c_double), ("f1b_ms", C.c_double), ("c3_bp_ms", C.c_double), ("elapsed_ms", C.c_double),
                ("dt_step", C.c_int32), ("edge", C.c_int32), ("n_refs", C.c_int32), ("gated", C.c_int32), ("c3_ran", C.c_int32),
                ("bp_rc", C.c_int32), ("bp_path", C.c_int32), ("bp_crc_ok", C.c_int32), ("bp_ldpc_errors", C.c_int32),
                ("a91", C.c_uint8 * 12)]


class Stats(C.Structure):
    _fields_ = [(n, C.c_int32) for n in ("n_candidates", "n_decoded", "n_dup_position", "n_eligible", "n_gated", "n_attempted", "n_crc_ok",
                                         "n_crc_new", "n_edge", "n_decoded_estimated", "n_rows", "reserved")] + \
               [(n, C.c_double) for n in ("estimate_ms", "f1b_ms", "c3_bp_ms", "total_ms")]


class Row(C.Structure):
    _fields_ = [("freq_hz", C.c_float), ("dt_s", C.c_float), ("pass_", C.c_int32), ("decoded", C.c_int32), ("crc_new", C.c_int32),
                ("reserved", C.c_int32), ("r", Res)]


class StatsV67(C.Structure):
    _fields_ = [(n, C.c_int32) for n in ("n_candidates", "n_decoded", "n_dup_position", "n_eligible", "n_attempted", "n_crc_ok", "n_crc_new", "n_f1b_computed",
                                         "n_gated", "n_published", "n_abandoned", "n_edge", "n_decoded_estimated", "n_rows", "reserved0", "reserved1")] +                [(n, C.c_double) for n in ("estimate_ms", "f1b_ms", "c3_bp_ms", "total_ms")]


class RowV67(C.Structure):
    _fields_ = [("freq_hz", C.c_float), ("dt_s", C.c_float), ("pass_", C.c_int32), ("decoded", C.c_int32), ("crc_new", C.c_int32),
                ("f1b_computed", C.c_int32), ("published", C.c_int32), ("reserved", C.c_int32), ("r", Res)]


class FT8Result(C.Structure):
    _fields_ = [("freq_hz", C.c_int), ("dt", C.c_float), ("snr", C.c_int), ("message", C.c_char * 36)]


assert C.sizeof(Res) == SIZE_RES and C.sizeof(Stats) == SIZE_STATS and C.sizeof(Row) == SIZE_ROW, (C.sizeof(Res), C.sizeof(Stats), C.sizeof(Row))
assert C.sizeof(StatsV67) == 96 and C.sizeof(RowV67) == 144, (C.sizeof(StatsV67), C.sizeof(RowV67))


class Native:
    def __init__(self, path, expected_sha256, expected_shim=20260066, nhard=24):
        self.v67 = expected_shim >= 20260067
        self.Stats, self.Row = (StatsV67, RowV67) if self.v67 else (Stats, Row)
        sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
        assert sha == expected_sha256, ("DLL differs from the pin", sha)
        self.sha = sha
        self.dll = C.CDLL(path)
        d = self.dll
        d.ft8_lib_version_check.restype = C.c_int
        assert d.ft8_lib_version_check() == expected_shim
        fp = C.POINTER(C.c_float)
        d.ft8_coherent_fallback_at.restype = C.c_int
        d.ft8_coherent_fallback_at.argtypes = [fp, C.c_int, C.c_double, C.c_double, C.c_int, C.POINTER(Res), fp]
        d.ft8_coherent_fallback_cycle.restype = C.c_int
        d.ft8_coherent_fallback_cycle.argtypes = [fp, C.c_int, C.c_int, C.POINTER(self.Stats), C.POINTER(self.Row), C.c_int]
        d.ft8_decode_all.restype = C.c_int
        d.ft8_decode_all.argtypes = [fp, C.c_int, C.POINTER(FT8Result), C.c_int]
        d.ft8_set_decode_params.argtypes = [C.c_int, C.c_float, C.c_int]
        d.ft8_set_osd_sign_fix.argtypes = [C.c_int]
        d.ft8_get_osd_sign_fix.restype = C.c_int
        d.ft8_set_decode_params(10, 0.10, nhard)
        d.ft8_set_osd_sign_fix(1)
        assert d.ft8_get_osd_sign_fix() == 1

    @staticmethod
    def _p(pcm):
        assert pcm.dtype == np.float32 and pcm.flags["C_CONTIGUOUS"] and len(pcm) == PCM_LEN
        return pcm.ctypes.data_as(C.POINTER(C.c_float))

    def at(self, pcm, f0, t0, flags=0, want_llr=False):
        res = Res()
        llr = (C.c_float * 174)() if want_llr else None
        rc = self.dll.ft8_coherent_fallback_at(self._p(pcm), PCM_LEN, float(f0), float(t0), int(flags), C.byref(res), llr)
        return rc, res, (list(llr) if want_llr else None)

    def decode_all(self, pcm, cap=200):
        arr = (FT8Result * cap)()
        n = self.dll.ft8_decode_all(self._p(pcm), PCM_LEN, arr, cap)
        return n, arr

    def cycle(self, pcm, flags=0, cap=2000):
        st = self.Stats()
        rows = (self.Row * cap)()
        n = self.dll.ft8_coherent_fallback_cycle(self._p(pcm), PCM_LEN, int(flags), C.byref(st), rows, cap)
        return n, st, rows
