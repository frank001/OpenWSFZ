using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Web;

/// <summary>
/// Phase 1 auth policy: pass-through no-op.
/// Exercises the <see cref="IAuthPolicy"/> seam without any real logic.
/// Replaced by a token / OIDC policy in a future phase.
/// </summary>
public sealed class NullAuthPolicy : IAuthPolicy { }
