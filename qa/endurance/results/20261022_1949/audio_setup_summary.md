### Audio-setup sampler (#194)

- **Sampler output: OK** — coverage 100.0 % of 43924 s (heartbeats with no gap over 70 s; max gap 60.5 s; PARTIAL below 98 %).
- Worker crashes: **0**; restarts: **0**.
- First (cold) sample 657.8 ms; warm sample max 130.7 ms.
- Setup changes logged: **67**; `unverified_start_diff` (excluded from the join): 1.
- `VBVMR_IsParametersDirty`: 8716 calls, 3 returned non-zero, longest loop 3 calls.
- Scan join window: detected_utc in [S-30 s, S+40 s].
- Scan-flagged slots joined: not yet computed (run `summarize.py <jsonl> --flagged <flagged_slots.csv>` after the scan).
- Teardown: return code 0, force-killed False, pidfile removed True, orphans found [].
