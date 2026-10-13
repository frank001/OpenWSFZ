"""Tests for perf_phase_split: the rows are mutually exclusive, sum to 100 %, and classify known stacks as specified."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import perf_phase_split as P  # noqa: E402

LIB = "/x/libft8.so"
MAP = "/tmp/perf-123.map"


def stack(*names):
    """leaf first; a name 'sym@dso' gives the dso, default libft8.so"""
    out = []
    for n in names:
        s, _, d = n.partition("@")
        out.append((s, d or LIB))
    return out


def test_fit_with_kiss_fft_under_freq_search():
    f = stack("kf_bfly4", "kiss_fft", "freq_search", "fine_fit_with_drift", "fit_signal_body", "ft8_subfeas_fit_signal", "ShimCall@" + MAP, "RunCore@" + MAP)
    assert P.classify(f) == ("fits", "kiss_fft") and P.kiss_by_parent(f) == "freq_search"


def test_fit_trig_and_correlation_and_other():
    assert P.classify(stack("__sincos_fma", "apply_freq_shift", "fine_fit_with_drift", "ft8_subfeas_fit_signal")) == ("fits", "trig")
    assert P.classify(stack("sin", "r_fit_drift", "fine_fit_with_drift", "ft8_subfeas_fit_signal")) == ("fits", "trig")
    assert P.classify(stack("cos", "fine_fit_with_drift", "ft8_subfeas_fit_signal")) == ("fits", "trig")      # a libm leaf is trig whoever calls it
    assert P.classify(stack("fine_fit_with_drift", "ft8_subfeas_fit_signal")) == ("fits", "step3_correlation")
    assert P.classify(stack("freq_search", "fine_fit_with_drift", "ft8_subfeas_fit_signal")) == ("fits", "freq_search_self")
    assert P.classify(stack("lp_envelope", "fit_signal_body", "ft8_subfeas_fit_signal")) == ("fits", "lp_envelope_self")
    assert P.classify(stack("memcpy", "fit_signal_body", "ft8_subfeas_fit_signal")) == ("fits", "fits_other")


def test_decode_phases_residual_vs_pass0():
    res = stack("ldpc_decode", "ft8_decode_all", "Ft8LibInterop::DecodeAll@" + MAP, "SubtractionPass::RunCore@" + MAP)
    p0 = stack("ldpc_decode", "ft8_decode_all", "Ft8LibInterop::DecodeAll@" + MAP, "Ft8Decoder::DecodeTwoStageAsync@" + MAP)
    assert P.classify(res) == ("residual_decode", None) and P.classify(p0) == ("pass0_decode", None)
    assert P.classify(stack("compute_candidates", "ft8_subfeas_compute_analytic", "x@" + MAP)) == ("analytic", None)


def test_managed_other_and_unresolved():
    assert P.classify(stack("OpenWSFZ.Ft8.Ft8Decoder::Merge@" + MAP))[0] == "managed"
    assert P.classify(stack("memset@/lib/libc.so.6"))[0] == "other"
    assert P.classify(stack("[unknown]", "ft8_subfeas_fit_signal"))[0] == "unresolved"          # the leaf decides OC-V2
    assert P.classify(stack("0x7f12ab", "x"))[0] == "unresolved"


def test_parse_and_summarise_sum_to_100():
    dump = """\t    7f01 kf_bfly4 (/x/libft8.so)
\t    7f02 kiss_fft (/x/libft8.so)
\t    7f03 freq_search+0x1a (/x/libft8.so)
\t    7f04 ft8_subfeas_fit_signal (/x/libft8.so)

\t    7f11 ldpc_decode (/x/libft8.so)
\t    7f12 ft8_decode_all (/x/libft8.so)
\t    7f13 SubtractionPass::RunCore (/tmp/perf-9.map)

\t    7f21 [unknown] ([unknown])

\t    7f31 memcpy (/lib/libc.so.6)
"""
    samples = list(P.parse_dump(dump.splitlines()))
    assert len(samples) == 4 and samples[0][2] == ("freq_search", "/x/libft8.so")                # the +0x offset is stripped
    r = P.summarise(samples)
    assert r["samples"] == 4 and r["phase_pct_sum"] == 100.0
    assert r["phase_pct"]["fits"] == 25.0 and r["phase_pct"]["residual_decode"] == 25.0
    assert r["phase_pct"]["unresolved"] == 25.0 and r["phase_pct"]["other"] == 25.0
    assert r["fits_inner_pct_of_all_samples"]["kiss_fft"] == 25.0 and r["kiss_fft_by_parent_pct_of_all_samples"] == {"freq_search": 25.0}
    assert abs(sum(r["fits_inner_pct_of_all_samples"].values()) - r["phase_pct"]["fits"]) < 1e-9
    assert r["top_self_symbols_pct"][0][1] == 25.0
