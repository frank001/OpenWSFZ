# Developer task: #225 phase 2, AMENDMENT 1 - never resolve the 10-bit hash (call3 is always `<...>`)

To: Developer. From: QA, on the Architect's Addendum 3 ruling (a) and Addendum 4 R4a (`arch/dxped-225-review` `47462f04`, `ae0f381e`). Base: your build `87beed94` on `feat/dxpedition-decode-225`. This amends `dev-tasks/2026-10-19-dxpedition-fox-hound-decode-225.md`; everything not named here is unchanged.

## Why (data, not an opinion)
- The quick-check replay (455 cycles) found ONE different Fox call: a 10-bit hash collision, 1 wrong of 8 resolved.
- The live night on `87beed94` (19.4 h, 2026-10-19/20): 436 matched type-0.1 rows, unique-match resolved the Fox on only 16 of them (all right); over both runs 1 of 24 resolved names was wrong. The gain is small and a wrong name is the worse error (F-001: no name beats a wrong name).
- Ruling (a), Architect: **in phase 2 the 10-bit hash is never resolved. `call3` is always `<...>`.** (b) rejected; (c) goes to phase 3, where a Hound can verify the hash against the Fox it chose.

## Change (spec section 1.34 and section 3 "Hash policy")
1. `cb_lookup_hash` (`ft8_shim.c`): the 10-bit type returns "not found" in every case, whatever the table holds. Keep the 22-bit and 12-bit paths exactly as they are (12-bit keeps its F-001 unique-match). Say in a comment WHY (this ruling, F-001), and that phase 3 may add verification against a chosen Fox.
2. Do NOT delete the "save every unpacked call to the session table" behaviour for calls the unpacker sees (that is `message.c`, not the lookup); only the 10-bit LOOKUP stops resolving.
3. **Noise suppression: OPTION B (Captain's decision 2026-10-20 14:54Z by the Architect's clock; recorded in `d2b32736` on `arch/dxped-225-review`): type 0.1 rows are EXEMPT from noise suppression.** Every 0.1 row has an unresolved `call3`, so its region is always a lookup miss; the exemption makes it shown anyway. This REPLACES spec section 2.4's "existing noise-suppression rule applies unchanged" for 0.1 rows ONLY. An ordinary (non-0.1) region-miss row is still hidden exactly as today. Identify a 0.1 row by the decode's type (i3 = 0, n3 = 1) carried through, not by sniffing the text for `RR73;` if the type is available; say which you used. Exempt rows stay display-only and inert for every other consumer (spec section 2.3).
4. Tests: replace the 0/1/2-match 10-bit lookup test by one that puts 0, 1 and 2 matching callsigns in the table and asserts `<...>` in all three. Keep the 12-bit/22-bit unchanged test.
   **Suppression tests, for EACH batch number 1, 2 and 3 (Architect):** (a) with noise suppression ON, a 0.1 row is shown; (b) with noise suppression ON, an ordinary region-miss row is still hidden. Also one test with suppression OFF showing the 0.1 row (unchanged).
5. Bump the shim version as your convention requires (the native decode output changes) and give the new Windows `libft8.dll` and Linux `libft8.so` SHA-256.

## Also, for the PR gate (Architect R4b) - cite or add
The live night's "0 spots" did not test the guard (external reporting was OFF). QA will replay on your amended build with reporting ON, pointed at a loopback UDP listener (0.1-row datagrams = 0; ordinary datagrams > 0 as the positive control). **If your per-batch unit tests already cover "a 0.1 row never reaches the external reporting datagram for batches 1, 2 and 3", name them in your report; if they do not, add them.**

## Hand-back
Branch and commit SHA(s); `git diff --stat origin/main..HEAD` (expected: `ft8_shim.c`, shim version file(s), tests; no ABI struct change); the new shim number and both library SHA-256 values; the full unfiltered Windows test result (state the exact command; a filtered-out suite is silent, HK-022) and the ASan/UBSan self-test; the test names for the datagram point above.

## Acceptance (QA)
- V2b becomes **"any resolved `call3` = FAIL"** (the Architect's wording); QA re-runs the quick-check replay and the loopback reporting replay on the amended build before any PR. V1, V2c, M1 as before; M2 is not measurable on a build where the type is supported (note, no bar).
- Push, PR and merge only on the Captain's explicit go (HK-010, HK-033).
