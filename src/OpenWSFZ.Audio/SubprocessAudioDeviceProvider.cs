using System.Diagnostics;
using System.Text.RegularExpressions;
using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Audio;

/// <summary>
/// Enumerates audio capture devices by invoking an external command and parsing
/// its stdout. Used on Linux (<c>arecord --list-devices</c>) and macOS
/// (<c>system_profiler SPAudioDataType -json</c>). Returns an empty list — never
/// throws — if the command is absent or exits non-zero.
/// </summary>
internal sealed class SubprocessAudioDeviceProvider : IAudioDeviceProvider
{
    private readonly string   _command;
    private readonly string[] _arguments;
    private readonly Func<string, IReadOnlyList<AudioDeviceInfo>> _parser;

    internal SubprocessAudioDeviceProvider(
        string   command,
        string[] arguments,
        Func<string, IReadOnlyList<AudioDeviceInfo>> parser)
    {
        _command   = command;
        _arguments = arguments;
        _parser    = parser;
    }

    // ── Factory methods ──────────────────────────────────────────────────────

    /// <summary>Creates the Linux provider (parses <c>arecord --list-devices</c>).</summary>
    public static SubprocessAudioDeviceProvider ForLinux() =>
        new("arecord", ["--list-devices"], ParseArecordOutput);

    /// <summary>Creates the macOS provider (parses <c>system_profiler SPAudioDataType -json</c>).</summary>
    public static SubprocessAudioDeviceProvider ForMacOs() =>
        new("system_profiler", ["SPAudioDataType", "-json"], ParseSystemProfilerOutput);

    // ── IAudioDeviceProvider ─────────────────────────────────────────────────

    public async Task<IReadOnlyList<AudioDeviceInfo>> GetDevicesAsync(CancellationToken ct = default)
    {
        try
        {
            using var process = new Process
            {
                StartInfo = new ProcessStartInfo(_command)
                {
                    RedirectStandardOutput = true,
                    RedirectStandardError  = true,
                    UseShellExecute        = false,
                },
            };

            foreach (var arg in _arguments)
                process.StartInfo.ArgumentList.Add(arg);

            process.Start();
            var stdout = await process.StandardOutput.ReadToEndAsync(ct);
            await process.WaitForExitAsync(ct);

            if (process.ExitCode != 0)
                return [];

            return _parser(stdout);
        }
        catch (OperationCanceledException)
        {
            // Propagate cancellation — callers that cancel the token expect the exception.
            throw;
        }
        catch
        {
            // Tool absent, permission denied, or any other failure → empty list.
            return [];
        }
    }

    // ── Parsers ──────────────────────────────────────────────────────────────

    /// <summary>
    /// Parses <c>arecord --list-devices</c> output.
    /// Sample lines:
    ///   card 0: PCH [HDA Intel PCH], device 0: ALC892 Analog [ALC892 Analog]
    ///   card 1: USB [Generic USB Audio], device 0: USB Audio [USB Audio]
    /// </summary>
    internal static IReadOnlyList<AudioDeviceInfo> ParseArecordOutput(string output)
    {
        var devices = new List<AudioDeviceInfo>();
        // Match "card N: ShortName [Long Name], device M: ..."
        var regex = new Regex(
            @"^card\s+(\d+):\s+\S+\s+\[([^\]]+)\],\s+device\s+(\d+):",
            RegexOptions.Multiline);

        foreach (Match m in regex.Matches(output))
        {
            var card   = m.Groups[1].Value;
            var name   = m.Groups[2].Value.Trim();
            var device = m.Groups[3].Value;
            devices.Add(new AudioDeviceInfo(
                Id:   $"hw:{card},{device}",
                Name: name));
        }

        return devices;
    }

    /// <summary>
    /// Parses <c>system_profiler SPAudioDataType -json</c> output.
    /// Looks for items under SPAudioDataType[].Items[] that have _name and
    /// coreaudio_input_source fields, indicating capture capability.
    /// Falls back to returning all named items if structured parsing fails.
    /// </summary>
    internal static IReadOnlyList<AudioDeviceInfo> ParseSystemProfilerOutput(string output)
    {
        var devices = new List<AudioDeviceInfo>();

        try
        {
            using var doc = System.Text.Json.JsonDocument.Parse(output);
            if (!doc.RootElement.TryGetProperty("SPAudioDataType", out var dataType))
                return devices;

            foreach (var entry in dataType.EnumerateArray())
            {
                if (!entry.TryGetProperty("_items", out var items))
                    continue;

                foreach (var item in items.EnumerateArray())
                {
                    if (!item.TryGetProperty("_name", out var nameProp))
                        continue;

                    // Only include devices with an input source (capture capable).
                    if (!item.TryGetProperty("coreaudio_input_source", out _))
                        continue;

                    var name = nameProp.GetString() ?? string.Empty;
                    if (string.IsNullOrWhiteSpace(name)) continue;

                    devices.Add(new AudioDeviceInfo(Id: name, Name: name));
                }
            }
        }
        catch
        {
            // Malformed JSON or unexpected schema → return empty.
        }

        return devices;
    }
}
