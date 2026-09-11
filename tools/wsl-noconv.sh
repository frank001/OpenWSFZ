#!/usr/bin/env bash
# Wrapper for invoking `wsl` from Git Bash with MSYS2 path conversion fully
# disabled for every argument. Exists so the Claude Code permission rule for
# this invocation shape can be a plain `tools/wsl-noconv.sh *` (wildcard only
# after the subcommand) instead of embedding a literal `*` mid-pattern inside
# `MSYS2_ARG_CONV_EXCL="*"` — that shape triggered a permission-rule wildcard
# warning because the engine cannot distinguish a literal asterisk value from
# a matcher wildcard, so a `*` followed by more fixed text (` wsl *`) is
# treated as auto-approving anything inserted at that position.
set -euo pipefail

export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

exec wsl "$@"
