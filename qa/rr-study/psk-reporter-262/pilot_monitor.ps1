# Production pilot console monitor for the #262 PSK Reporter upload (QA). Run in its own window:
#   powershell -NoExit -File pilot_monitor.ps1 -LogDir <daemon log dir> -Receiver <own callsign>
# Shows (1) every "psk-reporter:" line of the daemon's newest log with a running R9 total (records sent, datagrams sent), and
# (2) every 5 minutes (the rate the protocol page asks of retrieve-API users) a COUNTS-ONLY summary of what PSK Reporter says it holds for
# this station as a receiver over the last hour: reports, how many carry a sender locator and how many do not, the frequency range,
# the age of the newest report. No third-party callsign is printed and nothing is written to disk.
param(
    [Parameter(Mandatory = $true)][string]$LogDir,
    [Parameter(Mandatory = $true)][string]$Receiver,
    [int]$RetrieveEverySeconds = 300,
    [int]$FirstRetrieveDelaySeconds = 0,     # the retrieve interface answered HTTP 429 to a faster cadence: wait before the first query
    [int]$PollSeconds = 5
)
$ErrorActionPreference = 'Continue'
$host.UI.RawUI.WindowTitle = 'PILOT: PSK Reporter upload monitor'
$url = "https://retrieve.pskreporter.info/query?receiverCallsign=$Receiver&flowStartSeconds=-3600&rronly=1&noactive=1&rptlimit=5000"
$offset = @{}
$records = 0; $datagrams = 0
$lastRetrieve = if ($FirstRetrieveDelaySeconds -gt 0) { [DateTime]::UtcNow.AddSeconds($FirstRetrieveDelaySeconds - $RetrieveEverySeconds) } else { [DateTime]::MinValue }

function Stamp { [DateTime]::UtcNow.ToString('HH:mm:ss') + 'Z' }
function Summarise {
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 40 -UserAgent 'OpenWSFZ-QA-pilot-monitor (counts only, every 5 min)'
        $x = $r.Content
        $reports = [regex]::Matches($x, '<receptionReport\b[^>]*>')
        $n = $reports.Count
        $withLoc = 0; $freqs = @(); $flows = @()
        foreach ($m in $reports) {
            $a = $m.Value
            if ($a -match 'senderLocator="[^"]+"') { $withLoc++ }
            if ($a -match 'frequency="?(\d+)') { $freqs += [double]$Matches[1] }
            if ($a -match 'flowStartSeconds="?(\d+)') { $flows += [double]$Matches[1] }
        }
        $line = "PSK Reporter holds $n report(s) for $Receiver in the last hour: $withLoc with a sender locator, $($n - $withLoc) without"
        if ($freqs.Count) { $line += "; frequency {0:N3}-{1:N3} MHz" -f (($freqs | Measure-Object -Minimum).Minimum / 1e6), (($freqs | Measure-Object -Maximum).Maximum / 1e6) }
        if ($flows.Count) { $age = [int]([DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - ($flows | Measure-Object -Maximum).Maximum); $line += "; newest report is $age s old" }
        return $line
    } catch { return "(could not read the retrieve interface: $($_.Exception.Message))" }
}

Write-Host "[$(Stamp)] Pilot monitor started. Daemon log dir: $LogDir" -ForegroundColor Cyan
Write-Host "[$(Stamp)] PSK Reporter retrieve summary every $RetrieveEverySeconds s (counts only)" -ForegroundColor Cyan
while ($true) {
    $log = Get-ChildItem -Path $LogDir -Filter 'openswfz-*.log' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($log) {
        $key = $log.FullName
        if (-not $offset.ContainsKey($key)) { $offset[$key] = $log.Length }   # only lines written from now on
        if ($log.Length -gt $offset[$key]) {
            try {
                $fs = [System.IO.File]::Open($key, 'Open', 'Read', 'ReadWrite')
                $null = $fs.Seek($offset[$key], 'Begin')
                $sr = New-Object System.IO.StreamReader($fs)
                $new = $sr.ReadToEnd(); $offset[$key] = $fs.Position
                $sr.Dispose(); $fs.Dispose()
                foreach ($line in ($new -split "`r?`n")) {
                    if ($line -match 'psk-reporter') {
                        if ($line -match 'datagram sent') {
                            $datagrams++
                            if ($line -match '(\d+) record\(s\)') { $records += [int]$Matches[1] }
                            Write-Host $line -ForegroundColor Green
                            Write-Host "          >>> daemon says: $datagrams datagram(s) sent, $records record(s) in total (the R9 sum)" -ForegroundColor Yellow
                        } elseif ($line -match 'Warning|WRN|could not|refused|placeholder') {
                            Write-Host $line -ForegroundColor Red
                        } else {
                            Write-Host $line -ForegroundColor Gray
                        }
                    }
                }
            } catch { Write-Host "[$(Stamp)] (log read: $($_.Exception.Message))" -ForegroundColor DarkYellow }
        }
    }
    if (([DateTime]::UtcNow - $lastRetrieve).TotalSeconds -ge $RetrieveEverySeconds) {
        $lastRetrieve = [DateTime]::UtcNow
        Write-Host ""
        Write-Host "==== [$(Stamp)] PSK REPORTER SAYS ====" -ForegroundColor Cyan
        Write-Host (Summarise)
        Write-Host "==== daemon R9 total so far: $datagrams datagram(s), $records record(s) ====" -ForegroundColor Cyan
        Write-Host ""
    }
    Start-Sleep -Seconds $PollSeconds
}
