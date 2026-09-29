"""API de LATAM Bank · intake de disputas (design.md, sección 6)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Header
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .auth import get_session, issue_token, require_role
from .config import get_policy, get_settings
from . import faults
from .errors import APIError, register_error_handlers
from .orchestrator import handle_chat
from .schemas import (AgentLoginRequest, CasesResponse, ChatRequest, ChatResponse, DemoCustomer,
                      DemoCustomersResponse, HandoffPackage, HandoffsResponse, HandoffSummary,
                      HealthResponse, LoginCustomer, LoginRequest, LoginResponse, Session, Trace)
from .store import store
from .tools import stub_data

app = FastAPI(title="LATAM Bank · Disputas", version="0.1.0")
register_error_handlers(app)
api = APIRouter(prefix="/api")


@api.get("/health", response_model=HealthResponse)
def health():
    s = get_settings()
    return HealthResponse(status="ok", policy_version=get_policy()["policy_version"],
                          intent_model="stub-keywords-0", llm_model=s.gemini_model, data_manifest=None)


# --- Auth (sección 7) -----------------------------------------------------------

@api.get("/auth/demo-customers", response_model=DemoCustomersResponse)
def demo_customers():
    return DemoCustomersResponse(customers=[DemoCustomer(**c) for c in stub_data.DEMO_CUSTOMERS])


@api.post("/auth/login", response_model=LoginResponse)
def login(req: LoginRequest):
    customer = next((c for c in stub_data.DEMO_CUSTOMERS if c["customer_id"] == req.customer_id), None)
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


app.include_router(api)

# --- Frontend (build de Vite servido por FastAPI: una imagen, un link) ------------

_dist = get_settings().frontend_dist
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        return FileResponse(_dist / "index.html")
