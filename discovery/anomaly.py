"""Anomaly and contradiction detection for scientific discovery."""
from __future__ import annotations

from collections import defaultdict
from statistics import mean, pstdev
from typing import Iterable

from .models import Anomaly, AnomalyKind, Evidence, new_id


def detect_numeric_outliers(values: dict[str, float], *, z_threshold: float = 3.0) -> tuple[Anomaly, ...]:
    if len(values) < 3:
        return ()
    xs = list(values.values())
    sd = pstdev(xs)
    if sd == 0:
        return ()
    mu = mean(xs)
    result = []
    for key, value in values.items():
        z = abs((value - mu) / sd)
        if z >= z_threshold:
            result.append(Anomaly(
                new_id("anomaly"), AnomalyKind.OUTLIER,
                f"{key} is an outlier with absolute z-score {z:.3f}", "medium", (key,)
            ))
    return tuple(result)


def detect_contradictions(evidence: Iterable[Evidence]) -> tuple[Anomaly, ...]:
    """Find claims supported by incompatible observations from independent groups."""
    groups: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    records = list(evidence)
    for item in records:
        groups[item.claim][item.independent_group].add(str(item.data.get("value", item.data.get("result", ""))))
    anomalies = []
    for claim, by_group in groups.items():
        values = {value for vals in by_group.values() for value in vals if value}
        if len(values) > 1 and len(by_group) > 1:
            ids = tuple(item.evidence_id for item in records if item.claim == claim)
            anomalies.append(Anomaly(
                new_id("anomaly"), AnomalyKind.CONTRADICTION,
                f"Independent evidence conflicts for claim: {claim}", "high", (), ids
            ))
    return tuple(anomalies)


def detect_expectation_mismatch(expected: float, observed: float, tolerance: float, *, related_id: str = "") -> Anomaly | None:
    if abs(observed - expected) <= tolerance:
        return None
    return Anomaly(
        new_id("anomaly"), AnomalyKind.EXPECTATION_MISMATCH,
        f"Observed value {observed} differs from expected {expected} beyond tolerance {tolerance}",
        "medium", (related_id,) if related_id else ()
    )
