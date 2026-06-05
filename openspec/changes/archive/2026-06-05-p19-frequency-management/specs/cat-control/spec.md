## MODIFIED Requirements

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

`SetDialFrequencyMhzAsync` is a fire-and-forget command: it sends the frequency-set instruction to the rig and returns; it does NOT re-read the rig to confirm. The next `GetDialFrequencyMhzAsync` poll will reflect the new frequency if the rig accepted the command.

The earlier p16 restriction prohibiting frequency-set commands is **hereby amended**: frequency-set is now a permitted operation on this interface. No mode-set, PTT, or other rig-altering commands are introduced by this change.

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
- `FA<11-digit-Hz>;` (VFO-A frequency **set**, sent by `SetDialFrequencyMhzAsync`)

No mode-set, PTT, or other rig-altering commands SHALL be sent by this class.

#### Scenario: ConnectAsync opens the serial port

- **WHEN** `ConnectAsync` is called with a valid port name and baud rate
- **THEN** the serial port SHALL be opened and `IsConnected` SHALL return `true`

#### Scenario: ConnectAsync throws when port is unavailable

- **WHEN** `ConnectAsync` is called with a port name that does not exist or is in use
- **THEN** the method SHALL throw an exception (propagating `SerialPort.Open()` failure) and `IsConnected` SHALL remain `false`

#### Scenario: GetDialFrequencyMhzAsync sends FA; and parses response

- **WHEN** `GetDialFrequencyMhzAsync` is called on a connected instance
- **THEN** the implementation SHALL write `FA;` to the serial port, read the response, and return the VFO-A frequency in MHz parsed from the serial CAT response format `FA<11-digit-Hz>;` (e.g. `FA00014074000;` → `14.074`)

#### Scenario: GetDialFrequencyMhzAsync throws on malformed response

- **WHEN** the serial port returns a response that does not start with `FA` or is not 15 characters long
- **THEN** `GetDialFrequencyMhzAsync` SHALL throw an `InvalidOperationException` with a message that includes the raw response for diagnostics

#### Scenario: GetDialFrequencyMhzAsync throws on read timeout

- **WHEN** no response arrives within 500 ms of the `FA;` command being written
- **THEN** `GetDialFrequencyMhzAsync` SHALL throw a `TimeoutException`

#### Scenario: SetDialFrequencyMhzAsync sends FA set command

- **WHEN** `SetDialFrequencyMhzAsync` is called with a frequency in MHz (e.g., `14.074`)
- **THEN** the implementation SHALL write `FA<11-digit-Hz>;` to the serial port, where the Hz value is rounded to the nearest integer and zero-padded to exactly 11 digits (e.g., `FA00014074000;`)
- **AND** the method SHALL return after the write completes without reading back a confirmation

#### Scenario: SetDialFrequencyMhzAsync Hz formatting is exact

- **WHEN** `SetDialFrequencyMhzAsync` is called with `7.074` MHz
- **THEN** the bytes written to the serial port SHALL be `FA00007074000;` (14 characters plus terminator)

#### Scenario: DisconnectAsync closes the serial port

- **WHEN** `DisconnectAsync` is called
- **THEN** the serial port SHALL be closed and `IsConnected` SHALL return `false`

#### Scenario: Dispose closes the serial port

- **WHEN** a `SerialCatConnection` instance is disposed while the port is open
- **THEN** the serial port SHALL be closed

---

### Requirement: RigctldConnection implements IRadioConnection

`OpenWSFZ.Rig` SHALL provide a class `RigctldConnection` that implements `IRadioConnection` using a `TcpClient` connected to a running `rigctld` daemon. The class SHALL be constructable with a hostname and port (defaults `"127.0.0.1"` and `4532`). All network I/O SHALL use a 500 ms receive timeout.

Commands sent by `RigctldConnection`:
- `\get_freq\n` (frequency **query**, sent by `GetDialFrequencyMhzAsync`)
- `\set_freq <Hz>\n` (frequency **set**, sent by `SetDialFrequencyMhzAsync`)

No transmit, PTT, or rig-altering commands SHALL be sent by this class.

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

- **WHEN** rigctld returns a response beginning with `RPRT` or a value that cannot be parsed as a non-negative integer
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
