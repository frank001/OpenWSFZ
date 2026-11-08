# Plays a WAV to the VB-Audio "CABLE Input" render endpoint (NOT Voicemeeter, NOT the station), starting on the next UTC 15-s boundary.
param([string]$Wav, [string]$Log)
$b='D:\Projects\claude\_qa-scratch\framer-266\main-tree\src\OpenWSFZ.Daemon\bin\Release\net10.0'
Add-Type -Path "$b\NAudio.Core.dll"; Add-Type -Path "$b\NAudio.Wasapi.dll"
$en = New-Object NAudio.CoreAudioApi.MMDeviceEnumerator
$dev = $en.EnumerateAudioEndPoints([NAudio.CoreAudioApi.DataFlow]::Render,[NAudio.CoreAudioApi.DeviceState]::Active) | Where-Object { $_.FriendlyName -eq 'CABLE Input (VB-Audio Virtual Cable)' } | Select-Object -First 1
if (-not $dev) { "no CABLE Input" | Out-File $Log; exit 2 }
$rd = New-Object NAudio.Wave.WaveFileReader($Wav)
$out = New-Object NAudio.Wave.WasapiOut($dev, [NAudio.CoreAudioApi.AudioClientShareMode]::Shared, $true, 100)
$out.Init($rd)
$now=[DateTime]::UtcNow; $sec=$now.Second; $wait=15-($sec % 15)-($now.Millisecond/1000.0); if ($wait -lt 2) { $wait += 15 }
"{0:o} armed, waiting {1:F2}s" -f $now,$wait | Out-File $Log
Start-Sleep -Milliseconds ([int]($wait*1000))
$out.Play(); "{0:o} play started" -f [DateTime]::UtcNow | Add-Content $Log
while ($out.PlaybackState -eq [NAudio.Wave.PlaybackState]::Playing) { Start-Sleep -Milliseconds 500 }
"{0:o} play ended" -f [DateTime]::UtcNow | Add-Content $Log
$out.Dispose(); $rd.Dispose()
