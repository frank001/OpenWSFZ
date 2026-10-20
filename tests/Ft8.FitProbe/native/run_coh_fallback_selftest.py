"""
run_coh_fallback_selftest.py -- TEST-ONLY. Builds and runs coh_fallback_selftest.c (COH-FALLBACK Stage 1, shim 20260066): the
fine-sync estimator, F1b and its gate, the BP-only decode, the flags, and the cycle export over ft8_decode_all's retained candidate
list. The self-test #includes the product shim (ft8_shim.c) and links every other native source of libft8 from native/ (the same
set rebuild_shim.bat / build_linux.sh compile), with the shipped flags (MSVC /std:c11 /O2 /W3 on Windows; cc -std=c11 -O2
-D_GNU_SOURCE elsewhere). Nothing is written into src/ or native/; the executable goes to the scratch directory given
(default: a temp folder).

AddressSanitizer + UBSan: set COHFB_ASAN=1 on a non-Windows host (gcc/clang) to build with -fsanitize=address,undefined.

Usage: python run_coh_fallback_selftest.py [<scratch_dir>]
Exit code: the self-test's (0 = every assertion held), 3 when it could not be built (no compiler found).
"""
import os
import shutil
import subprocess
import sys
import tempfile

here = os.path.dirname(os.path.abspath(__file__))
root = os.path.abspath(os.path.join(here, '..', '..', '..'))
out = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else tempfile.mkdtemp(prefix='coh_fallback_selftest_')
os.makedirs(out, exist_ok=True)

vendor = os.path.join(root, 'native', 'ft8_lib_vendor')
patched = os.path.join(root, 'native', 'ft8_lib_build', 'patched')
native = os.path.join(root, 'src', 'OpenWSFZ.Ft8', 'Native')
test_c = os.path.join(here, 'coh_fallback_selftest.c')

# Every native source of libft8 except ft8_shim.c (the test #includes it).
sources = [
    os.path.join(vendor, 'ft8', 'constants.c'),
    os.path.join(vendor, 'ft8', 'crc.c'),
    os.path.join(patched, 'ft8', 'decode.c'),
    os.path.join(vendor, 'ft8', 'encode.c'),
    os.path.join(vendor, 'ft8', 'ldpc.c'),
    os.path.join(vendor, 'ft8', 'message.c'),
    os.path.join(vendor, 'ft8', 'text.c'),
    os.path.join(patched, 'common', 'monitor.c'),
    os.path.join(vendor, 'fft', 'kiss_fft.c'),
    os.path.join(vendor, 'fft', 'kiss_fftr.c'),
    os.path.join(vendor, 'refine', 'sync_refiner.c'),
    os.path.join(vendor, 'refine', 'coherent_llr.c'),
    os.path.join(vendor, 'subfeas', 'subfeas_fit.c'),
    os.path.join(vendor, 'refine', 'coherent_fallback.c'),
]
incs = [vendor, os.path.join(vendor, 'ft8'), os.path.join(vendor, 'common'), os.path.join(vendor, 'fft'),
        os.path.join(vendor, 'subfeas'), native]


def find_vcvars():
    """vcvars64.bat of any installed Visual Studio edition: vswhere first (any version), then the 2022/2019 list."""
    vswhere = os.path.join(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'), 'Microsoft Visual Studio', 'Installer', 'vswhere.exe')
    if os.path.exists(vswhere):
        try:
            found = subprocess.run([vswhere, '-latest', '-products', '*', '-requires', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
                                    '-find', r'VC\Auxiliary\Build\vcvars64.bat'], capture_output=True, text=True, timeout=60)
            if found.returncode == 0:
                lines = found.stdout.splitlines()
                if lines and os.path.exists(lines[0].strip()):
                    return lines[0].strip()
        except (OSError, subprocess.SubprocessError):
            pass
    bases = [os.environ.get('ProgramFiles', r'C:\Program Files'), os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')]
    for base in bases:
        for year in ('2022', '2019'):
            for edition in ('Community', 'Professional', 'Enterprise', 'BuildTools'):
                cand = os.path.join(base, 'Microsoft Visual Studio', year, edition, 'VC', 'Auxiliary', 'Build', 'vcvars64.bat')
                if os.path.exists(cand):
                    return cand
    return None


if os.name == 'nt':
    vcvars = find_vcvars()
    if vcvars is None:
        print('no Visual Studio vcvars64.bat found')
        sys.exit(3)
    print(f'using vcvars: {vcvars}')
    exe = os.path.join(out, 'coh_fallback_selftest.exe')
    bat = os.path.join(out, 'build_coh_fallback_selftest.bat')
    compat = os.path.join(patched, 'stpcpy_msvc_compat.h')
    incflags = ' '.join(f'/I "{i}"' for i in incs)
    lines = [
        '@echo off',
        f'call "{vcvars}" >nul',
        f'cd /d "{out}"',                       # the object files land in the scratch directory
        f'cl /nologo /std:c11 /O2 /W3 /FI "{compat}" {incflags} /Fe"{exe}" "{test_c}" ' + ' '.join(f'"{s}"' for s in sources),
    ]
    with open(bat, 'w', newline='') as f:
        f.write('\r\n'.join(lines) + '\r\n')
    build = subprocess.run(['cmd', '/c', bat], capture_output=True, text=True)
else:
    exe = os.path.join(out, 'coh_fallback_selftest')
    cc = shutil.which('cc') or shutil.which('gcc') or shutil.which('clang')
    if cc is None:
        print('no C compiler found')
        sys.exit(3)
    asan = os.environ.get('COHFB_ASAN') == '1'
    flags = ['-std=c11', '-D_GNU_SOURCE']
    if asan:
        flags += ['-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']
        print('AddressSanitizer + UBSan build')
    else:
        flags += ['-O2']
    cmd = [cc] + flags + [f'-I{i}' for i in incs] + ['-o', exe, test_c] + sources + ['-lm', '-lpthread']
    build = subprocess.run(cmd, capture_output=True, text=True)

with open(os.path.join(out, 'build.log'), 'w', encoding='utf-8') as log:
    log.write(build.stdout + build.stderr)
if build.returncode != 0 or not os.path.exists(exe):
    print('BUILD FAILED; see', os.path.join(out, 'build.log'))
    print((build.stdout + build.stderr)[-4000:])
    sys.exit(3)

env = dict(os.environ)
if os.name != 'nt' and os.environ.get('COHFB_ASAN') == '1':
    env['ASAN_OPTIONS'] = 'detect_leaks=0:abort_on_error=0:halt_on_error=1'
    env['UBSAN_OPTIONS'] = 'print_stacktrace=1:halt_on_error=1'
run = subprocess.run([exe], capture_output=True, text=True, env=env)
print(run.stdout)
if run.stderr:
    print(run.stderr)
if run.returncode != 0:
    sys.exit(run.returncode)

sys.exit(0)
