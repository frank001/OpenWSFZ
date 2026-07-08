using OpenWSFZ.Abstractions;

namespace OpenWSFZ.Daemon;

/// <summary>
/// Shared ADIF log path-resolution logic, used by both <see cref="AdifLogWriter"/> (the
/// writer, <c>adif-log</c> capability) and <see cref="WorkedBeforeIndex"/> (the reader,
/// <c>qso-confirmation</c> capability) so the two components can never disagree on where
/// <c>ADIF.log</c> lives.
///
/// <para>
/// The ADIF file is placed in the same directory as the ALL.TXT decode log
/// (<c>decodeLog.path</c> from <see cref="IConfigStore"/>), named <c>ADIF.log</c>. If
/// <c>decodeLog.path</c> has no directory component the ADIF file resolves to the current
/// working directory.
/// </para>
/// </summary>
internal static class AdifPathResolver
{
    /// <summary>Resolves the current ADIF log path from <paramref name="configStore"/>.</summary>
    public static string Resolve(IConfigStore configStore)
    {
        var decodeLogPath = configStore.Current.DecodeLog.Path;
        var dir            = Path.GetDirectoryName(decodeLogPath);
        return string.IsNullOrEmpty(dir)
            ? "ADIF.log"
            : Path.Combine(dir, "ADIF.log");
    }
}
