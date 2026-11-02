"""Per-account station paths and the stale-log guard for QA live-run tools.

Why this exists (Architect task, Captain's go, 2026-11-02): project work moves from the
Windows account ``Frank`` to ``TBD\\frans``. A tool that hard-codes ``C:\\Users\\Frank\\...``
either fails under frans or, worse, reads Frank's frozen ``ALL.TXT`` WITHOUT AN ERROR, so the
run's WSJT-X decodes are silently absent from the comparison. This module removes the hard-coded
paths and makes the second failure mechanically impossible.

Resolution (no hard-coded user name anywhere):
  * ``%LOCALAPPDATA%`` / ``%APPDATA%`` of the RUNNING account (home-dir fallback if unset).
  * rig-name folders are unchanged: ``WSJT-X`` (rig_name None) or ``WSJT-X - <rig>``.
  * explicit overrides, highest priority first: the caller's CLI value, then the environment
    (``QA_WSJTX_ALL_TXT``, ``QA_WSJTX_INI``, ``QA_STATION_CONFIG``).

The stale-file predicate (all three are code, not prose; HK-021):
  1. ``check_in_profile(path, explicit=...)``: refuse when the resolved WSJT-X log lies outside the
     running user's profile directory, unless the path was given explicitly (CLI/env).
  2. ``check_fresh_start(path)``: a missing file is a clear message, not a traceback.
  3. ``GrowthWatch(path)``: ``start()`` records the size; ``verify()`` raises unless the file's size
     is STRICTLY greater than at start. A file that shrank (rotated or replaced) is reported apart.

Stdlib only. Importable from any QA script by putting ``qa/`` on ``sys.path``.
"""
from __future__ import annotations

import os
from pathlib import Path

ENV_WSJTX_ALL_TXT = "QA_WSJTX_ALL_TXT"
ENV_WSJTX_INI = "QA_WSJTX_INI"
ENV_STATION_CONFIG = "QA_STATION_CONFIG"
DEFAULT_WSJTX_FOLDER = "WSJT-X"
STATION_CONFIG_FOLDER = "OpenWSFZ"
ALL_TXT_NAME = "ALL.TXT"


class StaleLogError(RuntimeError):
    """The WSJT-X log cannot be trusted for this run; the message says why and what to do."""


def user_profile() -> Path:
    """The running account's profile directory (%USERPROFILE% on Windows, $HOME elsewhere)."""
    return Path(os.environ.get("USERPROFILE") or Path.home())


def local_appdata() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or user_profile() / "AppData" / "Local")


def roaming_appdata() -> Path:
    return Path(os.environ.get("APPDATA") or user_profile() / "AppData" / "Roaming")


def wsjtx_folder_name(rig_name: str | None = None) -> str:
    """``WSJT-X`` for the default profile, ``WSJT-X - <rig>`` for a multi-instance rig name."""
    return DEFAULT_WSJTX_FOLDER if not rig_name else f"{DEFAULT_WSJTX_FOLDER} - {rig_name}"


def wsjtx_dir(rig_name: str | None = None) -> Path:
    return local_appdata() / wsjtx_folder_name(rig_name)


def wsjtx_all_txt(rig_name: str | None = None) -> Path:
    """Default WSJT-X ALL.TXT for the running account (env override ``QA_WSJTX_ALL_TXT``)."""
    override = os.environ.get(ENV_WSJTX_ALL_TXT)
    return Path(override) if override else wsjtx_dir(rig_name) / ALL_TXT_NAME


def wsjtx_ini(rig_name: str | None = None) -> Path:
    """WSJT-X settings file. The default profile's is ``WSJT-X.ini``, a rig's ``WSJT-X - <rig>.ini``."""
    override = os.environ.get(ENV_WSJTX_INI)
    if override:
        return Path(override)
    d = wsjtx_dir(rig_name)
    return d / f"{d.name}.ini"


def station_config() -> Path:
    """OpenWSFZ station config (read-only template for arms); env override ``QA_STATION_CONFIG``."""
    override = os.environ.get(ENV_STATION_CONFIG)
    return Path(override) if override else roaming_appdata() / STATION_CONFIG_FOLDER / "config.json"


def is_explicit(chosen: str | os.PathLike, default: str | os.PathLike) -> bool:
    """True when ``chosen`` (e.g. a CLI value) differs from the resolver's default, i.e. was typed."""
    return os.path.normcase(os.path.abspath(chosen)) != os.path.normcase(os.path.abspath(default))


def _norm(p: str | os.PathLike) -> str:
    return os.path.normcase(os.path.realpath(p))


def is_under(path: str | os.PathLike, root: str | os.PathLike) -> bool:
    r, p = _norm(root), _norm(path)
    return p == r or p.startswith(r.rstrip("\\/") + os.sep)


def check_in_profile(path: str | os.PathLike, *, explicit: bool = False,
                     profile: str | os.PathLike | None = None) -> None:
    """Refuse a WSJT-X log outside the running user's profile unless it was named explicitly."""
    root = Path(profile) if profile is not None else user_profile()
    env = os.environ.get(ENV_WSJTX_ALL_TXT)
    if env and _norm(env) == _norm(path):
        explicit = True  # the environment override IS an explicit choice
    if explicit or is_under(path, root):
        return
    raise StaleLogError(
        f"REFUSED: the WSJT-X log {path} is outside the running account's profile ({root}). "
        "It is probably another account's frozen ALL.TXT, whose decodes would be silently absent "
        f"from this run. Fix the path, or pass it explicitly (CLI option or {ENV_WSJTX_ALL_TXT}) "
        "if the file is meant."
    )


def check_fresh_start(path: str | os.PathLike) -> None:
    """A missing log at run start is a message, not a traceback."""
    if not Path(path).is_file():
        raise StaleLogError(
            f"WSJT-X ALL.TXT not found at {path}. Under a fresh account WSJT-X creates it only "
            "after its first decode: start WSJT-X, set Monitor ON, wait one cycle, then retry "
            f"(or point at the right file with the CLI option / {ENV_WSJTX_ALL_TXT})."
        )


class GrowthWatch:
    """The log must GROW during the run: a frozen file is the silent-absence failure."""

    def __init__(self, path: str | os.PathLike):
        self.path = Path(path)
        self.start_size: int | None = None

    def start(self) -> "GrowthWatch":
        self.start_size = self.path.stat().st_size if self.path.is_file() else 0
        return self

    def verify(self) -> int:
        """Return the bytes added; raise StaleLogError unless strictly positive."""
        if self.start_size is None:
            raise RuntimeError("GrowthWatch.verify() called before start()")
        if not self.path.is_file():
            raise StaleLogError(f"WSJT-X ALL.TXT vanished during the run: {self.path}")
        grown = self.path.stat().st_size - self.start_size
        if grown < 0:
            raise StaleLogError(
                f"WSJT-X ALL.TXT SHRANK during the run ({self.path}: {self.start_size} -> "
                f"{self.start_size + grown} bytes): rotated or replaced. Decodes before the swap are lost."
            )
        if grown == 0:
            raise StaleLogError(
                f"WSJT-X ALL.TXT did not grow during the run ({self.path}, {self.start_size} bytes). "
                "WSJT-X wrote nothing: wrong account/profile path, Monitor off, or a frozen file. "
                "The run's WSJT-X side is EMPTY; do not compare."
            )
        return grown


def guard_run_start(path: str | os.PathLike, *, explicit: bool = False) -> GrowthWatch:
    """The run-start check in one call: in-profile, present, then arm the growth watch."""
    check_in_profile(path, explicit=explicit)
    check_fresh_start(path)
    return GrowthWatch(path).start()


if __name__ == "__main__":  # resolver report, no side effects
    import sys
    rig = sys.argv[1] if len(sys.argv) > 1 else None
    print(f"profile         : {user_profile()}")
    print(f"WSJT-X dir      : {wsjtx_dir(rig)}")
    print(f"WSJT-X ALL.TXT  : {wsjtx_all_txt(rig)}")
    print(f"WSJT-X ini      : {wsjtx_ini(rig)}")
    print(f"station config  : {station_config()}")
    p = wsjtx_all_txt(rig)
    try:
        check_in_profile(p, explicit=False)
        print("in-profile check: PASS")
    except StaleLogError as exc:
        print(f"in-profile check: {exc}")
    print(f"ALL.TXT present : {p.is_file()}")
