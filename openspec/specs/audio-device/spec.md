# audio-device Specification

## Purpose

Specifies audio capture device enumeration and the REST endpoint that exposes the available
input device list to the web frontend for selection.

## Requirements

### Requirement: USB audio capture device enumeration

The application SHALL enumerate audio capture devices available on the host OS and expose them through a stable `IAudioDeviceProvider` interface. The implementation SHALL use OS-native APIs (WASAPI on Windows; subprocess-based enumeration on Linux and macOS). The interface SHALL return an empty list — never throw — when no devices are found or the underlying tool is unavailable. On Windows, enumeration SHALL be performed on a COM STA thread to satisfy WASAPI's apartment-threading requirement.

#### Scenario: Devices enumerated on Windows via WASAPI

- **WHEN** `IAudioDeviceProvider.GetDevicesAsync()` is called on Windows
- **THEN** the implementation SHALL return a list of `AudioDeviceInfo` records, one per active WASAPI capture endpoint, each containing at minimum a non-empty `Id` and a human-readable `Name`

#### Scenario: Devices enumerated on Linux via arecord

- **WHEN** `IAudioDeviceProvider.GetDevicesAsync()` is called on Linux
- **THEN** the implementation SHALL invoke `arecord --list-devices`, parse the output, and return a list of `AudioDeviceInfo` records representing each reported capture device

#### Scenario: Enumeration tool absent or returns non-zero

- **WHEN** `IAudioDeviceProvider.GetDevicesAsync()` is called and the underlying tool is absent or exits with a non-zero code
- **THEN** the implementation SHALL return an empty list and SHALL NOT throw an exception

#### Scenario: No capture devices present

- **WHEN** `IAudioDeviceProvider.GetDevicesAsync()` is called on a host with no audio capture devices
- **THEN** the implementation SHALL return an empty list (zero elements)

#### Scenario: Windows enumeration succeeds from a non-STA calling thread

- **WHEN** `IAudioDeviceProvider.GetDevicesAsync()` is called from a thread-pool thread (MTA apartment)
- **THEN** the implementation SHALL internally switch to a COM STA thread for the `MMDeviceEnumerator` call and return the correct device list without throwing

---

### Requirement: Audio device REST endpoint

The web server SHALL expose `GET /api/v1/audio/devices` that returns the current list of enumerated audio capture devices as a JSON array.

#### Scenario: Endpoint returns device list

- **WHEN** a client sends `GET /api/v1/audio/devices`
- **THEN** the server SHALL respond with HTTP 200, `Content-Type: application/json`, and a JSON array where each element contains at minimum `id` and `name` string fields

#### Scenario: Endpoint returns empty array when no devices present

- **WHEN** a client sends `GET /api/v1/audio/devices` and no capture devices are available
- **THEN** the server SHALL respond with HTTP 200 and an empty JSON array `[]`
