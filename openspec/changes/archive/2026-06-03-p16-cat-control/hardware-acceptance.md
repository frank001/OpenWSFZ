# Hardware Acceptance Gates — p16 CAT Control

**Gates:** 15 (Serial CAT) and 16 (rigctld)  
**Tasks:** 15.1–15.7, 16.1–16.7  
**Required hardware:** CAT-capable rig on COM6, 9600 baud (Windows)

The 14 steps below must be completed before the p16 change can be archived.
Each step maps directly to a task in `tasks.md`. Tick the checkbox in `tasks.md`
as you complete each step.

---

## Prerequisites — Do this once before either gate

### 1. Build and locate the daemon

```powershell
cd D:\Projects\claude\OpenWSFZ
dotnet build -c Release
```

The daemon executable is at:
```
src\OpenWSFZ.Daemon\bin\Release\net10.0\OpenWSFZ.Daemon.exe
```

The config file and ALL.TXT are written **beside the executable**, so run the
daemon from that directory to keep artefacts in one place:

```powershell
cd src\OpenWSFZ.Daemon\bin\Release\net10.0
.\OpenWSFZ.Daemon.exe
```

Open a second terminal window to watch the log in real time:
```powershell
Get-Content .\logs\*.log -Wait
```
(or watch the console output directly if file logging is enabled)

### 2. Open the Settings page

With the daemon running, open `http://127.0.0.1:<port>/settings.html` in a
browser. The port is printed in the daemon's startup log.

### 3. Verify the rig is ready

- Power on the rig
- Confirm it is on a known frequency (e.g. 7.074 MHz — 40 m FT8 dial)
- Confirm no other application (WSJT-X, etc.) holds COM6 before Gate 15

---

## Gate 15 — Serial CAT mode

### 15.1 — Configure and start

In the Settings page CAT section:
- `rigModel` → `SerialCat`
- `serialPort` → `COM6`
- `baudRate` → `9600`
- `enabled` → `true`
- Click **Save**

The daemon detects the config change within one poll interval (≤ 2 s) and
attempts to open COM6 without a restart.

**What to look for in the log:**
```
CAT connected via SerialCat.
```

**What to look for in the UI:**
The Settings page CAT status indicator should change from **Disabled** to
**Connected** (green). The main page status bar CAT badge should appear green.

**Fail criteria:** The log shows an error and no "CAT connected" message
within 5 s. Common causes: wrong port name, wrong baud rate, another
application holds COM6.

**✅ Mark 15.1 complete once the daemon connects without error.**

---

### 15.2 — Verify frequency appears in status bar

On the main page (`http://127.0.0.1:<port>/`), check the status bar.

**What to look for:**
The dial frequency field should show the rig's current VFO-A frequency
formatted to three decimal places, e.g. `7.074 MHz`. It must update within
2 seconds of the daemon connecting (two poll intervals at the 1 s default).

**Fail criteria:** The frequency shown is `0.000 MHz` or still shows the
manually configured value from Settings rather than the live rig value.

**✅ Mark 15.2 complete once the live rig frequency is visible in the status bar.**

---

### 15.3 — Verify frequency tracks rig tuning

Tune the rig VFO to a different frequency — e.g. move from 7.074 MHz to
14.074 MHz (or any clearly different value you can read from the rig display).

**What to look for:**
The status bar frequency on the main page must update to the new value within
2 seconds (two poll intervals).

**Fail criteria:** The status bar remains on the old frequency for more than
5 seconds after the rig is tuned.

**✅ Mark 15.3 complete once the status bar tracks the rig VFO.**

---

### 15.4 — Verify ALL.TXT records the live frequency

While CAT is active and the rig is on a known frequency (e.g. 7.074 MHz),
wait for one or more FT8 decode cycles to complete (each cycle is 15 seconds).

Open `ALL.TXT` in the same directory as the executable. Each decode line
should use the rig's live frequency, not the manually configured fallback.

**What to look for:**
```
260603_150000     7.074 Rx FT8   -12  0.3  1234 Q1AW Q1TTT EN43
```
The `7.074` column (position 3) must match the rig's VFO-A frequency.

**Fail criteria:** The frequency in ALL.TXT does not match the rig's VFO-A
frequency as shown on the rig display.

**Note:** If no FT8 signals are decoded (band is quiet, antenna disconnected,
etc.), you can verify by checking that `AllTxtWriter` would use the CAT value
— enable audio capture, wait for a cycle, and inspect ANY line written.

**✅ Mark 15.4 complete once ALL.TXT lines use the live rig frequency.**

---

### 15.5 — Verify graceful degradation on cable disconnect

With the daemon running and CAT connected, **unplug the serial cable** (or
power off the rig, or switch off the USB-serial adapter).

**What to look for in the log (within 2 s):**
```
CAT: frequency poll failed via SerialCat — <exception message> Retrying in 2 s.
```
(logged at Warning, not Error)

**What to look for in the UI:**
- The status bar CAT badge changes to the **Error** state (red/amber)
- The frequency field falls back to the `decodeLog.dialFrequencyMHz` value
  from Settings (the operator's manual fallback)
- The daemon continues running; no crash; FT8 decoding continues if active

**What NOT to see:**
- The daemon must not crash or throw an unhandled exception
- The FT8 decode pipeline must not stall

**✅ Mark 15.5 complete once the Error indicator appears and the daemon
keeps running.**

---

### 15.6 — Verify automatic reconnection

Reconnect the serial cable (or power the rig back on / re-enable the adapter).

**What to look for (within 4 s — two 2-second retry cycles):**
```
CAT connected via SerialCat.
```

**What to look for in the UI:**
- CAT badge returns to **Connected** (green)
- Status bar frequency resumes showing the live rig frequency

**Fail criteria:** The daemon does not reconnect within 10 seconds without a
manual restart or config save.

**✅ Mark 15.6 complete once automatic reconnection is confirmed.**

---

### 15.7 — Confirm radio safety throughout Gate 15

Review the daemon's full log output for the Gate 15 session.

**What to look for (should be absent):**
- Any log line mentioning frequency-set, mode-set, PTT, or transmit commands
- Any line containing `FA0` written TO the rig (only `FA;` should appear as
  outgoing; `FA<digits>;` is the response read FROM the rig)

**What to verify on the rig itself:**
- The VFO frequency has not changed from what you set it to
- The operating mode has not changed
- The rig has not transmitted (no TX LED activity you did not initiate)

**✅ Mark 15.7 complete once radio safety is confirmed.**

---

## Gate 16 — rigctld mode

### Setup — Start rigctld

Locate your `rigctld` installation (part of Hamlib). On Windows with Hamlib
installed:

```powershell
# Example — replace <model-id> with your rig's Hamlib model number.
# For Kenwood TS-890S: -m 2047
# For Icom IC-7300:    -m 3073
# Run `rigctld --list` to find your model ID.
rigctld -m <model-id> -r COM6 -s 9600
```

`rigctld` should print something like:
```
Opened rig model 2047, 'TS-890S'
Backend version 20210307, Status: Beta
```

Leave `rigctld` running in its own terminal window. It now holds COM6
exclusively and will serve multiple TCP clients simultaneously.

---

### 16.1 — rigctld started

**✅ Mark 16.1 complete once `rigctld` is running and has opened the rig
without error.**

---

### 16.2 — Configure and start in rigctld mode

In the Settings page, **while the daemon is running**:
- `rigModel` → `RigCtld`
- `rigctldHost` → `127.0.0.1`
- `rigctldPort` → `4532`
- `enabled` → `true`
- Click **Save**

**What to look for in the log:**
```
CAT connected via RigCtld.
```

The daemon must switch from SerialCat to RigCtld without a restart.

**✅ Mark 16.2 complete once the daemon connects to rigctld.**

---

### 16.3 — Verify frequency in status bar (rigctld)

Same verification as 15.2, but via rigctld transport.

The status bar must show the rig's live VFO-A frequency within 2 seconds.

**✅ Mark 16.3 complete once the live frequency is visible via rigctld.**

---

### 16.4 — Verify no port conflict with a second client

With `rigctld` running and OpenWSFZ connected, open a **second TCP connection**
to `rigctld` to confirm it serves multiple clients simultaneously.

The simplest second client is `rigctl` (the interactive Hamlib command-line
tool) or a raw netcat/telnet session:

```powershell
# Option A — rigctl interactive client
rigctl -m 2 -r 127.0.0.1:4532
# At the rigctl prompt, type:  f   (get frequency)
# Expected output: the current VFO-A frequency in Hz

# Option B — raw TCP (PowerShell)
$tcp = New-Object System.Net.Sockets.TcpClient("127.0.0.1", 4532)
$stream = $tcp.GetStream()
$writer = New-Object System.IO.StreamWriter($stream); $writer.AutoFlush = $true
$reader = New-Object System.IO.StreamReader($stream)
$writer.Write("\get_freq`n")
$reader.ReadLine()   # should print frequency in Hz
$tcp.Close()
```

**What to look for:**
- The second client receives a valid frequency response
- OpenWSFZ's CAT badge remains green throughout
- No error appears in the daemon log

**✅ Mark 16.4 complete once simultaneous access is confirmed.**

---

### 16.5 — Verify graceful degradation when rigctld stops

**Stop rigctld** (Ctrl-C in its terminal window).

**What to look for in the log (within 2 s):**
```
CAT: frequency poll failed via RigCtld — <exception message> Retrying in 2 s.
```

**What to look for in the UI:**
- CAT badge switches to **Error**
- Frequency falls back to the manual fallback
- Daemon keeps running; FT8 decode pipeline unaffected

**✅ Mark 16.5 complete once the Error indicator appears and the daemon
keeps running.**

---

### 16.6 — Verify automatic reconnection (rigctld)

**Restart rigctld** with the same command as step 16.1.

**What to look for (within 4 s):**
```
CAT connected via RigCtld.
```

**What to look for in the UI:**
- CAT badge returns to **Connected**
- Status bar resumes live frequency

**✅ Mark 16.6 complete once automatic reconnection is confirmed.**

---

### 16.7 — Confirm radio safety throughout Gate 16

Same check as 15.7 — review the log for the Gate 16 session.

**What must be absent:**
- Any transmit, PTT, frequency-set, or mode-set command
- Any command other than `\get_freq` sent to rigctld

**What to verify on the rig:**
- VFO frequency unchanged from what you set it to
- Mode unchanged
- No TX activity

**✅ Mark 16.7 complete once radio safety is confirmed.**

---

## After Completing Both Gates

### Tick the tasks

Open `openspec/changes/p16-cat-control/tasks.md` and change all 14
`- [ ]` entries in sections 15 and 16 to `- [x]`.

### Commit

```powershell
git add openspec/changes/p16-cat-control/tasks.md
git commit -m "chore(p16): mark hardware acceptance gates 15 and 16 complete"
```

### Archive

Return to QA and ask to archive the change:

> "archive the change"

The archive step will sync the delta specs to the main spec library and move
the change directory to `openspec/changes/archive/`.

---

## Quick Reference — What Each Indicator Looks Like

| CAT state | Status bar badge | Log message |
|---|---|---|
| Disabled | *(absent)* | *(none)* |
| Connecting | Connecting (transitional) | `CAT: connecting via SerialCat/RigCtld` |
| Connected | **Connected** (green) | `CAT connected via SerialCat/RigCtld.` |
| Error | **Error** (red/amber) | `CAT: frequency poll failed via … Retrying in 2 s.` |

## Quick Reference — Config Keys

```json
{
  "cat": {
    "enabled": true,
    "rigModel": "SerialCat",
    "serialPort": "COM6",
    "baudRate": 9600,
    "rigctldHost": "127.0.0.1",
    "rigctldPort": 4532,
    "pollIntervalSeconds": 1
  }
}
```

Config file location: beside the executable at
`src\OpenWSFZ.Daemon\bin\Release\net10.0\openswfz.json`
(or wherever the daemon was started from).
Changes saved via the Settings page take effect within 2 poll intervals
without a daemon restart.
