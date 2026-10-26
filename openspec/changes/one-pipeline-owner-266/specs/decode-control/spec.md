## ADDED Requirements

### Requirement: The pipeline has one owner and is reconciled from the current configuration

One component of the daemon SHALL be the only code that constructs a `CycleFramer`, holds the framer's cancellation and task, starts or stops audio capture and resets the audio, data-flow and spectrum monitors, and it SHALL serialise those actions with one semaphore. It SHALL expose one entry point, `ReconcileAsync(reason, forceRestart)`, which inside the semaphore reads the **current** configuration (never a value captured when the trigger fired) and converges as follows:

- the pipeline is **desired** if and only if `AudioDeviceId` is non-null and `DecodingEnabled` is true;
- running on a device other than `AudioDeviceId`, or `forceRestart` with the pipeline desired: stop, then start;
- desired and not running: start; not desired and running: stop; otherwise: no action.

"Running" SHALL mean the owner's own record that it started a pipeline on a device and has not stopped it; a capture that has failed while the record stands is still "running" (its retry belongs to the capture-recovery coordinator, which calls the owner with `forceRestart`). At most one framer SHALL exist at any time. The start step SHALL stop any framer found in the slot before it starts a new one and, if it found one, SHALL log one Warning without a callsign or other message text (`Pipeline start found a framer still running; stopped it first (reason: {Reason}).`); that Warning SHALL NOT occur on any normal path. The owner SHALL log at Information `Pipeline started on '{Device}' (reason: {Reason}).` and `Pipeline stopped (reason: {Reason}).`, so that starts minus stops is the number of framers running (0 or 1). Startup auto-start, `CaptureFailed` and watchdog retries, the configuration save handler (device or `DecodingEnabled` changed) and shutdown SHALL all go through the owner; shutdown SHALL keep the order health monitor, framer, decoder dispose, capture.

#### Scenario: Device chosen while off, then Start gives exactly one framer

- **WHEN** decoding is off, a device is saved, and decoding is then started
- **THEN** no framer SHALL have existed before the start and exactly one framer SHALL exist after it, on the saved device

#### Scenario: Repeated stop and start never leaves a second framer

- **WHEN** decoding alternates off and on 50 times
- **THEN** the number of live framers SHALL never exceed one at any step and SHALL be one at the end

#### Scenario: Start while running does not restart

- **WHEN** `POST /api/v1/decode/start` is called while the pipeline is running, or the same device is saved again
- **THEN** the pipeline SHALL continue running without a stop or a start

#### Scenario: The order in which queued reconciles run does not matter

- **WHEN** a device change, a Start and a Stop are queued in any order and the configuration is changed again while a reconcile waits for the semaphore
- **THEN** the pipeline SHALL end in the state the **last** configuration describes, with at most one framer at every step

#### Scenario: A retry while decoding is off starts nothing

- **WHEN** a capture-failure retry, a watchdog restart or an adoption of a rotated device identifier reaches the owner while `DecodingEnabled` is false
- **THEN** no capture and no framer SHALL be started

#### Scenario: An adoption while decoding is on causes exactly one start

- **WHEN** the capture-recovery coordinator adopts a rotated device identifier and saves it while decoding is on
- **THEN** exactly one pipeline start SHALL result

#### Scenario: A cleared device stops the pipeline

- **WHEN** `AudioDeviceId` is set to null while the pipeline is running
- **THEN** the pipeline SHALL be stopped and not started again

#### Scenario: Shutdown leaves nothing running

- **WHEN** the daemon shuts down while the pipeline runs, or while a reconcile is in progress
- **THEN** shutdown SHALL wait for that reconcile, then leave no framer and no capture running

#### Scenario: The defence fires only when needed

- **WHEN** the slot holds a live framer at the start step
- **THEN** that framer SHALL be stopped before the new one starts and exactly one Warning SHALL be logged; on every normal path the count of that Warning SHALL be zero
