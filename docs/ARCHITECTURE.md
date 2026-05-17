# OpenWSFZ Architecture

> Living document. Updated by every change that materially affects the
> shape of the system.

## One picture

```
+--------------------+     HTTP (static + /api/*)         +-----------------+
|   Browser-served   | <--------------------------------- |                 |
|       Web UI       |                                    |    openwsfz     |
|   (vanilla JS)     |                                    |   (single C++   |
|                    |     WebSocket  /ws  (JSON env.)    |     binary)     |
|                    | <================================> |                 |
+--------------------+                                    +-----------------+
                                                          |   Drogon HTTP/WS,
                                                          |   future:
                                                          |     audio I/O,
                                                          |     FFT,
                                                          |     decoders,
                                                          |     rig control,
                                                          |     logbook
                                                          +-----------------+
```

The daemon is **one** binary. It owns the HTTP server, serves the static
UI, exposes a small JSON HTTP surface (`/api/*`) for synchronous
queries, and exposes a `/ws` WebSocket for everything streaming or
event-driven. Every later capability extends the WebSocket envelope by
registering a new `type`.

## Constraints

- MIT-licensed, clean-room from public protocol specifications. No
  GPL-3.0 code from WSJT-X or JS8Call is consulted while implementing.
- No Qt, no Fortran, no Node.js. The web UI is plain HTML/CSS/JS with
  no bundler.
- Cross-compiles to Windows (MSVC), Linux (GCC), macOS (Clang) from one
  CMake tree, driven by `CMakePresets.json`.

## Daemon layout

```
src/
  main.cpp          Entry: CLI, signals, lifecycle, server config
  WsController.h    /ws controller declaration
  WsController.cc   /ws envelope parsing, ping/echo replies
include/openwsfz/
  version.hpp.in    Substituted at configure time
cmake/
  Dependencies.cmake   FetchContent for Drogon (and its transitive deps)
  CompileFlags.cmake   Warning/sanitizer knobs applied to first-party code
```

Drogon is fetched at configure time, pinned by tag. We deliberately do
not depend on a system package manager (vcpkg, Conan), so a contributor
with only CMake and a compiler can build.

## HTTP surface

| Endpoint        | Method | Response                                    |
|-----------------|--------|---------------------------------------------|
| `/`             | GET    | `web/index.html`                            |
| `/<path>`       | GET    | `web/<path>` if it exists, else 404         |
| `/api/health`   | GET    | `{ status, version, git_sha, uptime_seconds }` |

## WebSocket envelope

Every message in either direction is a JSON object:

```json
{
  "type":    "kebab-case identifier, registered per capability",
  "id":      "string or number; client-correlation key",
  "ts":      "ISO-8601 millisecond timestamp",
  "payload": { /* type-specific, may be absent */ }
}
```

The skeleton defines exactly three types:

| Direction     | `type`  | Meaning                                          |
|---------------|---------|--------------------------------------------------|
| client &rarr; daemon | `ping`  | Heartbeat. Optional `payload`.            |
| daemon &rarr; client | `pong`  | Reply to `ping`. `payload.echoed` carries any payload that came in. |
| daemon &rarr; client | `echo`  | Fallback for any unrecognised request type. `payload.original` is the full incoming envelope. |
| daemon &rarr; client | `error` | Malformed JSON, missing fields, or unsupported frame kind. `payload.message` is human-readable. |

### Adding new types

Each new capability change proposal must:

1. List the new `type` value(s) in its spec, under
   `## ADDED Requirements`.
2. Document the payload shape in both directions.
3. Update this table.

The receiving side dispatches on `type`. Unknown types still receive
`echo` from the daemon so a UI under development can ship ahead of its
server-side handler.

## Lifecycle

1. `main()` parses CLI flags (`--bind`, `--port`, `--doc-root`).
2. The web doc-root is resolved (default: `<exe-dir>/web`).
3. Drogon is configured (listener, doc-root, handlers).
4. SIGINT/SIGTERM handlers wire up to `drogon::app().quit()`.
5. A structured startup line is emitted to stderr.
6. `app().run()` blocks until shutdown.
7. A structured shutdown line is emitted; process exits 0.

## Threat model (skeleton)

- Default bind is `127.0.0.1` only. The daemon assumes the local user
  trusts the local process.
- There is no authentication on the HTTP or WS surfaces. Loopback bind
  is the entire defence.
- TLS is intentionally disabled in the dependency pin. Re-enabled when
  remote operation becomes a capability.

Hardening for LAN or remote operation is a separate, future change.

## Extension model

Adding a capability is always:

1. **Propose**: `openspec new change <kebab-case-name>`; fill in
   `proposal.md`, `design.md`, `specs/<capability>/spec.md`,
   `tasks.md`. Validate.
2. **Branch**: `git checkout -b feature/<change-name>` from `main`.
3. **Implement** the tasks. Code lives in `src/` (and `include/`),
   never in `openspec/`.
4. **Review** the change proposal + diff in a pull request.
5. **Merge** to `main`. The change is archived under
   `openspec/changes/archive/`.

Spec-level requirements never get "fixed in code without a spec". If
the spec is wrong, file a MODIFIED-Requirements change first.
