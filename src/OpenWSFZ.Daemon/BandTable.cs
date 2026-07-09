namespace OpenWSFZ.Daemon;

/// <summary>
/// Shared frequency (MHz) → ITU amateur band name mapping (<c>qso-confirmation-band-awareness</c>
/// design.md Decision 4). Extracted from <see cref="AdifLogWriter.DeriveBand"/> so both
/// <see cref="AdifLogWriter"/> (writing a QSO's <c>BAND</c> tag) and the decode pump's
/// "current active band" resolution (<see cref="Program"/>, threaded into
/// <c>Ft8Decoder.DecodeAsync</c>) use exactly one table — mirrors the existing
/// <see cref="AdifPathResolver"/> extraction precedent (<c>adif-qso-confirmation</c> design.md).
/// </summary>
internal static class BandTable
{
    /// <summary>
    /// Derives the ITU amateur band name from a dial frequency in MHz.
    /// Returns <c>null</c> when the frequency is zero or outside all known ham bands.
    /// </summary>
    public static string? DeriveBand(double freqMHz)
    {
        return freqMHz switch
        {
            >= 1.800 and < 2.000   => "160m",
            >= 3.500 and < 4.000   => "80m",
            >= 5.250 and < 5.450   => "60m",
            >= 7.000 and < 7.300   => "40m",
            >= 10.100 and < 10.150 => "30m",
            >= 14.000 and < 14.350 => "20m",
            >= 18.068 and < 18.168 => "17m",
            >= 21.000 and < 21.450 => "15m",
            >= 24.890 and < 24.990 => "12m",
            >= 28.000 and < 29.700 => "10m",
            >= 50.000 and < 54.000 => "6m",
            >= 144.000 and < 148.000 => "2m",
            >= 420.000 and < 450.000 => "70cm",
            _ => null
        };
    }
}
