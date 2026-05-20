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

// Create and configure the web application.
var app = WebApp.Create(
    port,
    configStore:   configStore,
    audioProvider: new PlatformAudioDeviceProvider());

// Emit the welcome banner once Kestrel is bound and ready.
app.Lifetime.ApplicationStarted.Register(() => WelcomeBannerEmitter.Emit(port));

await app.RunAsync();

// Public partial Program class — type anchor for WebApplicationFactory<Program> in tests.
public partial class Program { }
