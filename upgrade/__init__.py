"""Governed AEGIS self-upgrade primitives."""

from .engine import SelfUpgradeEngine
from .models import UpgradePlan, UpgradeResult, UpgradeStage

__all__ = ["SelfUpgradeEngine", "UpgradePlan", "UpgradeResult", "UpgradeStage"]
