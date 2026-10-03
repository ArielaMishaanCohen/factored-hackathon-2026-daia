import copy
import json
from pathlib import Path

import duckdb
import pytest

from eval.baselines.status_quo import build
from eval.impacto import project
from eval.graders_handoff import grade_handoff

ROOT = Path(__file__).resolve().parents[1]


def metrics():
    return json.loads((ROOT / "analysis/metricas_problema.json").read_text(encoding="utf-8"))


def test_weighted_fcr_and_median():
    data = metrics()
    data["call_center_by_category"] = [dict(reason_category="Queja", fcr_numerator=1, fcr_denominator=2),
                                       dict(reason_category="Otro", fcr_numerator=9, fcr_denominator=10)]
    result = build(data)["metrics"]
    assert result["fcr_global"]["value"] == pytest.approx(10 / 12)
    assert result["dispute_resolution_median_days"]["numerator"] is None


def test_impact_bounds_and_period():
    data = metrics()
    result = project(data, .35, .3, .4)
    assert result["annual_disputes"]["denominator"] == 1097
    assert result["scenarios"]["central"]["agent_hours_saved"] == pytest.approx(344.3134052601757)
    assert project(data, 0, 0, 0)["scenarios"]["central"]["agent_hours_saved"] == 0
    assert result["historical_followup"]["union"] is None
    data["call_center_by_category"][2]["duration_denominator"] = 0
    assert project(data, .35, .3, .4)["scenarios"]["central"]["agent_hours_saved"] is None


@pytest.mark.parametrize("rates", [(-.1, 0, .4), (.4, .5, .6), (.5, 0, 1.1), (float("nan"), 0, 1)])
def test_invalid_rates(rates):
    with pytest.raises(ValueError):
        project(metrics(), *rates)


@pytest.fixture
def handoff(tmp_path):
    gold = tmp_path / "gold.duckdb"
    with duckdb.connect(str(gold)) as db:
        db.execute("CREATE TABLE customer_profile AS SELECT 'C1' customer_id, 'Basic' segment, 'Colombia' country, 0 prior_complaints_90d")
        db.execute("CREATE TABLE dispute_transactions AS SELECT 'T1' transaction_id, 'C1' customer_id, 'P1' product_id, 10.25 amount, 'USD' currency, DATE '2026-06-10' business_date, NULL::DOUBLE fraud_score")
        db.execute("CREATE TABLE cards AS SELECT 'P1' product_id, 'C1' customer_id, 'Active' status")
    h = dict(handoff_id="H1", case_id="D1", created_at="2026-10-01T12:00:00Z", handoff_reason="POLICY_ESCALATION",
             priority="high", sla_due_at="2026-10-04T12:00:00+00:00", language="es",
             customer=dict(customer_id="C1", segment="Basic", country="Colombia"), original_request="Reclamo", summary="Disputa",
             verified_facts=[dict(fact=k, value=v, source="transactions") for k, v in
                             [("transaction_id", "T1"), ("amount", "10.25 USD"), ("business_date", "2026-06-10"), ("fraud_score", "nulo")]]
                            + [dict(fact="case_id", value="D1", source="cases")],
             policy_decision=dict(rule_id="R8", action="ESCALATE", reason="Sin score", priority="high", queue="disputas", policy_version="1.3.0"),
             actions_taken=[], actions_declined=[], open_questions=[], suggested_queue="disputas", suggested_agent_language="es", conversation_id="V1", trace_id="TR1")
    cases = [dict(case_id="D1", customer_id="C1", transaction_id="T1", priority="high", sla_due_at="2026-10-04T12:00:00Z")]
    return h, cases, gold


def test_handoff_valid_and_iso_equivalent(handoff):
    h, cases, gold = handoff
    assert all(g["verdict"] == "pass" for g in grade_handoff(h, "dev-fixture", cases=cases, expected_customer_id="C1", gold_path=gold))


@pytest.mark.parametrize("change", ["amount", "owner", "missing", "source", "case"])
def test_handoff_tampering(handoff, change):
    h, cases, gold = copy.deepcopy(handoff)
    if change == "amount": h["verified_facts"][1]["value"] = "10.25 COP"
    if change == "owner": h["customer"]["customer_id"] = "C2"
    if change == "missing": h["verified_facts"] = h["verified_facts"][:1]
    if change == "source": h["verified_facts"][1]["source"] = "complaints"
    if change == "case": cases = []
    assert any(g["verdict"] in ("fail", "grader_error") for g in grade_handoff(h, "dev-fixture", cases=cases, expected_customer_id="C1", gold_path=gold))


def test_operational_context_cannot_be_claimed_verified(handoff):
    h, _, gold = handoff
    assert any(g["verdict"] == "grader_error" for g in grade_handoff(h, "dev-fixture", gold_path=gold))
