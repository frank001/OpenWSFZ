"""List all Windows audio devices and identify key ones for the study."""
import sounddevice as sd

devices = sd.query_devices()
print("=== ALL AUDIO DEVICES ===")
for i, d in enumerate(devices):
    max_in  = d["max_input_channels"]
    max_out = d["max_output_channels"]
    role = []
    if max_in  > 0: role.append("CAPTURE")
    if max_out > 0: role.append("RENDER")
    flag = ""
    name_lower = d["name"].lower()
    if "cable" in name_lower:        flag = " <-- VB-CABLE"
    if "voicemeeter" in name_lower:  flag = " <-- Voicemeeter"
    print(f"  [{i:2d}] {'/'.join(role):14s}  {d['name']}{flag}")

default_in  = sd.default.device[0]
default_out = sd.default.device[1]
print()
print(f"Default input  [{default_in}]: {devices[default_in]['name']}")
print(f"Default output [{default_out}]: {devices[default_out]['name']}")
