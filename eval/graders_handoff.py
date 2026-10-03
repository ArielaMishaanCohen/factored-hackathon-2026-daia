"""Hechos del handoff contrastados con gold y, para casos, con el resultado operativo."""
from datetime import date, datetime
from math import isclose
from pathlib import Path

import duckdb
from eval.formato import HandoffPackage

GOLD = Path(__file__).resolve().parents[1] / "data/gold/gold.duckdb"
GRADER_VERSION = "handoff-1.0.0"


def _dict(value):
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


def _equal(a, b):
    if b is None:
        return a is None or a in ("nulo", "null")
    if isinstance(b, (date, datetime)):
        b = b.isoformat()
    if isinstance(b, (int, float)) and not isinstance(a, bool):
        try:
            return isclose(float(a), b, rel_tol=0, abs_tol=1e-6)
        except (ValueError, TypeError):
            return False
    return a == b


def grade_handoff(handoff, case_id: str, *, cases=None, expected_customer_id=None, gold_path=GOLD) -> list[dict]:
    """case_id identifica el caso de evaluación, no el DSP operativo.

    Sin contexto operativo, un hecho cases queda grader_error, nunca un pase falso.
    No importa el estado global del backend ni ejecuta SQL procedente de un hecho.
    """
    out = []

    def check(field, expected, observed, *, verdict=None, detail=None):
        out.append(dict(field=field, expected=expected, observed=observed,
                        verdict=verdict or ("pass" if _equal(observed, expected) else "fail"),
                        evidence=f"{case_id}: {field}", detail=detail))

    raw = _dict(handoff)
    missing = sorted(set(HandoffPackage.model_fields) - raw.keys())
    check("required_fields", [], missing)
    try:
        h = HandoffPackage.model_validate(raw)
    except Exception as error:
        check("schema", "HandoffPackage válido", type(error).__name__, verdict="fail")
        return out
    for field in ("handoff_id", "original_request", "summary", "conversation_id", "trace_id"):
        check(field + ".nonempty", True, bool(getattr(h, field).strip()))
    check("agent_language", h.language, h.suggested_agent_language)
    if expected_customer_id is not None:
        check("customer.session_owner", expected_customer_id, h.customer.customer_id)
    with duckdb.connect(str(gold_path), read_only=True) as db:
        def row(table, key, value):
            # table/key are constants from this module, values are always parameters.
            cur = db.execute(f"SELECT * FROM {table} WHERE {key} = ?", [value])
            result = cur.fetchone()
            return dict(zip([x[0] for x in cur.description], result)) if result else None

        profile = row("customer_profile", "customer_id", h.customer.customer_id)
        check("customer.exists", True, profile is not None)
        if profile:
            for field in ("segment", "country"):
                check("customer." + field, profile[field], getattr(h.customer, field))
        ids = [f.value for f in h.verified_facts if f.source == "transactions" and f.fact == "transaction_id"]
        needs_tx = h.policy_decision is not None or any(f.source in ("transactions", "cards") for f in h.verified_facts)
        check("transaction.anchor_count", 1 if needs_tx else 0, len(ids))
        tx = row("dispute_transactions", "transaction_id", ids[0]) if len(ids) == 1 else None
        if needs_tx:
            check("transaction.exists", True, tx is not None)
        if tx:
            check("transaction.owner", h.customer.customer_id, tx["customer_id"])
            present = {f.fact for f in h.verified_facts if f.source == "transactions"}
            check("transaction.required_facts", [], sorted({"transaction_id", "amount", "business_date"} - present))
        card = row("cards", "product_id", tx["product_id"]) if tx else None
        operational = {c["case_id"]: c for c in map(_dict, cases or [])}
        case = operational.get(h.case_id)
        if h.case_id:
            check("case.exists", True, case is not None,
                  verdict="grader_error" if cases is None else None,
                  detail="Requiere res.cases; gold no contiene casos operativos." if cases is None else None)
            if case:
                check("case.owner", h.customer.customer_id, case["customer_id"])
                check("case.transaction", tx["transaction_id"] if tx else None, case["transaction_id"])
                check("case.priority", case["priority"], h.priority)
                expected_sla = datetime.fromisoformat(case["sla_due_at"])
                check("case.sla", True, expected_sla == h.sla_due_at)
            check("case.required_fact", True, any(f.source == "cases" and f.fact == "case_id" for f in h.verified_facts))
        if h.policy_decision:
            if h.policy_decision.priority:
                check("policy.priority", h.policy_decision.priority, h.priority)
            check("policy.queue", h.policy_decision.queue or "disputas", h.suggested_queue)
        seen = set()
        for i, fact in enumerate(h.verified_facts):
            field = f"verified_facts[{i}].{fact.source}.{fact.fact}"
            key = (fact.source, fact.fact)
            if key in seen:
                check(field, "hecho único", fact.value, verdict="fail")
                continue
            seen.add(key)
            source = {"transactions": tx, "cards": card, "customer_profile": profile, "cases": case}.get(fact.source)
            if fact.source == "cards" and fact.fact == "status":
                check(field, "estado operativo", fact.value, verdict="grader_error",
                      detail="Gold refleja estado inicial; verificar bloqueo requiere resultado operativo de tarjeta.")
            elif fact.source == "transactions" and fact.fact == "amount" and tx:
                check(field, f"{tx['amount']:.2f} {tx['currency']}", fact.value)
            elif source is not None and fact.fact in source:
                check(field, source[fact.fact], fact.value)
            else:
                check(field, "fuente y campo verificables", fact.value, verdict="grader_error",
                      detail="Fuente ausente o campo no soportado; no se considera verificado.")
    return out
