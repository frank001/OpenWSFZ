### Audio-setup sampler (#194)

- **Sampler output: OK** — coverage 100.0 % of 54530 s (heartbeats with no gap over 70 s; max gap 60.6 s; PARTIAL below 98 %).
- Worker crashes: **0**; restarts: **0**.
- First (cold) sample 670.5 ms; warm sample max 130.4 ms.
- Setup changes logged: **131**; `unverified_start_diff` (excluded from the join): 2.
- `VBVMR_IsParametersDirty`: 10818 calls, 5 returned non-zero, longest loop 3 calls.
- Scan join window: detected_utc in [S-30 s, S+40 s].
- Scan-flagged slots joined: not yet computed (run `summarize.py <jsonl> --flagged <flagged_slots.csv>` after the scan).
- Teardown: return code 0, force-killed False, pidfile removed True, orphans found [].
