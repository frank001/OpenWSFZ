@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul 2>&1
echo Compiling ft8_shim.c...
cl /I"C:\Temp\ft8_lib_headers" /I"D:\Projects\claude\OpenWSFZ\src\OpenWSFZ.Ft8\Native" /std:c11 /O2 /W3 /c /FoD:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\ft8_shim.obj D:\Projects\claude\OpenWSFZ\src\OpenWSFZ.Ft8\Native\ft8_shim.c
if %ERRORLEVEL% neq 0 ( echo COMPILE FAILED & exit /b 1 )
echo Linking...
link /DLL /OUT:D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\libft8.dll /EXPORT:ft8_lib_version_check /EXPORT:ft8_decode_all /EXPORT:ft8_get_last_pass_counts /EXPORT:ft8_get_max_passes /EXPORT:ft8_get_last_noise_floor_db D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\constants.obj D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\crc.obj D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\decode.obj D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\encode.obj D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\ldpc.obj D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\message.obj D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\text.obj D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\monitor.obj D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\kiss_fft.obj D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\kiss_fftr.obj D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\obj\ft8_shim.obj
if %ERRORLEVEL% neq 0 ( echo LINK FAILED & exit /b 1 )
echo Copying DLL to repo...
copy /Y D:\Projects\claude\OpenWSFZ\native\ft8_lib_build\libft8.dll D:\Projects\claude\OpenWSFZ\src\OpenWSFZ.Ft8\Native\win-x64\libft8.dll
if %ERRORLEVEL% neq 0 ( echo COPY FAILED & exit /b 1 )
echo BUILD SUCCESS
