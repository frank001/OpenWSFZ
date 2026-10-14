"""Per-sweep monitoring summary (2026-10-14). Synthetic folders only, no message text."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "linux"))
sys.path.insert(0, str(ROOT / "s6"))

import monitoring_summary as MS  # noqa: E402


def smp(t, ok=True, age=5.0, wpid=100, rss="200000 kB", susp=1000.0, alsa="state: RUNNING", load=1.2, aplay=0):
    return {"t": t, "ok": ok, "reason": "ok" if ok else "no new save WAV for 60 s", "wav_age_s": age, "wav_count": 10, "wsjtx": [{"pid": wpid, "state": "S", "rss_kb": rss, "threads": "10"}],
            "jt9": [{"pid": 101, "state": "S", "rss_kb": "1 kB", "threads": "1"}], "aplay": {"count": aplay, "oldest_s": 3.0 if aplay else None}, "alsa": {"card0/pcm0c/sub0/status": alsa},
            "suspended_s": susp, "load1": load, "owsfz_archive_age_s": 4.0}


def test_monitor_summary_counts_stalls_restarts_and_sleep():
    ss = [smp("2026-10-14T10:00:00Z"), smp("2026-10-14T10:00:15Z", age=40.0), smp("2026-10-14T10:00:30Z", ok=False, age=61.0, alsa="state: XRUN"),
          smp("2026-10-14T10:01:00Z", wpid=200, rss="150000 kB", susp=1030.5, aplay=1)]
    ev = [{"t": "2026-10-14T10:00:30Z", "reason": "no new save WAV for 61 s", "snapshot": "/x/stall-2026-10-14T100030Z"}]
    r = MS.summarise_monitor(ss, ev)
    assert r["samples"] == 4 and r["samples_not_ok"] == 1 and r["stall_episodes"] == 1 and r["stalls"][0]["snapshot"] == "stall-2026-10-14T100030Z"
    assert r["wsjtx_pids"] == [100, 200] and r["wsjtx_restarts_during_monitoring"] == 1 and r["wsjtx_rss_kb"] == {"first": 200000, "last": 150000, "max": 200000}
    assert r["wav_age_s"]["max"] == 61.0 and r["max_gap_s"] == 30.0 and r["gaps_over_2x_interval"] == 0
    assert r["suspended_s"] == {"first": 1000.0, "last": 1030.5, "delta": 30.5}                 # a sleep during the run shows as a delta
    assert r["alsa_states"]["card0/pcm0c/sub0/status"] == {"state: RUNNING": 3, "state: XRUN": 1}
    assert r["aplay"]["max_count"] == 1 and r["host_load1"]["max"] == 1.2 and r["owsfz_archive_age_s_max"] == 4.0


def test_monitor_summary_without_a_log_says_so():
    assert MS.summarise_monitor([], [])["samples"] == 0


def test_coverage_rows_are_read_from_the_report():
    md = "| Coverage (validity) | S1/WSJT-X | 30 of 30 cycles with data (needs >= 29) | PASS |\n| Coverage (validity) | S4/WSJT-X | 7 of 15 cycles with data (needs >= 14) | INVALID |\n| other | x | y | PASS |\n"
    rows = MS.coverage_rows_from_report(md)
    assert [r["verdict"] for r in rows] == ["PASS", "INVALID"] and rows[1]["scope"] == "S4/WSJT-X"


def test_summarise_run_reads_gate_stall_pins_and_replacement(tmp_path):
    sup, run = tmp_path / "sup", tmp_path / "run"
    sup.mkdir(); run.mkdir()
    (sup / "monitor.jsonl").write_text(json.dumps(smp("2026-10-14T10:00:00Z")) + "\n")
    (run / "liveness_gate.json").write_text(json.dumps({"first_reading_ok": True}))
    (run / "STALLED.json").write_text(json.dumps({"scenario": "S4", "reason": "no new save WAV"}))
    (run / "REPLACEMENT.json").write_text(json.dumps({"attempt": 2, "replaces": "x-INVALID-stall-attempt1"}))
    (run / "arm_config.json").write_text(json.dumps({"build": {"commit": "abc", "build_dirty": False}, "daemon": {"shim_version": 20260062, "dll_sha256": "dead", "decoder_readback": {"osdNhardMax": 24}}, "wsjtx": {"NDepth": 3}}))
    (run / "report.md").write_text("| Coverage (validity) | S1/OpenWSFZ | 30 of 30 cycles with data (needs >= 29) | PASS |\n")
    r = MS.summarise_run(str(sup), str(run), 2.0)
    assert r["M2_gate"]["stalled"] and r["M2_gate"]["gate_record"]["first_reading_ok"] and r["M3_coverage"]["rows_pass"] == 1
    assert r["build_pins"]["shim"] == 20260062 and r["build_pins"]["commit"] == "abc" and r["replacement"]["attempt"] == 2
    assert r["daemon_log"]["note"].startswith("no daemon") and r["S6_validity"] is None


def test_daemon_log_aggregates_counts_only(tmp_path):
    log = tmp_path / "daemon.stdout.log"
    log.write_text("\n".join([
        "[12:00:16 INF] Cycle 10:00:00: 12 decode(s) found, elapsed=900 ms.",
        "[12:00:21 INF] Sub-feas residual pass: residualDecodes=2 elapsedMs=3100 deadlineAbandoned=False containedException=False fittedSignals=9",
        "[12:00:50 INF] Cycle 10:00:15: 3 decode(s) found, elapsed=800 ms.",
        "[12:00:51 INF] Sub-feas residual pass: residualDecodes=0 elapsedMs=10400 deadlineAbandoned=True containedException=False fittedSignals=11",
        "[12:01:05 WRN] Cycle-grid realignment clamped: wanted 15000 samples (1.250 s), applied 3000 (0.250 s)"]) + "\n")
    r = MS.summarise_daemon_log(str(log), 2.0)
    assert r["cycles_logged"] == 2 and r["residual_passes"] == 2 and r["residual_abandoned"] == 1 and r["clamp_warnings"] == 1 and r["clamp_positive"] == 1
    assert r["late_cycles"] == 1 and r["residual_elapsed_ms"]["max"] == 10400
    assert "episodes" in r and "examples" not in json.dumps(r)
