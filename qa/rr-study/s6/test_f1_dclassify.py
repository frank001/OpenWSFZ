"""Unit tests for f1_dclassify: synthetic sampler traces for L1, L2, an idle trace and a short trace; each must be able to fail (HK-025 k)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import f1_dclassify as F  # noqa: E402

T_OV = 1000.0


def trace(state, wchan, delay_per_s_ns=0, n=30, start=T_OV - 3.0):
    return [{"t": start + i * 0.1, "pid": 1, "state": state, "wchan": wchan, "run_ns": 0, "wait_ns": int(i * 0.1 * delay_per_s_ns)} for i in range(n + 1)]


def test_blocked_writing_to_a_pipe_is_l2():
    assert F.classify(trace("S", "pipe_write"), T_OV)["class"] == "L2"


def test_runnable_with_rising_run_delay_is_l1():
    assert F.classify(trace("R", "0", delay_per_s_ns=0.8e9), T_OV)["class"] == "L1"


def test_runnable_without_run_delay_is_not_l1():
    assert F.classify(trace("R", "0", delay_per_s_ns=0.1e9), T_OV)["class"] == "unclassified"


def test_sleeping_in_alsa_wait_is_unclassified():
    assert F.classify(trace("S", "snd_pcm_wait"), T_OV)["class"] == "unclassified"


def test_a_short_trace_is_no_trace():
    assert F.classify(trace("S", "pipe_write", n=5), T_OV)["class"] == "no trace"
