using OpenWSFZ.Daemon;
using OpenWSFZ.Web;

// Parse CLI options before building the host.
var options = LaunchOptions.Parse(args);

// Create and configure the web application.
var app = WebApp.Create(options.Port);

// Emit the welcome banner once Kestrel is bound and ready.
app.Lifetime.ApplicationStarted.Register(() => WelcomeBannerEmitter.Emit(options.Port));

await app.RunAsync();

// Public partial Program class — type anchor for WebApplicationFactory<Program> in tests.
public partial class Program { }
