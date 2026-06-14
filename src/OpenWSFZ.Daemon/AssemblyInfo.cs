using System.Runtime.CompilerServices;

// Allow the Ft8 test project to call internal members of OpenWSFZ.Daemon
// (used for LogRotationService.CalculateNextBoundary unit tests).
[assembly: InternalsVisibleTo("OpenWSFZ.Ft8.Tests")]

// Allow the Daemon test project to call internal members of OpenWSFZ.Daemon
// (used for QsoAnswererService parser unit tests).
[assembly: InternalsVisibleTo("OpenWSFZ.Daemon.Tests")]
