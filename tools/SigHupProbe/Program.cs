// SigHupProbe: a minimal helper process for daemon-background-mode's SIGHUP-ignore
// integration test (tasks.md 3.3). Exercises the exact BCL mechanism
// ConsoleDetacher.Detach() uses on Linux/macOS (PosixSignalRegistration.Create(SIGHUP, ...))
// so the test can prove a real OS SIGHUP delivered to a real subprocess is survived when the
// handler is armed, and terminates the process (the expected control case) when it is not.
//
// Usage: SigHupProbe [--ignore]
//   --ignore   register a SIGHUP-ignore handler before signalling readiness.
//              Absent: no handler is registered — SIGHUP's default disposition applies.
//
// Prints "READY" (then flushes) once armed/started, so the parent test can synchronise
// before sending a signal. Then waits up to 60 seconds so the test always has a bounded
// worst case even if something goes wrong and the process is never killed.

using System.Runtime.InteropServices;

PosixSignalRegistration? registration = null;

if (args.Contains("--ignore"))
{
    registration = PosixSignalRegistration.Create(PosixSignal.SIGHUP, ctx => ctx.Cancel = true);
}

Console.Out.WriteLine("READY");
Console.Out.Flush();

await Task.Delay(TimeSpan.FromSeconds(60));

GC.KeepAlive(registration);
