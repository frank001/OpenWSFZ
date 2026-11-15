### Audio-setup sampler (#194)

- **Sampler output: OK** — coverage 100.0 % of 69945 s (heartbeats with no gap over 70 s; max gap 60.7 s; PARTIAL below 98 %).
- Worker crashes: **0**; restarts: **0**.
- First (cold) sample 656.3 ms; warm sample max 130.9 ms.
- Setup changes logged: **358**; `unverified_start_diff` (excluded from the join): 3.
- `VBVMR_IsParametersDirty`: 13895 calls, 22 returned non-zero, longest loop 3 calls.
- Scan join window: detected_utc in [S-30 s, S+40 s].
- Scan-flagged slots joined: not yet computed (run `summarize.py <jsonl> --flagged <flagged_slots.csv>` after the scan).
- Teardown: return code 0, force-killed False, pidfile removed True, orphans found [].
