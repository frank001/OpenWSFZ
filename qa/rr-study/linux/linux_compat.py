"""Linux compatibility layer for the Windows-built R&R launcher chain (QA tooling only; nothing on the Windows path changes).

``endurance_supervisor`` (reused by ``rr_precheck`` / ``run_study_detached``) drives the daemon through PowerShell
(``Get-Process``), ``taskkill`` and Windows process-creation flags. ``install()`` replaces exactly those primitives with
POSIX equivalents on the SAME module object, so every caller sees the patched versions:

    ps()             understands the three PowerShell one-liners the chain uses and answers them from /proc
    kill_tree()      SIGTERM then SIGKILL to the daemon's process group
    daemon_processes()/pid_alive()   /proc scan for the OpenWSFZ.Daemon process
    start_daemon()   Popen without creationflags, in its own session
    NOWIN            0
"""
import os
import re
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENDURANCE = os.path.normpath(os.path.join(HERE, "..", "..", "endurance"))
DAEMON_COMM = "OpenWSFZ.Daemon"            # /proc/<pid>/comm is truncated to 15 characters: "OpenWSFZ.Daemon" is exactly 15


def _pids_by_comm(name):
    out = []
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                with open("/proc/%s/comm" % d) as fh:
                    if fh.read().strip() == name[:15]:
                        out.append(int(d))
            except OSError:
                pass
    return sorted(out)


def _alive(pid):
    try:
        with open("/proc/%d/stat" % pid) as fh:
            return fh.read().rsplit(")", 1)[1].split()[0] != "Z"   # a zombie is not alive
    except (OSError, IndexError):
        return False


def _lib_path(pid, lib="libft8.so"):
    try:
        with open("/proc/%d/maps" % pid) as fh:
            for line in fh:
                if lib in line:
                    return line.split()[-1]
    except OSError:
        pass
    return ""


def install():
    if ENDURANCE not in sys.path:
        sys.path.insert(0, ENDURANCE)
    import endurance_supervisor as ES

    ES.NOWIN = 0

    def ps(cmd, timeout=60):
        m = re.search(r"Get-Process -Id (\d+)\)\.Modules .*ModuleName -eq '(libft8)\.dll'", cmd)
        if m:
            return _lib_path(int(m.group(1)))
        m = re.search(r"\(Get-Process -Id (\d+) -ErrorAction SilentlyContinue\)\.Id", cmd)
        if m:
            pid = int(m.group(1))
            return str(pid) if _alive(pid) else ""
        if "Get-Process -Name OpenWSFZ.Daemon" in cmd:
            return "\n".join(str(p) for p in _pids_by_comm(DAEMON_COMM))
        raise NotImplementedError("linux_compat.ps: unhandled PowerShell command: " + cmd[:80])

    def kill_tree(pid):
        for sig, wait_s in ((signal.SIGTERM, 20), (signal.SIGKILL, 5)):
            try:
                os.killpg(os.getpgid(pid), sig)
            except (ProcessLookupError, PermissionError):
                return
            t0 = time.time()
            while time.time() - t0 < wait_s:
                if not _alive(pid):
                    return
                time.sleep(0.5)

    def start_daemon(run, daemon_exe, config_path, port):
        out = open(os.path.join(run.c, "daemon.stdout.log"), "ab")
        proc = subprocess.Popen([daemon_exe, "--config", config_path, "--port", str(port)], stdout=out,
                                stderr=subprocess.STDOUT, start_new_session=True)
        run.daemon_pid = proc.pid
        run.daemon_proc = proc
        run.state["daemon_pid"] = proc.pid
        run.save()
        run.log("daemon started pid %d (exe=%s config=%s port=%d)" % (proc.pid, daemon_exe, config_path, port))
        run.event("daemon_start", pid=proc.pid, exe=daemon_exe, config=config_path, port=port)
        return proc

    ES.ps = ps
    ES.kill_tree = kill_tree
    ES.daemon_processes = lambda: _pids_by_comm(DAEMON_COMM)
    ES.pid_alive = lambda pid: pid is not None and _alive(pid)
    ES.start_daemon = start_daemon
    return ES
