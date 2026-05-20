#if WASAPI_SUPPORTED

using System.Runtime.Versioning;

namespace OpenWSFZ.Audio;

/// <summary>
/// Runs a delegate on a dedicated COM STA background thread.
/// Required for WASAPI's <c>MMDeviceEnumerator</c> and <c>WasapiCapture</c>,
/// both of which require the creating thread to be in the STA apartment.
/// </summary>
[SupportedOSPlatform("windows")]
internal static class StaThread
{
    /// <summary>
    /// Executes <paramref name="func"/> on a new STA background thread and
    /// returns its result (or exception) via a <see cref="TaskCompletionSource{T}"/>.
    /// </summary>
    public static Task<T> Run<T>(Func<T> func)
    {
        var tcs = new TaskCompletionSource<T>(
            TaskCreationOptions.RunContinuationsAsynchronously);

        var t = new Thread(() =>
        {
            try   { tcs.SetResult(func()); }
            catch (Exception ex) { tcs.SetException(ex); }
        });

        t.IsBackground = true;
        t.SetApartmentState(ApartmentState.STA);
        t.Start();
        return tcs.Task;
    }
}

#endif
