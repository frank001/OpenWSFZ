using System.Reflection;
using System.Runtime.InteropServices;
using System.Text.RegularExpressions;
using FluentAssertions;
using OpenWSFZ.Abstractions;
using OpenWSFZ.Ft8.Interop;
using Xunit;
using Xunit.Abstractions;

namespace OpenWSFZ.Ft8.Tests;

/// <summary>
/// Tests for the decoder parameter readout (decoder-param-readout, DENSITY-REMEDY Stage 1, shim
/// 20260054): <c>ft8_get_decoder_params</c> (the whole parameter table, one call) and the
/// soft-suppression ramp's runtime setter/getter <c>ft8_set_supp_params</c> /
/// <c>ft8_get_supp_params</c>.
/// <para>
/// <b>Test-local P/Invoke, on purpose.</b> The two suppression exports have NO managed binding: no
/// <c>DllImport</c> in <c>src/OpenWSFZ.Ft8</c> (the live application never sets the ramp), so they are
/// declared in <see cref="ParamNative"/> below, in the TEST assembly only. The table itself IS bound
/// in <c>src/</c>, read-only, and is exercised through <see cref="Ft8LibInterop.GetDecoderParams"/>.
/// </para>
/// <para>
/// <b>Native state is process-global and persists across tests.</b> Every test that sets a
/// parameter does so inside a <see cref="NativeStateGuard"/>, which snapshots the current runtime
/// values FROM THE TABLE ITSELF and restores them exactly, so no test can leak a setting into another.
/// Test parallelisation is disabled for this assembly (<c>AssemblyInfo.cs</c>).
/// </para>
/// <para>
/// Deterministic synthetic scenes only; <c>Q</c>-prefix synthetic callsigns only (NFR-021).
/// </para>
/// </summary>
[Trait("Category", "RequiresNativeBinary")]
public sealed class DecoderParamReadoutTests
{
    private readonly ITestOutputHelper _out;
    public DecoderParamReadoutTests(ITestOutputHelper output) => _out = output;

    // ── Test-local P/Invoke (NOT in src/) ────────────────────────────────────

    /// <summary>Mirror of the native <c>FT8Result</c> (48 bytes).</summary>
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)]
    private struct NativeResult
    {
        public int   FreqHz;
        public float Dt;
        public int   Snr;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 36)]
        public string Message;
    }

    /// <summary>Mirror of the native <c>Ft8ParamEntry</c> (72 bytes).</summary>
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)]
    private struct NativeParam
    {
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 48)]
        public string Name;
        public double Value;
        public double DefaultValue;
        public int    Kind;
        public int    Reserved;
    }

    private static class ParamNative
    {
        private const string Lib = "libft8.dll";

        // The test assembly needs its own resolver: Ft8LibInterop's is registered on the
        // OpenWSFZ.Ft8 assembly and does not apply to this one. It loads the SAME file from the
        // SAME directory, so both bind the one module (and its process-global state).
        static ParamNative()
        {
            try { NativeLibrary.SetDllImportResolver(typeof(ParamNative).Assembly, Resolve); }
            catch (InvalidOperationException) { /* already registered for this assembly */ }
        }

        private static IntPtr Resolve(string name, Assembly asm, DllImportSearchPath? path)
        {
            if (name != Lib) return IntPtr.Zero;
            string file = RuntimeInformation.IsOSPlatform(OSPlatform.Windows) ? "libft8.dll"
                        : RuntimeInformation.IsOSPlatform(OSPlatform.OSX)     ? "libft8.dylib"
                        : "libft8.so";
            return NativeLibrary.Load(Path.Combine(AppContext.BaseDirectory, file));
        }

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        public static extern int ft8_lib_version_check();

        // [In, Out] so the runtime's copy-back can never disturb entries the native side did not
        // write: the "untouched beyond capacity" assertions must test the NATIVE code.
        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        public static extern int ft8_get_decoder_params([In, Out] NativeParam[]? buf, int capacity);

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        public static extern void ft8_set_decode_params(int kMinScorePass2, float osdCorrThreshold, int osdNhardMax);

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        public static extern int ft8_set_supp_params(float snrMinDb, float snrMaxDb, float sideWeight);

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        public static extern int ft8_get_supp_params([In, Out] float[]? out3);

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        public static extern int ft8_decode_all([In] float[] pcm, int pcmLen, [Out] NativeResult[] results, int maxResults);

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        public static extern int ft8_get_max_passes();

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        public static extern int ft8_get_last_pass_counts([Out] int[] counts, int capacity);

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        public static extern int ft8_get_last_candidate_counts([Out] int[] counts, int capacity);

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        public static extern int ft8_get_last_snr_terms([Out] float[] signalDb, [Out] float[] localNoiseDb, int capacity);

        [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
        public static extern float ft8_get_last_noise_floor_db();
    }

    // ── Constants asserted as LITERALS on purpose (the documented contract), not imported ──

    private const int    NameCapacity   = 48;
    private const int    KindCompile    = 0;
    private const int    KindRuntime    = 1;
    private const int    PcmLen         = 180_000;
    private const int    MaxResults     = 340;

    private const int    DefaultK       = 10;
    private const float  DefaultCorr    = 0.10f;
    private const int    DefaultNhard   = 60;
    private const float  DefaultSnrMin  = -5.0f;
    private const float  DefaultSnrMax  = 15.0f;
    private const float  DefaultSide    = 1.0f;

    /// <summary>The six runtime-settable values, in table order.</summary>
    private static readonly string[] RuntimeNames =
    [
        "k_min_score_pass2", "osd_corr_threshold", "osd_nhard_max",
        "supp_snr_min_db", "supp_snr_max_db", "supp_side_weight",
    ];

    /// <summary>
    /// The completeness LEDGER: every name the table must carry, runtime first. A parameter added to
    /// the native table must be added here, deliberately: that friction is the point (design D2/D12).
    /// </summary>
    private static readonly string[] ExpectedNames =
    [
        // runtime
        "k_min_score_pass2", "osd_corr_threshold", "osd_nhard_max",
        "supp_snr_min_db", "supp_snr_max_db", "supp_side_weight",
        // compile-time: every #define K_* the decode path reads (ft8_shim.c)
        "K_MIN_SCORE", "K_MAX_CANDIDATES", "K_LDPC_ITERATIONS", "K_FREQ_OSR", "K_TIME_OSR", "K_MAX_PASSES",
        "K_SOFT_SUPP_SNR_MIN_DB", "K_SOFT_SUPP_SNR_MAX_DB", "K_SUPP_FOOTPRINT_HALF_BINS",
        "K_MAX_CANDIDATES_PASS2", "K_LDPC_ITERATIONS_PASS2", "K_MAX_DECODED", "K_MAX_CANDIDATES_ANY_PASS",
        "K_LOCAL_NOISE_WINDOW", "K_PASSBAND_MIN_HZ", "K_PASSBAND_MAX_HZ", "K_SNR_OFFSET_DB",
        // compile-time: named tuning #defines that are not K_-prefixed
        "FT8_AP_LLR_HARD", "HASH_TABLE_SIZE",
        // compile-time: tuning constants defined in patched decode.c
        "OSD_DEPTH", "OSD_SEARCH_K_MAX", "LLR_NORM_TARGET_VARIANCE", "CAND_TIME_OFFSET_MIN", "CAND_TIME_OFFSET_END",
    ];

    // ── Native helpers ───────────────────────────────────────────────────────

    private static NativeParam[] ReadTable()
    {
        int total = ParamNative.ft8_get_decoder_params(null, 0);
        total.Should().BeGreaterThan(0, "the sizing call must return the total entry count");
        var buf = new NativeParam[total];
        ParamNative.ft8_get_decoder_params(buf, total).Should().Be(total);
        return buf;
    }

    private static NativeParam Entry(NativeParam[] table, string name)
    {
        var hits = table.Where(e => e.Name == name).ToArray();
        hits.Should().ContainSingle($"the table must carry exactly one entry named '{name}'");
        return hits[0];
    }

    private static float[] ReadSupp()
    {
        var v = new float[3];
        ParamNative.ft8_get_supp_params(v).Should().Be(0);
        return v;
    }

    /// <summary>
    /// Snapshots the runtime parameters FROM THE TABLE and restores them on dispose, so a test that
    /// sets them can never leak state into another (the native state is process-global).
    /// </summary>
    private sealed class NativeStateGuard : IDisposable
    {
        private readonly int _k; private readonly float _corr; private readonly int _nhard;
        private readonly float[] _supp;

        public NativeStateGuard()
        {
            var t = ReadTable();
            _k     = (int)Entry(t, "k_min_score_pass2").Value;
            _corr  = (float)Entry(t, "osd_corr_threshold").Value;
            _nhard = (int)Entry(t, "osd_nhard_max").Value;
            _supp  = ReadSupp();
        }

        public void Dispose()
        {
            ParamNative.ft8_set_decode_params(_k, _corr, _nhard);
            ParamNative.ft8_set_supp_params(_supp[0], _supp[1], _supp[2]);
        }
    }

    private static void SetDefaults()
    {
        ParamNative.ft8_set_decode_params(DefaultK, DefaultCorr, DefaultNhard);
        ParamNative.ft8_set_supp_params(DefaultSnrMin, DefaultSnrMax, DefaultSide).Should().Be(0);
    }

    // ── Source-tree access for the completeness checks ───────────────────────

    private static string RepoFile(string relative)
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null && !File.Exists(Path.Combine(dir.FullName, "OpenWSFZ.slnx")))
            dir = dir.Parent;
        dir.Should().NotBeNull(
            "the completeness checks read native/ and src/ sources from the repository checkout " +
            "(found no OpenWSFZ.slnx above the test output directory)");
        string path = Path.Combine(dir!.FullName, relative.Replace('/', Path.DirectorySeparatorChar));
        File.Exists(path).Should().BeTrue($"'{relative}' must exist in the checkout");
        return File.ReadAllText(path);
    }

    private const string ShimC   = "src/OpenWSFZ.Ft8/Native/ft8_shim.c";
    private const string DecodeC = "native/ft8_lib_build/patched/ft8/decode.c";

    /// <summary>
    /// The source with C comments and string literals blanked (newlines kept), so a check about
    /// literals in CODE is not confused by a comment that quotes the old value. Nested/odd cases
    /// are not a concern: both files are plain C, and this only needs to be right for them.
    /// </summary>
    private static string CodeOnly(string source)
        => Regex.Replace(source, @"/\*.*?\*/|//[^\r\n]*|""(?:\\.|[^""\\])*""",
                         m => Regex.Replace(m.Value, @"[^\r\n]", " "), RegexOptions.Singleline);

    /// <summary>Parses a literal-valued <c>#define NAME value</c>, tolerating parentheses and an <c>f</c> suffix.</summary>
    private static double? DefineValue(string source, string name)
    {
        var m = Regex.Match(source,
            @"^[ \t]*#define[ \t]+" + Regex.Escape(name) + @"[ \t]+\(?[ \t]*(-?[0-9]+(?:\.[0-9]+)?)[fF]?[ \t]*\)?",
            RegexOptions.Multiline);
        return m.Success ? double.Parse(m.Groups[1].Value, System.Globalization.CultureInfo.InvariantCulture) : null;
    }

    // ═════════════════════════════════════════════════════════════════════════
    // FR-067 — the parameter table
    // ═════════════════════════════════════════════════════════════════════════

    [Fact(DisplayName = "FR-067: the loaded native binary is at least shim 20260054 and Ft8ParamEntry is 72 bytes")]
    public void LoadedBinary_HasTheTable_AndEntryLayoutIs72Bytes()
    {
        // A capability precondition, not an identity pin: the table exists from 20260054 onwards.
        // (ExpectedShimVersion's own load-time self-test is what enforces the EXACT version.)
        ParamNative.ft8_lib_version_check().Should().BeGreaterThanOrEqualTo(20260054);
        Marshal.SizeOf<NativeParam>().Should().Be(72, "char[48] + two doubles + two int32, no padding");
        Marshal.SizeOf<Ft8NativeParamEntry>().Should().Be(72, "the production mirror must match the native struct");
    }

    [Fact(DisplayName = "FR-067: ft8_get_decoder_params(NULL, 0) returns the total and writes nothing; a short buffer is filled only to capacity")]
    public void GetDecoderParams_SizingAndCapacityContract()
    {
        int total = ParamNative.ft8_get_decoder_params(null, 0);
        total.Should().Be(ExpectedNames.Length);
        ParamNative.ft8_get_decoder_params(null, 50).Should().Be(total, "a NULL buffer writes nothing whatever the capacity");

        NativeParam Sentinel() => new() { Name = "SENTINEL", Value = -12345.0, DefaultValue = -54321.0, Kind = 99, Reserved = 77 };

        // capacity 0 and negative: the buffer must be untouched
        foreach (int cap in new[] { 0, -3 })
        {
            var b = Enumerable.Range(0, 4).Select(_ => Sentinel()).ToArray();
            ParamNative.ft8_get_decoder_params(b, cap).Should().Be(total);
            b.Should().OnlyContain(e => e.Name == "SENTINEL" && e.Kind == 99, $"capacity {cap} must write nothing");
        }

        // capacity smaller than the total: exactly `capacity` entries written, the rest untouched
        var few = Enumerable.Range(0, 5).Select(_ => Sentinel()).ToArray();
        ParamNative.ft8_get_decoder_params(few, 3).Should().Be(total, "the TOTAL is returned even when the buffer is short");
        few.Take(3).Select(e => e.Name).Should().Equal(RuntimeNames.Take(3));
        few.Skip(3).Should().OnlyContain(e => e.Name == "SENTINEL" && e.Kind == 99, "entries beyond `capacity` must not be written");
    }

    [Fact(DisplayName = "FR-067: every table entry is well-formed, names are unique, and the table matches the completeness ledger exactly")]
    public void Table_IsWellFormed_AndMatchesTheLedger()
    {
        var t = ReadTable();

        t.Select(e => e.Name).Should().Equal(ExpectedNames,
            "a parameter added to or removed from the native table must be added to or removed from " +
            "the ledger in this test, deliberately (design D2/D12: nothing is omitted silently)");
        t.Select(e => e.Name).Should().OnlyHaveUniqueItems();
        t.Should().OnlyContain(e => e.Name.Length > 0 && e.Name.Length < NameCapacity, "names are NUL-terminated within 48 bytes");
        t.Should().OnlyContain(e => e.Kind == KindCompile || e.Kind == KindRuntime);
        t.Should().OnlyContain(e => e.Reserved == 0);
        t.Where(e => e.Kind == KindRuntime).Select(e => e.Name).Should().Equal(RuntimeNames, "exactly the six runtime-settable values");
        t.Where(e => e.Kind == KindCompile).Should().OnlyContain(e => e.Value == e.DefaultValue,
            "for a compile-time constant, value and default are both the constant the decode path uses");
        t.Should().OnlyContain(e => !double.IsNaN(e.Value) && !double.IsInfinity(e.Value));
    }

    [Fact(DisplayName = "FR-067: the table reports what the decoder is running with, not what the application configured (osd_nhard_max 40, default 60)")]
    public void Table_ReportsNativeValue_NotTheConfiguredOne()
    {
        using var guard = new NativeStateGuard();

        ParamNative.ft8_set_decode_params(10, 0.10f, 40);      // what the daemon applies from DecoderConfig

        var e = Entry(ReadTable(), "osd_nhard_max");
        e.Kind.Should().Be(KindRuntime);
        e.Value.Should().Be(40);
        e.DefaultValue.Should().Be(60, "the compiled-in default is unchanged by a set: that split is the point of the feature");
    }

    [Fact(DisplayName = "FR-067: every compile-time value in the table equals the #define the decode path reads (ft8_shim.c and patched decode.c)")]
    public void CompileTimeEntries_EqualTheirDefines()
    {
        var t = ReadTable();
        string shim = RepoFile(ShimC), decode = RepoFile(DecodeC);

        // Every #define K_* in the shim must be tabled (S1-f(i)). Literal-valued ones are compared to
        // their #define; the two derived ones are checked by their relation.
        var kNames = Regex.Matches(shim, @"^[ \t]*#define[ \t]+(K_[A-Z0-9_]+)\b", RegexOptions.Multiline)
                          .Select(m => m.Groups[1].Value).Distinct().ToList();
        kNames.Should().NotBeEmpty();
        var derived = new[] { "K_MAX_DECODED", "K_MAX_CANDIDATES_ANY_PASS" };

        foreach (string name in kNames)
        {
            var e = Entry(t, name);
            e.Kind.Should().Be(KindCompile, $"{name} is a compile-time constant");
            if (derived.Contains(name)) continue;
            double? def = DefineValue(shim, name);
            def.Should().NotBeNull($"{name} must be a literal-valued #define this test can read (or be added to the derived list)");
            e.Value.Should().BeApproximately(def!.Value, 1e-6, $"{name} in the table must equal its #define");
        }

        double pass1 = Entry(t, "K_MAX_CANDIDATES").Value, pass2 = Entry(t, "K_MAX_CANDIDATES_PASS2").Value;
        Entry(t, "K_MAX_DECODED").Value.Should().Be(pass1 + pass2);
        Entry(t, "K_MAX_CANDIDATES_ANY_PASS").Value.Should().Be(Math.Max(pass1, pass2));

        // the named non-K_ tuning defines in the shim
        foreach (string name in new[] { "FT8_AP_LLR_HARD", "HASH_TABLE_SIZE" })
            Entry(t, name).Value.Should().BeApproximately(DefineValue(shim, name)!.Value, 1e-6);

        // the constants decode.c owns (read through const mirrors initialised from those macros)
        foreach (string name in new[] { "OSD_DEPTH", "OSD_SEARCH_K_MAX", "LLR_NORM_TARGET_VARIANCE", "CAND_TIME_OFFSET_MIN", "CAND_TIME_OFFSET_END" })
            Entry(t, name).Value.Should().BeApproximately(DefineValue(decode, name)!.Value, 1e-6, $"{name} must equal decode.c's #define");
    }

    [Fact(DisplayName = "FR-067: the runtime defaults in the table are the compiled-in defaults, and every setter's parameters are tabled")]
    public void RuntimeDefaults_AreTheCompiledDefaults()
    {
        var t = ReadTable();
        Entry(t, "k_min_score_pass2").DefaultValue.Should().Be(DefaultK);
        Entry(t, "osd_corr_threshold").DefaultValue.Should().Be((double)DefaultCorr);
        Entry(t, "osd_nhard_max").DefaultValue.Should().Be(DefaultNhard);
        Entry(t, "supp_snr_min_db").DefaultValue.Should().Be(DefaultSnrMin);
        Entry(t, "supp_snr_max_db").DefaultValue.Should().Be(DefaultSnrMax);
        Entry(t, "supp_side_weight").DefaultValue.Should().Be(DefaultSide);

        // The suppression defaults are the compile-time constants the ramp was baked with.
        Entry(t, "supp_snr_min_db").DefaultValue.Should().Be(Entry(t, "K_SOFT_SUPP_SNR_MIN_DB").Value);
        Entry(t, "supp_snr_max_db").DefaultValue.Should().Be(Entry(t, "K_SOFT_SUPP_SNR_MAX_DB").Value);
    }

    [Fact(DisplayName = "FR-067: no decode-path tuning value is a bare literal any more (passband, OSD depth, SNR offset, footprint)")]
    public void TuningValues_AreNamedConstants_UsedAtEverySite()
    {
        // CODE only: a comment may quote an old literal to explain what a constant replaced.
        string shim = CodeOnly(RepoFile(ShimC)), decode = CodeOnly(RepoFile(DecodeC));

        // The passband literals appear only in their two #defines; both monitor_config_t initialisers use the constants.
        Regex.Matches(shim, @"\b140\.0f\b").Should().HaveCount(1, "140.0f is written once, in `#define K_PASSBAND_MIN_HZ`");
        Regex.Matches(shim, @"\b3075\.0f\b").Should().HaveCount(1, "3075.0f is written once, in `#define K_PASSBAND_MAX_HZ`");
        Regex.Matches(shim, @"\.f_min\s*=\s*K_PASSBAND_MIN_HZ,\s*\.f_max\s*=\s*K_PASSBAND_MAX_HZ").Should().HaveCount(2,
            "both monitor_config_t sites (ft8_decode_all and ft8_extract_llrs_at) must read the constants");

        // No osd_decode call in decode.c passes a bare numeric depth (the parameter-driven harness call is fine).
        Regex.Matches(decode, @"osd_decode\(\s*llr_for_osd\s*,\s*[0-9]").Should().BeEmpty(
            "the OSD depth must be OSD_DEPTH at every production call site");
        Regex.Matches(decode, @"osd_decode\(\s*llr_for_osd\s*,\s*OSD_DEPTH\s*,").Should().HaveCount(2,
            "ftx_decode_candidate and ftx_decode_candidate_ap");

        // The SNR offset and suppression footprint are named too.
        shim.Should().Contain("- K_SNR_OFFSET_DB;");
        Regex.Matches(shim, @"\b26\.5f\b").Should().HaveCount(1, "26.5f only in `#define K_SNR_OFFSET_DB`");
        shim.Should().Contain("d = -K_SUPP_FOOTPRINT_HALF_BINS; d <= K_SUPP_FOOTPRINT_HALF_BINS");
    }

    [Fact(DisplayName = "FR-067: the managed reader returns every native row with the right kind, floats as their shortest decimal, and never an empty table")]
    public void ManagedReader_ReturnsTheNativeTable()
    {
        IReadOnlyList<DecoderParamEntry> managed = Ft8LibInterop.GetDecoderParams();
        var native = ReadTable();

        managed.Should().HaveSameCount(native);
        managed.Select(e => e.Name).Should().Equal(native.Select(e => e.Name));
        managed.Select(e => e.Kind).Should().Equal(
            native.Select(e => e.Kind == KindRuntime ? DecoderParamKind.Runtime : DecoderParamKind.CompileTime));

        // Values agree with the native double to within float precision; only the SPELLING of a float changes.
        for (int i = 0; i < native.Length; i++)
        {
            managed[i].Value.Should().BeApproximately(native[i].Value, 1e-6, managed[i].Name);
            managed[i].Default.Should().BeApproximately(native[i].DefaultValue, 1e-6, managed[i].Name);
        }
        var corr = managed.Single(e => e.Name == "osd_corr_threshold");
        corr.Value.Should().Be(0.1, "0.10f is presented as the number that was set, not 0.10000000149011612");
        corr.Default.Should().Be(0.1);
    }

    [Theory(DisplayName = "FR-067: NormaliseFloatValue gives an exact float its shortest decimal and leaves every other value untouched")]
    [InlineData(0.10000000149011612, 0.1)]      // (double)0.1f
    [InlineData(0.15000000596046448, 0.15)]     // (double)0.15f
    [InlineData(40.0, 40.0)]
    [InlineData(-5.0, -5.0)]
    [InlineData(3075.0, 3075.0)]
    [InlineData(26.5, 26.5)]
    [InlineData(0.1, 0.1)]                      // a genuine double that is NOT a float: unchanged
    [InlineData(1e300, 1e300)]                  // out of float range: unchanged
    public void NormaliseFloatValue_OnlyRespellsExactFloats(double input, double expected)
        => Ft8LibInterop.NormaliseFloatValue(input).Should().Be(expected);

    [Fact(DisplayName = "FR-067: NormaliseFloatValue leaves NaN and infinities untouched")]
    public void NormaliseFloatValue_LeavesNonFiniteAlone()
    {
        Ft8LibInterop.NormaliseFloatValue(double.PositiveInfinity).Should().Be(double.PositiveInfinity);
        Ft8LibInterop.NormaliseFloatValue(double.NegativeInfinity).Should().Be(double.NegativeInfinity);
        double.IsNaN(Ft8LibInterop.NormaliseFloatValue(double.NaN)).Should().BeTrue();
    }

    // ═════════════════════════════════════════════════════════════════════════
    // FR-068 — the suppression ramp's runtime setter / getter
    // ═════════════════════════════════════════════════════════════════════════

    [Fact(DisplayName = "FR-068: the defaults are -5 / 15 / 1.0 and a valid triple is stored and read back exactly")]
    public void SuppParams_DefaultsAndExactReadBack()
    {
        using var guard = new NativeStateGuard();

        SetDefaults();
        ReadSupp().Should().Equal(DefaultSnrMin, DefaultSnrMax, DefaultSide);

        ParamNative.ft8_set_supp_params(-25.0f, 30.0f, 0.5f).Should().Be(0);
        ReadSupp().Should().Equal(new[] { -25.0f, 30.0f, 0.5f }, "a valid triple must read back EXACTLY");

        ParamNative.ft8_set_supp_params(-5.0f, 15.0f, 0.0f).Should().Be(0, "side_weight 0 is the lower bound and is valid");
        ParamNative.ft8_set_supp_params(-5.0f, 15.0f, 1.0f).Should().Be(0, "side_weight 1 is the upper bound and is valid");
    }

    [Fact(DisplayName = "FR-068: snr_max has no upper bound beyond being finite and above snr_min (30 and 1000 are accepted)")]
    public void SuppParams_SnrMax_HasNoUpperBound()
    {
        using var guard = new NativeStateGuard();

        ParamNative.ft8_set_supp_params(-5.0f, 30.0f, 1.0f).Should().Be(0, "the Stage 2 bench sweeps snr_max above +15");
        ReadSupp()[1].Should().Be(30.0f);
        ParamNative.ft8_set_supp_params(-5.0f, 1000.0f, 1.0f).Should().Be(0);
        ReadSupp()[1].Should().Be(1000.0f);
    }

    public static TheoryData<string, float, float, float> InvalidTriples => new()
    {
        { "NaN snr_min",         float.NaN,               15.0f,                    1.0f  },
        { "NaN snr_max",         -5.0f,                   float.NaN,                1.0f  },
        { "NaN side_weight",     -5.0f,                   15.0f,                    float.NaN },
        { "+Inf snr_max",        -5.0f,                   float.PositiveInfinity,   1.0f  },
        { "-Inf snr_min",        float.NegativeInfinity,  15.0f,                    1.0f  },
        { "+Inf side_weight",    -5.0f,                   15.0f,                    float.PositiveInfinity },
        { "min == max",          10.0f,                   10.0f,                    1.0f  },
        { "min > max",           20.0f,                   10.0f,                    1.0f  },
        { "side_weight < 0",     -5.0f,                   15.0f,                    -0.001f },
        { "side_weight > 1",     -5.0f,                   15.0f,                    1.001f },
    };

    [Theory(DisplayName = "FR-068: each invalid class returns -1 and leaves ALL THREE prior values unchanged")]
    [MemberData(nameof(InvalidTriples))]
    public void SuppParams_InvalidInput_IsRejected_AndLeavesPriorValuesUnchanged(string why, float min, float max, float side)
    {
        using var guard = new NativeStateGuard();

        ParamNative.ft8_set_supp_params(-12.5f, 22.5f, 0.25f).Should().Be(0, "precondition: a known prior triple");

        ParamNative.ft8_set_supp_params(min, max, side).Should().Be(-1, why);
        ReadSupp().Should().Equal(new[] { -12.5f, 22.5f, 0.25f }, $"a rejected call ({why}) must not change ANY of the three values");
    }

    [Fact(DisplayName = "FR-068: ft8_get_supp_params(NULL) returns -1 and does not crash")]
    public void GetSuppParams_NullBuffer_IsRejected()
        => ParamNative.ft8_get_supp_params(null).Should().Be(-1);

    [Fact(DisplayName = "FR-068: round trip through the table — a set is reported exactly, the defaults are untouched, and a reset reports the defaults")]
    public void Table_RoundTrips_ThroughTheSetters()
    {
        using var guard = new NativeStateGuard();

        ParamNative.ft8_set_decode_params(7, 0.15f, 50);
        ParamNative.ft8_set_supp_params(-10.0f, 15.0f, 0.5f).Should().Be(0);

        var t = ReadTable();
        Entry(t, "k_min_score_pass2").Value.Should().Be(7);
        Entry(t, "osd_corr_threshold").Value.Should().Be((double)0.15f);
        Entry(t, "osd_nhard_max").Value.Should().Be(50);
        Entry(t, "supp_snr_min_db").Value.Should().Be(-10.0);
        Entry(t, "supp_snr_max_db").Value.Should().Be(15.0);
        Entry(t, "supp_side_weight").Value.Should().Be(0.5);
        // the compiled defaults are what they were
        Entry(t, "k_min_score_pass2").DefaultValue.Should().Be(DefaultK);
        Entry(t, "osd_nhard_max").DefaultValue.Should().Be(DefaultNhard);
        Entry(t, "supp_snr_min_db").DefaultValue.Should().Be(DefaultSnrMin);

        SetDefaults();
        t = ReadTable();
        foreach (string name in RuntimeNames)
            Entry(t, name).Value.Should().Be(Entry(t, name).DefaultValue, $"after a reset {name} must read its default");
    }

    // ── default-path identity ────────────────────────────────────────────────

    private const int    NoiseSeed  = 20260920;
    private const double NoiseSigma = 0.08;

    /// <summary>
    /// A crowded scene: strong/weak pairs 12.5 Hz and 6.25 Hz apart (so the pass-1 suppression's
    /// footprint lands on a neighbour), plus lone signals. tone-0 Hz, start sample, amplitude, text.
    /// </summary>
    private static readonly (double FreqHz, int StartSample, float Amplitude, string Text)[] CrowdedScene =
    [
        (  800.0, 6_000, 0.30f, "Q1OFZ Q9XYZ JO33"),
        (  812.5, 6_600, 0.05f, "CQ Q2WEA AA00"),
        ( 1400.0, 6_300, 0.28f, "Q9XYZ Q1OFZ RR73"),
        ( 1406.25, 7_000, 0.05f, "Q3WEB Q4WEC -12"),
        ( 1800.0, 6_500, 0.14f, "CQ Q5MID BB11"),
        ( 2000.0, 6_800, 0.09f, "CQ Q1ABC AA00"),
        ( 2500.0, 7_200, 0.06f, "Q6LOW Q1OFZ R-15"),
    ];

    private static float[] BuildCrowdedScene()
    {
        var pcm = new float[PcmLen];
        foreach (var (freq, start, amp, text) in CrowdedScene)
        {
            var tones = new byte[Ft8LibInterop.EncodedToneCount];
            Ft8LibInterop.EncodeMessage(text, tones);
            float[] one = TestFt8Encoder.SymbolsToPcm(Array.ConvertAll(tones, static t => (int)t), freq, start, amp);
            for (int i = 0; i < PcmLen; i++) pcm[i] += one[i];
        }

        var rng = new Random(NoiseSeed);       // new Random(seed) is a stable, documented sequence
        for (int i = 0; i < PcmLen; i++)
        {
            double u1 = 1.0 - rng.NextDouble();
            double u2 = rng.NextDouble();
            pcm[i] += (float)(NoiseSigma * Math.Sqrt(-2.0 * Math.Log(u1)) * Math.Cos(2.0 * Math.PI * u2));
        }
        return pcm;
    }

    private sealed record Snapshot(
        int Count, string[] Messages, int[] FreqHz, int[] DtBits, int[] Snr,
        int[] PassCounts, int[] CandidateCounts, int NoiseFloorBits, int[] SignalDbBits, int[] LocalNoiseDbBits);

    /// <summary>One decode plus the per-cycle diagnostics; every float compared as bits, never with ==.</summary>
    private static Snapshot Decode(float[] pcm)
    {
        var results = new NativeResult[MaxResults];
        int n = ParamNative.ft8_decode_all(pcm, pcm.Length, results, MaxResults);
        n.Should().BeGreaterThanOrEqualTo(0, "the decode call itself must not fail");

        int passes = ParamNative.ft8_get_max_passes();
        var pc = new int[passes];  ParamNative.ft8_get_last_pass_counts(pc, passes);
        var cc = new int[passes];  ParamNative.ft8_get_last_candidate_counts(cc, passes);
        var sig = new float[MaxResults]; var loc = new float[MaxResults];
        int nst = ParamNative.ft8_get_last_snr_terms(sig, loc, MaxResults);
        nst.Should().Be(n);

        var raw = results.Take(n).ToArray();
        return new Snapshot(n,
            raw.Select(r => r.Message).ToArray(), raw.Select(r => r.FreqHz).ToArray(),
            raw.Select(r => BitConverter.SingleToInt32Bits(r.Dt)).ToArray(), raw.Select(r => r.Snr).ToArray(),
            pc, cc, BitConverter.SingleToInt32Bits(ParamNative.ft8_get_last_noise_floor_db()),
            sig.Take(nst).Select(BitConverter.SingleToInt32Bits).ToArray(),
            loc.Take(nst).Select(BitConverter.SingleToInt32Bits).ToArray());
    }

    [Fact(DisplayName = "FR-068: decode output is bit-identical with the setter never called and with (-5, 15, 1.0) set explicitly")]
    public void DefaultPath_IsIdentical_WithSetterNeverCalledAndExplicitDefaults()
    {
        using var guard = new NativeStateGuard();
        float[] pcm = BuildCrowdedScene();

        // The starting state must BE the defaults, or "never called" would be a false description.
        ReadSupp().Should().Equal(new[] { DefaultSnrMin, DefaultSnrMax, DefaultSide },
            "precondition: no earlier test left the ramp at non-default values (they restore via NativeStateGuard)");

        Snapshot neverCalled = Decode(pcm);
        Decode(pcm).Should().BeEquivalentTo(neverCalled, o => o.WithStrictOrdering(),
            "precondition: two decodes of the same PCM at the same state must already be identical");

        ParamNative.ft8_set_supp_params(-5.0f, 15.0f, 1.0f).Should().Be(0);
        Snapshot explicitDefaults = Decode(pcm);

        explicitDefaults.Should().BeEquivalentTo(neverCalled, o => o.WithStrictOrdering(),
            "explicit defaults must take the SAME arithmetic as never having called the setter (side_weight 1.0 uses `factor` itself)");

        _out.WriteLine($"decodes: {neverCalled.Count} | pass counts {string.Join(",", neverCalled.PassCounts)} | " +
                       $"candidates {string.Join(",", neverCalled.CandidateCounts)}");
        neverCalled.Count.Should().BeGreaterThan(3, "the scene must actually decode, or the identity above proves nothing");
        neverCalled.CandidateCounts[1].Should().BeGreaterThan(0, "pass 1 must have run, so the suppression path was exercised");
    }

    [Theory(DisplayName = "FR-068: a non-default suppression setting DOES change the decode (the setter is live, so the identity above is not vacuous)")]
    [InlineData(-25.0f, 15.0f, 1.0f)]     // a lower floor: E at low SNR is now suppressed
    [InlineData(-5.0f,  15.0f, 0.0f)]     // side bins untouched: the footprint shrinks to the tone bin
    [InlineData(-5.0f,  30.0f, 1.0f)]     // a higher ceiling: the ramp is stretched
    public void NonDefaultSetting_ChangesTheDecode(float min, float max, float side)
    {
        using var guard = new NativeStateGuard();
        float[] pcm = BuildCrowdedScene();

        ParamNative.ft8_set_supp_params(DefaultSnrMin, DefaultSnrMax, DefaultSide).Should().Be(0);
        Snapshot baseline = Decode(pcm);

        ParamNative.ft8_set_supp_params(min, max, side).Should().Be(0);
        Snapshot changed = Decode(pcm);

        changed.Should().NotBeEquivalentTo(baseline, o => o.WithStrictOrdering(),
            "the ramp now reads the runtime values, so changing them must change the pass-1 waterfall and hence the decode diagnostics");
    }
}
