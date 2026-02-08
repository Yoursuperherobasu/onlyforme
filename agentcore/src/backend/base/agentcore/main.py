import asyncio
import json
import os
import re
import warnings
from contextlib import asynccontextmanager
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlencode
import builtins
from agentcore.services.auth.decorators import verify_permissions
builtins.verify_permissions = verify_permissions
import sys

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from langfuse import get_client
from importlib.metadata import version
print("Langfuse version:", version("langfuse"))
client = get_client()
print("Langfuse class:", type(client))
print("Langfuse version:", getattr(client, "__module__", "unknown"))

# DEBUG: Print LANGFUSE env vars at startup
import sys as _sys
print("[STARTUP] Checking LANGFUSE env vars after load_dotenv():")
_sys.stdout.flush()
for _k, _v in os.environ.items():
    if 'LANGFUSE' in _k.upper():
        print(f"  {_k}={'SET' if _v else 'NOT SET'} (len={len(_v) if _v else 0})")
        _sys.stdout.flush()
print("[STARTUP] End of LANGFUSE env vars check")
_sys.stdout.flush()


import anyio
import sqlalchemy
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi_pagination import add_pagination
from loguru import logger
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import PydanticDeprecatedSince20
from pydantic_core import PydanticSerializationError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from agentcore.api import health_check_router, log_router, router
from agentcore.api.openai_compat_router import router as openai_router
from agentcore.api.mcp_projects import init_mcp_servers
from agentcore.interface.components import get_and_cache_all_types_dict
from agentcore.interface.utils import setup_llm_caching
from agentcore.logging.logger import configure
from agentcore.middleware import ContentSizeLimitMiddleware
from agentcore.services.deps import (
    get_queue_service,
    get_settings_service,
    get_telemetry_service,
)
from agentcore.services.utils import initialize_services, teardown_services

if TYPE_CHECKING:
    from tempfile import TemporaryDirectory

# Ignore Pydantic deprecation warnings from Langchain
warnings.filterwarnings("ignore", category=PydanticDeprecatedSince20)

_tasks: list[asyncio.Task] = []

MAX_PORT = 65535


class RequestCancelledMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        sentinel = object()

        async def cancel_handler():
            while True:
                if await request.is_disconnected():
                    return sentinel
                await asyncio.sleep(0.1)

        handler_task = asyncio.create_task(call_next(request))
        cancel_task = asyncio.create_task(cancel_handler())

        done, pending = await asyncio.wait([handler_task, cancel_task], return_when=asyncio.FIRST_COMPLETED)

        for task in pending:
            task.cancel()

        if cancel_task in done:
            return Response("Request was cancelled", status_code=499)
        return await handler_task


class JavaScriptMIMETypeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            response = await call_next(request)
        except Exception as exc:
            if isinstance(exc, PydanticSerializationError):
                message = (
                    "Something went wrong while serializing the response. "
                    "Please share this error on our GitHub repository."
                )
                error_messages = json.dumps([message, str(exc)])
                raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=error_messages) from exc
            raise
        if (
            "files/" not in request.url.path
            and request.url.path.endswith(".js")
            and response.status_code == HTTPStatus.OK
        ):
            response.headers["Content-Type"] = "text/javascript"
        return response


def get_lifespan(*, fix_migration=True, version=None):
    telemetry_service = get_telemetry_service()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        configure(async_file=True)

        # Startup message
        if version:
            logger.debug(f"Starting Agentcore v{version}...")
        else:
            logger.debug("Starting Agentcore...")

        temp_dirs: list[TemporaryDirectory] = []

        try:
            start_time = asyncio.get_event_loop().time()

            logger.debug("Initializing services")
            await initialize_services(fix_migration=fix_migration)
            logger.debug(f"Services initialized in {asyncio.get_event_loop().time() - start_time:.2f}s")

            current_time = asyncio.get_event_loop().time()
            logger.debug("Setting up LLM caching")
            setup_llm_caching()
            logger.debug(f"LLM caching setup in {asyncio.get_event_loop().time() - current_time:.2f}s")

            current_time = asyncio.get_event_loop().time()
            logger.debug("Caching types")
            all_types_dict = await get_and_cache_all_types_dict(get_settings_service())
            logger.debug(f"Types cached in {asyncio.get_event_loop().time() - current_time:.2f}s")

            current_time = asyncio.get_event_loop().time()
            logger.debug("Starting telemetry service")
            telemetry_service.start()
            logger.debug(f"started telemetry service in {asyncio.get_event_loop().time() - current_time:.2f}s")

            current_time = asyncio.get_event_loop().time()
            queue_service = get_queue_service()
            if not queue_service.is_started():  # Start if not already started
                queue_service.start()
            logger.debug(f"Flows loaded in {asyncio.get_event_loop().time() - current_time:.2f}s")

            current_time = asyncio.get_event_loop().time()
            logger.debug("Loading mcp servers for projects")
            await init_mcp_servers()
            logger.debug(f"mcp servers loaded in {asyncio.get_event_loop().time() - current_time:.2f}s")

            total_time = asyncio.get_event_loop().time() - start_time
            logger.debug(f"Total initialization time: {total_time:.2f}s")
            yield

        except asyncio.CancelledError:
            logger.debug("Lifespan received cancellation signal")
        except Exception as exc:
            if "agentcore migration --fix" not in str(exc):
                logger.exception(exc)
            raise
        finally:
            # Clean shutdown
            try:
                # Stopping Server
                logger.debug("Stopping server gracefully...")

                # Cleaning Up Services
                try:
                    await asyncio.wait_for(teardown_services(), timeout=10)
                except asyncio.TimeoutError:
                    logger.warning("Teardown services timed out.")

                # Clearing Temporary Files
                temp_dir_cleanups = [asyncio.to_thread(temp_dir.cleanup) for temp_dir in temp_dirs]
                await asyncio.gather(*temp_dir_cleanups)

                # Finalizing Shutdown
                logger.debug("Agentcore shutdown complete")

            except (sqlalchemy.exc.OperationalError, sqlalchemy.exc.DBAPIError) as e:
                # Case where the database connection is closed during shutdown
                logger.warning(f"Database teardown failed due to closed connection: {e}")
            except asyncio.CancelledError:
                # Swallow this - it's normal during shutdown
                logger.debug("Teardown cancelled during shutdown.")
            except Exception as e:  # noqa: BLE001
                logger.exception(f"Unhandled error during cleanup: {e}")

            try:
                await asyncio.shield(asyncio.sleep(0.1))  # let logger flush async logs
                await asyncio.shield(logger.complete())
            except asyncio.CancelledError:
                # Cancellation during logger flush is possible during shutdown, so we swallow it
                pass

    return lifespan


def create_app():
    """Create the FastAPI app and include the router."""
    from agentcore.utils.version import get_version_info
   
    
    
    DB_URL = os.getenv("DATABASE_URL")
    print("Database URL:", DB_URL)  # For debugging purposes only; remove in production

    __version__ = get_version_info()["version"]
    configure()
    lifespan = get_lifespan(version=__version__)
    app = FastAPI(
        title="AgentCore",
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(
        ContentSizeLimitMiddleware,
    )

    setup_sentry(app)
    origins = ["http://localhost:3000","http://localhost:8767"]
    # origins = os.getenv("CORS_ALLOWED_ORIGINS".split(",") if os.getenv("CORS_ALLOWED_ORIGINS") else [["http://localhost:3000","http://localhost:8767"]])

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(JavaScriptMIMETypeMiddleware)

    @app.middleware("http")
    async def check_boundary(request: Request, call_next):
        if "/api/v1/files/upload" in request.url.path:
            content_type = request.headers.get("Content-Type")

            if not content_type or "multipart/form-data" not in content_type or "boundary=" not in content_type:
                return JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    content={"detail": "Content-Type header must be 'multipart/form-data' with a boundary parameter."},
                )

            boundary = content_type.split("boundary=")[-1].strip()

            if not re.match(r"^[\w\-]{1,70}$", boundary):
                return JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    content={"detail": "Invalid boundary format"},
                )

            body = await request.body()

            boundary_start = f"--{boundary}".encode()
            # The multipart/form-data spec doesn't require a newline after the boundary, however many clients do
            # implement it that way
            boundary_end = f"--{boundary}--\r\n".encode()
            boundary_end_no_newline = f"--{boundary}--".encode()

            if not body.startswith(boundary_start) or not body.endswith((boundary_end, boundary_end_no_newline)):
                return JSONResponse(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    content={"detail": "Invalid multipart formatting"},
                )

        return await call_next(request)

    @app.middleware("http")
    async def flatten_query_string_lists(request: Request, call_next):
        flattened: list[tuple[str, str]] = []
        for key, value in request.query_params.multi_items():
            flattened.extend((key, entry) for entry in value.split(","))

        request.scope["query_string"] = urlencode(flattened, doseq=True).encode("utf-8")

        return await call_next(request)

    settings = get_settings_service().settings
    if prome_port_str := os.environ.get("PROMETHEUS_PORT"):
        # set here for create_app() entry point
        prome_port = int(prome_port_str)
        if prome_port > 0 or prome_port < MAX_PORT:
            logger.debug(f"Starting Prometheus server on port {prome_port}...")
            settings.prometheus_enabled = True
            settings.prometheus_port = prome_port
        else:
            msg = f"Invalid port number {prome_port_str}"
            raise ValueError(msg)

    if settings.mcp_server_enabled:
        from agentcore.api import mcp_router

        router.include_router(mcp_router)

    app.include_router(router)
    app.include_router(health_check_router)
    app.include_router(log_router)
    app.include_router(openai_router, prefix="")

    @app.exception_handler(Exception)
    async def exception_handler(_request: Request, exc: Exception):
        if isinstance(exc, HTTPException):
            logger.error(f"HTTPException: {exc}", exc_info=exc)
            return JSONResponse(
                status_code=exc.status_code,
                content={"message": str(exc.detail)},
            )
        logger.error(f"unhandled error: {exc}", exc_info=exc)
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content={"message": str(exc)},
        )

    # Exclude API routes from OTEL instrumentation to prevent HTTP traces
    # from polluting Langfuse with "POST /api/v1/..." instead of actual flow names.
    # Flow tracing is handled separately by the TracingService with proper names.
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="/api/.*,/health,/health_check",
    )

    add_pagination(app)

    return app


def setup_sentry(app: FastAPI) -> None:
    settings = get_settings_service().settings
    if settings.sentry_dsn:
        import sentry_sdk
        from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            profiles_sample_rate=settings.sentry_profiles_sample_rate,
        )
        app.add_middleware(SentryAsgiMiddleware)


def setup_static_files(app: FastAPI, static_files_dir: Path) -> None:
    """Setup the static files directory.

    Args:
        app (FastAPI): FastAPI app.
        static_files_dir (str): Path to the static files directory.
    """
    app.mount(
        "/",
        StaticFiles(directory=static_files_dir, html=True),
        name="static",
    )

    @app.exception_handler(404)
    async def custom_404_handler(_request, _exc):
        path = anyio.Path(static_files_dir) / "index.html"

        if not await path.exists():
            msg = f"File at path {path} does not exist."
            raise RuntimeError(msg)
        return FileResponse(path)


def get_static_files_dir():
    """Get the static files directory relative to Agentcore's main.py file."""
    frontend_path = Path(__file__).parent
    return frontend_path / "frontend"


def setup_app(static_files_dir: Path | None = None, *, backend_only: bool = False) -> FastAPI:
    """Setup the FastAPI app."""
    # get the directory of the current file
    if not static_files_dir:
        static_files_dir = get_static_files_dir()

    if not backend_only and (not static_files_dir or not static_files_dir.exists()):
        msg = f"Static files directory {static_files_dir} does not exist."
        raise RuntimeError(msg)
    app = create_app()

    if not backend_only and static_files_dir is not None:
        setup_static_files(app, static_files_dir)
    return app


if __name__ == "__main__":
    import uvicorn

    from agentcore.__main__ import get_number_of_workers

    configure()
    uvicorn.run(
        "agentcore.main:create_app",
        host="127.0.0.1",
        port=7860,
        workers=get_number_of_workers(),
        log_level="error",
        reload=True,
        loop="asyncio",
    )
