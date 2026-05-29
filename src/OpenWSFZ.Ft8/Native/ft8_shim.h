/*
 * ft8_shim.h — Public ABI for the OpenWSFZ libft8.dll shim
 *
 * This header declares the two symbols exported by libft8.dll:
 *   ft8_lib_version_check()  — ABI sentinel; must return FT8_SHIM_VERSION
 *   ft8_decode_all()         — decode FT8 signals from a 15-second PCM buffer
 *
 * The managed caller (Ft8LibInterop.cs) P/Invokes both functions.
 * Marshal.SizeOf<Ft8NativeResult>() MUST equal sizeof(FT8Result) = 48 bytes.
 *
 * Layout:
 *   offset  0 : int   freq_hz  (4 bytes)
 *   offset  4 : float dt       (4 bytes)
 *   offset  8 : int   snr      (4 bytes)
 *   offset 12 : char  message  (36 bytes, null-terminated, max 35 chars)
 *   total     : 48 bytes — no padding
 */

#ifndef FT8_SHIM_H
#define FT8_SHIM_H

#ifdef __cplusplus
extern "C" {
#endif

/* Bump this constant whenever the ABI changes (struct layout, function
 * signatures). The managed loader checks it matches FT8_SHIM_VERSION. */
#define FT8_SHIM_VERSION 20240001

/* One decoded FT8 message. sizeof(FT8Result) == 48. */
typedef struct
{
    int   freq_hz;      /* Centre frequency of the signal, Hz                  */
    float dt;           /* Time offset from cycle start, seconds               */
    int   snr;          /* SNR estimate, dB (approx: cand.score * 0.5)         */
    char  message[36];  /* Null-terminated text, max 35 chars (FTX_MAX_MESSAGE_LENGTH) */
} FT8Result;

/*
 * ft8_lib_version_check — ABI sentinel.
 * Returns the compile-time constant FT8_SHIM_VERSION.
 * The managed loader calls this immediately after NativeLibrary.Load and
 * throws InvalidOperationException if the value does not match.
 */
int ft8_lib_version_check(void);

/*
 * ft8_decode_all — decode all FT8 signals from a 15-second PCM buffer.
 *
 * Parameters:
 *   pcm         — float32 samples, 12 kHz mono, normalised to [-1, 1]
 *   pcm_len     — must be 180 000 (15 s × 12 000 Hz)
 *   results     — caller-allocated array of FT8Result; receives the decoded messages
 *   max_results — size of the results array; at most this many messages are written
 *
 * Returns: number of unique messages written to results (0..max_results).
 *          Returns -1 if pcm_len != 180 000.
 */
int ft8_decode_all(
    const float* pcm,
    int          pcm_len,
    FT8Result*   results,
    int          max_results
);

#ifdef __cplusplus
}
#endif

#endif /* FT8_SHIM_H */
