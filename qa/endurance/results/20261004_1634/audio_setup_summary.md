### Audio-setup sampler (#194)

- **Sampler output: OK** — coverage 100.0 % of 46594 s (heartbeats with no gap over 70 s; max gap 61.2 s; PARTIAL below 98 %).
- Worker crashes: **0**; restarts: **0**.
- First (cold) sample 646.0 ms; warm sample max 140.8 ms.
- Setup changes logged: **64**; `unverified_start_diff` (excluded from the join): 0.
- `VBVMR_IsParametersDirty`: 9302 calls, 61 returned non-zero, longest loop 3 calls.
- Scan join window: detected_utc in [S-30 s, S+40 s].
- Scan-flagged slots joined: not yet computed (run `summarize.py <jsonl> --flagged <flagged_slots.csv>` after the scan).
- Teardown: return code 0, force-killed False, pidfile removed True, orphans found [].
