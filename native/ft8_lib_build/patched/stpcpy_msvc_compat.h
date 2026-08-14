#ifndef STPCPY_MSVC_COMPAT_H
#define STPCPY_MSVC_COMPAT_H

/*
 * r0-reproducible-native-build: MSVC's <string.h> does not declare stpcpy()
 * (POSIX/GNU extension only; the Linux/macOS builds get it via -D_GNU_SOURCE,
 * see BUILD.md). Vendored ft8/message.c (upstream, unmodified) calls stpcpy()
 * with no prototype in scope under MSVC. Without one, MSVC falls back to
 * "implicit extern returning int" (warning C4013) and truncates the returned
 * char* to 32 bits on assignment (warning C4047) -- MECHANICALLY CONFIRMED
 * during R0 implementation (2026-08-14) to reproduce D-006's root cause
 * exactly: a 32-bit pointer truncation in ftx_message_decode()'s "R " reply-
 * prefix path that caused a fatal 0xC0000005 access violation when the
 * thread stack sat above the 4 GB VA boundary (dump analysis
 * ft8_av_20260614_133145_28356.dmp; see src/OpenWSFZ.Ft8/Native/ft8_shim.c's
 * "fix-d006-ptr-truncation (FT8_SHIM_VERSION 20260015)" history comment).
 *
 * That fix was applied as a single hand-patched opcode byte directly to the
 * pre-built native/ft8_lib_build/obj/message.obj (0x63 MOVSXD -> 0x8B MOV at
 * offset 0x01B27) -- carved out of .gitignore for exactly that reason -- and
 * NO source-level fix was ever written, because until R0, message.c was
 * never recompiled by rebuild_shim.bat at all.
 *
 * Force-including this prototype ahead of message.c's compilation (see the
 * /FI flag on its cl invocation in rebuild_shim.bat) gives the compiler the
 * correct 64-bit-returning signature, restoring the D-006 fix at the source
 * level -- without changing one byte of the vendored tree (per this change's
 * "vendor as-is, upstream content stays content-identical" requirement).
 * The actual definition already exists and is unaffected: see the
 * `#ifdef _MSC_VER` block in src/OpenWSFZ.Ft8/Native/ft8_shim.c, which the
 * linker resolves this call against.
 */
#ifdef _MSC_VER
char* stpcpy(char* dest, const char* src);
#endif

#endif /* STPCPY_MSVC_COMPAT_H */
