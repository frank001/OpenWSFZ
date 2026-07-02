"""Check PortAudio host APIs and which API CABLE/Voicemeeter devices use."""
import sounddevice as sd

apis = sd.query_hostapis()
print("=== Host APIs ===")
for i, a in enumerate(apis):
    print(f"  [{i}] {a['name']}  default_in={a['default_input_device']}  default_out={a['default_output_device']}")

print()
print("=== CABLE and Voicemeeter Out B2 devices ===")
devs = sd.query_devices()
for i, d in enumerate(devs):
    name = d["name"].lower()
    if ("cable input" in name or "cable output" in name or "voicemeeter out b2" in name) and i < 120:
        api_name = apis[d["hostapi"]]["name"]
        print(f"  [{i:3d}] API={d['hostapi']:2d} ({api_name:15s})  in={d['max_input_channels']}  out={d['max_output_channels']}  {d['name']}")
