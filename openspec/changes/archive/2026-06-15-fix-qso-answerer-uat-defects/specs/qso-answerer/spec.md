## MODIFIED Requirements

### Requirement: Retry on no-response in waiting states

In `WaitReport` and `WaitRr73`, if a decode cycle produces no message addressed to `tx.callsign` from the active partner, the service SHALL retransmit the last transmitted message. The retry counter SHALL increment. After `tx.retryCount` consecutive retransmits without a matching response, the service SHALL abort to `Idle` without writing an ADIF record.

The service SHALL NOT count the first empty cycle after entering `WaitReport` or `WaitRr73` as a missed response. This first cycle coincides with the service's own prior TX window; the capture RMS will be suppressed by the silence guard and there is no opportunity for the partner to have responded. The retry logic SHALL only activate from the second consecutive empty cycle onward.

#### Scenario: No decode in WaitReport triggers retransmit

- **WHEN** the service is in `WaitReport`, no decode is addressed to `tx.callsign`, and the retry counter is below `tx.retryCount`
- **THEN** the service SHALL retransmit the answer message and increment the retry counter

#### Scenario: Retry exhaustion in WaitReport aborts to Idle

- **WHEN** the retry counter reaches `tx.retryCount` without a matching response
- **THEN** the service SHALL abort to `Idle`, log the abort at Information level, and SHALL NOT write an ADIF record

#### Scenario: Retry counter resets on state advance

- **WHEN** the service advances from `WaitReport` to `TxReport`
- **THEN** the retry counter SHALL reset to zero for the `WaitRr73` waiting state

#### Scenario: First empty cycle after entering WaitReport is not a retry trigger

- **WHEN** the service enters `WaitReport` and the immediately following decode cycle is empty (silence guard or zero decodes)
- **THEN** the service SHALL NOT retransmit and SHALL NOT increment the retry counter; it SHALL wait for the next cycle before applying retry logic

#### Scenario: First empty cycle after entering WaitRr73 is not a retry trigger

- **WHEN** the service enters `WaitRr73` and the immediately following decode cycle is empty (silence guard or zero decodes)
- **THEN** the service SHALL NOT retransmit and SHALL NOT increment the retry counter; it SHALL wait for the next cycle before applying retry logic

#### Scenario: Second consecutive empty cycle in WaitReport triggers retry

- **WHEN** the service is in `WaitReport`, the first empty cycle was already skipped, a second consecutive empty cycle occurs, and the retry counter is below `tx.retryCount`
- **THEN** the service SHALL retransmit the answer message and increment the retry counter
