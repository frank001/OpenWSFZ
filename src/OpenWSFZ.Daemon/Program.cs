using System.Threading.Channels;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Audio;
using OpenWSFZ.Config;
using OpenWSFZ.Daemon;
using OpenWSFZ.Ft8;
using OpenWSFZ.Web;

// Parse CLI options before building the host.
var options = LaunchOptions.Parse(args);

// Resolve the config file path (CLI flag → env var → platform default).
var (configPath, configSource) = ConfigPathResolver.Resolve(options.ConfigPath);
Console.Error.WriteLine($"[OpenWSFZ] Config: {configSource} → {configPath}");

// Load (or create) the config file and wire DI.
var configStore = new JsonConfigStore(configPath);

// CLI --port wins; fall back to the persisted config value.
var port = options.Port ?? configStore.Current.Port;

// ── Audio capture ─────────────────────────────────────────────────────────────

var audioSource    = new PlatformAudioSource();
var captureManager = new CaptureManager(audioSource);

// ── FT8 decode pipeline ──────────────────────────────────────────────────────

var clock       = new SystemClock();
var ft8Decoder  = new Ft8Decoder(clock);
var decodeEventBus = new DecodeEventBus();

// Channel 1: CycleFramer → float[] PCM windows → decode pump
// Channel 2: decode pump → DecodeEventBus (direct call, no channel needed)
var framerOutput = Channel.CreateBounded<float[]>(new BoundedChannelOptions(2)
{
    FullMode     = BoundedChannelFullMode.DropOldest,
    SingleWriter = true,
    SingleReader = true,
});

CancellationTokenSource? framerCts = null;
Task? framerTask = null;

// Create and configure the web application.
var app = WebApp.Create(
    port,
    configStore:          configStore,
    audioProviderFactory: sp => new PlatformAudioDeviceProvider(
                                    sp.GetRequiredService<ILoggerFactory>()),
    captureManager:       captureManager);

// ── Lifecycle hooks ──────────────────────────────────────────────────────────

app.Lifetime.ApplicationStarted.Register(() =>
{
    WelcomeBannerEmitter.Emit(port);

    var deviceName = configStore.Current.AudioDeviceName;
    if (deviceName is not null)
        StartPipeline(deviceName);

    // Decode-pump: reads completed PCM windows, decodes, broadcasts results.
    _ = Task.Run(async () =>
    {
        await foreach (var pcmWindow in framerOutput.Reader.ReadAllAsync())
        {
            try
            {
                var results = await ft8Decoder.DecodeAsync(pcmWindow);
                decodeEventBus.Publish(results);
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[OpenWSFZ] Decode error: {ex.Message}");
            }
        }
    });
});

// Restart pipeline when the device name changes via POST /api/v1/config.
string? runningDevice = configStore.Current.AudioDeviceName;
configStore.OnSaved += newConfig =>
{
    var newDevice = newConfig.AudioDeviceName;
    if (newDevice == runningDevice) return;

    runningDevice = newDevice;

    _ = Task.Run(async () =>
    {
        await StopFramerAsync();
        await captureManager.StopAsync();

        if (newDevice is not null)
        {
            try
            {
                await captureManager.StartAsync(newDevice);
                StartPipeline(newDevice);
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine(
                    $"[OpenWSFZ] Audio capture failed to restart: {ex.Message}");
            }
        }
    });
};

// Stop pipeline and dispose on application shutdown.
app.Lifetime.ApplicationStopping.Register(() =>
{
    StopFramerAsync().GetAwaiter().GetResult();
    captureManager.StopAsync().GetAwaiter().GetResult();
    captureManager.DisposeAsync().AsTask().GetAwaiter().GetResult();
    framerOutput.Writer.TryComplete();
});

await app.RunAsync();

// ── Helper methods ───────────────────────────────────────────────────────────

void StartPipeline(string deviceName)
{
    _ = captureManager
        .StartAsync(deviceName)
        .ContinueWith(t =>
        {
            if (t.IsFaulted)
                Console.Error.WriteLine(
                    $"[OpenWSFZ] Audio capture failed to start: {t.Exception?.GetBaseException().Message}");
        });

    framerCts = new CancellationTokenSource();
    var ct = framerCts.Token;

    var cycleFramer = new CycleFramer(captureManager.Samples, clock);
    framerTask = Task.Run(() => cycleFramer.RunAsync(framerOutput.Writer, ct));
}

async Task StopFramerAsync()
{
    var cts = framerCts;
    if (cts is null) return;

    cts.Cancel();

    var task = framerTask;
    if (task is not null)
    {
        try { await task.WaitAsync(TimeSpan.FromSeconds(3)); }
        catch (TimeoutException) { }
        catch (OperationCanceledException) { }
        catch (Exception) { }
    }

    cts.Dispose();
    framerCts  = null;
    framerTask = null;
}

// Public partial Program class — type anchor for WebApplicationFactory<Program> in tests.
public partial class Program { }
