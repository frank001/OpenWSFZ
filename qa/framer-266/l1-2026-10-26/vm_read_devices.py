# READ-ONLY: prints the input device name of each Voicemeeter strip (no writes). Login/Logout only.
import ctypes, time
dll = ctypes.WinDLL(r"C:\Program Files (x86)\VB\Voicemeeter\VoicemeeterRemote64.dll")
assert dll.VBVMR_Login() == 0
time.sleep(0.8)
dll.VBVMR_IsParametersDirty()
for i in range(0, 5):
    buf = ctypes.create_unicode_buffer(512)
    rc = dll.VBVMR_GetParameterStringW(f"Strip[{i}].device.name".encode(), buf)
    print(i, rc, repr(buf.value))
dll.VBVMR_Logout()
