namespace OpenWSFZ.Ft8.Interop;

/// <summary>
/// COH-FALLBACK step 4 (shim 20260069): the real <c>libft8</c> behind <see cref="ICohFallbackBackend"/>. Stateless; every worker owns
/// its native scratch context.
/// </summary>
internal sealed class CohFallbackLibBackend : ICohFallbackBackend
{
    /// <summary>The one instance (the backend holds no state).</summary>
    public static readonly CohFallbackLibBackend Instance = new();

    private CohFallbackLibBackend() { }

    /// <inheritdoc/>
    public CohFallbackPlan? Plan(byte[] snapshot) => Ft8LibInterop.CohFallbackMakePlan(snapshot);

    /// <inheritdoc/>
    public ICohFallbackWorker CreateWorker() => new LibWorker();

    private sealed class LibWorker : ICohFallbackWorker
    {
        private IntPtr _ctx = Ft8LibInterop.CohFallbackNewContext();
        private CohFallbackStatsNative _acc;

        public CohFallbackRow Process(float[] pcm, byte[] snapshot, int candidateIndex)
        {
            if (_ctx == IntPtr.Zero) throw new ObjectDisposedException(nameof(LibWorker));
            return Ft8LibInterop.CohFallbackProcess(_ctx, pcm, snapshot, candidateIndex, ref _acc);
        }

        public CohFallbackStats Accumulated => CohFallbackStats.From(in _acc);

        public void Dispose()
        {
            var ctx = _ctx;
            _ctx = IntPtr.Zero;
            if (ctx != IntPtr.Zero) Ft8LibInterop.CohFallbackFreeContext(ctx);
        }
    }
}
