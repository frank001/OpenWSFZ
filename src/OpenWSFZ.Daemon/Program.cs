using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using OpenWSFZ.Audio;
using OpenWSFZ.Config;
using OpenWSFZ.Daemon;
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

var audioSource     = new PlatformAudioSource();
var captureManager  = new CaptureManager(audioSource);

// Create and configure the web application.
// audioProviderFactory defers construction of PlatformAudioDeviceProvider until
// DI resolves it, so the app's own ILoggerFactory is available when it's built.
var app = WebApp.Create(
    port,
    configStore:          configStore,
    audioProviderFactory: sp => new PlatformAudioDeviceProvider(
                                    sp.GetRequiredService<ILoggerFactory>()),
    captureManager:       captureManager);

// ── Lifecycle hooks ──────────────────────────────────────────────────────────

// Start capture at startup if a device is already configured.
app.Lifetime.ApplicationStarted.Register(() =>
{
    WelcomeBannerEmitter.Emit(port);

    var deviceName = configStore.Current.AudioDeviceName;
    if (deviceName is not null)
    {
        _ = captureManager
            .StartAsync(deviceName)
            .ContinueWith(t =>
            {
                if (t.IsFaulted)
                    Console.Error.WriteLine(
                        $"[OpenWSFZ] Audio capture failed to start: {t.Exception?.GetBaseException().Message}");
            });
    }
});

// Restart capture when the device name changes via POST /api/v1/config.
string? runningDevice = configStore.Current.AudioDeviceName;
configStore.OnSaved += newConfig =>
{
    var newDevice = newConfig.AudioDeviceName;
    if (newDevice == runningDevice) return;

    runningDevice = newDevice;

    _ = Task.Run(async () =>
    {
        await captureManager.StopAsync();
        if (newDevice is not null)
        {
            try { await captureManager.StartAsync(newDevice); }
            catch (Exception ex)
            {
                Console.Error.WriteLine(
                    $"[OpenWSFZ] Audio capture failed to restart: {ex.Message}");
            }
        }
    });
};

// Stop capture and dispose on application shutdown.
app.Lifetime.ApplicationStopping.Register(() =>
{
    captureManager.StopAsync().GetAwaiter().GetResult();
    captureManager.DisposeAsync().AsTask().GetAwaiter().GetResult();
});

await app.RunAsync();

// Public partial Program class — type anchor for WebApplicationFactory<Program> in tests.
public partial class Program { }
