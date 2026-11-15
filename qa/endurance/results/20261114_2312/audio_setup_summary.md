### Audio-setup sampler (#194)

- **Sampler output: OK** — coverage 100.0 % of 42527 s (heartbeats with no gap over 70 s; max gap 60.6 s; PARTIAL below 98 %).
- Worker crashes: **0**; restarts: **0**.
- First (cold) sample 721.3 ms; warm sample max 105.3 ms.
- Setup changes logged: **78**; `unverified_start_diff` (excluded from the join): 3.
- `VBVMR_IsParametersDirty`: 8439 calls, 2 returned non-zero, longest loop 2 calls.
- Scan join window: detected_utc in [S-30 s, S+40 s].
- Scan-flagged slots joined: not yet computed (run `summarize.py <jsonl> --flagged <flagged_slots.csv>` after the scan).
- Teardown: return code 0, force-killed False, pidfile removed True, orphans found [].
