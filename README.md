# OpenWSFZ

An open-source, cross-platform, MIT-licensed weak-signal amateur-radio
application for HAM operators — covering the WSJT-X family of modes (FT8, FT4,
JS8, JT9, JT65, WSPR, and related).

## Project intent

- **For HAM operators**, designed to be something they would prefer over
  existing software.
- **Cross-platform** (Windows, Linux, macOS) and **free of restrictions**.
- **MIT-licensed**, clean-room implementation derived from public protocol
  specifications. No code, algorithms, or assets are taken from the GPL-3.0
  WSJT-X or JS8Call source trees.
- **Spec-driven and incrementally delivered**: every behavioural change goes
  through a written proposal (OpenSpec) before implementation.

## Status

Active v1 development. The first OpenSpec change — [`p0-foundation`](openspec/changes/p0-foundation/proposal.md) — establishes the build pipeline, CI quality gates, and tooling foundation. All subsequent v1 work proceeds through the [OpenSpec workflow](openspec/).

## License

MIT — see [LICENSE](LICENSE).
