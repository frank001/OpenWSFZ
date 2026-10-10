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


# ── 2026-10-02: no duplicate OpenWSFZ WAVs on disk (artefacts 20260925_2010 and 20260930_1930) ──

from datetime import datetime, timedelta  # noqa: E402

_WAV_START = datetime(2026, 1, 1, 12, 0, 0)
_WAV_END = datetime(2026, 1, 1, 12, 1, 0)
_NO_PAD = timedelta(seconds=0)


def _make_wavs(src: Path) -> dict[str, bytes]:
    src.mkdir(parents=True, exist_ok=True)
    made = {}
    for name, payload in ((IN_WINDOW_TS + ".wav", b"RIFF-in-window"), ("260101_130000.wav", b"RIFF-outside")):
        (src / name).write_bytes(payload)
        made[name] = payload
    return made


def test_copy_mode_leaves_the_source_in_place(tmp_path):
    src, dst = tmp_path / "cycle-audio", tmp_path / "gathered" / "owsfz" / "wav"
    made = _make_wavs(src)
    n = gla.copy_wav_window(src, dst, _WAV_START, _WAV_END, _NO_PAD, mode="copy")
    assert n == 1
    assert (dst / (IN_WINDOW_TS + ".wav")).read_bytes() == made[IN_WINDOW_TS + ".wav"]
    assert (src / (IN_WINDOW_TS + ".wav")).exists(), "copy must not remove the source"


def test_move_mode_removes_the_source_and_keeps_the_bytes(tmp_path):
    src, dst = tmp_path / "cycle-audio", tmp_path / "gathered" / "owsfz" / "wav"
    made = _make_wavs(src)
    n = gla.copy_wav_window(src, dst, _WAV_START, _WAV_END, _NO_PAD, mode="move")
    assert n == 1
    assert (dst / (IN_WINDOW_TS + ".wav")).read_bytes() == made[IN_WINDOW_TS + ".wav"]
    assert not (src / (IN_WINDOW_TS + ".wav")).exists(), "move must leave no duplicate in the source"
    assert (src / "260101_130000.wav").exists(), "a WAV outside the window must not be touched"


def test_move_mode_split_by_band_removes_the_source(tmp_path):
    src, dst_root = tmp_path / "cycle-audio", tmp_path / "gathered" / "owsfz"
    made = _make_wavs(src)
    counts = gla.copy_wav_window_split_by_band(
        src, dst_root, _WAV_START, _WAV_END, _NO_PAD, {IN_WINDOW_TS + ".wav": "20m"}, mode="move")
    assert sum(counts.values()) == 1
    assert (dst_root / "20m" / "wav" / (IN_WINDOW_TS + ".wav")).read_bytes() == made[IN_WINDOW_TS + ".wav"]
    assert not (src / (IN_WINDOW_TS + ".wav")).exists()


def test_auto_moves_only_when_the_source_is_under_out_root(tmp_path):
    out_root = tmp_path / "artefacts"
    inside = out_root / "run" / "cycle-audio"
    outside = tmp_path / "appdata" / "cycle-audio"
    inside.mkdir(parents=True)
    outside.mkdir(parents=True)
    assert gla.resolve_wav_mode("auto", inside, out_root) == "move"
    assert gla.resolve_wav_mode("auto", outside, out_root) == "copy", (
        "a live archive outside the artefacts tree must never be emptied by default")
    assert gla.resolve_wav_mode("copy", inside, out_root) == "copy"
    assert gla.resolve_wav_mode("move", outside, out_root) == "move"
    with pytest.raises(ValueError):
        gla.resolve_wav_mode("bogus", inside, out_root)


def test_failed_cross_volume_move_never_loses_the_source(tmp_path, monkeypatch):
    src, dst = tmp_path / "a.wav", tmp_path / "out" / "a.wav"
    src.write_bytes(b"payload")
    dst.parent.mkdir()

    def _no_replace(*_a, **_k):
        raise OSError("cross-device")

    real_copy2 = gla.shutil.copy2

    def _short_copy(s, d):
        real_copy2(s, d)
        Path(d).write_bytes(b"short")          # a copy whose size does not verify

    monkeypatch.setattr(gla.os, "replace", _no_replace)
    monkeypatch.setattr(gla.shutil, "copy2", _short_copy)
    with pytest.raises(OSError):
        gla.transfer_wav(src, dst, "move")
    assert src.read_bytes() == b"payload", "the source must survive a copy whose size does not verify"
    assert not dst.exists(), "the bad partial copy must be removed"


# --- #194 section 11: the build comes from the run's own record, never the gatherer's checkout ---------

def test_build_info_uses_the_daemons_arm_config_not_the_checkout(tmp_path):
    arm = tmp_path / "arm_config.json"
    arm.write_text(
        '{"recorded_utc": "2026-09-23T10:33:00Z", "daemon": {"daemon_version": "0.52", "shim_version": 20260054, '
        '"dll_sha256": "38a21f84", "exe": "D:/w/OpenWSFZ.Daemon.exe", "commit": "84cac119"}}',
        encoding="utf-8",
    )
    text = gla.build_info(arm)
    assert "84cac119" in text and "38a21f84" in text and "20260054" in text and "0.52" in text
    assert "deliberately NOT used" in text
    assert gla.git_build_info() not in text


def test_build_info_without_a_record_says_not_recorded_and_labels_the_checkout():
    text = gla.build_info(None)
    assert text.startswith("**NOT RECORDED**") and "not necessarily the daemon build" in text
    unreadable = gla.build_info(Path("does-not-exist.json"))
    assert unreadable.startswith("**NOT RECORDED**")


def test_synthetic_run_contents_has_no_real_callsign_claim_and_no_todo_headline(tmp_path):
    s = _build_scenario(tmp_path, ["WSJT-X - A"])
    arm = tmp_path / "arm_config.json"
    arm.write_text('{"daemon": {"daemon_version": "0.54", "dll_sha256": "abc"}}', encoding="utf-8")
    argv = _base_argv(s, "WSJT-X - A", ["--synthetic-run", "--arm-config", str(arm)])
    assert gla.main(argv) == 0
    body = (s["out_root"] / "test_run" / "contents.md").read_text(encoding="utf-8")
    assert "SYNTHETIC R&R run" in body and "real third-party" not in body
    assert "Headline result\n\nSee the R&R report" in body
    assert "daemon version `0.54`" in body
