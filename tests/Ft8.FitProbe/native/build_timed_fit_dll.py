"""
build_timed_fit_dll.py -- TEST-ONLY. Builds libft8.dll from the repo's native sources with ONE difference:
subfeas_fit.c is replaced by the timing-instrumented COPY made by make_timed_fit.py (plus two test-only exports).
ft8_shim.c and every other source are the shipped ones, so the shim version and every other export are unchanged.

Derived from native/ft8_lib_build/rebuild_shim.bat itself (same flags, sources, object list); only the obj/output
directories (scratch, never the repo's obj\\ or the tracked DLL), the subfeas source path and the export list are
rewritten. Nothing is copied into src/ or native/. Windows-only test scaffolding.

Usage: python build_timed_fit_dll.py <out_dir>   ->   <out_dir>\\libft8.dll
"""
import os
import re
import subprocess
import sys

out_dir = os.path.abspath(sys.argv[1])
here = os.path.dirname(os.path.abspath(__file__))
root = os.path.abspath(os.path.join(here, '..', '..', '..'))
os.makedirs(os.path.join(out_dir, 'obj'), exist_ok=True)

timed_c = os.path.join(out_dir, 'subfeas_fit_timed.c')
subprocess.run([sys.executable, os.path.join(here, 'make_timed_fit.py'),
                os.path.join(root, 'native', 'ft8_lib_vendor', 'subfeas', 'subfeas_fit.c'), timed_c], check=True)

bat = open(os.path.join(root, 'native', 'ft8_lib_build', 'rebuild_shim.bat'), encoding='utf-8', newline='').read().replace('\r\n', '\n')

def sub_once(old, new):
    global bat
    assert bat.count(old) == 1, (bat.count(old), old[:70])
    bat = bat.replace(old, new, 1)

bat = re.sub(r'for %%i in \("%~dp0\.\.\\\.\."\) do set "FT8_ROOT=%%~fi"', lambda m: f'set "FT8_ROOT={root}"', bat, count=1)
assert f'set "FT8_ROOT={root}"' in bat
bat = bat.replace('%FT8_ROOT%\\native\\ft8_lib_build\\obj', out_dir + '\\obj')
bat = bat.replace('%FT8_ROOT%\\native\\ft8_lib_build\\libft8.dll', out_dir + '\\libft8.dll')
sub_once('"%FT8_ROOT%\\native\\ft8_lib_vendor\\subfeas\\subfeas_fit.c"', f'"{timed_c}"')
sub_once('  /EXPORT:ft8_subfeas_fit_signal ^\n', '  /EXPORT:ft8_subfeas_fit_signal ^\n  /EXPORT:ft8_subfeas_pt_get ^\n  /EXPORT:ft8_subfeas_pt_frequency ^\n')
a = bat.index('echo === Copying DLL to repo ===')
b = bat.index('echo === SUCCESS ===')
bat = bat[:a] + bat[b:]
assert 'win-x64\\libft8.dll' not in bat

gen = os.path.join(out_dir, 'build_timed_fit.bat')
open(gen, 'w', encoding='utf-8', newline='').write(bat.replace('\n', '\r\n'))
r = subprocess.run(['cmd', '/c', gen], capture_output=True, text=True)
open(os.path.join(out_dir, 'build_timed_fit.log'), 'w', encoding='utf-8').write(r.stdout + r.stderr)
ok = os.path.exists(os.path.join(out_dir, 'libft8.dll')) and '=== SUCCESS ===' in r.stdout
print('BUILD OK' if ok else 'BUILD FAILED (see build_timed_fit.log)', os.path.join(out_dir, 'libft8.dll'))
sys.exit(0 if ok else 1)
