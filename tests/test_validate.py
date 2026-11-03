from conftest import AS_OF, risk

from airisk.validate import errors, validate


def messages(issues, level=None):
    return [f"{i.ref}: {i.message}" for i in issues if level is None or i.level == level]


def test_example_has_no_errors_and_expected_warnings(raw):
    issues = validate(raw, AS_OF)
    assert errors(issues) == []
    refs = {i.ref for i in issues}
    assert refs == {"AIR-006", "AIR-007.treatments[0]", "AIR-009"}


def test_unknown_system_is_error(raw):
    risk(raw, "AIR-001")["system"] = "SYS-999"
    assert any("unknown system" in m for m in messages(validate(raw, AS_OF), "error"))


def test_scores_must_be_1_to_5(raw):
    risk(raw, "AIR-001")["likelihood"] = 6
    risk(raw, "AIR-002")["impact"] = True  # bools are not scores
    errs = messages(validate(raw, AS_OF), "error")
    assert any("AIR-001" in m and "likelihood" in m for m in errs)
    assert any("AIR-002" in m and "impact" in m for m in errs)


def test_residual_cannot_exceed_inherent(raw):
    r = risk(raw, "AIR-004")
    r["residual_impact"] = 5
    assert any("cannot exceed" in m for m in messages(validate(raw, AS_OF), "error"))


def test_acceptance_required_above_appetite(raw):
    del risk(raw, "AIR-006")["acceptance"]
    assert any("requires an 'acceptance' block" in m for m in messages(validate(raw, AS_OF), "error"))


def test_expired_acceptance_is_error(raw):
    risk(raw, "AIR-006")["acceptance"]["expires"] = "2026-10-01"
    assert any("acceptance expired" in m for m in messages(validate(raw, AS_OF), "error"))


def test_acceptance_not_required_within_appetite(raw):
    r = risk(raw, "AIR-006")
    del r["acceptance"]
    r["likelihood"], r["impact"] = 3, 3  # score 9 == appetite
    assert errors(validate(raw, AS_OF)) == []


def test_mitigate_requires_treatments(raw):
    risk(raw, "AIR-002")["treatments"] = []
    assert any("no treatments are listed" in m for m in messages(validate(raw, AS_OF), "error"))


def test_framework_refs_validated(raw):
    t = risk(raw, "AIR-001")["treatments"][0]
    t["nist_ai_rmf"] = ["MEASURE 9", "measure 2"]
    t["iso_42001"] = ["A.11"]
    errs = messages(validate(raw, AS_OF), "error")
    assert sum("unknown NIST" in m for m in errs) == 2
    assert any("unknown ISO" in m for m in errs)


def test_subcategory_refs_are_accepted(raw):
    t = risk(raw, "AIR-001")["treatments"][0]
    t["nist_ai_rmf"] = ["GOVERN 1.6", "MAP 4.1"]
    t["iso_42001"] = ["A.6.2.4", "A.10.3"]
    assert errors(validate(raw, AS_OF)) == []


def test_review_cadence_follows_residual_rating(raw):
    # AIR-004 is Low (365 days). Reviewed 2026-06-10, so it is due 2027-06-10.
    assert not any(i.ref == "AIR-004" for i in validate(raw, AS_OF))
    assert any(i.ref == "AIR-004" and "overdue" in i.message
               for i in validate(raw, __import__("datetime").date(2027, 7, 1)))


def test_never_reviewed_is_warning(raw):
    del risk(raw, "AIR-002")["last_reviewed"]
    assert any(i.ref == "AIR-002" and "never been reviewed" in i.message for i in validate(raw, AS_OF))


def test_high_risk_system_needs_oversight(raw):
    raw["systems"][1]["human_oversight"] = ""
    assert any(i.ref == "SYS-002" and "human oversight" in i.message for i in validate(raw, AS_OF))


def test_prohibited_system_must_be_retired(raw):
    raw["systems"][2]["eu_ai_act_tier"] = "unacceptable"
    assert any(i.ref == "SYS-003" and "prohibited" in i.message for i in errors(validate(raw, AS_OF)))


def test_production_system_without_risks(raw):
    raw["risks"] = [r for r in raw["risks"] if r["system"] != "SYS-003"]
    assert any(i.ref == "SYS-003" and "no assessed risks" in i.message for i in validate(raw, AS_OF))


def test_duplicate_ids(raw):
    raw["risks"].append(dict(risk(raw, "AIR-001")))
    raw["governance"].append(dict(raw["governance"][0]))
    errs = messages(validate(raw, AS_OF), "error")
    assert any("duplicate risk id" in m for m in errs)
    assert any("duplicate governance control id" in m for m in errs)


def test_bad_config(raw):
    raw["config"]["bands"] = [{"label": "Low", "max": 10}]
    assert any(i.ref == "config" for i in errors(validate(raw, AS_OF)))
