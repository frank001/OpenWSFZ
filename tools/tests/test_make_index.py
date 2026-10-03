"""Tests for tools/make_index.py and the gatherer's index refresh (2026-10-03: the index was stale because
nothing called its generator).

Run with: python -m pytest tools/tests/test_make_index.py -v
"""
from __future__ import annotations

import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gather_live_run_artefacts as gla  # noqa: E402
import make_index  # noqa: E402


def _tree(root: Path) -> None:
    (root / "20260930_1930_endurance_run").mkdir(parents=True)
    (root / "20260930_1930_endurance_run-gathered").mkdir()
    (root / "rr_2026-10-01_onoff_replay").mkdir()
    (root / "speed_review.log").write_text("x")


def test_index_lists_every_entry_with_date_and_kind_and_skips_itself(tmp_path):
    _tree(tmp_path)
    (tmp_path / "INDEX.md").write_text("old")
    assert make_index.write_index(tmp_path) == 4
    text = (tmp_path / "INDEX.md").read_text(encoding="utf-8")
    assert "| 2026-09-30 | `20260930_1930_endurance_run/` | endurance run: raw run folder" in text
    assert "| 2026-09-30 | `20260930_1930_endurance_run-gathered/` | endurance run: gathered" in text
    assert "`rr_2026-10-01_onoff_replay/` | SUB-FEAS offline flag-OFF/ON replay" in text
    assert "`speed_review.log` | log or captured output" in text
    assert "`INDEX.md`" not in text


def test_index_is_rewritten_to_include_a_folder_added_after_it_was_generated(tmp_path):
    """The 2026-10-03 defect: a folder created after the last generation was missing from the index."""
    _tree(tmp_path)
    make_index.write_index(tmp_path)
    (tmp_path / "20261003_1200_endurance_run").mkdir()
    assert "20261003_1200_endurance_run" not in (tmp_path / "INDEX.md").read_text(encoding="utf-8")
    assert gla.refresh_artefacts_index(tmp_path) is True
    assert "`20261003_1200_endurance_run/`" in (tmp_path / "INDEX.md").read_text(encoding="utf-8")


def test_render_names_the_generator_and_the_date():
    text = make_index.render([("2026-09-30", "a/", "")], today=datetime.date(2026, 10, 3))
    assert "Generated 2026-10-03 by `tools/make_index.py`" in text


def test_no_index_flag_leaves_the_folder_untouched(tmp_path):
    _tree(tmp_path)
    assert gla.refresh_artefacts_index(tmp_path, skip=True) is False
    assert not (tmp_path / "INDEX.md").exists()


def test_an_index_failure_never_fails_the_gather(tmp_path, monkeypatch, capsys):
    def boom(_root):
        raise OSError("disk full")
    monkeypatch.setattr(make_index, "write_index", boom)
    assert gla.refresh_artefacts_index(tmp_path) is False          # reported, not raised
    assert "NOT refreshed" in capsys.readouterr().out


# ── the real gatherer path: main() refreshes the index, --no-index opts out ───────────────────
import test_gather_live_run_artefacts as tg  # noqa: E402


def test_gatherer_main_refreshes_the_index_with_the_new_run(tmp_path, capsys):
    s = tg._build_scenario(tmp_path, ["WSJT-X - A"])
    rc = gla.main(tg._base_argv(s, "WSJT-X - A"))
    assert rc == 0, capsys.readouterr().err
    idx = (s["out_root"] / "INDEX.md").read_text(encoding="utf-8")
    assert "`test_run/`" in idx                       # the run just gathered is listed
    assert "Refreshed" in capsys.readouterr().out


def test_gatherer_main_with_no_index_does_not_write_it(tmp_path, capsys):
    s = tg._build_scenario(tmp_path, ["WSJT-X - A"])
    rc = gla.main(tg._base_argv(s, "WSJT-X - A", ["--no-index"]))
    assert rc == 0, capsys.readouterr().err
    assert not (s["out_root"] / "INDEX.md").exists()
