## 1. Build foundation

- [ ] 1.1 Add root `CMakeLists.txt` declaring `openwsfz` project, C++17,
      output dir conventions, and warning flags per compiler
- [ ] 1.2 Add `cmake/Dependencies.cmake` that uses `FetchContent` to
      pull Drogon (MIT) at a pinned tag, with TLS/zlib options disabled
      for the skeleton
- [ ] 1.3 Add `cmake/CompileFlags.cmake` with shared warning/sanitizer
      knobs (`-Wall -Wextra -Wpedantic` / `/W4`, opt-in sanitizers)
- [ ] 1.4 Add `CMakePresets.json` with `windows-msvc`, `linux-gcc`,
      and `macos-clang` configure + build presets, all using Ninja

## 2. Daemon entry and lifecycle

- [ ] 2.1 Create `src/main.cpp` parsing `--bind`, `--port`, `--help`
      flags and printing usage on unknown flags
- [ ] 2.2 Implement startup logging line (timestamp, level, component,
      message) printed to stderr
- [ ] 2.3 Install SIGINT/SIGTERM handler that triggers Drogon's
      `app().quit()` and emits a shutdown log line
- [ ] 2.4 Track process start time and expose `uptime_seconds()` for
      the health endpoint

## 3. HTTP surface

- [ ] 3.1 Configure Drogon's static file handler so `GET /` returns
      `web/index.html` and other paths resolve under `web/`
- [ ] 3.2 Implement `GET /api/health` returning JSON
      `{status:"ok", version, uptime_seconds}` with version baked in
      at configure time via a generated header
- [ ] 3.3 Generate `include/openwsfz/version.hpp` from CMake variables
      (version + short git SHA)

## 4. WebSocket surface

- [ ] 4.1 Implement a WebSocket controller mounted at `/ws`
- [ ] 4.2 Parse incoming text frames as JSON envelopes
      `{type, id, ts, payload?}`; reject malformed/missing-field frames
      with `type:"error"` (connection stays open)
- [ ] 4.3 Register a `ping` handler that replies with `type:"pong"`,
      same `id`, fresh `ts`, and `payload.echoed = payload`
- [ ] 4.4 Default handler for any other `type` returns
      `type:"echo"` with `payload.original` set to the full request

## 5. Web UI scaffold

- [ ] 5.1 Write `web/index.html` with header, connection-status pill,
      and placeholder panels for spectrogram / decoded messages /
      transmit controls (placeholders are visibly disabled per the
      UI-visibility rule)
- [ ] 5.2 Write `web/app.js` (vanilla, no bundler) that opens a
      WebSocket to `/ws`, sends a `ping` every 5 s, and updates the
      status pill from pong replies
- [ ] 5.3 Write `web/style.css` with minimal layout, no framework

## 6. CI

- [ ] 6.1 Add `.github/workflows/build.yml` matrix on
      `windows-latest` (msvc), `ubuntu-latest` (gcc), `macos-latest`
      (clang); each runs `cmake --preset <name>` then
      `cmake --build --preset <name>`
- [ ] 6.2 Cache `build/_deps/` keyed on Drogon's pinned tag to
      keep CI under 5 minutes per platform after the first run

## 7. Documentation

- [ ] 7.1 Add `docs/ARCHITECTURE.md` covering the daemon/web split,
      the JSON envelope, and the extension model for future
      capabilities
- [ ] 7.2 Update root `README.md` build section to reference the
      preset names

## 8. Verification

- [ ] 8.1 Build on Windows with `cmake --preset windows-msvc &&
      cmake --build --preset windows-msvc`; confirm `openwsfz.exe`
      links cleanly
- [ ] 8.2 Launch the binary, visit `http://127.0.0.1:8080/` in a
      browser, observe the UI connecting and the status pill turning
      green within 2 seconds
- [ ] 8.3 With `curl`, confirm `GET /api/health` returns the
      documented JSON shape
- [ ] 8.4 Send SIGINT (Ctrl-C); confirm graceful shutdown within 5 s
      and the documented shutdown log line on stderr
- [ ] 8.5 `openspec validate add-project-skeleton --strict` passes
