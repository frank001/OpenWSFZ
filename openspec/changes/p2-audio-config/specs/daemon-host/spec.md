## ADDED Requirements

### Requirement: Config-file path override via CLI flag and environment variable

The daemon SHALL accept a `--config <path>` CLI argument and an `OPENWSFZ_CONFIG` environment variable. When either is provided it SHALL override the platform default config-file path. The CLI flag takes precedence over the environment variable.

#### Scenario: --config flag overrides default path

- **WHEN** the daemon is launched with `--config /custom/path/config.json`
- **THEN** the daemon SHALL load and save configuration from `/custom/path/config.json` instead of the platform default path

#### Scenario: OPENWSFZ_CONFIG env var overrides default path

- **WHEN** the daemon is launched with `OPENWSFZ_CONFIG=/custom/config.json` set in the environment and no `--config` flag
- **THEN** the daemon SHALL use the path from the environment variable

#### Scenario: CLI flag takes precedence over env var

- **WHEN** both `--config` flag and `OPENWSFZ_CONFIG` are set
- **THEN** the daemon SHALL use the path from the `--config` flag

#### Scenario: Resolved config path logged at startup

- **WHEN** the daemon starts
- **THEN** it SHALL log a line at INFO level naming the resolved config-file path and its source (flag / env-var / default) before the web host starts accepting connections
