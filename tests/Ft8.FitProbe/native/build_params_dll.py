"""
build_params_dll.py -- TEST-ONLY (sub-feas-speed-redesign tasks.md 15.3; design.md D11, "fitted-parameter visibility").
Builds libft8.dll from the repo's native sources with ONE difference: subfeas_fit.c is replaced by a COPY of the file you
name, patched to RECORD the fitted parameters of the last fit on the calling thread and to export one extra function:

    int ft8_subfeas_fit_params(double* out)     // out[5]: dt_s, df_hz, fdot_hz_per_s, start_sample, fine_fit rc
                                                // returns 1 if the last ft8_subfeas_fit_signal on THIS thread got that far
                                                // (rc -1, -4 before the fit returns 0)

The export exists only in this test DLL; the shipped export list and ABI are untouched, and the product file is never
edited. The SAME patch applies to the Stage A source and to the B2 source (every insertion is anchored on text both
have, and the script FAILS if an anchor is missing or ambiguous), so E2 compares like with like:

    # Stage A (main's fit):
    git show origin/main:native/ft8_lib_vendor/subfeas/subfeas_fit.c > <dir>/subfeas_fit_stageA.c
    python build_params_dll.py <dir>/subfeas_fit_stageA.c <dir>/stageA        # -> <dir>/stageA/libft8.dll
    # B2 (this branch's fit):
    python build_params_dll.py ../../../native/ft8_lib_vendor/subfeas/subfeas_fit.c <dir>/b2

Both DLLs carry THIS checkout's ft8_shim.c (so the same shim version literal and the same managed ABI check); only the
fit differs. Call it from managed code through the same Ft8LibInterop.SubfeasFitSignal path as the product, then read the
parameters on the SAME thread with the extra export (see Ft8.FitProbe's `fitparams` mode).

Derived from native/ft8_lib_build/rebuild_shim.bat (same flags, sources, object list); only the obj/output directories
(scratch, never the repo's obj\\ or the tracked DLL), the subfeas source path and the export list are rewritten. Nothing is
copied into src/ or native/. Windows-only test scaffolding.

Usage: python build_params_dll.py <subfeas_fit.c> <out_dir>   ->   <out_dir>\\libft8.dll
"""
import os
import re
import subprocess
import sys

src_path = os.path.abspath(sys.argv[1])
out_dir = os.path.abspath(sys.argv[2])
here = os.path.dirname(os.path.abspath(__file__))
root = os.path.abspath(os.path.join(here, '..', '..', '..'))
os.makedirs(os.path.join(out_dir, 'obj'), exist_ok=True)

# ---- patch the copy -----------------------------------------------------------------------------------------------
s = open(src_path, encoding='utf-8', newline='').read().replace('\r\n', '\n')


def once(old, new):
    global s
    n = s.count(old)
    assert n == 1, f'anchor found {n} times (need exactly 1): {old[:80]!r}'
    s = s.replace(old, new, 1)


once('#include "../fft/kiss_fft.h"', '#include "kiss_fft.h"')

once('\ntypedef struct { float r, i; } cf32;', r'''
/* ===================== TEST-ONLY fitted-parameter record (build_params_dll.py) ================================== */
static __declspec(thread) double pp_last[5];     /* per worker thread: the last fit's dt_s, df_hz, fdot, start_sample, rc */
static __declspec(thread) int    pp_have;
/* ================================================================================================================= */

typedef struct { float r, i; } cf32;''')

once('    nominal_t_s = (double)decoded_dt_s + SUBFEAS_TAU0_S;\n',
     '    pp_have = 0;\n    nominal_t_s = (double)decoded_dt_s + SUBFEAS_TAU0_S;\n')

once('''            &dt_s, &df_hz, &fdot, &start_sample, ws->r_base_final, cancel_flag);
    if (ok == -4) return -4;''', '''            &dt_s, &df_hz, &fdot, &start_sample, ws->r_base_final, cancel_flag);
    if (ok == 1) { pp_last[0] = dt_s; pp_last[1] = df_hz; pp_last[2] = fdot; pp_last[3] = (double)start_sample; pp_last[4] = 1.0; pp_have = 1; }
    if (ok == -4) return -4;''')

s += '''

/* ===================== TEST-ONLY export (build_params_dll.py) =================================================== */
int ft8_subfeas_fit_params(double* out)
{
    int i;
    if (!out || !pp_have) return 0;
    for (i = 0; i < 5; i++) out[i] = pp_last[i];
    return 1;
}
'''
patched_c = os.path.join(out_dir, 'subfeas_fit_params.c')
open(patched_c, 'w', encoding='utf-8', newline='').write(s)

# ---- build, derived from rebuild_shim.bat -------------------------------------------------------------------------
bat = open(os.path.join(root, 'native', 'ft8_lib_build', 'rebuild_shim.bat'), encoding='utf-8', newline='').read().replace('\r\n', '\n')


def sub_once(old, new):
    global bat
    assert bat.count(old) == 1, (bat.count(old), old[:70])
    bat = bat.replace(old, new, 1)


bat = re.sub(r'for %%i in \("%~dp0\.\.\\\.\."\) do set "FT8_ROOT=%%~fi"', lambda m: f'set "FT8_ROOT={root}"', bat, count=1)
assert f'set "FT8_ROOT={root}"' in bat
bat = bat.replace('%FT8_ROOT%\\native\\ft8_lib_build\\obj', out_dir + '\\obj')
bat = bat.replace('%FT8_ROOT%\\native\\ft8_lib_build\\libft8.dll', out_dir + '\\libft8.dll')
sub_once('"%FT8_ROOT%\\native\\ft8_lib_vendor\\subfeas\\subfeas_fit.c"', f'"{patched_c}"')
sub_once('  /EXPORT:ft8_subfeas_fit_signal ^\n', '  /EXPORT:ft8_subfeas_fit_signal ^\n  /EXPORT:ft8_subfeas_fit_params ^\n')
a = bat.index('echo === Copying DLL to repo ===')
b = bat.index('echo === SUCCESS ===')
bat = bat[:a] + bat[b:]
assert 'win-x64\\libft8.dll' not in bat

gen = os.path.join(out_dir, 'build_params.bat')
open(gen, 'w', encoding='utf-8', newline='').write(bat.replace('\n', '\r\n'))
r = subprocess.run(['cmd', '/c', gen], capture_output=True, text=True)
open(os.path.join(out_dir, 'build_params.log'), 'w', encoding='utf-8').write(r.stdout + r.stderr)
ok = os.path.exists(os.path.join(out_dir, 'libft8.dll')) and '=== SUCCESS ===' in r.stdout
print('BUILD OK' if ok else 'BUILD FAILED (see build_params.log)', os.path.join(out_dir, 'libft8.dll'))
sys.exit(0 if ok else 1)
