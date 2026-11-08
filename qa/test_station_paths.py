"""Tests for station_paths (stdlib unittest; no station, radio, Voicemeeter or sol).

Run: python -I qa/test_station_paths.py   (or python -m unittest from qa/)
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import station_paths as sp  # noqa: E402

_ENV_KEYS = ("USERPROFILE", "LOCALAPPDATA", "APPDATA",
             sp.ENV_WSJTX_ALL_TXT, sp.ENV_WSJTX_INI, sp.ENV_STATION_CONFIG)


class _Env(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in _ENV_KEYS}
        for k in (sp.ENV_WSJTX_ALL_TXT, sp.ENV_WSJTX_INI, sp.ENV_STATION_CONFIG):
            os.environ.pop(k, None)
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "frans"
        (self.home / "AppData" / "Local").mkdir(parents=True)
        (self.home / "AppData" / "Roaming").mkdir(parents=True)
        os.environ["USERPROFILE"] = str(self.home)
        os.environ["LOCALAPPDATA"] = str(self.home / "AppData" / "Local")
        os.environ["APPDATA"] = str(self.home / "AppData" / "Roaming")

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()


class ResolverTests(_Env):
    def test_default_and_rig_folders_are_kept_distinct(self):
        la = self.home / "AppData" / "Local"
        self.assertEqual(sp.wsjtx_all_txt(), la / "WSJT-X" / "ALL.TXT")
        self.assertEqual(sp.wsjtx_all_txt("FT991A"), la / "WSJT-X - FT991A" / "ALL.TXT")
        self.assertEqual(sp.wsjtx_ini("FT991A"), la / "WSJT-X - FT991A" / "WSJT-X - FT991A.ini")
        self.assertEqual(sp.station_config(), self.home / "AppData" / "Roaming" / "OpenWSFZ" / "config.json")

    def test_no_hardcoded_user_name(self):
        for p in (sp.wsjtx_all_txt(), sp.wsjtx_ini("FT991A"), sp.station_config()):
            rel = p.relative_to(self.home)            # the temp dir itself may sit under Frank
            self.assertNotIn("Frank", str(rel))
            self.assertTrue(is_home := str(p).startswith(str(self.home)))

    def test_env_overrides(self):
        os.environ[sp.ENV_WSJTX_ALL_TXT] = str(Path(self.tmp.name) / "x" / "ALL.TXT")
        self.assertEqual(sp.wsjtx_all_txt("FT991A"), Path(self.tmp.name) / "x" / "ALL.TXT")


class StaleGuardTests(_Env):
    def test_path_outside_profile_is_refused(self):
        other = Path(self.tmp.name) / "Frank" / "AppData" / "Local" / "WSJT-X" / "ALL.TXT"  # fake path
        with self.assertRaises(sp.StaleLogError) as cm:
            sp.check_in_profile(other)
        self.assertIn("outside the running account's profile", str(cm.exception))

    def test_explicit_outside_profile_is_allowed(self):
        other = Path(self.tmp.name) / "Frank" / "ALL.TXT"
        sp.check_in_profile(other, explicit=True)

    def test_env_override_counts_as_explicit(self):
        other = Path(self.tmp.name) / "Frank" / "ALL.TXT"
        os.environ[sp.ENV_WSJTX_ALL_TXT] = str(other)
        sp.check_in_profile(sp.wsjtx_all_txt())

    def test_inside_profile_passes_and_prefix_sibling_does_not(self):
        sp.check_in_profile(sp.wsjtx_all_txt())
        sibling = Path(str(self.home) + "2") / "ALL.TXT"   # 'frans2' shares the string prefix 'frans'
        with self.assertRaises(sp.StaleLogError):
            sp.check_in_profile(sibling)

    def test_missing_file_is_a_message(self):
        with self.assertRaises(sp.StaleLogError) as cm:
            sp.check_fresh_start(sp.wsjtx_all_txt())
        self.assertIn("Monitor ON", str(cm.exception))

    def test_growth_watch(self):
        f = self.home / "ALL.TXT"
        f.write_bytes(b"a\n")
        w = sp.guard_run_start(f)
        with self.assertRaises(sp.StaleLogError) as cm:      # frozen
            w.verify()
        self.assertIn("did not grow", str(cm.exception))
        with open(f, "ab") as fh:
            fh.write(b"b\n")
        self.assertEqual(w.verify(), 2)                      # grew
        f.write_bytes(b"")                                     # shrank
        with self.assertRaises(sp.StaleLogError) as cm:
            w.verify()
        self.assertIn("SHRANK", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
