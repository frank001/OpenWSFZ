using Microsoft.AspNetCore.Mvc.Testing;

namespace OpenWSFZ.Web.Tests;

/// <summary>
/// Integration-test factory for HTTP-only tests.  Uses <c>TestServer</c> (in-process,
/// no real socket) which is fast and sufficient for REST endpoint tests.
/// WebSocket upgrade tests use <see cref="RealServerFixture"/> instead.
/// </summary>
public sealed class WebTestFactory : WebApplicationFactory<Program>
{
    // No overrides needed: default TestServer works for HTTP endpoint tests.
}
