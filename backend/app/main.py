"""API de LATAM Bank · intake de disputas (design.md, sección 6)."""
from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends, FastAPI, Header
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .auth import get_session, issue_token, require_role
from .config import get_policy, get_settings
from . import faults
from .errors import APIError, register_error_handlers
from .nlu.classifier import get_classifier
from .orchestrator import handle_chat
from .schemas import (AgentLoginRequest, CasesResponse, ChatRequest, ChatResponse, DemoCustomer,
                      DemoCustomersResponse, HandoffPackage, HandoffsResponse, HandoffSummary,
                      HealthResponse, LoginCustomer, LoginRequest, LoginResponse, Session, Trace)
from .store import flush, store
from .tools import data_source

app = FastAPI(title="LATAM Bank · Disputas", version="0.1.0")
register_error_handlers(app)


@app.middleware("http")
async def _persist_after_request(request, call_next):
    """Al terminar cada petición a la API, guardar el estado en SQLite (store.flush)."""
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        flush()
    return response
api = APIRouter(prefix="/api")


@api.get("/health", response_model=HealthResponse)
def health():
    s = get_settings()
    clf = get_classifier()
    return HealthResponse(status="ok", policy_version=get_policy()["policy_version"],
                          intent_model=clf.model_version if clf else "stub-keywords-0",
                          llm_model=s.gemini_model if s.gemini_api_key else f"{s.gemini_model} (sin llave: plantillas)",
                          data_manifest=data_source.source_name())


# --- Auth (sección 7) -----------------------------------------------------------

@api.get("/auth/demo-customers", response_model=DemoCustomersResponse)
def demo_customers():
    return DemoCustomersResponse(customers=[DemoCustomer(**c) for c in data_source.demo_customers()])


@api.post("/auth/login", response_model=LoginResponse)
def login(req: LoginRequest):
    customer = next((c for c in data_source.demo_customers() if c["customer_id"] == req.customer_id), None)
    if customer is None or req.otp != get_settings().demo_otp:
        raise APIError("UNAUTHENTICATED", "Cliente u OTP inválido.")
    token, exp = issue_token(customer["customer_id"], "customer", customer["suggested_language"])
    return LoginResponse(access_token=token, expires_at=exp, customer=LoginCustomer(
        customer_id=customer["customer_id"], segment=customer["segment"], country=customer["country"],
        language=customer["suggested_language"]))


@api.post("/auth/agent-login", response_model=LoginResponse)
def agent_login(req: AgentLoginRequest):
    s = get_settings()
    if req.agent_id != s.demo_agent_id or req.otp != s.demo_otp:
        raise APIError("UNAUTHENTICATED", "Agente u OTP inválido.")
    token, exp = issue_token(req.agent_id, "agent", "es")
    return LoginResponse(access_token=token, expires_at=exp)


@api.post("/auth/demo/expire", status_code=204)
def expire_session(session: Session = Depends(require_role("customer"))):
    if not get_settings().demo_mode:
        raise APIError("NOT_FOUND", "No disponible.")
    store.revoked_sessions.add(session.session_id)


# --- Chat y consultas -----------------------------------------------------------

@api.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, session: Session = Depends(require_role("customer")),
         x_fault_inject: str | None = Header(default=None, include_in_schema=False)):
    # Solo en evaluación/demo: "X-Fault-Inject: create_dispute_case" hace fallar esa herramienta.
    forced = {t.strip() for t in (x_fault_inject or "").split(",") if t.strip()}
    token = faults.set_forced(forced if get_settings().fault_injection else set())
    try:
        return handle_chat(session, req)
    finally:
        faults.reset_forced(token)


@api.get("/cases", response_model=CasesResponse)
def list_cases(session: Session = Depends(get_session)):
    all_cases = list(store.cases.values())
    if session.role == "customer":
        all_cases = [c for c in all_cases if c.customer_id == session.customer_id]
    return CasesResponse(cases=all_cases)


@api.get("/handoffs", response_model=HandoffsResponse)
def list_handoffs(_: Session = Depends(require_role("agent"))):
    return HandoffsResponse(handoffs=[HandoffSummary(
        handoff_id=h.handoff_id, case_id=h.case_id, priority=h.priority, suggested_queue=h.suggested_queue,
        language=h.language, created_at=h.created_at, handoff_reason=h.handoff_reason)
        for h in store.handoffs.values()])


@api.get("/handoffs/{handoff_id}", response_model=HandoffPackage)
def get_handoff(handoff_id: str, _: Session = Depends(require_role("agent"))):
    if handoff_id not in store.handoffs:
        raise APIError("NOT_FOUND", "Handoff no encontrado.")
    return store.handoffs[handoff_id]


@api.get("/traces/{trace_id}", response_model=Trace)
def get_trace(trace_id: str, session: Session = Depends(get_session)):
    trace = store.traces.get(trace_id)
    if trace is None or (session.role == "customer" and trace.customer_id != session.customer_id):
        raise APIError("NOT_FOUND", "Traza no encontrada.")
    if session.role == "customer":  # sin datos internos de riesgo para el cliente
        trace = trace.model_copy(deep=True)
        for turn in trace.turns:
            turn.spans = [s for s in turn.spans if s.name != "tool.get_transaction_risk"]
    return trace


# --- Operación (Fase 7) ---------------------------------------------------------------

def _percentile(values: list[int], p: float) -> int | None:
    if not values:
        return None
    values = sorted(values)
    return values[min(len(values) - 1, round(p / 100 * (len(values) - 1)))]


@api.get("/ops/metrics")
def ops_metrics(_: Session = Depends(require_role("agent"))):
    """Tablero de operación: lo que vigilaríamos en producción (docs/operations.md)."""
    turns = [t for tr in store.traces.values() for t in tr.turns]
    latencies = [t.latency_ms for t in turns if t.latency_ms is not None]
    count = lambda items: dict(sorted(Counter(i for i in items if i).items()))  # noqa: E731
    actions = [a for t in turns for a in t.actions]
    handoffs = list(store.handoffs.values())
    return {
        "conversations": len(store.traces),
        "turns": len(turns),
        "latency_ms": {"p50": _percentile(latencies, 50), "p95": _percentile(latencies, 95),
                       "max": max(latencies, default=None)},
        # Una decisión = un turno donde la política evaluó una transacción (o R1: no encontrada).
        "rules": count(t.rule_id for t in turns
                       if t.rule_id == "R1" or any(sp.name == "policy.evaluate" for sp in t.spans)),
        "intents": count(t.intent for t in turns),
        "languages": count(t.language for t in turns),
        "cases_created": sum(1 for a in actions if a.action == "create_dispute_case" and a.status == "verified"),
        "actions": count(a.status for a in actions),
        "handoffs": len(handoffs),
        "handoff_rate": round(len(handoffs) / len(store.traces), 3) if store.traces else None,
        "handoffs_by_reason": count(h.handoff_reason for h in handoffs),
        "tool_errors": count(s.name.removeprefix("tool.") for t in turns for s in t.spans
                             if s.error and s.name.startswith("tool.")),
        "cost_usd": round(sum(t.cost_usd for t in turns), 6),
    }


app.include_router(api)

# --- Frontend (build de Vite servido por FastAPI: una imagen, un link) ------------

_dist = get_settings().frontend_dist
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        return FileResponse(_dist / "index.html")
