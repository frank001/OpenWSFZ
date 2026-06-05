## MODIFIED Requirements

### Requirement: SerialCatConnection implements IRadioConnection

`OpenWSFZ.Rig` SHALL provide a class `SerialCatConnection` that implements `IRadioConnection` using `System.IO.Ports.SerialPort` and the serial CAT command set. The class SHALL be constructable with a port name and baud rate. All serial I/O SHALL use a 500 ms `ReadTimeout`.

`SerialCatConnection` SHALL support two CAT operations:

- **Frequency query**: `GetDialFrequencyMhzAsync` sends `FA;` and parses the VFO-A frequency from the rig's response.
- **Frequency set**: `SetDialFrequencyMhzAsync` sends `FA<Hz>;` with the Hz value zero-padded to the rig's native digit width (self-calibrated from the first successful query response). No mode-set or PTT commands SHALL be sent by this class.

The rig's native digit width SHALL be discovered automatically: on the first successful `GetDialFrequencyMhzAsync` call, the class SHALL record the digit count of the FA response and use that same width for all subsequent `SetDialFrequencyMhzAsync` calls. Until the first successful query, `SetDialFrequencyMhzAsync` SHALL fall back to an 11-digit format.

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
