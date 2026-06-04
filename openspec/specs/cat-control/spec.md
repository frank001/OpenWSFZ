## Requirements

### Requirement: IRadioConnection abstraction

`OpenWSFZ.Abstractions` SHALL define a public interface `IRadioConnection` with the following members:

```csharp
Task ConnectAsync(CancellationToken cancellationToken = default);
Task DisconnectAsync(CancellationToken cancellationToken = default);
Task<double> GetDialFrequencyMhzAsync(CancellationToken cancellationToken = default);
Task SetDialFrequencyMhzAsync(double frequencyMHz, CancellationToken cancellationToken = default);
bool IsConnected { get; }
```

The interface SHALL be the only type that `CatPollingService` and any consumer outside `OpenWSFZ.Rig` depend upon.

`SetDialFrequencyMhzAsync` is a fire-and-forget command: it sends the frequency-set instruction to the rig and returns without reading back confirmation. The next `GetDialFrequencyMhzAsync` poll reflects the new frequency if the rig accepted the command. No mode-set, PTT, or other rig-altering commands are introduced by this interface.

#### Scenario: IRadioConnection is defined in OpenWSFZ.Abstractions

- **WHEN** `OpenWSFZ.Abstractions` is compiled
- **THEN** the assembly SHALL export a public interface named `IRadioConnection` with the five members listed above

#### Scenario: SetDialFrequencyMhzAsync is a member of IRadioConnection

- **WHEN** the interface is reflected at runtime
- **THEN** `SetDialFrequencyMhzAsync` SHALL be present with signature `Task SetDialFrequencyMhzAsync(double, CancellationToken)`

---

### Requirement: SerialCatConnection implements IRadioConnection

`OpenWSFZ.Rig` SHALL provide a class `SerialCatConnection` that implements `IRadioConnection` using `System.IO.Ports.SerialPort` and the serial CAT command set. The class SHALL be constructable with a port name and baud rate. All serial I/O SHALL use a 500 ms `ReadTimeout`.

CAT commands sent by `SerialCatConnection`:
- `FA;` (VFO-A frequency **query**, sent by `GetDialFrequencyMhzAsync`)
- `FA<Hz>;` (VFO-A frequency **set**, sent by `SetDialFrequencyMhzAsync`) — Hz zero-padded to the rig's native digit width (self-calibrated from the first successful query response; 11-digit fallback until then)

No mode-set, PTT, or other rig-altering commands SHALL be sent by this class.

#### Scenario: ConnectAsync opens the serial port

- **WHEN** `ConnectAsync` is called with a valid port name and baud rate
- **THEN** the serial port SHALL be opened and `IsConnected` SHALL return `true`

#### Scenario: ConnectAsync throws when port is unavailable

- **WHEN** `ConnectAsync` is called with a port name that does not exist or is in use
- **THEN** the method SHALL throw an exception (propagating `SerialPort.Open()` failure) and `IsConnected` SHALL remain `false`

#### Scenario: GetDialFrequencyMhzAsync sends FA; and parses response

- **WHEN** `GetDialFrequencyMhzAsync` is called on a connected instance and the rig responds with a valid `FA<Hz>;` frame
- **THEN** the implementation SHALL write `FA;` to the serial port, read the response up to the `;` delimiter, and return the VFO-A frequency in MHz. The response Hz field SHALL be accepted with 8 to 11 digits inclusive (e.g. `FA014074000;` → `14.074`, `FA00014074000;` → `14.074`).

#### Scenario: GetDialFrequencyMhzAsync calibrates digit width on first success

- **WHEN** `GetDialFrequencyMhzAsync` succeeds for the first time on a given connection
- **THEN** the class SHALL record the digit count from the FA response and use that count as the zero-pad width for all subsequent `SetDialFrequencyMhzAsync` calls on that connection

#### Scenario: GetDialFrequencyMhzAsync throws on malformed response

- **WHEN** the serial port returns a response that does not start with `FA`, or whose digit count (characters between the `FA` prefix and the `;` delimiter) is outside the range 8–11
- **THEN** `GetDialFrequencyMhzAsync` SHALL throw an `InvalidOperationException` with a message that includes the raw response for diagnostics

#### Scenario: GetDialFrequencyMhzAsync throws on read timeout

- **WHEN** no response arrives within 500 ms of the `FA;` command being written
- **THEN** `GetDialFrequencyMhzAsync` SHALL throw a `TimeoutException`

#### Scenario: SetDialFrequencyMhzAsync sends FA set command using calibrated width

- **WHEN** `SetDialFrequencyMhzAsync` is called after at least one successful `GetDialFrequencyMhzAsync` has recorded the rig's digit width
- **THEN** the implementation SHALL write `FA<Hz>;` to the serial port with the Hz value rounded to the nearest integer and zero-padded to the previously recorded digit width (e.g. for a 9-digit rig: `14.074 MHz → FA014074000;`)

#### Scenario: SetDialFrequencyMhzAsync uses 11-digit fallback before first poll

- **WHEN** `SetDialFrequencyMhzAsync` is called before any successful `GetDialFrequencyMhzAsync` has completed on the current connection
- **THEN** the implementation SHALL format the FA set command using an 11-digit zero-padded Hz value (e.g. `FA00014074000;`)

#### Scenario: DisconnectAsync closes the serial port

- **WHEN** `DisconnectAsync` is called
- **THEN** the serial port SHALL be closed and `IsConnected` SHALL return `false`

#### Scenario: Dispose closes the serial port

- **WHEN** a `SerialCatConnection` instance is disposed while the port is open
- **THEN** the serial port SHALL be closed

---

### Requirement: RigctldConnection implements IRadioConnection

`OpenWSFZ.Rig` SHALL provide a class `RigctldConnection` that implements `IRadioConnection` using a `TcpClient` connected to a running `rigctld` daemon. The class SHALL be constructable with a hostname and port (defaults `"127.0.0.1"` and `4532`). All network I/O SHALL use a 500 ms receive timeout. No transmit, PTT, or rig-altering commands SHALL be sent by this class.

Commands sent by `RigctldConnection`:
- `\get_freq\n` (frequency **query**, sent by `GetDialFrequencyMhzAsync`)
- `\set_freq <Hz>\n` (frequency **set**, sent by `SetDialFrequencyMhzAsync`)

#### Scenario: ConnectAsync opens a TCP connection to rigctld

- **WHEN** `ConnectAsync` is called and `rigctld` is listening on the configured host and port
- **THEN** the TCP connection SHALL be established and `IsConnected` SHALL return `true`

#### Scenario: ConnectAsync throws when rigctld is not reachable

- **WHEN** `ConnectAsync` is called and no process is listening on the configured host and port
- **THEN** the method SHALL throw a `SocketException` and `IsConnected` SHALL remain `false`

#### Scenario: GetDialFrequencyMhzAsync sends get_freq and parses response

- **WHEN** `GetDialFrequencyMhzAsync` is called on a connected instance
- **THEN** the implementation SHALL send `\get_freq\n` to the rigctld socket, read the response line, and return the frequency in MHz by dividing the Hz integer value by 1 000 000 (e.g. `14074000` → `14.074`)

#### Scenario: GetDialFrequencyMhzAsync throws on rigctld error response

- **WHEN** rigctld returns a response beginning with `RPRT` (rigctld error report) or a value that cannot be parsed as a non-negative integer
- **THEN** `GetDialFrequencyMhzAsync` SHALL throw an `InvalidOperationException` with the raw response included in the message

#### Scenario: GetDialFrequencyMhzAsync throws on receive timeout

- **WHEN** no response arrives within 500 ms of the command being sent
- **THEN** `GetDialFrequencyMhzAsync` SHALL throw a `TimeoutException`

#### Scenario: SetDialFrequencyMhzAsync sends set_freq command

- **WHEN** `SetDialFrequencyMhzAsync` is called with a frequency in MHz (e.g., `14.074`)
- **THEN** the implementation SHALL send `\set_freq <Hz>\n` to the rigctld socket, where Hz is the frequency rounded to the nearest integer (e.g., `\set_freq 14074000\n`)
- **AND** the method SHALL return after the write completes without waiting for a confirmation response

#### Scenario: DisconnectAsync closes the TCP connection

- **WHEN** `DisconnectAsync` is called
- **THEN** the TCP connection SHALL be closed and `IsConnected` SHALL return `false`

#### Scenario: Dispose closes the TCP connection

- **WHEN** a `RigctldConnection` instance is disposed while connected
- **THEN** the TCP connection SHALL be closed

---

### Requirement: ICatState tracks live CAT telemetry

`OpenWSFZ.Daemon` (or `OpenWSFZ.Rig`) SHALL define a public interface `ICatState` and a concrete `CatState` implementation registered as a singleton in DI. `ICatState` SHALL expose:

```csharp
double? DialFrequencyMHz { get; }   // null when CAT disabled or no successful poll yet
CatConnectionStatus Status { get; } // Disabled | Connecting | Connected | Error
```

`CatState` SHALL be thread-safe: reads and writes to `DialFrequencyMHz` SHALL use `Interlocked`-style or `volatile` semantics to prevent torn reads.

#### Scenario: DialFrequencyMHz is null when CAT is disabled

- **WHEN** `AppConfig.Cat.Enabled` is `false`
- **THEN** `ICatState.DialFrequencyMHz` SHALL be `null`

#### Scenario: DialFrequencyMHz is updated after a successful poll

- **WHEN** `CatPollingService` successfully calls `GetDialFrequencyMhzAsync` and receives a value
- **THEN** `ICatState.DialFrequencyMHz` SHALL reflect that value within one poll interval

#### Scenario: Status is Connected after first successful poll

- **WHEN** `CatPollingService` completes its first successful `GetDialFrequencyMhzAsync` call
- **THEN** `ICatState.Status` SHALL be `CatConnectionStatus.Connected`

#### Scenario: Status is Error after a failed poll

- **WHEN** `GetDialFrequencyMhzAsync` throws any exception
- **THEN** `ICatState.Status` SHALL be `CatConnectionStatus.Error`

---

### Requirement: CatPollingService polls the rig at the configured interval

`OpenWSFZ.Daemon` SHALL provide a `CatPollingService : IHostedService` that, when CAT is enabled, polls `IRadioConnection.GetDialFrequencyMhzAsync` at the interval specified by `AppConfig.Cat.PollIntervalSeconds` (default 1 s). On each successful poll it SHALL update `ICatState.DialFrequencyMHz`. On failure it SHALL log a Warning with the exception message, set `ICatState.Status` to `Error`, wait 2 s, and retry.

#### Scenario: Polling starts when CAT is enabled and daemon starts

- **WHEN** the daemon starts with `AppConfig.Cat.Enabled = true` and a reachable serial port
- **THEN** `CatPollingService.StartAsync` SHALL open the connection and begin polling within one poll interval

#### Scenario: Polling does not start when CAT is disabled

- **WHEN** the daemon starts with `AppConfig.Cat.Enabled = false`
- **THEN** `CatPollingService` SHALL start without opening any serial port and `ICatState.Status` SHALL be `Disabled`

#### Scenario: Serial port open failure is logged and CAT enters Error state

- **WHEN** `ConnectAsync` throws during service start
- **THEN** `CatPollingService` SHALL log an Error containing the port name and exception message, set `ICatState.Status` to `Error`, and retry after 2 s without crashing the daemon

#### Scenario: Decode pipeline is unaffected by CAT failure

- **WHEN** `CatPollingService` enters `Error` state
- **THEN** the FT8 decode pipeline SHALL continue processing cycles normally and ALL.TXT logging SHALL fall back to `AppConfig.DecodeLog.DialFrequencyMHz`

#### Scenario: Polling stops on daemon shutdown

- **WHEN** the daemon initiates graceful shutdown (SIGTERM / Ctrl-C)
- **THEN** `CatPollingService.StopAsync` SHALL cancel the polling loop and call `DisconnectAsync`, and SHALL complete within 3 s

#### Scenario: Config hot-reload reconnects on port or baud change

- **WHEN** the operator saves a new `serialPort` or `baudRate` value via `POST /api/v1/config`
- **THEN** `CatPollingService` SHALL disconnect from the current port and reconnect using the updated parameters within two poll intervals

---

### Requirement: Effective dial frequency resolution

Any component that needs the current dial frequency (ALL.TXT writer, `DaemonStatus`, WebSocket heartbeat) SHALL resolve it using the following precedence:

1. `ICatState.DialFrequencyMHz` — when non-null (CAT active and producing data)
2. `AppConfig.DecodeLog.DialFrequencyMHz` — operator's manual configuration (fallback)

No component SHALL read `ICatState.DialFrequencyMHz` directly without providing the fallback.

#### Scenario: CAT value takes precedence over manual config

- **WHEN** `ICatState.DialFrequencyMHz` is `14.074` and `AppConfig.DecodeLog.DialFrequencyMHz` is `7.074`
- **THEN** `AllTxtWriter` SHALL write `14.074` MHz in ALL.TXT log lines

#### Scenario: Manual config is used when CAT is disabled

- **WHEN** `ICatState.DialFrequencyMHz` is `null` and `AppConfig.DecodeLog.DialFrequencyMHz` is `7.074`
- **THEN** `AllTxtWriter` SHALL write `7.074` MHz in ALL.TXT log lines

---

### Requirement: CAT WebSocket status events

`CatPollingService` SHALL push a `cat_status` WebSocket event to all connected clients when the CAT connection state changes (`Disabled` → `Connected`, `Connected` → `Error`, etc.) or when the polled frequency changes by ≥ 1 Hz. The event payload SHALL be:

```json
{ "type": "cat_status", "payload": { "status": "Connected", "dialFrequencyMHz": 14.074 } }
```

The existing `status` and `heartbeat` events SHALL include `dialFrequencyMHz` using the effective resolution rule above.

#### Scenario: cat_status event emitted on state change

- **WHEN** `ICatState.Status` changes from any state to any other state
- **THEN** a `cat_status` WebSocket event SHALL be pushed to all connected clients within one poll interval

#### Scenario: cat_status event emitted on frequency change

- **WHEN** the polled VFO-A frequency changes by ≥ 1 Hz from the last emitted value
- **THEN** a `cat_status` WebSocket event SHALL be pushed

#### Scenario: No cat_status event when frequency is stable

- **WHEN** successive polls return the same frequency (within 1 Hz)
- **THEN** no additional `cat_status` WebSocket event SHALL be emitted between heartbeats

---

### Requirement: CAT status indicator in UI

The main page status bar SHALL display the current effective dial frequency and a CAT connection indicator. The indicator SHALL reflect `ICatState.Status` as reported in the `cat_status` or `status` WebSocket event. The indicator SHALL comply with FR-016: it SHALL only appear once the backend CAT capability is implemented (i.e., from this change onwards).

#### Scenario: Status bar shows dial frequency

- **WHEN** the main page receives a `status` or `cat_status` WebSocket event containing a non-zero `dialFrequencyMHz`
- **THEN** the status bar SHALL display the frequency formatted to three decimal places followed by `MHz` (e.g. `14.074 MHz`)

#### Scenario: CAT connected indicator

- **WHEN** the `cat_status` payload contains `"status": "Connected"`
- **THEN** the status bar SHALL show a visual indicator that CAT is connected (e.g. a labelled badge or icon)

#### Scenario: CAT error indicator

- **WHEN** the `cat_status` payload contains `"status": "Error"`
- **THEN** the status bar SHALL show a visually distinct error indicator (different colour or label from the connected state)

#### Scenario: CAT disabled — indicator absent

- **WHEN** the `cat_status` payload contains `"status": "Disabled"`
- **THEN** no CAT indicator SHALL be shown in the status bar (the frequency field still shows the manual fallback value if non-zero)
