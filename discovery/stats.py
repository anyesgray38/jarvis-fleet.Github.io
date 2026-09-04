"""Dependency-free statistical helpers for discovery experiments.

These routines are intentionally conservative. They provide descriptive statistics
and a deterministic permutation test primitive; domain-specific scientific claims
still require appropriate experimental design and independent verification.
"""
from __future__ import annotations

import math
import random
from statistics import mean as _mean, median, pstdev
from typing import Sequence


def mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("values must not be empty")
    return float(_mean(values))


def summarize_samples(values: Sequence[float]) -> dict[str, float | int]:
    if not values:
        raise ValueError("values must not be empty")
    data = [float(x) for x in values]
    return {
        "n": len(data),
        "mean": float(_mean(data)),
        "median": float(median(data)),
        "population_stddev": float(pstdev(data)),
        "min": min(data),
        "max": max(data),
    }


def permutation_p_value(
    left: Sequence[float],
    right: Sequence[float],
    *,
    permutations: int = 2000,
    seed: int = 0,
) -> float:
    """Two-sided permutation p-value for a difference in means.

    This is a screening statistic, not a substitute for domain-appropriate inference.
    Inputs must be independent samples for the interpretation used here.
    """
    if not left or not right:
        raise ValueError("both samples must be non-empty")
    if permutations < 100:
        raise ValueError("permutations must be >= 100")
    a = [float(x) for x in left]
    b = [float(x) for x in right]
    observed = abs(_mean(a) - _mean(b))
    pooled = a + b
    n_a = len(a)
    rng = random.Random(seed)
    extreme = 0
    for _ in range(permutations):
        rng.shuffle(pooled)
        delta = abs(_mean(pooled[:n_a]) - _mean(pooled[n_a:]))
        if delta >= observed:
            extreme += 1
    return (extreme + 1) / (permutations + 1)


def standardized_difference(left: Sequence[float], right: Sequence[float]) -> float:
    """Return a simple standardized mean difference (pooled population SD)."""
    if not left or not right:
        raise ValueError("both samples must be non-empty")
    a, b = [float(x) for x in left], [float(x) for x in right]
    va, vb = pstdev(a), pstdev(b)
    pooled = math.sqrt((va * va + vb * vb) / 2)
    if pooled == 0:
        return 0.0 if _mean(a) == _mean(b) else math.inf
    return (_mean(a) - _mean(b)) / pooled
