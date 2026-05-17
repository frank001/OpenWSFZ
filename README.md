# OpenWSFZ

An open-source, cross-compiling, MIT-licensed implementation of the WSJT-X
weak-signal amateur-radio application family (FT8, FT4, JS8, JT9, JT65, WSPR,
and related modes).

## Project goals

- **MIT-licensed**, clean-room implementation derived from the public protocol
  specifications (K1JT et al., QEX). No code, algorithms, or assets are taken
  from the GPL-3.0 WSJT-X or JS8Call source trees.
- **No Qt, Fortran, or Node.js dependencies.** The daemon is plain C++17 with
  CMake. The user interface is a browser page (vanilla HTML/CSS/JS) served by
  the daemon itself over HTTP + WebSocket.
- **Cross-compiles** to Windows, Linux, and macOS from a single CMake tree.
- **Spec-driven.** Every behavioural change ships through an
  [OpenSpec](https://github.com/Fission-AI/OpenSpec) change proposal that is
  reviewed and merged before the implementation is accepted on `main`.
- **Branch-per-feature.** `main` only receives reviewed, approved merges.

## Status

Early scaffolding. Nothing decodes anything yet. The first milestone is the
project skeleton plus a daemon that serves the web UI and a WebSocket echo
endpoint, proving the end-to-end control pipeline.

See `openspec/changes/` for the current and proposed changes.

## Repository layout

```
openspec/        OpenSpec proposals, specs, designs (single source of truth)
src/             C++ daemon source
include/         Public headers
web/             Static web UI served by the daemon
cmake/           CMake helpers and toolchain files
docs/            Long-form documentation
prompts/         AI assistant prompts used during development (see CREDITS)
.github/         CI workflows and issue templates
```

## Building

Prerequisites: a C++17 compiler, CMake 3.20+, and Ninja (all bundled with
Visual Studio 2022 on Windows; `apt`/`brew` on Linux/macOS).

```sh
cmake --preset windows-msvc      # or linux-gcc, macos-clang
cmake --build --preset windows-msvc
./build/windows-msvc/openwsfz
```

The daemon listens on `http://localhost:8080/` and serves the UI from `web/`.

## License

MIT &mdash; see [LICENSE](LICENSE).

## Contributing

1. Open an OpenSpec change proposal under `openspec/changes/`.
2. Branch off `main` as `feature/<change-id>`.
3. Implement, push, open a PR that references the change proposal.
4. Review and merge.

`main` is the protected, reviewed line. No direct commits.
