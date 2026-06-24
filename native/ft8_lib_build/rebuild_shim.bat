@echo off
echo === Setting up MSVC x64 environment ===
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
echo ERRORLEVEL after vcvars64: %ERRORLEVEL%
if %ERRORLEVEL% neq 0 goto :err_env

echo === Compiling patched decode.c ===
cl ^
  /I "C:\Temp\ft8_lib_headers\ft8" ^
  /I "C:\Temp\ft8_lib_headers" ^
  /I "D:\Projects\claude\OpenWSFZ\src\OpenWSFZ.Ft8\Native" ^
  /std:c11 /O2 /W3 /c ^
  /Fo"D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\decode.obj" ^
  "D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\patched\ft8\decode.c"
echo ERRORLEVEL after cl (decode.c): %ERRORLEVEL%
if %ERRORLEVEL% neq 0 goto :err_cl

echo === Compiling ft8_shim.c ===
cl ^
  /I "C:\Temp\ft8_lib_headers" ^
  /I "D:\Projects\claude\OpenWSFZ\src\OpenWSFZ.Ft8\Native" ^
  /std:c11 /O2 /W3 /c ^
  /Fo"D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\ft8_shim.obj" ^
  "D:\Projects\claude\OpenWSFZ\src\OpenWSFZ.Ft8\Native\ft8_shim.c"
echo ERRORLEVEL after cl: %ERRORLEVEL%
if %ERRORLEVEL% neq 0 goto :err_cl

echo === Linking libft8.dll ===
link /DLL ^
  /OUT:"D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\libft8.dll" ^
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
  "D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\constants.obj" ^
  "D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\crc.obj" ^
  "D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\decode.obj" ^
  "D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\encode.obj" ^
  "D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\ldpc.obj" ^
  "D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\message.obj" ^
  "D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\text.obj" ^
  "D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\monitor.obj" ^
  "D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\kiss_fft.obj" ^
  "D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\kiss_fftr.obj" ^
  "D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\ft8_shim.obj"
echo ERRORLEVEL after link: %ERRORLEVEL%
if %ERRORLEVEL% neq 0 goto :err_link

echo === Copying DLL to repo ===
copy /Y "D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\libft8.dll" ^
        "D:\Projects\claude\OpenWSFZ\src\OpenWSFZ.Ft8\Native\win-x64\libft8.dll"
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
