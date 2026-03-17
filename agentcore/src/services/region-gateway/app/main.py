from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings, load_regions, get_regions, get_region_by_code
from app.proxy import region_proxy

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    logger.info("Region Gateway starting on %s:%s", settings.host, settings.port)

    regions = load_regions(settings)
    logger.info("Loaded %d region(s): %s", len(regions), [r.code for r in regions])

    yield

    await region_proxy.close()
    logger.info("Region Gateway shut down")


def create_app() -> FastAPI:
    settings = get_settings()

    application = FastAPI(
        title="Region Gateway",
        description="Cross-region dashboard proxy for AgentCore",
        version="1.0.0",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins.split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── List all regions ──────────────────────────────────────────────────

    @application.get("/api/regions")
    async def list_regions():
        """Return all registered regions (called by hub backend on behalf of root admin)."""
        regions = get_regions()
        return [
            {
                "code": r.code,
                "name": r.name,
                "is_hub": r.is_hub,
            }
            for r in regions
        ]

    # ── Proxy dashboard request to a spoke ────────────────────────────────

    @application.get("/api/regions/{region_code}/dashboard/{section:path}")
    async def proxy_dashboard(
        region_code: str,
        section: str,
        caller: str | None = Query(default=None, description="Root admin user ID"),
        org_id: str | None = Query(default=None),
        range: str | None = Query(default=None),
        tz_offset_minutes: int | None = Query(default=None),
    ):
        """Proxy a dashboard section request to the spoke region's backend.

        The hub backend calls this endpoint; the frontend never calls it directly.
        """
        region = get_region_by_code(region_code)
        if region is None:
            raise HTTPException(status_code=404, detail=f"Region '{region_code}' not found")

        # Build query params to forward (only non-None values)
        query_params: dict = {}
        if org_id:
            query_params["org_id"] = org_id
        if range:
            query_params["range"] = range
        if tz_offset_minutes is not None:
            query_params["tz_offset_minutes"] = str(tz_offset_minutes)

        try:
            data = await region_proxy.proxy_dashboard(
                region=region,
                path=f"/api/dashboard/sections/{section}",
                query_params=query_params,
                caller_user_id=caller,
            )
            return data
        except RuntimeError as e:
            # Circuit breaker open
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            logger.error("Proxy error for region '%s': %s", region_code, e, exc_info=True)
            raise HTTPException(
                status_code=502,
                detail=f"Failed to reach region '{region_code}': {type(e).__name__}",
            )

    # ── Health check for a specific spoke ─────────────────────────────────

    @application.get("/api/regions/{region_code}/health")
    async def region_health(region_code: str):
        """Check health of a specific spoke region."""
        region = get_region_by_code(region_code)
        if region is None:
            raise HTTPException(status_code=404, detail=f"Region '{region_code}' not found")

        result = await region_proxy.check_health(region)
        return {"region": region_code, **result}

    # ── Gateway's own health ──────────────────────────────────────────────

    @application.get("/health")
    async def health():
        return {"status": "ok", "service": "region-gateway"}

    return application


app = create_app()


def run():
    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
    
if __name__ == "__main__":
    run()