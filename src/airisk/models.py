"""Register data model. Built only from data that has passed validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

DEFAULT_CONFIG = {
    "organization": "Example Organization",
    "risk_appetite": 9,
    "bands": [
        {"label": "Low", "max": 4},
        {"label": "Medium", "max": 9},
        {"label": "High", "max": 15},
        {"label": "Critical", "max": 25},
    ],
    "review_days": {"Low": 365, "Medium": 180, "High": 90, "Critical": 30},
}


def as_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


@dataclass
class Config:
    organization: str
    risk_appetite: int
    bands: list[dict]
    review_days: dict[str, int]

    @classmethod
    def from_raw(cls, raw: dict | None) -> "Config":
        merged = {**DEFAULT_CONFIG, **(raw or {})}
        bands = sorted(merged["bands"], key=lambda b: b["max"])
        if bands[-1]["max"] < 25:
            raise ValueError("the highest band must cover a score of 25")
        missing = [b["label"] for b in bands if b["label"] not in merged["review_days"]]
        if missing:
            raise ValueError(f"review_days has no entry for band(s): {', '.join(missing)}")
        return cls(merged["organization"], int(merged["risk_appetite"]), bands, merged["review_days"])

    def rating(self, score: int) -> str:
        for band in self.bands:
            if score <= band["max"]:
                return band["label"]
        return self.bands[-1]["label"]


@dataclass
class Control:
    """A risk treatment, or an organization-level governance control."""

    description: str
    status: str  # planned | in_progress | implemented
    nist_ai_rmf: list[str] = field(default_factory=list)
    iso_42001: list[str] = field(default_factory=list)
    due: date | None = None
    id: str | None = None
    owner: str | None = None

    @classmethod
    def from_raw(cls, raw: dict) -> "Control":
        return cls(
            description=raw["description"],
            status=raw["status"],
            nist_ai_rmf=[str(x) for x in raw.get("nist_ai_rmf", [])],
            iso_42001=[str(x) for x in raw.get("iso_42001", [])],
            due=as_date(raw.get("due")),
            id=raw.get("id"),
            owner=raw.get("owner"),
        )

    @property
    def implemented(self) -> bool:
        return self.status == "implemented"


@dataclass
class System:
    id: str
    name: str
    owner: str
    lifecycle_stage: str
    eu_ai_act_tier: str | None
    description: str = ""
    model_source: str = ""
    human_oversight: str = ""
    data_categories: list[str] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: dict) -> "System":
        return cls(
            id=raw["id"], name=raw["name"], owner=raw["owner"],
            lifecycle_stage=raw["lifecycle_stage"], eu_ai_act_tier=raw.get("eu_ai_act_tier"),
            description=raw.get("description", ""), model_source=raw.get("model_source", ""),
            human_oversight=raw.get("human_oversight", ""),
            data_categories=list(raw.get("data_categories", [])),
        )


@dataclass
class Acceptance:
    approver: str
    date: date
    expires: date
    rationale: str = ""


@dataclass
class Risk:
    id: str
    system: str
    title: str
    category: str
    owner: str
    likelihood: int
    impact: int
    residual_likelihood: int
    residual_impact: int
    treatment: str  # mitigate | accept | transfer | avoid
    treatments: list[Control]
    description: str = ""
    acceptance: Acceptance | None = None
    last_reviewed: date | None = None

    @classmethod
    def from_raw(cls, raw: dict) -> "Risk":
        acc = raw.get("acceptance")
        return cls(
            id=raw["id"], system=raw["system"], title=raw["title"], category=raw["category"],
            owner=raw["owner"], likelihood=raw["likelihood"], impact=raw["impact"],
            residual_likelihood=raw.get("residual_likelihood", raw["likelihood"]),
            residual_impact=raw.get("residual_impact", raw["impact"]),
            treatment=raw["treatment"],
            treatments=[Control.from_raw(t) for t in raw.get("treatments", [])],
            description=raw.get("description", ""),
            acceptance=Acceptance(acc["approver"], as_date(acc["date"]), as_date(acc["expires"]),
                                  acc.get("rationale", "")) if acc else None,
            last_reviewed=as_date(raw.get("last_reviewed")),
        )

    @property
    def inherent_score(self) -> int:
        return self.likelihood * self.impact

    @property
    def residual_score(self) -> int:
        return self.residual_likelihood * self.residual_impact


@dataclass
class Register:
    config: Config
    systems: dict[str, System]
    risks: list[Risk]
    governance: list[Control]

    def next_review(self, risk: Risk) -> date | None:
        if risk.last_reviewed is None:
            return None
        days = self.config.review_days[self.config.rating(risk.residual_score)]
        return risk.last_reviewed + timedelta(days=days)

    def review_overdue(self, risk: Risk, as_of: date) -> bool:
        nxt = self.next_review(risk)
        return nxt is None or nxt < as_of

    def above_appetite(self, risk: Risk) -> bool:
        return risk.residual_score > self.config.risk_appetite

    def risks_for(self, system_id: str) -> list[Risk]:
        return [r for r in self.risks if r.system == system_id]

    def all_controls(self) -> list[tuple[str, Control]]:
        """(source, control) pairs: risk treatments plus governance controls."""
        pairs = [(r.id, t) for r in self.risks for t in r.treatments]
        pairs += [(g.id or "governance", g) for g in self.governance]
        return pairs
