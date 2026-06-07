@echo off
:: rebuild_monitor_and_shim.bat
::
:: Full rebuild of the two patched C translation units that need MSVC-specific
:: treatment (monitor.c ??? patched VLAs; ft8_shim.c ??? our shim), then relinks
:: libft8.dll using the pre-built .obj files for the remaining ft8_lib sources.
::
:: Run this when:
::   - ft8_shim.c has changed (heap-allocation fix, new pass logic, etc.)
::   - native/ft8_lib_build/patched/common/monitor.c has changed (LOG_LEVEL, etc.)
::
:: For changes to other ft8_lib sources (decode.c, ldpc.c, etc.) you need a
:: full rebuild from source ??? see BUILD.md.

call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
if %ERRORLEVEL% neq 0 ( echo FAILED: vcvars64.bat & exit /b 1 )

set OBJ_DIR=D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj
set HEADERS=C:\Temp\ft8_lib_headers
set SHIM_DIR=D:\Projects\claude\OpenWSFZ\src\OpenWSFZ.Ft8\Native
set PATCHED_DIR=D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\patched

echo Compiling patched monitor.c...
cl /I"%HEADERS%" /I"%HEADERS%\common" /std:c11 /O2 /W3 /c ^
   /Fo"%OBJ_DIR%\monitor.obj" ^
   "%PATCHED_DIR%\common\monitor.c"
if %ERRORLEVEL% neq 0 ( echo COMPILE FAILED: monitor.c & exit /b 1 )

echo Compiling ft8_shim.c...
cl /I"%HEADERS%" /I"%SHIM_DIR%" /std:c11 /O2 /W3 /c ^
   /Fo"%OBJ_DIR%\ft8_shim.obj" ^
   "%SHIM_DIR%\ft8_shim.c"
if %ERRORLEVEL% neq 0 ( echo COMPILE FAILED: ft8_shim.c & exit /b 1 )

echo Linking...
link /DLL ^
  /OUT:"D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\libft8.dll" ^
  /EXPORT:ft8_lib_version_check ^
  /EXPORT:ft8_decode_all ^
  /EXPORT:ft8_get_last_pass_counts ^
  /EXPORT:ft8_get_max_passes ^
  "%OBJ_DIR%\constants.obj" ^
  "%OBJ_DIR%\crc.obj" ^
  "%OBJ_DIR%\decode.obj" ^
  "%OBJ_DIR%\encode.obj" ^
  "%OBJ_DIR%\ldpc.obj" ^
  "%OBJ_DIR%\message.obj" ^
  "%OBJ_DIR%\text.obj" ^
  "%OBJ_DIR%\monitor.obj" ^
  "%OBJ_DIR%\kiss_fft.obj" ^
  "%OBJ_DIR%\kiss_fftr.obj" ^
  "%OBJ_DIR%\ft8_shim.obj"
if %ERRORLEVEL% neq 0 ( echo LINK FAILED & exit /b 1 )

echo Copying DLL to repo...
copy /Y "D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\libft8.dll" ^
        "D:\Projects\claude\OpenWSFZ\src\OpenWSFZ.Ft8\Native\win-x64\libft8.dll"
if %ERRORLEVEL% neq 0 ( echo COPY FAILED & exit /b 1 )

echo BUILD SUCCESS
