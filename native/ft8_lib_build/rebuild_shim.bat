@echo off
echo === Setting up MSVC x64 environment ===
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
echo ERRORLEVEL after vcvars64: %ERRORLEVEL%
if %ERRORLEVEL% neq 0 goto :err_env

rem dev-tasks/2026-09-15-rebuild-shim-bat-hardcoded-root-landmine.md: derive FT8_ROOT from this
rem script's own location (native\ft8_lib_build\rebuild_shim.bat -> repo root is two levels up),
rem rather than a literal path, so the script builds against and writes back to whichever worktree
rem actually invoked it -- not always the Architect's own checkout. Mirrors build_linux.sh's own
rem FT8_ROOT variable (same name, same role) so the two scripts stay recognizably parallel. %~dp0 is
rem the drive+path of this script (trailing backslash included); the "for %%i in (...) do set
rem "...=%%~fi"" idiom resolves the resulting "...\..\.." into a clean, normalized absolute path.
for %%i in ("%~dp0..\..") do set "FT8_ROOT=%%~fi"
echo FT8_ROOT resolved to: %FT8_ROOT%

echo === r0-reproducible-native-build: clearing obj\ so every .obj below is produced by this invocation ===
if exist "%FT8_ROOT%\native\ft8_lib_build\obj\*.obj" del /Q "%FT8_ROOT%\native\ft8_lib_build\obj\*.obj"

echo === r0-reproducible-native-build: compiling the nine previously-prebuilt objects from native\ft8_lib_vendor ===

echo === Compiling constants.c ===
cl ^
  /I "%FT8_ROOT%\native\ft8_lib_vendor" ^
  /std:c11 /O2 /W3 /c ^
  /Fo"%FT8_ROOT%\native\ft8_lib_build\obj\constants.obj" ^
  "%FT8_ROOT%\native\ft8_lib_vendor\ft8\constants.c"
echo ERRORLEVEL after cl (constants.c): %ERRORLEVEL%
if %ERRORLEVEL% neq 0 goto :err_cl

echo === Compiling crc.c ===
cl ^
  /I "%FT8_ROOT%\native\ft8_lib_vendor" ^
  /std:c11 /O2 /W3 /c ^
  /Fo"%FT8_ROOT%\native\ft8_lib_build\obj\crc.obj" ^
  "%FT8_ROOT%\native\ft8_lib_vendor\ft8\crc.c"
echo ERRORLEVEL after cl (crc.c): %ERRORLEVEL%
if %ERRORLEVEL% neq 0 goto :err_cl

echo === Compiling ldpc.c ===
cl ^
  /I "%FT8_ROOT%\native\ft8_lib_vendor" ^
  /std:c11 /O2 /W3 /c ^
  /Fo"%FT8_ROOT%\native\ft8_lib_build\obj\ldpc.obj" ^
  "%FT8_ROOT%\native\ft8_lib_vendor\ft8\ldpc.c"
echo ERRORLEVEL after cl (ldpc.c): %ERRORLEVEL%
if %ERRORLEVEL% neq 0 goto :err_cl

echo === Compiling text.c ===
cl ^
  /I "%FT8_ROOT%\native\ft8_lib_vendor" ^
  /std:c11 /O2 /W3 /c ^
  /Fo"%FT8_ROOT%\native\ft8_lib_build\obj\text.obj" ^
  "%FT8_ROOT%\native\ft8_lib_vendor\ft8\text.c"
echo ERRORLEVEL after cl (text.c): %ERRORLEVEL%
if %ERRORLEVEL% neq 0 goto :err_cl

echo === Compiling encode.c ===
cl ^
  /I "%FT8_ROOT%\native\ft8_lib_vendor" ^
  /std:c11 /O2 /W3 /c ^
  /Fo"%FT8_ROOT%\native\ft8_lib_build\obj\encode.obj" ^
  "%FT8_ROOT%\native\ft8_lib_vendor\ft8\encode.c"
echo ERRORLEVEL after cl (encode.c): %ERRORLEVEL%
if %ERRORLEVEL% neq 0 goto :err_cl

echo === Compiling message.c (r0: /FI stpcpy_msvc_compat.h -- see that file for the D-006 rationale) ===
cl ^
  /I "%FT8_ROOT%\native\ft8_lib_vendor" ^
  /FI "%FT8_ROOT%\native\ft8_lib_build\patched\stpcpy_msvc_compat.h" ^
  /std:c11 /O2 /W3 /c ^
  /Fo"%FT8_ROOT%\native\ft8_lib_build\obj\message.obj" ^
  "%FT8_ROOT%\native\ft8_lib_vendor\ft8\message.c"
echo ERRORLEVEL after cl (message.c): %ERRORLEVEL%
if %ERRORLEVEL% neq 0 goto :err_cl

echo === Compiling monitor.c (patched, MSVC VLA compat) ===
cl ^
  /I "%FT8_ROOT%\native\ft8_lib_vendor\common" ^
  /I "%FT8_ROOT%\native\ft8_lib_vendor" ^
  /std:c11 /O2 /W3 /c ^
  /Fo"%FT8_ROOT%\native\ft8_lib_build\obj\monitor.obj" ^
  "%FT8_ROOT%\native\ft8_lib_build\patched\common\monitor.c"
echo ERRORLEVEL after cl (monitor.c): %ERRORLEVEL%
if %ERRORLEVEL% neq 0 goto :err_cl

echo === Compiling kiss_fft.c ===
cl ^
  /I "%FT8_ROOT%\native\ft8_lib_vendor" ^
  /std:c11 /O2 /W3 /c ^
  /Fo"%FT8_ROOT%\native\ft8_lib_build\obj\kiss_fft.obj" ^
  "%FT8_ROOT%\native\ft8_lib_vendor\fft\kiss_fft.c"
echo ERRORLEVEL after cl (kiss_fft.c): %ERRORLEVEL%
if %ERRORLEVEL% neq 0 goto :err_cl

echo === Compiling kiss_fftr.c ===
cl ^
  /I "%FT8_ROOT%\native\ft8_lib_vendor" ^
  /std:c11 /O2 /W3 /c ^
  /Fo"%FT8_ROOT%\native\ft8_lib_build\obj\kiss_fftr.obj" ^
  "%FT8_ROOT%\native\ft8_lib_vendor\fft\kiss_fftr.c"
echo ERRORLEVEL after cl (kiss_fftr.c): %ERRORLEVEL%
if %ERRORLEVEL% neq 0 goto :err_cl

echo === Compiling patched decode.c ===
cl ^
  /I "%FT8_ROOT%\native\ft8_lib_vendor\ft8" ^
  /I "%FT8_ROOT%\native\ft8_lib_vendor" ^
  /I "%FT8_ROOT%\src\OpenWSFZ.Ft8\Native" ^
  /std:c11 /O2 /W3 /c ^
  /Fo"%FT8_ROOT%\native\ft8_lib_build\obj\decode.obj" ^
  "%FT8_ROOT%\native\ft8_lib_build\patched\ft8\decode.c"
echo ERRORLEVEL after cl (decode.c): %ERRORLEVEL%
if %ERRORLEVEL% neq 0 goto :err_cl

echo === Compiling ft8_shim.c ===
cl ^
  /I "%FT8_ROOT%\native\ft8_lib_vendor" ^
  /I "%FT8_ROOT%\src\OpenWSFZ.Ft8\Native" ^
  /std:c11 /O2 /W3 /c ^
  /Fo"%FT8_ROOT%\native\ft8_lib_build\obj\ft8_shim.obj" ^
  "%FT8_ROOT%\src\OpenWSFZ.Ft8\Native\ft8_shim.c"
echo ERRORLEVEL after cl: %ERRORLEVEL%
if %ERRORLEVEL% neq 0 goto :err_cl

echo === Compiling sync_refiner.c (r1-sync-refiner-instrument-validation, OpenWSFZ-original, diagnostic-only) ===
cl ^
  /I "%FT8_ROOT%\native\ft8_lib_vendor" ^
  /I "%FT8_ROOT%\src\OpenWSFZ.Ft8\Native" ^
  /std:c11 /O2 /W3 /c ^
  /Fo"%FT8_ROOT%\native\ft8_lib_build\obj\sync_refiner.obj" ^
  "%FT8_ROOT%\native\ft8_lib_vendor\refine\sync_refiner.c"
echo ERRORLEVEL after cl (sync_refiner.c): %ERRORLEVEL%
if %ERRORLEVEL% neq 0 goto :err_cl

echo === Compiling coherent_llr.c (r2-coherent-llr-instrument, OpenWSFZ-original, diagnostic-only) ===
cl ^
  /I "%FT8_ROOT%\native\ft8_lib_vendor" ^
  /I "%FT8_ROOT%\src\OpenWSFZ.Ft8\Native" ^
  /std:c11 /O2 /W3 /c ^
  /Fo"%FT8_ROOT%\native\ft8_lib_build\obj\coherent_llr.obj" ^
  "%FT8_ROOT%\native\ft8_lib_vendor\refine\coherent_llr.c"
echo ERRORLEVEL after cl (coherent_llr.c): %ERRORLEVEL%
if %ERRORLEVEL% neq 0 goto :err_cl

echo === Linking libft8.dll ===
link /DLL ^
  /OUT:"%FT8_ROOT%\native\ft8_lib_build\libft8.dll" ^
  /EXPORT:ft8_lib_version_check ^
  /EXPORT:ft8_decode_all ^
  /EXPORT:ft8_get_last_pass_counts ^
  /EXPORT:ft8_get_max_passes ^
  /EXPORT:ft8_get_last_noise_floor_db ^
  /EXPORT:ft8_encode_message ^
  /EXPORT:ft8_get_last_candidate_counts ^
  /EXPORT:ft8_get_last_llr_stats ^
  /EXPORT:ft8_set_ap_bits ^
  /EXPORT:ft8_set_decode_params ^
  /EXPORT:ft8_get_hash_table_reject_count ^
  /EXPORT:ft8_refine_candidate ^
  /EXPORT:ft8_extract_llrs_at ^
  /EXPORT:ft8_coherent_llr_at ^
  /EXPORT:ft8_ldpc_decode_llrs ^
  /EXPORT:ft8_get_last_snr_terms ^
  /EXPORT:ft8_get_h12_displaying_count ^
  /EXPORT:ft8_get_h12_ambiguous_count ^
  /EXPORT:ft8_get_h12_divergent_count ^
  /EXPORT:ft8_get_h12_by_code ^
  /EXPORT:ft8_get_h12_suppressed_count ^
  /EXPORT:ft8_get_h12_unresolved_by_code ^
  "%FT8_ROOT%\native\ft8_lib_build\obj\constants.obj" ^
  "%FT8_ROOT%\native\ft8_lib_build\obj\crc.obj" ^
  "%FT8_ROOT%\native\ft8_lib_build\obj\decode.obj" ^
  "%FT8_ROOT%\native\ft8_lib_build\obj\encode.obj" ^
  "%FT8_ROOT%\native\ft8_lib_build\obj\ldpc.obj" ^
  "%FT8_ROOT%\native\ft8_lib_build\obj\message.obj" ^
  "%FT8_ROOT%\native\ft8_lib_build\obj\text.obj" ^
  "%FT8_ROOT%\native\ft8_lib_build\obj\monitor.obj" ^
  "%FT8_ROOT%\native\ft8_lib_build\obj\kiss_fft.obj" ^
  "%FT8_ROOT%\native\ft8_lib_build\obj\kiss_fftr.obj" ^
  "%FT8_ROOT%\native\ft8_lib_build\obj\ft8_shim.obj" ^
  "%FT8_ROOT%\native\ft8_lib_build\obj\sync_refiner.obj" ^
  "%FT8_ROOT%\native\ft8_lib_build\obj\coherent_llr.obj"
echo ERRORLEVEL after link: %ERRORLEVEL%
if %ERRORLEVEL% neq 0 goto :err_link

echo === Copying DLL to repo ===
copy /Y "%FT8_ROOT%\native\ft8_lib_build\libft8.dll" ^
        "%FT8_ROOT%\src\OpenWSFZ.Ft8\Native\win-x64\libft8.dll"
if %ERRORLEVEL% neq 0 goto :err_copy

echo === SUCCESS ===
goto :eof

:err_env
echo FAILED: vcvars64.bat returned non-zero
exit /b 1
:err_cl
echo FAILED: cl.exe compile step
exit /b 1
:err_link
echo FAILED: link.exe step
exit /b 1
:err_copy
echo FAILED: copy step
exit /b 1
