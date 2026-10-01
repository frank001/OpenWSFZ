"""Tests for qa/config_drift.py (Part E of config-save-preserves-unsent-settings).

All callsigns/paths below are synthetic (NFR-021). The privacy tests plant a recognisable
canary in every non-allowlisted watched value and assert it never reaches a log or report row.
"""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config_drift as cd  # noqa: E402

CANARY_DIR = "D:/canary-archive-dir-QZZZZ"


def cfg(mode="all", directory=CANARY_DIR, decoding=True, nhard=40, **extra):
    c = {
        "decodingEnabled": decoding,
        "cycleAudioArchive": {"mode": mode, "directory": directory, "maxSizeMb": 2048},
        "decoder": {"kMinScorePass2": 12, "osdNhardMax": nhard, "nhard40MigrationApplied": True},
        "tx": {"callsign": "QA1ZZZ"},
    }
    c.update(extra)
    return c


class Rig:
    """A DriftWatcher wired to a mutable fake config and captured log/report."""
    def __init__(self, **kw):
        self.current = cfg(**kw)
        self.lines, self.rows = [], []
        self.w = cd.DriftWatcher(lambda: self.current, self.lines.append, self.rows.append)
        self.w.snapshot()

    @property
    def text(self):
        return "\n".join(self.lines) + json.dumps(self.rows)


def test_no_change_no_drift():
    r = Rig()
    assert r.w.poll() == []
    assert not r.w.drift_seen
    assert not any("CONFIG-DRIFT" in l for l in r.lines)


def test_archive_mode_drift_reports_values():
    r = Rig(mode="all")
    r.current = cfg(mode="off")
    new = r.w.poll()
    assert [d.path for d in new] == ["cycleAudioArchive.mode"]
    assert any('CONFIG-DRIFT cycleAudioArchive.mode ("all"->"off")' in l for l in r.lines)
    assert r.rows[0]["event"] == "CONFIG-DRIFT" and r.rows[0]["old"] == "all" and r.rows[0]["new"] == "off"
    assert r.w.drift_seen


def test_decoding_enabled_and_decoder_values_are_watched():
    r = Rig()
    r.current = cfg(decoding=False, nhard=60)
    paths = sorted(d.path for d in r.w.poll())
    assert paths == ["decoder.osdNhardMax", "decodingEnabled"]
    assert any('decoder.osdNhardMax (40->60)' in l for l in r.lines)


def test_directory_drift_is_path_only_never_the_value():
    r = Rig()
    r.current = cfg(directory="D:/other-canary-QYYYYY")
    r.w.poll()
    assert any("CONFIG-DRIFT cycleAudioArchive.directory" in l for l in r.lines)
    assert "canary" not in r.text          # neither old nor new path leaks
    assert "old" not in r.rows[0] and "new" not in r.rows[0]


def test_unwatched_change_is_ignored_and_never_logged():
    r = Rig()
    r.current = cfg(tx={"callsign": "QA1YYY"})
    assert r.w.poll() == []
    assert "QA1" not in r.text


def test_snapshot_line_never_contains_values():
    r = Rig()
    assert "canary" not in r.lines[0] and "watching" in r.lines[0]


def test_same_drift_reported_once_not_every_poll():
    r = Rig(mode="all")
    r.current = cfg(mode="off")
    assert len(r.w.poll()) == 1
    assert r.w.poll() == [] and r.w.poll() == []
    assert sum("CONFIG-DRIFT" in l for l in r.lines) == 1


def test_further_change_of_a_drifted_key_is_reported_again():
    r = Rig(mode="all")
    r.current = cfg(mode="off")
    r.w.poll()
    r.current = cfg(mode="decoded")
    assert len(r.w.poll()) == 1
    assert any('("all"->"decoded")' in l for l in r.lines)


def test_return_to_start_value_logs_restored_and_is_not_repeated():
    r = Rig(mode="all")
    r.current = cfg(mode="off")
    r.w.poll()
    r.current = cfg(mode="all")
    assert r.w.poll() == []
    assert sum("CONFIG-RESTORED cycleAudioArchive.mode" in l for l in r.lines) == 1
    r.w.poll()
    assert sum("CONFIG-RESTORED" in l for l in r.lines) == 1
    assert r.w.drift_seen  # history is kept: the run WAS drifted


def test_key_removed_from_config_is_drift_not_a_crash():
    r = Rig()
    r.current = {"decodingEnabled": True}
    paths = {d.path for d in r.w.poll()}
    assert "cycleAudioArchive.mode" in paths and "decoder.osdNhardMax" in paths


def test_poll_failure_is_logged_but_is_not_drift():
    r = Rig()

    def boom():
        raise ConnectionError("down")
    r.w._fetch = boom
    assert r.w.poll() == []
    assert not r.w.drift_seen and r.w.poll_failures == 1
    assert any("CONFIG-POLL-FAILED ConnectionError" in l for l in r.lines)


def test_watcher_never_writes_back():
    """A silent repair would hide the event: the only fetch is a read (no POST path exists)."""
    src = Path(cd.__file__).read_text(encoding="utf-8")
    assert "POST" not in src and "method=" not in src and "data=" not in src


def test_run_abort_on_drift_returns_exit_3():
    r = Rig(mode="all")
    r.current = cfg(mode="off")
    stop = threading.Event()
    assert r.w.run(0.01, stop, abort_on_drift=True) == cd.EXIT_DRIFT


def test_run_stops_cleanly_when_told():
    r = Rig()
    stop = threading.Event()
    threading.Timer(0.05, stop.set).start()
    assert r.w.run(0.01, stop) == cd.EXIT_OK


def test_interval_is_clamped_to_five_minutes():
    assert cd._clamp_interval(10_000) == cd.MAX_INTERVAL_S
    assert cd._clamp_interval(0) == 1.0
    assert cd._clamp_interval(60) == 60


def test_flatten_treats_lists_and_empty_objects_as_leaves():
    flat = cd.flatten({"a": {"b": [1, 2], "c": {}}, "d": None})
    assert flat == {"a.b": [1, 2], "a.c": {}, "d": None}


# ── real HTTP, real main() ─────────────────────────────────────────────────────────────────────
class _Handler(BaseHTTPRequestHandler):
    body = cfg()

    def do_GET(self):
        if self.path != "/api/v1/config":
            self.send_error(404)
            return
        data = json.dumps(type(self).body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


@pytest.fixture
def server():
    _Handler.body = cfg(mode="all")
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_main_detects_drift_over_http_and_writes_log_snapshot_report(server, tmp_path):
    log, snap, rep = tmp_path / "d.log", tmp_path / "s.json", tmp_path / "r.jsonl"
    threading.Timer(0.15, lambda: setattr(_Handler, "body", cfg(mode="off"))).start()
    rc = cd.main(["--base-url", server, "--interval", "1", "--log", str(log),
                  "--snapshot", str(snap), "--report", str(rep), "--abort-on-drift"])
    assert rc == cd.EXIT_DRIFT
    assert "CONFIG-DRIFT cycleAudioArchive.mode" in log.read_text()
    assert json.loads(snap.read_text())["cycleAudioArchive.mode"] == "all"
    assert json.loads(rep.read_text().splitlines()[0])["new"] == "off"


def test_main_returns_2_when_no_start_snapshot(tmp_path):
    log = tmp_path / "d.log"
    rc = cd.main(["--base-url", "http://127.0.0.1:9", "--log", str(log)])
    assert rc == cd.EXIT_NO_SNAPSHOT
    assert "CONFIG-SNAPSHOT-FAILED" in log.read_text()
