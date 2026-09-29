"""Autenticación de prueba (design.md, sección 7). Identidad SIMULADA."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings
from .errors import APIError
from .schemas import Session
from .store import store

ALGORITHM = "HS256"
bearer = HTTPBearer(auto_error=False)


def issue_token(subject: str, role: str, language: str) -> tuple[str, datetime]:
    s = get_settings()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=s.jwt_ttl_minutes)
    claims = {"sub": subject, "role": role, "sid": uuid.uuid4().hex, "lang": language,
              "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    return jwt.encode(claims, s.jwt_secret, algorithm=ALGORITHM), exp


def decode_token(token: str) -> Session:
    try:
        claims = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise APIError("SESSION_EXPIRED", "La sesión expiró. Vuelve a ingresar.")
    except jwt.PyJWTError:
        raise APIError("UNAUTHENTICATED", "Token inválido.")
    if claims["sid"] in store.revoked_sessions:
        raise APIError("SESSION_EXPIRED", "La sesión expiró. Vuelve a ingresar.")
    return Session(session_id=claims["sid"], customer_id=claims["sub"], role=claims["role"],
                   language=claims["lang"], expires_at=datetime.fromtimestamp(claims["exp"], timezone.utc))


def get_session(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Session:
    """customer_id sale SIEMPRE de aquí: nunca del cuerpo, del mensaje ni del LLM."""
    if creds is None or creds.scheme.lower() != "bearer":
        raise APIError("UNAUTHENTICATED", "Falta el token.")
    return decode_token(creds.credentials)


def require_role(*roles: str):
    def dep(session: Session = Depends(get_session)) -> Session:
        if session.role not in roles:
            raise APIError("FORBIDDEN", "No tienes permiso para este recurso.")
        return session
    return dep
