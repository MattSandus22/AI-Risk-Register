from conftest import AS_OF, EXAMPLE

from airisk.cli import main
from airisk.coverage import GAP, iso_coverage, nist_coverage
from airisk.loader import build
from airisk.report import build_view, to_csv, to_html, to_markdown
from airisk.validate import validate


def test_scoring_and_ratings(raw):
    reg = build(raw)
    r = next(x for x in reg.risks if x.id == "AIR-001")
    assert (r.inherent_score, r.residual_score) == (20, 10)
    assert reg.config.rating(r.inherent_score) == "Critical"
    assert reg.config.rating(r.residual_score) == "High"
    assert reg.above_appetite(r)


def test_residual_defaults_to_inherent(raw):
    r = next(x for x in build(raw).risks if x.id == "AIR-006")
    assert r.residual_score == r.inherent_score == 12


def test_coverage_counts_governance_and_treatments(raw):
    reg = build(raw)
    nist = {row.ref: row for row in nist_coverage(reg)}
    assert nist["GOVERN 1"].implemented == ["GOV-001"]
    assert set(nist["GOVERN 6"].planned) == {"AIR-007", "AIR-009"}
    assert nist["GOVERN 5"].status == GAP
    # subcategory MEASURE 2.11 rolls up to MEASURE 2
    assert "AIR-005" in nist["MEASURE 2"].implemented
    iso = {row.ref: row for row in iso_coverage(reg)}
    assert "AIR-007" in iso["A.10"].planned  # A.10.3 rolls up to A.10


def test_reports_render(raw):
    view = build_view(build(raw), validate(raw, AS_OF), AS_OF)
    assert [r.risk.id for r in view.rows][:2] == ["AIR-005", "AIR-006"]  # sorted by residual
    md, page, csv = to_markdown(view), to_html(view), to_csv(view)
    assert "AIR-005" in md and "NIST AI RMF coverage" in md
    assert page.startswith("<!doctype html>") and "prefers-color-scheme" in page
    assert len(csv.strip().splitlines()) == 1 + len(view.rows)


def test_html_escapes_user_content(raw):
    raw["risks"][0]["title"] = "<script>alert(1)</script>"
    page = to_html(build_view(build(raw), [], AS_OF))
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


def test_cli(tmp_path):
    assert main(["validate", str(EXAMPLE), "--as-of", "2026-11-03"]) == 0
    assert main(["validate", str(EXAMPLE), "--as-of", "2026-11-03", "--strict"]) == 1
    out = tmp_path / "r.html"
    assert main(["report", str(EXAMPLE), "--as-of", "2026-11-03", "-o", str(out)]) == 0
    assert "AI Risk Register" in out.read_text()
    assert main(["coverage", str(EXAMPLE), "--as-of", "2026-11-03"]) == 0
    assert main(["validate", str(tmp_path)]) == 2  # no systems.yaml
