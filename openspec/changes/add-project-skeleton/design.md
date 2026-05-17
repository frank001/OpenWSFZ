## Context

OpenWSFZ exists today as an empty directory plus a license and README on
`main`. There is no build system, no daemon, no UI, no CI. The first
feature branch must establish all of these in a way that lets every later
capability &mdash; audio, FFT, FT8/FT4/JS8/JT9/JT65/WSPR decoders, rig
control, logging &mdash; slot in without redesign.

Constraints carried over from the project charter:

- **MIT-licensed**, clean-room from public specs. No GPL-3.0 WSJT-X or
  JS8Call source consulted.
- **No Qt, Fortran, or Node.js dependencies.**
- **Cross-compiles** to Windows, Linux, macOS from one tree.
- **Web UI** is the only user interface; the daemon serves it.

## Goals / Non-Goals

**Goals:**

- A single CMake project that configures and builds on Windows
  (MSVC 2022), Linux (GCC), and macOS (Clang).
- A daemon binary that listens on `127.0.0.1:8080`, serves the web UI as
  static assets, exposes `/api/health`, and accepts WebSocket clients at
  `/ws`.
- A documented JSON envelope on `/ws` that every future capability can
  extend by registering a `type`.
- Vanilla-JS web UI that proves the connection end-to-end with no
  bundler, no framework, and no Node toolchain.
- GitHub Actions matrix build across the three platforms.

**Non-Goals:**

- Any DSP, audio I/O, decoder, modulator, rig control, or logbook
  functionality. Those are entirely later changes.
- TLS / HTTPS. The skeleton binds to loopback only; TLS is a later
  concern once remote operation enters scope.
- Authentication. Loopback-only bind is the current threat model.
- Packaging (installers, .deb, .pkg, MSI). Out of scope until the
  daemon does something worth installing.
- Persistent storage / databases. Skeleton is stateless.

## Decisions

### 1. Language and build system: C++17 with CMake + Ninja

C++17 is the floor (filesystem, structured bindings, optional). Drogon
itself targets C++17. We pin to C++17 rather than C++20 so the toolchain
matrix stays generous (Ubuntu LTS GCC, macOS system Clang, MSVC 2022
all comfortably support 17).

**Alternatives considered:** Rust (excellent cross-compile and safety,
but the reference protocol code in the field is overwhelmingly C/C++;
keeping the same language as the reference lowers porting friction
even though we are not copying code), Go (weaker DSP ecosystem), pure
C (more plumbing for HTTP/WS than worthwhile).

### 2. HTTP + WebSocket: Drogon (MIT) via CMake FetchContent

Drogon ships HTTP, WebSocket, static file serving, JSON, and an async
runtime in a single MIT-licensed package. It builds cleanly on all three
target platforms.

**Alternatives considered:**
- **cpp-httplib** (MIT, header-only): great HTTP, weak WS. We would
  hand-roll the WS handshake or pull a second lib.
- **Crow** (BSD-3): header-only, HTTP+WS, Flask-like. Lighter, but less
  battle-tested for long-running servers.
- **Boost.Beast** (BSL-1.0): most powerful, drags in Boost. Overkill
  for this slice.

Drogon wins on completeness without paying the Boost cost.

### 3. Dependency strategy: CMake `FetchContent`, not vcpkg or Conan

Every build configures with one command on a clean checkout. No external
package manager prerequisite for contributors. FetchContent will pin
Drogon by tag in `cmake/Dependencies.cmake`. If supply-chain concerns
later argue for vendored tarballs, we can swap the source URL without
touching the rest of the tree.

### 4. WebSocket message envelope

Every message in either direction is a JSON object:

```json
{
  "type":    "string, kebab-case, registered per-capability",
  "id":      "client-generated correlation id (uuid v4 or short int)",
  "ts":      "ISO-8601 millisecond timestamp",
  "payload": { /* type-specific, may be omitted */ }
}
```

Rationale: `type` lets each future capability claim its slice without
versioning the whole protocol. `id` lets the UI correlate request and
response without subscribing to global streams. `ts` aids debugging.
`payload` is open-shape per type.

The skeleton defines exactly two types:
- `ping` (client → daemon) and `pong` (daemon → client), with the
  daemon echoing the same `id`.
- `echo` (daemon → client), returned for any unrecognised `type`, so
  the UI can develop ahead of new server-side handlers.

### 5. Single binary serves the UI

The daemon mounts `web/` as the static root rather than requiring an
external web server. This keeps the run story `./openwsfz` and `open
http://localhost:8080/`. The build copies (or, in the source-tree
layout, references) `web/` next to the binary so packaging stays simple.

### 6. Default bind: `127.0.0.1`, not `0.0.0.0`

Loopback-only by default. A `--bind` flag exists to opt in to LAN
access. This is the threat model until auth is designed.

### 7. CMake Presets, not bespoke scripts

`CMakePresets.json` provides `windows-msvc`, `linux-gcc`, `macos-clang`
configure + build presets. CI invokes them by name; developers do the
same locally. Avoids divergent build incantations.

## Risks / Trade-offs

- **Drogon configure-time fetch slows first-time CI by ~1&ndash;3 min**
  → Mitigation: cache `build/_deps/` between CI runs with
  `actions/cache` keyed on the Drogon pin.
- **Drogon optionally depends on OpenSSL/zlib on Windows**
  → Mitigation: configure Drogon with TLS off for this slice; plain
  `http://` over loopback is sufficient. Re-enable when remote operation
  is on the table.
- **No bundler means the UI is plain JS modules**
  → Trade-off accepted: matches the no-Node constraint. If complexity
  grows, a later change can introduce a build-time bundler that runs
  in CI but is not a developer prerequisite.
- **C++17 is fine today but C++20 ranges/coroutines would simplify
  later async code**
  → We can raise the floor in a later change once all three target
  toolchains support it without flags.
- **Loopback bind hides multi-host bugs**
  → Documented; a future `remote-operation` change owns network
  hardening.

## Migration Plan

There is no prior version to migrate from. After this change merges,
`main` will contain a buildable end-to-end skeleton. Rollback is `git
revert` of the merge commit; the daemon was non-functional before, so
there is nothing to preserve.

## Open Questions

- Drogon version pin: latest stable tag at scaffold time. Recorded in
  `cmake/Dependencies.cmake`; revisited per release.
- Logging library: standard `std::cerr` for the skeleton; a structured
  logging capability is a candidate for the next change.
- Configuration format: out of scope for the skeleton (CLI flags only).
  A `daemon-config` capability will introduce TOML/JSON loading later.
