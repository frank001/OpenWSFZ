# L1 console monitor for the #262 PSK Reporter upload (QA). Run in its own window:  powershell -NoExit -File l1_monitor.ps1 -LogDir <daemon log dir>
# Shows (1) every "psk-reporter:" line of the daemon's newest log as it appears, with a running R9 total (records sent, datagrams sent), and
# (2) every minute, what the PSK Reporter TEST listener's analysis page says it received from THIS connection's IP address (the page lists only
# packets from the requester's own address, so it shows this station's datagrams and nobody else's). Nothing is written to disk by this script.
param(
    [Parameter(Mandatory = $true)][string]$LogDir,
    [int]$AnalysisEverySeconds = 60,
    [int]$PollSeconds = 5
)
$ErrorActionPreference = 'Continue'
$host.UI.RawUI.WindowTitle = 'L1: PSK Reporter test listener monitor'
$analysisUrl = 'https://pskreporter.info/cgi-bin/psk-analysis.pl'
$offset = @{}                 # log file -> bytes already shown
$records = 0; $datagrams = 0
$lastAnalysis = [DateTime]::MinValue
$lastAnalysisText = ''

function Stamp { [DateTime]::UtcNow.ToString('HH:mm:ss') + 'Z' }
function Show-Analysis {
    try {
        $r = Invoke-WebRequest -Uri $analysisUrl -UseBasicParsing -TimeoutSec 20 -UserAgent 'OpenWSFZ-QA-L1-monitor'
        $t = $r.Content
        $t = [regex]::Replace($t, '(?is)<(script|style).*?</\1>', '')
        $t = [regex]::Replace($t, '(?i)<br\s*/?>|</p>|</tr>|</li>|</h\d>|</div>|</table>', "`n")
        $t = [regex]::Replace($t, '(?i)</t[dh]>', "`t")
        $t = [regex]::Replace($t, '<[^>]+>', '')
        $t = [System.Net.WebUtility]::HtmlDecode($t)
        $t = ([regex]::Replace($t, "[ \t]+\n", "`n") -replace "(\r?\n){2,}", "`n").Trim()
        # the page repeats its title and names this PC's public address: drop those lines from the display
        $lines = $t -split "`n" | Where-Object { $_ -notmatch '^\s*PSKReporter Packet Analysis\s*$' } | ForEach-Object { $_ -replace '\b\d{1,3}(\.\d{1,3}){3}\b', '<your IP>' }
        return ($lines -join "`n")
    } catch { return "(could not read the analysis page: $($_.Exception.Message))" }
}

Write-Host "[$(Stamp)] L1 monitor started. Daemon log dir: $LogDir" -ForegroundColor Cyan
Write-Host "[$(Stamp)] Test listener analysis page: $analysisUrl (updates every $AnalysisEverySeconds s; shows only packets from this IP)" -ForegroundColor Cyan
while ($true) {
    $log = Get-ChildItem -Path $LogDir -Filter 'openswfz-*.log' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($log) {
        $key = $log.FullName
        if (-not $offset.ContainsKey($key)) { $offset[$key] = 0L }
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
    if (([DateTime]::UtcNow - $lastAnalysis).TotalSeconds -ge $AnalysisEverySeconds) {
        $lastAnalysis = [DateTime]::UtcNow
        $text = Show-Analysis
        Write-Host ""
        Write-Host "==== [$(Stamp)] TEST LISTENER SAYS (packets it received from this IP) ====" -ForegroundColor Cyan
        Write-Host $text
        Write-Host "==== daemon R9 total so far: $datagrams datagram(s), $records record(s) ====" -ForegroundColor Cyan
        Write-Host ""
    }
    Start-Sleep -Seconds $PollSeconds
}
