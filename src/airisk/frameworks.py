"""Framework catalogs and reference parsing."""

from __future__ import annotations

import re
from functools import lru_cache
from importlib import resources

import yaml

# NIST AI RMF trustworthy characteristics, used as risk categories.
CATEGORIES = {
    "valid_reliable": "Valid and reliable",
    "safe": "Safe",
    "secure_resilient": "Secure and resilient",
    "accountable_transparent": "Accountable and transparent",
    "explainable_interpretable": "Explainable and interpretable",
    "privacy_enhanced": "Privacy-enhanced",
    "fair_bias_managed": "Fair, with harmful bias managed",
}

EU_AI_ACT_TIERS = {
    "unacceptable": "Prohibited practice",
    "high": "High-risk",
    "limited": "Limited risk (transparency obligations)",
    "minimal": "Minimal risk",
}

_NIST_RE = re.compile(r"^(GOVERN|MAP|MEASURE|MANAGE) (\d+)(\.\d+)?$")
_ISO_RE = re.compile(r"^A\.(\d+)((\.\d+)*)$")


@lru_cache(maxsize=None)
def _load(name: str) -> dict:
    return yaml.safe_load(resources.files("airisk").joinpath(f"data/{name}").read_text())


def nist_categories() -> dict[str, str]:
    return _load("nist_ai_rmf.yaml")["categories"]


def iso_objectives() -> dict[str, str]:
    return _load("iso_42001.yaml")["objectives"]


def nist_category(ref: str) -> str | None:
    """'MEASURE 2.7' -> 'MEASURE 2'; None if not a known category."""
    m = _NIST_RE.match(str(ref).strip())
    if not m:
        return None
    cat = f"{m.group(1)} {m.group(2)}"
    return cat if cat in nist_categories() else None


def iso_objective(ref: str) -> str | None:
    """'A.6.2.4' -> 'A.6'; None if not a known objective."""
    m = _ISO_RE.match(str(ref).strip())
    if not m:
        return None
    obj = f"A.{m.group(1)}"
    return obj if obj in iso_objectives() else None
