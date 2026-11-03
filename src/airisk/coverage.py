"""Framework coverage: which NIST AI RMF categories and ISO/IEC 42001 objectives
are addressed by implemented or planned controls in the register."""

from __future__ import annotations

from dataclasses import dataclass, field

from .frameworks import iso_objective, iso_objectives, nist_categories, nist_category
from .models import Register

COVERED, PLANNED, GAP = "Covered", "Planned", "Gap"


@dataclass
class CoverageRow:
    ref: str
    title: str
    implemented: list[str] = field(default_factory=list)  # sources (risk or control ids)
    planned: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.implemented:
            return COVERED
        return PLANNED if self.planned else GAP


def _build(catalog: dict[str, str], normalize, refs_of, register: Register) -> list[CoverageRow]:
    rows = {k: CoverageRow(k, v) for k, v in catalog.items()}
    for source, control in register.all_controls():
        for ref in {normalize(x) for x in refs_of(control)} - {None}:
            bucket = rows[ref].implemented if control.implemented else rows[ref].planned
            if source not in bucket:
                bucket.append(source)
    return list(rows.values())


def nist_coverage(register: Register) -> list[CoverageRow]:
    return _build(nist_categories(), nist_category, lambda c: c.nist_ai_rmf, register)


def iso_coverage(register: Register) -> list[CoverageRow]:
    return _build(iso_objectives(), iso_objective, lambda c: c.iso_42001, register)


def summary(rows: list[CoverageRow]) -> dict[str, int]:
    out = {COVERED: 0, PLANNED: 0, GAP: 0}
    for r in rows:
        out[r.status] += 1
    return out
