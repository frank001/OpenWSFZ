## ADDED Requirements

### Requirement: The primary target is sent to and listened on from one OS-assigned port

`ExternalReportingService` SHALL, while at least one target is enabled, use **one** IPv4 UDP socket, bound to an OS-assigned (ephemeral) local port, both to send every datagram to the primary target (index 0 of the enabled targets) and to receive inbound datagrams. The service SHALL NOT bind any socket to a target's port, with or without address reuse. The socket SHALL be created when a primary target first exists and disposed when none does; a change of the primary target's host or port SHALL NOT recreate it, so the peer sees the same source port throughout. On Windows the socket SHALL disable the UDP connection-reset notification, so that sending to a closed localhost port does not fail a later receive.

#### Scenario: The daemon starts before the peer

- **WHEN** the service is started with a primary target `127.0.0.1:P`, and only afterwards a peer binds port `P` (with address reuse, as GridTracker2 does)
- **THEN** the peer SHALL receive the service's Status and Decode datagrams within two reporting intervals, and the service SHALL hold no socket on `P`

#### Scenario: The peer starts before the daemon

- **WHEN** a peer is bound to port `P` and the service is then started with primary target `127.0.0.1:P`
- **THEN** the peer SHALL receive the service's Status and Decode datagrams within two reporting intervals

#### Scenario: The peer restarts while the service runs

- **WHEN** the peer's socket on `P` is closed and a new peer binds `P` while the service keeps running
- **THEN** the new peer SHALL receive the service's datagrams within two reporting intervals, without any action on the service

#### Scenario: A reply to the daemon's datagram reaches the daemon

- **WHEN** the peer sends Halt Tx (or a Reply with `honourInboundCommands` true) to the **source endpoint** of a datagram it received from the service
- **THEN** the service SHALL handle it exactly as inbound commands were handled before this change

#### Scenario: The service holds nothing on the target port

- **WHEN** the service is running with a primary target on port `P` and no peer is bound
- **THEN** a socket in another process SHALL be able to bind `P`

#### Scenario: The peer is absent and then appears

- **WHEN** the service has sent at least 20 datagrams to a closed localhost port on Windows, and a peer then binds that port and sends Halt Tx to the service's source endpoint
- **THEN** Halt Tx SHALL be handled, the receive loop SHALL be alive, and no inbound socket error SHALL have been logged for the earlier sends

#### Scenario: A change of the primary target keeps the source port

- **WHEN** the primary target's port is changed through the configuration store while the service runs
- **THEN** the source port observed by the peer SHALL be the same before and after the change

#### Scenario: A command sent unsolicited to the target port does not reach the service

- **WHEN** a peer sends Halt Tx to the target's well-known port without having received a datagram from the service
- **THEN** the service SHALL NOT receive it (the service listens only on its own OS-assigned port)
