"""HK-021 sibling (v): P(each row fires) at the Architect's OWN stated range.

ROW 1 fires iff CP95 upper <= 0.02 ; ROW 2 fires iff CP95 lower >= 0.05.
"""
from scipy.stats import beta, binom

N = 873  # removed set, primary corpus (20260803_live_run_1713)

def cp(k, n, a=0.05):
    lo = beta.ppf(a / 2, k, n - k + 1) if k > 0 else 0.0
    hi = beta.isf(a / 2, k + 1, n - k) if k < n else 1.0
    return lo, hi

# largest k that still fires ROW 1, smallest k that fires ROW 2
k_row1 = max(k for k in range(N) if cp(k, N)[1] <= 0.02)
k_row2 = min(k for k in range(N) if cp(k, N)[0] >= 0.05)
print(f"n = {N}")
print(f"ROW 1 fires iff k <= {k_row1}   (rate <= {k_row1/N:.5f}, CP hi = {cp(k_row1,N)[1]:.5f})")
print(f"   next k up: {k_row1+1} -> CP hi = {cp(k_row1+1,N)[1]:.5f}")
print(f"ROW 2 fires iff k >= {k_row2}   (rate >= {k_row2/N:.5f}, CP lo = {cp(k_row2,N)[0]:.5f})")
print()
print("true K   P(ROW 1)  P(ROW 2)  P(ROW 3)")
for p in (0.0, 0.0025, 0.005, 0.0075, 0.010, 0.015, 0.02, 0.03, 0.04, 0.06, 0.08):
    p1 = binom.cdf(k_row1, N, p)
    p2 = 1 - binom.cdf(k_row2 - 1, N, p)
    print(f"{p:6.4f}   {p1:7.3f}  {p2:8.3f}  {1-p1-p2:8.3f}")
