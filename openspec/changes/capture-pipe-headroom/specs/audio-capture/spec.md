## ADDED Requirements

### Requirement: The Linux capture source SHALL enlarge its stdout pipe and pin the capture period

The `arecord`-based capture source SHALL, right after starting the child and before reading its standard output, request a standard-output pipe of 1 MiB (`fcntl` `F_SETPIPE_SZ`), read the granted size back (`F_GETPIPE_SZ`) and log it at Information. If the request fails for any reason, the source SHALL log a Warning containing the error and SHALL continue capturing with the default pipe; the failure SHALL NOT end or delay the capture. The pipe request SHALL NOT change which bytes are read: the chunks yielded SHALL be byte-identical whether the request is granted or refused. `arecord` SHALL be started with the additional argument `--period-time=20000` and otherwise with the same arguments and environment as before.

#### Scenario: The pipe is enlarged and the granted size is logged

- **WHEN** the capture source starts `arecord` on Linux and the pipe request is granted
- **THEN** one Information line states the requested and the granted size
- **AND** the chunks yielded are those of the child's output

#### Scenario: A refused request is a Warning, not a failure

- **WHEN** the pipe request fails with an error
- **THEN** a Warning containing the error is logged and capture continues
- **AND** the chunks yielded are byte-identical to those of a run where the request is granted

#### Scenario: A descriptor that is not a pipe is not touched

- **WHEN** the child's standard output is not a pipe
- **THEN** no pipe request is made and a Warning is logged
- **AND** capture is unaffected

#### Scenario: The capture period is pinned

- **WHEN** the default start information is built for a device
- **THEN** the argument list is `-D <device> -f FLOAT_LE -r 12000 -c 1 -t raw --period-time=20000 -` and `LC_ALL=C` is in the environment
