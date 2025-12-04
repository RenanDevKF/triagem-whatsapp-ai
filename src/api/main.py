"""
Aplicação FastAPI principal.
Define rotas, middlewares e configurações globais.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from loguru import logger
import time

from src.core.config import get_settings
from src.core.exceptions import BaseAppException
from src.core.logging import setup_logging, log_request
from src.infrastructure.database.session import lifespan_db, check_db_connection
from src.api.routes import webhooks, leads, conversations, health

settings = get_settings()


# ========================================
# LIFESPAN (startup/shutdown)
# ========================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Gerencia o ciclo de vida da aplicação.
    Executa setup no startup e cleanup no shutdown.
    """
    # ========== STARTUP ==========
    logger.info(f"🚀 Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    
    # Setup logging
    setup_logging()
    
    # Inicializa banco de dados
    async with lifespan_db():
        logger.success("✅ Database initialized")
        
        # Valida configurações críticas
        if not settings.whatsapp_access_token:
            logger.warning("⚠️  WhatsApp access token not configured")
        
        if not settings.gemini_api_key:
            logger.warning("⚠️  Gemini API key not configured")
        
        logger.success(f"✅ {settings.app_name} is ready!")
        
        yield
    
    # ========== SHUTDOWN ==========
    logger.info("Shutting down application...")
    logger.success("👋 Goodbye!")


# ========================================
# APP INSTANCE
# ========================================

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Sistema inteligente de triagem de leads via WhatsApp",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    openapi_url="/openapi.json" if settings.is_development else None,
)


# ========================================
# MIDDLEWARES
# ========================================

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Compressão GZIP
app.add_middleware(GZipMiddleware, minimum_size=1000)


# Middleware de logging de requisições
@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    """Loga todas as requisições HTTP com tempo de processamento"""
    
    start_time = time.time()
    
    # Processa requisição
    response = await call_next(request)
    
    # Calcula duração
    duration_ms = (time.time() - start_time) * 1000
    
    # Loga (skip health checks para não poluir logs)
    if request.url.path != "/health":
        log_request(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms
        )
    
    # Adiciona headers de timing
    response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"
    
    return response


# Middleware de rate limiting (básico)
# TODO: Implementar rate limiting robusto com Redis se necessário
request_counts: dict[str, list[float]] = {}

@app.middleware("http")
async def simple_rate_limiter(request: Request, call_next):
    """
    Rate limiter simples baseado em IP.
    Limite: 60 requisições por minuto por IP.
    """
    
    # Apenas para endpoints não-críticos (skip webhooks)
    if request.url.path.startswith("/webhooks"):
        return await call_next(request)
    
    client_ip = request.client.host if request.client else "unknown"
    current_time = time.time()
    
    # Limpa requests antigos (>1 minuto)
    if client_ip in request_counts:
        request_counts[client_ip] = [
            t for t in request_counts[client_ip]
            if current_time - t < 60
        ]
    else:
        request_counts[client_ip] = []
    
    # Verifica limite
    if len(request_counts[client_ip]) >= settings.rate_limit_per_minute:
        logger.warning(f"Rate limit exceeded for {client_ip}")
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "Rate limit exceeded",
                "message": f"Maximum {settings.rate_limit_per_minute} requests per minute"
            }
        )
    
    # Registra request
    request_counts[client_ip].append(current_time)
    
    return await call_next(request)


# ========================================
# EXCEPTION HANDLERS
# ========================================

@app.exception_handler(BaseAppException)
async def app_exception_handler(request: Request, exc: BaseAppException):
    """Handler para exceções customizadas da aplicação"""
    
    logger.error(f"Application error: {exc.message}", extra=exc.details)
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.message,
            "details": exc.details
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handler para erros de validação do Pydantic"""
    
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    logger.warning(f"Validation error: {errors}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation error",
            "details": errors
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handler global para exceções não tratadas"""
    
    logger.exception(f"Unhandled exception: {exc}")
    
    # Em produção, não expõe detalhes do erro
    if settings.is_production:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "message": "An unexpected error occurred"
            }
        )
    
    # Em desenvolvimento, mostra stack trace
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "message": str(exc),
            "type": type(exc).__name__
        }
    )


# ========================================
# ROTAS
# ========================================

# Incluir routers
app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
app.include_router(leads.router, prefix="/api/leads", tags=["Leads"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["Conversations"])


# Root endpoint
@app.get("/", include_in_schema=False)
async def root():
    """Endpoint raiz"""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs" if settings.is_development else "disabled",
        "health": "/health"
    }


# ========================================
# DEBUG INFO (apenas desenvolvimento)
# ========================================

if settings.is_development:
    @app.get("/debug/config", include_in_schema=False)
    async def debug_config():
        """Mostra configurações (sem secrets)"""
        return settings.model_dump_safe()
    
    @app.get("/debug/db", include_in_schema=False)
    async def debug_db():
        """Testa conexão com banco"""
        is_connected = await check_db_connection()
        return {
            "database_connected": is_connected,
            "database_url": settings.database_url.split("@")[0] + "@***"
        }


# ========================================
# STARTUP MESSAGE
# ========================================

@app.on_event("startup")
async def startup_message():
    """Mensagem de boas-vindas no console"""
    logger.info("=" * 60)
    logger.info(f"  {settings.app_name} v{settings.app_version}")
    logger.info(f"  Environment: {settings.environment}")
    logger.info(f"  Listening on: http://{settings.api_host}:{settings.api_port}")
    logger.info(f"  Docs: http://{settings.api_host}:{settings.api_port}/docs")
    logger.info("=" * 60)