"""
run_freq_search_selftest.py -- TEST-ONLY. Builds and runs freq_search_selftest.c (B2, sub-feas-speed-redesign tasks.md
15.4): the pruned freq_search against the reference full-FFT search on synthetic inputs. Same compiler flags as the
shipped build (MSVC /std:c11 /O2 /W3 on Windows; cc -std=c11 -O2 elsewhere), no /fp:fast. Nothing is written into src/
or native/; the executable goes to the scratch directory given (default: a temp folder).

Usage: python run_freq_search_selftest.py [<scratch_dir>]
Exit code: the self-test's (0 = every assertion held), 3 when it could not be built (no compiler found).
"""
import os
import shutil
import subprocess
import sys
import tempfile

here = os.path.dirname(os.path.abspath(__file__))
root = os.path.abspath(os.path.join(here, '..', '..', '..'))
out = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else tempfile.mkdtemp(prefix='freq_search_selftest_')
os.makedirs(out, exist_ok=True)

test_c = os.path.join(here, 'freq_search_selftest.c')
kiss_c = os.path.join(root, 'native', 'ft8_lib_vendor', 'fft', 'kiss_fft.c')
inc = os.path.join(root, 'native', 'ft8_lib_vendor')


def find_vcvars():
    """vcvars64.bat of any installed Visual Studio edition (the shipped build script names Community).

    vswhere first (finds any version, e.g. VS 2026 on the windows-2025-vs2026 runner); the 2022/2019 edition list is the fallback.
    """
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
    exe = os.path.join(out, 'freq_search_selftest.exe')
    bat = os.path.join(out, 'build_selftest.bat')
    lines = [
        '@echo off',
        f'call "{vcvars}" >nul',
        f'cd /d "{out}"',                       # the object files land in the scratch directory
        f'cl /nologo /std:c11 /O2 /W3 /I "{inc}" /Fe"{exe}" "{test_c}" "{kiss_c}"',
    ]
    with open(bat, 'w', newline='') as f:
        f.write('\r\n'.join(lines) + '\r\n')
    build = subprocess.run(['cmd', '/c', bat], capture_output=True, text=True)
else:
    exe = os.path.join(out, 'freq_search_selftest')
    cc = shutil.which('cc') or shutil.which('gcc') or shutil.which('clang')
    if cc is None:
        print('no C compiler found')
        sys.exit(3)
    build = subprocess.run([cc, '-std=c11', '-O2', '-D_GNU_SOURCE', '-I', inc, '-o', exe, test_c, kiss_c, '-lm', '-lpthread'],
                           capture_output=True, text=True)

with open(os.path.join(out, 'build.log'), 'w', encoding='utf-8') as log:
    log.write(build.stdout + build.stderr)
if build.returncode != 0 or not os.path.exists(exe):
    print('BUILD FAILED; see', os.path.join(out, 'build.log'))
    print((build.stdout + build.stderr)[-3000:])
    sys.exit(3)

run = subprocess.run([exe], capture_output=True, text=True)
print(run.stdout)
if run.stderr:
    print(run.stderr)
sys.exit(run.returncode)
