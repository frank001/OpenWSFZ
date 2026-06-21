@echo off
echo === Setting up MSVC x64 environment ===
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
if %ERRORLEVEL% neq 0 goto :err_env

echo === Compiling patched decode.c [NHARD_DIAG] ===
cl /DNHARD_DIAG /I "C:\Temp\ft8_lib_headers\ft8" /I "C:\Temp\ft8_lib_headers" /I "D:\Projects\claude\OpenWSFZ\src\OpenWSFZ.Ft8\Native" /std:c11 /O2 /W3 /c /Fo"D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\decode_diag.obj" "D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\patched\ft8\decode.c"
if %ERRORLEVEL% neq 0 goto :err_cl

echo === Linking libft8_diag.dll ===
link /DLL /OUT:"D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\libft8_diag.dll" /EXPORT:ft8_lib_version_check /EXPORT:ft8_decode_all /EXPORT:ft8_get_last_pass_counts /EXPORT:ft8_get_max_passes /EXPORT:ft8_get_last_noise_floor_db /EXPORT:ft8_encode_message /EXPORT:ft8_get_last_candidate_counts /EXPORT:ft8_get_last_llr_stats /EXPORT:ft8_set_ap_bits "D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\constants.obj" "D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\crc.obj" "D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\decode_diag.obj" "D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\encode.obj" "D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\ldpc.obj" "D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\message.obj" "D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\text.obj" "D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\monitor.obj" "D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\kiss_fft.obj" "D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\kiss_fftr.obj" "D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\ft8_shim.obj"
if %ERRORLEVEL% neq 0 goto :err_link

echo === SUCCESS - libft8_diag.dll built (NOT copied to win-x64) ===
echo Next step: copy /Y native\ft8_lib_build\libft8_diag.dll src\OpenWSFZ.Ft8\Native\win-x64\libft8.dll
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