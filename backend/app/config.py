"""Configuración: variables de entorno + config/policy.yaml."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes"}


@dataclass(frozen=True)
class Settings:
    jwt_secret: str = field(default_factory=lambda: (os.environ.get("JWT_SECRET") or "dev-secret-solo-local-cambiar-en-env-0000"))
    jwt_ttl_minutes: int = field(default_factory=lambda: int(os.environ.get("JWT_TTL_MINUTES", "15")))
    demo_mode: bool = field(default_factory=lambda: _bool("DEMO_MODE", True))
    demo_otp: str = field(default_factory=lambda: os.environ.get("DEMO_OTP", "123456"))
    demo_agent_id: str = field(default_factory=lambda: os.environ.get("DEMO_AGENT_ID", "AGT-DEMO"))
    gemini_api_key: str | None = field(default_factory=lambda: os.environ.get("GEMINI_API_KEY") or None)
    gemini_model: str = field(default_factory=lambda: os.environ.get("GEMINI_MODEL", "sin-fijar"))
    fault_injection: bool = field(default_factory=lambda: _bool("FAULT_INJECTION", False))
    # "full" (por defecto): clasificador + Gemini. "keywords": baseline B1 de la evaluación (stub de
    # palabras clave + reglas + plantillas, sin Gemini aunque haya llave). Otro valor → "full".
    nlu_mode: str = field(default_factory=lambda: "keywords" if os.environ.get("NLU_MODE", "full").strip().lower()
                          == "keywords" else "full")
    policy_path: Path = field(default_factory=lambda: Path(os.environ.get("POLICY_PATH", ROOT / "config" / "policy.yaml")))
    gold_db_path: Path = field(default_factory=lambda: Path(os.environ.get("GOLD_DB_PATH", ROOT / "data" / "gold" / "gold.duckdb")))
    ops_db_path: Path = field(default_factory=lambda: Path(os.environ.get("OPS_DB_PATH", ROOT / "data" / "ops.sqlite")))
    frontend_dist: Path = field(default_factory=lambda: Path(os.environ.get("FRONTEND_DIST", ROOT / "frontend" / "dist")))


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_policy() -> dict:
    with open(get_settings().policy_path, encoding="utf-8") as f:
        return yaml.safe_load(f)
