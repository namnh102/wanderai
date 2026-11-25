"""D06.5 statistical inference: PCG64(20261105), B=10,000, BCa + degeneracy fallbacks, MC sign-flip, Holm K1..K5, Winner Gate."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.stats import norm

STAT_SEED: int = 20261105
DEFAULT_B: int = 10_000
EXHAUSTIVE_SIGN_FLIP_MAX_N: int = 16
WINNER_DELTA_MIN: float = 0.030


@dataclass(frozen=True)
class PairedStatsResult:
    n: int
    mean_delta: float
    percentile_ci_low: float
    percentile_ci_high: float
    bca_ci_low: float | None
    bca_ci_high: float | None
    ci_low: float
    ci_high: float
    ci_method: str
    p_mc: float
    test_method: str
    p0: float | None
    acceleration: float | None


@dataclass(frozen=True)
class ContrastEvaluation:
    contrast_id: str
    cell_a: str
    cell_b: str
    delta_min: float
    delta_max: float
    d_low_mean: float
    stats: PairedStatsResult
    p_mc_holm: float
    vis_span_delta: float | None
    fse_a: float | None
    fse_b: float | None
    decision: str
    flags: tuple[str, ...]
    bounds_non_identifying: bool


def paired_bootstrap_and_sign_flip(
    deltas: Sequence[float],
    *,
    seed: int = STAT_SEED,
    b_resamples: int = DEFAULT_B,
    allow_exhaustive_small_n: bool = True,
) -> PairedStatsResult:
    """Compute paired sign-flip p-value (MC for n>16, exhaustive 2^n only for n<=16) and 95% Percentile + BCa CIs."""
    arr = np.asarray(deltas, dtype=float)
    if arr.ndim != 1 or arr.size == 0:
        raise ValueError("deltas must be a non-empty 1D sequence")
    if not np.all(np.isfinite(arr)):
        raise ValueError("deltas must contain only finite floats")
    if b_resamples < 1:
        raise ValueError(f"b_resamples must be >= 1, got {b_resamples}")

    n = int(arr.size)
    obs_mean = float(np.mean(arr))

    # 1. Paired sign-flip randomization test
    if float(np.max(np.abs(arr))) <= 1e-12:
        p_mc = 1.0
        test_method = "DEGENERATE_ALL_ZERO"
    elif allow_exhaustive_small_n and n <= EXHAUSTIVE_SIGN_FLIP_MAX_N:
        # Exhaustive 2^n sign-flip enumeration only for small sub-analyses n <= 16
        bit_indices = np.arange(n, dtype=np.uint32)
        masks = np.arange(1 << n, dtype=np.uint32)[:, None]
        signs = (((masks >> bit_indices) & 1) * 2.0 - 1.0).astype(float)
        perm_means = (signs @ arr) / float(n)
        extreme_count = int(np.sum(np.abs(perm_means) >= abs(obs_mean) - 1e-12))
        p_mc = float(extreme_count / float(1 << n))
        test_method = "EXHAUSTIVE_SIGN_FLIP"
    else:
        rng_mc = np.random.Generator(np.random.PCG64(seed))
        signs = rng_mc.choice(np.array([-1.0, 1.0]), size=(b_resamples, n))
        perm_means = (signs @ arr) / float(n)
        extreme_count = int(np.sum(np.abs(perm_means) >= abs(obs_mean) - 1e-12))
        p_mc = float((1 + extreme_count) / float(b_resamples + 1))
        test_method = "MONTE_CARLO_SIGN_FLIP"

    # 2. Paired bootstrap 95% CI with BCa + exact degeneracy fallbacks
    if n == 1 or float(np.max(arr) - np.min(arr)) <= 1e-12:
        return PairedStatsResult(
            n=n,
            mean_delta=obs_mean,
            percentile_ci_low=obs_mean,
            percentile_ci_high=obs_mean,
            bca_ci_low=obs_mean,
            bca_ci_high=obs_mean,
            ci_low=obs_mean,
            ci_high=obs_mean,
            ci_method="DEGENERATE_CONSTANT",
            p_mc=p_mc,
            test_method=test_method,
            p0=None,
            acceleration=None,
        )

    rng_boot = np.random.Generator(np.random.PCG64(seed))
    boot_idx = rng_boot.integers(0, n, size=(b_resamples, n))
    boot_means = arr[boot_idx].mean(axis=1)

    pct_low = float(np.quantile(boot_means, 0.025))
    pct_high = float(np.quantile(boot_means, 0.975))
    p0 = float(np.mean(boot_means < obs_mean))

    # Leave-one-out jackknife for BCa acceleration constant a (scale-invariant)
    total_sum = float(np.sum(arr))
    jack_means = (total_sum - arr) / float(n - 1)
    jack_bar = float(np.mean(jack_means))
    d_vec = jack_bar - jack_means
    scale = float(np.max(np.abs(d_vec)))
    if scale > 0.0:
        d_norm = d_vec / scale
        ssq = float(np.sum(d_norm**2))
        denom = 6.0 * (ssq**1.5)
        sum_d3 = float(np.sum(d_norm**3))
    else:
        ssq = 0.0
        denom = 0.0
        sum_d3 = 0.0

    bca_low: float | None = None
    bca_high: float | None = None
    accel: float | None = None
    ci_method = "PERCENTILE_FALLBACK_BCA_UNDEFINED"
    ci_low = pct_low
    ci_high = pct_high

    if 0.0 < p0 < 1.0 and denom > 1e-15:
        z0 = float(norm.ppf(p0))
        a = sum_d3 / denom
        accel = a
        z_025 = float(norm.ppf(0.025))
        z_975 = float(norm.ppf(0.975))
        u_low = z0 + z_025
        u_high = z0 + z_975
        den_low = 1.0 - a * u_low
        den_high = 1.0 - a * u_high
        if den_low > 1e-12 and den_high > 1e-12:
            adj_low = float(norm.cdf(z0 + u_low / den_low))
            adj_high = float(norm.cdf(z0 + u_high / den_high))
            if 0.0 < adj_low < 1.0 and 0.0 < adj_high < 1.0 and adj_low <= adj_high:
                bca_low = float(np.quantile(boot_means, adj_low))
                bca_high = float(np.quantile(boot_means, adj_high))
                ci_method = "BCA_AND_PERCENTILE"
                ci_low = min(pct_low, bca_low)
                ci_high = max(pct_high, bca_high)

    return PairedStatsResult(
        n=n,
        mean_delta=obs_mean,
        percentile_ci_low=pct_low,
        percentile_ci_high=pct_high,
        bca_ci_low=bca_low,
        bca_ci_high=bca_high,
        ci_low=ci_low,
        ci_high=ci_high,
        ci_method=ci_method,
        p_mc=p_mc,
        test_method=test_method,
        p0=p0,
        acceleration=accel,
    )


def holm_bonferroni(p_values: Mapping[str, float]) -> dict[str, float]:
    """Step-down Holm-Bonferroni multiplicity adjustment."""
    if not p_values:
        return {}
    for k, p in p_values.items():
        if not isinstance(p, (int, float)) or isinstance(p, bool):
            raise ValueError(f"Invalid p-value for {k!r}: {p!r}")
        pf = float(p)
        if not math.isfinite(pf) or pf < 0.0 or pf > 1.0:
            raise ValueError(f"Out-of-range p-value for {k!r}: {p!r} (must be in [0.0, 1.0])")
    ordered = sorted(p_values.items(), key=lambda kv: float(kv[1]))
    m = len(ordered)
    adj: dict[str, float] = {}
    running_max = 0.0
    for i, (k, p) in enumerate(ordered):
        raw_adj = min(1.0, float(p) * (m - i))
        running_max = max(running_max, raw_adj)
        adj[k] = running_max
    return adj


def evaluate_winner_gate(
    contrast_id: str,
    cell_a: str,
    cell_b: str,
    *,
    delta_min: float,
    delta_max: float,
    d_low_vec: Sequence[float],
    stats_res: PairedStatsResult,
    p_mc_holm: float,
    vis_span_delta: float | None = None,
    fse_a: float | None = None,
    fse_b: float | None = None,
) -> ContrastEvaluation:
    """Apply the 4-part Annex G1.5 v0.2.1 D06.5 Winner & Non-Identification Gate."""
    flags: list[str] = []

    cond1_delta_min = delta_min >= WINNER_DELTA_MIN - 1e-12
    both_ci_gt_zero = stats_res.percentile_ci_low > 0.0 and (
        stats_res.bca_ci_low > 0.0 if stats_res.bca_ci_low is not None else True
    )
    cond2_stat = both_ci_gt_zero and (p_mc_holm < 0.05)
    cond3_vis = True if vis_span_delta is None else (vis_span_delta >= -1e-12)
    cond4_fse = True if (fse_a is None or fse_b is None) else (fse_a <= fse_b + 0.10 + 1e-12)

    if cond1_delta_min and cond2_stat and cond3_vis and cond4_fse:
        decision = "A_OVER_B"
        bounds_non_identifying = False
    else:
        decision = "NO_CLEAR_WINNER"
        bounds_non_identifying = bool(delta_min < WINNER_DELTA_MIN - 1e-12 <= delta_max + 1e-12)
        if bounds_non_identifying:
            flags.append("BOUNDS_NON_IDENTIFYING")

    return ContrastEvaluation(
        contrast_id=contrast_id,
        cell_a=cell_a,
        cell_b=cell_b,
        delta_min=float(delta_min),
        delta_max=float(delta_max),
        d_low_mean=sum(d_low_vec) / float(len(d_low_vec)),
        stats=stats_res,
        p_mc_holm=float(p_mc_holm),
        vis_span_delta=vis_span_delta,
        fse_a=fse_a,
        fse_b=fse_b,
        decision=decision,
        flags=tuple(flags),
        bounds_non_identifying=bounds_non_identifying,
    )
