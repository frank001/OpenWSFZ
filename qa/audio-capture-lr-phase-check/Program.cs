// Raw stereo dump straight off a WASAPI capture device -- no left-channel extraction, no
// resampling, no FT8 decode. Purpose: measure the actual L/R relationship on
// "Microphone (2- USB Audio CODEC)" directly, to check the WasapiAudioSource.cs "D6" comment's
// claim that this device delivers a differential signal (L = -R). See LrPhaseCheck.csproj
// header for full context.
//
// Usage: dotnet run -- [seconds] [out.wav] [device-name-substring]
//   seconds                default 10
//   out.wav                default ./lr_phase_check.wav (write it under a git-ignored path)
//   device-name-substring  default "USB Audio CODEC" (case-insensitive contains match)

using NAudio.CoreAudioApi;
using NAudio.Wave;

double seconds = args.Length > 0 ? double.Parse(args[0]) : 10.0;
string outPath = args.Length > 1 ? args[1] : "lr_phase_check.wav";
string nameMatch = args.Length > 2 ? args[2] : "USB Audio CODEC";

Exception? failure = null;

// WASAPI requires the calling thread to be STA.
var t = new Thread(() =>
{
    try
    {
        using var enumerator = new MMDeviceEnumerator();
        var endpoints = enumerator.EnumerateAudioEndPoints(DataFlow.Capture, DeviceState.Active);

        MMDevice? device = null;
        Console.WriteLine("Active capture devices:");
        foreach (var ep in endpoints)
        {
            Console.WriteLine($"  '{ep.FriendlyName}'");
            if (ep.FriendlyName.Contains(nameMatch, StringComparison.OrdinalIgnoreCase))
                device = ep;
        }

        if (device is null)
            throw new InvalidOperationException($"No active capture device matching '{nameMatch}'.");

        Console.WriteLine($"\nOpening '{device.FriendlyName}' ...");

        using var capture = new WasapiCapture(device, useEventSync: false);
        Console.WriteLine(
            $"Negotiated format: {capture.WaveFormat.SampleRate} Hz, " +
            $"{capture.WaveFormat.BitsPerSample}-bit, {capture.WaveFormat.Channels} ch, " +
            $"Encoding={capture.WaveFormat.Encoding}");

        if (capture.WaveFormat.Channels != 2)
            Console.WriteLine(
                "WARNING: device did not negotiate stereo -- L/R comparison is not possible " +
                "with this format.");

        using var writer = new WaveFileWriter(outPath, capture.WaveFormat);
        var done = new ManualResetEventSlim(false);

        capture.DataAvailable += (_, e) =>
        {
            writer.Write(e.Buffer, 0, e.BytesRecorded);
        };
        capture.RecordingStopped += (_, e) =>
        {
            if (e.Exception is not null) failure = e.Exception;
            done.Set();
        };

        Console.WriteLine($"Recording {seconds:F1} s of RAW audio (no processing) -- keep the radio active/receiving now...");
        capture.StartRecording();
        Thread.Sleep(TimeSpan.FromSeconds(seconds));
        capture.StopRecording();
        done.Wait(TimeSpan.FromSeconds(5));

        writer.Flush();
        Console.WriteLine($"Wrote {outPath}");
    }
    catch (Exception ex)
    {
        failure = ex;
    }
});
t.SetApartmentState(ApartmentState.STA);
t.Start();
t.Join();

if (failure is not null)
{
    Console.Error.WriteLine($"FAILED: {failure}");
    Environment.Exit(1);
}
