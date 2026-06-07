# Option A — Upstream ft8_lib Audit

**Date:** 2026-06-07  
**Auditor:** Claude Code  
**Pinned version:** kgoba/ft8_lib v2.0 (tag `2.0`, commit `50ee0c06`)

---

## Repository Status

**Active.** Last commit 2025-08-24 — not abandoned. Only two tags exist: `0.1` and `2.0`.

---

## Commits Since v2.0

Exactly one commit above the pinned v2.0 tag:

| SHA | Date | Title |
|---|---|---|
| `9fec6ca3` | 2025-08-24 | non-standard callsigns; special CQ; field type annotation (#47) |

---

## What PR #47 Changes

Files modified:

| File | Purpose |
|---|---|
| `ft8/message.c` | Message text encoding/decoding logic |
| `ft8/message.h` | Message header — new types and modified function signature |
| `ft8/text.c` / `ft8/text.h` | Text utility functions |
| `demo/decode_ft8.c` | Demo program only |
| `Makefile` | Build system |
| `test/test.c` | Unit tests |

**None of the decode pipeline files are touched:**  
`ft8/decode.c`, `ft8/ldpc.c`, `common/monitor.c`, `common/monitor.h` — all unchanged since v2.0.

### Key changes in PR #47

1. **Non-standard callsign support with prefixes** (e.g. `EA/K1ABC`, `KH6/W9XYZ`) — new encode/decode path.
2. **Special CQ encoding fixes** — `CQ_nnn` (three digits) and `CQ_a[bcd]` (four letters) now correctly encoded with space delimiter rather than underscore.
3. **Field type annotation API** — new `ftx_message_offsets_t` struct and `ftx_field_t` enum added so callers can know which spans of the decoded text are callsigns, grids, tokens, etc.
4. **`copy_token()` null-terminator fix** — buffer overflow fix found with ASAN.
5. **`ftx_message_encode()` fallback** — falls back to free text for >3-token messages instead of misfiring a type 1 encode.
6. **`pack_basecall()` added to public API** — lets callers pre-check whether a callsign is standard.

---

## ABI Impact

`ftx_message_decode()` gained a **4th parameter**:

```c
/* v2.0 */
ftx_message_rc_t ftx_message_decode(const ftx_message_t* msg,
                                    ftx_callsign_hash_interface_t* hash_if,
                                    char* message);

/* post-v2.0 (9fec6ca3) */
ftx_message_rc_t ftx_message_decode(const ftx_message_t* msg,
                                    ftx_callsign_hash_interface_t* hash_if,
                                    char* message,
                                    ftx_message_offsets_t* offsets);  /* new */
```

Our `ft8_shim.c` currently calls the 3-argument form. Updating to 9fec6ca3 would require a 1-line shim change to pass `NULL` as the 4th argument (we don't need the field type metadata). This is a **source-level change only** — not a binary ABI issue since we compile our own shim. The `FT8Result` struct layout and `ft8_decode_all()` / `ft8_lib_version_check()` signatures are unchanged.

---

## Verdict

**Upstream improvement not available for D-001 purposes.**

The single post-v2.0 commit improves message text encoding/decoding for non-standard callsigns and adds field type metadata. It is **entirely orthogonal** to co-channel decode sensitivity. No multi-pass decode, no SIC, no LDPC improvement, no waterfall processing change.

**Recommendation:** Do not update the upstream binary as part of this change. The rebuild effort (three platforms, CI, binary commits) is not justified for a feature (non-standard callsigns) that OpenWSFZ does not currently expose. If non-standard callsign support is ever needed it warrants its own dedicated change.

**Proceed directly to Option B** (soft SNR-scaled spectrogram suppression).

---

## Task 1.3 Status

- [x] Audit completed: one post-v2.0 commit found, decode pipeline unchanged.
- [ ] Verdict recorded: **no upstream update; proceed to Option B**.
