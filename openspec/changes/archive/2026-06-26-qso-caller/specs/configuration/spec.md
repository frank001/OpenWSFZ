## ADDED Requirements

### Requirement: TxConfig gains Role and CallerPartnerSelect fields

`TxConfig` SHALL include two new fields:

```csharp
public TxRole                Role                { get; init; } = TxRole.Answerer;
public CallerPartnerSelectMode CallerPartnerSelect { get; init; } = CallerPartnerSelectMode.First;
```

Both fields SHALL have backward-compatible defaults so that existing config files
without these keys deserialise correctly (per lesson 6: STJ source-gen uses `0` for
absent enum fields — the `[JsonConstructor]` on `TxConfig` MUST carry explicit default
parameter values for both fields).

**`TxRole` enum:**
```csharp
public enum TxRole { Answerer = 0, Caller = 1 }
```

**`CallerPartnerSelectMode` enum:**
```csharp
public enum CallerPartnerSelectMode { First = 0, None = 1 }
```

Both enums SHALL be defined in `OpenWSFZ.Abstractions`.

#### Scenario: Existing config without Role field loads as Answerer

- **WHEN** a config file contains a `tx` object with no `role` key
- **THEN** `config.Tx.Role` SHALL equal `TxRole.Answerer`
- **AND** the daemon SHALL start without error

#### Scenario: Existing config without CallerPartnerSelect loads as First

- **WHEN** a config file contains a `tx` object with no `callerPartnerSelect` key
- **THEN** `config.Tx.CallerPartnerSelect` SHALL equal `CallerPartnerSelectMode.First`

#### Scenario: Role field round-trips through GET/POST config

- **WHEN** `POST /api/v1/config` is called with `{ "tx": { "role": "Caller", ... } }`
- **THEN** `GET /api/v1/config` SHALL subsequently return `"tx": { "role": "Caller", ... }`

#### Scenario: CallerPartnerSelect field round-trips through GET/POST config

- **WHEN** `POST /api/v1/config` is called with
  `{ "tx": { "callerPartnerSelect": "None", ... } }`
- **THEN** `GET /api/v1/config` SHALL subsequently return
  `"tx": { "callerPartnerSelect": "None", ... }`
