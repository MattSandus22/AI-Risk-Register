"""Validation rules for the register.

Errors make the register unusable (bad data, broken governance rules).
Warnings are governance findings a reviewer should act on.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta

from .frameworks import CATEGORIES, EU_AI_ACT_TIERS, iso_objective, nist_category
from .models import Config, as_date

LIFECYCLE = ("design", "development", "validation", "production", "retired")
TREATMENT_TYPES = ("mitigate", "accept", "transfer", "avoid")
CONTROL_STATUS = ("planned", "in_progress", "implemented")
SYSTEM_REQUIRED = ("id", "name", "owner", "lifecycle_stage")
RISK_REQUIRED = ("id", "system", "title", "category", "owner", "likelihood", "impact", "treatment")


@dataclass(frozen=True)
class Issue:
    level: str  # "error" | "warning"
    ref: str
    message: str

    def __str__(self) -> str:
        return f"{self.level.upper():7} {self.ref}: {self.message}"


class _Collector:
    def __init__(self):
        self.issues: list[Issue] = []

    def error(self, ref: str, msg: str):
        self.issues.append(Issue("error", ref, msg))

    def warn(self, ref: str, msg: str):
        self.issues.append(Issue("warning", ref, msg))


def _parse_date(c: _Collector, ref: str, field: str, value) -> date | None:
    try:
        return as_date(value)
    except (ValueError, TypeError):
        c.error(ref, f"'{field}' must be a date (YYYY-MM-DD), got {value!r}")
        return None


def _validate_control(c: _Collector, ref: str, t: dict, as_of: date) -> None:
    if not isinstance(t, dict):
        c.error(ref, "must be a mapping")
        return
    if not t.get("description"):
        c.error(ref, "missing required field 'description'")
    if t.get("status") not in CONTROL_STATUS:
        c.error(ref, f"'status' must be one of {', '.join(CONTROL_STATUS)}")
    for r in t.get("nist_ai_rmf", []):
        if nist_category(r) is None:
            c.error(ref, f"unknown NIST AI RMF reference '{r}' (expected e.g. 'MEASURE 2' or 'MEASURE 2.7')")
    for r in t.get("iso_42001", []):
        if iso_objective(r) is None:
            c.error(ref, f"unknown ISO/IEC 42001 reference '{r}' (expected A.2 to A.10, e.g. 'A.6.2.4')")
    if not t.get("nist_ai_rmf") and not t.get("iso_42001"):
        c.warn(ref, "not mapped to any framework reference")
    due = _parse_date(c, ref, "due", t.get("due"))
    if due and t.get("status") != "implemented" and due < as_of:
        c.warn(ref, f"treatment overdue (due {due}, status {t.get('status')})")


def _is_score(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 5


def validate(raw: dict, as_of: date | None = None) -> list[Issue]:
    as_of = as_of or date.today()
    c = _Collector()

    try:
        cfg = Config.from_raw(raw.get("config"))
    except (ValueError, KeyError, TypeError) as exc:
        c.error("config", f"invalid configuration: {exc}")
        return c.issues

    # --- systems ---------------------------------------------------------------
    systems: dict[str, dict] = {}
    for i, s in enumerate(raw.get("systems", [])):
        ref = (s.get("id") if isinstance(s, dict) else None) or f"systems[{i}]"
        if not isinstance(s, dict):
            c.error(ref, "must be a mapping")
            continue
        for f in SYSTEM_REQUIRED:
            if not s.get(f):
                c.error(ref, f"missing required field '{f}'")
        if s.get("id") in systems:
            c.error(ref, "duplicate system id")
        if s.get("lifecycle_stage") and s["lifecycle_stage"] not in LIFECYCLE:
            c.error(ref, f"'lifecycle_stage' must be one of {', '.join(LIFECYCLE)}")
        tier = s.get("eu_ai_act_tier")
        if tier is not None and tier not in EU_AI_ACT_TIERS:
            c.error(ref, f"'eu_ai_act_tier' must be one of {', '.join(EU_AI_ACT_TIERS)}")
        if tier == "unacceptable" and s.get("lifecycle_stage") != "retired":
            c.error(ref, "system is classified as a prohibited practice but is not retired")
        if tier == "high" and not s.get("human_oversight"):
            c.warn(ref, "high-risk system has no documented human oversight")
        if s.get("id"):
            systems[s["id"]] = s

    # --- risks -------------------------------------------------------------------
    seen: set[str] = set()
    per_system: Counter = Counter()
    for i, r in enumerate(raw.get("risks", [])):
        ref = (r.get("id") if isinstance(r, dict) else None) or f"risks[{i}]"
        if not isinstance(r, dict):
            c.error(ref, "must be a mapping")
            continue
        for f in RISK_REQUIRED:
            if r.get(f) in (None, ""):
                c.error(ref, f"missing required field '{f}'")
        if r.get("id") in seen:
            c.error(ref, "duplicate risk id")
        seen.add(r.get("id"))
        if r.get("system"):
            if r["system"] in systems:
                per_system[r["system"]] += 1
            else:
                c.error(ref, f"references unknown system '{r['system']}'")
        if r.get("category") and r["category"] not in CATEGORIES:
            c.error(ref, f"'category' must be one of {', '.join(CATEGORIES)}")
        if r.get("treatment") and r["treatment"] not in TREATMENT_TYPES:
            c.error(ref, f"'treatment' must be one of {', '.join(TREATMENT_TYPES)}")

        treatments = r.get("treatments") or []
        for j, t in enumerate(treatments):
            _validate_control(c, f"{ref}.treatments[{j}]", t, as_of)
        if r.get("treatment") == "mitigate" and not treatments:
            c.error(ref, "treatment is 'mitigate' but no treatments are listed")

        bad_scores = False
        for f in ("likelihood", "impact", "residual_likelihood", "residual_impact"):
            v = r.get(f)
            if v is None and f.startswith("residual"):
                continue
            if v is not None and not _is_score(v):
                c.error(ref, f"'{f}' must be an integer from 1 to 5, got {v!r}")
                bad_scores = True
        if bad_scores or not (_is_score(r.get("likelihood")) and _is_score(r.get("impact"))):
            continue

        lik, imp = r["likelihood"], r["impact"]
        rlik, rimp = r.get("residual_likelihood", lik), r.get("residual_impact", imp)
        inherent, residual = lik * imp, rlik * rimp
        if rlik > lik or rimp > imp:
            c.error(ref, "residual likelihood/impact cannot exceed inherent ratings")

        implemented = [t for t in treatments if isinstance(t, dict) and t.get("status") == "implemented"]
        if residual < inherent and not implemented:
            c.warn(ref, f"residual score ({residual}) is below inherent ({inherent}) "
                        "but no treatment is implemented; the reduction is not yet supported")

        if residual > cfg.risk_appetite and r.get("treatment") == "accept":
            acc = r.get("acceptance")
            if not isinstance(acc, dict):
                c.error(ref, f"residual score {residual} exceeds risk appetite ({cfg.risk_appetite}); "
                             "accepting it requires an 'acceptance' block (approver, date, expires)")
            else:
                for f in ("approver", "date", "expires"):
                    if not acc.get(f):
                        c.error(ref, f"acceptance is missing '{f}'")
                exp = _parse_date(c, ref, "acceptance.expires", acc.get("expires"))
                if exp and exp < as_of:
                    c.error(ref, f"risk acceptance expired on {exp}; re-approve or treat the risk")

        reviewed = _parse_date(c, ref, "last_reviewed", r.get("last_reviewed"))
        if r.get("last_reviewed") is None:
            c.warn(ref, "has never been reviewed")
        elif reviewed:
            rating = cfg.rating(residual)
            due = reviewed + timedelta(days=cfg.review_days[rating])
            if due < as_of:
                c.warn(ref, f"review overdue: {rating} risks are reviewed every "
                            f"{cfg.review_days[rating]} days; last reviewed {reviewed}, due {due}")

    for sid, s in systems.items():
        if s.get("lifecycle_stage") == "production" and per_system[sid] == 0:
            c.warn(sid, "system is in production but has no assessed risks")

    # --- governance controls -----------------------------------------------------
    gov_ids: set[str] = set()
    for i, g in enumerate(raw.get("governance", [])):
        ref = (g.get("id") if isinstance(g, dict) else None) or f"governance[{i}]"
        if isinstance(g, dict):
            if not g.get("id"):
                c.error(ref, "missing required field 'id'")
            elif g["id"] in gov_ids:
                c.error(ref, "duplicate governance control id")
            gov_ids.add(g.get("id"))
        _validate_control(c, ref, g, as_of)

    return c.issues


def errors(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.level == "error"]
