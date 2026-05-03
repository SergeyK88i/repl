from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from agents.coordinator.api.routes import router as coordinator_router
from agents.cr_manager.api.routes import router as cr_manager_router

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(title="Agentic Replica Readiness Platform")
    app.include_router(coordinator_router)
    app.include_router(cr_manager_router)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def index() -> str:
        return (STATIC_DIR / "agent_console.html").read_text(encoding="utf-8")

    @app.get("/console", response_class=HTMLResponse, include_in_schema=False)
    async def console() -> str:
        return (STATIC_DIR / "agent_console.html").read_text(encoding="utf-8")

    @app.get("/internal-delivery-status-2026", response_class=HTMLResponse, include_in_schema=False)
    async def internal_delivery_status() -> str:
        return (STATIC_DIR / "product_status_dashboard.html").read_text(encoding="utf-8")

    @app.get("/product", response_class=HTMLResponse, include_in_schema=False)
    async def product_dashboard() -> str:
        return (STATIC_DIR / "executive_product_dashboard.html").read_text(encoding="utf-8")

    return app


app = create_app()
