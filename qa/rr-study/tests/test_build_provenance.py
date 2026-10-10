"""The report header must name the daemon BUILD (arm_config.json), and a run without one is refused loudly
(Architect, 2026-10-03; HK-022: the analyser's header named the analysis worktree's HEAD four times)."""
import json
import sys
from pathlib import Path

import pytest

RR = Path(__file__).resolve().parents[1]
for p in (str(RR), str(RR / "harness")):
    if p not in sys.path:
        sys.path.insert(0, p)

from harness import analyse as A  # noqa: E402
import run_study as RS  # noqa: E402

COMMIT = "cddd7e340d922abddefbbe1dc9ff35e76ec93e7d"
HEAD = "96077a0f4814baeba983bce2bd0ed18221838cfc"


def _arm(run_dir, commit=COMMIT, flag=True):
    arm = {"build": {"commit": commit},
           "daemon": {"dll_sha256": "ee00d118" + "0" * 56, "shim_version": 20260056, "daemon_version": "0.54",
                      "decoder_readback": {"subtractionEnabled": flag, "subtractionMaxThreads": 0, "osdNhardMax": 40}}}
    (run_dir / "arm_config.json").write_text(json.dumps(arm), encoding="utf-8")


def test_header_names_the_build_not_the_analysis_head(tmp_path):
    _arm(tmp_path)
    rows = "\n".join(A._header_sha_rows(tmp_path, HEAD))
    assert COMMIT in rows and "`libft8.dll` SHA-256" in rows and "subtractionEnabled" in rows
    assert HEAD[:8] in rows                      # the HEAD is still disclosed, as the tooling commit
    assert rows.index(COMMIT) < rows.index(HEAD[:8])


def test_header_without_arm_config_says_not_verified(tmp_path):
    rows = "\n".join(A._header_sha_rows(tmp_path, HEAD))
    assert "NOT VERIFIED" in rows


def test_analyser_refuses_a_run_without_a_build_commit(tmp_path):
    with pytest.raises(SystemExit) as e:
        A._require_build_provenance(tmp_path, allow_legacy=False)
    assert "arm_config.json" in str(e.value)
    (tmp_path / "arm_config.json").write_text(json.dumps({"build": {}}), encoding="utf-8")
    with pytest.raises(SystemExit):
        A._require_build_provenance(tmp_path, allow_legacy=False)


def test_analyser_accepts_a_run_with_a_build_commit_and_the_explicit_legacy_flag(tmp_path):
    A._require_build_provenance(tmp_path, allow_legacy=True)            # old dir, explicit flag
    _arm(tmp_path)
    A._require_build_provenance(tmp_path, allow_legacy=False)


def test_run_study_reads_flag_state_and_build_from_arm_config(tmp_path):
    _arm(tmp_path, flag=True)
    a = RS._load_arm_config(tmp_path)
    assert a["commit"] == COMMIT and a["subtraction_enabled"] == "true" and a["dll_sha256"].startswith("ee00d118")
    _arm(tmp_path, flag=False)
    assert RS._load_arm_config(tmp_path)["subtraction_enabled"] == "false"
    (tmp_path / "arm_config.json").write_text(json.dumps({"build": {"commit": COMMIT}, "daemon": {}}), encoding="utf-8")
    assert RS._load_arm_config(tmp_path)["subtraction_enabled"] == "unknown"        # never guessed
    assert RS._load_arm_config(tmp_path / "missing") == {}
