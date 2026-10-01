@echo off
rem TEST-ONLY. Builds phase_timing.exe against a subfeas_fit.c given as %1 (default: the worktree's own).
rem Same compiler flags as rebuild_shim.bat's subfeas_fit.c compile: /std:c11 /O2 /W3.
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
for %%i in ("%~dp0..\..\..") do set "ROOT=%%~fi"
set "SRC=%~1"
if "%SRC%"=="" set "SRC=%ROOT%\native\ft8_lib_vendor\subfeas\subfeas_fit.c"
set "OUT=%~2"
if "%OUT%"=="" set "OUT=%TEMP%\phase_timing.exe"
cl /nologo /std:c11 /Zc:preprocessor /O2 /W3 /DSUBFEAS_SRC="\"%SRC%\"" ^
  /I "%ROOT%\native\ft8_lib_vendor" /I "%ROOT%\native\ft8_lib_vendor\fft" /I "%ROOT%\native\ft8_lib_vendor\subfeas" ^
  /Fo"%TEMP%\\" /Fe"%OUT%" "%~dp0phase_timing.c" "%ROOT%\native\ft8_lib_vendor\fft\kiss_fft.c"
