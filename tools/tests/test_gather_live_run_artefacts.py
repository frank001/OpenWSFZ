"""Tests for tools/gather_live_run_artefacts.py's G1 provenance/guard behaviour.

G1 (qa/cycleframer-alignment-replay/2026-08-10-1559-architect-to-qa-spec-g1-gather-tool-
reference-provenance-guard.md §4): there were no tests for this tool at all before this file.
These cover the defect's fix -- the --wsjtx-link-from premise guard (§3.3), the operator
override (--wsjtx-shared-install), and the provenance recorded into contents.md (§3.2) -- using
only synthetic tmp_path fixtures, no live WSJT-X install required.

Run with: python -m pytest tools/tests/test_gather_live_run_artefacts.py -v
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gather_live_run_artefacts as gla  # noqa: E402


START = "2026-01-01 12:00:00"
END = "2026-01-01 12:01:00"
IN_WINDOW_TS = "260101_120030"  # matches TS_FMT, falls inside [START, END]


def _write_alltxt(path: Path, ts: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"{ts}     14.074 Rx FT8   -10  0.1  1234 ~  CQ TEST AB1CD FN42\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _build_scenario(tmp_path: Path, live_instance_names: list[str]) -> dict:
    """Common fixture layout for every test below.

    tmp_path/
        home/<live_instance_names...>/ALL.TXT   -- candidate LIVE WSJT-X installs (§3.3 scans
                                                     these; only the ones with an in-window
                                                     decode line count as "active")
        prior_gather/wsjt-x/ALL.TXT + wav/one.wav -- an already-gathered sibling run's wsjt-x/
                                                     folder, the --wsjtx-link-from source
        owsfz/ALL.TXT                             -- OpenWSFZ's own live decode log
        logs/, cycle-audio/                       -- empty, just so nothing errors
        out/                                       -- --out-root
    """
    home = tmp_path / "home"
    for inst in live_instance_names:
        _write_alltxt(home / inst / "ALL.TXT", IN_WINDOW_TS)

    prior_gather = tmp_path / "prior_gather" / "wsjt-x"
    _write_alltxt(prior_gather / "ALL.TXT", IN_WINDOW_TS)
    (prior_gather / "wav").mkdir(parents=True, exist_ok=True)
    (prior_gather / "wav" / f"{IN_WINDOW_TS}.wav").write_bytes(b"RIFF....fake-wav-bytes....")

    owsfz_alltxt = tmp_path / "owsfz" / "ALL.TXT"
    _write_alltxt(owsfz_alltxt, IN_WINDOW_TS)

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    cycle_audio_dir = tmp_path / "cycle-audio"
    cycle_audio_dir.mkdir(parents=True, exist_ok=True)
    owsfz_config = tmp_path / "config.json"
    owsfz_config.write_text("{}", encoding="utf-8")

    out_root = tmp_path / "out"

    return dict(
        home=home,
        prior_gather=prior_gather,
        owsfz_alltxt=owsfz_alltxt,
        logs_dir=logs_dir,
        cycle_audio_dir=cycle_audio_dir,
        owsfz_config=owsfz_config,
        out_root=out_root,
    )


def _base_argv(s: dict, wsjtx_root_instance: str, extra: list[str] | None = None) -> list[str]:
    argv = [
        "--start", START,
        "--end", END,
        "--name", "test_run",
        "--out-root", str(s["out_root"]),
        "--owsfz-alltxt", str(s["owsfz_alltxt"]),
        "--owsfz-log-dir", str(s["logs_dir"]),
        "--owsfz-cycle-audio-dir", str(s["cycle_audio_dir"]),
        "--owsfz-config", str(s["owsfz_config"]),
        "--wsjtx-root", str(s["home"] / wsjtx_root_instance),
        "--wsjtx-link-from", str(s["prior_gather"]),
    ]
    if extra:
        argv += extra
    return argv


# ── 1. two window-active instances, no assertion -> refuse, name both ──────────────────────


def test_two_active_instances_refused_without_assertion(tmp_path, capsys):
    s = _build_scenario(tmp_path, ["WSJT-X - A", "WSJT-X - B"])
    argv = _base_argv(s, "WSJT-X - A")

    rc = gla.main(argv)

    assert rc == 1
    err = capsys.readouterr().err
    assert "WSJT-X - A" in err
    assert "WSJT-X - B" in err
    assert "2 candidate WSJT-X installs" in err
    # Nothing should have been written -- the guard fires before any copying.
    assert not (s["out_root"] / "test_run").exists()


# ── 2. two window-active instances, WITH --wsjtx-shared-install -> succeeds, recorded ───────


def test_two_active_instances_succeeds_with_shared_install_flag(tmp_path):
    s = _build_scenario(tmp_path, ["WSJT-X - A", "WSJT-X - B"])
    argv = _base_argv(s, "WSJT-X - A", extra=["--wsjtx-shared-install"])

    rc = gla.main(argv)

    assert rc == 0
    contents = (s["out_root"] / "test_run" / "contents.md").read_text(encoding="utf-8")
    assert gla.SHARED_INSTALL_ASSERTION_MARKER in contents


# ── 3. exactly one window-active instance (the 2026-07-31 case) -> succeeds, hardlinks ──────


def test_one_active_instance_succeeds_and_links(tmp_path):
    s = _build_scenario(tmp_path, ["WSJT-X - A"])
    argv = _base_argv(s, "WSJT-X - A")

    rc = gla.main(argv)

    assert rc == 0
    out_wsjtx = s["out_root"] / "test_run" / "wsjt-x"
    assert (out_wsjtx / "ALL.TXT").is_file()
    assert (out_wsjtx / "wav" / f"{IN_WINDOW_TS}.wav").is_file()

    contents = (s["out_root"] / "test_run" / "contents.md").read_text(encoding="utf-8")
    assert str(s["prior_gather"].resolve()) in contents
    assert "hardlinked from sibling gather" in contents


# ── 4. provenance block present, and its recorded hash matches the file on disk ─────────────


def test_provenance_hash_matches_gathered_file(tmp_path):
    s = _build_scenario(tmp_path, ["WSJT-X - A"])
    argv = _base_argv(s, "WSJT-X - A")

    rc = gla.main(argv)
    assert rc == 0

    out_dir = s["out_root"] / "test_run"
    contents = (out_dir / "contents.md").read_text(encoding="utf-8")
    assert "## WSJT-X / OpenWSFZ provenance (G1)" in contents

    gathered_alltxt = out_dir / "wsjt-x" / "ALL.TXT"
    actual_hash = _sha256(gathered_alltxt)
    assert actual_hash in contents

    # And it must be the SAME bytes as the --wsjtx-link-from source (hardlink or copy, either
    # way the content must be identical -- this is the check that would have caught G1's own
    # defect, where the wrong instance's ALL.TXT ended up in the folder).
    assert actual_hash == _sha256(s["prior_gather"] / "ALL.TXT")

    owsfz_hash = _sha256(out_dir / "owsfz" / "ALL.TXT")
    assert owsfz_hash in contents


# ── Bonus: --dry-run must not create the output folder even on the success path ─────────────


def test_dry_run_creates_nothing(tmp_path):
    s = _build_scenario(tmp_path, ["WSJT-X - A"])
    argv = _base_argv(s, "WSJT-X - A", extra=["--dry-run"])

    rc = gla.main(argv)

    assert rc == 0
    assert not (s["out_root"] / "test_run").exists()


# ── §3.5: the default --wsjtx-root warns when a named sibling has the real data ─────────────


def test_default_wsjtx_root_warns_when_a_sibling_has_the_data(tmp_path, monkeypatch, capsys):
    s = _build_scenario(tmp_path, [])
    # The "plain" default install exists but has NO in-window decodes; a named sibling does.
    (s["home"] / "WSJT-X").mkdir(parents=True, exist_ok=True)
    (s["home"] / "WSJT-X" / "ALL.TXT").write_text("", encoding="utf-8")
    _write_alltxt(s["home"] / "WSJT-X - Real" / "ALL.TXT", IN_WINDOW_TS)
    monkeypatch.setattr(gla, "platform_localappdata_root", lambda: s["home"])

    argv = [
        "--start", START, "--end", END, "--name", "test_run",
        "--out-root", str(s["out_root"]),
        "--owsfz-alltxt", str(s["owsfz_alltxt"]),
        "--owsfz-log-dir", str(s["logs_dir"]),
        "--owsfz-cycle-audio-dir", str(s["cycle_audio_dir"]),
        "--owsfz-config", str(s["owsfz_config"]),
        # --wsjtx-root deliberately omitted -> exercises the default path.
    ]
    rc = gla.main(argv)

    assert rc == 0  # warning, not fatal
    err = capsys.readouterr().err
    assert "ZERO decodes" in err
    assert "WSJT-X - Real" in err


# ── §3.4: two independent direct gathers colliding on the same live install warns ───────────


def test_sibling_gather_collision_warns(tmp_path, capsys):
    s = _build_scenario(tmp_path, ["WSJT-X - A"])

    def direct_argv(name: str) -> list[str]:
        return [
            "--start", START, "--end", END, "--name", name,
            "--out-root", str(s["out_root"]),
            "--owsfz-alltxt", str(s["owsfz_alltxt"]),
            "--owsfz-log-dir", str(s["logs_dir"]),
            "--owsfz-cycle-audio-dir", str(s["cycle_audio_dir"]),
            "--owsfz-config", str(s["owsfz_config"]),
            "--wsjtx-root", str(s["home"] / "WSJT-X - A"),
        ]

    assert gla.main(direct_argv("run_one")) == 0
    capsys.readouterr()  # discard first run's own output

    rc = gla.main(direct_argv("run_two"))

    assert rc == 0  # warning, not fatal
    err = capsys.readouterr().err
    assert "G1 defect signature" in err
    assert "run_one" in err


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
